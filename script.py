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

PLACEHOLDERS = ["@@TITLE@@", "@@SUBTITLE@@", "@@SUBMITTEDTO@@", "@@AUTHORS@@", "@@DATE@@", "@@INPUT_FILE@@", "@@ENABLE_TITLE_PAGE@@", "@@ENABLE_CONTENT_PAGE@@", "@@ENABLE_LAST_PAGE_CREDITS@@", "@@ENABLE_FOOTNOTES_AT_END@@", "@@ENABLE_THATS_ALL_PAGE@@", "@@UNIVERSITY@@", "@@DEPARTMENT@@"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps", ".bmp", ".webp"}


class BuildError(Exception):
    pass


def log(msg: str):
    print(f"[INFO] {msg}")


def err(msg: str):
    print(f"[ERROR] {msg}")


def load_or_create_metadata(script_root: Path, md_dir: Path, md_base: str) -> dict:
    meta_path = md_dir / f"{md_base}.json"
    if not meta_path.exists():
        log(f"{md_base}.json not found. Creating default.")
        default = json.load(open(script_root / "default.json"))
        default["date"] = datetime.now().strftime("%B %d, %Y")
        meta_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
    else:
        log(f"{md_base}.json exists. Using existing file.")
    try:
        raw = meta_path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data
    except Exception as e:
        raise BuildError(f"Failed to parse {md_base}.json: {e}") from e


def build_authors(meta: dict) -> str:
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
    content = tex_path.read_text(encoding="utf-8")
    authors_block = build_authors(meta)
    
    # Get all values directly from meta without any hardcoded defaults
    # If a key is missing, it should have been set in default.json when the file was created
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
    log("Injected metadata into template.tex")


def run_lualatex(build_dir: Path):
    cmd = [
        "lualatex",
        "--shell-escape",
        "-synctex=1",
        "-interaction=nonstopmode",
        "-file-line-error",
        "template.tex",
    ]

    # Run LuaLaTeX twice for minted package to work properly
    # First pass: Extract code snippets and generate syntax-highlighted files
    # Second pass: Include the generated highlighted code in the PDF
    for pass_num in range(1, 3):
        log(f"Running LuaLaTeX compile (pass {pass_num}/2)...")
        try:
            proc = subprocess.run(
                cmd,
                cwd=build_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                check=False,
            )
        except FileNotFoundError as e:  # noqa: BLE001
            raise BuildError("lualatex not found in PATH.") from e

        # Only print output on second pass to reduce clutter
        if pass_num == 2:
            print(proc.stdout)

        # Store the return code from the final pass
        if pass_num == 2:
            final_returncode = proc.returncode

    pdf_path = build_dir / "template.pdf"
    produced = pdf_path.exists()
    return final_returncode, produced, pdf_path


def find_markdown_images(md_path: Path) -> list[Path]:
    """Extract local image paths from markdown (basic patterns: ![](), HTML <img src>, and reference style)."""
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    candidates: set[str] = set()
    # Inline image syntax ![alt](path "title")
    for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
        raw = m.group(1).strip()
        # Remove optional title after space unless path is quoted
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        # Separate title part
        if " " in raw and not any(raw.startswith(q) for q in ('"', "'")):
            raw = raw.split(" ")[0]
        candidates.add(raw)
    # HTML <img src="...">
    for m in re.finditer(r'<img[^>]*?src=["\']([^"\']+)["\']', text, re.IGNORECASE):
        candidates.add(m.group(1).strip())
    # Reference style: [id]: path  (only treat if extension looks like image)
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
    """Convert markdown footnotes to LaTeX \\footnote{} commands.

    Handles both reference-style [^label] and inline ^[content] footnotes.
    """
    # Step 1: Extract all footnote definitions [^label]: content
    footnote_defs = {}

    def extract_definition(match):
        label = match.group(1)
        # Capture everything until the next blank line or another footnote definition
        content = match.group(2).strip()
        footnote_defs[label] = content
        return ""  # Remove the definition from text

    # Match [^label]: content (can span multiple lines until next blank line)
    content = re.sub(r"^\[(\^[^\]]+)\]:\s*(.+?)(?=\n\s*\n|\n\s*\[|\Z)", extract_definition, content, flags=re.MULTILINE | re.DOTALL)

    # Step 2: Replace inline footnotes ^[content] with \footnote{content}
    def replace_inline(match):
        footnote_content = match.group(1)
        return f"\\footnote{{{footnote_content}}}"

    content = re.sub(r"\^\[([^\]]+)\]", replace_inline, content)

    # Step 3: Replace reference-style footnotes [^label] with \footnote{content}
    def replace_reference(match):
        label = match.group(1)
        if label in footnote_defs:
            footnote_content = footnote_defs[label]
            return f"\\footnote{{{footnote_content}}}"
        return match.group(0)  # Keep as-is if definition not found

    content = re.sub(r"\[(\^[^\]]+)\]", replace_reference, content)

    return content


def escape_percent(content: str):
    return content.replace("%", "\\%")


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
                log(f"Copied image: {rel}")
            except Exception as e:  # noqa: BLE001
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
    fonts_dir = script_root / "fonts"

    build_dir = md_dir / f"_build_{md_base}"
    if not build_dir.exists():
        build_dir.mkdir()
        log(f"Created build directory: {build_dir}")
    else:
        log(f"Using existing build directory (cache): {build_dir}")  # Overwrite core files each run to keep cache valid
    for stale in [build_dir / "template.tex", build_dir / md_path.name, build_dir / f"{md_base}.json"]:
        if stale.exists():
            try:
                stale.unlink()
            except Exception:
                pass  # Copy resources (do not remove entire cache like fonts/ or other LaTeX aux files)
    shutil.copy(template_tex, build_dir / "template.tex")

    # Preprocess markdown: convert markdown footnotes to LaTeX footnotes
    md_content = md_path.read_text(encoding="utf-8", errors="ignore")
    md_content = convert_markdown_footnotes_to_latex(md_content)
    md_content = escape_percent(md_content)
    (build_dir / md_path.name).write_text(md_content, encoding="utf-8")
    log("Preprocessed markdown: converted footnotes to LaTeX format")

    shutil.copy(md_dir / f"{md_base}.json", build_dir / f"{md_base}.json")
    if logo.exists():
        shutil.copy(logo, build_dir / logo.name)
    if fonts_dir.exists() and not (build_dir / "fonts").exists():
        shutil.copytree(fonts_dir, build_dir / "fonts")  # Copy images referenced in markdown
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
            err(f"LuaLaTeX exited with code {rc} but PDF was produced and saved: {target_pdf}")
            log("Done with warnings.")
            sys.exit(0)
        log(f"PDF generated: {target_pdf}")
        log("Done.")
        sys.exit(0)
    else:
        err(f"LuaLaTeX failed (exit code {rc}) and no PDF produced.")
        sys.exit(1)


if __name__ == "__main__":
    main()
