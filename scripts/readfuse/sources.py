"""Conservative, ordered local source inspection."""
import hashlib
from pathlib import Path, PurePosixPath
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def xml(data):
    # A plain HTML5 doctype has no external subset or entities and is common in EPUB.
    data = re.sub(br'<!DOCTYPE\s+html\s*>', b'', data, flags=re.I)
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', data, re.I):
        raise ValueError('XML declarations/entities are not supported')
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f'Malformed XML: {exc}') from exc


def local_name(element):
    return element.tag.rsplit('}', 1)[-1]


def zip_member(base, href):
    if not isinstance(href, str) or re.search(r'[:\\?#]', href) or href.startswith('/'):
        raise ValueError(f'Nonlocal/unsupported EPUB reference: {href}')
    result = posixpath.normpath(posixpath.join(base, href))
    if result == '..' or result.startswith('../'):
        raise ValueError('EPUB reference escapes archive')
    return result


def read_epub(path):
    """Return heading/body events in spine order; never extract archive files."""
    events, warnings = [], ['EPUB rich layouts, images, and styling require manual review.']
    with zipfile.ZipFile(path) as z:
        total = 0
        for item in z.infolist():
            zip_member('', item.filename.rstrip('/'))
            total += item.file_size
            if item.file_size > 32 * 1024 * 1024 or total > 256 * 1024 * 1024:
                raise ValueError('EPUB exceeds safe inspection size')
        container = xml(z.read('META-INF/container.xml'))
        roots = [e for e in container.iter() if local_name(e) == 'rootfile']
        if not roots:
            raise ValueError('EPUB has no rootfile')
        opf_name = zip_member('', roots[0].get('full-path'))
        opf = xml(z.read(opf_name))
        items = {e.get('id'): e for e in opf.iter() if local_name(e) == 'item'}
        for ref in (e for e in opf.iter() if local_name(e) == 'itemref'):
            item = items.get(ref.get('idref'))
            if item is None:
                raise ValueError('EPUB spine references missing item')
            member = zip_member(posixpath.dirname(opf_name), item.get('href'))
            root = xml(z.read(member))
            body = next((e for e in root.iter() if local_name(e) == 'body'), None)
            if body is None:
                raise ValueError(f'EPUB document lacks body: {member}')
            if not any(local_name(e) in ('h1', 'h2') for e in body.iter()):
                events.append(('heading', PurePosixPath(member).stem, {'member': member}))
                warnings.append(f'Chapter label inferred from spine file: {member}')

            def walk(el):
                tag = local_name(el)
                if tag in ('script', 'style'):
                    warnings.append(f'Non-reading {tag} omitted: {member}')
                    return
                if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'pre', 'table', 'li', 'figcaption'):
                    text = ''.join(el.itertext()).strip()
                    if text:
                        kind = 'heading' if tag in ('h1', 'h2') else 'text'
                        if tag.startswith('h') and kind == 'text':
                            text = '#' * int(tag[1]) + ' ' + text
                        events.append((kind, text, {'member': member}))
                        if tag in ('table', 'pre'):
                            warnings.append(f'{tag} flattened to text: {member}; review required')
                    return
                if el.text and el.text.strip():
                    events.append(('text', el.text.strip(), {'member': member}))
                for child in el:
                    walk(child)
                    if child.tail and child.tail.strip():
                        events.append(('text', child.tail.strip(), {'member': member}))
            walk(body)
    return events, warnings


def read_markdown(path):
    text = path.read_text(encoding='utf-8-sig')
    events, buffer, offset, start, fenced = [], [], 0, 0, None

    def flush():
        if buffer:
            value = ''.join(buffer).strip()
            if value:
                events.append(('text', value, {'offset': start}))
            buffer.clear()

    for line in text.splitlines(keepends=True):
        fence = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence:
            marker = fence.group(1)[0]
            if fenced is None:
                fenced = marker
            elif fenced == marker:
                fenced = None
        heading = re.match(r'^#{1,2}\s+(.+?)\s*#*\s*$', line) if not fenced else None
        if heading:
            flush()
            events.append(('heading', heading.group(1), {'offset': offset}))
        elif not line.strip() and fenced is None:
            flush()
        else:
            if not buffer:
                start = offset
            buffer.append(line)
        offset += len(line)
    flush()
    return events, []


