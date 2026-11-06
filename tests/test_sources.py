import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def make_epub(path, unsafe=False):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
        z.writestr('OEBPS/book.opf', '<package><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/><item id="b" href="b.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>')
        z.writestr('OEBPS/a.xhtml', '<html><body><h1>A</h1><p>Alpha</p></body></html>')
        z.writestr('OEBPS/b.xhtml', ('<!DOCTYPE html [<!ENTITY x SYSTEM "file:///secret">]>' if unsafe else '') + '<html><body><h1>B</h1><p>Beta</p></body></html>')


class TestSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('readfuse'), 'source indexing not implemented')
        return importlib.import_module('readfuse.sources')

    def test_markdown_front_matter_and_eight_chapters_stable(self):
        p = self.root / 'book.md'
        p.write_text('Preface text.\n\n' + '\n\n'.join(f'# Chapter {i}\n\nParagraph {i}.' for i in range(1, 9)), encoding='utf-8')
        index = self.api().inspect_source(p)
        self.assertEqual([c['title'] for c in index['chapters']], ['Front matter'] + [f'Chapter {i}' for i in range(1, 9)])
        self.assertEqual(len(index['segments']), 9)
        self.assertEqual(index, self.api().inspect_source(p))
        self.assertIsNone(index['page_count'])
        self.assertEqual(index['segments'][0]['text'], 'Preface text.')

    def test_epub_spine_not_zip_order(self):
        p = self.root / 'book.epub'
        make_epub(p)
        index = self.api().inspect_source(p)
        self.assertEqual([c['title'] for c in index['chapters']], ['B', 'A'])
        self.assertEqual([s['text'] for s in index['segments']], ['Beta', 'Alpha'])

    def test_epub_entities_rejected(self):
        p = self.root / 'book.epub'
        make_epub(p, True)
        with self.assertRaises(ValueError):
            self.api().inspect_source(p)

    def test_epub_plain_html_doctype_is_supported(self):
        p = self.root / 'book.epub'
        make_epub(p)
        with zipfile.ZipFile(p) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        entries['OEBPS/b.xhtml'] = b'<!DOCTYPE html>' + entries['OEBPS/b.xhtml']
        with zipfile.ZipFile(p, 'w') as z:
            for name, data in entries.items():
                z.writestr(name, data)
        self.assertEqual([c['title'] for c in self.api().inspect_source(p)['chapters']], ['B', 'A'])

    def test_epub_archive_escape_rejected(self):
        p = self.root / 'book.epub'
        make_epub(p)
        with zipfile.ZipFile(p, 'a') as z:
            z.writestr('../escape', 'bad')
        with self.assertRaises(ValueError):
            self.api().inspect_source(p)

    def test_malformed_index_rejected(self):
        with self.assertRaises(ValueError):
            self.api().validate_index({'version': 2})

    def test_pdf_pages_outline_shared_page_and_ocr(self):
        self.api()
        try:
            import pymupdf
        except ImportError:
            self.skipTest('optional PyMuPDF not installed')
        p = self.root / 'book.pdf'
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), 'Chapter One\nFirst body.\nChapter Two\nSecond body.')
        doc.new_page()
        doc.set_toc([[1, 'Chapter One', 1], [1, 'Chapter Two', 1]])
        doc.save(p)
        doc.close()
        index = self.api().inspect_source(p)
        self.assertEqual(index['page_count'], 2)
        self.assertTrue(any('OCR' in w for w in index['warnings']))
        self.assertEqual({a['page'] for s in index['segments'] for a in s['anchors']}, {1})

    def test_pdf_chapter_boundary_midpage_does_not_leak_previous_chapter(self):
        self.api()
        try:
            import pymupdf
        except ImportError:
            self.skipTest('optional PyMuPDF not installed')
        p = self.root / 'boundary.pdf'
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), 'Chapter One\nOpening.')
        doc.new_page().insert_text((72, 72), 'Ending of chapter one.\nChapter Two\nBeginning of chapter two.')
        doc.set_toc([[1, 'Chapter One', 1], [1, 'Chapter Two', 2]])
        doc.save(p)
        doc.close()
        index = self.api().inspect_source(p)
        from readfuse.selection import select_scope
        selected = select_scope(index, chapter_ids=['ch002'])['segment_ids']
        text = '\n'.join(s['text'] for s in index['segments'] if s['id'] in selected)
        self.assertNotIn('Ending of chapter one.', text)
        self.assertIn('Beginning of chapter two.', text)

    def test_unmatched_pdf_outline_boundary_requires_review(self):
        self.api()
        try:
            import pymupdf
        except ImportError:
            self.skipTest('optional PyMuPDF not installed')
        p = self.root / 'uncertain.pdf'
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), 'A passage with no recognizable heading.')
        doc.set_toc([[1, 'Outline-only title', 1]])
        doc.save(p)
        doc.close()
        index = self.api().inspect_source(p)
        from readfuse.selection import select_scope
        with self.assertRaises(ValueError):
            select_scope(index, chapter_ids=['ch001'])
