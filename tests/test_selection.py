import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from readfuse.sources import inspect_source


class TestSelection(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'book.md'
            p.write_text('\n\n'.join(f'# Chapter {i}\n\nA{i}\n\nB{i}' for i in range(1, 9)), encoding='utf-8')
            self.index = inspect_source(p)

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('readfuse.selection'), 'selection not implemented')
        return importlib.import_module('readfuse.selection')

    def test_continue_one_three_eight_four_in_source_order(self):
        api = self.api()
        existing = api.select_scope(self.index, chapter_ids=['ch001', 'ch002', 'ch003'])['segment_ids']
        for chapter in ['ch008', 'ch004']:
            existing = api.merge_coverage(self.index, existing, api.select_scope(self.index, chapter_ids=[chapter])['segment_ids'])
        self.assertEqual(existing, [f'ch{i:03}-s{j:05}' for i in [1, 2, 3, 4, 8] for j in [1, 2]])

    def test_shared_page_partial_and_overlap(self):
        idx = self.index
        idx['source']['format'] = 'pdf'
        idx['page_count'] = 16
        for n, s in enumerate(idx['segments']):
            s['anchors'] = [{'page': n + 1}]
        idx['segments'][2]['anchors'] = [{'page': 2}]
        a = self.api().select_scope(idx, pages=[2])
        self.assertEqual(a['segment_ids'], ['ch001-s00002', 'ch002-s00001'])
        self.assertEqual(a['coverage'], {'ch001': 'partial', 'ch002': 'partial'})
        b = self.api().select_scope(idx, pages=[1, 2])
        self.assertEqual(self.api().merge_coverage(idx, a['segment_ids'], b['segment_ids']), ['ch001-s00001', 'ch001-s00002', 'ch002-s00001'])

    def test_invalid_scopes_rejected(self):
        for kw in [{}, {'pages': [1]}, {'chapter_ids': ['unknown']}, {'chapter_ids': []}, {'chapter_ids': ['ch001'], 'all_content': True}]:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.api().select_scope(self.index, **kw)