def read_pdf(path):
    try:
        import pymupdf
    except ImportError as exc:
        raise ValueError('PDF inspection requires optional PyMuPDF: python -m pip install pymupdf') from exc
    events, warnings = [], ['PDF extraction order, tables, equations, images and footnotes need review.']
    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError('Encrypted PDF requires an unlocked local copy')
        toc = [r for r in doc.get_toc() if r[0] == 1 and 1 <= r[2] <= len(doc)]
        by_page = {}
        for _, title, page in toc:
            by_page.setdefault(page, []).append(title)
        if not toc:
            warnings.append('Uncertain chapter boundaries: no top-level PDF outline; review page-based sections before chapter selection.')
        for number, page in enumerate(doc, 1):
            label = page.get_label() or None
            anchor = {'page': number, 'printed_label': label}
            titles = by_page.get(number, [])
            blocks = [b[4].strip() for b in page.get_text('blocks', sort=True) if len(b) > 4 and isinstance(b[4], str) and b[4].strip()]
            if not toc:
                events.append(('heading', f'PDF page {number}', anchor))
            if not blocks:
                warnings.append(f'PDF page {number}: no extractable text; OCR or manual review required.')
            page_events, found = [], 0
            for i, block in enumerate(blocks):
                buffered = []
                block_anchor = dict(anchor, block=i)
                for line in block.splitlines():
                    normalized = ' '.join(line.split()).casefold()
                    if found < len(titles) and normalized == ' '.join(titles[found].split()).casefold():
                        if buffered:
                            page_events.append(('text', '\n'.join(buffered), block_anchor))
                            buffered = []
                        page_events.append(('heading', titles[found], block_anchor))
                        found += 1
                    else:
                        buffered.append(line)
                if buffered:
                    page_events.append(('text', '\n'.join(buffered), block_anchor))
            if found != len(titles):
                warnings.append(f'Uncertain chapter boundaries: PDF page {number} outline titles do not match exact extracted heading lines; review or select pages.')
                events.append(('heading', ' / '.join(titles), anchor))
                events.extend(('text', block, dict(anchor, block=i)) for i, block in enumerate(blocks))
            else:
                events.extend(page_events)
        return events, warnings, len(doc)


def inspect_source(path: Path) -> dict:
    path = Path(path).resolve()
    fmt = path.suffix.lower().lstrip('.')
    if fmt == 'md':
        events, warnings = read_markdown(path)
        pages = None
    elif fmt == 'epub':
        events, warnings = read_epub(path)
        pages = None
    elif fmt == 'pdf':
        events, warnings, pages = read_pdf(path)
    else:
        raise ValueError('Supported source formats: .md, .epub, .pdf')
    index = {'version': 2, 'source': {'path': str(path), 'sha256': sha(path.read_bytes()), 'format': fmt},
             'page_count': pages, 'chapters': [], 'segments': [], 'warnings': warnings}
    chapter = None
    for kind, text, anchor in events:
        if kind == 'heading' or chapter is None:
            chapter = {'id': f'ch{len(index["chapters"]) + 1:03}', 'title': text if kind == 'heading' else 'Front matter', 'segment_ids': []}
            index['chapters'].append(chapter)
        if kind == 'heading':
            continue
        key = f'{chapter["id"]}-s{len(chapter["segment_ids"]) + 1:05}'
        chapter['segment_ids'].append(key)
        index['segments'].append({'id': key, 'chapter_id': chapter['id'], 'ordinal': len(index['segments']),
                                  'text': text, 'sha256': sha(text.encode('utf-8')), 'anchors': [anchor]})
    validate_index(index)
    return index


def validate_index(index: dict) -> None:
    try:
        if index['version'] != 2 or index['source']['format'] not in ('md', 'pdf', 'epub'):
            raise ValueError('Unsupported source index')
        if not re.fullmatch(r'[a-f0-9]{64}', index['source']['sha256']) or not isinstance(index['source']['path'], str):
            raise ValueError('Invalid source fingerprint/path')
        chapters, segments = index['chapters'], index['segments']
        if not isinstance(chapters, list) or not isinstance(segments, list) or not segments:
            raise ValueError('No readable source segments')
        ids = [s['id'] for s in segments]
        cids = [c['id'] for c in chapters]
        if len(set(ids)) != len(ids) or len(set(cids)) != len(cids):
            raise ValueError('Duplicate source identifiers')
        if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', key) for key in ids + cids):
            raise ValueError('Invalid source identifier')
        if [sid for c in chapters for sid in c['segment_ids']] != ids:
            raise ValueError('Chapter membership/order mismatch')
        pages = index['page_count']
        if index['source']['format'] == 'pdf' and (type(pages) is not int or pages < 1):
            raise ValueError('Invalid PDF page count')
        for n, s in enumerate(segments):
            if s['ordinal'] != n or not s['text'].strip() or sha(s['text'].encode('utf-8')) != s['sha256']:
                raise ValueError('Invalid source segment/hash')
            if s['chapter_id'] not in cids or s['id'] not in chapters[cids.index(s['chapter_id'])]['segment_ids']:
                raise ValueError('Invalid chapter membership')
            if not isinstance(s['anchors'], list) or not s['anchors']:
                raise ValueError('Missing source anchors')
            for a in s['anchors']:
                if index['source']['format'] == 'pdf' and (type(a.get('page')) is not int or not 1 <= a['page'] <= pages):
                    raise ValueError('Invalid PDF page anchor')
        if not isinstance(index['warnings'], list):
            raise ValueError('Invalid warnings')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Malformed source index') from exc
