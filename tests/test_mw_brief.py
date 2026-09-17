from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mw_brief import (  # noqa: E402
    BriefError,
    affected_modules,
    merge_brief_update,
    migrate_legacy_ledger,
    normalize_coverage,
    normalize_records,
)


def module(module_id: str, files: list[str], **extra: object) -> dict:
    return {
        "id": module_id, "summary": f"Responsibilities of {module_id}",
        "files": files, "read_files": list(files), "boundary_files": [], **extra,
    }


class CoverageTests(unittest.TestCase):
    def test_machine_computation_ignores_claimed_complete_or_unread(self) -> None:
        result = normalize_coverage({
            "modules": [module("app", ["a.py", "b.py"], read_files=["a.py"])],
            "complete": True, "unread_files": [], "covered_count": 2,
        }, ["a.py", "b.py"])
        self.assertEqual(result["unread_files"], ["b.py"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["covered_count"], 1)

    def test_missing_inventory_is_rejected_even_when_claiming_no_unread(self) -> None:
        with self.assertRaisesRegex(BriefError, "missing inventory paths"):
            normalize_coverage({"modules": [module("app", ["a.py"])], "unread_files": []}, ["a.py", "b.py"])

    def test_unknown_paths_and_duplicate_ownership_are_rejected(self) -> None:
        with self.assertRaisesRegex(BriefError, "unknown inventory"):
            normalize_coverage({"modules": [module("app", ["absent.py"])]}, ["a.py"])
        with self.assertRaisesRegex(BriefError, "Duplicate file ownership"):
            normalize_coverage({"modules": [module("a", ["a.py"]), module("b", ["a.py"])]}, ["a.py"])

    def test_shared_boundary_paths_are_allowed_but_require_read_coverage(self) -> None:
        modules = [module("a", ["a.py"]), module("b", ["b.py"], boundary_files=["a.py"])]
        result = normalize_coverage({"modules": modules}, ["a.py", "b.py"])
        self.assertEqual(result["unread_files"], ["a.py"])
        modules[1]["read_files"].append("a.py")
        self.assertTrue(normalize_coverage({"modules": modules}, ["a.py", "b.py"])["complete"])

    def test_unknown_reads_and_dependencies_are_rejected(self) -> None:
        for extra, message in [
            ({"read_files": ["a.py", "b.py"]}, "owned or boundary"),
            ({"depends_on": ["missing"]}, "unknown or self dependencies"),
            ({"depends_on": ["a"]}, "unknown or self dependencies"),
        ]:
            with self.subTest(extra=extra), self.assertRaisesRegex(BriefError, message):
                normalize_coverage({"modules": [module("a", ["a.py"], **extra)]}, ["a.py"])

    def test_paths_cannot_escape_or_alias_inventory(self) -> None:
        for path in ["../a.py", "/a.py", "./a.py", "dir/../a.py", "a\\b.py"]:
            with self.subTest(path=path), self.assertRaisesRegex(BriefError, "canonical project-relative"):
                normalize_coverage({"modules": [module("a", [path])]}, [path])

    def test_empty_inventory_can_be_complete(self) -> None:
        result = normalize_coverage({"modules": []}, [])
        self.assertTrue(result["complete"])
        self.assertEqual(result["inventory_count"], 0)

    def test_significant_filename_spaces_are_preserved(self) -> None:
        result = normalize_coverage({"modules": [module("a", [" folder/a.py "])]}, [" folder/a.py "])
        self.assertEqual(result["modules"][0]["files"], [" folder/a.py "])
        self.assertTrue(result["complete"])


class IncrementalBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inventory = ["core.py", "api.py", "docs.md"]
        self.modules = [
            module("core", ["core.py"]),
            module("api", ["api.py"], depends_on=["core"]),
            module("docs", ["docs.md"]),
        ]
        self.existing = {
            "version": 2, "coverage": normalize_coverage({"modules": self.modules}, self.inventory),
            "positioning": {"purpose": "preserved"},
            "uncertainties": [{"topic": "latency", "status": "unresolved", "detail": "unmeasured"}],
            "records": [{"id": "d1", "kind": "decision", "text": "use local state", "source": "user"}],
        }

    def update(self, changed: list[str] | None = None) -> dict:
        return {
            "base_version": 2,
            "updated_modules": [], "deleted_modules": [],
            "retained_modules": [{"id": item["id"], "evidence": "Inventory and dependencies unchanged"} for item in self.modules],
            "reviewed_changed_files": changed or [],
        }

    def valid_core_update(self) -> dict:
        update = self.update(["core.py"])
        update["updated_modules"] = [
            module("core", ["core.py"], reread_files=["core.py"], review_evidence="Reviewed changed API"),
            module("api", ["api.py"], depends_on=["core"], reviewed_dependencies=["core"],
                   review_evidence="Inspected call sites; API remains valid"),
        ]
        update["retained_modules"] = [{"id": "docs", "evidence": "Unchanged inventory and no affected dependencies"}]
        return update

    def test_retained_brief_preserves_sections_and_increments_version_without_mutation(self) -> None:
        before = deepcopy(self.existing)
        result = merge_brief_update(self.existing, self.update(), self.inventory, [])
        self.assertEqual(result["version"], 3)
        self.assertEqual(result["positioning"], before["positioning"])
        self.assertEqual(result["uncertainties"], before["uncertainties"])
        self.assertEqual(self.existing, before)

    def test_stale_base_and_boolean_version_fail(self) -> None:
        for base in [1, 3, None, True]:
            update = self.update()
            update["base_version"] = base
            with self.subTest(base=base), self.assertRaisesRegex(BriefError, "base_version"):
                merge_brief_update(self.existing, update, self.inventory, [])

    def test_changes_compared_as_exact_set_including_deleted_paths(self) -> None:
        update = self.update()
        with self.assertRaisesRegex(BriefError, "exactly match"):
            merge_brief_update(self.existing, update, self.inventory, ["core.py"])
        update = self.valid_core_update()
        update["reviewed_changed_files"] = ["core.py", "core.py"]
        with self.assertRaisesRegex(BriefError, "duplicate"):
            merge_brief_update(self.existing, update, self.inventory, ["core.py"])

    def test_modules_cannot_disappear_or_be_implicitly_retained(self) -> None:
        update = self.update()
        update["retained_modules"].pop()
        with self.assertRaisesRegex(BriefError, "Every existing module"):
            merge_brief_update(self.existing, update, self.inventory, [])

    def test_unknown_deletion_fails(self) -> None:
        update = self.update()
        update["deleted_modules"] = ["unknown"]
        with self.assertRaisesRegex(BriefError, "existing module ids"):
            merge_brief_update(self.existing, update, self.inventory, [])

    def test_changed_module_cannot_be_retained_despite_evidence_claim(self) -> None:
        with self.assertRaisesRegex(BriefError, "Affected modules"):
            merge_brief_update(self.existing, self.update(["core.py"]), self.inventory, ["core.py"])

    def test_dependency_requires_review_not_implicit_retention(self) -> None:
        update = self.valid_core_update()
        update["updated_modules"].pop()
        update["retained_modules"].append({"id": "api", "evidence": "Files unchanged"})
        with self.assertRaisesRegex(BriefError, "Affected modules.*api"):
            merge_brief_update(self.existing, update, self.inventory, ["core.py"])

    def test_affected_module_requires_reread_and_dependency_evidence(self) -> None:
        for module_index, field, message in [(0, "reread_files", "requires reread_files"),
                                              (1, "reviewed_dependencies", "requires reviewed_dependencies"),
                                              (1, "review_evidence", "review_evidence")]:
            update = self.valid_core_update()
            del update["updated_modules"][module_index][field]
            with self.subTest(field=field), self.assertRaisesRegex(BriefError, message):
                merge_brief_update(self.existing, update, self.inventory, ["core.py"])

    def test_valid_incremental_change_preserves_unaffected_modules_and_history(self) -> None:
        update = self.valid_core_update()
        update["record_updates"] = [{"id": "d2", "kind": "decision", "text": "use checked local state", "supersedes": ["d1"]}]
        result = merge_brief_update(self.existing, update, self.inventory, ["core.py"])
        self.assertTrue(result["coverage"]["complete"])
        self.assertEqual([item["id"] for item in result["records"]], ["d1", "d2"])
        self.assertEqual(result["refresh_evidence"]["affected_modules"], ["api", "core"])

    def test_module_deletion_requires_dependents_to_update(self) -> None:
        update = self.update(["core.py"])
        update["deleted_modules"] = ["core"]
        update["retained_modules"] = [{"id": "docs", "evidence": "Unchanged"}]
        update["updated_modules"] = [module("api", ["api.py"], review_evidence="Removed core dependency", reviewed_dependencies=["core"])]
        result = merge_brief_update(self.existing, update, ["api.py", "docs.md"], ["core.py"])
        self.assertEqual(result["coverage"]["inventory_count"], 2)
        self.assertEqual(result["refresh_evidence"]["deleted_modules"], ["core"])
        del update["updated_modules"][0]["reviewed_dependencies"]
        with self.assertRaisesRegex(BriefError, "reviewed_dependencies"):
            merge_brief_update(self.existing, update, ["api.py", "docs.md"], ["core.py"])

    def test_retaining_a_module_with_a_deleted_file_fails(self) -> None:
        with self.assertRaisesRegex(BriefError, "unknown inventory"):
            merge_brief_update(self.existing, self.update(["docs.md"]), ["api.py", "core.py"], ["docs.md"])

    def test_new_module_requires_read_and_current_review_evidence(self) -> None:
        update = self.update(["new.py"])
        update["updated_modules"] = [module("new", ["new.py"], reread_files=["new.py"], review_evidence="Read new module")]
        result = merge_brief_update(self.existing, update, self.inventory + ["new.py"], ["new.py"])
        self.assertTrue(result["coverage"]["complete"])

    def test_inventory_changes_cannot_be_omitted_from_machine_change_list(self) -> None:
        update = self.update()
        update["updated_modules"] = [module("new", ["new.py"])]
        with self.assertRaisesRegex(BriefError, "every added or deleted"):
            merge_brief_update(self.existing, update, self.inventory + ["new.py"], [])

    def test_foreign_changed_paths_cannot_be_attested_as_reviewed(self) -> None:
        with self.assertRaisesRegex(BriefError, "outside both"):
            merge_brief_update(self.existing, self.update(["foreign.py"]), self.inventory, ["foreign.py"])

    def test_transitive_and_boundary_impact_are_detected(self) -> None:
        self.modules.append(module("web", ["web.py"], depends_on=["api"]))
        self.modules.append(module("config", ["config.py"], boundary_files=["core.py"], read_files=["config.py", "core.py"]))
        coverage = {"modules": self.modules}
        self.assertEqual(affected_modules(coverage, ["core.py"]), {"core", "api", "web", "config"})


class DurableRecordAndMigrationTests(unittest.TestCase):
    def test_records_allow_optional_id_and_preserve_superseded_history(self) -> None:
        records = [
            {"kind": "fact", "text": "A contextual fact"},
            {"id": "p1", "kind": "preference", "text": "Use concise logs", "source": "user"},
            {"id": "p2", "kind": "preference", "text": "Use detailed failure logs", "supersedes": ["p1"]},
        ]
        self.assertEqual(normalize_records(records), records)

    def test_record_references_cannot_be_unknown_or_cyclic(self) -> None:
        for records in [
            [{"id": "a", "kind": "fact", "text": "a", "supersedes": ["a"]}],
            [{"id": "a", "kind": "fact", "text": "a", "supersedes": ["missing"]}],
            [{"kind": "fact", "text": "a", "supersedes": []}],
        ]:
            with self.subTest(records=records), self.assertRaises(BriefError):
                normalize_records(records)

    def test_migration_retains_provenance_without_claiming_reread(self) -> None:
        ledger = [{"path": "src/a.py", "purpose": "Core", "exports": ["a"], "used_by": []}]
        result = migrate_legacy_ledger(ledger, ["src/a.py", "src/new.py", "README.md"], {
            "modules": [{"name": "Core", "responsibility": "Parse input", "files": ["src/a.py"]}],
        })
        self.assertFalse(result["complete"])
        self.assertEqual(result["unread_files"], ["README.md", "src/a.py", "src/new.py"])
        self.assertTrue(all(not item["read_files"] for item in result["modules"]))
        self.assertTrue(any(item["summary"] == "Parse input" for item in result["modules"]))
        self.assertEqual(ledger[0]["purpose"], "Core")

    def test_migration_drops_historical_empty_repository_sentinel(self) -> None:
        result = migrate_legacy_ledger([], ["(empty repository)"])
        self.assertEqual(result["inventory_count"], 0)
        self.assertEqual(result["modules"], [])


if __name__ == "__main__":
    unittest.main()
