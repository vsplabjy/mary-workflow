#!/usr/bin/env python3
"""Offline human-readable HTML projection of existing Mary workflow records.

``mw_report`` renders an authored presentation JSON plus already recorded
worker results and validation receipts into a static ``file://`` report
package under ``.mary-workflow/reports/``.  It is a readable projection for
humans only: it executes no commands, mutates no task, knowledge or stop
state, and its check states are historical command records rather than fresh
engineering, visual or scientific acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
from datetime import datetime, timezone

from mw_runtime import atomic_write_text, ensure_workflow_gitignore, workflow_lock

MAX_FILE_BYTES = 1 << 20
MAX_TOTAL_BYTES = 4 << 20
EXCERPT_BYTES = 2000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_BAD_STATES = {
    "failed": "失败", "timeout": "超时", "cancelled": "取消", "interrupted": "中断",
    "失败": "失败", "超时": "超时", "取消": "取消", "中断": "中断",
}
_BADGES = {"通过": "pass", "失败": "fail", "运行中": "info", "未运行": "warn"}
_TASK_STATUS = {"ready_for_review": "已提交待复核", "blocked": "受阻", "failed": "失败",
                "running": "进行中", "cancelled": "已取消"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_ACTIVE_SUFFIXES = {".svg", ".html", ".htm", ".xhtml", ".xml"}

_PAGE_STYLE = (
    ":root{color-scheme:light dark}body{font:16px/1.7 system-ui,sans-serif;max-width:960px;"
    "margin:28px auto;padding:0 20px;overflow-wrap:anywhere}h1{font-size:clamp(24px,3vw,34px);line-height:1.35}"
    "h2{font-size:22px;margin-top:1.8em}h3{font-size:18px;margin:.4em 0}.meta,.note{opacity:.75}"
    ".note{font-size:14px}code{overflow-wrap:anywhere}.badge{display:inline-block;"
    "border:1px solid currentColor;border-radius:999px;padding:0 10px;font-size:14px}"
    ".badge.pass{color:light-dark(#176a2f,#75d897)}.badge.fail{color:light-dark(#b9232f,#ff9ba3)}"
    ".badge.warn{color:light-dark(#805600,#eac365)}a{color:light-dark(#234eb2,#9bbdff)}"
    ".badge.info{opacity:.85}.card,.check{border:1px solid #888;border-radius:10px;"
    "padding:12px 18px;margin:14px 0}pre.log{white-space:pre-wrap;overflow-wrap:anywhere;"
    "background:rgba(127,127,127,.15);padding:10px;border-radius:8px;font-size:13px}"
    "table{border-collapse:collapse;margin:10px 0;width:100%;table-layout:fixed}"
    "th,td{border:1px solid #888;padding:5px 10px;text-align:left;overflow-wrap:anywhere}"
    "img{max-width:100%;height:auto}ul{padding-left:1.2em}figure{margin:8px 0}"
    "figcaption{font-size:14px;opacity:.75}header{border-bottom:1px solid #888;padding-bottom:12px}")

_INDEX_STYLE = ("body{font:17px/1.65 system-ui,sans-serif;max-width:900px;margin:48px auto;padding:0 24px;overflow-wrap:anywhere}"
                "article{border:1px solid #8490a0;border-radius:12px;padding:24px;margin:24px 0}"
                "a{color:light-dark(#234eb2,#9bbdff)}small{opacity:.75}code{overflow-wrap:anywhere}"
                ":root{color-scheme:light dark}")

_INDEX_TEMPLATE = (
    "<!doctype html>\n<html lang=\"zh-CN\">\n<head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>Mary Workflow · 汇报目录</title><style>" + _INDEX_STYLE + "</style></head>\n<body>\n"
    "<h1>项目汇报</h1><p>静态 HTML · 最新优先 · 本地离线查看</p>\n"
    "<!-- mw-report entries: newest first -->\n{entry}\n"
    "<p><small>路径：<code>.mary-workflow/reports/index.html</code>。"
    "报告不替代正式验收或科学评测。</small></p>\n</body></html>\n")


class ReportError(ValueError):
    """Invalid presentation input or unsafe path."""


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _text(value, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportError(f"{field} 必须是非空字符串")
    text = value.strip()
    if len(text) > limit:
        raise ReportError(f"{field} 超过 {limit} 字符上限")
    return text


def _optional_strings(payload: dict, field: str, limit: int) -> list[str]:
    values = payload.get(field)
    if values is None:
        return []
    if not isinstance(values, list):
        raise ReportError(f"{field} 必须是字符串列表")
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ReportError(f"{field} 每项必须是非空字符串")
        text = value.strip()
        if len(text) > limit:
            raise ReportError(f"{field} 每项超过 {limit} 字符上限")
        result.append(text)
    return result


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return False
    return True


def _relative_name(value: object) -> str | None:
    """Return a safe project/record-relative POSIX path, or None if unsafe."""
    name = str(value or "")
    parts = PurePosixPath(name).parts
    if (not parts or name.startswith("/") or "\\" in name or "\x00" in name
            or ".." in parts):
        return None
    return PurePosixPath(name).as_posix()


def _record_path(project: Path, value: object, field: str) -> Path:
    """Validate an existing project-relative control record (no symlinks)."""
    name = _relative_name(value)
    if name is None:
        raise ReportError(f"{field} 必须是项目内相对路径（不得越界）：{value!r}")
    path = project.joinpath(*PurePosixPath(name).parts)
    cursor = project
    for part in PurePosixPath(name).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ReportError(f"{field} 路径含符号链接，拒绝读取：{name!r}")
    if not path.is_file() or not _inside(path, project):
        raise ReportError(f"{field} 必须是项目内已存在的普通文件：{name!r}")
    return path


def _artifact_target(project: Path, value: str) -> tuple[Path | None, str]:
    """Soft-validate an artifact path; unsafe targets are flagged, not fatal."""
    name = _relative_name(value)
    if name is None:
        return None, "路径不安全（绝对路径、反斜杠或含越界成分）"
    path = project.joinpath(*PurePosixPath(name).parts)
    if not _inside(path, project):
        return None, "符号链接越出项目范围"
    return path, ""


def _log_path(directory: Path, value: object) -> Path | None:
    name = _relative_name(value)
    if name is None:
        return None
    path = directory.joinpath(*PurePosixPath(name).parts)
    cursor = directory
    for part in PurePosixPath(name).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return None
    if not path.is_file() or not _inside(path, directory):
        return None
    return path


def _identifier(value: object) -> str | None:
    text = str(value or "")
    if _ID.fullmatch(text) and text not in {".", ".."}:
        return text
    return None


def _read_bytes(path: Path) -> bytes:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ReportError(f"文件超出单文件 {MAX_FILE_BYTES} 字节读取上限：{path.name}")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ReportError(f"读取时文件超出单文件 {MAX_FILE_BYTES} 字节上限：{path.name}")
    return data


def _file_digest(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


def _command_text(value) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list) and value and all(isinstance(t, str) and t.strip() for t in value):
        return shlex.join(value)
    return ""


def _excerpt(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - EXCERPT_BYTES))
            data = stream.read(EXCERPT_BYTES)
        if size > EXCERPT_BYTES:
            data = b"[...] " + data
    except OSError:
        return ""
    return data.decode("utf-8", "replace").strip("\n")


def _project_rel(project: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project).as_posix()
    except (ValueError, OSError):
        return path.name


def _warn(warnings: list[str], message: str) -> None:
    warnings.append(message)


def _view(name, command, state, reason, exit_code, logs, record=None) -> dict:
    record = record if isinstance(record, dict) else {}
    duration = record.get("duration_ms")
    created = record.get("created_at")
    return {"name": str(name), "command": command, "state": state, "reason": reason,
            "exit_code": exit_code, "logs": logs, "detail": str(record.get("summary") or ""),
            "duration_ms": duration if isinstance(duration, int) and not isinstance(duration, bool) else None,
            "created_at": str(created) if isinstance(created, str) else ""}


def _classify_check(record: dict, directory: Path, warnings: list[str]) -> dict:
    """Project a recorded command result without executing anything.

    A status string alone never yields 通过: a green state requires a nonempty
    command, a genuine integer exit code and present logs. Supplied log digests
    must match; contradictory failure states never become a pass.
    Explicit negative command records remain failed with an unknown exit code;
    readable, digest-matching partial logs remain available for inspection.
    """
    name = record.get("name") or record.get("acceptance_id") or record.get("evidence_id") or "未命名检查"
    candidate = record.get("argv")
    if candidate is None:
        candidate = record.get("command")
    command = _command_text(candidate)
    status_value = record.get("status")
    if status_value is None:
        status_value = record.get("result")
    status = str(status_value or "").strip().lower()
    exit_code = record.get("exit_code")
    bad = next((str(value).strip().lower() for value in
                (record.get("status"), record.get("result"))
                if str(value).strip().lower() in _BAD_STATES), None)

    def incomplete(reason: str) -> dict:
        if status:
            reason += f"（记录状态：{status}）"
        _warn(warnings, f"检查 {name}：{reason}")
        return _view(name, command, "未运行", reason, None, (None, None), record)

    if not command:
        return incomplete("回执缺少非空命令记录，不能凭状态字符串显示通过")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        if bad is None:
            return incomplete("回执缺少真实整数退出码，不能凭状态字符串显示通过")
        exit_code = None

    bad_reason = ""
    if bad is not None:
        bad_reason = f"回执记录为{_BAD_STATES[bad]}"
        if exit_code is None:
            bad_reason += "；退出码未知，未获得通过证据"
        elif exit_code == 0:
            bad_reason += "，与退出码 0 矛盾，不能升级为通过"

    logs: list[Path | None] = []
    problems: list[str] = []
    for stream in ("stdout", "stderr"):
        path = _log_path(directory, record.get(stream))
        digest = record.get(stream + "_sha256")
        try:
            if path is not None and path.stat().st_size > MAX_FILE_BYTES:
                problems.append(f"{stream} 日志超出读取上限，未核对")
                path = None
            elif path is not None and digest is not None and _file_digest(path) != str(digest).strip().lower():
                problems.append(f"{stream} 日志与回执摘要不符")
                path = None
            elif path is None:
                problems.append(f"{stream} 日志缺失或不可读")
        except (OSError, ReportError):
            problems.append(f"{stream} 日志无法安全读取")
            path = None
        logs.append(path)
    if problems:
        reason = "；".join(([bad_reason] if bad_reason else []) + problems)
        _warn(warnings, f"检查 {name}：{reason}")
        return _view(name, command, "失败", reason, exit_code, tuple(logs), record)
    if bad is not None:
        return _view(name, command, "失败", bad_reason, exit_code, tuple(logs), record)
    if exit_code == 0:
        return _view(name, command, "通过", "", exit_code, tuple(logs), record)
    reason = f"退出码 {exit_code}"
    if status == "passed":
        reason += "；回执状态声称通过，与退出码矛盾"
    return _view(name, command, "失败", reason, exit_code, tuple(logs), record)


def _load_verification(project: Path, value: object, warnings: list[str]) -> list[dict]:
    """Load a verification.json or receipt file; unreadable refs stay visible."""
    if not isinstance(value, str) or not value.strip():
        raise ReportError("verification 必须是项目内相对路径字符串")
    reason = ""
    payload: dict | None = None
    directory: Path | None = None
    try:
        path = _record_path(project, value, "verification")
        loaded = json.loads(_read_bytes(path).decode("utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("回执必须是 JSON 对象")
        payload, directory = loaded, path.parent
    except (ReportError, OSError, ValueError) as exc:
        reason = f"verification 回执无法读取：{exc}"
    if payload is None:
        _warn(warnings, reason)
        return [_view("verification", "", "未运行",
                      reason + "；本报告不据此显示任何通过", None, (None, None))]
    records = payload["checks"] if isinstance(payload.get("checks"), list) else [payload]
    views = []
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            _warn(warnings, f"verification.checks[{index}] 不是 JSON 对象")
            views.append(_view(f"checks[{index}]", "", "未运行", "回执项不是 JSON 对象", None, (None, None)))
            continue
        views.append(_classify_check(item, directory, warnings))
    return views


def _task_directory(project: Path, task_id: object) -> Path | None:
    identifier = _identifier(task_id)
    if identifier is None:
        return None
    cursor = project
    for part in (".mary-workflow", "tasks", identifier):
        cursor = cursor / part
        if cursor.is_symlink():
            return None
    return cursor if cursor.is_dir() else None


def _load_tasks(project: Path, values: object, warnings: list[str]) -> list[tuple[dict, Path | None]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ReportError("tasks 必须是列表（结果对象或 result.json 路径）")
    tasks: list[tuple[dict, Path | None]] = []
    for item in values:
        if isinstance(item, dict):
            tasks.append((item, _task_directory(project, item.get("task_id"))))
        elif isinstance(item, str):
            try:
                path = _record_path(project, item, "tasks 路径")
                result = json.loads(_read_bytes(path).decode("utf-8"))
                if not isinstance(result, dict):
                    raise ValueError("任务结果必须是 JSON 对象")
                tasks.append((result, path.parent))
            except (ReportError, OSError, ValueError) as exc:
                warnings.append(f"任务结果 {item} 无法读取：{exc}")
                tasks.append(({"task_id": item, "status": "unknown",
                               "summary": f"引用的 result.json 缺失、越界或无法解析（{exc}）；"
                                          "本报告不展示其任何回执。",
                               "blockers": ["result.json 引用无效"]}, None))
        else:
            raise ReportError("tasks 每项必须是结果对象或 result.json 路径")
    return tasks


def _receipt_file(directory: Path | None, evidence_id: str) -> Path | None:
    if directory is None or directory.is_symlink():
        return None
    path = directory / (evidence_id + ".json")
    if path.is_symlink() or not path.is_file():
        return None
    return path


def _task_check_view(value: object, directory: Path | None, project: Path,
                     warnings: list[str]) -> dict:
    evidence_id = _identifier(value)
    if evidence_id is None:
        reason = f"validation 项不是安全回执标识：{value!r}"
        _warn(warnings, reason)
        return _view(str(value), "", "未运行", reason, None, (None, None))
    if directory is None:
        reason = "缺少合法 task_id 或任务目录，无法定位回执"
        _warn(warnings, f"回执 {evidence_id}：{reason}")
        return _view(evidence_id, "", "未运行", reason, None, (None, None))
    path = _receipt_file(directory, evidence_id)
    if path is None or not _inside(path, project):
        reason = "回执不在其任务/结果目录中或不可读"
        _warn(warnings, f"回执 {evidence_id}：{reason}")
        return _view(evidence_id, "", "未运行", reason, None, (None, None))
    try:
        record = json.loads(_read_bytes(path).decode("utf-8"))
    except (OSError, ValueError) as exc:
        reason = f"回执 JSON 无法读取：{exc}"
        _warn(warnings, f"回执 {evidence_id}：{reason}")
        return _view(evidence_id, "", "未运行", "回执 JSON 无法读取", None, (None, None))
    if not isinstance(record, dict):
        _warn(warnings, f"回执 {evidence_id}：回执必须是 JSON 对象")
        return _view(evidence_id, "", "未运行", "回执必须是 JSON 对象", None, (None, None))
    return _classify_check(record, path.parent, warnings)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    temporary = path.parent / f".{path.name}.{os.urandom(8).hex()}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _asset_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "evidence"
    return safe[:80]


class _AssetStore:
    """Bounded copies of small evidence files into the new package."""

    def __init__(self, package: Path):
        self.directory = package / "assets"
        self.total = 0
        self._count = 0

    def copy(self, source: Path, display: str) -> tuple[str | None, str]:
        self._count += 1
        try:
            size = source.stat().st_size
            if size > MAX_FILE_BYTES:
                return None, f"超出单文件 {MAX_FILE_BYTES} 字节上限，仅保留原位置"
            if self.total + size > MAX_TOTAL_BYTES:
                return None, "超出报告证据总量上限，仅保留原位置"
            data = _read_bytes(source)
        except (OSError, ReportError):
            return None, "文件无法在读取上限内安全读取"
        if self.total + len(data) > MAX_TOTAL_BYTES:
            return None, "读取时超出报告证据总量上限，仅保留原位置"
        self.directory.mkdir(parents=True, exist_ok=True)
        label = f"{self._count:02d}-{_asset_name(Path(display).name)}"
        _atomic_write_bytes(self.directory / label, data)
        self.total += len(data)
        return "assets/" + label, ""


def _render_check(view: dict, store: _AssetStore, project: Path, *, kind: str) -> str:
    badge = _BADGES.get(view["state"], "warn")
    out = [f'<div class="check"><p><span class="badge {badge}">{_e(view["state"])}</span> '
           f'<strong>{_e(view["name"])}</strong> <small class="meta">历史{kind}</small></p>']
    if view["command"]:
        out.append(f"<p><code>{_e(view['command'])}</code></p>")
    meta = []
    if view["exit_code"] is not None:
        meta.append(f"退出码 {view['exit_code']}")
    if view["duration_ms"] is not None:
        meta.append(f"用时 {view['duration_ms']} ms")
    if view["created_at"]:
        meta.append(f"记录时间 {view['created_at']}")
    if meta:
        out.append('<p class="meta">' + " · ".join(_e(item) for item in meta) + "</p>")
    if view["detail"]:
        out.append(f'<p class="meta">回执摘要：{_e(view["detail"])}</p>')
    if view["reason"]:
        out.append(f"<p>说明：{_e(view['reason'])}</p>")
    if any(view["logs"]):
        items = []
        for stream, path in zip(("stdout", "stderr"), view["logs"]):
            if path is None:
                items.append(f"<li>{stream} 日志缺失或与回执不符</li>")
                continue
            excerpt = _excerpt(path)
            if excerpt:
                out.append(f'<pre class="log">{_e(stream)} 尾部摘录：\n{_e(excerpt)}</pre>')
            asset, reason = store.copy(path, path.name)
            if asset is None:
                items.append(f"<li>{_e(stream)} 日志未复制（{_e(reason)}）；原位置 "
                             f"<code>{_e(_project_rel(project, path))}</code></li>")
            else:
                items.append(f'<li><a href="{_e(asset)}" download>{_e(stream)} 日志</a></li>')
        out.append("<ul>" + "".join(items) + "</ul>")
    out.append("</div>")
    return "".join(out)


def _render_task_card(result: dict, views: list[dict], store: _AssetStore, project: Path) -> str:
    task_id = str(result.get("task_id") or result.get("agent_id") or "未命名任务")
    status = str(result.get("status") or "未记录状态")
    parts = [f'<article class="card"><h3>{_e(task_id)} '
             f'<span class="badge info">{_e(_TASK_STATUS.get(status, status))}</span></h3>']
    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(f'<p class="meta">worker 叙述：{_e(summary.strip())}</p>')
    for key, heading, code in (("files_changed", "变更文件", True),
                               ("blockers", "阻塞", False),
                               ("uncertainties", "不确定", False)):
        values = result.get(key)
        if not isinstance(values, list):
            continue
        items = "".join((f"<li><code>{_e(value)}</code></li>" if code else f"<li>{_e(value)}</li>")
                        for value in values if isinstance(value, str) and value.strip())
        if items:
            parts.append(f"<p>{heading}：</p><ul>{items}</ul>")
    submitted = result.get("submitted_at")
    if isinstance(submitted, str) and submitted:
        parts.append(f'<p class="meta">提交时间：{_e(submitted)}</p>')
    if views:
        parts.append("<p>验收回执（历史命令记录，非当前验收）：</p>")
        parts.extend(_render_check(view, store, project, kind="验收回执") for view in views)
    else:
        parts.append('<p class="meta">此任务卡未单独关联验收回执；如有全局命令记录，请见上方。'
                     '未关联回执不等于没有执行检查。</p>')
    parts.append("</article>")
    return "".join(parts)


def _render_artifacts(values: list[str], project: Path, store: _AssetStore,
                      warnings: list[str]) -> str:
    rows = []
    for value in values:
        path, reason = _artifact_target(project, value)
        if path is None:
            _warn(warnings, f"证据 {value}：{reason}")
            rows.append(f'<li><span class="badge warn">未收录</span> <code>{_e(value)}</code>：{_e(reason)}</li>')
            continue
        resolved = path.resolve()
        if not resolved.is_file():
            reason = "文件缺失或不是普通文件"
            _warn(warnings, f"证据 {value}：{reason}")
            rows.append(f'<li><span class="badge warn">缺失</span> <code>{_e(value)}</code>：{_e(reason)}</li>')
            continue
        asset, reason = store.copy(resolved, resolved.name)
        size = _e(f"{resolved.stat().st_size} B")
        if asset is None:
            _warn(warnings, f"证据 {value}：{reason}")
            rows.append(f'<li><span class="badge warn">未复制</span> <code>{_e(value)}</code>：{_e(reason)}；'
                        f"原位置 <code>{_e(_project_rel(project, resolved))}</code></li>")
            continue
        suffix = resolved.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            rows.append(f'<li><figure><img loading="lazy" src="{_e(asset)}" alt="{_e(value)}">'
                        f"<figcaption>{_e(value)}（{size}，选中样本）</figcaption></figure></li>")
        elif suffix in _ACTIVE_SUFFIXES:
            rows.append(f'<li><span class="badge warn">仅下载</span> <a href="{_e(asset)}" download>{_e(value)}</a>'
                        f"（不内嵌可执行内容，{size}）</li>")
        else:
            rows.append(f'<li><a href="{_e(asset)}" download>{_e(value)}</a>（{size}）</li>')
    return ('<section id="artifacts"><h2>证据快照</h2>'
            '<p class="note">仅复制小体积本地证据；缺失、越界或超限文件如实标注，绝不伪造截图或数据。</p>'
            "<ul>" + "".join(rows) + "</ul></section>")


def _metrics(values: object) -> list[tuple[str, object, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ReportError("metrics 必须是列表")
    rows = []
    for item in values:
        if not isinstance(item, dict):
            raise ReportError("metrics 每项必须是对象")
        name = _text(item.get("name"), "metrics.name", 200)
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ReportError(f"metrics 值必须是数字或字符串标量：{name}")
        unit = item.get("unit", "")
        if unit is None:
            unit = ""
        if not isinstance(unit, str):
            raise ReportError(f"metrics.unit 必须是字符串：{name}")
        rows.append((name, value, unit))
    return rows


def _metrics_section(metrics: list[tuple[str, object, str]]) -> str:
    if not metrics:
        return ""
    rows = "".join(f"<tr><td>{_e(name)}</td><td>{_e(value)}</td><td>{_e(unit)}</td></tr>"
                   for name, value, unit in metrics)
    return ('<section id="metrics"><h2>指标</h2><table><tr><th>指标</th><th>值</th><th>单位</th></tr>'
            + rows + "</table></section>")


def _counts(views: list[dict]) -> tuple[int, int, int, int]:
    passed = sum(1 for view in views if view["state"] == "通过")
    bad = sum(1 for view in views if view["state"] == "失败")
    unrun = sum(1 for view in views if view["state"] == "未运行")
    return len(views), passed, bad, unrun


def _display_time(timestamp: str) -> str:
    return (f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} "
            f"{timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]} UTC")


def _slug(name: str | None, title: str) -> str:
    slug = (name or "").strip().lower()
    if name is not None and not _SLUG.fullmatch(slug):
        raise ReportError("--name 必须是小写字母、数字与连字符的安全 slug")
    if not slug:
        slug = "-".join(word.lower() for word in re.findall(r"[A-Za-z0-9]+", title)[:6])[:64].strip("-")
    return slug or "report"


def _package_name(reports: Path, timestamp: str, slug: str) -> str:
    base = f"{timestamp}-{slug}"
    candidate, suffix = base, 1
    while (reports / candidate).exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _index_entry(package: str, slug: str, title: str, timestamp: str, summary: str,
                 counts: tuple[int, int, int, int]) -> str:
    total, passed, bad, unrun = counts
    if total:
        state = f"命令回执 {total} 项：通过 {passed} · 异常 {bad} · 未运行 {unrun}"
    else:
        state = "未附命令回执（未运行）"
    lead = summary if len(summary) <= 160 else summary[:159].rstrip() + "…"
    return (f'<article style="overflow-wrap:anywhere"><small>{_display_time(timestamp)} · {_e(slug)}</small>'
            f'<h2><a href="{_e(package)}/index.html">{_e(title)}</a></h2>'
            f"<p>状态：{_e(state)}</p><p>{_e(lead)}</p></article>")


def _update_index(reports: Path, entry_html: str) -> None:
    """Prepend one entry; never rebuild from old packages or drop old entries."""
    index = reports / "index.html"
    payload = entry_html.encode("utf-8") + b"\n"
    if index.is_file() and not index.is_symlink():
        original = index.read_bytes()
        marker = original.find(b"<article")
        if marker != -1:
            updated = original[:marker] + payload + original[marker:]
        else:
            close = original.find(b"</body>")
            updated = (original[:close] + payload + original[close:]
                       if close != -1 else original + payload)
        atomic_write_text(index, updated.decode("utf-8", "replace"))
        return
    atomic_write_text(index, _INDEX_TEMPLATE.replace("{entry}", entry_html))


def _render_page(*, title: str, summary: str, timestamp: str, package: str,
                 metrics: list[tuple[str, object, str]], checks_section: str,
                 task_blocks: list[str], artifact_section: str, next_steps: list[str]) -> str:
    parts = ["<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
             "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
             f"<title>{_e(title)}</title><style>{_PAGE_STYLE}</style></head><body>",
             "<header><h1>", _e(title), "</h1>",
             f'<p class="lead">{_e(summary)}</p>',
             f'<p class="meta">生成时间：{_e(_display_time(timestamp))}</p></header>',
             '<nav><a href="../index.html">← 汇报目录</a></nav>']
    parts.append(_metrics_section(metrics))
    parts.append(checks_section)
    if task_blocks:
        parts.append('<section id="tasks"><h2>任务</h2><p class="note">任务卡文字为 worker 自报'
                     "叙述；回执区是机械记录的命令结果。叙述与记录状态分开呈现。</p>"
                     + "".join(task_blocks) + "</section>")
    if artifact_section:
        parts.append(artifact_section)
    if next_steps:
        parts.append("<section id=\"next\"><h2>后续</h2><ul>"
                     + "".join(f"<li>{_e(step)}</li>" for step in next_steps) + "</ul></section>")
    parts.append("<footer><p class=\"note\">本页是静态人类可读投影：命令行为历史回执记录，"
                 "不代表当前工程、视觉或科学验收；生成过程不执行任何命令，"
                 "也不改变任务、知识或停止状态。</p>"
                 f"<p class=\"note\">报告包：<code>{_e(package)}/index.html</code></p></footer></body></html>\n")
    return "".join(parts)


def generate(project: Path, payload: dict, name: str | None = None) -> dict:
    """Render one immutable report package; return exact paths and warnings."""
    project = Path(project).resolve()
    if not isinstance(payload, dict):
        raise ReportError("输入必须是 JSON 对象")
    warnings: list[str] = []
    title = _text(payload.get("title"), "title", 300)
    summary = _text(payload.get("summary"), "summary", 6000)
    tasks = _load_tasks(project, payload.get("tasks"), warnings)
    metrics = _metrics(payload.get("metrics"))
    artifact_values = _optional_strings(payload, "artifacts", 4096)
    next_steps = _optional_strings(payload, "next_steps", 500)

    verification_views: list[dict] | None = None
    if payload.get("verification") is not None:
        verification_views = _load_verification(project, payload["verification"], warnings)

    slug = _slug(name, title)
    reports = project / ".mary-workflow" / "reports"
    for directory in (project / ".mary-workflow", reports):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ReportError(f"报告控制目录必须是项目内普通目录：{directory.name}")
    for target in (reports / ".write.lock", reports / "index.html"):
        if target.is_symlink():
            raise ReportError(f"拒绝写入符号链接报告控制文件：{target.name}")
    ensure_workflow_gitignore(project)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with workflow_lock(reports):
        package = reports / _package_name(reports, timestamp, slug)
        package.mkdir(parents=True)
        store = _AssetStore(package)

        task_blocks, all_views = [], list(verification_views or [])
        for result, directory in tasks:
            ids = result.get("validation")
            views = ([_task_check_view(value, directory, project, warnings)
                      for value in ids] if isinstance(ids, list) else [])
            all_views.extend(views)
            task_blocks.append(_render_task_card(result, views, store, project))

        total, passed, bad, unrun = _counts(all_views)
        stats = (f"<p>统计：共 {total} 项 · 通过 {passed} · 异常 {bad} · 未运行 {unrun}。</p>"
                 if total else "")
        if verification_views is None:
            checks_section = ('<section id="checks"><h2>命令记录</h2>'
                              "<p>未提供验证回执：本报告覆盖的检查按<strong>未运行</strong>显示。"
                              "这只说明本报告未附回执，不断言这些命令从未在别处运行；"
                              "报告生成过程本身不执行命令。</p>" + stats + "</section>")
        else:
            body = "".join(_render_check(view, store, project, kind="命令记录")
                           for view in verification_views)
            if not verification_views:
                body = "<p>回执未包含任何检查条目。</p>"
            checks_section = (f'<section id="checks"><h2>命令记录（{len(verification_views)} 项）</h2>'
                              '<p class="note">以下为已有回执的<strong>历史命令记录</strong>：'
                              "通过仅表示记录中的退出码为 0 且日志存在；已核对回执提供的摘要。"
                              "未提供摘要的日志不能校验完整性，以上均不是当前工程、视觉或科学验收。</p>" + body + stats + "</section>")

        artifact_section = _render_artifacts(artifact_values, project, store, warnings) \
            if artifact_values else ""
        page = _render_page(title=title, summary=summary, timestamp=timestamp,
                            package=package.name, metrics=metrics, checks_section=checks_section,
                            task_blocks=task_blocks, artifact_section=artifact_section,
                            next_steps=next_steps)
        atomic_write_text(package / "index.html", page)
        entry = _index_entry(package.name, slug, title, timestamp, summary, (total, passed, bad, unrun))
        _update_index(reports, entry)
    result = {"report": str((package / "index.html").resolve()),
              "index": str((reports / "index.html").resolve())}
    if warnings:
        result["warnings"] = warnings
    return result


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="mw_report", description="Render a static human-readable HTML report package.")
    parser.add_argument("--project", type=Path, default=Path.cwd(),
                        help="Project root holding .mary-workflow/")
    parser.add_argument("--input", type=Path, required=True,
                        help="Authored presentation JSON payload file")
    parser.add_argument("--name", help="Optional safe slug for the package directory")
    args = parser.parse_args(argv)
    try:
        raw = _read_bytes(args.input).decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ReportError("输入必须是 JSON 对象")
        output = generate(args.project, payload, args.name)
    except ReportError as exc:
        parser.exit(2, f"mw-report: {exc}\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"mw-report: 无法读取输入或写出报告：{exc}\n")
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
