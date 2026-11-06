"""Thin, JSON-speaking command line interface for host agents."""
import argparse
import json
from pathlib import Path
import re
import sys
import zipfile

from .sources import inspect_source
from .selection import select_scope
from . import state as store
from .assembly import assemble
from .export import export_edition


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f'Invalid UTF-8 JSON: {path}') from exc


def positions(value, limit):
    numbers = set()
    for part in value.split(','):
        if not re.fullmatch(r'\d+(?:-\d+)?', part):
            raise ValueError('Use positions like 1-3,8 (1-based inclusive)')
        bounds = [int(n) for n in part.split('-')]
        start, end = bounds[0], bounds[-1]
        if not 1 <= start <= end <= limit:
            raise ValueError(f'Position outside available range 1–{limit}')
        numbers.update(range(start, end + 1))
    return sorted(numbers)


def parser():
    p = argparse.ArgumentParser(description='ReadFuse local learning-edition helpers; language work is performed by the host agent.')
    sub = p.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Index a local source without translating it')
    inspect.add_argument('--source', required=True, type=Path)
    inspect.add_argument('--index', required=True, type=Path)
    for name in ['init', 'select', 'status', 'record', 'fail', 'assemble', 'export', 'verify']:
        command = sub.add_parser(name)
        command.add_argument('--job-dir', required=True, type=Path)
        if name == 'init':
            command.add_argument('--index', required=True, type=Path)
            command.add_argument('--config', required=True, type=Path)
        elif name == 'select':
            group = command.add_mutually_exclusive_group(required=True)
            group.add_argument('--chapters')
            group.add_argument('--pages')
            group.add_argument('--all', action='store_true', dest='all_content')
        elif name == 'record':
            command.add_argument('--artifact', required=True, type=Path)
        elif name == 'fail':
            command.add_argument('--unit-id', required=True)
            command.add_argument('--reason', required=True)
        elif name == 'export':
            command.add_argument('--formats', required=True)
        elif name == 'verify':
            command.add_argument('--require-complete', action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    code = 0
    try:
        command = args.command
        if command == 'inspect':
            if args.index.resolve() == args.source.resolve():
                raise ValueError('Index output cannot overwrite the original source')
            index = inspect_source(args.source)
            store.atomic_write(args.index, store.encoded(index))
            result = {'index': str(args.index.resolve()), 'page_count': index['page_count'], 'warnings': index['warnings'],
                      'chapters': [{'position': n, 'id': c['id'], 'title': c['title'], 'segments': len(c['segment_ids'])}
                                   for n, c in enumerate(index['chapters'], 1)]}
        elif command == 'init':
            store.init_job(args.job_dir, read_json(args.index), read_json(args.config))
            result = store.status(args.job_dir)
        elif command == 'select':
            index = store.load_job(args.job_dir)['index']
            chapters = None
            pages = None
            if args.chapters is not None:
                chapters = [index['chapters'][n - 1]['id'] for n in positions(args.chapters, len(index['chapters']))]
            if args.pages is not None:
                if index['source']['format'] != 'pdf':
                    raise ValueError('Page selection is only available for PDF file positions')
                pages = positions(args.pages, index['page_count'])
            selection = select_scope(index, chapter_ids=chapters, pages=pages, all_content=args.all_content)
            store.extend_selection(args.job_dir, selection)
            result = store.status(args.job_dir)
        elif command == 'record':
            store.record_artifact(args.job_dir, read_json(args.artifact))
            result = store.status(args.job_dir)
        elif command == 'fail':
            store.record_failure(args.job_dir, args.unit_id, args.reason)
            result = store.status(args.job_dir)
        elif command == 'assemble':
            result = {'path': str(assemble(args.job_dir)), 'status': store.status(args.job_dir)}
        elif command == 'export':
            result = export_edition(args.job_dir, args.formats.split(','))
            if any('error' in info for info in result['formats'].values()):
                code = 1
        else:
            result = store.status(args.job_dir)
            if command == 'verify' and (result['issues'] or (args.require_complete and not result['requested_complete'])):
                code = 1
        # ASCII-safe JSON also works in older Windows consoles; files remain UTF-8.
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return code
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1
