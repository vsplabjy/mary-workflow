from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class NotionCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = (REPO_ROOT / "commands/notion.md").read_text(encoding="utf-8")
        self.skill = (REPO_ROOT / "skills/notion/SKILL.md").read_text(encoding="utf-8")
        self.root_skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.references = REPO_ROOT / "skills/notion/references"

    def test_command_is_wired_without_mary_state_dependency(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )

        self.assertIn("# /notion", self.command)
        self.assertIn("$ARGUMENTS", self.command)
        self.assertIn("Do not require `.mary-workflow/`", self.command)
        self.assertIn("skills/notion/SKILL.md", self.command)
        self.assertIn("`/notion`", self.root_skill)
        self.assertIn("skills/notion/SKILL.md", self.root_skill)
        self.assertIn("`/notion [请求]`", self.readme)
        self.assertTrue(
            any(prompt.startswith("/notion ") for prompt in manifest["interface"]["defaultPrompt"])
        )
        self.assertIn("notion", manifest["keywords"])

    def test_skill_enforces_notions_read_write_safety_boundary(self) -> None:
        normalized_skill = " ".join(self.skill.split())
        required = (
            "Inspect the Notion MCP tools",
            "Read before writing",
            "Execute writes to the same page sequentially",
            "Fetch the affected page",
            "Do not replace `<page>` with `<mention-page>`",
            "database or data-source tools",
            "Do not fabricate URLs",
            "no authorized Notion MCP tool is available",
        )
        for marker in required:
            self.assertIn(marker, normalized_skill)

    def test_exported_reference_contract_is_complete(self) -> None:
        expected = {
            "mcp-playbook.md",
            "notion-markdown.md",
            "page-craft.md",
            "personal-rules.md",
            "task-profiles.md",
        }
        self.assertEqual({path.name for path in self.references.glob("*.md")}, expected)

        combined = "\n".join(
            (self.references / name).read_text(encoding="utf-8") for name in sorted(expected)
        )
        for marker in (
            "Delivery Checklist",
            "semantic icon on every new page",
            "three to six callouts",
            "at most five columns",
            "Deduplicate",
            "Asia/Shanghai",
            "Math Rendering",
            "Paper Translation",
            "Slides to Lecture Notes",
            "visually read every result",
        ):
            self.assertIn(marker, combined)

    def test_skill_has_no_scaffold_placeholders(self) -> None:
        files = [
            REPO_ROOT / "skills/notion/SKILL.md",
            REPO_ROOT / "skills/notion/agents/openai.yaml",
            REPO_ROOT / "commands/notion.md",
            *sorted(self.references.glob("*.md")),
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotIn("TODO", combined)
        self.assertNotIn("[TODO:", combined)


if __name__ == "__main__":
    unittest.main()
