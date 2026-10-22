from __future__ import annotations

import hashlib
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from mw_report import generate  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "mw_report.py"
IGNORES = "/.mary-workflow/\n/.mary-workflow-worker/\n/.mary-research/\n/.vspi/\n"


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.labels = []

    def handle_data(self, value):
        if value.strip() in {"通过", "失败", "运行中", "未运行"}:
            self.labels.append(value.strip())


class ReportBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.root = self.project / ".mary-workflow"
        self.root.mkdir()
        # Pre-install the exact root ignores so the renderer's ignore step is a no-op
        # and state-immutability snapshots stay meaningful.
        (self.project / ".gitignore").write_text(IGNORES, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    # -- helpers -----------------------------------------------------------

    def write_receipt(self, command: str = "pytest -q tests/", exit_code: int | None = 0,
                      status: str | None = "passed", name: str = "check-1",
                      stdout: str = "3 passed\n", stderr: str = "",
                      digest: bool = True) -> tuple[str, dict]:
        directory = self.root / "evidence"
        directory.mkdir(parents=True, exist_ok=True)
        record = {"schema_version": 1, "evidence_id": name, "name": name,
                  "command": command, "cwd": str(self.project),
                  "exit_code": exit_code, "created_at": "2026-10-22T00:00:00+00:00",
                  "result": status, "summary": f"exit {exit_code}", "duration_ms": 1200}
        for stream, text in (("stdout", stdout), ("stderr", stderr)):
            log = directory / f"{name}.{stream}.log"
            if not log.exists():
                log.write_text(text, encoding="utf-8")
            record[stream] = log.name
            if digest:
                record[stream + "_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
        path = directory / (name + ".json")
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return path.relative_to(self.project).as_posix(), record

    def verification(self, checks: list[dict], logs: dict[str, str] | None = None) -> str:
        """Write a verification.json whose logs sit beside it; return relative path."""
        directory = self.root / "checks"
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"checks": checks}
        for check in checks:
            for stream in ("stdout", "stderr"):
                name = check.get(stream)
                if name:
                    content = (logs or {}).get(name, name + " content\n")
                    (directory / name).write_text(content, encoding="utf-8")
        path = directory / "verification.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path.relative_to(self.project).as_posix()

    def snapshot(self) -> dict[str, bytes]:
        state = {}
        for path in sorted(self.project.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.project).as_posix()
            if relative.startswith(".mary-workflow/reports"):
                continue
            state[relative] = path.read_bytes()
        return state

    def render(self, payload: dict, name: str | None = None) -> dict:
        return generate(self.project, payload, name)

    def states(self, page: str) -> list[str]:
        parser = VisibleText()
        parser.feed(page)
        return parser.labels

    def cli(self, payload_path: Path, name: str | None = None) -> subprocess.CompletedProcess:
        command = [sys.executable, str(SCRIPT), "--project", str(self.project),
                   "--input", str(payload_path)]
        if name is not None:
            command += ["--name", name]
        return subprocess.run(command, capture_output=True, text=True, cwd=str(REPO_ROOT))

    # -- status forgery / contradictions ------------------------------------

    def test_non_integer_exit_code_cannot_support_a_pass(self):
        for index, exit_code in enumerate((None, False, "0")):
            with self.subTest(exit_code=exit_code):
                path = self.verification([{
                    "name": "unproven", "argv": ["pytest", "-q"], "exit_code": exit_code,
                    "status": "passed", "stdout": f"out-{index}.log", "stderr": f"err-{index}.log"
                }])
                result = self.render({"title": "未证实的通过", "summary": "日志存在仍不能补造整数退出码",
                                      "verification": path})
                page = Path(result["report"]).read_text(encoding="utf-8")
                self.assertEqual(self.states(page), ["未运行"])

    def test_contradictory_failure_status_with_exit_zero_stays_bad(self):
        for states in ({"status": "failed"}, {"status": "失败"},
                       {"status": "passed", "result": "failed"},
                       {"status": "通过", "result": "timeout"}):
            with self.subTest(states=states):
                path = self.verification([{
                    "name": "check-1", "argv": ["pytest", "-q"], "exit_code": 0,
                    "stdout": "out.log", "stderr": "err.log", **states
                }], logs={"out.log": "ok\n", "err.log": ""})
                result = self.render({"title": "矛盾回执", "summary": "失败记录不得升级",
                                      "verification": path})
                page = Path(result["report"]).read_text(encoding="utf-8")
                self.assertIn("失败", self.states(page))
                self.assertNotIn("通过", self.states(page))

    def test_interrupted_receipt_with_unknown_exit_keeps_partial_logs(self):
        stdout = "RECOVERY_PARTIAL_STDOUT\n"
        stderr = "RECOVERY_PARTIAL_STDERR\n"
        path, _ = self.write_receipt(exit_code=None, status="interrupted",
                                     stdout=stdout, stderr=stderr)
        before = self.snapshot()
        result = self.render({"title": "中断回执", "summary": "未知退出码不能抹掉已中断记录",
                              "verification": path})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertEqual(self.states(page), ["失败"])
        self.assertIn(stdout.strip(), page)
        self.assertIn(stderr.strip(), page)
        self.assertEqual(self.snapshot(), before)

    def test_interruption_outweighs_passed_status_without_exit_code(self):
        path = self.verification([{
            "name": "recovery", "argv": ["pytest", "-q"], "exit_code": None,
            "status": "passed", "result": "interrupted",
            "stdout": "out.log", "stderr": "err.log"
        }], logs={"out.log": "PARTIAL_RECOVERY_OUTPUT\n", "err.log": ""})
        result = self.render({"title": "矛盾中断回执", "summary": "中断记录不能被通过标签覆盖",
                              "verification": path})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertEqual(self.states(page), ["失败"])
        self.assertIn("PARTIAL_RECOVERY_OUTPUT", page)

    def test_interruption_preserves_valid_log_when_other_log_is_unavailable(self):
        for problem in ("missing", "digest-mismatch"):
            with self.subTest(problem=problem):
                stdout = f"INTACT_RECOVERY_OUTPUT_{problem}\n"
                path, record = self.write_receipt(
                    name="recovery-" + problem, exit_code=None, status="interrupted",
                    stdout=stdout, stderr="RECOVERY_STDERR_ORIGINAL\n")
                stderr = (self.project / path).parent / record["stderr"]
                if problem == "missing":
                    stderr.unlink()
                else:
                    stderr.write_text("RECOVERY_STDERR_TAMPERED\n", encoding="utf-8")
                before = self.snapshot()
                result = self.render({"title": "部分中断日志", "summary": "坏日志不能隐藏其他可用证据",
                                      "verification": path})
                page = Path(result["report"]).read_text(encoding="utf-8")
                self.assertEqual(self.states(page), ["失败"])
                self.assertIn(stdout.strip(), page)
                self.assertNotIn("RECOVERY_STDERR_ORIGINAL", page)
                self.assertNotIn("RECOVERY_STDERR_TAMPERED", page)
                self.assertEqual(self.snapshot(), before)

    def test_task_validation_id_resolves_only_from_task_directory(self):
        self.write_receipt(command="pytest -q tests/", name="check-abc123")  # foreign copy
        task_dir = self.root / "tasks" / "implementation"
        task_dir.mkdir(parents=True)
        forged = {"schema_version": 1, "evidence_id": "check-abc123", "name": "check-abc123",
                  "command": "echo forged", "exit_code": 0, "result": "passed",
                  "created_at": "2026-10-22T00:00:00+00:00", "summary": "exit 0"}
        for stream, text in (("stdout", "forged\n"), ("stderr", "")):
            (task_dir / f"check-abc123.{stream}.log").write_text(text, encoding="utf-8")
            forged[stream] = f"check-abc123.{stream}.log"
            forged[stream + "_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        (task_dir / "check-abc123.json").write_text(json.dumps(forged, ensure_ascii=False),
                                                    encoding="utf-8")
        result = self.render({"title": "任务回执定位", "summary": "回执只从任务目录解析",
                              "tasks": [{"task_id": "implementation", "status": "ready_for_review",
                                         "summary": "完成", "validation": ["check-abc123"]}]})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertIn("echo forged", page)
        self.assertNotIn("pytest -q tests/", page)

    # -- bad receipts and log digests --------------------------------------

    def test_bad_log_digest_is_flagged_not_passed(self):
        path = self.verification([{"name": "check-1", "argv": ["pytest", "-q"], "exit_code": 0,
                                   "status": "passed", "stdout": "out.log", "stderr": "err.log",
                                   "stdout_sha256": "0" * 64}],
                                 logs={"out.log": "ok\n", "err.log": ""})
        result = self.render({"title": "摘要不符", "summary": "日志摘要不符按失败标注",
                              "verification": path})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertIn("失败", self.states(page))
        self.assertNotIn("通过", self.states(page))

    def test_missing_verification_renders_unrun_honestly(self):
        result = self.render({"title": "无回执", "summary": "未提供回执时不得宣称命令未执行过"})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertIn("未运行", page)
        self.assertNotIn("通过", self.states(page))

    def test_unreadable_verification_reference_is_unrun(self):
        result = self.render({"title": "坏引用", "summary": "回执文件缺失按未运行显示",
                              "verification": ".mary-workflow/missing/verification.json"})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertIn("未运行", page)
        self.assertTrue(any(".mary-workflow/missing/verification.json" in warning
                            for warning in result["warnings"]))

    def test_unreadable_task_result_path_is_visible(self):
        result = self.render({"title": "坏任务路径", "summary": "result.json 缺失要有诚实任务卡",
                              "tasks": [".mary-workflow/tasks/ghost/result.json"]})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertIn("ghost/result.json", page)
        self.assertTrue(any(".mary-workflow/tasks/ghost/result.json" in warning
                            for warning in result["warnings"]))

    # -- escaping and HTML injection ---------------------------------------

    def test_hostile_text_is_escaped(self):
        payload = {"title": "<script>alert('title')</script>",
                   "summary": "<img src=x onerror=alert(1)> 注入尝试",
                   "next_steps": ["</ul><script>evil()</script>"],
                   "metrics": [{"name": "<b>PSNR</b>", "value": 31.2, "unit": "dB"}]}
        result = self.render(payload)
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;script&gt;", page)

    def test_log_excerpt_is_escaped(self):
        poison = "<script>alert('log')</script>\n"
        directory = self.root / "checks"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "out.log").write_text(poison, encoding="utf-8")
        (directory / "err.log").write_text("", encoding="utf-8")
        path = self.verification([
            {"name": "check-1", "argv": ["run"], "exit_code": 0, "status": "passed",
             "stdout": "out.log", "stderr": "err.log",
             "stdout_sha256": hashlib.sha256(poison.encode()).hexdigest()}],
            logs={"out.log": poison, "err.log": ""})
        result = self.render({"title": "日志转义", "summary": "日志内容不得作为 HTML 执行",
                              "verification": path})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    # -- path traversal and symlink escapes ---------------------------------

    def test_absolute_and_traversal_artifacts_are_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        victim = outside / "mw-report-victim.txt"
        victim.write_text("secret\n", encoding="utf-8")
        try:
            result = self.render({"title": "越界证据", "summary": "绝对路径与越界路径不收录",
                                  "artifacts": ["/etc/passwd", "../mw-report-victim.txt",
                                                "missing/preview.png"]})
            page = Path(result["report"]).read_text(encoding="utf-8")
            self.assertIn("未收录", page)
            self.assertIn("缺失", page)
            assets = Path(result["report"]).parent / "assets"
            self.assertTrue(not assets.exists() or not any(assets.iterdir()))
        finally:
            victim.unlink(missing_ok=True)

    def test_symlink_escape_is_not_copied(self):
        if os.name != "posix":
            self.skipTest("POSIX symlinks required")
        outside = self.base / "mw-report-outside"
        outside.mkdir(exist_ok=True)
        secret = outside / "secret.txt"
        secret.write_text("secret\n", encoding="utf-8")
        link = self.project / "proof.png"
        link.symlink_to(secret)
        try:
            result = self.render({"title": "符号链接", "summary": "符号链接越界不复制",
                                  "artifacts": ["proof.png"]})
            page = Path(result["report"]).read_text(encoding="utf-8")
            self.assertIn("越出项目范围", page)
            assets = Path(result["report"]).parent / "assets"
            self.assertTrue(not assets.exists() or not any(assets.iterdir()))
        finally:
            link.unlink(missing_ok=True)
            secret.unlink()
            outside.rmdir()

    def test_report_control_symlinks_cannot_redirect_or_replace_outputs(self):
        if os.name != "posix":
            self.skipTest("POSIX symlinks required")
        for component in (".mary-workflow", "reports", "index.html", ".write.lock"):
            with self.subTest(component=component):
                project = self.base / ("control-" + component.replace(".", "-"))
                project.mkdir()
                outside = self.base / ("outside-" + component.replace(".", "-"))
                outside.mkdir()
                marker = outside / "keep.txt"
                marker.write_bytes(b"do not change")
                root = project / ".mary-workflow"
                if component == ".mary-workflow":
                    root.symlink_to(outside, target_is_directory=True)
                else:
                    reports = root / "reports"
                    if component == "reports":
                        root.mkdir()
                        reports.symlink_to(outside, target_is_directory=True)
                    else:
                        reports.mkdir(parents=True)
                        (reports / component).symlink_to(marker)
                with self.assertRaises(ValueError):
                    generate(project, {"title": "控制路径", "summary": "不能重定向写入"})
                self.assertEqual(marker.read_bytes(), b"do not change")
                self.assertEqual({p.name for p in outside.iterdir()}, {"keep.txt"})

    # -- index preservation and duplicate generation ------------------------

    def test_legacy_index_entries_are_preserved_and_new_report_prepends(self):
        reports = self.root / "reports"
        reports.mkdir(parents=True)
        (reports / "index.html").write_text(
            "<html><body><article>OLD</article></body></html>", encoding="utf-8")
        old_bundle = reports / "20260101T000000Z-old"
        (old_bundle / "assets").mkdir(parents=True)
        old_page = "<html>old report</html>"
        (old_bundle / "index.html").write_text(old_page, encoding="utf-8")
        first = self.render({"title": "第一份", "summary": "先结论"}, name="first")
        second = self.render({"title": "第二份", "summary": "再来一份"}, name="first")
        index = (reports / "index.html").read_text(encoding="utf-8")
        self.assertIn("OLD", index)
        self.assertIn("第二份", index)
        self.assertIn("第一份", index)
        self.assertLess(index.index("第二份"), index.index("第一份"))
        self.assertLess(index.index("第一份"), index.index("OLD"))
        self.assertNotEqual(Path(first["report"]), Path(second["report"]))
        self.assertEqual((old_bundle / "index.html").read_text(encoding="utf-8"), old_page)

    # -- assets honesty -----------------------------------------------------

    def test_evidence_bounds_and_honest_display(self):
        (self.project / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (self.project / "big.bin").write_bytes(b"\0" * ((1 << 20) + 1))
        result = self.render({"title": "证据边界", "summary": "超限证据只标注不复制",
                              "artifacts": ["data.csv", "big.bin"]})
        package = Path(result["report"]).parent
        self.assertTrue((package / "assets").is_dir())
        page = (package / "index.html").read_text(encoding="utf-8")
        self.assertIn("data.csv", page)
        self.assertTrue(any("big.bin" in warning for warning in result["warnings"]))
        self.assertFalse(any(path.name.endswith("big.bin")
                             for path in (package / "assets").iterdir()))

    # -- state immutability through the real CLI -----------------------------

    def test_cli_emits_fixed_json_and_changes_no_state(self):
        (self.root / "state.yaml").write_text("status: running\n", encoding="utf-8")
        (self.root / "knowledge").mkdir()
        (self.root / "knowledge" / "index.json").write_text("{}", encoding="utf-8")
        tasks = self.root / "tasks" / "implementation"
        tasks.mkdir(parents=True)
        (tasks / "task.json").write_text('{"task_id": "implementation", "status": "running"}',
                                         encoding="utf-8")
        payload = {"title": "CLI 冒烟", "summary": "固定 report/index 键",
                   "tasks": [{"task_id": "implementation", "status": "ready_for_review",
                              "summary": "完成", "files_changed": ["scripts/mw_report.py"],
                              "validation": []}],
                   "verification": self.verification(
                       [{"name": "check-1", "argv": ["python", "-m", "py_compile",
                                                     "scripts/mw_report.py"],
                         "exit_code": 0, "status": "passed",
                         "stdout": "out.log", "stderr": "err.log"}],
                       logs={"out.log": "compiled\n", "err.log": ""})}
        payload_file = self.project / "input.json"
        payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        before = self.snapshot()
        process = self.cli(payload_file, name="cli-smoke")
        self.assertEqual(process.returncode, 0, process.stderr)
        output = json.loads(process.stdout)
        self.assertIn("report", output)
        self.assertIn("index", output)
        report = Path(output["report"])
        self.assertTrue(report.is_file())
        self.assertTrue(str(report).startswith(str(self.project)))
        self.assertEqual(self.snapshot(), before)  # no state/knowledge/task mutation
        entries = {p.name for p in (self.root / "reports").glob("*")}
        self.assertIn(report.parent.name, entries)
        self.assertIn("index.html", entries)
        self.assertLessEqual(entries, {report.parent.name, "index.html", ".write.lock"})

    def test_invalid_presentation_input_exits_with_message(self):
        missing = self.project / "nope.json"
        process = self.cli(missing)
        self.assertEqual(process.returncode, 2)
        self.assertIn("mw-report", process.stderr)

        bad = self.project / "bad.json"
        bad.write_text(json.dumps({"title": "t", "summary": "s"}), encoding="utf-8")
        process = self.cli(bad, name="../escape")
        self.assertEqual(process.returncode, 2)
        self.assertFalse((self.root / "reports").exists())

    def test_summary_appears_once_for_simple_card(self):
        result = self.render({"title": "单卡", "summary": "唯一的结论文字XYZ"})
        page = Path(result["report"]).read_text(encoding="utf-8")
        self.assertEqual(page.count("唯一的结论文字XYZ"), 1)


if __name__ == "__main__":
    unittest.main()
