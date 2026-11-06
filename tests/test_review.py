import copy
import importlib
import json
from pathlib import Path

from test_learning_state import JobCase
from readfuse import state as store
from readfuse.selection import select_scope
from readfuse.sources import sha


class ReviewCase(JobCase):
    def ready(self, chapters=('ch001',)):
        self.initialize(select_scope(self.index, chapter_ids=list(chapters)))
        for cid in chapters:
            self.chapter(cid)

    def payload(self, cid='ch001'):
        current = store.load_job(self.job)
        coverage = [sid for c in current['index']['chapters'] if c['id'] == cid
                    for sid in c['segment_ids'] if sid in current['selected']]
        keys = [f'heading:{cid}']
        if current['config']['mode'] != 'summarize':
            for sid in coverage:
                keys.append(f'translation:{sid}')
                if current['config']['mode'] == 'learning' and current['config'].get('notes_policy', 'selective') != 'none':
                    keys.append(f'notes:{sid}')
        if current['config']['mode'] != 'translate':
            keys.append(f'summary:{cid}')
        sources = {s['id']: s['sha256'] for s in current['index']['segments']}
        return {'version': 1, 'chapter_id': cid, 'coverage': coverage,
                'source_sha256': current['index']['source']['sha256'],
                'source_segments': {sid: sources[sid] for sid in coverage},
                'inputs': {key: current['artifacts'][key]['sha256'] for key in keys},
                'checks': ['completeness', 'polarity_modality', 'relations_details', 'terminology', 'references_structure', 'fluency'],
                'verdict': 'passed', 'findings': [],
                'limitations': ['Agent review against extracted text; no independent accuracy certification.']}

    def record_review(self, payload=None, name='review.json'):
        obj = payload if payload is not None else self.payload()
        path = self.job / 'work' / name
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        store.record_artifact(self.job, {'kind': 'review', 'unit_id': obj['chapter_id'], 'path': str(path)})
        return path

    def semantic(self, cid='ch001'):
        return store.status(self.job)['semantic_review'][cid]


