"""Build PDF from a markdown file using template.tex template with JSON metadata.

Usage:
    python script.py path/to/templatexyz.md

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

PLACEHOLDERS = ["@@TITLE@@", "@@SUBTITLE@@", "@@SUBMITTEDTO@@", "@@AUTHORS@@", "@@DATE@@", "@@INPUT_FILE@@", "@@TITLE_TEMPLATE@@", "@@ENABLE_CONTENT_PAGE@@", "@@ENABLE_PAGE_CREDITS@@", "@@ENABLE_FOOTNOTES_AT_END@@", "@@ENABLE_THATS_ALL_PAGE@@", "@@UNIVERSITY@@", "@@DEPARTMENT@@"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps", ".bmp", ".webp"}
SUPPRESS_HYBRID_WARNING = True


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


def log(msg: str):
    Logger.info(msg)


def err(msg: str):
    Logger.error(msg)


def load_or_create_metadata(script_root: Path, md_dir: Path, md_base: str) -> dict:
    """Load metadata JSON file, creating default if missing."""
    meta_path = md_dir / f"{md_base}.json"
    if not meta_path.exists():
        default = json.load(open(script_root / "default.json"))
        default["date"] = datetime.now().strftime("%B %d, %Y")
        meta_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        Logger.warning(f"Created {md_base}.json")

    try:
        raw = meta_path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data
    except Exception as e:
        raise BuildError(f"Failed to parse {md_base}.json: {e}") from e


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

    enable_credits = bool(meta.get("enablePageCredits", False))
    last_page_credits_toggle = "\\enablelastpagecreditstrue" if enable_credits else "\\enablelastpagecreditsfalse"

    enable_footnotes_at_end = bool(meta.get("moveFootnotesToEnd"))
    footnotes_at_end_toggle = "\\enablefootnotesatendtrue" if enable_footnotes_at_end else "\\enablefootnotesatendfalse"
    enable_thats_all = bool(meta.get("enableThatsAllPage"))
    thats_all_toggle = "\\enablethatsalltrue" if enable_thats_all else "\\enablethatsallfalse"

    mapping = {
        "@@TITLE@@": meta.get("title", ""),
        "@@SUBTITLE@@": meta.get("subtitle", ""),
        "@@SUBMITTEDTO@@": to_value,
        "@@AUTHORS@@": authors_block,
        "@@DATE@@": meta.get("date", ""),        "@@INPUT_FILE@@": md_path.name,
        "@@TITLE_TEMPLATE@@": title_template_cmd,
        "@@ENABLE_CONTENT_PAGE@@": content_page_toggle,
        "@@ENABLE_PAGE_CREDITS@@": last_page_credits_toggle,
        "@@ENABLE_FOOTNOTES_AT_END@@": footnotes_at_end_toggle,
        "@@ENABLE_THATS_ALL_PAGE@@": thats_all_toggle,
        "@@UNIVERSITY@@": meta.get("university", ""),
        "@@DEPARTMENT@@": meta.get("department", ""),
    }

    for ph in PLACEHOLDERS:
        val = mapping.get(ph, "")
        content = content.replace(ph, val)
    tex_path.write_text(content, encoding="utf-8")


def run_lualatex(build_dir: Path):
    cmd = [
        "lualatex",
        "--shell-escape",
        "-synctex=1",
        "-interaction=nonstopmode",
        "-file-line-error",
        "template.tex",
    ]

    Logger.info("Compiling LaTeX...")

    for pass_num in range(1, 3):
        try:
            Logger.info(f"Pass {pass_num}/2...", persist=False)
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
        if pass_num == 2:
            final_returncode = proc.returncode
            output = proc.stdout

            lines = output.split("\n")
            filtered_lines = []
            skip_next = False

            for i, line in enumerate(lines):
                if "Package markdown Warning: The `hybrid` option has been soft-deprecated." in line:
                    skip_next = True
                    continue
                if skip_next and line.strip() and not line.strip().startswith("("):
                    skip_next = False
                if not skip_next:
                    filtered_lines.append(line)

            filtered_output = "\n".join(filtered_lines)

            if final_returncode != 0 or "warning" in filtered_output.lower() or "error" in filtered_output.lower():
                print(filtered_output)

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


def convert_markdown_footnotes_to_latex(content: str) -> str:
    content, protected_blocks = protect_code_and_math_blocks(content)
    footnote_defs = {}

    def extract_definition(match):
        label = match.group(1)
        content = match.group(2).strip()
        footnote_defs[label] = content
        return ""

    content = re.sub(r"^\[(\^[^\]]+)\]:\s*(.+?)(?=\n\s*\n|\n\s*\[|\Z)", extract_definition, content, flags=re.MULTILINE | re.DOTALL)

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
        parts = re.findall(r"\[([^\]]+)\]|(\s*[\+\-]\s*)", shortcut_content)

        latex_parts = []
        for key, separator in parts:
            if key:
                latex_parts.append(f"\\kbdkey{{{key}}}")
            elif separator:
                sep = separator.strip()
                if sep == "+":
                    latex_parts.append("\\kbdplus")
                elif sep == "-":
                    latex_parts.append("\\kbdminus")
                else:
                    latex_parts.append(separator)

        joined_latex = "".join(latex_parts)
        return f"\\kbdshortcut{{{joined_latex}}}"

    content = re.sub(r"\[\[(.*?)\]\]", convert_shortcut, content)

    content = restore_protected_blocks(content, protected_blocks)
    return content


def process_github_alerts(content: str) -> str:
    """Convert GitHub-style alert blocks to LaTeX alert environments."""
    alert_types = {
        "NOTE": "mdalertnote",
        "TIP": "mdalerttip",
        "IMPORTANT": "mdalertimportant",
        "WARNING": "mdalertwarning",
        "CAUTION": "mdalertcaution",
    }

    alert_counter = [0]

    for alert_type, latex_env in alert_types.items():
        pattern = rf"^>\s*\[!{alert_type}\]\s*\n((?:>.*\n)*?)(?=\n[^>\n]|\n*$)"

        def replace_alert(match):
            content_lines = match.group(1)
            alert_id = alert_counter[0]
            alert_counter[0] += 1

            lines = content_lines.split("\n")
            cleaned_lines = []
            for line in lines:
                if line.startswith("> "):
                    cleaned_lines.append(line[2:])
                elif line.startswith(">"):
                    cleaned_lines.append(line[1:])
                else:
                    cleaned_lines.append(line)
            cleaned_content = "\n".join(cleaned_lines)

            return f"__ALERT_BEGIN_{alert_id}_{latex_env}__\n\n{cleaned_content}\n\n__ALERT_END_{alert_id}_{latex_env}__\n"

        content = re.sub(pattern, replace_alert, content, flags=re.MULTILINE)

    return content


def post_process_alerts(content: str) -> str:
    """Convert alert placeholders to raw LaTeX blocks after markdown processing."""

    def replace_begin(match):
        env_name = match.group(1)
        return f"\\begin{{{env_name}}}"

    def replace_end(match):
        env_name = match.group(1)
        return f"\\end{{{env_name}}}"

    content = re.sub(r"__ALERT_BEGIN_\d+_([a-z]+)__", replace_begin, content)
    content = re.sub(r"__ALERT_END_\d+_([a-z]+)__", replace_end, content)

    return content


def protect_code_and_math_blocks(content: str) -> tuple[str, list[str]]:
    """Temporarily replace code blocks and math blocks with placeholders."""
    protected_blocks = []

    def store_protected_block(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_PLACEHOLDER_{len(protected_blocks)-1}__"

    content = re.sub(r"````+.*?````+", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"```.*?```", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"`[^`\n]+`", store_protected_block, content)
    content = re.sub(r"\$\$.*?\$\$", store_protected_block, content, flags=re.DOTALL)
    content = re.sub(r"\$[^$\n]+\$", store_protected_block, content)

    return content, protected_blocks


def restore_protected_blocks(content: str, protected_blocks: list[str]) -> str:
    """Restore protected blocks from placeholders."""
    for i, protected_block in enumerate(protected_blocks):
        content = content.replace(f"__PROTECTED_PLACEHOLDER_{i}__", protected_block)
    return content


def apply_markdown_formatting_math_safe(content: str) -> str:
    """Apply markdown formatting while protecting LaTeX math blocks and code blocks."""
    content, protected_blocks = protect_code_and_math_blocks(content)

    content = re.sub(r"==([^=\n]+)==", r"\\mdhighlight{\1}", content)
    content = re.sub(r"~~([^~]+)~~", r"\\mdstrikethrough{\1}", content)
    content = re.sub(r"\^([^^]+)\^", r"\\textsuperscript{\1}", content)
    content = re.sub(r"~([^~]+)~", r"\\textsubscript{\1}", content)

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
                err(f"Failed to copy image {img}: {e}")


def process_executable_python_blocks(content: str, build_dir: Path) -> str:
    """Execute Python code blocks with property-based control.

    Syntax: ```python {.execute .show-code .show-output}

    Properties:
    - .execute - Execute the code block
    - .show-code - Display the source code (default: hidden)
    - .show-output - Display execution output/plot (default: shown)
    - .hide-code - Explicitly hide the source code
    - .hide-output - Hide execution output/plot
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

        show_code = ".show-code" in properties and ".hide-code" not in properties
        show_output = ".hide-output" not in properties

        code_hash = hashlib.md5(code.encode("utf-8")).hexdigest()[:12]

        has_matplotlib = "matplotlib" in code or "plt." in code
        try:
            if has_matplotlib:
                plot_filename = f"python_plot_{code_hash}.pdf"
                plot_path = build_dir / plot_filename

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
                result = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=30, check=False)
                if result.returncode != 0:
                    Logger.warning(f"Failed to execute Python block {block_counter}/{total_blocks}")
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    if show_code:
                        return f"```python\n{code}\n```\n\n```output\nError executing code:\n{error_msg}\n```"
                    else:
                        return f"```output\nError executing code:\n{error_msg}\n```"

                output = result.stdout.strip()
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


def main():
    if len(sys.argv) != 2:
        err("Usage: python script.py path/to/file.md")
        sys.exit(1)
    md_path = Path(sys.argv[1]).expanduser().resolve()
    if not md_path.exists():
        err(f"Markdown file not found: {md_path}")
        sys.exit(1)
    if md_path.suffix.lower() != ".md":
        err("Provided file must have .md extension.")
        sys.exit(1)

    md_dir = md_path.parent
    md_base = md_path.stem
    script_root = Path(__file__).parent.resolve()

    meta = load_or_create_metadata(script_root, md_dir, md_base)

    template_tex = script_root / "template.tex"
    if not template_tex.exists():
        err(f"Template template.tex not found at {template_tex}")
        sys.exit(1)
    logo = script_root / "uni-logo.pdf"
    credit_sign = script_root / "credit-sign.pdf"
    fonts_dir = script_root / "fonts"
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
    md_content = convert_markdown_footnotes_to_latex(md_content)
    md_content = process_mermaid_diagrams(md_content, build_dir)
    md_content = normalize_language_identifiers(md_content)
    md_content = process_keyboard_shortcuts(md_content)
    md_content = process_github_alerts(md_content)
    md_content = apply_markdown_formatting_math_safe(md_content)
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
    except BuildError as e:
        err(str(e))
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
        sys.exit(0)
    else:
        err(f"LuaLaTeX failed (exit code {rc}) and no PDF produced.")
        sys.exit(1)


if __name__ == "__main__":
    main()
