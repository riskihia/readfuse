"""Version-2 job persistence, artifact provenance, and honest completion reports."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from .sources import sha, validate_index
from .selection import merge_coverage


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def fingerprint(obj):
    return sha(encoded(obj))


def safe_path(job, name):
    job = Path(job).resolve()
    path = Path(name)
    lexical = Path(os.path.abspath(path if path.is_absolute() else job / path))
    path = lexical.resolve()
    if path != lexical:
        raise ValueError(f'Symlink/reparse artifact paths are not supported: {name}')
    if not path.is_relative_to(job) or path == job:
        raise ValueError(f'Path escapes job directory: {name}')
    return path


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.readfuse-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def job_lock(job):
    job = Path(job).resolve()
    lock = safe_path(job, 'state/.write.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError(f'Job is locked: {lock}. Verify the owner is stopped before manual recovery.') from exc
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(f'pid={os.getpid()}\n')
        yield
    finally:
        lock.unlink()


def validate_config(config):
    if not isinstance(config, dict) or config.get('mode') not in ('learning', 'translate', 'summarize'):
        raise ValueError('Config mode must be learning, translate, or summarize')
    if any(not isinstance(config.get(k), str) or not config[k].strip() for k in ('source_language', 'target_language')):
        raise ValueError('Config requires source_language and target_language')
    if config.get('notes_policy', 'selective') not in ('selective', 'none'):
        raise ValueError('notes_policy must be selective or none')


def save(job, state):
    state['revision'] += 1
    atomic_write(safe_path(job, 'state/checkpoint.json'), encoded(state))


def init_job(job: Path, index: dict, config: dict) -> None:
    job = Path(job).resolve()
    validate_index(index)
    validate_config(config)
    source = Path(index['source']['path']).resolve()
    if source.is_relative_to(job):
        raise ValueError('Original source must be outside the generated job directory')
    if sha(source.read_bytes()) != index['source']['sha256']:
        raise ValueError('Original source changed since inspection')
    with job_lock(job):
        if safe_path(job, 'state/checkpoint.json').exists():
            raise ValueError('Existing job preserved; use status/select to continue')
        state = {'version': 2, 'index': index, 'index_sha256': fingerprint(index), 'config': config,
                 'config_sha256': fingerprint(config), 'selected': [], 'artifacts': {}, 'failures': {}, 'revision': 0}
        save(job, state)


def load_job(job: Path) -> dict:
    try:
        state = json.loads(safe_path(job, 'state/checkpoint.json').read_text(encoding='utf-8'))
        if state['version'] != 2:
            raise ValueError('Version-1/unknown jobs require the legacy checkpoint utility; no automatic migration')
        validate_index(state['index'])
        validate_config(state['config'])
        if fingerprint(state['index']) != state['index_sha256'] or fingerprint(state['config']) != state['config_sha256']:
            raise ValueError('Persisted index/config fingerprint changed; create a compatible new job')
        if merge_coverage(state['index'], [], state['selected']) != state['selected']:
            raise ValueError('Selected coverage is malformed')
        if not isinstance(state['artifacts'], dict) or not isinstance(state['failures'], dict) or type(state['revision']) is not int:
            raise ValueError('Malformed job records')
        owners = {}
        for key, artifact in state['artifacts'].items():
            kind, unit = key.split(':', 1)
            if artifact['kind'] != kind or artifact['unit_id'] != unit:
                raise ValueError('Artifact key mismatch')
            dependencies(state, kind, unit, artifact.get('segment_ids'))
            if not isinstance(artifact['dependency'], str) or len(artifact['sha256']) != 64:
                raise ValueError('Malformed artifact hashes')
            # Stale dependencies are valid persisted history, not malformed state.
            validate_artifact_path(job, state, artifact['path'], key, owners=owners)
        return state
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('Malformed version-2 checkpoint') from exc


def assert_source(state):
    src = Path(state['index']['source']['path'])
    if not src.is_file() or sha(src.read_bytes()) != state['index']['source']['sha256']:
        raise ValueError('Original source missing/changed; inspect into a new job')


def extend_selection(job: Path, selection: dict) -> None:
    with job_lock(job):
        state = load_job(job)
        assert_source(state)
        added = selection.get('segment_ids')
        if not isinstance(added, list) or not added:
            raise ValueError('Empty/invalid selection')
        state['selected'] = merge_coverage(state['index'], state['selected'], added)
        save(job, state)


def chapter_ids(state, cid):
    chapter = next((c for c in state['index']['chapters'] if c['id'] == cid), None)
    if chapter is None:
        raise ValueError(f'Unknown chapter: {cid}')
    return [sid for sid in chapter['segment_ids'] if sid in state['selected']]


def dependencies(state, kind, unit, coverage=None):
    segments = {s['id']: s for s in state['index']['segments']}
    if kind in ('translation', 'notes'):
        if unit not in segments or unit not in state['selected']:
            raise ValueError(f'Unknown/unselected segment: {unit}')
        ids = [unit]
        if coverage is not None and coverage != ids:
            raise ValueError('Artifact segment coverage mismatch')
    elif kind == 'heading':
        chapter_ids(state, unit)
        chapter = next(c for c in state['index']['chapters'] if c['id'] == unit)
        return {'config': state['config_sha256'], 'chapter_id': unit, 'source_title': chapter['title']}
    elif kind == 'summary':
        ids = chapter_ids(state, unit)
        if not ids:
            raise ValueError('Summary chapter has no selected coverage')
        if coverage is not None:
            # Permit old summaries over a prior subset; fingerprint marks them stale.
            if not coverage or any(sid not in ids for sid in coverage) or len(set(coverage)) != len(coverage):
                raise ValueError('Invalid summary source coverage')
    else:
        raise ValueError(f'Unsupported artifact kind: {kind}')
    result = {'config': state['config_sha256'], 'sources': [(sid, segments[sid]['sha256']) for sid in ids]}
    if kind == 'notes':
        translation = state['artifacts'].get(f'translation:{unit}')
        result['translation'] = translation['sha256'] if translation else None
    return result


def same_file(first, second):
    return first == second or (first.exists() and second.exists() and first.samefile(second))


def validate_artifact_path(job, state, name, key, *, owners=None):
    path = safe_path(job, name)
    relative = path.relative_to(Path(job).resolve()).as_posix()
    if relative.split('/')[0].casefold() in ('state', 'edition') or same_file(path, Path(state['index']['source']['path']).resolve()):
        raise ValueError('Artifact cannot alias source, state, or assembled edition')
    if owners is None:
        for other_key, other in state['artifacts'].items():
            if other_key != key and same_file(path, safe_path(job, other['path'])):
                raise ValueError('Artifact path already owned by another unit')
    else:
        identities = [path]
        if path.exists():
            stat = path.stat()
            if stat.st_ino:
                identities.append((stat.st_dev, stat.st_ino))
        for identity in identities:
            if identity in owners and owners[identity] != key:
                raise ValueError('Artifact path already owned by another unit')
            owners[identity] = key
    return path, relative


def validate_notes(text, unit):
    try:
        obj = json.loads(text)
        if obj.get('reviewed') is not True or not isinstance(obj['notes'], list):
            raise ValueError('Notes must include reviewed:true and a notes list')
        for note in obj['notes']:
            if note.get('anchor') != unit or not isinstance(note.get('text'), str) or not note['text'].strip():
                raise ValueError('Invalid explanatory note anchor/text')
        return obj
    except (TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid notes JSON') from exc


def record_artifact(job: Path, artifact: dict) -> None:
    with job_lock(job):
        state = load_job(job)
        assert_source(state)
        try:
            kind, unit = artifact['kind'], artifact['unit_id']
            key = f'{kind}:{unit}'
            dep = dependencies(state, kind, unit, artifact.get('segment_ids'))
            if kind == 'summary' and artifact.get('segment_ids') != chapter_ids(state, unit):
                raise ValueError('New summary must cover exactly the selected source portions in order')
            path, relative = validate_artifact_path(job, state, artifact['path'], key)
            text = path.read_text(encoding='utf-8')
            if not text.strip():
                raise ValueError('Artifact is empty')
            if kind == 'heading' and len(text.strip().splitlines()) != 1:
                raise ValueError('Translated chapter heading must be a single line')
            if kind == 'notes':
                if f'translation:{unit}' not in state['artifacts']:
                    raise ValueError('Translate before reviewing explanatory notes')
                validate_notes(text, unit)
            mode = state['config']['mode']
            if (mode == 'translate' and kind not in ('translation', 'heading')) or (mode == 'summarize' and kind not in ('summary', 'heading')):
                raise ValueError('Artifact kind not requested by job mode')
            state['artifacts'][key] = {'kind': kind, 'unit_id': unit, 'path': relative, 'sha256': sha(path.read_bytes()),
                                       'segment_ids': artifact.get('segment_ids', [unit]), 'dependency': fingerprint(dep)}
            state['failures'].pop(key, None)
            save(job, state)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('Malformed artifact record') from exc


def required_units(state):
    mode = state['config']['mode']
    keys = [f'heading:{c["id"]}' for c in state['index']['chapters'] if chapter_ids(state, c['id'])]
    for sid in state['selected']:
        if mode != 'summarize':
            keys.append(f'translation:{sid}')
        if mode == 'learning' and state['config'].get('notes_policy', 'selective') != 'none':
            keys.append(f'notes:{sid}')
    if mode != 'translate':
        keys += [f'summary:{c["id"]}' for c in state['index']['chapters'] if chapter_ids(state, c['id'])]
    return keys


def record_failure(job: Path, unit_id: str, reason: str) -> None:
    with job_lock(job):
        state = load_job(job)
        if unit_id not in required_units(state) or not isinstance(reason, str) or not reason.strip():
            raise ValueError('Failure needs a required unit ID and a reason')
        state['failures'][unit_id] = reason
        save(job, state)


def report(job, state):
    issues, stale, valid = [], [], []
    try:
        assert_source(state)
    except (ValueError, OSError) as exc:
        issues.append(str(exc))
    for key, artifact in state['artifacts'].items():
        try:
            path = safe_path(job, artifact['path'])
            if not path.is_file() or sha(path.read_bytes()) != artifact['sha256']:
                raise ValueError('missing/modified output')
            dep = dependencies(state, artifact['kind'], artifact['unit_id'], artifact['segment_ids'])
            if fingerprint(dep) != artifact['dependency']:
                stale.append(key)
            else:
                valid.append(key)
        except (ValueError, OSError) as exc:
            issues.append(f'{key}: {exc}')
    pending = [key for key in required_units(state) if key not in valid]
    complete = bool(state['selected']) and not issues and not pending and not state['failures']
    index = state['index']
    source_coverage_complete = True
    if index['source']['format'] == 'pdf':
        covered_pages = {a['page'] for s in index['segments'] for a in s['anchors']}
        source_coverage_complete = covered_pages == set(range(1, index['page_count'] + 1))
    return {'issues': issues, 'pending': pending, 'stale': stale, 'failed': state['failures'], 'valid': valid,
            'selected': state['selected'], 'requested_complete': complete,
            'book_complete': complete and source_coverage_complete and len(state['selected']) == len(index['segments']),
            'source_coverage_complete': source_coverage_complete,
            'revision': state['revision'], 'warnings': state['index']['warnings']}


def status(job: Path, *, expected_config=None) -> dict:
    state = load_job(job)
    if expected_config is not None and fingerprint(expected_config) != state['config_sha256']:
        raise ValueError('Incompatible configuration; create a new job rather than reusing old outputs')
    return report(job, state)
