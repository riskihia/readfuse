import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'readfuse_cli.py'


class TestLearningWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.job = self.root / 'job'

    def cli(self, *args, ok=True):
        self.assertTrue(CLI.is_file(), 'integrated CLI not implemented')
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        if result.stdout.strip():
            return json.loads(result.stdout)

    def init(self):
        index_path = self.root / 'index.json'
        config = self.root / 'config.json'
        self.cli('inspect', '--source', ROOT / 'tests/fixtures/learning-book.md', '--index', index_path)
        config.write_text(json.dumps({'source_language': 'en', 'target_language': 'id', 'mode': 'learning'}), encoding='utf-8')
        self.cli('init', '--job-dir', self.job, '--index', index_path, '--config', config)
        return json.loads(index_path.read_text(encoding='utf-8'))

    def record(self, kind, unit, text, coverage=None):
        output = self.job / 'work' / f'{kind}-{unit}.md'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding='utf-8')
        descriptor = self.root / 'artifact.json'
        record = {'kind': kind, 'unit_id': unit, 'path': str(output)}
        if coverage is not None:
            record['segment_ids'] = coverage
        descriptor.write_text(json.dumps(record), encoding='utf-8')
        self.cli('record', '--job-dir', self.job, '--artifact', descriptor)

    def test_continuation_one_three_eight_four_preserves_previous(self):
        index = self.init()
        old = None
        for scope, wanted in [('1-3', [1, 2, 3]), ('8', [1, 2, 3, 8]), ('4', [1, 2, 3, 4, 8])]:
            self.cli('select', '--job-dir', self.job, '--chapters', scope)
            if old is not None:
                self.assertEqual((self.job / 'work/translation-ch001-s00001.md').read_bytes(), old)
            report = self.cli('status', '--job-dir', self.job)
            for unit in report['pending']:
                kind, key = unit.split(':')
                if kind == 'heading':
                    text = next(c['title'] for c in index['chapters'] if c['id'] == key)
                elif kind == 'translation':
                    text = f'Terjemahan {key}.'
                elif kind == 'notes':
                    text = '{"reviewed":true,"notes":[]}'
                else:
                    text = f'Inti {key}.\n\n- Poin utama.'
                coverage = next(c['segment_ids'] for c in index['chapters'] if c['id'] == key) if kind == 'summary' else None
                self.record(kind, key, text, coverage)
            self.cli('verify', '--job-dir', self.job, '--require-complete')
            self.cli('assemble', '--job-dir', self.job)
            content = (self.job / 'edition/book.md').read_text(encoding='utf-8')
            positions = [content.index(f'## Chapter {n}:') for n in wanted]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(content.count('Terjemahan ch001-s00001.'), 1)
            self.assertIn('Edisi sebagian', content)
            old = (self.job / 'work/translation-ch001-s00001.md').read_bytes()
        self.cli('select', '--job-dir', self.job, '--chapters', '2-4')
        self.assertEqual(self.cli('status', '--job-dir', self.job)['pending'], [])

    def test_integrity_and_completion_distinct_and_bad_inputs(self):
        self.init()
        self.cli('select', '--job-dir', self.job, '--chapters', '1')
        self.cli('verify', '--job-dir', self.job)
        self.cli('verify', '--job-dir', self.job, '--require-complete', ok=False)
        self.cli('select', '--job-dir', self.job, '--chapters', '0', ok=False)
        self.cli('select', '--job-dir', self.job, '--pages', '1', ok=False)
        self.cli('fail', '--job-dir', self.job, '--unit-id', 'translation:ch001-s00001', '--reason', 'Review pending')
        self.assertIn('translation:ch001-s00001', self.cli('status', '--job-dir', self.job)['failed'])
        bad = self.root / 'bad.json'
        bad.write_text('{', encoding='utf-8')
        self.cli('record', '--job-dir', self.job, '--artifact', bad, ok=False)

    def test_real_pdf_partial_pages_then_continue_regenerates_summary(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest('optional PyMuPDF not installed')
        source = self.root / 'book.pdf'
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), 'One\nFirst passage.')
        doc.new_page().insert_text((72, 72), 'Second passage.')
        doc.set_toc([[1, 'One', 1]])
        doc.save(source)
        doc.close()
        idxpath = self.root / 'pdf-index.json'
        self.cli('inspect', '--source', source, '--index', idxpath)
        cfg = self.root / 'config.json'
        cfg.write_text('{"source_language":"en","target_language":"id","mode":"learning"}', encoding='utf-8')
        self.cli('init', '--job-dir', self.job, '--index', idxpath, '--config', cfg)
        self.cli('select', '--job-dir', self.job, '--pages', '1')
        self.record('heading', 'ch001', 'Satu')
        self.record('translation', 'ch001-s00001', 'Bagian pertama.')
        self.record('notes', 'ch001-s00001', '{"reviewed":true,"notes":[]}')
        self.record('summary', 'ch001', 'Inti bagian pertama.\n\n- Poin pertama.', ['ch001-s00001'])
        self.cli('assemble', '--job-dir', self.job)
        text = (self.job / 'edition/book.md').read_text(encoding='utf-8')
        self.assertIn('Ringkasan hanya untuk bagian yang sudah diproses', text)
        self.cli('select', '--job-dir', self.job, '--pages', '1-2')
        report = self.cli('status', '--job-dir', self.job)
        self.assertIn('summary:ch001', report['stale'])
        self.assertNotIn('translation:ch001-s00001', report['pending'])
        self.record('translation', 'ch001-s00002', 'Bagian kedua.')
        self.record('notes', 'ch001-s00002', '{"reviewed":true,"notes":[]}')
        self.record('summary', 'ch001', 'Inti kedua bagian.\n\n- Dua bagian.', ['ch001-s00001', 'ch001-s00002'])
        report = self.cli('verify', '--job-dir', self.job, '--require-complete')
        self.assertTrue(report['book_complete'])
        self.cli('assemble', '--job-dir', self.job)
        text = (self.job / 'edition/book.md').read_text(encoding='utf-8')
        self.assertEqual(text.count('Bagian pertama.'), 1)
        self.assertIn('Bagian kedua.', text)
