#!/usr/bin/env python3
"""ReadFuse checkpoint utility; does not invoke a language model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

CHUNK_ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$')
KINDS = ('translation', 'summary')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def safe_path(job, name):
    """Accept only paths within the job folder, including via symlinks."""
    p = Path(name)
    path = (p if p.is_absolute() else job / p).resolve()
    if not path.is_relative_to(job.resolve()):
        raise ValueError(f'Path escapes job directory: {name}')
    return path


def relpath(job, path):
    return str(path.relative_to(job.resolve())).replace(os.sep, '/')


def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.readfuse-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_state(job):
    path = job / 'state' / 'checkpoint.json'
    if not path.is_file():
        raise ValueError('Job not initialized; run init first')
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def save_state(job, state):
    atomic_json(job / 'state' / 'checkpoint.json', state)


def init(job, manifest_path):
    if (job / 'state' / 'checkpoint.json').exists():
        raise ValueError('Job already initialized; existing checkpoint preserved')
    with manifest_path.open(encoding='utf-8') as f:
        manifest = json.load(f)
    if manifest.get('version') != 1 or manifest.get('mode') not in ('translate', 'summarize', 'both'):
        raise ValueError('Unsupported manifest version or mode')
    chunks = manifest.get('chunks')
    if not isinstance(chunks, list) or not chunks:
        raise ValueError('Manifest needs nonempty chunks')
    seen = set()
    rows = {}
    for ch in chunks:
        key = ch.get('id')
        if not isinstance(key, str) or not CHUNK_ID.fullmatch(key) or key in seen:
            raise ValueError(f'Duplicate/invalid chunk ID: {key}')
        seen.add(key)
        src = safe_path(job, ch['source_path'])
        if not src.is_file() or not src.read_bytes().strip():
            raise ValueError(f'Missing/empty source: {src}')
        rows[key] = {'source_path': relpath(job, src), 'source_sha256': digest(src), 'outputs': {}}
    state = {'version': 1, 'manifest_sha256': digest(manifest_path), 'mode': manifest['mode'], 'order': list(rows), 'chunks': rows}
    save_state(job, state)
    print(f'Initialized {len(rows)} chunks in {job}')


def required_kinds(mode):
    return {'translate': ['translation'], 'summarize': ['summary'], 'both': list(KINDS)}[mode]


def check(job, state):
    issues = []
    counts = {k: 0 for k in ('complete', 'pending', 'invalid')}
    for key in state['order']:
        ch = state['chunks'][key]
        try:
            src = safe_path(job, ch['source_path'])
            if not src.is_file() or digest(src) != ch['source_sha256']:
                raise ValueError('missing or changed source')
            for kind, output in ch['outputs'].items():
                target = safe_path(job, output['path'])
                if not target.is_file() or digest(target) != output['sha256']:
                    raise ValueError(f'{kind}: missing or modified output')
            done = all(k in ch['outputs'] for k in required_kinds(state['mode']))
            counts['complete' if done else 'pending'] += 1
        except (ValueError, KeyError, OSError) as exc:
            counts['invalid'] += 1
            issues.append(f'{key}: {exc}')
    return counts, issues


def complete(job, chunk_id, kind, output_file):
    state = load_state(job)
    if chunk_id not in state['chunks']:
        raise ValueError(f'Unknown chunk: {chunk_id}')
    if kind not in required_kinds(state['mode']):
        raise ValueError(f'Output kind not requested by job mode: {kind}')
    ch = state['chunks'][chunk_id]
    src = safe_path(job, ch['source_path'])
    if not src.is_file() or digest(src) != ch['source_sha256']:
        raise ValueError('Source changed since job initialization')
    out = safe_path(job, output_file)
    if not out.is_file() or not out.read_bytes().strip():
        raise ValueError('Output missing or empty')
    if out == src or out == job / 'state' / 'checkpoint.json':
        raise ValueError('Output cannot overwrite source or checkpoint')
    out.read_text(encoding='utf-8')  # ensure readable text
    ch['outputs'][kind] = {'path': relpath(job, out), 'sha256': digest(out)}
    save_state(job, state)
    print(f'Completed {chunk_id}: {kind} (hash recorded, semantic QA not included)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init')
    p.add_argument('--job-dir', required=True)
    p.add_argument('--manifest', required=True)
    for command in ('status', 'verify'):
        p = sub.add_parser(command)
        p.add_argument('--job-dir', required=True)
    p = sub.add_parser('complete')
    p.add_argument('--job-dir', required=True)
    p.add_argument('--chunk-id', required=True)
    p.add_argument('--kind', required=True, choices=KINDS)
    p.add_argument('--output', required=True)
    a = parser.parse_args()
    try:
        job = Path(a.job_dir).resolve()
        if a.command == 'init':
            init(job, Path(a.manifest).resolve())
        elif a.command == 'complete':
            complete(job, a.chunk_id, a.kind, a.output)
        else:
            counts, issues = check(job, load_state(job))
            print(json.dumps({'counts': counts, 'issues': issues}, indent=2))
            if a.command == 'verify' and issues:
                return 1
    except (ValueError, OSError, json.JSONDecodeError, UnicodeError, KeyError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
