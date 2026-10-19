"""Scoped command evidence must stay separate from whole-workspace ownership checks."""
from pathlib import Path
import copy
import json
import shlex
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mw_workers as workers
from mary_workflow import default_state, write_state, read_state, normalize_milestones, milestone_plan_signature, WorkflowError


class ValidationInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.root = self.project / '.mary-workflow'
        self.root.mkdir()
        for name in ['product.txt', 'notes.md', 'unrelated.txt']:
            (self.project / name).write_text('original')
        self.command = shlex.quote(sys.executable) + ' -c ' + shlex.quote("from pathlib import Path; assert Path('product.txt').read_text() == 'finished'")
        self.milestone = {'id': 'milestone-1', 'title': 'Delivery', 'deliverables': ['product.txt'],
                          'write_scope': ['product.txt', 'notes.md'], 'read_dependencies': [],
                          'acceptance': [self.command], 'validation_inputs': ['product.txt'], 'estimated_scope': 2}
        self.state = {'phase': 'EXECUTING', 'status': 'running', 'cycle': 'C0', 'lease_run_id': 'run-1',
                      'current_milestone_id': 'milestone-1', 'milestones': [self.milestone],
                      'runtime_meta': {'plan_revision': 1, 'execution_mode': 'single_agent'}}

    def dispatch(self, task_id='implementation', **extra):
        return workers.create_task(self.root, self.state,
            {'task_id': task_id, 'agent_id': task_id, 'role': 'implementer', 'objective': 'Deliver', 'write_scope': self.milestone['write_scope'], **extra})

    def validate(self, task):
        return workers.run_validation(self.root, self.state,
            {'task_id': task['task_id'], 'attempt_id': task['attempt_id'], 'acceptance_id': 'check-1'})

    def submit(self, task, evidence, changed):
        return workers.submit_result(self.root, self.state,
            {'task_id': task['task_id'], 'attempt_id': task['attempt_id'], 'status': 'ready_for_review',
             'summary': 'Delivered', 'files_changed': changed, 'validation': [evidence['evidence_id']],
             'scope_deviations': [], 'blockers': [], 'uncertainties': []})

    def test_notes_can_change_after_validation_without_rerunning_product_check(self):
        task = self.dispatch()
        (self.project / 'product.txt').write_text('finished')
        original = workers._file_digest
        def guard(path):
            if path.name == 'unrelated.txt':
                raise AssertionError('Validation read an unrelated file')
            return original(path)
        with mock.patch.object(workers, '_file_digest', guard):
            evidence = self.validate(task)
        (self.project / 'notes.md').write_text('documented after validation')
        result = self.submit(task, evidence, ['notes.md', 'product.txt'])
        self.assertEqual(result['result']['validation'], [evidence['evidence_id']])
        accepted = workers.verify_milestone_evidence(self.root, self.state, self.milestone,
                                                    {'task_ids': [task['task_id']]})
        self.assertEqual(len(accepted['validation']), 1)
        self.assertEqual(accepted['validation'][0]['validation_inputs'], ['product.txt'])

    def test_dependency_change_invalidates_receipt_even_with_same_file_length(self):
        task = self.dispatch()
        (self.project / 'product.txt').write_text('finished')
        evidence = self.validate(task)
        (self.project / 'product.txt').write_text('broken!!')
        with self.assertRaisesRegex(workers.WorkerError, 'stale'):
            self.submit(task, evidence, ['product.txt'])

    def test_scope_violation_is_still_detected_at_delivery(self):
        self.milestone['acceptance'] = [shlex.quote(sys.executable) + ' -c ' + shlex.quote("from pathlib import Path; Path('unrelated.txt').write_text('illegal')")]
        task = self.dispatch()
        evidence = self.validate(task)
        self.assertEqual(evidence['exit_code'], 0)
        with self.assertRaisesRegex(workers.WorkerError, 'Out-of-scope'):
            self.submit(task, evidence, [])

    def test_input_creation_and_deletion_change_identity(self):
        self.milestone['validation_inputs'].append('optional.txt')
        task = self.dispatch()
        (self.project / 'product.txt').write_text('finished')
        evidence = self.validate(task)
        (self.project / 'optional.txt').write_text('appeared')
        task = json.loads((self.root / 'tasks' / task['task_id'] / 'task.json').read_text())
        # Direct input evidence check isolates freshness from the separate scope gate.
        snapshot = workers._task_snapshot(self.root, task, audit=True)
        with self.assertRaisesRegex(workers.WorkerError, 'stale'):
            workers._evidence(self.root, task, evidence['evidence_id'], snapshot)
        (self.project / 'optional.txt').unlink()
        (self.project / 'product.txt').unlink()
        with self.assertRaisesRegex(workers.WorkerError, 'stale'):
            workers._evidence(self.root, task, evidence['evidence_id'], workers._task_snapshot(self.root, task, audit=True))

    def test_domain_is_frozen_and_cannot_be_narrowed_in_the_task(self):
        task = self.dispatch()
        path = self.root / 'tasks' / task['task_id'] / 'task.json'
        modified = json.loads(path.read_text())
        modified['validation_inputs'] = ['notes.md']
        path.write_text(json.dumps(modified))
        with self.assertRaisesRegex(workers.WorkerError, 'domain differs'):
            self.validate(task)

    def test_read_dependencies_are_checked_but_not_all_are_test_inputs(self):
        self.milestone['read_dependencies'] = ['unrelated.txt']
        task = self.dispatch()
        (self.project / 'product.txt').write_text('finished')
        evidence = self.validate(task)
        (self.project / 'unrelated.txt').write_text('dependency changed')
        with self.assertRaisesRegex(workers.WorkerError, 'Out-of-scope'):
            self.submit(task, evidence, ['product.txt'])

    def test_domain_roundtrips_state_and_changes_plan_signature(self):
        state = default_state(self.project, scan_project=False)
        normalized = normalize_milestones([self.milestone])
        state['milestones'] = normalized
        write_state(self.root, state)
        self.assertEqual(read_state(self.root)['milestones'][0]['validation_inputs'], ['product.txt'])
        original = milestone_plan_signature(normalized)
        changed = copy.deepcopy(normalized)
        changed[0]['validation_inputs'].append('notes.md')
        self.assertNotEqual(original, milestone_plan_signature(changed))

    def test_empty_or_unsafe_domain_is_rejected(self):
        for inputs in [[], ['../outside'], ['*.py']]:
            self.milestone['validation_inputs'] = inputs
            with self.assertRaises((ValueError, WorkflowError)):
                normalize_milestones([self.milestone])

    def test_scoped_evidence_supports_same_agent_review_without_global_rerun(self):
        task = self.dispatch()
        (self.project / 'product.txt').write_text('finished')
        evidence = self.validate(task)
        self.submit(task, evidence, ['product.txt'])
        self.state['phase'] = 'REVIEWING'
        reviewer = self.dispatch('reviewer', role='verifier', agent_id=task['agent_id'], write_scope=[],
                                 reviews_task_ids=[task['task_id']])
        workers.submit_result(self.root, self.state,
            {'task_id': reviewer['task_id'], 'attempt_id': reviewer['attempt_id'], 'status': 'ready_for_review',
             'summary': 'Reviewed', 'files_changed': [], 'validation': [], 'decision': 'passed',
             'findings': [], 'review_mode': 'same_agent'})
        accepted = workers.verify_review_evidence(self.root, self.state, self.milestone,
                                                 {'verifier_task_id': reviewer['task_id']})
        self.assertFalse(accepted['independent_review'])
        self.assertEqual(len(accepted['validation']), 1)
