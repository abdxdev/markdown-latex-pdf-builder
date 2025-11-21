"""Build PDF from a markdown file using template.tex template with JSON metadata.

Usage:
    python script.py path/to/templatexyz.md [--show] [--latex-log LEVEL]

Options:
    --show              Open the generated PDF file after successful build
    --latex-log LEVEL   LaTeX compilation output verbosity:
                        0 = silent (default, no LaTeX output shown)
                        1 = errors/warnings only
                        2 = verbose (show all LaTeX output)

LaTeX Output Control:
    Use --latex-log argument to control LaTeX compilation output visibility.
    Set SUPPRESS_HYBRID_WARNING to True/False to control hybrid warning suppression.

Steps:
1. Validate markdown path.
2. Ensure metadata.json exists (create default if missing).
3. Create build directory _build_<basename> next to markdown.
4. Copy template (template.tex), fonts/, uni-logo.pdf, markdown file, metadata.json into build dir.
5. Replace placeholders in template.tex: @@TITLE@@, @@SUBTITLE@@, @@SUBMITTEDTO@@, @@AUTHORS@@, @@DATE@@.
6. Run: lualatex --shell-escape -synctex=1 -interaction=nonstopmode -file-line-error template.tex
7. Move template.pdf to <basename>.pdf next to markdown.
"""

from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import re
import hashlib
import tempfile
import os

ROOT = Path(__file__).parent.resolve()

PLACEHOLDERS = [
    "@@TITLE@@",
    "@@SUBTITLE@@",
    "@@SUBMITTEDTO@@",
    "@@AUTHORS@@",
    "@@DATE@@",
    "@@INPUT_FILE@@",
    "@@TITLE_TEMPLATE@@",
    "@@ENABLE_CONTENT_PAGE@@",
    "@@TOC_DEPTH@@",
    "@@ENABLE_PAGE_CREDITS@@",
    "@@ENABLE_FOOTNOTES_AT_END@@",
    "@@ENABLE_FOOTNOTES_AS_COMMENTS@@",
    "@@ENABLE_THATS_ALL_PAGE@@",
    "@@UNIVERSITY@@",
    "@@DEPARTMENT@@",
]
IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".svg",
    ".eps",
    ".bmp",
    ".webp",
}


LATEX_LOG_SILENT = 0
LATEX_LOG_ERROR_ONLY = 1
LATEX_LOG_VERBOSE = 2


LATEX_LOG_LEVEL = LATEX_LOG_SILENT


class BuildError(Exception):
    pass


class Logger:
    """Colored console logging utility with single-line overwriting."""

    COLORS = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "WARNING": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}
    _last_length = 0

    @classmethod
    def _print(cls, msg: str, persist: bool = False):
        """Print message, optionally overwriting previous line."""
        padding = max(0, cls._last_length - len(msg))
        padded_msg = msg + " " * padding
        cls._last_length = len(msg)

        if persist:
            print(f"\r{padded_msg}")
            cls._last_length = 0
        else:
            print(f"\r{padded_msg}", end="", flush=True)

    @classmethod
    def info(cls, msg: str, persist: bool = False):
        cls._print(f"{cls.COLORS['INFO']}[INFO]{cls.COLORS['RESET']} {msg}", persist)

    @classmethod
    def success(cls, msg: str, persist: bool = True):
        cls._print(f"{cls.COLORS['SUCCESS']}[SUCCESS]{cls.COLORS['RESET']} {msg}", persist)

    @classmethod
    def warning(cls, msg: str, persist: bool = True):
        cls._print(f"{cls.COLORS['WARNING']}[WARNING]{cls.COLORS['RESET']} {msg}", persist)

    @classmethod
    def error(cls, msg: str, persist: bool = True):
        cls._print(f"{cls.COLORS['ERROR']}[ERROR]{cls.COLORS['RESET']} {msg}", persist)


