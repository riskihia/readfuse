import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'readfuse_cli.py'


class TestReviewWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.job = self.root / 'job'

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def setup_job(self):
        index = self.root / 'index.json'
        cfg = self.root / 'config.json'
        self.cli('inspect', '--source', ROOT / 'tests/fixtures/learning-book.md', '--index', index)
        cfg.write_text('{"source_language":"en","target_language":"id","mode":"learning"}', encoding='utf-8')
        self.cli('init', '--job-dir', self.job, '--index', index, '--config', cfg)
        self.cli('select', '--job-dir', self.job, '--chapters', '1')
        snapshot = self.cli('status', '--job-dir', self.job)
        state = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        chapter = state['index']['chapters'][0]
        for key in snapshot['pending']:
            kind, unit = key.split(':', 1)
            text = {'heading': 'Bab Satu', 'translation': 'Terjemahan lengkap.',
                    'notes': '{"reviewed":true,"notes":[]}', 'summary': 'Inti bab.\n\n- Poin.'}[kind]
            path = self.job / 'work' / (key.replace(':', '-') + '.md')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            descriptor = self.root / 'artifact.json'
            obj = {'kind': kind, 'unit_id': unit, 'path': str(path)}
            if kind == 'summary':
                obj['segment_ids'] = chapter['segment_ids']
            descriptor.write_text(json.dumps(obj), encoding='utf-8')
            self.cli('record', '--job-dir', self.job, '--artifact', descriptor)
        return self.cli('status', '--job-dir', self.job), state

    def add_review(self, state, verdict='passed', cid='ch001'):
        chapter = next(c for c in state['index']['chapters'] if c['id'] == cid)
        coverage = [sid for sid in chapter['segment_ids'] if sid in state['selected']]
        sources = {s['id']: s['sha256'] for s in state['index']['segments']}
        keys = [f'heading:{cid}']
        for sid in coverage:
            keys += [f'translation:{sid}', f'notes:{sid}']
        keys.append(f'summary:{cid}')
        current = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        payload = {'version': 1, 'chapter_id': cid, 'coverage': coverage,
                   'source_sha256': current['index']['source']['sha256'],
                   'source_segments': {sid: sources[sid] for sid in coverage},
                   'inputs': {k: current['artifacts'][k]['sha256'] for k in keys},
                   'checks': ['completeness', 'polarity_modality', 'relations_details', 'terminology', 'references_structure', 'fluency'],
                   'verdict': verdict, 'findings': [], 'limitations': ['Agent review; not independent certification.']}
        if verdict == 'needs_revision':
            payload['findings'] = [{'segment_ids': [coverage[0]], 'category': 'omission',
                                    'explanation': 'Missing clause.', 'source_evidence': 'A.', 'target_evidence': 'B.'}]
        path = self.job / 'work' / f'review-{cid}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')
        descriptor = self.root / 'review.json'
        descriptor.write_text(json.dumps({'kind': 'review', 'unit_id': cid, 'path': path.relative_to(self.job).as_posix()}), encoding='utf-8')
        self.cli('record', '--job-dir', self.job, '--artifact', descriptor)

    def test_old_job_and_complete_content_fail_require_reviewed(self):
        before, state = self.setup_job()
        self.assertTrue(before['requested_complete'])
        self.assertFalse(before['semantic_review_complete'])
        self.cli('verify', '--job-dir', self.job, '--require-reviewed', ok=False)
        self.add_review(state)
        after = self.cli('verify', '--job-dir', self.job, '--require-reviewed')
        self.assertTrue(after['semantic_review_complete'])

    def test_needs_revision_and_stale_review_fail_gate(self):
        _, state = self.setup_job()
        self.add_review(state, 'needs_revision')
        self.cli('verify', '--job-dir', self.job, '--require-reviewed', ok=False)
        state = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        self.add_review(state)
        changed = self.job / 'work/translation-ch001-s00001.md'
        changed.write_text('Perubahan setelah review.', encoding='utf-8')
        descriptor = self.root / 'changed.json'
        descriptor.write_text(json.dumps({'kind': 'translation', 'unit_id': 'ch001-s00001', 'path': str(changed)}), encoding='utf-8')
        self.cli('record', '--job-dir', self.job, '--artifact', descriptor)
        self.cli('verify', '--job-dir', self.job, '--require-reviewed', ok=False)

    def test_partial_selection_can_be_reviewed_without_claiming_full_book(self):
        _, state = self.setup_job()
        self.add_review(state)
        result = self.cli('status', '--job-dir', self.job)
        self.assertTrue(result['semantic_review_complete'])
        self.assertFalse(result['book_complete'])
        self.assertFalse(result['semantic_review']['ch002'] if 'ch002' in result['semantic_review'] else False)

    def test_revision_in_one_chapter_keeps_other_chapter_review_current(self):
        _, state = self.setup_job()
        self.add_review(state)
        self.cli('select', '--job-dir', self.job, '--chapters', '2')
        state = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        chapter = next(c for c in state['index']['chapters'] if c['id'] == 'ch002')
        for key in self.cli('status', '--job-dir', self.job)['pending']:
            kind, unit = key.split(':', 1)
            text = {'heading': 'Bab Dua', 'translation': 'Terjemahan kedua.',
                    'notes': '{"reviewed":true,"notes":[]}', 'summary': 'Inti kedua.\n\n- Poin.'}[kind]
            path = self.job / 'work' / (key.replace(':', '-') + '.md')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            descriptor = self.root / 'artifact.json'
            obj = {'kind': kind, 'unit_id': unit, 'path': str(path)}
            if kind == 'summary':
                obj['segment_ids'] = chapter['segment_ids']
            descriptor.write_text(json.dumps(obj), encoding='utf-8')
            self.cli('record', '--job-dir', self.job, '--artifact', descriptor)
        self.add_review(state, cid='ch002')
        before = self.cli('status', '--job-dir', self.job)
        self.assertEqual(before['semantic_review'], {'ch001': 'passed', 'ch002': 'passed'})
        changed = self.job / 'work/translation-ch001-s00001.md'
        changed.write_text('Revisi terjemahan pertama.', encoding='utf-8')
        descriptor = self.root / 'changed.json'
        descriptor.write_text(json.dumps({'kind': 'translation', 'unit_id': 'ch001-s00001', 'path': str(changed)}), encoding='utf-8')
        self.cli('record', '--job-dir', self.job, '--artifact', descriptor)
        after = self.cli('status', '--job-dir', self.job)
        self.assertEqual(after['semantic_review'], {'ch001': 'stale', 'ch002': 'passed'})
        self.cli('verify', '--job-dir', self.job, '--require-reviewed', ok=False)

    def test_broken_other_chapter_report_does_not_block_review_recovery(self):
        _, state = self.setup_job()
        self.add_review(state)
        self.cli('select', '--job-dir', self.job, '--chapters', '2')
        state = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        chapter = next(c for c in state['index']['chapters'] if c['id'] == 'ch002')
        for key in self.cli('status', '--job-dir', self.job)['pending']:
            kind, unit = key.split(':', 1)
            text = {'heading': 'Bab Dua', 'translation': 'Terjemahan kedua.',
                    'notes': '{"reviewed":true,"notes":[]}', 'summary': 'Inti kedua.\n\n- Poin.'}[kind]
            path = self.job / 'work' / (key.replace(':', '-') + '.md')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
            descriptor = self.root / 'artifact.json'
            obj = {'kind': kind, 'unit_id': unit, 'path': str(path)}
            if kind == 'summary':
                obj['segment_ids'] = chapter['segment_ids']
            descriptor.write_text(json.dumps(obj), encoding='utf-8')
            self.cli('record', '--job-dir', self.job, '--artifact', descriptor)
        state = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        self.add_review(state, cid='ch002')
        (self.job / 'work/review-ch002.json').unlink()
        state = json.loads((self.job / 'state/checkpoint.json').read_text(encoding='utf-8'))
        self.add_review(state, cid='ch001')
        result = self.cli('status', '--job-dir', self.job)
        self.assertEqual(result['semantic_review']['ch001'], 'passed')
        self.assertEqual(result['semantic_review']['ch002'], 'stale')


if __name__ == '__main__':
    unittest.main()
