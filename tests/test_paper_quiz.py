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
    PaperError,
    append_prepared_quiz_session,
    apply_paper_action,
    create_paper,
    paper_directory,
    prepare_quiz,
    prepare_summary,
    propose_quiz_question,
    read_paper_state,
    validate_prepared_quiz,
)
from mw_paper_quiz import (  # noqa: E402
    JUDGMENTS,
    QUIZ_CONTEXT_SCHEMA,
    QUIZ_HEAD_FILE,
    QUIZ_LOG_FILE,
    next_quiz_question,
    parse_quiz_log,
    render_quiz_log,
    validate_quiz_history,
)
from mw_paper_sources import sha256_file  # noqa: E402
from tests.paper_read_helpers import write_read_fixture, write_summary_fixture  # noqa: E402


def fingerprint(character: str) -> str:
    return character * 64


class QuizContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)
        self.locator = "https://arxiv.org/abs/2401.12345v2"
        self.paper_id = "arxiv-2401.12345v2"
        create_paper(self.project, self.locator, fingerprint("1"), self.paper_id)
        apply_paper_action(
            self.project,
            self.paper_id,
            {"action": "start_stage", "data": {"stage": "read"}},
        )
        self.workspace = paper_directory(self.project, self.paper_id)
        notes_fingerprint = write_read_fixture(
            self.workspace,
            paper_id=self.paper_id,
            locator=self.locator,
            source_fingerprint=fingerprint("1"),
        )
        apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "read",
                    "artifact": "paper-notes.md",
                    "output_fingerprint": notes_fingerprint,
                },
            },
        )
        prepare_summary(self.project, self.paper_id)
        summary_fingerprint = write_summary_fixture(self.workspace)
        apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "summary",
                    "artifact": "summary.md",
                    "output_fingerprint": summary_fingerprint,
                },
            },
        )
        self.state, self.context = prepare_quiz(self.project, self.paper_id)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def payload(
        self,
        *,
        uncertainty_ids: list[str] | None = None,
        method_ids: list[str] | None = None,
        judgment: str = "supported",
        locator: str = "html#S1",
        evidence: str = "Fixture source.",
    ) -> dict[str, object]:
        return {
            "question": "How should this paper detail be understood?",
            "anchors": {
                "uncertainty_ids": uncertainty_ids or [],
                "method_claim_ids": method_ids or [],
            },
            "answer": "This answer explains the selected paper detail.",
            "judgment": judgment,
            "rationale": "The judgment follows from the cited normalized source excerpt.",
            "citations": [{"source_locator": locator, "evidence": evidence}],
        }

    def append_uncertainty(self, judgment: str = "uncertain") -> dict[str, object]:
        return append_prepared_quiz_session(
            self.project,
            self.paper_id,
            self.payload(uncertainty_ids=["U01"], judgment=judgment),
        )[1]

    def append_method(self, judgment: str = "supported") -> dict[str, object]:
        return append_prepared_quiz_session(
            self.project,
            self.paper_id,
            self.payload(method_ids=["M01"], judgment=judgment),
        )[1]

    def complete(self, output_fingerprint: str | None = None) -> dict[str, object]:
        return apply_paper_action(
            self.project,
            self.paper_id,
            {
                "action": "complete_stage",
                "data": {
                    "stage": "quiz",
                    "artifact": QUIZ_LOG_FILE,
                    "output_fingerprint": output_fingerprint
                    or sha256_file(self.workspace / QUIZ_LOG_FILE),
                },
            },
        )

    def test_prepare_quiz_builds_pedagogical_catalogs_and_empty_history(self) -> None:
        self.assertEqual(self.state["stages"]["quiz"]["status"], "in_progress")
        self.assertEqual(self.context["quiz_context_schema"], QUIZ_CONTEXT_SCHEMA)
        self.assertEqual(self.context["quiz_attempt"], 1)
        self.assertEqual(
            self.context["scientific_uncertainty_catalog"][0]["uncertainty_id"],
            "U01",
        )
        self.assertEqual(self.context["source_quality_notes"], [])
        self.assertEqual(self.context["method_claim_catalog"][0]["claim_id"], "M01")
        self.assertTrue(
            self.context["completion_requirements"]["require_scientific_uncertainty_anchor"]
        )
        self.assertEqual(tuple(self.context["judgments"]), JUDGMENTS)
        sessions, head = validate_quiz_history(self.workspace, paper_id=self.paper_id)
        self.assertEqual(sessions, [])
        self.assertEqual(head["session_count"], 0)
        self.assertTrue((self.workspace / "quiz-context.json").is_file())
        self.assertTrue((self.workspace / QUIZ_LOG_FILE).is_file())
        self.assertTrue((self.workspace / QUIZ_HEAD_FILE).is_file())

    def test_question_generator_covers_method_before_scientific_uncertainty(self) -> None:
        first = propose_quiz_question(self.project, self.paper_id)[1]
        self.assertEqual(first["anchors"], {"uncertainty_ids": [], "method_claim_ids": ["M01"]})
        self.assertIn("method pipeline", first["question"])
        self.append_method()
        second = propose_quiz_question(self.project, self.paper_id)[1]
        self.assertEqual(second["anchors"], {"uncertainty_ids": ["U01"], "method_claim_ids": []})
        self.append_uncertainty()
        third = propose_quiz_question(self.project, self.paper_id)[1]
        self.assertEqual(third["anchors"], {"uncertainty_ids": [], "method_claim_ids": ["M01"]})

    def test_all_four_judgments_append_and_complete_with_metadata(self) -> None:
        sessions = [
            self.append_uncertainty("supported"),
            self.append_method("partially-supported"),
            self.append_method("unsupported"),
            self.append_uncertainty("uncertain"),
        ]
        self.assertEqual([session["judgment"] for session in sessions], list(JUDGMENTS))
        self.assertEqual([session["session_id"] for session in sessions], ["Q001", "Q002", "Q003", "Q004"])
        self.assertEqual(sessions[1]["previous_entry_hash"], sessions[0]["entry_hash"])
        readable_log = (self.workspace / QUIZ_LOG_FILE).read_text(encoding="utf-8")
        self.assertIn("## Q001 · supported", readable_log)
        self.assertIn("**Question:**", readable_log)
        self.assertIn("**Source citations:**", readable_log)
        self.assertIn("<summary>Machine record</summary>", readable_log)

        state = self.complete()
        quiz = state["stages"]["quiz"]
        self.assertEqual(quiz["status"], "complete")
        self.assertEqual(quiz["artifact"], QUIZ_LOG_FILE)
        self.assertEqual(quiz["metadata"]["session_count"], 4)
        self.assertEqual(quiz["metadata"]["history_session_count"], 4)
        self.assertEqual(
            quiz["metadata"]["judgment_counts"],
            {judgment: 1 for judgment in JUDGMENTS},
        )
        self.assertEqual(quiz["metadata"]["uncertainty_anchor_ids"], ["U01"])
        self.assertEqual(quiz["metadata"]["method_claim_anchor_ids"], ["M01"])

    def test_invalid_judgment_is_rejected_without_appending(self) -> None:
        log_before = (self.workspace / QUIZ_LOG_FILE).read_bytes()
        head_before = (self.workspace / QUIZ_HEAD_FILE).read_bytes()
        with self.assertRaisesRegex(PaperError, "judgment must be one of"):
            append_prepared_quiz_session(
                self.project,
                self.paper_id,
                self.payload(uncertainty_ids=["U01"], judgment="correct"),
            )
        self.assertEqual((self.workspace / QUIZ_LOG_FILE).read_bytes(), log_before)
        self.assertEqual((self.workspace / QUIZ_HEAD_FILE).read_bytes(), head_before)

    def test_session_requires_known_nonempty_anchors(self) -> None:
        with self.assertRaisesRegex(PaperError, "must select at least one"):
            append_prepared_quiz_session(self.project, self.paper_id, self.payload())
        with self.assertRaisesRegex(PaperError, "unknown uncertainty ids: U99"):
            append_prepared_quiz_session(
                self.project,
                self.paper_id,
                self.payload(uncertainty_ids=["U99"]),
            )
        with self.assertRaisesRegex(PaperError, "unknown method claim ids: M99"):
            append_prepared_quiz_session(
                self.project,
                self.paper_id,
                self.payload(method_ids=["M99"]),
            )

    def test_citations_must_be_anchor_backed_exact_source_excerpts(self) -> None:
        with self.assertRaisesRegex(PaperError, "is not backed by the selected anchors"):
            append_prepared_quiz_session(
                self.project,
                self.paper_id,
                self.payload(
                    uncertainty_ids=["U01"],
                    locator="html#S1.F1",
                    evidence="Figure 1: Fixture method overview.",
                ),
            )
        with self.assertRaisesRegex(PaperError, "evidence does not resolve"):
            append_prepared_quiz_session(
                self.project,
                self.paper_id,
                self.payload(uncertainty_ids=["U01"], evidence="Invented source excerpt."),
            )

    def test_completion_requires_a_method_anchor(self) -> None:
        self.append_uncertainty()
        with self.assertRaises(SystemExit) as rejection:
            self.complete()
        self.assertIn("at least one method-claim-anchored session", str(rejection.exception))
        self.append_method()
        self.assertEqual(self.complete()["stages"]["quiz"]["status"], "complete")

    def test_completion_requires_scientific_uncertainty_when_catalog_is_nonempty(self) -> None:
        self.append_method()
        with self.assertRaises(SystemExit) as rejection:
            self.complete()
        self.assertIn("scientific-uncertainty-anchored session", str(rejection.exception))
        self.append_uncertainty()
        self.assertEqual(self.complete()["stages"]["quiz"]["status"], "complete")

    def test_changing_answer_or_judgment_is_detected(self) -> None:
        self.append_uncertainty("supported")
        log_path = self.workspace / QUIZ_LOG_FILE
        log_path.write_text(
            log_path.read_text(encoding="utf-8").replace(
                '"judgment": "supported"',
                '"judgment": "unsupported"',
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "canonical append-only history"):
            validate_quiz_history(self.workspace, paper_id=self.paper_id)

    def test_deleting_history_is_detected_against_head(self) -> None:
        self.append_uncertainty()
        self.append_method()
        log_path = self.workspace / QUIZ_LOG_FILE
        sessions = parse_quiz_log(log_path.read_text(encoding="utf-8"))
        log_path.write_text(render_quiz_log(sessions[:-1]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs from quiz-head.json"):
            validate_quiz_history(self.workspace, paper_id=self.paper_id)

    def test_quiz_history_symlink_is_rejected(self) -> None:
        log_path = self.workspace / QUIZ_LOG_FILE
        external = self.workspace / "external-log.md"
        external.write_bytes(log_path.read_bytes())
        log_path.unlink()
        log_path.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "must not be symbolic links"):
            validate_quiz_history(self.workspace, paper_id=self.paper_id)

    def test_context_tampering_is_rejected(self) -> None:
        context_path = self.workspace / "quiz-context.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))
        context["quiz_attempt"] = 99
        context_path.write_text(json.dumps(context), encoding="utf-8")
        with self.assertRaisesRegex(PaperError, "quiz-context.json is stale"):
            propose_quiz_question(self.project, self.paper_id)

    def test_reset_preserves_history_but_requires_new_attempt_sessions(self) -> None:
        self.append_uncertainty()
        self.append_method()
        self.complete()
        old_log = (self.workspace / QUIZ_LOG_FILE).read_text(encoding="utf-8")
        apply_paper_action(
            self.project,
            self.paper_id,
            {"action": "reset_stage", "data": {"stage": "quiz"}},
        )
        state, context = prepare_quiz(self.project, self.paper_id)
        self.assertEqual(state["stages"]["quiz"]["attempts"], 2)
        self.assertEqual(context["quiz_attempt"], 2)
        self.assertEqual((self.workspace / QUIZ_LOG_FILE).read_text(encoding="utf-8"), old_log)
        with self.assertRaisesRegex(PaperError, "current quiz attempt"):
            validate_prepared_quiz(self.project, self.paper_id)
        self.append_uncertainty()
        self.append_method()
        state = self.complete()
        self.assertEqual(state["stages"]["quiz"]["metadata"]["session_count"], 2)
        self.assertEqual(state["stages"]["quiz"]["metadata"]["history_session_count"], 4)

    def test_declared_output_fingerprint_cannot_bypass_gate(self) -> None:
        self.append_uncertainty()
        self.append_method()
        with self.assertRaises(SystemExit) as rejection:
            self.complete(fingerprint("f"))
        self.assertIn("output_fingerprint does not match quiz-log.md", str(rejection.exception))
        state = read_paper_state(self.project, self.paper_id)
        self.assertEqual(state["stages"]["quiz"]["status"], "in_progress")

    def test_prepare_next_append_lint_complete_cli(self) -> None:
        def run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/mw_paper.py"),
                    "--project-root",
                    str(self.project),
                    *arguments,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=check,
            )

        prepared = run("prepare-quiz", "--paper-id", self.paper_id)
        self.assertIn("quiz_context:", prepared.stdout)
        next_question = json.loads(run("next-quiz-question", "--paper-id", self.paper_id).stdout)
        self.assertEqual(next_question["anchors"]["method_claim_ids"], ["M01"])
        for payload in (
            self.payload(method_ids=["M01"], judgment="partially-supported"),
            self.payload(uncertainty_ids=["U01"], judgment="uncertain"),
        ):
            appended = run(
                "append-quiz-session",
                "--paper-id",
                self.paper_id,
                "--json",
                json.dumps(payload),
            )
            self.assertIn("appended_session", json.loads(appended.stdout))
        self.assertEqual(json.loads(run("lint-quiz", "--paper-id", self.paper_id).stdout)["lint"], "passed")
        completed = json.loads(run("complete-quiz", "--paper-id", self.paper_id).stdout)
        self.assertEqual(completed["paper"]["stages"]["quiz"]["status"], "complete")


class QualityUncertaintyFilteringTests(unittest.TestCase):
    def test_parse_quality_uncertainty_is_audit_only_and_method_can_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            locator = "https://arxiv.org/abs/2401.54321v1"
            paper_id = "arxiv-2401.54321v1"
            create_paper(project, locator, fingerprint("2"), paper_id)
            apply_paper_action(
                project,
                paper_id,
                {"action": "start_stage", "data": {"stage": "read"}},
            )
            workspace = paper_directory(project, paper_id)
            notes_fingerprint = write_read_fixture(
                workspace,
                paper_id=paper_id,
                locator=locator,
                source_fingerprint=fingerprint("2"),
                statuses={
                    "text": "pass",
                    "structure": "pass",
                    "equations": "not_applicable",
                    "figures": "degraded",
                    "tables": "not_applicable",
                },
            )
            apply_paper_action(
                project,
                paper_id,
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "read",
                        "artifact": "paper-notes.md",
                        "output_fingerprint": notes_fingerprint,
                    },
                },
            )
            prepare_summary(project, paper_id)
            summary_fingerprint = write_summary_fixture(workspace)
            apply_paper_action(
                project,
                paper_id,
                {
                    "action": "complete_stage",
                    "data": {
                        "stage": "summary",
                        "artifact": "summary.md",
                        "output_fingerprint": summary_fingerprint,
                    },
                },
            )
            _, context = prepare_quiz(project, paper_id)
            self.assertEqual(context["scientific_uncertainty_catalog"], [])
            self.assertEqual(context["source_quality_notes"][0]["note_id"], "SQ01")
            self.assertEqual(context["source_quality_notes"][0]["quality_dimensions"], ["figures"])
            self.assertFalse(
                context["completion_requirements"]["require_scientific_uncertainty_anchor"]
            )
            proposal = propose_quiz_question(project, paper_id)[1]
            self.assertEqual(
                proposal["anchors"],
                {"uncertainty_ids": [], "method_claim_ids": ["M01"]},
            )
            append_prepared_quiz_session(
                project,
                paper_id,
                {
                    "question": "How does the paper's core method mechanism work?",
                    "anchors": {"uncertainty_ids": [], "method_claim_ids": ["M01"]},
                    "answer": "The method applies the grounded fixture mechanism.",
                    "judgment": "supported",
                    "rationale": "The direct method claim is present in the cited source span.",
                    "citations": [
                        {"source_locator": "html#S1", "evidence": "Fixture source."}
                    ],
                },
            )
            validation = validate_prepared_quiz(project, paper_id)[1]
            self.assertEqual(validation["metadata"]["uncertainty_anchor_ids"], [])
            self.assertEqual(validation["metadata"]["method_claim_anchor_ids"], ["M01"])

    def test_chinese_method_claim_produces_a_chinese_paper_question(self) -> None:
        context = {
            "scientific_uncertainty_catalog": [],
            "method_claim_catalog": [
                {
                    "claim_id": "M01",
                    "claim_text": "场景外观由球谐函数表示。",
                    "evidence": "Fixture source.",
                    "source_locators": ["html#S1"],
                }
            ],
        }
        proposal = next_quiz_question(context, [], context_fingerprint="f" * 64)
        self.assertIn("请结合论文的方法流程说明", proposal["question"])
        self.assertNotIn("PDF", proposal["question"])


if __name__ == "__main__":
    unittest.main()