def load_or_create_metadata(md_dir: Path, md_base: str) -> dict:
    def is_similar_json(s1: dict, s2: dict, except_keys: set) -> bool:
        """Check if two JSON objects have the same keys with matching data types."""
        s1_filtered = {k: v for k, v in s1.items() if k not in except_keys}
        s2_filtered = {k: v for k, v in s2.items() if k not in except_keys}

        if s1_filtered.keys() != s2_filtered.keys():
            return False
        for key in s1_filtered.keys():
            if type(s1_filtered[key]) != type(s2_filtered[key]):
                return False
        return True

    def load_json_file(path: Path) -> dict:
        """Safely load JSON from file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_current_date() -> str:
        """Get current date in the required format."""
        return datetime.now().strftime("%B %d, %Y")

    def write_metadata_with_date(data: dict, path: Path) -> None:
        """Write metadata JSON file with current date."""
        data["date"] = get_current_date()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def update_compatible_fields(target: dict, source: dict | None) -> None:
        """Update target dict with compatible fields from source."""
        if source is not None:
            target.update({k: v for k, v in source.items() if k in target and type(v) == type(target[k])})

    """Load metadata JSON file, creating default if missing."""
    meta_path = md_dir / f"{md_base}.json"
    json_file = load_json_file(ROOT / "default.json")

    if not meta_path.exists():

        parent_default_path = ROOT.parent / "default.json"
        if parent_default_path.exists():
            try:
                modified_default = load_json_file(parent_default_path)
            except json.JSONDecodeError:
                Logger.error(f"Invalid JSON in {parent_default_path}. Using default.")
                modified_default = None
            if is_similar_json(json_file, modified_default, except_keys={"date"}):
                json_file = modified_default
            else:
                update_compatible_fields(json_file, modified_default)
                with open(parent_default_path, "w", encoding="utf-8") as f:
                    json.dump(json_file, f, indent=2)

        write_metadata_with_date(json_file, meta_path)
        Logger.warning(f"Created {md_base}.json")
    else:
        try:
            json_file_in_dir = load_json_file(meta_path)
        except json.JSONDecodeError:
            Logger.error(f"Invalid JSON in {md_base}.json. Recreating from default.")
            write_metadata_with_date(json_file, meta_path)
            return json_file

        if not is_similar_json(json_file, json_file_in_dir, except_keys={"date"}):
            update_compatible_fields(json_file, json_file_in_dir)
            write_metadata_with_date(json_file, meta_path)
            Logger.warning(f"Updated {md_base}.json to match expected structure")

    return load_json_file(meta_path)


def build_authors(meta: dict) -> str:
    """Build LaTeX table rows for authors from metadata."""
    authors = meta.get("submittedby") or []
    if not isinstance(authors, list):
        return ""
    lines: list[str] = []
    for i, a in enumerate(authors):
        name = str(a.get("name", ""))
        roll = str(a.get("roll", ""))
        if i > 0:
            lines.append(r"\noalign{\vspace{0.3cm}}")
        lines.append(f"Name: & {name} \\\\")
        lines.append(f"Reg\\#: & {roll} \\\\")
    if not lines:
        return ""
    return "\n".join(lines)


def replace_placeholders(md_path: Path, tex_path: Path, meta: dict):
    """Replace template placeholders with metadata values."""
    content = tex_path.read_text(encoding="utf-8")
    authors_block = build_authors(meta)
    to_value = meta.get("submittedto", "")

    title_template = int(meta.get("titleTemplate", 1))
    if title_template < 0 or title_template > 3:
        title_template = 1
    title_template_cmd = f"\\renewcommand{{\\titleTemplate}}{{{title_template}}}"
    enable_content = bool(meta.get("enableContentPage"))
    content_page_toggle = "\\enablecontentpagetrue" if enable_content else "\\enablecontentpagefalse"

    toc_depth = int(meta.get("tocDepth", 3))
    if toc_depth < 1 or toc_depth > 6:
        toc_depth = 3
    toc_depth_cmd = f"\\setcounter{{tocdepth}}{{{toc_depth}}}"

    enable_credits = bool(meta.get("enablePageCredits", False))
    page_credits_toggle = "\\enablepagecreditstrue" if enable_credits else "\\enablepagecreditsfalse"

    enable_footnotes_at_end = bool(meta.get("moveFootnotesToEnd"))
    footnotes_at_end_toggle = "\\enablefootnotesatendtrue" if enable_footnotes_at_end else "\\enablefootnotesatendfalse"

    enable_footnotes_as_comments = bool(meta.get("footnotesAsComments"))
    footnotes_as_comments_toggle = "\\enablefootnotesascommentstrue" if enable_footnotes_as_comments else "\\enablefootnotesascommentsfalse"

    enable_thats_all = bool(meta.get("enableThatsAllPage"))
    thats_all_toggle = "\\enablethatsalltrue" if enable_thats_all else "\\enablethatsallfalse"

    mapping = {
        "@@TITLE@@": meta.get("title", ""),
        "@@SUBTITLE@@": meta.get("subtitle", ""),
        "@@SUBMITTEDTO@@": to_value,
        "@@AUTHORS@@": authors_block,
        "@@DATE@@": meta.get("date", ""),
        "@@INPUT_FILE@@": md_path.name,
        "@@TITLE_TEMPLATE@@": title_template_cmd,
        "@@ENABLE_CONTENT_PAGE@@": content_page_toggle,
        "@@TOC_DEPTH@@": toc_depth_cmd,
        "@@ENABLE_PAGE_CREDITS@@": page_credits_toggle,
        "@@ENABLE_FOOTNOTES_AT_END@@": footnotes_at_end_toggle,
        "@@ENABLE_FOOTNOTES_AS_COMMENTS@@": footnotes_as_comments_toggle,
        "@@ENABLE_THATS_ALL_PAGE@@": thats_all_toggle,
        "@@UNIVERSITY@@": meta.get("university", ""),
        "@@DEPARTMENT@@": meta.get("department", ""),
    }

    for ph in PLACEHOLDERS:
        val = mapping.get(ph, "")
        content = content.replace(ph, val)
    tex_path.write_text(content, encoding="utf-8")


def set_latex_log_level(level: int) -> None:
    """Set the LaTeX output log level.

    Args:
        level: Log level (LATEX_LOG_SILENT, LATEX_LOG_ERROR_ONLY, or LATEX_LOG_VERBOSE)
    """
    global LATEX_LOG_LEVEL
    if level in (LATEX_LOG_SILENT, LATEX_LOG_ERROR_ONLY, LATEX_LOG_VERBOSE):
        LATEX_LOG_LEVEL = level
    else:
        Logger.warning(f"Invalid log level {level}. Valid levels: 0 (SILENT), 1 (ERROR_ONLY), 2 (VERBOSE)")


def _filter_latex_output(output: str, returncode: int) -> str:
    """Filter LaTeX output based on suppression settings."""
    lines = output.split("\n")
    filtered_lines = []
    skip_next = False

    for line in lines:
        if skip_next and line.strip() and not line.strip().startswith("("):
            skip_next = False
        if not skip_next:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def _display_latex_output(filtered_output: str, returncode: int) -> None:
    """Display LaTeX output based on the current log level setting."""
    has_errors_or_warnings = returncode != 0 or "warning" in filtered_output.lower() or "error" in filtered_output.lower()

    if LATEX_LOG_LEVEL == LATEX_LOG_VERBOSE:
        if filtered_output.strip():
            print(filtered_output)
    elif LATEX_LOG_LEVEL == LATEX_LOG_ERROR_ONLY:
        if has_errors_or_warnings:
            print(filtered_output)


def run_lualatex(build_dir: Path):
    cmd = [
        "lualatex",
        "--shell-escape",
        "-synctex=1",
        "-interaction=nonstopmode",
        "-file-line-error",
        "template.tex",
    ]

    try:
        Logger.info(f"Compiling into PDF...", persist=False)
        proc = subprocess.run(
            cmd,
            cwd=build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError as e:
        raise BuildError("lualatex not found") from e
    final_returncode = proc.returncode
    output = proc.stdout
    filtered_output = _filter_latex_output(output, final_returncode)
    _display_latex_output(filtered_output, final_returncode)

    pdf_path = build_dir / "template.pdf"
    produced = pdf_path.exists()
    return final_returncode, produced, pdf_path


def find_markdown_images(md_path: Path) -> list[Path]:
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    candidates: set[str] = set()

    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        raw = m.group(1).strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        if " " in raw and not any(raw.startswith(q) for q in ('"', "'")):
            raw = raw.split(" ")[0]
        candidates.add(raw)

    for m in re.finditer(r'<img[^>]*?src=["\']([^"\']+)["\']', text, re.IGNORECASE):
        candidates.add(m.group(1).strip())

    for m in re.finditer(r"^\s*\[[^\]]+\]:\s*(\S+)", text, re.MULTILINE):
        target = m.group(1).strip()
        candidates.add(target)

    paths: list[Path] = []
    for c in candidates:
        if not c or "://" in c or c.startswith("data:") or c.startswith("#"):
            continue
        p = (md_path.parent / c).resolve()
        if p.exists() and p.suffix.lower() in IMAGE_EXTS:
            paths.append(p)
    return paths


def convert_markdown_footnotes_to_latex(content: str, use_comments: bool = False) -> str:
    content, protected_blocks = protect_code_and_math_blocks(content)
    footnote_defs = {}

    def extract_definition(match):
        label = match.group(1)
        content = match.group(2).strip()
        footnote_defs[label] = content
        return ""

    content = re.sub(r"^\[(\^[^\]]+)\]:\s*(.+?)(?=\n\s*\n|\n\s*\[|\Z)", extract_definition, content, flags=re.MULTILINE | re.DOTALL)

    if use_comments:
        def replace_inline(match):
            footnote_content = match.group(1)
            return f"\\todoComment{{{footnote_content}}}"

        content = re.sub(r"\^\[([^\]]+)\]", replace_inline, content)

        def replace_reference(match):
            label = match.group(1)
            if label in footnote_defs:
                footnote_content = footnote_defs[label]
                return f"\\todoComment{{{footnote_content}}}"
            return match.group(0)

        content = re.sub(r"\[(\^[^\]]+)\]", replace_reference, content)
    else:
        def replace_inline(match):
            footnote_content = match.group(1)
            return f"\\footnote{{{footnote_content}}}"

        content = re.sub(r"\^\[([^\]]+)\]", replace_inline, content)

        def replace_reference(match):
            label = match.group(1)
            if label in footnote_defs:
                footnote_content = footnote_defs[label]
                return f"\\footnote{{{footnote_content}}}"
            return match.group(0)

        content = re.sub(r"\[(\^[^\]]+)\]", replace_reference, content)

    content = restore_protected_blocks(content, protected_blocks)
    return content


def escape_signs(content: str, to_escape: list[str]) -> str:
    """Escape special characters while protecting code blocks and raw latex blocks."""
    protected_blocks = []

    def store_protected_block(match):
        protected_blocks.append(match.group(0))
        return f"__ESCAPE_PROTECTED_{len(protected_blocks)-1}__"

    content = re.sub(r"`+\{=latex\}.*?`+", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"````+.*?````+", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"```.*?```", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"`[^`\n]+`", store_protected_block, content)
    content = re.sub(r"\$\$.*?\$\$", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"\$[^$\n]+\$", store_protected_block, content)

    for sign in to_escape:
        content = content.replace(sign, f"\\{sign}")

    for i, block in enumerate(protected_blocks):
        content = content.replace(f"__ESCAPE_PROTECTED_{i}__", block)

    return content


def normalize_language_identifiers(content: str) -> str:
    lang_map = {
        "jsonc": "json",
        "tsx": "typescript",
        "jsx": "javascript",
        "vue": "html",
        "svelte": "html",
        "astro": "html",
    }

    for unsupported, supported in lang_map.items():
        content = re.sub(rf"```{unsupported}\b", f"```{supported}", content)

    return content


def process_code_highlights(content: str, build_dir: Path) -> str:
    def replace_highlight_attribute(match):
        header = match.group(1)
        code_content = match.group(2)
        highlight_match = re.search(r'\.highlightlines=([\d,-]+)', header)
        if highlight_match:
            lang_match = re.match(r'(\w+)', header)
            lang = lang_match.group(1) if lang_match else 'text'
            
            clean_code_content = code_content.strip()
            code_hash = hashlib.md5(clean_code_content.encode('utf-8')).hexdigest()
            code_filename = f"code_{code_hash}.txt"
            code_filepath = build_dir / code_filename
            
            code_filepath.write_text(clean_code_content, encoding='utf-8')

            line_spec = highlight_match.group(1)
            highlight_option = f"highlightlines={{{line_spec}}}"    

            return f"```{{=latex}}\n\\codeblock{{{code_filename}}}{{{lang}}}{{20pt}}{{true}}{{{highlight_option}}}\n```"
        else:
            return match.group(0)

    pattern = r"^```([^\n]*)\n(.*?)\n^```"
    processed_content = re.sub(pattern, replace_highlight_attribute, content, flags=re.DOTALL | re.MULTILINE)
    return processed_content


def find_mmdc_command():
    """Return path to mermaid-cli (mmdc) if available in PATH."""
    candidates = ["mmdc"]
    if os.name == "nt":
        candidates.insert(0, "mmdc.cmd")

    for cmd in candidates:
        found = shutil.which(cmd)
        if found:
            return found

    return None


def process_mermaid_diagrams(content: str, build_dir: Path) -> str:
    if "```mermaid" not in content:
        return content

    protected_blocks = []

    def store_non_mermaid_block(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_CODE_BLOCK_{len(protected_blocks)-1}__"

    content = re.sub(r"````+.*?````+", store_non_mermaid_block, content, flags=re.DOTALL)

    mmdc_cmd = find_mmdc_command()
    if mmdc_cmd is None:
        Logger.warning("Mermaid-cli not found. Install with: npm install -g @mermaid-js/mermaid-cli")

        def mermaid_to_text(match):
            mermaid_code = match.group(1).strip()
            return f"```text\n{mermaid_code}\n```"

        pattern = r"```mermaid\n(.*?)\n```"
        content = re.sub(pattern, mermaid_to_text, content, flags=re.DOTALL)

        for i, block in enumerate(protected_blocks):
            content = content.replace(f"__PROTECTED_CODE_BLOCK_{i}__", block)

        return content

    total_diagrams = len(re.findall(r"```mermaid\n(.*?)\n```", content, flags=re.DOTALL))
    if total_diagrams > 0:
        Logger.info(f"Processing {total_diagrams} Mermaid diagram(s)...", persist=False)

    diagram_counter = 0

    def replace_mermaid_block(match):
        nonlocal diagram_counter
        diagram_counter += 1

        mermaid_code = match.group(1).strip()
        diagram_hash = hashlib.md5(mermaid_code.encode("utf-8")).hexdigest()[:12]
        image_name = f"mermaid_{diagram_hash}.pdf"
        image_path = build_dir / image_name
        if not image_path.exists():
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as temp_file:
                    temp_file.write(mermaid_code)
                    temp_mmd_path = Path(temp_file.name)

                config_content = {"theme": "neutral", "themeVariables": {"background": "#ffffff", "primaryColor": "#ffffff"}}

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as config_file:
                    json.dump(config_content, config_file, indent=2)
                    temp_config_path = Path(config_file.name)

                cmd = [
                    mmdc_cmd,
                    "-i",
                    str(temp_mmd_path),
                    "-o",
                    str(image_path),
                    "-t",
                    "neutral",
                    "-b",
                    "white",
                    "-c",
                    str(temp_config_path),
                    "--pdfFit",
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, check=False)

                temp_mmd_path.unlink()
                temp_config_path.unlink()
                if result.returncode != 0 or not image_path.exists():
                    Logger.warning(f"Failed {diagram_counter}/{total_diagrams}")
                    return f"```text\n{mermaid_code}\n```"
                else:
                    Logger.info(f"Generated {diagram_counter}/{total_diagrams}", persist=False)

            except Exception:
                Logger.warning(f"Error {diagram_counter}/{total_diagrams}")
                return f"```text\n{mermaid_code}\n```"
        else:
            Logger.info(f"Cached {diagram_counter}/{total_diagrams}", persist=False)
        return f"![Mermaid Diagram]({image_name})"

    pattern = r"```mermaid\n(.*?)\n```"
    processed_content = re.sub(pattern, replace_mermaid_block, content, flags=re.DOTALL)

    for i, block in enumerate(protected_blocks):
        processed_content = processed_content.replace(f"__PROTECTED_CODE_BLOCK_{i}__", block)

    return processed_content


def process_keyboard_shortcuts(content: str) -> str:
    """Convert [[KEY]] and [[KEY1] + [KEY2]] syntax to LaTeX keyboard shortcut commands."""
    content, protected_blocks = protect_code_and_math_blocks(content)

    def convert_shortcut(match):
        captured = match.group(1)
        shortcut_content = "[" + captured + "]"
        parts = re.findall(r"\[([^\]]+)\]|(\s*\+\s*)", shortcut_content)

        latex_parts = []
        for key, separator in parts:
            if key:
                latex_parts.append(f"\\kbdkey{{{key}}}")
            elif separator:
                latex_parts.append("\\kbdplus")

        joined_latex = "".join(latex_parts)
        return f"\\kbdshortcut{{{joined_latex}}}"

    content = re.sub(r"\[\[(.*?)\]\]", convert_shortcut, content)

    content = restore_protected_blocks(content, protected_blocks)
    return content


def process_container_blocks(content: str) -> str:
    """Convert container-style blocks (alerts, alignment, boxes) to LaTeX environments with proper nesting support."""
    content, protected_blocks = protect_code_and_math_blocks(content)

    container_types = {
        "note": "mdalertnote",
        "tip": "mdalerttip",
        "important": "mdalertimportant",
        "warning": "mdalertwarning",
        "caution": "mdalertcaution",
        "center": "mdcenter",
        "right": "mdright",
        "box": "mdbox",
    }

    lines = content.split("\n")
    processed_lines = []
    i = 0
    alert_counter = 0

    while i < len(lines):
        line = lines[i]

        match = re.match(r"^(\s*):::\s*(note|tip|important|warning|caution|center|right|box)\s*$", line, re.IGNORECASE)
        if match:
            indent = match.group(1)
            alert_type = match.group(2).lower()
            latex_env = container_types[alert_type]
            alert_id = alert_counter
            alert_counter += 1

            alert_lines = []
            i += 1

            nesting_level = 1
            while i < len(lines) and nesting_level > 0:
                current_line = lines[i]

                if re.match(r"^(\s*):::\s*(note|tip|important|warning|caution|center|right|box)\s*$", current_line, re.IGNORECASE):
                    nesting_level += 1
                    if current_line.startswith(indent) and len(current_line) > len(indent):
                        clean_line = current_line[len(indent) :]
                    elif current_line.strip() == "":
                        clean_line = ""
                    else:
                        clean_line = current_line
                    alert_lines.append(clean_line)
                elif re.match(r"^(\s*):::\s*$", current_line):
                    nesting_level -= 1
                    if nesting_level > 0:
                        if current_line.startswith(indent) and len(current_line) > len(indent):
                            clean_line = current_line[len(indent) :]
                        elif current_line.strip() == "":
                            clean_line = ""
                        else:
                            clean_line = current_line
                        alert_lines.append(clean_line)
                else:
                    if current_line.startswith(indent) and len(current_line) > len(indent):
                        clean_line = current_line[len(indent) :]
                    elif current_line.strip() == "":
                        clean_line = ""
                    else:
                        clean_line = current_line
                    alert_lines.append(clean_line)

                i += 1

            while alert_lines and alert_lines[-1].strip() == "":
                alert_lines.pop()

            alert_content = "\n".join(alert_lines)
            processed_alert_content = process_container_blocks(alert_content)  # Recursive call
            processed_alert_lines = processed_alert_content.split("\n") if processed_alert_content else []

            processed_lines.append(f"{indent}__ALERT_BEGIN_{alert_id}_{latex_env}__")
            processed_lines.append("")

            for alert_line in processed_alert_lines:
                processed_lines.append(f"{indent}{alert_line}")

            processed_lines.append("")
            processed_lines.append(f"{indent}__ALERT_END_{alert_id}_{latex_env}__")
        else:
            processed_lines.append(line)
            i += 1

    result = "\n".join(processed_lines)
    result = restore_protected_blocks(result, protected_blocks)
    return result


def post_process_alerts(content: str) -> str:
    """Convert alert placeholders to raw LaTeX blocks after markdown processing."""
    content, protected_blocks = protect_code_and_math_blocks(content)

    def replace_begin(match):
        env_name = match.group(1)
        return f"\\begin{{{env_name}}}"

    def replace_end(match):
        env_name = match.group(1)
        return f"\\end{{{env_name}}}"

    content = re.sub(r"__ALERT_BEGIN_\d+_([a-z]+)__", replace_begin, content)
    content = re.sub(r"__ALERT_END_\d+_([a-z]+)__", replace_end, content)

    content = restore_protected_blocks(content, protected_blocks)
    return content


def protect_code_and_math_blocks(content: str) -> tuple[str, list[str]]:
    """Temporarily replace code blocks and math blocks with placeholders."""
    protected_blocks = []

    def store_protected_block(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_PLACEHOLDER_{len(protected_blocks)-1}__"

    content = re.sub(r"````+.*?````+", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"```.*?```", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"`[^`\n]*`", store_protected_block, content)
    content = re.sub(r"\$\$.*?\$\$", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"\$[^$\n]*\$", store_protected_block, content)

    return content, protected_blocks


def restore_protected_blocks(content: str, protected_blocks: list[str]) -> str:
    """Restore protected blocks from placeholders."""
    for i, protected_block in enumerate(protected_blocks):
        content = content.replace(f"__PROTECTED_PLACEHOLDER_{i}__", protected_block)
    return content


def process_emojis(content: str) -> str:
    """Convert emoji characters in content to LaTeX \\emoji{shortcode} using emoji-table.def mapping."""

    content, protected_blocks = protect_code_and_math_blocks(content)

    if not hasattr(process_emojis, "_emoji_map"):
        emoji_map = {}
        emoji_table_path = subprocess.check_output(["kpsewhich", "emoji-table.def"], text=True).strip()
        if emoji_table_path and os.path.exists(emoji_table_path):
            with open(emoji_table_path, encoding="utf-8") as f:
                data = f.read()
            pattern = r"\\__emoji_def:nnnnn\s*{([^}]*)}\s*{([^}]*)}"
            for m in re.findall(pattern, data):
                hex_seq, shortcode = m
                chars = []
                for cp in re.findall(r"\^+([0-9a-fA-F]+)", hex_seq):
                    chars.append(chr(int(cp, 16)))
                emoji = "".join(chars)
                emoji_map[emoji] = shortcode
        process_emojis._emoji_map = emoji_map
    else:
        emoji_map = process_emojis._emoji_map

    def replace_emoji(match):
        emoji = match.group(0)
        shortcode = emoji_map.get(emoji)
        if shortcode:
            return f"\\emoji{{{shortcode}}}"
        return emoji

    if emoji_map:
        emoji_regex = re.compile("|".join(re.escape(e) for e in sorted(emoji_map, key=len, reverse=True)))
        content = emoji_regex.sub(replace_emoji, content)

    content = restore_protected_blocks(content, protected_blocks)

    return content


def apply_markdown_formatting_math_safe(content: str) -> str:
    """Apply markdown formatting while protecting LaTeX math blocks and code blocks."""
    content, protected_blocks = protect_code_and_math_blocks(content)

    content = re.sub(r"==([^=\n]+)==", r"\\mdhighlight{\1}", content)
    content = re.sub(r"~~([^~]+)~~", r"\\mdstrikethrough{\1}", content)
    content = re.sub(r"\^([^^]+)\^", r"\\textsuperscript{\1}", content)
    content = re.sub(r"~([^~]+)~", r"\\textsubscript{\1}", content)
    content = re.sub(r":sc\[([^\]]+)\]", r"\\textsc{\1}", content)
    content = re.sub(r":u\[([^\]]+)\]", r"\\underline{\1}", content)

    content = restore_protected_blocks(content, protected_blocks)
    return content


def copy_image_assets(md_path: Path, build_dir: Path, root_md_dir: Path):
    images = find_markdown_images(md_path)
    if not images:
        return
    for img in images:
        try:
            rel = img.relative_to(root_md_dir)
        except ValueError:
            rel = Path(img.name)

        dest = build_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            try:
                shutil.copy(img, dest)
            except Exception as e:
                Logger.error(f"Failed to copy image {img}: {e}")


def process_executable_python_blocks(content: str, build_dir: Path) -> str:
    """Execute Python code blocks with property-based control.

    Syntax: ```python {.execute .show-code .show-output .no-cache}

    Properties:
    - .execute - Execute the code block
    - .show-code - Display the source code (default: hidden)
    - .show-output - Display execution output/plot (default: shown)
    - .hide-code - Explicitly hide the source code
    - .hide-output - Hide execution output/plot
    - .cache - Cache the execution output
    - .no-cache - Do not use cache and force re-execution
    """
    protected_blocks = []

    def store_protected_block(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_PYTHON_BLOCK_{len(protected_blocks)-1}__"

    content = re.sub(r"````+.*?````+", store_protected_block, content, flags=re.DOTALL)

    pattern = r"```python\s+\{([^}]+)\}\n(.*?)\n```"

    total_blocks = len(re.findall(pattern, content, flags=re.DOTALL))
    if total_blocks == 0:
        for i, block in enumerate(protected_blocks):
            content = content.replace(f"__PROTECTED_PYTHON_BLOCK_{i}__", block)
        return content
    Logger.info(f"Processing {total_blocks} executable Python block(s)...", persist=False)

    block_counter = 0

    def execute_python_block(match):
        nonlocal block_counter
        block_counter += 1

        properties_str = match.group(1)
        properties = set(prop.strip() for prop in properties_str.split())

        if ".execute" not in properties:
            return match.group(0)

        code = match.group(2)
        
        use_cache = ".no-cache" not in properties

        show_code = ".show-code" in properties and ".hide-code" not in properties
        show_output = ".hide-output" not in properties

        code_hash = hashlib.md5(code.encode("utf-8")).hexdigest()[:12]

        has_matplotlib = "matplotlib" in code or "plt." in code
        try:
            if has_matplotlib:
                plot_filename = f"python_plot_{code_hash}.pdf"
                plot_path = build_dir / plot_filename
                
                if use_cache and plot_path.exists():
                    Logger.info(f"Cached plot {block_counter}/{total_blocks}", persist=False)
                    parts = []
                    if show_code:
                        parts.append(f"```python\n{code}\n```")
                    if show_output:
                        parts.append(f"![Python Plot]({plot_filename})")
                    return "\n\n".join(parts) if parts else ""

                wrapped_code = code.replace("plt.show()", "")
                wrapped_code += f"\nimport matplotlib.pyplot as plt\nplt.savefig(r'{plot_path}', format='pdf', bbox_inches='tight')\nplt.close()"

                result = subprocess.run(["python", "-c", wrapped_code], capture_output=True, text=True, timeout=30, check=False)

                if result.returncode != 0:
                    Logger.warning(f"Failed to execute Python block {block_counter}/{total_blocks}")
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    parts = []
                    if show_code:
                        parts.append(f"```python\n{code}\n```")
                    parts.append(f"```output\nError executing code:\n{error_msg}\n```")
                    return "\n\n".join(parts)

                if plot_path.exists():
                    Logger.info(f"Generated plot {block_counter}/{total_blocks}", persist=False)
                    parts = []
                    if show_code:
                        parts.append(f"```python\n{code}\n```")
                    if show_output:
                        parts.append(f"![Python Plot]({plot_filename})")
                    return "\n\n".join(parts) if parts else ""
                else:
                    Logger.warning(f"Plot file not created {block_counter}/{total_blocks}")
                    parts = []
                    if show_code:
                        parts.append(f"```python\n{code}\n```")
                    if show_output:
                        parts.append(f"```output\nNo plot generated\n```")
                    return "\n\n".join(parts) if parts else ""
            else:
                output_filename = f"python_output_{code_hash}.txt"
                output_path = build_dir / output_filename
                
                if use_cache and output_path.exists():
                    Logger.info(f"Cached output {block_counter}/{total_blocks}", persist=False)
                    output = output_path.read_text(encoding="utf-8")
                    parts = []
                    if show_code:
                        parts.append(f"```python\n{code}\n```")
                    if show_output:
                        if output:
                            parts.append(f"```output\n{output}\n```")
                        else:
                            parts.append(f"```output\n(No output)\n```")
                    return "\n\n".join(parts) if parts else ""

                result = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=30, check=False)
                if result.returncode != 0:
                    Logger.warning(f"Failed to execute Python block {block_counter}/{total_blocks}")
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    if show_code:
                        return f"```python\n{code}\n```\n\n```output\nError executing code:\n{error_msg}\n```"
                    else:
                        return f"```output\nError executing code:\n{error_msg}\n```"

                output = result.stdout.strip()
                
                if use_cache:
                    output_path.write_text(output, encoding="utf-8")

                Logger.info(f"Executed Python block {block_counter}/{total_blocks}", persist=False)

                parts = []
                if show_code:
                    parts.append(f"```python\n{code}\n```")
                if show_output:
                    if output:
                        parts.append(f"```output\n{output}\n```")
                    else:
                        parts.append(f"```output\n(No output)\n```")
                return "\n\n".join(parts) if parts else ""
        except subprocess.TimeoutExpired:
            Logger.warning(f"Python block {block_counter}/{total_blocks} timed out")
            if show_code:
                return f"```python\n{code}\n```\n\n```output\nExecution timed out (30s limit)\n```"
            else:
                return f"```output\nExecution timed out (30s limit)\n```"
        except Exception as e:
            Logger.warning(f"Error executing Python block {block_counter}/{total_blocks}: {str(e)}")
            if show_code:
                return f"```python\n{code}\n```\n\n```output\nError: {str(e)}\n```"
            else:
                return f"```output\nError: {str(e)}\n```"

    processed_content = re.sub(pattern, execute_python_block, content, flags=re.DOTALL)

    for i, block in enumerate(protected_blocks):
        processed_content = processed_content.replace(f"__PROTECTED_PYTHON_BLOCK_{i}__", block)

    if total_blocks > 0:
        Logger.info(f"Completed {total_blocks} Python block(s)", persist=True)
    return processed_content


def substitute_variables(content: str, meta: dict) -> str:
    """Substitute variables from metadata into markdown content.

    Variables in markdown are in the format {{variable_name}}.
    Variables are defined in the metadata JSON under the "variables" key.

    Args:
        content: Markdown content
        meta: Metadata dictionary containing variables

    Returns:
        Content with variables substituted
    """
    variables = meta.get("variables", {})

    all_variables = re.findall(r"\{\{[^}]+\}\}", content)
    if not all_variables:
        return content

    Logger.info(f"Substituting {len(all_variables)} variable(s)...", persist=False)
    content, protected_blocks = protect_code_and_math_blocks(content)
    substituted_variables = set()
    for var_name, var_value in variables.items():
        pattern = r"\{\{\s*" + re.escape(var_name) + r"\s*\}\}"
        if re.search(pattern, content):
            escaped_value = str(var_value).replace("\\", "\\\\").replace("%", "\\%").replace("&", "\\&").replace("$", "\\$").replace("#", "\\#").replace("^", "\\^").replace("_", "\\_").replace("{", "\\{").replace("}", "\\}")
            content = re.sub(pattern, escaped_value, content)
            substituted_variables.add(var_name)
    unresolved_pattern = r"\{\{([^}]+)\}\}"
    unresolved_matches = re.findall(unresolved_pattern, content)
    if unresolved_matches:
        unique_unresolved = list(set(match.strip() for match in unresolved_matches))
        Logger.warning(f"Unresolved variables: {', '.join(unique_unresolved)}")

        def replace_unresolved_variable(match):
            var_name = match.group(1).strip()
            return f"[UNDEFINED: {var_name}]"

        content = re.sub(unresolved_pattern, replace_unresolved_variable, content)

    if len(all_variables) > 0:
        Logger.info(f"Resolved {len(substituted_variables)} unique variable(s)", persist=True)
    content = restore_protected_blocks(content, protected_blocks)
    return content


def open_pdf_file(pdf_path: Path):
    """Open PDF file using the default system application."""
    try:
        if os.name == "nt":
            os.startfile(str(pdf_path))
        elif os.name == "posix":
            if sys.platform == "darwin":
                subprocess.run(["open", str(pdf_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(pdf_path)], check=False)
        else:
            Logger.warning(f"Cannot open PDF on this platform: {os.name}")
            return False
        return True
    except Exception as e:
        Logger.warning(f"Failed to open PDF: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Build PDF from a markdown file using template.tex template with JSON metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
1. Validate markdown path.
2. Ensure metadata.json exists (create default if missing).
3. Create build directory _build_<basename> next to markdown.
4. Copy template (template.tex), fonts/, uni-logo.pdf, markdown file, metadata.json into build dir.
5. Replace placeholders in template.tex: @@TITLE@@, @@SUBTITLE@@, @@SUBMITTEDTO@@, @@AUTHORS@@, @@DATE@@.
6. Run: lualatex --shell-escape -synctex=1 -interaction=nonstopmode -file-line-error template.tex
7. Move template.pdf to <basename>.pdf next to markdown.
        """,
    )
    parser.add_argument("markdown_file", help="Path to the markdown file to process")
    parser.add_argument("--show", action="store_true", help="Open the generated PDF file after successful build")
    parser.add_argument("--latex-log", "-l", type=int, choices=[0, 1, 2], default=0, help="LaTeX compilation output verbosity: 0=silent (default), 1=errors/warnings only, 2=verbose")

    parser.add_argument("--titleTemplate", type=int, choices=[0, 1, 2, 3])
    parser.add_argument("--enableContentPage", type=str, choices=["true", "false"])
    parser.add_argument("--tocDepth", type=int, choices=[1, 2, 3, 4, 5, 6])
    parser.add_argument("--enablePageCredits", type=str, choices=["true", "false"])
    parser.add_argument("--moveFootnotesToEnd", type=str, choices=["true", "false"])
    parser.add_argument("--footnotesAsComments", type=str, choices=["true", "false"])
    parser.add_argument("--enableThatsAllPage", type=str, choices=["true", "false"])

    args = parser.parse_args()

    def apply_cli_overrides(meta, args):
        """Override metadata fields only if user provided CLI args."""
        if args.titleTemplate is not None:
            meta["titleTemplate"] = args.titleTemplate

        if args.enableContentPage is not None:
            meta["enableContentPage"] = args.enableContentPage.lower() == "true"

        if args.tocDepth is not None:
            meta["tocDepth"] = args.tocDepth

        if args.enablePageCredits is not None:
            meta["enablePageCredits"] = args.enablePageCredits.lower() == "true"

        if args.moveFootnotesToEnd is not None:
            meta["moveFootnotesToEnd"] = args.moveFootnotesToEnd.lower() == "true"

        if args.footnotesAsComments is not None:
            meta["footnotesAsComments"] = args.footnotesAsComments.lower() == "true"

        if args.enableThatsAllPage is not None:
            meta["enableThatsAllPage"] = args.enableThatsAllPage.lower() == "true"

        return meta


    global LATEX_LOG_LEVEL
    LATEX_LOG_LEVEL = args.latex_log

    md_path = Path(args.markdown_file).expanduser().resolve()
    if not md_path.exists():
        Logger.error(f"Markdown file not found: {md_path}")
        sys.exit(1)
    if md_path.suffix.lower() != ".md":
        Logger.error("Provided file must have .md extension.")
        sys.exit(1)

    md_dir = md_path.parent
    md_base = md_path.stem

    meta = load_or_create_metadata(md_dir, md_base)
    meta = apply_cli_overrides(meta, args)

    template_tex = ROOT / "template.tex"
    if not template_tex.exists():
        Logger.error(f"Template template.tex not found at {template_tex}")
        sys.exit(1)
    logo = ROOT / "uni-logo.pdf"
    credit_sign = ROOT / "credit-sign.pdf"
    fonts_dir = ROOT / "fonts"
    build_dir = md_dir / f"_build_{md_base}"
    if not build_dir.exists():
        build_dir.mkdir()

    for stale in [build_dir / "template.tex", build_dir / md_path.name, build_dir / f"{md_base}.json"]:
        if stale.exists():
            try:
                stale.unlink()
            except Exception:
                pass
    shutil.copy(template_tex, build_dir / "template.tex")
    md_content = md_path.read_text(encoding="utf-8", errors="ignore")
    md_content = substitute_variables(md_content, meta)
    md_content = process_code_highlights(md_content, build_dir)

    if meta.get("footnotesAsComments"):
        # This function will be modified to handle todo comments directly
        md_content = convert_markdown_footnotes_to_latex(md_content, use_comments=True)
    else:
        md_content = convert_markdown_footnotes_to_latex(md_content)

    md_content = process_mermaid_diagrams(md_content, build_dir)
    md_content = normalize_language_identifiers(md_content)
    md_content = process_keyboard_shortcuts(md_content)
    md_content = process_container_blocks(md_content)
    md_content = apply_markdown_formatting_math_safe(md_content)
    md_content = process_emojis(md_content)
    md_content = escape_signs(md_content, ["%"])
    md_content = post_process_alerts(md_content)
    md_content = process_executable_python_blocks(md_content, build_dir)

    (build_dir / md_path.name).write_text(md_content, encoding="utf-8")
    shutil.copy(md_dir / f"{md_base}.json", build_dir / f"{md_base}.json")
    if logo.exists():
        shutil.copy(logo, build_dir / logo.name)
    if credit_sign.exists():
        shutil.copy(credit_sign, build_dir / credit_sign.name)
    if fonts_dir.exists() and not (build_dir / "fonts").exists():
        shutil.copytree(fonts_dir, build_dir / "fonts")

    copy_image_assets(md_path, build_dir, md_dir)
    replace_placeholders(md_path, build_dir / "template.tex", meta)
    try:
        rc, produced, pdf_path = run_lualatex(build_dir)

        if meta.get("enableContentPage") or meta.get("footnotesAsComments"):
            Logger.info("Rerunning LuaLaTeX for table of contents/footnotes...", persist=True)
            rc, produced, pdf_path = run_lualatex(build_dir)
    except BuildError as e:
        Logger.error(str(e))
        sys.exit(1)

    target_pdf = md_dir / f"{md_base}.pdf"
    if produced:
        if target_pdf.exists():
            try:
                target_pdf.unlink()
            except Exception:
                pass
        shutil.move(str(pdf_path), target_pdf)
        if rc != 0:
            Logger.warning(f"Exit {rc}, PDF: {target_pdf}")
        else:
            Logger.success(f"PDF: {target_pdf}")

        if args.show:
            Logger.info("Opening PDF file...")
            if open_pdf_file(target_pdf):
                Logger.success("PDF opened successfully")
            else:
                Logger.warning("Could not open PDF automatically")

        sys.exit(0)
    else:
        Logger.error(f"LuaLaTeX failed (exit code {rc}) and no PDF produced.")
        sys.exit(1)


if __name__ == "__main__":
    main()
