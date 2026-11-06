"""Explicit scope selection against a stable source inventory."""
from .sources import validate_index


def merge_coverage(index: dict, existing: list[str], added: list[str]) -> list[str]:
    validate_index(index)
    known = {s['id'] for s in index['segments']}
    wanted = set(existing) | set(added)
    if not wanted <= known:
        raise ValueError('Coverage references unknown source segments')
    return [s['id'] for s in index['segments'] if s['id'] in wanted]


def select_scope(index: dict, *, chapter_ids=None, pages=None, all_content=False) -> dict:
    validate_index(index)
    if sum([chapter_ids is not None, pages is not None, bool(all_content)]) != 1:
        raise ValueError('Choose exactly one explicit scope: chapters, PDF pages, or all')
    if chapter_ids is not None:
        if not chapter_ids or not set(chapter_ids) <= {c['id'] for c in index['chapters']}:
            raise ValueError('Empty or unknown chapter selection')
        if any('uncertain chapter boundaries' in w.lower() for w in index['warnings']):
            raise ValueError('Chapter boundaries need review; select PDF pages or supply a reviewed index')
        ids = [s['id'] for s in index['segments'] if s['chapter_id'] in chapter_ids]
    elif pages is not None:
        if index['source']['format'] != 'pdf' or not pages or any(type(p) is not int or not 1 <= p <= index['page_count'] for p in pages):
            raise ValueError('Use valid 1-based PDF file page positions')
        ids = [s['id'] for s in index['segments'] if any(a['page'] in pages for a in s['anchors'])]
    else:
        ids = [s['id'] for s in index['segments']]
    if not ids:
        raise ValueError('Selection has no readable source text; inspect extraction/OCR warnings')
    selected = set(ids)
    coverage = {c['id']: 'full' if set(c['segment_ids']) <= selected else 'partial'
                for c in index['chapters'] if selected.intersection(c['segment_ids'])}
    return {'segment_ids': ids, 'chapter_ids': list(coverage), 'coverage': coverage}
