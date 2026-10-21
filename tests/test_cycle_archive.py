"""A failed cycle archive preserves evidence and can finish on the next call."""
from __future__ import annotations

import argparse
from pathlib import Path
import unittest
from unittest import mock

import test_workflow_boundaries as fixtures
import mary_workflow as mw


class CycleArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.WorkflowBoundaryTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        (self.root / 'reports').mkdir(exist_ok=True)
        (self.root / 'reports' / 'receipt.txt').write_text('original evidence\n')

    def tearDown(self):
        self.fixture.tearDown()

    def cycle(self):
        with mock.patch.object(Path, 'cwd', return_value=self.fixture.project):
            return mw.cmd_cycle(argparse.Namespace(workers_quiescent=False))

    def make_html_reports(self):
        (self.root / 'reports' / 'index.html').write_text('<html>entry</html>\n')
        bundle = self.root / 'reports' / '20261021T120000Z-e8-decoder'
        (bundle / 'assets').mkdir(parents=True)
        (bundle / 'index.html').write_text('<html>report</html>\n')
        (bundle / 'assets' / 'style.css').write_text('body { color: #123456 }\n')
        return bundle

    def seed_formal_receipts(self):
        (self.root / 'reports' / 'C0').mkdir()
        (self.root / 'reports' / 'C0' / 'receipt.md').write_text('formal receipt\n')


    def test_copy_failure_preserves_source_and_retries(self):
        with mock.patch.object(mw.shutil, 'copytree', side_effect=OSError('interrupted copy')):
            with self.assertRaisesRegex(OSError, 'interrupted copy'):
                self.cycle()
        self.assertTrue((self.root / 'reports/receipt.txt').exists())
        self.assertTrue((self.root / 'cycle-archive.json').exists())
        self.assertFalse((self.root / 'cycles/C0').exists())
        with self.assertRaisesRegex(mw.WorkflowError, 'recover'):
            self.fixture.act('update_interview', mode='propose', clarifications=['Requested'], draft_milestones=[fixtures.milestone()])
        self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.assertEqual((self.root / 'cycles/C0/reports/receipt.txt').read_text(), 'original evidence\n')
        self.assertFalse((self.root / 'cycle-archive.json').exists())

    def test_state_write_failure_after_copy_and_cleanup_recovers(self):
        real_write = mw.write_state
        def interrupted(root, state):
            if state['cycle'] == 'C1':
                raise OSError('state interrupted')
            real_write(root, state)
        with mock.patch.object(mw, 'write_state', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'state interrupted'):
                self.cycle()
        self.assertTrue((self.root / 'cycles/C0/reports/receipt.txt').exists())
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C0')
        self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.assertTrue((self.root / 'cycles/C0/reports/receipt.txt').exists())

    def test_failure_after_new_state_recovers_without_starting_another_cycle(self):
        with mock.patch.object(mw, 'write_project_brief', side_effect=OSError('brief interrupted')):
            with self.assertRaisesRegex(OSError, 'brief interrupted'):
                self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.assertFalse((self.root / 'cycles/C1').exists())

    def test_archive_collision_never_overwrites_or_creates_transaction(self):
        archive = self.root / 'cycles/C0'
        archive.mkdir(parents=True)
        (archive / 'user.txt').write_text('preserve')
        with self.assertRaisesRegex(mw.WorkflowError, 'already exists'):
            self.cycle()
        self.assertEqual((archive / 'user.txt').read_text(), 'preserve')
        self.assertFalse((self.root / 'cycle-archive.json').exists())

    def test_symlink_receipt_never_changes_external_target_permissions(self):
        target = self.fixture.project / 'private-evidence.txt'
        target.write_text('external evidence')
        target.chmod(0o600)
        (self.root / 'reports/link.txt').symlink_to(target)
        # Product fixture must be refreshed because the new external file is real.
        state = mw.read_state(self.root)
        mw.apply_project_detection(state, mw.detect_project(self.fixture.project))
        mw.write_state(self.root, state)
        self.cycle()
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.root / 'cycles/C0/reports/link.txt').is_symlink())

    def test_top_level_control_symlink_rejected_without_copying_external_data(self):
        external = self.fixture.project / 'external'
        external.mkdir()
        (external / 'secret.txt').write_text('not a workflow report')
        mw.remove_tree(self.root / 'reports')
        (self.root / 'reports').symlink_to(external, target_is_directory=True)
        state = mw.read_state(self.root)
        mw.apply_project_detection(state, mw.detect_project(self.fixture.project))
        mw.write_state(self.root, state)
        with self.assertRaisesRegex(mw.WorkflowError, 'must not be symlinks'):
            self.cycle()
        self.assertFalse((self.root / 'cycles/C0').exists())
        self.assertEqual((external / 'secret.txt').read_text(), 'not a workflow report')

    def test_cycle_preserves_html_entry_and_report_bundles_in_place(self):
        bundle = self.make_html_reports()
        self.seed_formal_receipts()
        self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.assertEqual((self.root / 'reports' / 'index.html').read_bytes(), b'<html>entry</html>\n')
        self.assertEqual((bundle / 'index.html').read_bytes(), b'<html>report</html>\n')
        self.assertEqual((bundle / 'assets' / 'style.css').read_bytes(), b'body { color: #123456 }\n')
        self.assertFalse((self.root / 'reports' / 'C0').exists())
        self.assertFalse((self.root / 'reports' / 'receipt.txt').exists())
        self.assertEqual((self.root / 'cycles/C0/reports/receipt.md').read_text(), 'formal receipt\n')

    def test_html_reports_survive_without_formal_cycle_receipts(self):
        bundle = self.make_html_reports()
        (self.root / 'reports' / 'receipt.txt').unlink()
        self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.assertTrue((self.root / 'reports' / 'index.html').is_file())
        self.assertEqual((bundle / 'index.html').read_text(), '<html>report</html>\n')

    def test_interrupted_cleanup_retry_keeps_html_reports(self):
        bundle = self.make_html_reports()
        self.seed_formal_receipts()
        real_write = mw.write_state
        def interrupted(root, state):
            if state['cycle'] == 'C1':
                raise OSError('state interrupted')
            real_write(root, state)
        with mock.patch.object(mw, 'write_state', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'state interrupted'):
                self.cycle()
        self.assertTrue((self.root / 'cycles/C0').is_dir())
        self.assertTrue((self.root / 'cycle-archive.json').is_file())
        self.assertTrue((self.root / 'reports' / 'index.html').is_file())
        self.assertEqual((bundle / 'assets' / 'style.css').read_text(), 'body { color: #123456 }\n')
        self.assertFalse((self.root / 'reports' / 'C0').exists())
        self.cycle()
        self.assertEqual(mw.read_state(self.root)['cycle'], 'C1')
        self.assertEqual((self.root / 'reports' / 'index.html').read_text(), '<html>entry</html>\n')
        self.assertEqual((bundle / 'index.html').read_text(), '<html>report</html>\n')
        self.assertEqual((bundle / 'assets' / 'style.css').read_text(), 'body { color: #123456 }\n')
        self.assertEqual((self.root / 'cycles/C0/reports/receipt.md').read_text(), 'formal receipt\n')

    def test_directory_without_index_html_is_not_a_report_bundle(self):
        (self.root / 'reports' / 'not-a-bundle').mkdir()
        (self.root / 'reports' / 'not-a-bundle' / 'index.html').symlink_to(self.root / 'reports' / 'receipt.txt')
        self.cycle()
        self.assertFalse((self.root / 'reports' / 'not-a-bundle').exists())
        self.assertTrue((self.root / 'cycles/C0').is_dir())

    def test_cycle_named_directory_with_index_html_is_not_preserved(self):
        named = self.root / 'reports' / 'C7'
        named.mkdir()
        (named / 'index.html').write_text('<html>stale</html>\n')
        self.cycle()
        self.assertFalse((self.root / 'reports' / 'C7').exists())
        self.assertTrue((self.root / 'cycles/C0/reports/C7/index.html').is_file())
        self.assertTrue((self.root / 'cycles/C0').is_dir())


if __name__ == '__main__':
    unittest.main()
