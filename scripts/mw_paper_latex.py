#!/usr/bin/env python3
"""Discover a paper folder and turn its LaTeX source into readable Markdown.

The generated Markdown is a learner-facing draft. PDF extraction remains the
machine-locatable evidence source, so LaTeX conversion never pretends to provide
page locators for claims.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Callable

from mw_paper_artifacts import NORMALIZED_SOURCE_FILE, RAW_SOURCE_PDF

MAX_SOURCE_BYTES = 64 * 1024 * 1024
PDF_EXTRACTOR = Callable[[bytes], tuple[str, dict[str, dict[str, object]]]]


class LatexFolderError(ValueError):
    """The supplied folder cannot provide a usable paper bundle."""


@dataclass(frozen=True)
class PaperFolder:
    folder: Path
    pdf: Path
    latex_entry: Path | None
    source_files: tuple[Path, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _candidate_files(folder: Path, suffix: str) -> list[Path]:
    ignored = {".git", ".hg", ".svn", "__pycache__", "build", "dist"}
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() == suffix.lower()
        and not any(part in ignored for part in path.relative_to(folder).parts)
    )


def _read_entry_hint(folder: Path) -> str | None:
    for path in sorted(folder.rglob("00README.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for item in payload.get("sources", []) if isinstance(payload, dict) else []:
            if isinstance(item, dict) and item.get("usage") == "toplevel" and item.get("filename"):
                return str(item["filename"])
    return None


def _select_pdf(candidates: list[Path]) -> Path:
    if not candidates:
        raise LatexFolderError("Paper folder contains no PDF source.")
    selected = max(candidates, key=lambda path: (path.stat().st_size, len(path.parts), path.as_posix()))
    if selected.stat().st_size > MAX_SOURCE_BYTES:
        raise LatexFolderError(
            f"The selected PDF exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MiB limit: {selected}"
        )
    # The paper PDF is normally the largest PDF; figure PDFs are intentionally
    # smaller and are not selected as the evidence source.
    return selected


def _select_latex(folder: Path, candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    hint = _read_entry_hint(folder)
    if hint:
        hinted = [path for path in candidates if path.name == Path(hint).name]
        if hinted:
            return min(hinted, key=lambda path: len(path.parts))
    named = [path for path in candidates if path.name.lower() in {"main.tex", "paper.tex", "manuscript.tex"}]
    if named:
        return min(named, key=lambda path: (len(path.parts), path.as_posix()))
    return max(candidates, key=lambda path: (path.stat().st_size, path.as_posix()))


def discover_paper_folder(folder: Path) -> PaperFolder:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise LatexFolderError(f"Paper source folder does not exist: {root}")
    pdf = _select_pdf(_candidate_files(root, ".pdf"))
    tex_candidates = _candidate_files(root, ".tex")
    latex_entry = _select_latex(root, tex_candidates)
    source_files: set[Path] = {pdf}
    if latex_entry is not None:
        queue = [latex_entry]
        seen: set[Path] = set()
        while queue:
            current = queue.pop()
            if current in seen or not current.is_file():
                continue
            seen.add(current)
            source_files.add(current)
            text = current.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"\\(?:input|include)\s*\{([^{}]+)\}", _strip_comments(text)):
                target = _resolve_tex_path(current.parent, match.group(1))
                if target is not None:
                    queue.append(target)
            for match in re.finditer(r"\\(?:bibliography|addbibresource)\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}", text):
                for item in match.group(1).split(","):
                    target = _resolve_asset_path(current.parent, item.strip(), (".bib",))
                    if target is not None:
                        source_files.add(target)
            for match in re.finditer(r"\\includegraphics(?:\[[^]]*\])?\s*\{([^{}]+)\}", text):
                target = _resolve_asset_path(current.parent, match.group(1).strip(),
                                             (".pdf", ".png", ".jpg", ".jpeg", ".eps"))
                if target is not None:
                    source_files.add(target)
    return PaperFolder(root, pdf, latex_entry, tuple(sorted(source_files, key=lambda path: path.as_posix())))


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def _resolve_asset_path(base: Path, raw: str, suffixes: tuple[str, ...]) -> Path | None:
    candidate = (base / raw).resolve()
    options = [candidate]
    if candidate.suffix == "":
        options.extend(candidate.with_suffix(suffix) for suffix in suffixes)
    return next((path for path in options if path.is_file()), None)


def _resolve_tex_path(base: Path, raw: str) -> Path | None:
    return _resolve_asset_path(base, raw, (".tex",))


def _balanced(text: str, opening: int) -> tuple[str, int] | None:
    if opening >= len(text) or text[opening] != "{":
        return None
    depth = 0
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if char == "{" and not escaped:
            depth += 1
        elif char == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return text[opening + 1:index], index + 1
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    return None


def _balanced_delimited(text: str, opening: int, left: str, right: str) -> tuple[str, int] | None:
    if opening >= len(text) or text[opening] != left:
        return None
    depth = 0
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if char == left and not escaped:
            depth += 1
        elif char == right and not escaped:
            depth -= 1
            if depth == 0:
                return text[opening + 1:index], index + 1
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    return None


def _command_arg(text: str, command: str, start: int = 0) -> tuple[str, int] | None:
    match = re.search(rf"\\{re.escape(command)}\s*\{{", text[start:])
    if match is None:
        return None
    opening = start + match.end() - 1
    value = _balanced(text, opening)
    if value is None:
        return None
    return value


def _expand_inputs(entry: Path) -> str:
    seen: set[Path] = set()

    def expand(path: Path) -> str:
        if path in seen:
            return "\n% skipped recursive input: " + path.name + "\n"
        seen.add(path)
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))

        def replace(match: re.Match[str]) -> str:
            target = _resolve_tex_path(path.parent, match.group(1))
            return expand(target) if target is not None else f"\n% missing input: {match.group(1)}\n"

        return re.sub(r"\\(?:input|include)\s*\{([^{}]+)\}", replace, text)

    return expand(entry)


def _collect_macros(text: str) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    simple: dict[str, str] = {}
    parameterized: dict[str, tuple[str, ...]] = {}
    for match in re.finditer(r"\\(?:newcommand|renewcommand)\s*\{\\([A-Za-z@]+)\}(?:\s*\[(\d+)\])?\s*\{", text):
        value = _balanced(text, match.end() - 1)
        if value is None:
            continue
        name = match.group(1)
        body, _ = value
        count = int(match.group(2) or "0")
        if count:
            parameterized[name] = tuple(f"#{index}" for index in range(1, count + 1))
            simple[name] = body
        else:
            simple[name] = body
    for match in re.finditer(r"\\def\\([A-Za-z@]+)((?:#\d+)*)\s*\{", text):
        value = _balanced(text, match.end() - 1)
        if value is None:
            continue
        name = match.group(1)
        body, _ = value
        parameters = tuple(re.findall(r"#\d", match.group(2)))
        if parameters:
            parameterized[name] = parameters
        simple[name] = body
    return simple, parameterized


def _extract_acronyms(text: str) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for match in re.finditer(r"\\acrodef\{([^{}]+)\}\[([^{}]+)\]\{([^{}]+)\}", text):
        result[match.group(1)] = (match.group(2), match.group(3))
    return result


def _replace_balanced_command(text: str, command: str, replacement: Callable[[str], str]) -> str:
    pattern = re.compile(rf"\\{re.escape(command)}\s*\{{")
    cursor = 0
    output: list[str] = []
    while True:
        match = pattern.search(text, cursor)
        if match is None:
            output.append(text[cursor:])
            return "".join(output)
        value = _balanced(text, match.end() - 1)
        if value is None:
            output.append(text[cursor:])
            return "".join(output)
        body, end = value
        output.append(text[cursor:match.start()])
        output.append(replacement(body))
        cursor = end


def _replace_macros(text: str, simple: dict[str, str], parameterized: dict[str, tuple[str, ...]]) -> str:
    for name, parameters in parameterized.items():
        if not parameters:
            continue
        pattern = re.compile(rf"\\{re.escape(name)}\s*")
        cursor = 0
        while True:
            match = pattern.search(text, cursor)
            if match is None:
                break
            args: list[str] = []
            end = match.end()
            valid = True
            for _ in parameters:
                while end < len(text) and text[end].isspace():
                    end += 1
                value = _balanced(text, end)
                if value is None:
                    valid = False
                    break
                arg, end = value
                args.append(arg)
            if not valid:
                cursor = match.end()
                continue
            body = simple.get(name, "")
            for index, arg in enumerate(args, start=1):
                body = body.replace(f"#{index}", arg)
            text = text[:match.start()] + body + text[end:]
            cursor = match.start() + len(body)
    for name, body in sorted(simple.items(), key=lambda item: -len(item[0])):
        if name in parameterized:
            continue
        text = re.sub(rf"\\{re.escape(name)}(?![A-Za-z@])", lambda _match, value=body: value, text)
    return text


def _clean_inline(text: str, acronyms: dict[str, tuple[str, str]]) -> str:
    math_blocks: list[str] = []

    def protect_math(match: re.Match[str]) -> str:
        value = match.group(0)
        if value.startswith("\\(") and value.endswith("\\)"):
            value = "$" + value[2:-2].strip() + "$"
        elif value.startswith("\\[") and value.endswith("\\]"):
            value = "$$\n" + value[2:-2].strip() + "\n$$"
        math_blocks.append(value)
        return f"@@MWMATH{len(math_blocks) - 1}@@"

    text = re.sub(r"\$\$.*?\$\$|\$[^$\n]+\$|\\\[.*?\\\]|\\\(.*?\\\)", protect_math, text, flags=re.DOTALL)
    text = re.sub(r"\\(?:ac|acs)\s*\{([^{}]+)\}", lambda m: acronyms.get(m.group(1), (m.group(1), m.group(1)))[0], text)
    text = re.sub(r"\\(?:acf|acl)\s*\{([^{}]+)\}", lambda m: acronyms.get(m.group(1), (m.group(1), m.group(1)))[1], text)
    text = re.sub(r"\\(?:citep|citet|cite|citeauthor|citeyear)\s*\{([^{}]+)\}", lambda m: f"[{m.group(1).replace(',', '; ')}]", text)
    text = re.sub(r"\\(?:cref|Cref|ref)\s*\{([^{}]+)\}", lambda m: f"[{m.group(1)}]", text)
    text = re.sub(r"\\label\s*\{[^{}]*\}", "", text)
    text = re.sub(r"\\url\s*\{([^{}]+)\}", r"<\1>", text)
    text = re.sub(r"\\(?:textbf|mathbf|boldsymbol)\s*\{([^{}]*)\}", r"**\1**", text)
    text = re.sub(r"\\(?:emph|textit|textnormal)\s*\{([^{}]*)\}", r"*\1*", text)
    text = re.sub(r"\\textsuperscript\s*\{([^{}]*)\}", r"^\1", text)
    text = re.sub(r"\\texttt\s*\{([^{}]*)\}", r"`\1`", text)
    text = re.sub(r"\\(?:mbox|hbox|textrm|mathrm|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}(?:\[[^]]*\])?", "", text)
    text = re.sub(r"\\(,|;|:|!|quad|qquad|enspace|xspace)\b", " ", text)
    text = text.replace("~", " ")
    text = re.sub(r"\\item\s*", "- ", text)
    text = re.sub(r"\\(?:linebreak|newpage|clearpage|noindent|centering)\b", "", text)
    text = re.sub(r"\\[A-Za-z@]+(?:\s*\[[^]]*\])?\s*", "", text)
    text = re.sub(r"\{[^{}\n]+\}\{([^{}\n]+)\}", r"\1", text)
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_")
    text = re.sub(r"[ \t]+", " ", text)
    for index, value in enumerate(math_blocks):
        text = text.replace(f"@@MWMATH{index}@@", value)
    return text.strip()


def _extract_environment(text: str, environment: str, start: int = 0) -> tuple[str, int, int] | None:
    opening = re.search(rf"\\begin\{{{re.escape(environment)}\}}", text[start:])
    if opening is None:
        return None
    begin = start + opening.start()
    body_start = start + opening.end()
    end_match = re.search(rf"\\end\{{{re.escape(environment)}\}}", text[body_start:])
    if end_match is None:
        return None
    body_end = body_start + end_match.start()
    return text[body_start:body_end], begin, body_start + end_match.end()


def _convert_figures(text: str) -> str:
    pattern = re.compile(r"\\begin\{(?:figure|figure\*)\}.*?\\end\{(?:figure|figure\*)\}", re.DOTALL)
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        body = match.group(0)
        caption_match = re.search(r"\\caption(?:\[[^]]*\])?\s*\{", body)
        caption = ""
        if caption_match:
            value = _balanced(body, caption_match.end() - 1)
            if value:
                caption = _clean_inline(value[0], {})
        label = re.search(r"\\label\{([^{}]+)\}", body)
        asset = re.search(r"\\includegraphics(?:\[[^]]*\])?\s*\{([^{}]+)\}", body)
        asset_name = asset.group(1).strip() if asset else "figure asset not extracted"
        title = f"Figure {counter}"
        if label:
            title += f" ({label.group(1)})"
        lines = [f"> **{title}.** {caption or 'Caption unavailable in the source.'}"]
        lines.append(f"> _Asset: `{asset_name}` (inspect the original PDF for the visual evidence.)_")
        return "\n\n" + "\n".join(lines) + "\n\n"

    return pattern.sub(replace, text)


def _convert_tables(text: str) -> str:
    pattern = re.compile(r"\\begin\{(?:table|table\*)\}.*?\\end\{(?:table|table\*)\}", re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        body = match.group(0)
        caption_match = re.search(r"\\caption(?:\[[^]]*\])?\s*\{", body)
        caption = ""
        if caption_match:
            value = _balanced(body, caption_match.end() - 1)
            if value:
                caption = _clean_inline(value[0], {})
        return f"\n\n> **Table.** {caption or 'Table caption available in the original PDF.'}\n> _Table content is kept in the PDF evidence source._\n\n"

    return pattern.sub(replace, text)


def _convert_equations(text: str) -> str:
    environments = ("equation", "equation*", "align", "align*", "gather", "gather*")
    for environment in environments:
        pattern = re.compile(rf"\\begin\{{{re.escape(environment)}\}}(.*?)\\end\{{{re.escape(environment)}\}}", re.DOTALL)
        text = pattern.sub(lambda match: f"\n\n$$\n{match.group(1).strip()}\n$$\n\n", text)
    return text


def _convert_headings(text: str) -> str:
    for command, level in (("section", 2), ("subsection", 3), ("subsubsection", 4), ("paragraph", 5)):
        pattern = re.compile(rf"\\{command}\s*\{{")
        cursor = 0
        pieces: list[str] = []
        while True:
            match = pattern.search(text, cursor)
            if match is None:
                pieces.append(text[cursor:])
                break
            value = _balanced(text, match.end() - 1)
            if value is None:
                pieces.append(text[cursor:])
                break
            pieces.append(text[cursor:match.start()])
            pieces.append("#" * level + " " + _clean_inline(value[0], {}))
            cursor = value[1]
        text = "".join(pieces)
    return text


def _remove_command_block(text: str, command: str, left: str = "[", right: str = "]") -> str:
    marker = re.compile(rf"\\{re.escape(command)}\s*{re.escape(left)}")
    while True:
        match = marker.search(text)
        if match is None:
            return text
        value = _balanced_delimited(text, match.end() - 1, left, right)
        if value is None:
            return text
        text = text[:match.start()] + text[value[1]:]


def latex_to_markdown(source: str, entry: Path, folder: Path) -> tuple[str, dict[str, object]]:
    expanded = _expand_inputs(entry)
    acronyms = _extract_acronyms(expanded)
    simple, parameterized = _collect_macros(expanded)
    title_value = _command_arg(expanded, "title")
    author_value = _command_arg(expanded, "author")
    abstract = _extract_environment(expanded, "abstract")
    body = re.search(r"\\begin\{document\}(.*)\\end\{document\}", expanded, flags=re.DOTALL)
    content = body.group(1) if body else expanded
    content = _replace_macros(content, simple, parameterized)
    content = _remove_command_block(content, "twocolumn")
    content = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", "", content, flags=re.DOTALL)
    content = _convert_figures(content)
    content = _convert_tables(content)
    content = _convert_equations(content)
    content = _convert_headings(content)
    content = _clean_inline(content, acronyms)
    content = re.sub(r"\{(?:itemize|enumerate|description)\}(?:\[[^]]*\])?", "", content)
    content = re.sub(r"\\(?:maketitle|twocolumn|onecolumn|appendix)\b", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    title_body = _replace_macros(title_value[0], simple, parameterized) if title_value else entry.stem
    author_body = _replace_macros(author_value[0], simple, parameterized) if author_value else "Unknown authors"
    abstract_body = _replace_macros(abstract[0], simple, parameterized) if abstract else "Abstract text was not extracted from the LaTeX source."
    title = _clean_inline(title_body, acronyms)
    authors = _clean_inline(author_body, acronyms)
    abstract_text = _clean_inline(abstract_body, acronyms)
    authors = re.sub(r"\$+", "", authors)
    authors = re.sub(r"\\(?:dagger|star|,|quad|textsuperscript)\s*", "", authors)
    authors = authors.replace("\\\\", "; ")
    authors = re.sub(r"\s+", " ", authors).strip()
    header = [
        "<!-- mary-reading:v1 -->",
        "",
        f"# {title}",
        "",
        f"**Authors:** {authors}",
        "",
        "> This is a LaTeX-derived reading draft. Scientific claims must be checked against the PDF evidence source; difficult points intentionally keep an empty Open question area.",
        "",
        "## Abstract",
        "",
        abstract_text,
        "",
    ]
    document = "\n".join(header) + content.strip() + "\n"
    document += "\n## Open Questions\n\n<details>\n<summary>Open question</summary>\n\n<!-- Add the learner's question or clarification here. -->\n\n</details>\n"
    document = re.sub(r"\n{3,}", "\n\n", document)
    metadata = {
        "title": title,
        "authors": authors,
        "latex_entry": _relative(entry, folder),
        "source_kind": "latex",
        "open_question_template": "<details>\n<summary>Open question</summary>\n\n<!-- Add the learner's question or clarification here. -->\n\n</details>",
    }
    return document, metadata


def _manifest(folder: PaperFolder) -> dict[str, object]:
    files = [
        {"path": _relative(path, folder.folder), "sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in folder.source_files
    ]
    payload = {
        "source_manifest_schema": 1,
        "folder": str(folder.folder),
        "selected_pdf": _relative(folder.pdf, folder.folder),
        "latex_entry": _relative(folder.latex_entry, folder.folder) if folder.latex_entry else "",
        "files": files,
    }
    identity = {key: value for key, value in payload.items() if key != "folder"}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    payload["bundle_fingerprint"] = digest
    return payload


def acquire_folder_source(folder: Path, pdf_extractor: PDF_EXTRACTOR) -> dict[str, object]:
    paper = discover_paper_folder(folder)
    pdf_bytes = paper.pdf.read_bytes()
    if not pdf_bytes.startswith(b"%PDF-"):
        raise LatexFolderError(f"Selected evidence file is not a PDF: {paper.pdf}")
    normalized_source, dimensions = pdf_extractor(pdf_bytes)
    manifest = _manifest(paper)
    latex_markdown = ""
    latex_metadata: dict[str, object] = {"source_kind": "pdf-only"}
    if paper.latex_entry is not None:
        latex_markdown, latex_metadata = latex_to_markdown(
            _expand_inputs(paper.latex_entry), paper.latex_entry, paper.folder
        )
    else:
        latex_markdown = (
            "<!-- mary-reading:v1 -->\n\n"
            "# Paper Reading Draft\n\n"
            "> No LaTeX source was found. This draft is organized from the PDF text; "
            "check equations, section order, and figures against the original PDF.\n\n"
            + normalized_source
            + "\n## Open Questions\n\n"
            "<details>\n<summary>Open question</summary>\n\n"
            "<!-- Add the learner's question or clarification here. -->\n\n"
            "</details>\n"
        )
    gate, blocking = _quality_gate(dimensions)
    source_locator = str(paper.folder)
    report = {
        "parse_quality_schema": 1,
        "source": {
            "locator": source_locator,
            "resolved_locator": str(paper.pdf),
            "format": "pdf",
            "fingerprint": str(manifest["bundle_fingerprint"]),
            "pdf_fingerprint": _sha256(paper.pdf),
            "raw_artifact": RAW_SOURCE_PDF,
            "normalized_artifact": NORMALIZED_SOURCE_FILE,
            "input_kind": "folder",
            "selected_pdf": _relative(paper.pdf, paper.folder),
            "latex_entry": _relative(paper.latex_entry, paper.folder) if paper.latex_entry else "",
        },
        "dimensions": dimensions,
        "gate": gate,
        "blocking_dimensions": blocking,
        "acquisition_attempts": [{
            "format": "folder",
            "locator": source_locator,
            "result": "selected",
            "pdf": _relative(paper.pdf, paper.folder),
            "latex": _relative(paper.latex_entry, paper.folder) if paper.latex_entry else "",
        }],
        "source_manifest": manifest,
    }
    return {
        "raw": pdf_bytes,
        "normalized_source": normalized_source,
        "report": report,
        "reading_markdown": latex_markdown,
        "reading_metadata": latex_metadata,
    }


def _quality_gate(dimensions: dict[str, dict[str, object]]) -> tuple[str, list[str]]:
    blocking = [
        name for name, item in dimensions.items()
        if str(item.get("status")) == "failed"
    ]
    return ("blocked" if blocking else "pass"), blocking
