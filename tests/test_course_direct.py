from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mw_codex import COURSE_SKILLS, main, prompt_path_for, render_prompt
from mw_bundle import install_bundle, verify_bundle


class DirectCourseTests(unittest.TestCase):
    def test_no_init_state_hashes_or_control_writes_needed(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            with mock.patch('mw_codex.read_state', side_effect=AssertionError('direct task read formal state')):
                for alias, skill in COURSE_SKILLS.items():
                    phase, source = prompt_path_for(project, alias)
                    self.assertEqual(phase, 'DIRECT')
                    self.assertEqual(source.parent.name, skill)
                    self.assertIn(source.read_text().split('---', 2)[2].strip(), render_prompt(project, alias))
            self.assertEqual(list(project.iterdir()), [])

    def test_unrelated_malformed_state_is_not_a_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            state = project / '.mary-workflow/state.yaml'
            state.parent.mkdir()
            state.write_text('unrelated invalid formal state')
            before = state.read_bytes()
            self.assertIn('Exam Review', render_prompt(project, 'mw-exam'))
            self.assertEqual(state.read_bytes(), before)

    def test_direct_cli_does_not_forward_to_a_pinned_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch('mw_bundle.forward_to_pinned', side_effect=AssertionError('direct course bundle audit')), mock.patch('builtins.print') as output:
                self.assertEqual(main(['mw-learn', '--project-root', directory]), 0)
            self.assertIn('Lecture Learning', output.call_args.args[0])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_explicit_formal_entry_requires_existing_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                render_prompt(Path(directory), 'mw-learn', formal=True)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_bundle_has_shared_policy_and_direct_course_entry_works(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root = project / '.mary-workflow'
            manifest = install_bundle(root, ROOT)
            self.assertIn('runtime/references/task-policy.md', manifest['files'])
            command = [sys.executable, str(root / 'runtime/scripts/mw_codex.py'), 'mw-exam', '--project-root', str(project)]
            response = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertEqual(response.returncode, 0, response.stderr)
            self.assertIn(str(root / 'runtime/references/task-policy.md'), response.stdout)
            self.assertFalse((root / 'state.yaml').exists())
            self.assertEqual(verify_bundle(root), manifest)
