"""Validate semantic-review records and bind them to current job inputs.

This module checks provenance and report structure only. It cannot determine
whether a translation is semantically correct.
"""
from pathlib import Path, PurePosixPath
import re

from .sources import sha

CHECKS = ('completeness', 'polarity_modality', 'relations_details',
          'terminology', 'references_structure', 'fluency')
FINDING_CATEGORIES = {'omission', 'addition', 'meaning', 'detail',
                      'reference', 'source_uncertainty', 'style'}
SUBSTANTIVE = FINDING_CATEGORIES - {'style'}
HASH = re.compile(r'^[0-9a-f]{64}$')


def review_dependency(state: dict, chapter_id: str) -> dict:
    """Return the current chapter-local source/config/content snapshot."""
    chapter = next((c for c in state['index']['chapters'] if c['id'] == chapter_id), None)
    if chapter is None:
        raise ValueError(f'Unknown chapter: {chapter_id}')
    selected = set(state['selected'])
    coverage = [sid for sid in chapter['segment_ids'] if sid in selected]
    if not coverage:
        raise ValueError(f'Chapter has no selected coverage: {chapter_id}')
    sources = {s['id']: s['sha256'] for s in state['index']['segments']}
    content = {f'heading:{chapter_id}': _artifact_hash(state, f'heading:{chapter_id}')}
    mode = state['config']['mode']
    if mode != 'summarize':
        for sid in coverage:
            content[f'translation:{sid}'] = _artifact_hash(state, f'translation:{sid}')
            if mode == 'learning' and state['config'].get('notes_policy', 'selective') != 'none':
                content[f'notes:{sid}'] = _artifact_hash(state, f'notes:{sid}')
    if mode != 'translate':
        content[f'summary:{chapter_id}'] = _artifact_hash(state, f'summary:{chapter_id}')
    return {'chapter_id': chapter_id, 'coverage': coverage,
            'source_sha256': state['index']['source']['sha256'],
            'source_segments': {sid: sources[sid] for sid in coverage},
            'config_sha256': state['config_sha256'], 'inputs': content}


def _artifact_hash(state, key):
    artifact = state['artifacts'].get(key)
    return artifact['sha256'] if artifact else None


def _is_hash(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def _validate_snapshot(payload, state, chapter_id):
    current = review_dependency(state, chapter_id)
    for field in ('coverage', 'source_sha256', 'source_segments', 'inputs'):
        if payload.get(field) != current[field]:
            raise ValueError(f'Review {field} does not match current chapter inputs')
    if any(value is None for value in current['inputs'].values()):
        raise ValueError('All required chapter content must be recorded before review')


def validate_review(payload: dict, state: dict, chapter_id: str) -> None:
    """Reject malformed or stale reports; content meaning remains agent-judged."""
    if not isinstance(payload, dict) or payload.get('version') != 1 or type(payload.get('version')) is not int:
        raise ValueError('Unsupported review report version')
    if payload.get('chapter_id') != chapter_id:
        raise ValueError('Review chapter_id mismatch')
    _validate_snapshot(payload, state, chapter_id)
    if 'context_inputs' in payload:
        contexts = payload['context_inputs']
        if not isinstance(contexts, dict):
            raise ValueError('context_inputs must be a path-to-hash object')
        for name, digest in contexts.items():
            path = PurePosixPath(name) if isinstance(name, str) else None
            if (path is None or path.is_absolute() or not path.parts
                    or any(part in ('..', '.') for part in path.parts)
                    or '\\' in name or not _is_hash(digest)):
                raise ValueError(f'Invalid context input path/hash: {name}')
    checks = payload.get('checks')
    if not isinstance(checks, list) or len(checks) != len(CHECKS) or set(checks) != set(CHECKS):
        raise ValueError('Review checklist must contain each required check exactly once')
    verdict = payload.get('verdict')
    if verdict not in ('passed', 'needs_revision'):
        raise ValueError('Review verdict must be passed or needs_revision')
    findings = payload.get('findings')
    if not isinstance(findings, list):
        raise ValueError('Review findings must be a list')
    coverage = set(payload['coverage'])
    has_substantive = False
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError('Each review finding must be an object')
        ids = finding.get('segment_ids')
        if (not isinstance(ids, list) or not ids or len(set(ids)) != len(ids)
                or any(not isinstance(sid, str) or sid not in coverage for sid in ids)):
            raise ValueError('Finding segment_ids must refer to reviewed coverage')
        if finding.get('category') not in FINDING_CATEGORIES:
            raise ValueError('Unknown review finding category')
        for field in ('explanation', 'source_evidence', 'target_evidence'):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ValueError(f'Finding requires nonempty {field}')
        has_substantive |= finding['category'] in SUBSTANTIVE
    limitations = payload.get('limitations')
    if not isinstance(limitations, list) or not limitations or any(not isinstance(x, str) or not x.strip() for x in limitations):
        raise ValueError('Review limitations must be a nonempty list of statements')
    if verdict == 'passed' and has_substantive:
        raise ValueError('Passed review cannot contain open substantive findings')
    if verdict == 'needs_revision' and not has_substantive:
        raise ValueError('needs_revision requires a substantive finding')


def review_status(job: Path, state: dict, valid_artifact_keys: list[str]) -> dict:
    """Return chapter review states using artifact integrity and live snapshots."""
    valid = set(valid_artifact_keys)
    result = {}
    for chapter in state['index']['chapters']:
        cid = chapter['id']
        coverage = [sid for sid in chapter['segment_ids'] if sid in set(state['selected'])]
        if not coverage:
            continue
        key = f'review:{cid}'
        artifact = state['artifacts'].get(key)
        if artifact is None:
            result[cid] = 'not_reviewed'
            continue
        if key not in valid:
            # Report already exposes missing/modified report files as integrity issues.
            result[cid] = 'stale'
            continue
        try:
            path = Path(job) / artifact['path']
            import json
            payload = json.loads(path.read_text(encoding='utf-8'))
            validate_review(payload, state, cid)
            required_inputs = set(payload['inputs'])
            if (not required_inputs.issubset(valid)
                    or required_inputs.intersection(state['failures'])):
                result[cid] = 'stale'
                continue
            for name, digest in payload.get('context_inputs', {}).items():
                from .state import safe_path
                context_path = safe_path(job, name)
                if not context_path.is_relative_to(Path(job).resolve()) or not context_path.is_file() or sha(context_path.read_bytes()) != digest:
                    raise ValueError('Context input changed or missing')
            if payload.get('verdict') not in ('passed', 'needs_revision'):
                raise ValueError('Malformed review verdict')
            result[cid] = payload['verdict']
        except (ValueError, OSError, KeyError, TypeError):
            result[cid] = 'stale'
    return result
