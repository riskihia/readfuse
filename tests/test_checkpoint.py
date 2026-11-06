"""Run: python -m unittest discover -s tests -v"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'checkpoint.py'


class TestCheckpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.job = Path(self.tmp.name)
        (self.job / 'source').mkdir()
        (self.job / 'source' / 'ch001-s001.md').write_text('Hello world', encoding='utf-8')
        (self.job / 'manifest.json').write_text(json.dumps({
            'version': 1, 'source': 'book.pdf', 'target_language': 'id', 'mode': 'both',
            'chunks': [{'id': 'ch001-s001', 'source_path': 'source/ch001-s001.md'}]
        }))

    def run_cmd(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *args, '--job-dir', str(self.job)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_resume_and_integrity(self):
        self.run_cmd('init', '--manifest', str(self.job / 'manifest.json'))
        self.assertIn('pending', self.run_cmd('status').stdout)
        (self.job / 'translation').mkdir()
        (self.job / 'summary').mkdir()
        for kind, dirname in [('translation', 'translation'), ('summary', 'summary')]:
            dest = self.job / dirname / 'ch001-s001.md'
            dest.write_text('Translated or summarized text', encoding='utf-8')
            self.run_cmd('complete', '--chunk-id', 'ch001-s001', '--kind', kind, '--output', str(dest))
        state = json.loads(self.run_cmd('verify').stdout)
        self.assertEqual(state['counts']['complete'], 1)
        (self.job / 'translation' / 'ch001-s001.md').write_text('tampered', encoding='utf-8')
        self.run_cmd('verify', ok=False)

    def test_path_traversal_rejected(self):
        self.run_cmd('init', '--manifest', str(self.job / 'manifest.json'))
        bad = self.run_cmd('complete', '--chunk-id', 'ch001-s001', '--kind', 'translation', '--output', '../outside.md', ok=False)
        self.assertIn('escapes job', bad.stderr)


if __name__ == '__main__':
    unittest.main()
