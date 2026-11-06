import importlib
from unittest.mock import patch
from test_learning_state import JobCase


class TestAssembly(JobCase):
    def test_translated_chapter_heading_is_rendered(self):
        self.initialize()
        self.chapter('ch001')
        self.artifact('heading', 'ch001', 'Bab Satu')
        text = self.assembly().assemble(self.job).read_text(encoding='utf-8')
        self.assertIn('## Bab Satu', text)
        self.assertNotIn('## One', text)

    def assembly(self):
        self.assertIsNotNone(importlib.util.find_spec('readfuse.assembly'), 'assembly not implemented')
        return importlib.import_module('readfuse.assembly')

    def test_notes_near_text_and_summary_at_end(self):
        self.initialize()
        for c in self.index['chapters']:
            self.chapter(c['id'])
        self.artifact('notes', 'ch001-s00001', '{"reviewed":true,"notes":[{"anchor":"ch001-s00001","text":"Contoh keseharian."}]}')
        p = self.assembly().assemble(self.job)
        text = p.read_text(encoding='utf-8')
        self.assertLess(text.index('Teks pembelajaran.'), text.index('Contoh keseharian.'))
        self.assertLess(text.index('Catatan ReadFuse'), text.index('Ringkasan bab'))
        self.assertLess(text.index('Ringkasan bab'), text.index('## Two'))
        self.assertNotIn('ch001-s00001', text)

    def test_partial_missing_and_stale_summary(self):
        from readfuse.selection import select_scope
        self.initialize(select_scope(self.index, chapter_ids=['ch002']))
        self.chapter('ch002')
        text = self.assembly().assemble(self.job).read_text(encoding='utf-8')
        self.assertIn('One', text)
        self.assertIn('Belum diproses', text)
        self.assertIn('Edisi sebagian', text)
        self.assertNotIn('buku lengkap', text.lower())

    def test_interruption_and_invalid_output_preserve_edition(self):
        self.initialize()
        self.chapter('ch001')
        p = self.assembly().assemble(self.job)
        old = p.read_bytes()
        with patch('readfuse.state.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.assembly().assemble(self.job)
        self.assertEqual(p.read_bytes(), old)
        (self.job / 'work' / 'translation-ch001-s00001.md').write_text('tampered', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.assembly().assemble(self.job)
        self.assertEqual(p.read_bytes(), old)
