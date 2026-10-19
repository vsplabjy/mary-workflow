from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mw_knowledge as knowledge


def intro(key, files, **extra):
    return {"id": key, "files": files,
            **{field: f"Recorded {field} of {key}" for field in knowledge.DETAILS}, **extra}


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def initial(self):
        return knowledge.update(self.project, {
            "overview": "Purpose and data flow", "handoff": "USER_STOP; do not restart training",
            "modules": [intro("core", ["src/core.py"], boundary_files=["schema.json"]),
                        intro("api", ["api.py"], depends_on=["core"]),
                        intro("ui", ["ui.py"], depends_on=["api"]),
                        intro("docs", ["README.md"]) ]}, 0)

    def test_read_missing_is_read_only_and_never_initializes(self):
        with mock.patch("pathlib.Path.rglob", side_effect=AssertionError("walk")), \
                mock.patch("os.walk", side_effect=AssertionError("walk")), \
                mock.patch("hashlib.sha256", side_effect=AssertionError("hash")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            knowledge.main(["--project", str(self.project), "read"])
        self.assertIn("UNKNOWN", out.getvalue())
        self.assertEqual(list(self.project.iterdir()), [])

    def test_changes_propagate_to_dependents_and_preserve_unrelated_intro(self):
        before = self.initial()
        with mock.patch("pathlib.Path.rglob", side_effect=AssertionError("walk")), \
                mock.patch("os.walk", side_effect=AssertionError("walk")), \
                mock.patch("hashlib.sha256", side_effect=AssertionError("hash")):
            data = knowledge.mark_changed(self.project, ["src/core.py", "schema.json", "new.py"], "API changes")
        for key in ("core", "api", "ui"):
            self.assertEqual(data["modules"][key]["status"], "stale")
            self.assertEqual(data["modules"][key]["pending_files"], ["schema.json", "src/core.py"])
        self.assertEqual(data["modules"]["docs"], before["modules"]["docs"])
        self.assertEqual(data["unmapped_files"], ["new.py", "schema.json"])
        self.assertIn("USER_STOP", knowledge.context_text(data))

    def test_update_cannot_clear_newer_revision_or_unreviewed_paths(self):
        self.initial()
        data = knowledge.mark_changed(self.project, ["src/core.py"], "change")
        payload = {"modules": [intro("core", ["src/core.py"], reviewed_files=["src/core.py"])]}
        with self.assertRaisesRegex(ValueError, "revision changed"):
            knowledge.update(self.project, payload, 1)
        payload["modules"][0]["reviewed_files"] = []
        with self.assertRaisesRegex(ValueError, "pending_files"):
            knowledge.update(self.project, payload, data["revision"])
        self.assertEqual(knowledge.load(self.project), data)
        payload["modules"][0]["reviewed_files"] = ["src/core.py"]
        updated = knowledge.update(self.project, payload, data["revision"])
        self.assertEqual(updated["modules"]["core"]["status"], "current")
        self.assertEqual(updated["modules"]["api"]["status"], "stale")

    def test_unknown_paths_need_explicit_documented_resolution(self):
        data = knowledge.mark_changed(self.project, ["new.py", "deleted.py"], "new module and deleted legacy")
        with self.assertRaises(ValueError):
            knowledge.update(self.project, {"resolved_unmapped_files": ["new.py"]}, data["revision"])
        data = knowledge.update(self.project, {
            "handoff": "Deleted obsolete deleted.py; new module introduced.",
            "modules": [intro("new", ["new.py"])],
            "resolved_unmapped_files": ["new.py", "deleted.py"], "removed_files": ["deleted.py"]}, data["revision"])
        self.assertEqual(data["unmapped_files"], [])

    def test_partial_write_retains_canonical_stale_marker_and_can_repair_views(self):
        self.initial()
        with mock.patch.object(knowledge, "render", side_effect=OSError("interrupted projection")):
            with self.assertRaises(OSError):
                knowledge.mark_changed(self.project, ["src/core.py"], "implementation in progress")
        data = knowledge.load(self.project)
        self.assertEqual(data["modules"]["core"]["status"], "stale")
        knowledge.render(self.project)
        self.assertIn("Status: stale", (knowledge.location(self.project) / "modules/core.md").read_text())

    def test_context_read_only_opens_index_not_code_or_projections(self):
        data = self.initial()
        original = Path.read_text
        opened = []
        def guarded(path, *args, **kwargs):
            opened.append(path.name)
            if path.name != "index.json":
                raise AssertionError(f"Unexpected read: {path}")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "read_text", guarded):
            output = knowledge.context_text(knowledge.load(self.project), ["api"])
        self.assertEqual(opened, ["index.json"])
        self.assertIn("Recorded interfaces of api", output)
        self.assertNotIn("Recorded interfaces of ui", output)
        self.assertEqual(knowledge.load(self.project), data)

    def test_change_does_not_read_or_rewrite_unaffected_module_views(self):
        self.initial()
        original = knowledge.atomic_write_text
        written = []
        def record(path, *args, **kwargs):
            written.append(path.name)
            return original(path, *args, **kwargs)
        with mock.patch.object(knowledge, "atomic_write_text", record):
            knowledge.mark_changed(self.project, ["README.md"], "documentation edit")
        self.assertIn("docs.md", written)
        self.assertNotIn("core.md", written)
        self.assertNotIn("api.md", written)

    def test_import_does_not_certify_summaries_or_overwrite_authored_text(self):
        brief = {"positioning": {"purpose": "Tool"}, "coverage": {"modules": [
            {"id": "core", "summary": "Core logic", "files": ["src/core.py"]}]}}
        seeded = knowledge.seed_brief(self.project, brief)
        self.assertEqual(seeded["modules"]["core"]["status"], "incomplete")
        updated = knowledge.update(self.project, {"modules": [intro("core", ["src/core.py"])]}, seeded["revision"])
        self.assertEqual(knowledge.seed_brief(self.project, brief), updated)

    def test_formal_metadata_import_does_not_change_product_files(self):
        knowledge.seed_brief(self.project, {"coverage": {"modules": []}}, ensure_ignore=False)
        self.assertFalse((self.project / ".gitignore").exists())
        self.assertTrue((knowledge.location(self.project) / "index.json").exists())

    def test_incremental_intro_patch_preserves_unchanged_fields(self):
        self.initial()
        changed = knowledge.mark_changed(self.project, ["src/core.py"], "new interface")
        updated = knowledge.update(self.project, {"modules": [{"id": "core", "interfaces": "New API",
            "reviewed_files": ["src/core.py"]}]}, changed["revision"])
        self.assertEqual(updated["modules"]["core"]["interfaces"], "New API")
        self.assertEqual(updated["modules"]["core"]["responsibility"], "Recorded responsibility of core")
        self.assertEqual(updated["modules"]["core"]["status"], "current")

    def test_import_missing_state_never_calls_scanning_default_state(self):
        with mock.patch("mary_workflow.detect_project", side_effect=AssertionError("scan")), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            knowledge.main(["--project", str(self.project), "import-brief"])
        self.assertEqual(list(self.project.iterdir()), [])

    def test_bad_paths_and_duplicate_ownership_fail_without_partial_commit(self):
        before = self.initial()
        for path in ("../outside", "/absolute", ".", "x/../y", "x//y"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                knowledge.mark_changed(self.project, [path], "invalid")
        with self.assertRaisesRegex(ValueError, "duplicate module ownership"):
            knowledge.update(self.project, {"modules": [intro("other", ["api.py"])]}, before["revision"])
        self.assertEqual(knowledge.load(self.project), before)


if __name__ == "__main__":
    unittest.main()
