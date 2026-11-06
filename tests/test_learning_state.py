import importlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from readfuse.sources import inspect_source
from readfuse.selection import select_scope


class JobCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / 'book.md'
        self.src.write_text('# One\n\nFirst.\n\nSecond.\n\n# Two\n\nThird.', encoding='utf-8')
        self.index = inspect_source(self.src)
        self.job = self.root / 'job'
        self.config = {'source_language': 'en', 'target_language': 'id', 'mode': 'learning', 'notes_policy': 'selective'}

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('readfuse.state'), 'v2 state not implemented')
        return importlib.import_module('readfuse.state')

    def initialize(self, selection=None):
        self.api().init_job(self.job, self.index, self.config)
        self.api().extend_selection(self.job, selection or select_scope(self.index, all_content=True))

    def artifact(self, kind, key, text='Teks pembelajaran.', **extra):
        path = self.job / 'work' / f'{kind}-{key}.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        artifact = {'kind': kind, 'unit_id': key, 'path': str(path), **extra}
        self.api().record_artifact(self.job, artifact)
        return path

    def chapter(self, cid):
        self.artifact('heading', cid, next(c['title'] for c in self.index['chapters'] if c['id'] == cid))
        ids = next(c['segment_ids'] for c in self.index['chapters'] if c['id'] == cid)
        for sid in ids:
            self.artifact('translation', sid)
            self.artifact('notes', sid, json.dumps({'notes': [], 'reviewed': True}), segment_ids=[sid])
        self.artifact('summary', cid, 'Inti bab.\n\n- Poin penting.', segment_ids=ids)


