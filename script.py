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

# Template placeholders that get replaced with metadata values
PLACEHOLDERS = ["@@TITLE@@", "@@SUBTITLE@@", "@@SUBMITTEDTO@@", "@@AUTHORS@@", "@@DATE@@", "@@INPUT_FILE@@", "@@ENABLE_TITLE_PAGE@@", "@@ENABLE_CONTENT_PAGE@@", "@@ENABLE_LAST_PAGE_CREDITS@@", "@@ENABLE_FOOTNOTES_AT_END@@", "@@ENABLE_THATS_ALL_PAGE@@", "@@UNIVERSITY@@", "@@DEPARTMENT@@"]

# Supported image file extensions for asset copying
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps", ".bmp", ".webp"}

# Flag to suppress markdown hybrid deprecation warning when it's the only output
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
        # Pad message to clear previous longer messages
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

    enable_title = bool(meta.get("enableTitlePage"))
    first_page_toggle = "\\enabletitlepagetrue" if enable_title else "\\enabletitlepagefalse"

    enable_content = bool(meta.get("enableContentPage"))
    content_page_toggle = "\\enablecontentpagetrue" if enable_content else "\\enablecontentpagefalse"

    enable_credits = bool(meta.get("enableLastPageCredits", False))
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
        "@@DATE@@": meta.get("date", ""),
        "@@INPUT_FILE@@": md_path.name,
        "@@ENABLE_TITLE_PAGE@@": first_page_toggle,
        "@@ENABLE_CONTENT_PAGE@@": content_page_toggle,
        "@@ENABLE_LAST_PAGE_CREDITS@@": last_page_credits_toggle,
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

            # Filter out the hybrid deprecation warning if it's the only warning
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

    return content


def escape_signs(content: str, to_escape: list[str]) -> str:
    for sign in to_escape:
        content = content.replace(sign, f"\\{sign}")
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
    """Return path to mermaid-cli (mmdc) if available in PATH.

    Simplified to rely on PATH discovery for cross-platform support.
    """
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

    mmdc_cmd = find_mmdc_command()
    if mmdc_cmd is None:
        Logger.warning("Mermaid-cli not found. Install with: npm install -g @mermaid-js/mermaid-cli")

        def mermaid_to_text(match):
            mermaid_code = match.group(1).strip()
            return f"```text\n{mermaid_code}\n```"

        pattern = r"```mermaid\n(.*?)\n```"
        return re.sub(pattern, mermaid_to_text, content, flags=re.DOTALL)
    # Count total mermaid diagrams for progress tracking
    total_diagrams = len(re.findall(r"```mermaid\n(.*?)\n```", content, flags=re.DOTALL))
    if total_diagrams > 0:
        Logger.info(f"Processing {total_diagrams} Mermaid diagram(s)...", persist=False)

    diagram_counter = 0

    def replace_mermaid_block(match):
        nonlocal diagram_counter
        diagram_counter += 1
        mermaid_code = match.group(1).strip()
        # Create a hash of the mermaid code for caching
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

    return processed_content


def process_keyboard_shortcuts(content: str) -> str:
    """Convert [[KEY]] and [[KEY1] + [KEY2]] syntax to LaTeX keyboard shortcut commands."""
    
    def convert_shortcut(match):
        captured = match.group(1)
        shortcut_content = '[' + captured + ']'
        parts = re.findall(r'\[([^\]]+)\]|(\s*[\+\-]\s*)', shortcut_content)
        
        latex_parts = []
        for key, separator in parts:
            if key:
                latex_parts.append(f"\\kbdkey{{{key}}}")
            elif separator:
                sep = separator.strip()
                if sep == '+':
                    latex_parts.append("\\kbdplus")
                elif sep == '-':
                    latex_parts.append("\\kbdminus")
                else:
                    latex_parts.append(separator)
        
        joined_latex = ''.join(latex_parts)
        return f"\\kbdshortcut{{{joined_latex}}}"

    content = re.sub(r'\[\[(.*?)\]\]', convert_shortcut, content)
    
    return content


def process_github_alerts(content: str) -> str:
    """Convert GitHub-style alert blocks to LaTeX alert environments.
    
    Converts:
    > [!NOTE]
    > Content here
    
    To:
    \\begin{mdalertnote}
    Content here
    \\end{mdalertnote}
    """
    alert_types = {
        'NOTE': 'mdalertnote',
        'TIP': 'mdalerttip',
        'IMPORTANT': 'mdalertimportant',
        'WARNING': 'mdalertwarning',
        'CAUTION': 'mdalertcaution',
    }
    
    # Pattern to match alert blocks:
    # > [!TYPE]
    # > content lines...
    # > more content...
    # (until we hit a line that doesn't start with >)
    
    for alert_type, latex_env in alert_types.items():
        # Match the alert header and all subsequent lines starting with >
        pattern = rf'^>\s*\[!{alert_type}\]\s*\n((?:>.*\n?)*)'
        
        def replace_alert(match):
            content_lines = match.group(1)
            # Remove the leading > and optional space from each line
            processed_lines = []
            for line in content_lines.split('\n'):
                stripped = line.lstrip('>')
                if stripped.startswith(' '):
                    stripped = stripped[1:]
                if stripped:  # Only add non-empty lines
                    processed_lines.append(stripped)
            
            alert_content = '\n'.join(processed_lines).strip()
            
            return f'\\begin{{{latex_env}}}\n{alert_content}\n\\end{{{latex_env}}}\n'
        
        content = re.sub(pattern, replace_alert, content, flags=re.MULTILINE)
    
    return content


def apply_markdown_formatting_math_safe(content: str) -> str:
    """Apply markdown formatting while protecting LaTeX math blocks from modification."""
    # Find and temporarily replace math blocks
    math_blocks = []

    def store_math_block(match):
        math_blocks.append(match.group(0))
        return f"__MATH_PLACEHOLDER_{len(math_blocks)-1}__"

    # Protect display math blocks ($$...$$) first - they can span multiple lines
    content = re.sub(r"\$\$.*?\$\$", store_math_block, content, flags=re.DOTALL)

    # Protect inline math blocks ($...$) - single line only
    content = re.sub(r"\$[^$\n]+\$", store_math_block, content)

    # Now safely apply formatting to non-math content
    content = re.sub(r"==([^=\n]+)==", r"\\mdhighlight{\1}", content)
    content = re.sub(r"~~([^~]+)~~", r"\\mdstrikethrough{\1}", content)
    content = re.sub(r"\^([^^]+)\^", r"\\textsuperscript{\1}", content)
    content = re.sub(r"~([^~]+)~", r"\\textsubscript{\1}", content)

    # Restore protected math blocks
    for i, math_block in enumerate(math_blocks):
        content = content.replace(f"__MATH_PLACEHOLDER_{i}__", math_block)

    return content


def copy_image_assets(md_path: Path, build_dir: Path, root_md_dir: Path):
    images = find_markdown_images(md_path)
    if not images:
        return
    for img in images:
        try:
            # Recreate relative structure from markdown dir
            rel = img.relative_to(root_md_dir)
        except ValueError:
            # Image outside markdown dir; flatten
            rel = Path(img.name)

        dest = build_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            try:
                shutil.copy(img, dest)
            except Exception as e:
                err(f"Failed to copy image {img}: {e}")


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