class TestReview(ReviewCase):
    def test_old_v2_job_has_no_semantic_review(self):
        self.ready()
        result = store.status(self.job)
        self.assertTrue(result['requested_complete'])
        self.assertIn('semantic_review_complete', result)
        self.assertFalse(result['semantic_review_complete'])
        self.assertEqual(self.semantic(), 'not_reviewed')

    def test_pass_requires_exact_current_coverage_and_input_hashes(self):
        self.ready()
        valid = self.payload()
        for field, bad in [('coverage', ['ch001-s00001']), ('inputs', {}),
                           ('source_segments', {}), ('source_sha256', '0' * 64),
                           ('checks', ['fluency'])]:
            altered = copy.deepcopy(valid)
            altered[field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.record_review(altered)
        self.record_review(valid)
        self.assertTrue(store.status(self.job)['semantic_review_complete'])

    def test_pass_rejects_open_meaning_findings(self):
        self.ready()
        obj = self.payload()
        obj['findings'] = [{'segment_ids': ['ch001-s00001'], 'category': 'omission',
                            'explanation': 'Second clause omitted.', 'source_evidence': 'First.', 'target_evidence': 'Text.'}]
        with self.assertRaises(ValueError):
            self.record_review(obj)
        obj['verdict'] = 'needs_revision'
        self.record_review(obj)
        self.assertEqual(self.semantic(), 'needs_revision')
        self.assertFalse(store.status(self.job)['semantic_review_complete'])

    def test_valid_style_variation_does_not_block_review(self):
        self.ready()
        obj = self.payload()
        obj['findings'] = [{'segment_ids': ['ch001-s00001'], 'category': 'style',
                            'explanation': 'Alternative wording is also acceptable.',
                            'source_evidence': 'First.', 'target_evidence': 'Teks pembelajaran.'}]
        self.record_review(obj)
        self.assertEqual(self.semantic(), 'passed')

    def test_translation_change_stales_review(self):
        self.ready()
        self.record_review()
        self.artifact('translation', 'ch001-s00001', 'Revised translation.')
        self.assertEqual(self.semantic(), 'stale')
        self.assertFalse(store.status(self.job)['semantic_review_complete'])

    def test_reregistering_old_report_does_not_bless_new_translation(self):
        self.ready()
        old = self.payload()
        self.record_review(old)
        self.artifact('translation', 'ch001-s00001', 'Changed translation.')
        with self.assertRaises(ValueError):
            self.record_review(old, 'old-attempt.json')
        self.assertEqual(self.semantic(), 'stale')

    def test_notes_summary_heading_or_context_change_stales_review(self):
        for kind in ('notes', 'summary', 'heading', 'context'):
            with self.subTest(kind=kind):
                # Restore content so each subcase starts from valid current artifacts.
                if not self.job.exists():
                    self.ready()
                else:
                    self.chapter('ch001')
                obj = self.payload()
                context = self.job / 'work' / 'glossary.md'
                context.write_text('term=padanan', encoding='utf-8')
                obj['context_inputs'] = {'work/glossary.md': sha(context.read_bytes())}
                self.record_review(obj)
                if kind == 'notes':
                    self.artifact('notes', 'ch001-s00001', '{"reviewed":true,"notes":[{"anchor":"ch001-s00001","text":"New note."}]}')
                elif kind == 'summary':
                    self.artifact('summary', 'ch001', 'New summary.', segment_ids=['ch001-s00001', 'ch001-s00002'])
                elif kind == 'heading':
                    self.artifact('heading', 'ch001', 'New heading')
                else:
                    context.write_text('term=new padanan', encoding='utf-8')
                self.assertEqual(self.semantic(), 'stale')

    def test_declared_context_must_exist_and_match_at_record_time(self):
        self.ready()
        context = self.job / 'work' / 'glossary.md'
        context.write_text('system=sistem', encoding='utf-8')
        payload = self.payload()
        payload['context_inputs'] = {'work/glossary.md': '0' * 64}
        with self.assertRaises(ValueError):
            self.record_review(payload)
        payload['context_inputs'] = {'work/missing.md': '0' * 64}
        with self.assertRaises(ValueError):
            self.record_review(payload, 'missing-context.json')

    def test_same_chapter_extension_stales_review_but_other_chapter_extension_does_not(self):
        self.ready()
        self.record_review()
        store.extend_selection(self.job, select_scope(self.index, chapter_ids=['ch002']))
        self.assertEqual(self.semantic(), 'passed')
        self.assertEqual(self.semantic('ch002'), 'not_reviewed')
        self.assertFalse(store.status(self.job)['semantic_review_complete'])
        self.chapter('ch002')
        self.record_review(self.payload('ch002'), 'review-two.json')
        self.assertTrue(store.status(self.job)['semantic_review_complete'])

    def test_same_chapter_partial_extension_stales_review(self):
        self.index['source']['format'], self.index['page_count'] = 'pdf', 3
        for n, segment in enumerate(self.index['segments'], 1):
            segment['anchors'] = [{'page': n}]
        self.initialize(select_scope(self.index, pages=[1]))
        self.artifact('heading', 'ch001', 'One')
        self.artifact('translation', 'ch001-s00001')
        self.artifact('notes', 'ch001-s00001', '{"reviewed":true,"notes":[]}')
        self.artifact('summary', 'ch001', 'Partial.', segment_ids=['ch001-s00001'])
        self.record_review()
        store.extend_selection(self.job, select_scope(self.index, pages=[2]))
        self.assertEqual(self.semantic(), 'stale')

    def test_malformed_reports_and_unsafe_paths_rejected(self):
        self.ready()
        good = self.payload()
        for field, bad in [('version', 99), ('findings', 'not-list'), ('limitations', []),
                           ('context_inputs', {'../escape': '0' * 64}), ('coverage', [None]),
                           ('verdict', 'perfect'), ('inputs', None)]:
            obj = copy.deepcopy(good)
            obj[field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.record_review(obj)
        for path in [self.src, self.job / 'state/checkpoint.json', self.job / 'work/translation-ch001-s00001.md']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                store.record_artifact(self.job, {'kind': 'review', 'unit_id': 'ch001', 'path': str(path)})

    def test_missing_review_or_corrupt_content_cannot_pass(self):
        self.ready()
        path = self.record_review()
        path.unlink()
        self.assertFalse(store.status(self.job)['semantic_review_complete'])
        self.assertTrue(store.status(self.job)['issues'])
        self.record_review()
        (self.job / 'work/translation-ch001-s00001.md').write_text('tampered', encoding='utf-8')
        self.assertFalse(store.status(self.job)['semantic_review_complete'])
        self.assertEqual(self.semantic(), 'stale')
        with self.assertRaises(ValueError):
            self.record_review(self.payload(), 'attempt.json')
        (self.job / 'work/translation-ch001-s00001.md').unlink()
        self.assertEqual(self.semantic(), 'stale')

    def test_relevant_recorded_failure_stales_chapter_review(self):
        self.ready()
        self.record_review()
        store.record_failure(self.job, 'translation:ch001-s00001', 'Re-translation needs retry')
        self.assertEqual(self.semantic(), 'stale')

    def test_another_chapters_corrupt_artifact_does_not_block_review_record(self):
        self.ready(('ch001', 'ch002'))
        (self.job / 'work/translation-ch002-s00001.md').write_text('tampered', encoding='utf-8')
        self.record_review(self.payload('ch001'), 'review-one.json')
        self.assertEqual(self.semantic('ch001'), 'passed')

    def test_empty_selection_never_counts_as_reviewed(self):
        store.init_job(self.job, self.index, self.config)
        self.assertFalse(store.status(self.job)['semantic_review_complete'])
