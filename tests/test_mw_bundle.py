from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mary_workflow import default_state, read_state, write_state  # noqa: E402
from mw_bundle import (  # noqa: E402
    BundleError, CORE_REFERENCES, CORE_SCRIPTS, CORE_SKILLS, LOCK_FILE,
    apply_migration, apply_upgrade, forward_to_pinned, install_bundle,
    preview_migration, preview_upgrade, verify_bundle,
)


class BundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "project" / ".mary-workflow"
        self.source = self.base / "skill"
        self.root.mkdir(parents=True)
        for name in CORE_SCRIPTS:
            path = self.source / "scripts" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# Fixture for {name}\n", encoding="utf-8")
        for name in CORE_REFERENCES:
            path = self.source / "references" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# Contract {name}\n", encoding="utf-8")
        for name in CORE_SKILLS:
            path = self.source / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"# Profile {name}\n", encoding="utf-8")
        (self.source / "defaults").mkdir()
        (self.source / "defaults" / "reading-profile.md").write_text("# Defaults\n", encoding="utf-8")
        (self.source / "references" / "phases").mkdir()
        for name in ("mw-init.md", "mw-plan.md", "mw-ready.md", "mw-execute.md", "mw-review.md", "mw-debug.md", "mw-resume.md"):
            (self.source / "references" / "phases" / name).write_text(f"# {name}\n", encoding="utf-8")
        self.state = default_state(self.root.parent, scan_project=False)
        write_state(self.root, self.state)

    def tree(self) -> dict[str, bytes]:
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
                and "migrations" not in path.relative_to(self.root).parts and path.name != ".write.lock"}

    def legacy_state(self, phase: str = "PLANNING") -> dict:
        state = deepcopy(self.state)
        state.update({
            "phase": phase, "project_brief_status": "complete", "project_brief_version": 2,
            "project_inventory": ["src/a.py"],
            "project_file_ledger": [{"path": "src/a.py", "purpose": "Core", "exports": ["a"], "used_by": []}],
            "project_uncertainties": [{"topic": "latency", "status": "unresolved", "detail": "Not measured"}],
        })
        if phase != "PLANNING":
            state["milestones"] = [{"id": "m1", "status": "pending", "title": "Build core",
                                    "deliverables": ["src/a.py"], "acceptance": ["python check.py"],
                                    "estimated_scope": 1, "gate": "auto", "review": ""}]
            state["current_milestone_id"] = "m1"
        if phase in {"EXECUTING", "REVIEWING", "DEBUGGING"}:
            state.update({"final_plan_confirmed": True, "lease_status": "active", "lease_run_id": "existing-run",
                          "lease_plan_digest": "old-digest", "interview_status": "complete"})
        if phase == "REVIEWING":
            state["milestones"][0]["status"] = "done"
        write_state(self.root, state)
        path = self.root / "state.yaml"
        text = path.read_text(encoding="utf-8").replace("version: 3.0", "version: 2.1", 1)
        text += "\nrun_grant:\n  token_digest: legacy-token-digest\n  purpose: start\n"
        path.write_text(text, encoding="utf-8")
        (self.root / "reports").mkdir(exist_ok=True)
        (self.root / "reports" / "m1.md").write_text("Historical execution evidence\n", encoding="utf-8")
        (self.root / "log.md").write_text("Historical log\n", encoding="utf-8")
        return state

    def test_install_pins_core_code_prompts_and_contracts_without_source_paths(self) -> None:
        manifest = install_bundle(self.root, self.source)
        self.assertEqual(manifest["state_version"], "3.0")
        for name in CORE_SCRIPTS:
            self.assertIn(f"runtime/scripts/{name}", manifest["files"])
        for name in CORE_REFERENCES:
            self.assertIn(f"runtime/references/{name}", manifest["files"])
        for name in CORE_SKILLS:
            self.assertIn(f"runtime/skills/{name}/SKILL.md", manifest["files"])
        self.assertNotIn(str(self.source), json.dumps(manifest))
        self.assertEqual(manifest, verify_bundle(self.root))

    def test_ordinary_install_keeps_pinned_version_after_source_upgrade(self) -> None:
        manifest = install_bundle(self.root, self.source)
        before = self.tree()
        (self.source / "scripts" / "mary_workflow.py").write_text("# Updated source\n", encoding="utf-8")
        self.assertEqual(install_bundle(self.root, self.source), manifest)
        self.assertEqual(self.tree(), before)

    def test_ordinary_install_cannot_silently_repair_tampered_prompt(self) -> None:
        install_bundle(self.root, self.source)
        (self.root / "prompts" / "mw-execute.md").write_text("Altered instructions", encoding="utf-8")
        with self.assertRaisesRegex(BundleError, "file changed"):
            install_bundle(self.root, self.source)

    def test_missing_source_does_not_partially_install(self) -> None:
        (self.source / "scripts" / "mw_host.py").unlink()
        before = self.tree()
        with self.assertRaisesRegex(BundleError, "missing"):
            install_bundle(self.root, self.source)
        self.assertEqual(before, self.tree())

    def test_verify_rejects_extra_runtime_code_and_missing_core_files(self) -> None:
        install_bundle(self.root, self.source)
        rogue = self.root / "runtime" / "scripts" / "injected.py"
        rogue.write_text("# injected", encoding="utf-8")
        with self.assertRaisesRegex(BundleError, "file set changed"):
            verify_bundle(self.root)
        rogue.unlink()
        (self.root / "runtime" / "scripts" / "mw_brief.py").unlink()
        with self.assertRaisesRegex(BundleError, "file set changed"):
            verify_bundle(self.root)

    def test_manifest_paths_cannot_escape_project(self) -> None:
        install_bundle(self.root, self.source)
        manifest = json.loads((self.root / LOCK_FILE).read_text())
        manifest["files"]["runtime/../../outside"] = "0" * 64
        (self.root / LOCK_FILE).write_text(json.dumps(manifest))
        with self.assertRaisesRegex(BundleError, "Unsafe manifest path"):
            verify_bundle(self.root)

    def test_verify_ignores_interpreter_bytecode_cache(self) -> None:
        install_bundle(self.root, self.source)
        cache = self.root / "runtime" / "scripts" / "__pycache__"
        cache.mkdir()
        (cache / "mw_runtime.cpython-314.pyc").write_bytes(b"cached")
        verify_bundle(self.root)

    def test_forward_uses_verified_pinned_script_and_preserves_arguments(self) -> None:
        install_bundle(self.root, self.source)
        with mock.patch("mw_bundle.subprocess.run", return_value=mock.Mock(returncode=7)) as run:
            result = forward_to_pinned(self.root, "mary_workflow.py", ["status", "--flag", "space value"])
        self.assertEqual(result, 7)
        self.assertEqual(run.call_args.args[0], [sys.executable, str(self.root / "runtime" / "scripts" / "mary_workflow.py"),
                                                "status", "--flag", "space value"])
        self.assertFalse(run.call_args.kwargs["check"])

    def test_forward_does_not_loop_or_intercept_explicit_migration_upgrade(self) -> None:
        install_bundle(self.root, self.source)
        with mock.patch("mw_bundle.subprocess.run") as run:
            self.assertIsNone(forward_to_pinned(self.root, "mary_workflow.py", ["migrate", "--apply"]))
            self.assertIsNone(forward_to_pinned(self.root, "mary_workflow.py", ["upgrade", "--apply"]))
            self.assertIsNone(forward_to_pinned(self.root, "mary_workflow.py", ["init", "--reset"]))
            with mock.patch.object(sys, "argv", [str(self.root / "runtime" / "scripts" / "mary_workflow.py")]):
                self.assertIsNone(forward_to_pinned(self.root, "mary_workflow.py", ["status"]))
            run.assert_not_called()

    def test_direct_pinned_reset_cannot_delete_its_own_runtime_source(self) -> None:
        install_bundle(self.root, self.source)
        with mock.patch("mw_bundle.__file__", str(self.root / "runtime" / "scripts" / "mw_bundle.py")):
            with self.assertRaisesRegex(BundleError, "installed skill entrypoint"):
                forward_to_pinned(self.root, "mary_workflow.py", ["init", "--reset"])

    def test_preview_migration_performs_no_project_writes(self) -> None:
        self.legacy_state("EXECUTING")
        before = self.tree()
        preview = preview_migration(self.root)
        self.assertTrue(preview["will_pause"])
        self.assertEqual(preview["brief_refresh"], "deferred_until_stable_phase")
        self.assertEqual(self.tree(), before)
        self.assertFalse((self.root / "migrations").exists())

    def test_migration_keeps_legacy_evidence_and_requires_honest_module_refresh(self) -> None:
        old = self.legacy_state()
        before = self.tree()
        result = apply_migration(self.root, self.source)
        state = read_state(self.root)
        self.assertEqual(state["version"], "3.0")
        self.assertEqual(state["phase"], "PLANNING")
        self.assertEqual(state["project_brief_status"], "refresh_required")
        self.assertEqual(state["project_file_ledger"], old["project_file_ledger"])
        self.assertEqual(state["project_uncertainties"], old["project_uncertainties"])
        self.assertFalse(state["runtime_meta"]["brief"]["coverage"]["complete"])
        self.assertEqual((self.root / "reports" / "m1.md").read_bytes(), before["reports/m1.md"])
        self.assertEqual((Path(result["backup"]) / "state.yaml").read_bytes(), before["state.yaml"])
        self.assertEqual((self.root / "log.md").read_bytes(), before["log.md"])

    def test_active_migration_pauses_and_preserves_run_authorization(self) -> None:
        self.legacy_state("EXECUTING")
        apply_migration(self.root, self.source)
        state = read_state(self.root)
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["lease_status"], "paused")
        self.assertEqual(state["lease_run_id"], "existing-run")
        self.assertTrue(state["final_plan_confirmed"])
        self.assertTrue(state["runtime_meta"]["legacy_brief_refresh_pending"])
        self.assertEqual(state["lease_plan_digest"], state["runtime_meta"]["frozen_plan_digest"])
        legacy = state["runtime_meta"]["legacy_transition"]
        self.assertEqual(legacy["authorization"]["lease_plan_digest"], "old-digest")
        self.assertEqual(legacy["authorization"]["run_grant_digest"], "legacy-token-digest")

    def test_pending_legacy_review_returns_to_execution_without_erasing_report(self) -> None:
        self.legacy_state("REVIEWING")
        apply_migration(self.root, self.source)
        state = read_state(self.root)
        self.assertEqual(state["phase"], "EXECUTING")
        self.assertEqual(state["milestones"][0]["status"], "pending")
        self.assertEqual(state["runtime_meta"]["legacy_transition"]["pending_review"]["status"], "done")
        self.assertEqual((self.root / "reports" / "m1.md").read_text(), "Historical execution evidence\n")

    def test_migration_failure_restores_original_state_and_keeps_backup(self) -> None:
        self.legacy_state()
        before = self.tree()

        def fail(root: Path, source: Path, *, replace: bool) -> None:
            (root / "state.yaml").write_text("broken intermediate state")
            raise OSError("simulated install failure")

        with mock.patch("mw_bundle._install_bundle", side_effect=fail):
            with self.assertRaisesRegex(OSError, "simulated"):
                apply_migration(self.root, self.source)
        self.assertEqual(self.tree(), before)
        self.assertEqual(len(list((self.root / "migrations").glob("backup-*"))), 1)

    def test_upgrade_preview_is_read_only_and_apply_replaces_only_bundle(self) -> None:
        install_bundle(self.root, self.source)
        before_state = (self.root / "state.yaml").read_bytes()
        (self.source / "scripts" / "mary_workflow.py").write_text("# New runtime\n", encoding="utf-8")
        before = self.tree()
        preview = preview_upgrade(self.root, self.source)
        self.assertEqual(preview["changed_files"], ["runtime/scripts/mary_workflow.py"])
        self.assertEqual(self.tree(), before)
        result = apply_upgrade(self.root, self.source)
        self.assertEqual((self.root / "state.yaml").read_bytes(), before_state)
        self.assertEqual((self.root / "runtime" / "scripts" / "mary_workflow.py").read_text(), "# New runtime\n")
        self.assertTrue(Path(result["backup"]).is_dir())
        verify_bundle(self.root)

    def test_explicit_upgrade_can_restore_drift_and_preserves_custom_prompts(self) -> None:
        custom = self.root / "prompts" / "custom.md"
        custom.parent.mkdir()
        custom.write_text("# Project-specific prompt\n", encoding="utf-8")
        install_bundle(self.root, self.source)
        (self.root / "prompts" / "mw-execute.md").write_text("Drifted instructions", encoding="utf-8")
        self.assertTrue(preview_upgrade(self.root, self.source)["detected_drift"])
        apply_upgrade(self.root, self.source)
        self.assertEqual(custom.read_text(), "# Project-specific prompt\n")
        verify_bundle(self.root)

    def test_upgrade_rejects_running_workflow_or_unsettled_workers(self) -> None:
        install_bundle(self.root, self.source)
        self.state.update(phase="EXECUTING", status="running")
        write_state(self.root, self.state)
        with self.assertRaisesRegex(BundleError, "Stop the active workflow"):
            apply_upgrade(self.root, self.source)
        self.state.update(status="stopped")
        self.state["runtime_meta"]["stop_pending"] = True
        write_state(self.root, self.state)
        with self.assertRaisesRegex(BundleError, "verify quiescence"):
            apply_upgrade(self.root, self.source)
        apply_upgrade(self.root, self.source, workers_quiescent=True)

    def test_current_state_uses_explicit_upgrade_instead_of_repeated_migration(self) -> None:
        self.assertFalse(preview_migration(self.root)["required"])
        with self.assertRaisesRegex(BundleError, "already current"):
            apply_migration(self.root, self.source)

    def test_real_pinned_entrypoints_run_outside_the_skill_checkout(self) -> None:
        source = Path(__file__).resolve().parents[1]
        install_bundle(self.root, source)
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        for script, args in [
            ("mary_workflow.py", ["status"]),
            ("mw_codex.py", ["mw-status", "--project-root", str(self.root.parent)]),
            ("mw_host.py", ["capabilities"]),
        ]:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, "-B", str(self.root / "runtime" / "scripts" / script), *args],
                    cwd=self.root.parent, env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip())
        verify_bundle(self.root)


if __name__ == "__main__":
    unittest.main()
