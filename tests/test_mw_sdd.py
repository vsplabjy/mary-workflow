from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import mw_sdd as sdd


REQ = '### Requirement: Delivery\nThe system SHALL deliver.\n\n#### Scenario: Success\n- **WHEN** invoked\n- **THEN** delivery succeeds\n'


class SDDTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.change = self.project / 'openspec/changes/demo'
        self.change.mkdir(parents=True)
        (self.change / 'proposal.md').write_text('# Proposal\nImprove delivery\n')
        self.delta('## Purpose\nPreserved purpose.\n\n## ADDED Requirements\n' + REQ)
        self.tasks({'service::Delivery::Success': ['check-1']})

    def delta(self, text):
        path = self.change / 'specs/service/spec.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def tasks(self, covers):
        task = {'id': 'milestone-1', 'deliverables': ['delivery.py'], 'acceptance': ['python -m unittest'], 'estimated_scope': 1, 'covers': covers}
        (self.change / 'tasks.md').write_text('# Tasks\n\n- [ ] 1.1 Implement delivery\n\n```mary-task\n' + json.dumps(task) + '\n```\n')

    def base(self):
        path = self.project / 'openspec/specs/service/spec.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Service\n\n## Purpose\nPreserved purpose.\n\n## Requirements\n' + REQ)
        return path

    def load(self):
        return sdd.load_change(self.project, 'demo')

    def state(self, binding):
        return {'phase': 'FINISHED', 'cycle': 'C0', 'runtime_meta': {'sdd': binding}, 'milestones': [{'id': 'milestone-1', 'status': 'done', 'review': 'accepted'}]}

    def test_load_and_checkboxes_do_not_change_binding(self):
        binding = self.load()
        self.assertEqual(binding['milestones'][0]['title'], 'Implement delivery')
        sdd.sync_tasks(self.project, binding, {'milestone-1'})
        self.assertIn('- [x] 1.1', (self.change / 'tasks.md').read_text())
        self.assertEqual(binding, self.load())
        sdd.sync_tasks(self.project, binding, set())
        self.assertIn('- [ ] 1.1', (self.change / 'tasks.md').read_text())

    def test_missing_and_unknown_coverage(self):
        for covers in ({}, {'service::Bad::Success': ['check-1']}, {'service::Delivery::Success': ['check-2']}):
            self.tasks(covers)
            with self.assertRaises(sdd.SDDError):
                self.load()

    def test_invalid_scenarios_and_duplicate_requirements(self):
        for content in (REQ.replace('**THEN**', '**LATER**'), REQ.replace('SHALL', 'can'), REQ + REQ, REQ.replace('#### Scenario', '##### Scenario')):
            self.delta('## Purpose\nDelivery.\n\n## ADDED Requirements\n' + content)
            with self.assertRaises(sdd.SDDError):
                self.load()

    def test_drift_content_added_file_and_base(self):
        binding = self.load()
        (self.change / 'design.md').write_text('New architecture')
        with self.assertRaises(sdd.SDDError):
            sdd.assert_binding(self.project, binding)
        (self.change / 'design.md').unlink()
        self.base()
        with self.assertRaises(sdd.SDDError):
            sdd.assert_binding(self.project, binding)

    def test_modified_preserves_purpose(self):
        self.base()
        self.delta('## MODIFIED Requirements\n' + REQ.replace('deliver.', 'deliver reliably.'))
        binding = self.load()
        merged = binding['merged_specs']['openspec/specs/service/spec.md']
        self.assertIn('Preserved purpose.', merged)
        self.assertIn('deliver reliably.', merged)

    def test_removed_and_renamed(self):
        self.base()
        self.delta('## REMOVED Requirements\n### Requirement: Delivery\n**Reason**: Obsolete\n**Migration**: Use transport\n')
        self.tasks({'service::REMOVED::Delivery': ['check-1']})
        self.assertNotIn('### Requirement: Delivery', self.load()['merged_specs']['openspec/specs/service/spec.md'])
        self.delta('## RENAMED Requirements\n- FROM: `### Requirement: Delivery`\n- TO: `### Requirement: Transport`\n')
        self.tasks({'service::RENAMED::Delivery': ['check-1']})
        self.assertIn('### Requirement: Transport', self.load()['merged_specs']['openspec/specs/service/spec.md'])

    def test_missing_base_and_collision(self):
        self.delta('## MODIFIED Requirements\n' + REQ)
        with self.assertRaises(sdd.SDDError): self.load()
        self.base()
        self.delta('## Purpose\nPreserved purpose.\n\n## ADDED Requirements\n' + REQ)
        with self.assertRaises(sdd.SDDError): self.load()

    def test_skip_reason_required(self):
        (self.change / 'specs/service/spec.md').unlink()
        self.tasks({})
        (self.change / '.openspec.yaml').write_text('skip_specs: true\n')
        with self.assertRaises(sdd.SDDError): self.load()
        (self.change / '.openspec.yaml').write_text('skip_specs: true\nskip_reason: Documentation only\n')
        self.assertEqual(self.load()['merged_specs'], {})

    def test_archive_recovery_after_rename_failure(self):
        binding = self.load()
        root = self.project / '.mary-workflow'
        state = self.state(binding)
        with patch.object(Path, 'rename', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): sdd.archive_change(root, state)
        self.assertTrue((root / 'sdd-archive.json').exists())
        self.assertTrue((self.project / 'openspec/specs/service/spec.md').exists())
        target = sdd.archive_change(root, state)
        self.assertEqual(sdd.archive_change(root, state), target)
        self.assertTrue((self.project / target / 'tasks.md').exists())

    def test_archive_drift_after_partial_write_blocks(self):
        binding = self.load()
        root = self.project / '.mary-workflow'
        state = self.state(binding)
        with patch.object(Path, 'rename', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): sdd.archive_change(root, state)
        main = self.project / 'openspec/specs/service/spec.md'
        main.write_text('third party edit')
        with self.assertRaisesRegex(sdd.SDDError, 'Third-party drift'): sdd.archive_change(root, state)
        self.assertEqual(main.read_text(), 'third party edit')

    def test_archive_collision_and_unaccepted(self):
        binding = self.load()
        root = self.project / '.mary-workflow'
        state = self.state(binding)
        state['milestones'][0]['review'] = 'pending'
        with self.assertRaises(sdd.SDDError): sdd.archive_change(root, state)
        state['milestones'][0]['review'] = 'accepted'
        (self.project / 'openspec/changes/archive/C0-demo').mkdir(parents=True)
        with self.assertRaises(sdd.SDDError): sdd.archive_change(root, state)

    def test_task_definition_drift_and_duplicate_ids(self):
        binding = self.load()
        path = self.change / 'tasks.md'
        text = path.read_text()
        path.write_text(text.replace('Implement delivery', 'Implement transport'))
        with self.assertRaises(sdd.SDDError):
            sdd.assert_binding(self.project, binding)
        path.write_text(text + text.replace('1.1 ', '1.2 '))
        with self.assertRaisesRegex(sdd.SDDError, 'Duplicate'):
            self.load()

    def test_unknown_and_duplicate_operations(self):
        for text in ('## UPDATED Requirements\n' + REQ, '## ADDED Requirements\n' + REQ + '\n## ADDED Requirements\n' + REQ):
            self.delta('## Purpose\nDelivery.\n\n' + text)
            with self.assertRaisesRegex(sdd.SDDError, 'operation'):
                self.load()

    def test_archive_recovers_after_rename_before_completion(self):
        binding = self.load()
        root = self.project / '.mary-workflow'
        state = self.state(binding)
        atomic = sdd._atomic
        def interrupt(path, text):
            if path.name == 'sdd-archive.json' and json.loads(text).get('complete'):
                raise OSError('interrupted after rename')
            return atomic(path, text)
        with patch.object(sdd, '_atomic', side_effect=interrupt):
            with self.assertRaises(OSError):
                sdd.archive_change(root, state)
        self.assertFalse(self.change.exists())
        self.assertTrue((self.project / sdd.archive_change(root, state)).exists())

    def test_archive_rejects_corrupt_journal_before_writes(self):
        binding = self.load()
        root = self.project / '.mary-workflow'
        state = self.state(binding)
        with patch.object(Path, 'rename', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                sdd.archive_change(root, state)
        path = root / 'sdd-archive.json'
        journal = json.loads(path.read_text())
        journal['entries']['openspec/specs/service/spec.md']['after'] = 'forged'
        path.write_text(json.dumps(journal))
        with self.assertRaisesRegex(sdd.SDDError, 'payload'):
            sdd.archive_change(root, state)
        self.assertTrue(self.change.exists())
        self.assertNotEqual((self.project / 'openspec/specs/service/spec.md').read_text(), 'forged')

    def test_new_capability_requires_purpose(self):
        self.delta('## ADDED Requirements\n' + REQ)
        with self.assertRaisesRegex(sdd.SDDError, 'Purpose'):
            self.load()

    def test_nested_capability(self):
        old = self.change / 'specs/service/spec.md'
        nested = self.change / 'specs/service/transport/spec.md'
        nested.parent.mkdir()
        old.rename(nested)
        self.tasks({'service/transport::Delivery::Success': ['check-1']})
        self.assertIn('openspec/specs/service/transport/spec.md', self.load()['merged_specs'])

    def test_metadata_duplicate_rejected(self):
        (self.change / '.openspec.yaml').write_text('skip_specs: false\nskip_specs: true\n')
        with self.assertRaisesRegex(sdd.SDDError, 'Duplicate metadata'):
            self.load()

    def test_runtime_milestone_contract(self):
        path = self.change / 'tasks.md'
        text = path.read_text()
        path.write_text(text.replace('"estimated_scope": 1', '"estimated_scope": 0'))
        self.assertEqual(self.load()['milestones'][0]['estimated_scope'], 0)
        path.write_text(text.replace('milestone-1', 'milestone-name'))
        with self.assertRaises(sdd.SDDError):
            self.load()

    def test_repair_milestone_archive_and_no_rewrite(self):
        binding = self.load()
        state = self.state(binding)
        state['milestones'].append({'id': 'milestone-2', 'repair_of': 'milestone-1', 'status': 'done', 'review': 'accepted'})
        root = self.project / '.mary-workflow'
        target = sdd.archive_change(root, state)
        self.assertIn('- [x]', (self.project / target / 'tasks.md').read_text())
        with patch.object(sdd, '_atomic', side_effect=AssertionError('must not rewrite')):
            self.assertEqual(sdd.archive_change(root, state), target)

    def test_symlink_and_traversal(self):
        with self.assertRaises(sdd.SDDError): sdd.load_change(self.project, '../demo')
        (self.change / 'design.md').symlink_to(self.change / 'proposal.md')
        with self.assertRaises(sdd.SDDError): self.load()


if __name__ == '__main__':
    unittest.main()
