from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper import (  # noqa: E402
    PAPER_STATE_SCHEMA,
    PaperError,
    apply_paper_action,
    create_paper,
    derive_paper_id,
    list_paper_ids,
    normalize_paper_id,
    paper_directory,
    paper_progress,
    read_paper_state,
    resolve_paper_id,
)
from mary_workflow import default_state as default_workflow_state  # noqa: E402


def fingerprint(character: str) -> str:
    return character * 64


class PaperStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.source = "https://arxiv.org/abs/2401.12345v2"
        self.paper_id = "arxiv-2401.12345v2"
        self.state, created = create_paper(self.project, self.source, fingerprint("1"))
        self.assertTrue(created)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def apply(self, action: str, data: dict[str, object]) -> dict[str, object]:
        return apply_paper_action(
            self.project,
            self.paper_id,
            {"action": action, "data": data},
        )

    def complete(self, stage: str, digest: str) -> dict[str, object]:
        self.apply("start_stage", {"stage": stage})
        return self.apply(
            "complete_stage",
            {
                "stage": stage,
                "output_fingerprint": digest,
                "artifact": f"{stage}.md",
            },
        )

    def complete_all(self) -> dict[str, object]:
        self.complete("read", fingerprint("a"))
        self.complete("summary", fingerprint("b"))
        self.complete("slides", fingerprint("c"))
        return self.complete("quiz", fingerprint("d"))

    def test_paper_id_normalization_and_local_derivation(self) -> None:
        self.assertEqual(normalize_paper_id(self.source), self.paper_id)
        self.assertEqual(normalize_paper_id("arXiv:hep-th/9901001v3"), "arxiv-hep-th-9901001v3")
        self.assertEqual(derive_paper_id("/tmp/paper.pdf", fingerprint("f")), "local-ffffffffffffffff")
        for invalid in ("../paper", "paper/child", "paper..draft", "paper id"):
            with self.subTest(invalid=invalid), self.assertRaises(PaperError):
                normalize_paper_id(invalid)

    def test_create_is_independent_from_main_workflow_and_idempotent(self) -> None:
        workspace = paper_directory(self.project, self.paper_id)
        self.assertEqual(workspace, self.project / ".mary-research/papers" / self.paper_id)
        self.assertTrue((workspace / "state.json").is_file())
        self.assertTrue((workspace / "log.md").is_file())
        self.assertFalse((self.project / ".mary-workflow/state.yaml").exists())
        self.assertEqual(self.state["paper_state_schema"], PAPER_STATE_SCHEMA)
        self.assertEqual(set(self.state["stages"]), {"read", "summary", "slides", "quiz"})

        same, created = create_paper(self.project, self.source, fingerprint("1"))
        self.assertFalse(created)
        self.assertEqual(same["paper_id"], self.paper_id)
        with self.assertRaises(PaperError):
            create_paper(self.project, self.source, fingerprint("2"), self.paper_id)

        workflow_state = default_workflow_state(self.project)
        self.assertFalse(any(path.startswith(".mary-research/") for path in workflow_state["project_inventory"]))

    def test_dependency_gate_rejects_summary_before_read(self) -> None:
        with self.assertRaises(SystemExit) as context:
            self.apply("start_stage", {"stage": "summary"})
        self.assertIn("blocked by incomplete dependencies: read", str(context.exception))

        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["summary"]["status"], "pending")
        self.assertEqual(state["audit"]["rejected_actions"], 1)
        log = (paper_directory(self.project, self.paper_id) / "log.md").read_text(encoding="utf-8")
        self.assertIn("action start_stage stage=summary", log)
        self.assertIn("rejected action=start_stage", log)

    def test_non_object_envelope_is_rejected_and_audited(self) -> None:
        with self.assertRaises(SystemExit) as context:
            apply_paper_action(self.project, self.paper_id, [])
        self.assertIn("JSON action must be an object", str(context.exception))

        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["audit"]["rejected_actions"], 1)
        log = (paper_directory(self.project, self.paper_id) / "log.md").read_text(encoding="utf-8")
        self.assertIn("rejected action=(missing)", log)

    def test_read_lifecycle_records_lineage_and_requires_reset_for_rerun(self) -> None:
        state = self.apply("start_stage", {"stage": "read"})
        self.assertEqual(state["stages"]["read"]["status"], "in_progress")
        self.assertEqual(state["stages"]["read"]["attempts"], 1)
        self.assertEqual(
            state["stages"]["read"]["input_fingerprints"],
            {"source": fingerprint("1")},
        )

        state = self.apply(
            "complete_stage",
            {"stage": "read", "output_fingerprint": fingerprint("a"), "artifact": "paper-notes.md"},
        )
        self.assertEqual(state["stages"]["read"]["status"], "complete")
        self.assertEqual(paper_progress(state), {"completed": 1, "total": 4, "eligible_stages": ["summary"]})
        with self.assertRaises(SystemExit):
            self.apply("start_stage", {"stage": "read"})

        state = self.apply("reset_stage", {"stage": "read"})
        self.assertEqual(state["stages"]["read"]["status"], "pending")
        self.assertEqual(state["stages"]["read"]["attempts"], 1)
        self.assertEqual(state["stages"]["read"]["output_fingerprint"], "")

    def test_quiz_depends_on_read_and_summary_but_not_slides(self) -> None:
        self.complete("read", fingerprint("a"))
        self.complete("summary", fingerprint("b"))

        state = self.apply("start_stage", {"stage": "quiz"})
        self.assertEqual(state["stages"]["quiz"]["status"], "in_progress")
        self.assertEqual(state["stages"]["slides"]["status"], "pending")
        self.assertEqual(
            state["stages"]["quiz"]["input_fingerprints"],
            {"read": fingerprint("a"), "summary": fingerprint("b")},
        )

    def test_source_change_cascades_stale_to_started_stages(self) -> None:
        self.complete_all()
        state = self.apply(
            "update_source",
            {"locator": self.source, "fingerprint": fingerprint("e")},
        )

        self.assertEqual(state["source"]["fingerprint"], fingerprint("e"))
        self.assertEqual(
            {stage: state["stages"][stage]["status"] for stage in state["stages"]},
            {"read": "stale", "summary": "stale", "slides": "stale", "quiz": "stale"},
        )
        state = self.apply("start_stage", {"stage": "read"})
        self.assertEqual(state["stages"]["read"]["output_fingerprint"], "")
        self.assertEqual(state["stages"]["read"]["input_fingerprints"], {"source": fingerprint("e")})

    def test_arxiv_revision_change_requires_a_separate_paper_id(self) -> None:
        with self.assertRaises(SystemExit) as context:
            self.apply(
                "update_source",
                {"locator": "https://arxiv.org/abs/2401.12345v3", "fingerprint": fingerprint("e")},
            )
        self.assertIn("requires paper_id arxiv-2401.12345v3", str(context.exception))
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["source"]["locator"], self.source)
        self.assertEqual(state["source"]["fingerprint"], fingerprint("1"))

    def test_source_change_leaves_never_started_downstream_pending(self) -> None:
        self.complete("read", fingerprint("a"))
        state = self.apply("update_source", {"fingerprint": fingerprint("e")})
        self.assertEqual(state["stages"]["read"]["status"], "stale")
        for stage in ("summary", "slides", "quiz"):
            self.assertEqual(state["stages"][stage]["status"], "pending")

    def test_reset_summary_stales_only_its_started_dependents(self) -> None:
        self.complete_all()
        state = self.apply("reset_stage", {"stage": "summary"})
        self.assertEqual(state["stages"]["read"]["status"], "complete")
        self.assertEqual(state["stages"]["summary"]["status"], "pending")
        self.assertEqual(state["stages"]["slides"]["status"], "stale")
        self.assertEqual(state["stages"]["quiz"]["status"], "stale")

    def test_failed_stage_can_retry_and_increments_attempts(self) -> None:
        self.apply("start_stage", {"stage": "read"})
        state = self.apply("fail_stage", {"stage": "read", "error": " parser unavailable "})
        self.assertEqual(state["stages"]["read"]["status"], "failed")
        self.assertEqual(state["stages"]["read"]["error"], "parser unavailable")
        state = self.apply("start_stage", {"stage": "read"})
        self.assertEqual(state["stages"]["read"]["attempts"], 2)

    def test_invalid_fingerprint_and_artifact_are_rejected(self) -> None:
        with self.assertRaises(PaperError):
            create_paper(self.project / "invalid", "/tmp/paper.pdf", "not-sha256")

        self.apply("start_stage", {"stage": "read"})
        with self.assertRaises(SystemExit) as context:
            self.apply(
                "complete_stage",
                {"stage": "read", "output_fingerprint": fingerprint("a"), "artifact": "../escape.md"},
            )
        self.assertIn("artifact must be a relative path", str(context.exception))
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["read"]["status"], "in_progress")
        self.assertEqual(state["audit"]["rejected_actions"], 1)

    def test_schema_mismatch_is_rejected(self) -> None:
        state_path = paper_directory(self.project, self.paper_id) / "state.json"
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        payload["paper_state_schema"] = 2
        state_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(PaperError, "Unsupported paper_state_schema: 2"):
            read_paper_state(self.project, self.paper_id)

    def test_multiple_papers_are_isolated_and_require_explicit_status_id(self) -> None:
        second, created = create_paper(self.project, "/tmp/other.pdf", fingerprint("2"))
        self.assertTrue(created)
        self.assertEqual(second["paper_id"], "local-2222222222222222")
        self.assertEqual(list_paper_ids(self.project), [self.paper_id, "local-2222222222222222"])
        with self.assertRaisesRegex(PaperError, "Multiple papers"):
            resolve_paper_id(self.project)
        self.assertEqual(resolve_paper_id(self.project, self.paper_id), self.paper_id)


class PaperCliAndSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.script = REPO_ROOT / "scripts/mw_paper.py"
        self.workflow_script = REPO_ROOT / "scripts/mary_workflow.py"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script), "--project-root", str(self.project), *arguments],
            cwd=self.project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_create_list_status_and_apply_action_cli(self) -> None:
        created = self.run_cli(
            "create",
            "--source",
            "https://arxiv.org/abs/2501.00001v1",
            "--fingerprint",
            fingerprint("3"),
        )
        self.assertIn("paper_workspace:", created.stdout)
        self.assertIn("created: true", created.stdout)
        self.assertEqual(self.run_cli("list").stdout.strip(), "arxiv-2501.00001v1")

        status = json.loads(self.run_cli("status").stdout)
        self.assertEqual(status["paper"]["paper_state_schema"], 1)
        self.assertEqual(status["progress"]["eligible_stages"], ["read"])

        action = self.run_cli(
            "apply-action",
            "--json",
            '{"action":"start_stage","data":{"stage":"read"}}',
        )
        self.assertEqual(json.loads(action.stdout)["paper"]["stages"]["read"]["status"], "in_progress")

    def test_cli_parse_error_is_rejected_and_audited(self) -> None:
        self.run_cli(
            "create",
            "--source",
            "https://arxiv.org/abs/2501.00003v1",
            "--fingerprint",
            fingerprint("5"),
        )
        rejected = subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--project-root",
                str(self.project),
                "apply-action",
                "--json",
                "{not-json",
            ],
            cwd=self.project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("Invalid JSON action", rejected.stderr)

        state = read_paper_state(self.project, "arxiv-2501.00003v1")
        self.assertEqual(state["audit"]["rejected_actions"], 1)

    def test_plugin_surfaces_mw_paper_without_claiming_content_stages(self) -> None:
        command = (REPO_ROOT / "commands/mw-paper.md").read_text(encoding="utf-8")
        skill = (REPO_ROOT / "skills/paper/SKILL.md").read_text(encoding="utf-8")
        contract = (REPO_ROOT / "references/paper-state-contract.md").read_text(encoding="utf-8")
        manifest = json.loads((REPO_ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))

        self.assertIn("# /mw-paper", command)
        self.assertIn("P1 implements state only", command)
        self.assertIn("name: paper", skill)
        self.assertIn("quiz` depends on `read` and `summary`, not `slides`", skill)
        self.assertIn("paper_state_schema", contract)
        self.assertTrue(manifest["version"].startswith("2.2.0-alpha.1"))

    def test_mw_init_reset_does_not_delete_paper_workspaces(self) -> None:
        self.run_cli(
            "create",
            "--source",
            "https://arxiv.org/abs/2501.00002v1",
            "--fingerprint",
            fingerprint("4"),
        )
        subprocess.run(
            [sys.executable, str(self.workflow_script), "init"],
            cwd=self.project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(self.workflow_script), "init", "--reset"],
            cwd=self.project,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        state = read_paper_state(self.project, "arxiv-2501.00002v1")
        self.assertEqual(state["source"]["fingerprint"], fingerprint("4"))


if __name__ == "__main__":
    unittest.main()
