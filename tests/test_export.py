import importlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from test_learning_state import JobCase


class TestExport(JobCase):
    def export(self):
        self.assertIsNotNone(importlib.util.find_spec('readfuse.export'), 'exports not implemented')
        return importlib.import_module('readfuse.export')

    def ready(self):
        self.initialize()
        self.chapter('ch001')
        self.chapter('ch002')

    def test_missing_dependencies_reported_without_false_files(self):
        self.ready()
        api = self.export()
        with patch.object(api, 'capabilities', return_value={'pandoc': None, 'pdf_renderer': None}):
            result = api.export_edition(self.job, ['md', 'epub', 'pdf'])
        self.assertTrue(Path(result['formats']['md']['path']).is_file())
        self.assertIn('error', result['formats']['epub'])
        self.assertIn('error', result['formats']['pdf'])

    def test_remote_image_refuses_render_preserves_export(self):
        self.ready()
        target = self.job / 'edition' / 'book.epub'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'previous export')
        self.artifact('translation', 'ch001-s00001', '![private](https://example.org/private.png)')
        result = self.export().export_edition(self.job, ['epub'])
        self.assertIn('error', result['formats']['epub'])
        self.assertEqual(target.read_bytes(), b'previous export')

    def test_export_failure_preserves_previous_output(self):
        self.ready()
        api = self.export()
        target = self.job / 'edition' / 'book.epub'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'previous export')
        with patch.object(api, 'run_pandoc', side_effect=ValueError('renderer failed')):
            result = api.export_edition(self.job, ['epub'])
        self.assertIn('error', result['formats']['epub'])
        self.assertEqual(target.read_bytes(), b'previous export')

    def test_malformed_exports_rejected(self):
        api = self.export()
        p = self.root / 'bad.epub'
        p.write_bytes(b'not epub')
        with self.assertRaises(ValueError):
            api.validate_export(p, 'epub')
        p.write_bytes(b'%PDF-1.7 invalid')
        with self.assertRaises(ValueError):
            api.validate_export(p, 'pdf')

    def test_real_epub_and_pdf_contain_learning_content(self):
        self.ready()
        api = self.export()
        cap = api.capabilities()
        if not cap['pandoc'] or not cap['pdf_renderer']:
            self.skipTest('real exports require Pandoc and PyMuPDF')
        result = api.export_edition(self.job, ['epub', 'pdf'])
        for fmt in ['epub', 'pdf']:
            self.assertNotIn('error', result['formats'][fmt], result)
            self.assertTrue(Path(result['formats'][fmt]['path']).is_file())
        import pymupdf
        with pymupdf.open(result['formats']['pdf']['path']) as doc:
            text = ''.join(page.get_text() for page in doc)
            self.assertIn('Teks pembelajaran.', text)
            self.assertIn('Ringkasan bab', text)
        import zipfile
        with zipfile.ZipFile(result['formats']['epub']['path']) as z:
            text = '\n'.join(z.read(n).decode('utf-8') for n in z.namelist() if n.endswith('.xhtml'))
            self.assertIn('Teks pembelajaran.', text)
