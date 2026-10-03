#!/usr/bin/env python3
"""Offline native XeLaTeX presentation support and grounded paper lint.

The authoring grammar deliberately exposes ordinary Beamer frames, common
text/math environments, and fixed figure/layout macros. It does not execute
user-defined TeX or expand arbitrary inclusions to discover page structure.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Any

from mw_paper_artifacts import SLIDES_CONTEXT_FILE, resolve_artifact_path
from mw_paper_sources import sha256_file


BEAMER_SLIDES_FILE = "slides.tex"
BEAMER_THEME_NAME = "mary-shanghaitech-red-beamer"
BEAMER_ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "beamer"
BEAMER_SUPPORT_DIRECTORY = "beamer"
BEAMER_MARKER = "% mary-slides:beamer:v1"
BEAMER_SUPPORT_FILES = (
    ".mary-beamer-support",
    "LICENSE",
    "THIRD_PARTY_ASSETS.md",
    "mary-paper.tex",
    "slides-template.tex",
    "themes/beamerthemeVSP.sty",
    "themes/beamerthemetutorial-red-shtu.sty",
    "images/shanghaitech-master.png",
    "images/ShanghaiTech_Logo_RGBA.png",
    "images/ShanghaiTech_Name_RGBA.png",
)
MAX_PAGES = 24
MAX_VISIBLE_CHARACTERS = 900
MAX_VISIBLE_LINES = 36
MAX_LIST_ITEMS = 8
MAX_CODE_LINES = 14
SECTION_ORDER = ("background", "method", "experiments", "takeaways")
SECTION_PREFIXES = {"background": "B", "method": "M", "experiments": "E"}
SECTION_PATTERN = re.compile(r"(?m)^\s*%\s*section:\s*(\S+)\s*$")
CLAIMS_PATTERN = re.compile(r"(?m)^\s*%\s*claims:\s*([^\n]*)$")
CLAIM_PATTERN = re.compile(r"[BME][0-9]{2,}")
VISIBLE_CLAIM_PATTERN = re.compile(r"(?<![A-Za-z0-9])[BME][0-9]{2,}(?![A-Za-z0-9])")
FIGURE_REFERENCE_PATTERN = re.compile(r"(?:\bfig(?:ure)?\.?|图)\s*([0-9]+(?:[a-z])?)", re.I)
COMMAND_PATTERN = re.compile(r"\\([A-Za-z]+|[^A-Za-z])")
LISTING_PATTERN = re.compile(r"\\begin\{(lstlisting|verbatim)\}(.*?)\\end\{\1\}", re.S)

# All permitted commands render text/math or use a fixed local presentation
# primitive. No definitions, I/O primitives, expansion, or font/template changes.
ALLOWED_COMMANDS = set("""
begin end MaryFigure MaryColumns MaryRows MaryPinThree includegraphics
item textbf textit texttt textrm textsf textnormal emph alert textcolor
underline overline hat widehat bar vec dot ddot tilde widetilde
textbackslash textasciitilde textasciicircum textless textgreater
par medskip smallskip bigskip hfill vfill quad qquad newline linebreak
centering raggedright raggedleft linewidth textwidth textheight
toprule midrule bottomrule cmidrule multicolumn multirow caption
label ref eqref cite url footnote
frac dfrac tfrac sqrt binom dbinom tbinom left right middle
sum prod coprod int iint iiint oint lim min max arg det log ln exp sin cos tan
sup inf argmin argmax operatorname mathrm mathbf mathit mathsf mathtt
mathcal mathbb mathfrak boldsymbol bm text substack overset underset
mathop limits nolimits displaystyle textstyle scriptstyle scriptscriptstyle
cdot cdots ldots vdots ddots times div pm mp ast star circ bullet
le leq ge geq neq ne approx equiv sim simeq propto ll gg in notin ni
subset subseteq supset supseteq cup cap setminus emptyset varnothing
forall exists neg land lor wedge vee lnot implies iff to mapsto
rightarrow leftarrow leftrightarrow Rightarrow Leftarrow Leftrightarrow
longrightarrow longleftarrow Longrightarrow Longleftarrow
uparrow downarrow partial nabla infinity infty ell hbar
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
langle rangle lvert rvert lVert rVert vert Vert lbrace rbrace
underbrace overbrace phantom hphantom vphantom nonumber notag
cr hline cline percent degree
""".split())
ALLOWED_ENVIRONMENTS = {
    "frame", "columns", "column", "itemize", "enumerate", "description",
    "block", "alertblock", "exampleblock", "center", "flushleft", "flushright",
    "minipage", "tabular", "tabularx", "array", "matrix", "pmatrix", "bmatrix",
    "Bmatrix", "vmatrix", "Vmatrix", "cases", "aligned", "alignedat", "gathered",
    "equation", "equation*", "align", "align*", "gather", "gather*", "split",
    "lstlisting", "verbatim", "vspquote", "vspquoteblue", "vspquotered",
    "vspquotegreen", "vspquotepurple", "vspquoteblack", "vspquoteyellow",
}
LAYOUT_ARITIES = {"MaryColumns": 2, "MaryRows": 2, "MaryPinThree": 3}
JsonObject = dict[str, Any]


class BeamerError(ValueError):
    """A native paper deck or its installed support violated the contract."""


def _support_record(root: Path) -> JsonObject:
    files: dict[str, str] = {}
    for name in BEAMER_SUPPORT_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise BeamerError(f"Offline Beamer support is missing or unsafe: {path}")
        files[f"beamer/{name}"] = sha256_file(path)
    digest = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"directory": BEAMER_SUPPORT_DIRECTORY, "fingerprint": digest, "files": files}


def install_beamer_support(workspace: Path) -> JsonObject:
    """Localize the distributable bundle; never overwrite the final slides.tex."""
    destination = Path(workspace) / BEAMER_SUPPORT_DIRECTORY
    source_record = _support_record(BEAMER_ASSET_ROOT)
    if destination.is_symlink():
        raise BeamerError("beamer/ must be a workspace-local directory, not a symlink.")
    if destination.exists() and not destination.is_dir():
        raise BeamerError("Existing beamer path must be a directory; preserve or move it before prepare-slides.")
    if destination.exists() and any(destination.iterdir()):
        marker = destination / ".mary-beamer-support"
        if not marker.is_file() or marker.read_bytes() != (BEAMER_ASSET_ROOT / ".mary-beamer-support").read_bytes():
            raise BeamerError("Existing beamer/ is not Mary-managed; preserve or move it before prepare-slides.")
    for name in BEAMER_SUPPORT_FILES:
        target = destination / name
        if target.is_symlink() or not target.resolve().is_relative_to(destination.resolve()):
            raise BeamerError(f"Cannot install Beamer support through a symlink: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BEAMER_ASSET_ROOT / name, target)
    return source_record


def validate_beamer_support(workspace: Path) -> JsonObject:
    installed = Path(workspace) / BEAMER_SUPPORT_DIRECTORY
    if installed.is_symlink():
        raise BeamerError("beamer/ must be a workspace-local directory, not a symlink.")
    actual = _support_record(installed)
    expected = _support_record(BEAMER_ASSET_ROOT)
    if actual != expected:
        raise BeamerError("Offline Beamer support is stale; run prepare-slides again.")
    return actual


def beamer_presentation(workspace: Path) -> JsonObject:
    support = validate_beamer_support(workspace)
    return {
        "backend": "beamer",
        "source_artifact": BEAMER_SLIDES_FILE,
        "theme": BEAMER_THEME_NAME,
        "theme_fingerprint": support["fingerprint"],
        "math": "xelatex",
        "size": "16:9",
        "support": support,
    }


def strip_tex_comments(text: str) -> str:
    """Remove comments while retaining escaped percentages and line boundaries."""
    lines = []
    listing: str | None = None
    for line in text.splitlines():
        if listing is not None:
            lines.append(line)
            if r"\end{" + listing + "}" in line:
                listing = None
            continue
        for match in re.finditer("%", line):
            backslashes = len(line[:match.start()]) - len(line[:match.start()].rstrip("\\"))
            if backslashes % 2 == 0:
                line = line[:match.start()]
                break
        match = re.search(r"\\begin\{(lstlisting|verbatim)\}", line)
        if match and r"\end{" + match.group(1) + "}" not in line:
            listing = match.group(1)
        lines.append(line)
    return "\n".join(lines)


def _skip_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _group(text: str, offset: int, *, optional: bool = False) -> tuple[str, int]:
    offset = _skip_space(text, offset)
    opening, closing = ("[", "]") if optional else ("{", "}")
    if offset >= len(text) or text[offset] != opening:
        raise BeamerError(f"slides.tex requires a balanced {opening}...{closing} argument.")
    start = offset + 1
    depth = 1
    offset += 1
    while offset < len(text):
        character = text[offset]
        if character == "\\" and offset + 1 < len(text):
            offset += 2
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return text[start:offset], offset + 1
        offset += 1
    raise BeamerError("slides.tex has an unclosed TeX argument.")


def _calls(text: str, name: str, arity: int) -> list[tuple[int, int, list[str]]]:
    result = []
    for match in re.finditer(r"\\" + re.escape(name) + r"(?![A-Za-z])", text):
        offset = match.end()
        arguments = []
        for _ in range(arity):
            argument, offset = _group(text, offset)
            arguments.append(argument)
        result.append((match.start(), offset, arguments))
    return result


def tex_unescape(text: str) -> str:
    """Decode authoring escapes before comparing exact catalog captions/locators."""
    result = text
    for command, value in (
        (r"\textbackslash{}", "\\"), (r"\textasciitilde{}", "~"),
        (r"\textasciicircum{}", "^"),
    ):
        result = result.replace(command, value)
    result = re.sub(r"\\([%&#_$\{\}])", lambda match: match.group(1), result)
    return result


def _listing_mask(text: str) -> str:
    """Keep offsets/newlines while removing displayed code from TeX semantics."""
    return LISTING_PATTERN.sub(
        lambda match: re.sub(r"[^\n]", " ", match.group(0)), text
    )


def _safe_media(workspace: Path, value: str, page_number: int) -> None:
    value = tex_unescape(value).strip()
    path = PurePosixPath(value)
    if (not value or re.search(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
            or value.startswith("//") or path.is_absolute() or ".." in path.parts
            or "\\" in value or any(character in value for character in "{}\x00")):
        raise BeamerError(f"slides.tex page {page_number} has an unsafe local image reference: {value[:80]}")
    target = (Path(workspace) / path.as_posix()).resolve()
    if not target.is_relative_to(Path(workspace).resolve()):
        raise BeamerError(f"slides.tex page {page_number} image escapes the paper workspace: {value}")
    if not target.is_file():
        raise BeamerError(f"slides.tex page {page_number} image does not exist: {value}")
    if target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf"}:
        raise BeamerError(f"slides.tex page {page_number} requires a XeLaTeX image (PNG, JPEG, PDF): {value}")


def _validate_tex(text: str) -> None:
    # ^^ can construct control sequences even when their spelling is absent.
    if "^^" in text or "\x00" in text:
        raise BeamerError("slides.tex contains unsafe TeX character construction.")
    syntax = LISTING_PATTERN.sub("", text)
    for match in COMMAND_PATTERN.finditer(syntax):
        command = match.group(1)
        if command.isalpha() and command not in ALLOWED_COMMANDS:
            raise BeamerError(f"slides.tex uses unsupported or unsafe command \\{command}.")
        if not command.isalpha() and command not in "%&#_$\\{}[](),;!:| -/":
            raise BeamerError(f"slides.tex uses unsupported control symbol \\{command}.")
        if syntax[match.end():].lstrip().startswith("<") and command not in {"left", "right", "middle"}:
            raise BeamerError("slides.tex overlays are unsupported; each frame must render exactly once.")
    if re.search(r"\\begin\s*\{[^{}]+\}\s*(?:<|\[[^\]]*<)", syntax):
        raise BeamerError("slides.tex environment overlays are unsupported; each frame must render exactly once.")
    stack: list[str] = []
    for match in re.finditer(r"\\(begin|end)\s*\{([^{}]+)\}", syntax):
        action, environment = match.groups()
        if environment not in ALLOWED_ENVIRONMENTS:
            raise BeamerError(f"slides.tex uses unsupported environment {environment}.")
        if action == "begin":
            stack.append(environment)
        elif not stack or stack.pop() != environment:
            raise BeamerError("slides.tex contains mismatched environments.")
    if stack:
        raise BeamerError("slides.tex contains unclosed environments.")
    # Balanced groups prevent a frame or macro argument from absorbing the next
    # frame, defeating page extraction or the capacity checks.
    depth = 0
    offset = 0
    while offset < len(syntax):
        if syntax[offset] == "\\":
            offset += 2
            continue
        if syntax[offset] == "{":
            depth += 1
        elif syntax[offset] == "}":
            depth -= 1
            if depth < 0:
                raise BeamerError("slides.tex contains mismatched TeX groups.")
        offset += 1
    if depth:
        raise BeamerError("slides.tex contains unclosed TeX groups.")


def _validate_inline(text: str) -> None:
    _validate_tex(text)
    forbidden = {"begin", "end", "includegraphics", "MaryFigure", "MaryColumns", "MaryRows",
                 "MaryPinThree", "item", "caption", "footnote"}
    if any(match.group(1) in forbidden for match in COMMAND_PATTERN.finditer(text)):
        raise BeamerError("slides.tex titles and metadata permit inline text/math only, without figures or frames.")


def _preamble(text: str) -> dict[str, str]:
    clean = strip_tex_comments(text).strip()
    required = r"\documentclass[aspectratio=169,10pt]{beamer}"
    if not clean.startswith(required):
        raise BeamerError("slides.tex must start with \\documentclass[aspectratio=169,10pt]{beamer}.")
    clean = clean[len(required):].lstrip()
    support = r"\input{beamer/mary-paper.tex}"
    if not clean.startswith(support):
        raise BeamerError("slides.tex must load only \\input{beamer/mary-paper.tex} after documentclass.")
    clean = clean[len(support):]
    metadata: dict[str, str] = {}
    offset = 0
    while _skip_space(clean, offset) < len(clean):
        offset = _skip_space(clean, offset)
        match = re.match(r"\\(title|subtitle|author|institute|date)(?![A-Za-z])", clean[offset:])
        if match is None:
            raise BeamerError("slides.tex preamble permits only title/subtitle/author/institute/date metadata.")
        name = match.group(1)
        if name in metadata:
            raise BeamerError(f"slides.tex preamble repeats {name}.")
        value, offset = _group(clean, offset + match.end())
        _validate_inline(value)
        metadata[name] = value
    if not metadata.get("title", "").strip():
        raise BeamerError("slides.tex requires one non-empty title.")
    return metadata


def _pages(text: str) -> tuple[dict[str, str], list[JsonObject]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(re.findall(r"(?m)^\s*%\s*mary-slides:beamer:v1\s*$", text)) != 1:
        raise BeamerError(f"slides.tex must contain exactly one {BEAMER_MARKER} marker.")
    document_start = list(re.finditer(r"\\begin\{document\}", text))
    document_end = list(re.finditer(r"\\end\{document\}", text))
    if len(document_start) != 1 or len(document_end) != 1:
        raise BeamerError("slides.tex requires exactly one document environment.")
    start, end = document_start[0], document_end[0]
    if start.end() >= end.start() or strip_tex_comments(text[end.end():]).strip():
        raise BeamerError("slides.tex has invalid document boundaries or trailing content.")
    metadata = _preamble(text[:start.start()])
    raw = text[start.end():end.start()]
    # Preserve comment offsets so each hidden declaration belongs to the frame
    # containing it, rather than leaking into its neighbour.
    clean = "\n".join(
        stripped.ljust(len(line))
        for line in raw.splitlines()
        for stripped in [strip_tex_comments(line)]
    )
    pages = []
    offset = 0
    while _skip_space(clean, offset) < len(clean):
        offset = _skip_space(clean, offset)
        if clean.startswith(r"\VSPtitleframe", offset):
            following = offset + len(r"\VSPtitleframe")
            if following < len(clean) and clean[following].isalpha():
                raise BeamerError("slides.tex has an unsupported page command.")
            pages.append({"kind": "cover", "title": metadata["title"], "body": ""})
            offset = following
        elif clean.startswith(r"\VSPendframe", offset):
            title, offset = _group(clean, offset + len(r"\VSPendframe"))
            _validate_inline(title)
            if not title.strip():
                raise BeamerError("slides.tex requires a non-empty closing title.")
            pages.append({"kind": "closing", "title": title, "body": ""})
        elif clean.startswith(r"\VSPsectionframe", offset):
            title, cursor = _group(clean, offset + len(r"\VSPsectionframe"))
            subtitle, offset = _group(clean, cursor)
            _validate_inline(title + " " + subtitle)
            pages.append({"kind": "structural", "title": title, "body": subtitle})
        elif clean.startswith(r"\begin{frame}", offset):
            cursor = _skip_space(clean, offset + len(r"\begin{frame}"))
            options = ""
            if cursor < len(clean) and clean[cursor] == "[":
                options, cursor = _group(clean, cursor, optional=True)
                if not set(options.split(",")) <= {"t", "c", "b", "fragile"}:
                    raise BeamerError("slides.tex frame options permit only t/c/b/fragile; no overlays, breaks, or shrink.")
            title, cursor = _group(clean, cursor)
            if not title.strip():
                raise BeamerError("slides.tex each content frame requires one non-empty title.")
            _validate_inline(title)
            frame_syntax = _listing_mask(clean)
            ending = frame_syntax.find(r"\end{frame}", cursor)
            if ending < 0 or r"\begin{frame}" in frame_syntax[cursor:ending]:
                raise BeamerError("slides.tex has an unclosed or nested frame.")
            body = raw[cursor:ending]
            # raw starts with a newline and splitlines retains that line. Both
            # strings have identical offsets except their absent final newline.
            _validate_tex(title + "\n" + strip_tex_comments(body))
            pages.append({"kind": "content", "title": title, "body": body, "options": options})
            offset = ending + len(r"\end{frame}")
        else:
            raise BeamerError("slides.tex document contains unsupported content outside an explicit frame.")
    if not 6 <= len(pages) <= MAX_PAGES:
        raise BeamerError(f"slides.tex must contain 6-{MAX_PAGES} slides; found {len(pages)}.")
    if pages[0]["kind"] != "cover" or pages[-1]["kind"] != "closing":
        raise BeamerError("slides.tex requires VSPtitleframe first and a pure VSPendframe last.")
    if any(page["kind"] in {"cover", "closing"} for page in pages[1:-1]):
        raise BeamerError("slides.tex may contain only one cover and one closing page.")
    declaration_source = _listing_mask(text)
    for pattern in (SECTION_PATTERN, CLAIMS_PATTERN):
        if len(pattern.findall(declaration_source)) != sum(
            len(pattern.findall(_listing_mask(page["body"]))) for page in pages
        ):
            raise BeamerError("slides.tex hidden sections/claims must be inside their content frame.")
    return metadata, pages


def _visible_tex(text: str) -> str:
    code = []
    def keep_code(match: re.Match[str]) -> str:
        code.append(match.group(2))
        return f"MARYCODETOKEN{len(code) - 1}TOKEN"
    clean = strip_tex_comments(LISTING_PATTERN.sub(keep_code, text))
    # Figure metadata and filenames never render. Its number and exact caption do.
    for start, end, args in reversed(_calls(clean, "MaryFigure", 4)):
        clean = clean[:start] + args[0] + "\n" + args[2] + clean[end:]
    clean = re.sub(r"\\includegraphics(?:\[[^]]*\])?\s*\{[^{}]*\}", "", clean)
    clean = re.sub(r"\\begin\{column\}\s*\{[^{}]*\}", "", clean)
    clean = re.sub(r"\\(?:begin|end)\{[^{}]*\}(?:\[[^]]*\])?", "", clean)
    clean = tex_unescape(clean)
    clean = re.sub(r"\\(?:textwidth|linewidth|textheight)\b", "", clean)
    clean = re.sub(r"\\(?:par|newline|linebreak)(?![A-Za-z])", "\n", clean)
    clean = clean.replace(r"\\", "\n")
    clean = COMMAND_PATTERN.sub(lambda match: " " if match.group(1).isalpha() else match.group(1), clean)
    clean = clean.replace("{", " ").replace("}", " ")
    for index, content in enumerate(code):
        clean = clean.replace(f"MARYCODETOKEN{index}TOKEN", content)
    return clean


def _capacity(text: str, page_number: int) -> JsonObject:
    clean = strip_tex_comments(text)
    visible = _visible_tex(text)
    metrics = {
        "visible_characters": len(re.sub(r"\s+", "", visible)),
        "visible_lines": sum(bool(line.strip()) for line in visible.splitlines()),
        "list_items": len(re.findall(r"\\item(?![A-Za-z])", LISTING_PATTERN.sub("", clean))),
        "code_lines": sum(
            sum(bool(line.strip()) for line in match.group(2).splitlines())
            for match in LISTING_PATTERN.finditer(text)
        ),
    }
    limits = {
        "visible_characters": MAX_VISIBLE_CHARACTERS,
        "visible_lines": MAX_VISIBLE_LINES,
        "list_items": MAX_LIST_ITEMS,
        "code_lines": MAX_CODE_LINES,
    }
    for name, limit in limits.items():
        if metrics[name] > limit:
            raise BeamerError(f"slides.tex page {page_number} exceeds {name} limit: {metrics[name]} > {limit}.")
    return metrics


def _layout(text: str) -> bool:
    found = False
    syntax = _listing_mask(text)
    for name, arity in LAYOUT_ARITIES.items():
        for start, _, _ in _calls(syntax, name, arity):
            args = []
            offset = start + len(name) + 1
            for _ in range(arity):
                argument, offset = _group(text, offset)
                args.append(argument)
            if any(not _visible_tex(argument).strip() and not re.search(
                r"\\(?:includegraphics|MaryFigure)(?![A-Za-z])", _listing_mask(argument)
            ) for argument in args):
                raise BeamerError("slides.tex multi-panel macros require non-empty panels.")
            found = True
    for match in re.finditer(r"\\begin\{columns\}(.*?)\\end\{columns\}", syntax, re.S):
        panels = re.findall(r"\\begin\{column\}(?:\[[^]]*\])?\s*\{[^{}]+\}(.*?)\\end\{column\}", match.group(1), re.S)
        if len(panels) >= 2:
            if any(not _visible_tex(panel).strip() and not re.search(
                r"\\(?:includegraphics|MaryFigure)(?![A-Za-z])", panel
            ) for panel in panels):
                raise BeamerError("slides.tex multi-panel columns require non-empty panels.")
            found = True
    return found


def validate_beamer_document(workspace: Path, text: str, context: JsonObject) -> JsonObject:
    """Validate the same narrative, lineage, figure and capacity contract as Marp."""
    metadata, pages = _pages(text)
    claims = {item["claim_id"]: item["section"] for item in context["claim_catalog"]}
    figures = {item["figure_id"]: item for item in context["figure_catalog"]}
    assets = {item["figure_id"]: item for item in context.get("figure_assets", [])}
    counts = {section: 0 for section in SECTION_ORDER}
    sequence: list[str] = []
    referenced_claims: set[str] = set()
    referenced_figures: set[str] = set()
    layout_pages = 0
    placeholder_count = 0
    page_metrics = []
    for index, page in enumerate(pages, start=1):
        body = page["body"]
        clean = strip_tex_comments(body)
        semantics = _listing_mask(clean)
        if page["kind"] == "content":
            sections = SECTION_PATTERN.findall(_listing_mask(body))
            declarations = CLAIMS_PATTERN.findall(_listing_mask(body))
            if len(sections) != 1 or sections[0] not in SECTION_ORDER:
                raise BeamerError(f"slides.tex content page {index} requires exactly one valid hidden section.")
            section = sections[0]
            if len(declarations) != 1:
                raise BeamerError(f"slides.tex content page {index} requires exactly one hidden claims declaration.")
            page_claims = declarations[0].split()
            if not page_claims or len(set(page_claims)) != len(page_claims) or any(
                CLAIM_PATTERN.fullmatch(claim) is None for claim in page_claims
            ):
                raise BeamerError(f"slides.tex page {index} contains invalid or duplicate claim references.")
            for claim in page_claims:
                if claim not in claims:
                    raise BeamerError(f"slides.tex page {index} references unknown summary claim {claim}.")
                if section in SECTION_PREFIXES and not claim.startswith(SECTION_PREFIXES[section]):
                    raise BeamerError(f"slides.tex page {index} section {section} cannot cite {claim}.")
                referenced_claims.add(claim)
            counts[section] += 1
            sequence.append(section)
        elif SECTION_PATTERN.search(body) or CLAIMS_PATTERN.search(body):
            raise BeamerError("slides.tex structural, cover, and closing pages cannot declare factual claims.")
        visible = _visible_tex(page["title"] + "\n" + body)
        if page["kind"] == "cover":
            visible += _visible_tex("\n".join(metadata.values()))
        if VISIBLE_CLAIM_PATTERN.search(visible):
            raise BeamerError(f"slides.tex page {index} exposes summary claim ids; keep them in hidden comments.")
        if _layout(clean):
            layout_pages += 1
        figure_calls = _calls(semantics, "MaryFigure", 4)
        page_figures: set[str] = set()
        without_captions = clean
        for start, end, arguments in reversed(figure_calls):
            figure_id, locator, caption, image = [tex_unescape(argument).strip() for argument in arguments]
            if figure_id not in figures:
                raise BeamerError(f"slides.tex page {index} references unknown {figure_id or 'Figure'}.")
            expected = figures[figure_id]
            if locator not in expected["source_locators"]:
                raise BeamerError(f"slides.tex page {index} locator does not resolve for {figure_id}.")
            if " ".join(caption.split()) != " ".join(str(expected["caption"]).split()):
                raise BeamerError(f"slides.tex page {index} caption does not exactly match {figure_id} context.")
            if figure_id in assets and image != assets[figure_id]["path"]:
                raise BeamerError(f"slides.tex page {index} must embed the prepared source asset for {figure_id}: {assets[figure_id]['path']}.")
            if image:
                _safe_media(workspace, image, index)
            page_figures.add(figure_id)
            referenced_figures.add(figure_id)
            placeholder_count += 1
            without_captions = without_captions[:start] + figure_id + without_captions[end:]
        visible_references = _visible_tex(page["title"] + "\n" + without_captions)
        mentions = {f"Figure {token.upper()}" for token in FIGURE_REFERENCE_PATTERN.findall(visible_references)}
        if mentions - set(figures):
            raise BeamerError(f"slides.tex page {index} references unknown figures: {', '.join(sorted(mentions - set(figures)))}.")
        if mentions - page_figures:
            raise BeamerError(f"slides.tex page {index} references figures without matching figure placeholders.")
        for match in re.finditer(r"\\includegraphics(?![A-Za-z])", semantics):
            offset = _skip_space(semantics, match.end())
            if offset < len(semantics) and semantics[offset] == "[":
                _, offset = _group(semantics, offset, optional=True)
            path, _ = _group(semantics, offset)
            _safe_media(workspace, path, index)
        metric_text = page["title"] + "\n" + body
        if page["kind"] == "cover":
            metric_text = "\n".join(metadata.values())
        page_metrics.append({"page": index, **_capacity(metric_text, index)})
    ranks = [SECTION_ORDER.index(section) for section in sequence]
    if ranks != sorted(ranks):
        raise BeamerError("slides.tex sections must progress background -> method -> experiments -> takeaways.")
    for section, minimum in (("background", 1), ("method", 2), ("experiments", 1)):
        if counts[section] < minimum:
            raise BeamerError(f"slides.tex requires at least {minimum} {section} content page(s).")
    if counts["method"] < max(counts["background"], counts["experiments"]):
        raise BeamerError("slides.tex must keep Method at least as detailed as Background and Experiments.")
    if layout_pages < 2:
        raise BeamerError("slides.tex requires real multi-panel layouts on at least two pages.")
    if figures and placeholder_count == 0:
        raise BeamerError("slides.tex must include at least one figure placeholder from the Figure catalog.")
    missing = [prefix for prefix in ("B", "M", "E") if not any(claim.startswith(prefix) for claim in referenced_claims)]
    if missing:
        raise BeamerError("slides.tex must cite background, method, and experiment claim families; missing: " + ", ".join(missing) + ".")
    return {
        "page_count": len(pages), "section_page_counts": counts,
        "layout_page_count": layout_pages, "claim_reference_count": len(referenced_claims),
        "referenced_claim_ids": sorted(referenced_claims),
        "figure_placeholder_count": placeholder_count,
        "referenced_figure_ids": sorted(referenced_figures), "page_metrics": page_metrics,
    }


def validate_beamer_slides(workspace: Path, context: JsonObject) -> JsonObject:
    path = Path(workspace) / BEAMER_SLIDES_FILE
    if not path.is_file():
        raise BeamerError(f"{BEAMER_SLIDES_FILE} is missing.")
    presentation = beamer_presentation(workspace)
    for key in ("theme", "theme_fingerprint", "math", "size"):
        if context.get("presentation", {}).get(key) != presentation[key]:
            raise BeamerError("Beamer presentation context is stale; run prepare-slides again.")
    report = validate_beamer_document(workspace, path.read_text(encoding="utf-8"), context)
    fingerprint = sha256_file(path)
    context_path = resolve_artifact_path(workspace, SLIDES_CONTEXT_FILE)
    return {
        "artifact": BEAMER_SLIDES_FILE, "artifact_fingerprint": fingerprint,
        "slides_fingerprint": fingerprint, "report": report,
        "metadata": {
            "slides_body_fingerprint": fingerprint,
            "slides_context_fingerprint": sha256_file(context_path) if context_path.is_file() else None,
            **presentation, **report,
        },
    }


def smoke_compile_beamer(workspace: Path) -> JsonObject:
    """Compile in a temporary directory without shell escape or retained PDF."""
    directory = Path(workspace).resolve()
    validate_beamer_support(directory)
    _pages((directory / BEAMER_SLIDES_FILE).read_text(encoding="utf-8"))
    runner = shutil.which("latexmk")
    if runner is None or shutil.which("xelatex") is None:
        raise BeamerError("Beamer smoke compile requires latexmk and xelatex on PATH.")
    env = dict(os.environ)
    env["TEXINPUTS"] = str(directory / "beamer" / "themes") + "//:" + env.get("TEXINPUTS", "")
    with tempfile.TemporaryDirectory(prefix="mary-beamer-smoke-") as temporary:
        completed = subprocess.run(
            [runner, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
             "-no-shell-escape", "-outdir=" + temporary, BEAMER_SLIDES_FILE],
            cwd=directory, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=90, check=False,
        )
        output = Path(temporary) / "slides.pdf"
        if completed.returncode != 0 or not output.is_file():
            detail = " ".join((completed.stderr + "\n" + completed.stdout).split())[-1200:]
            raise BeamerError(f"Beamer smoke compile failed: {detail or 'no output'}")
        log_path = Path(temporary) / "slides.log"
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
        diagnostics = [line.strip() for line in log.splitlines() if re.search(
            r"Overfull|Missing character|LaTeX (?:Error|Warning)|Package .* Warning|Font .* Warning", line
        )]
        severe = [line for line in diagnostics if "Overfull" in line or "Missing character" in line]
        if severe:
            raise BeamerError("Beamer smoke compile has overflow or missing glyphs: " + "; ".join(severe[:5]))
        return {"status": "passed", "runner": "latexmk-xelatex", "warnings": diagnostics}
