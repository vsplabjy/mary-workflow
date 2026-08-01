from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_paper import apply_paper_action, paper_directory, prepare_read  # noqa: E402
from mw_paper_artifacts import (  # noqa: E402
    NORMALIZED_SOURCE_FILE,
    PARSE_QUALITY_FILE,
    READ_CONTEXT_FILE,
    artifact_path,
)
from mw_paper_readings import (  # noqa: E402
    PaperReadingError,
    READING_SUMMARY_FILE,
    READING_SUMMARY_MARKER,
    NOTION_ENGLISH_ORIGINAL_MARKER,
    NOTION_ENGLISH_ORIGINAL_TITLE,
    render_notion_english_original_page,
    render_notion_reading_page,
    validate_reading_summary,
)
from mw_paper_sources import sha256_file  # noqa: E402


def extracted_pdf_text() -> str:
    paragraph = (
        "The paper defines a method, explains its information flow, reports controlled experiments, "
        "and describes the associated limitations. "
    ) * 24
    return f"Abstract\n{paragraph}\nMethod\n{paragraph}\nExperiments\n{paragraph}"


def completed_summary() -> str:
    method = (
        "作者先将输入转化为统一的 feature representation，再由核心 module 根据当前状态选择处理路径。"
        "这种 information flow 让局部变化能够在输出阶段保持一致，同时避免直接在原始空间中反复优化。"
        "设计动机是把复杂的 material interaction 分解为可学习的中间表示和明确的输出约束。"
        "训练时，objective 同时约束重建质量与时间连续性；前者保证 visual fidelity，后者限制动态场景中的漂移。"
        "该设计的 trade-off 是需要额外的 state estimation，并且当输入观测稀疏时中间表示可能传播误差。"
    ) * 3
    return f"""{READING_SUMMARY_MARKER}

# Folder Fixture - 中文论文导读

## 一句话概括

论文提出一个面向动态任务的 method，通过统一表示和受约束的 information flow 在复杂输入下保持稳定输出。

## 背景与问题

已有方法往往直接处理原始观测，因此难以同时保持局部细节与跨时间一致性。本文关注的核心问题是如何在有限观测下构建可解释的中间表示，并让后续模块能够可靠地利用它。

## 方法

### 设计动机

{method}

### 信息流与关键步骤

{method}

### 关键模块、训练目标与权衡

{method}

## Related Work（简略）

Related Work 主要覆盖直接重建和单一表示方法；本文的区别是显式建模中间状态，而非只依赖最终输出监督。

## Experiments（简略）

Experiments 在受控数据上比较 baseline，并用重建质量和时间一致性说明该 method 的效果；具体数值仍应回看原文表格。

## 结论与开放问题

该方法说明结构化 information flow 可以提高稳定性。开放问题是稀疏观测与极端 material interaction 下的误差是否会累积。
"""


def write_notes(workspace: Path) -> None:
    context = json.loads(artifact_path(workspace, READ_CONTEXT_FILE).read_text(encoding="utf-8"))
    source = artifact_path(workspace, NORMALIZED_SOURCE_FILE).read_text(encoding="utf-8")
    locator = re.search(r"<!-- locator: ([^ ]+) -->", source)
    if locator is None:
        raise AssertionError("fixture source has no locator")
    claim = {"text": "The fixture source supports this claim.", "locators": [locator.group(1)]}
    ledger = {
        "paper_notes_schema": 1,
        "paper_id": context["paper_id"],
        "source": context["source"],
        "bibliography": {"title": "Folder Fixture", "authors": ["Mary"], "year": "2026", "venue": "Test"},
        "research": {
            "background": claim,
            "problem": claim,
            "contributions": [claim],
            "method": claim,
            "experiments": claim,
            "limitations": claim,
            "conclusions": claim,
        },
        "section_ledger": [{"section": "Method", "locators": [locator.group(1)], "findings": ["Fixture finding."]}],
        "parse_quality": context["parse_quality"],
        "uncertainties": [{
            "question": "Which source details need a visual check?",
            "why_unresolved": "PDF extraction can omit visual encodings.",
            "impact": "Figure-dependent interpretation needs the original PDF.",
            "locators": [locator.group(1)],
            "quality_dimensions": context["uncertainty_required_for"],
        }],
    }
    (workspace / "paper-notes.md").write_text(
        "<!-- mary-paper-notes:v1 -->\n```json\n" + json.dumps(ledger, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )


class PaperReadingTests(unittest.TestCase):
    def test_summary_requires_chinese_method_detail_and_renders_notion_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            draft = workspace / READING_SUMMARY_FILE
            draft.write_text(f"{READING_SUMMARY_MARKER}\n\n## 方法\n\n[待补充]\n", encoding="utf-8")
            with self.assertRaisesRegex(PaperReadingError, "draft placeholder"):
                validate_reading_summary(workspace)

            summary = completed_summary()
            draft.write_text(summary, encoding="utf-8")
            validation = validate_reading_summary(workspace)
            self.assertEqual(validation["artifact"], READING_SUMMARY_FILE)
            notion = render_notion_reading_page(
                "<!-- mary-reading:v1 -->\n\n# Folder Fixture\n\n## Method\n\nEnglish body.\n",
                summary,
            )
            self.assertNotIn("# Folder Fixture", notion)
            self.assertNotIn("<details", notion)
            self.assertNotIn("English body.", notion)
            self.assertIn("## 中文概括", notion)
            self.assertIn("信息流与关键步骤", notion)
            english_original = render_notion_english_original_page(
                "<!-- mary-reading:v1 -->\n\n# Folder Fixture\n\n## Method\n\nEnglish body.\n"
            )
            self.assertIn(NOTION_ENGLISH_ORIGINAL_MARKER, english_original)
            self.assertEqual(NOTION_ENGLISH_ORIGINAL_TITLE, "English original")
            self.assertIn("English body.", english_original)

    def test_folder_read_keeps_machine_files_in_artifacts_and_requires_guide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "bundle"
            source.mkdir()
            (source / "paper.pdf").write_bytes(b"%PDF-fixture")
            state, _ = prepare_read(project, source_locator=source, pdf_extractor=lambda _: extracted_pdf_text())
            workspace = paper_directory(project, state["paper_id"])
            self.assertTrue(artifact_path(workspace, NORMALIZED_SOURCE_FILE).is_file())
            self.assertTrue(artifact_path(workspace, PARSE_QUALITY_FILE).is_file())
            self.assertFalse((workspace / "source.md").exists())
            self.assertTrue((workspace / READING_SUMMARY_FILE).is_file())

            write_notes(workspace)
            payload = {
                "action": "complete_stage",
                "data": {
                    "stage": "read",
                    "artifact": "paper-notes.md",
                    "output_fingerprint": sha256_file(workspace / "paper-notes.md"),
                },
            }
            with self.assertRaises(SystemExit) as rejection:
                apply_paper_action(project, state["paper_id"], payload)
            self.assertIn("reading-summary.md still contains a draft placeholder", str(rejection.exception))

            (workspace / READING_SUMMARY_FILE).write_text(completed_summary(), encoding="utf-8")
            completed = apply_paper_action(project, state["paper_id"], payload)
            metadata = completed["stages"]["read"]["metadata"]
            self.assertEqual(metadata["reading_summary_artifact"], READING_SUMMARY_FILE)
            self.assertEqual(len(metadata["reading_summary_fingerprint"]), 64)


if __name__ == "__main__":
    unittest.main()