class TestLearningState(JobCase):
    def test_second_process_refuses_live_writer_lock(self):
        self.initialize()
        cli = Path(__file__).resolve().parents[1] / 'scripts/readfuse_cli.py'
        before = self.api().load_job(self.job)['revision']
        with self.api().job_lock(self.job):
            other = subprocess.run([sys.executable, str(cli), 'select', '--job-dir', str(self.job), '--chapters', '1'], capture_output=True, text=True)
            self.assertNotEqual(other.returncode, 0)
            self.assertIn('locked', other.stderr)
        self.assertEqual(self.api().load_job(self.job)['revision'], before)
        self.api().extend_selection(self.job, select_scope(self.index, chapter_ids=['ch001']))

    def test_hardlink_aliases_rejected(self):
        self.initialize()
        first = self.artifact('translation', 'ch001-s00001')
        alias = self.job / 'work' / 'alias.md'
        os.link(first, alias)
        with self.assertRaises(ValueError):
            self.api().record_artifact(self.job, {'kind': 'translation', 'unit_id': 'ch001-s00002', 'path': str(alias)})

    def test_reserved_paths_are_case_insensitive(self):
        self.initialize()
        p = self.job / 'Edition' / 'book.md'
        p.parent.mkdir()
        p.write_text('not an artifact', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.api().record_artifact(self.job, {'kind': 'translation', 'unit_id': 'ch001-s00001', 'path': str(p)})

    def test_persisted_path_aliases_are_rejected(self):
        self.initialize()
        self.artifact('translation', 'ch001-s00001')
        self.artifact('translation', 'ch001-s00002')
        path = self.job / 'state' / 'checkpoint.json'
        obj = json.loads(path.read_text(encoding='utf-8'))
        obj['artifacts']['translation:ch001-s00002']['path'] = obj['artifacts']['translation:ch001-s00001']['path']
        path.write_text(json.dumps(obj), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.api().status(self.job)

    def test_chapter_heading_is_required_and_source_linked(self):
        self.initialize()
        self.assertIn('heading:ch001', self.api().status(self.job)['pending'])
        self.artifact('heading', 'ch001', 'Bab Satu')
        self.assertNotIn('heading:ch001', self.api().status(self.job)['pending'])

    def test_chapter_artifacts_and_completion(self):
        self.initialize()
        self.assertFalse(self.api().status(self.job)['requested_complete'])
        self.chapter('ch001')
        self.chapter('ch002')
        r = self.api().status(self.job)
        self.assertTrue(r['requested_complete'])
        self.assertTrue(r['book_complete'])
        self.assertEqual(r['issues'], [])

    def test_partial_coverage_growing_invalidates_summary_only(self):
        idx = self.index
        idx['source']['format'], idx['page_count'] = 'pdf', 3
        for n, s in enumerate(idx['segments'], 1):
            s['anchors'] = [{'page': n}]
        self.initialize(select_scope(idx, pages=[1]))
        self.artifact('heading', 'ch001', 'Satu')
        self.artifact('translation', 'ch001-s00001')
        self.artifact('notes', 'ch001-s00001', '{"reviewed":true,"notes":[]}')
        self.artifact('summary', 'ch001', 'Partial.', segment_ids=['ch001-s00001'])
        self.assertTrue(self.api().status(self.job)['requested_complete'])
        self.api().extend_selection(self.job, select_scope(idx, pages=[2]))
        r = self.api().status(self.job)
        self.assertIn('summary:ch001', r['stale'])
        self.assertNotIn('translation:ch001-s00001', r['pending'])

    def test_source_config_output_tampering(self):
        self.initialize()
        p = self.artifact('translation', 'ch001-s00001')
        p.write_text('changed', encoding='utf-8')
        self.assertTrue(self.api().status(self.job)['issues'])
        with self.assertRaises(ValueError):
            self.api().status(self.job, expected_config=dict(self.config, target_language='fr'))
        self.src.write_text('new edition', encoding='utf-8')
        self.assertTrue(self.api().status(self.job)['issues'])

    def test_failure_retry_and_artifact_aliases(self):
        self.initialize()
        self.api().record_failure(self.job, 'translation:ch001-s00001', 'Unreadable')
        self.assertIn('translation:ch001-s00001', self.api().status(self.job)['failed'])
        path = self.artifact('translation', 'ch001-s00001')
        self.assertNotIn('translation:ch001-s00001', self.api().status(self.job)['failed'])
        for other in [path, self.src, self.job / 'state' / 'checkpoint.json', self.job / 'edition' / 'book.md']:
            with self.subTest(path=other), self.assertRaises(ValueError):
                self.api().record_artifact(self.job, {'kind': 'translation', 'unit_id': 'ch001-s00002', 'path': str(other)})

    def test_corrupt_legacy_and_locked_jobs_rejected(self):
        self.initialize()
        lock = self.job / 'state' / '.write.lock'
        lock.write_text('other writer', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.api().extend_selection(self.job, select_scope(self.index, chapter_ids=['ch001']))
        lock.unlink()
        state = self.job / 'state' / 'checkpoint.json'
        state.write_text('{"version":1}', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.api().load_job(self.job)
        state.write_text('{', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.api().load_job(self.job)

    def test_atomic_interruption_preserves_state(self):
        self.initialize()
        p = self.job / 'state' / 'checkpoint.json'
        old = p.read_bytes()
        with patch('readfuse.state.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.api().record_failure(self.job, 'translation:ch001-s00001', 'failure')
        self.assertEqual(p.read_bytes(), old)
        self.assertFalse((self.job / 'state' / '.write.lock').exists())

    def test_generated_output_symlink_rejected(self):
        self.initialize()
        target = self.job / 'work' / 'unrelated.md'
        target.parent.mkdir()
        target.write_text('keep this', encoding='utf-8')
        link = self.job / 'edition'
        try:
            link.symlink_to(target.parent, target_is_directory=True)
        except OSError:
            self.skipTest('Windows symlink privilege unavailable')
        with self.assertRaises(ValueError):
            self.api().safe_path(self.job, 'edition/book.md')

    def test_missing_pdf_text_cannot_claim_book_complete(self):
        self.index['source']['format'], self.index['page_count'] = 'pdf', 4
        for n, s in enumerate(self.index['segments'], 1):
            s['anchors'] = [{'page': n}]
        self.index['warnings'] = ['PDF page 4: no extractable text; OCR or manual review required.']
        self.initialize()
        self.chapter('ch001')
        self.chapter('ch002')
        self.assertFalse(self.api().status(self.job)['book_complete'])

    def test_invalid_note_anchor_and_summary_coverage_rejected(self):
        self.initialize()
        with self.assertRaises(ValueError):
            self.artifact('notes', 'ch001-s00001', '{"reviewed":true,"notes":[{"anchor":"unknown","text":"Example"}]}')
        with self.assertRaises(ValueError):
            self.artifact('summary', 'ch001', segment_ids=['ch002-s00001'])
