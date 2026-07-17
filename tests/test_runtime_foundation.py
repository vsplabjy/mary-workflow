from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mary_workflow import (  # noqa: E402
    apply_action,
    default_state,
    load_json_payload,
    parse_json_payload as parse_workflow_json_payload,
    read_state,
    write_state,
)
from mw_runtime import (  # noqa: E402
    EnvelopeError,
    action_envelope_parts,
    append_log_entry,
    atomic_write_text,
    extract_first_json_object,
    parse_json_payload,
    require_json_object,
)


class EnvelopeFoundationTests(unittest.TestCase):
    def test_parses_direct_fenced_and_embedded_json(self) -> None:
        expected = {"action": "status"}
        self.assertEqual(parse_json_payload('{"action":"status"}'), expected)
        self.assertEqual(parse_json_payload('```json\n{"action":"status"}\n```'), expected)
        self.assertEqual(parse_json_payload('result: {"action":"status"} done'), expected)

    def test_embedded_object_balances_nested_data_and_escaped_strings(self) -> None:
        raw = 'prefix {"action":"update","data":{"value":"brace } and \\\"quote\\\""}} suffix'
        candidate = extract_first_json_object(raw)
        self.assertEqual(candidate, '{"action":"update","data":{"value":"brace } and \\\"quote\\\""}}')
        self.assertEqual(parse_json_payload(raw)["data"]["value"], 'brace } and "quote"')

    def test_parse_errors_keep_existing_messages(self) -> None:
        with self.assertRaisesRegex(EnvelopeError, "^Invalid fenced JSON action:"):
            parse_json_payload('```json\n{"action":}\n```')
        with self.assertRaisesRegex(EnvelopeError, "^Invalid JSON action: no JSON object found\\.$"):
            parse_json_payload("not an action")

    def test_outer_object_and_action_data_are_validated_separately(self) -> None:
        with self.assertRaisesRegex(EnvelopeError, "^JSON action must be an object\\.$"):
            require_json_object([])
        self.assertEqual(action_envelope_parts({"action": 7}), ("7", {}))
        with self.assertRaisesRegex(EnvelopeError, "^Action data must be an object\\.$"):
            action_envelope_parts({"action": "update", "data": []})

    def test_workflow_adapter_keeps_system_exit_contract(self) -> None:
        with self.assertRaises(SystemExit) as context:
            parse_workflow_json_payload("not an action")
        self.assertEqual(str(context.exception), "Invalid JSON action: no JSON object found.")

        args = argparse.Namespace(file=None, json="[]")
        with self.assertRaises(SystemExit) as context:
            load_json_payload(args)
        self.assertEqual(str(context.exception), "JSON action must be an object.")


class PersistenceFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def assert_no_temporary_files(self, target: Path) -> None:
        self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_atomic_write_replaces_from_same_directory_and_preserves_mode(self) -> None:
        target = self.root / "state.yaml"
        target.write_text("old\n", encoding="utf-8")
        target.chmod(0o640)

        with mock.patch("mw_runtime.os.replace", wraps=os.replace) as replace:
            atomic_write_text(target, "new\n")

        self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
        source, destination = replace.call_args.args
        self.assertEqual(Path(source).parent, target.parent)
        self.assertEqual(Path(destination), target)
        self.assert_no_temporary_files(target)

    def test_replace_failure_preserves_old_file_and_cleans_temporary(self) -> None:
        target = self.root / "state.yaml"
        target.write_text("old\n", encoding="utf-8")

        with mock.patch("mw_runtime.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                atomic_write_text(target, "new\n")

        self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
        self.assert_no_temporary_files(target)

    def test_flush_failure_preserves_old_file_and_cleans_temporary(self) -> None:
        target = self.root / "state.yaml"
        target.write_text("old\n", encoding="utf-8")

        with mock.patch("mw_runtime.os.fsync", side_effect=OSError("fsync failed")):
            with self.assertRaisesRegex(OSError, "fsync failed"):
                atomic_write_text(target, "new\n")

        self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
        self.assert_no_temporary_files(target)

    def test_append_log_creates_header_once_and_appends_entries(self) -> None:
        log_path = self.root / "log.md"
        append_log_entry(
            log_path,
            "first",
            timestamp="2026-01-01T00:00:00+00:00",
            header="# Runtime Log\n\n",
        )
        append_log_entry(
            log_path,
            "second",
            timestamp="2026-01-01T00:00:01+00:00",
            header="# Runtime Log\n\n",
        )

        self.assertEqual(
            log_path.read_text(encoding="utf-8"),
            "# Runtime Log\n\n"
            "- 2026-01-01T00:00:00+00:00 first\n"
            "- 2026-01-01T00:00:01+00:00 second\n",
        )

    def test_workflow_state_serialization_stays_byte_stable(self) -> None:
        workflow = self.root / ".mary-workflow"
        workflow.mkdir()
        write_state(workflow, default_state(self.root, scan_project=False))
        before = (workflow / "state.yaml").read_bytes()

        write_state(workflow, read_state(workflow))

        self.assertEqual((workflow / "state.yaml").read_bytes(), before)

    def test_workflow_state_replace_failure_preserves_previous_state(self) -> None:
        workflow = self.root / ".mary-workflow"
        workflow.mkdir()
        state = default_state(self.root, scan_project=False)
        write_state(workflow, state)
        before = (workflow / "state.yaml").read_bytes()
        state["status"] = "changed"

        with mock.patch("mw_runtime.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                write_state(workflow, state)

        self.assertEqual((workflow / "state.yaml").read_bytes(), before)
        self.assert_no_temporary_files(workflow / "state.yaml")

    def test_invalid_action_data_keeps_rejection_state_and_log_path(self) -> None:
        workflow = self.root / ".mary-workflow"
        workflow.mkdir()
        write_state(workflow, default_state(self.root, scan_project=False))

        with self.assertRaises(SystemExit) as context:
            apply_action(workflow, {"action": "update_project", "data": []})

        self.assertEqual(
            str(context.exception),
            "Rejected action update_project: Action data must be an object.",
        )
        state = read_state(workflow)
        self.assertEqual(state["rejected_actions"], 1)
        log = (workflow / "log.md").read_text(encoding="utf-8")
        self.assertIn(
            "rejected action=update_project phase=PLANNING reason=Action data must be an object.",
            log,
        )


if __name__ == "__main__":
    unittest.main()
