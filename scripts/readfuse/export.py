"""Local EPUB/PDF export from sanitized Pandoc AST; no remote resources."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from . import state as store
from .assembly import render
from .sources import xml, local_name, zip_member


def capabilities() -> dict:
    pandoc = shutil.which('pandoc')
    if not pandoc:
        try:
            import pypandoc
            pandoc = pypandoc.get_pandoc_path()
        except (ImportError, OSError):
            pass
    return {'pandoc': pandoc, 'pdf_renderer': 'pymupdf' if importlib.util.find_spec('pymupdf') else None}


def run_pandoc(executable, args, data, cwd):
    result = subprocess.run([executable, *args], input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=cwd, timeout=120, check=False)
    if result.returncode:
        raise ValueError('Pandoc failed: ' + result.stderr.decode('utf-8', errors='replace')[:1000])
    return result.stdout


def sanitized_ast(executable, markdown, cwd):
    raw = run_pandoc(executable, ['--from=markdown-raw_html-raw_tex', '--to=json'], markdown, cwd)
    ast = json.loads(raw)

    def check(node):
        if isinstance(node, dict):
            if node.get('t') in ('Image', 'RawBlock', 'RawInline'):
                raise ValueError('Images/raw active content need a reviewed local-resource workflow before export')
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)
    check(ast)
    # Source metadata must not inject CSS, includes, filters or resource paths.
    ast['meta'] = {}
    return json.dumps(ast, ensure_ascii=False).encode('utf-8')


def pdf_from_html(html, path):
    import pymupdf
    story = pymupdf.Story(html=html.decode('utf-8'), user_css='body {font-size:11pt;line-height:1.4;} blockquote {color:#334155;}')
    media = pymupdf.paper_rect('a4')

    def rectangle(rect_num, filled):
        if rect_num > 10000:
            raise ValueError('PDF layout exceeds page limit; review oversized content')
        return media, media + (48, 48, -48, -48), None

    with pymupdf.DocumentWriter(str(path)) as writer:
        story.write(writer, rectangle)


def validate_export(path: Path, fmt: str) -> None:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Empty/missing export')
        if fmt == 'epub':
            with zipfile.ZipFile(path) as z:
                if z.read('mimetype') != b'application/epub+zip':
                    raise ValueError('Invalid EPUB mimetype')
                for name in z.namelist():
                    zip_member('', name.rstrip('/'))
                root = xml(z.read('META-INF/container.xml'))
                opf_name = next(e.get('full-path') for e in root.iter() if local_name(e) == 'rootfile')
                opf_name = zip_member('', opf_name)
                opf = xml(z.read(opf_name))
                items = {e.get('id'): e.get('href') for e in opf.iter() if local_name(e) == 'item'}
                refs = [e.get('idref') for e in opf.iter() if local_name(e) == 'itemref']
                if not refs:
                    raise ValueError('Empty EPUB spine')
                for ref in refs:
                    name = zip_member(str(Path(opf_name).parent).replace('\\', '/'), items[ref])
                    if not z.read(name).strip():
                        raise ValueError('Empty EPUB spine document')
        elif fmt == 'pdf':
            import pymupdf
            with pymupdf.open(path) as doc:
                if not len(doc) or not all(page.get_text().strip() for page in doc):
                    raise ValueError('PDF has empty/unreadable pages')
        else:
            raise ValueError('Unknown validation format')
    except (OSError, ImportError, KeyError, StopIteration, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError(f'Invalid {fmt} export: {exc}') from exc


def export_edition(job: Path, formats: list[str]) -> dict:
    if not formats or len(set(formats)) != len(formats) or any(fmt not in ('md', 'epub', 'pdf') for fmt in formats):
        raise ValueError('Choose unique formats from md, epub, pdf')
    cap = capabilities()
    with store.job_lock(job):
        state = store.load_job(job)
        report = store.report(job, state)
        markdown = render(job, state, report)
        edition = store.safe_path(job, 'edition/book.md')
        store.atomic_write(edition, markdown)
        result = {'edition_sha256': store.sha(markdown), 'formats': {},
                  'requested_complete': report['requested_complete'], 'book_complete': report['book_complete'],
                  'warnings': ['Font coverage, complex layouts and semantic fidelity still need reader/agent review.']}
        for fmt in formats:
            target = store.safe_path(job, f'edition/book.{fmt}')
            try:
                if fmt == 'md':
                    result['formats'][fmt] = {'path': str(target), 'sha256': store.sha(markdown)}
                    continue
                if not cap['pandoc']:
                    raise ValueError('Pandoc is not installed; Markdown remains available')
                if fmt == 'pdf' and not cap['pdf_renderer']:
                    raise ValueError('PDF rendering/validation requires optional PyMuPDF')
                with tempfile.TemporaryDirectory(prefix='.export-', dir=target.parent) as temp:
                    staging = Path(temp)
                    ast = sanitized_ast(cap['pandoc'], markdown, staging)
                    staged = staging / ('book.' + fmt)
                    if fmt == 'epub':
                        run_pandoc(cap['pandoc'], ['--from=json', '--to=epub3', '--standalone', '--toc',
                                                   '--metadata=title:ReadFuse learning edition', '-o', str(staged)], ast, staging)
                    else:
                        html = run_pandoc(cap['pandoc'], ['--from=json', '--to=html5'], ast, staging)
                        pdf_from_html(html, staged)
                    validate_export(staged, fmt)
                    store.atomic_write(target, staged.read_bytes())
                result['formats'][fmt] = {'path': str(target), 'sha256': store.sha(target.read_bytes())}
            except (ValueError, OSError, ImportError, subprocess.SubprocessError, json.JSONDecodeError, RuntimeError) as exc:
                result['formats'][fmt] = {'error': str(exc), 'previous_export_preserved': target.exists()}
        store.atomic_write(store.safe_path(job, 'edition/export-report.json'), store.encoded(result))
        return result
