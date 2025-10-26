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

PLACEHOLDERS = ["@@TITLE@@", "@@SUBTITLE@@", "@@SUBMITTEDTO@@", "@@AUTHORS@@", "@@DATE@@", "@@INPUT_FILE@@", "@@ENABLE_TITLE_PAGE@@", "@@ENABLE_CONTENT_PAGE@@", "@@ENABLE_LAST_PAGE_CREDITS@@", "@@ENABLE_FOOTNOTES_AT_END@@", "@@ENABLE_THATS_ALL_PAGE@@", "@@UNIVERSITY@@", "@@DEPARTMENT@@"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps", ".bmp", ".webp"}


class BuildError(Exception):
    pass


class Logger:
    COLORS = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "WARNING": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}  # Blue  # Green  # Yellow  # Red  # Reset

    @classmethod
    def info(cls, msg: str):
        print(f"{cls.COLORS['INFO']}[INFO]{cls.COLORS['RESET']} {msg}")

    @classmethod
    def success(cls, msg: str):
        print(f"{cls.COLORS['SUCCESS']}[SUCCESS]{cls.COLORS['RESET']} {msg}")

    @classmethod
    def warning(cls, msg: str):
        print(f"{cls.COLORS['WARNING']}[WARNING]{cls.COLORS['RESET']} {msg}")

    @classmethod
    def error(cls, msg: str):
        print(f"{cls.COLORS['ERROR']}[ERROR]{cls.COLORS['RESET']} {msg}")


def log(msg: str):
    Logger.info(msg)


def err(msg: str):
    Logger.error(msg)


def load_or_create_metadata(script_root: Path, md_dir: Path, md_base: str) -> dict:
    meta_path = md_dir / f"{md_base}.json"
    if not meta_path.exists():
        default = json.load(open(script_root / "default.json"))
        default["date"] = datetime.now().strftime("%B %d, %Y")
        meta_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        Logger.warning(f"Created default {md_base}.json")

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


def run_lualatex(build_dir: Path):
    cmd = [
        "lualatex",
        "--shell-escape",
        "-synctex=1",
        "-interaction=nonstopmode",
        "-file-line-error",
        "template.tex",
    ]

    Logger.info("Compiling LaTeX document...")
    
    for pass_num in range(1, 3):
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
        except FileNotFoundError as e:
            raise BuildError("lualatex not found in PATH.") from e

        if pass_num == 2:
            final_returncode = proc.returncode
            output = proc.stdout
            
            # Only print output if there are errors or warnings
            if final_returncode != 0 or "warning" in output.lower() or "error" in output.lower():
                print(output)

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


def detect_portrait_diagram(mermaid_code: str) -> bool:
    code_lower = mermaid_code.lower().strip()

    portrait_indicators = ["graph td", "graph tb", "flowchart td", "flowchart tb", "sequencediagram", "journey", "gitgraph", "mindmap"]

    for indicator in portrait_indicators:
        if indicator in code_lower:
            return True

    vertical_arrows = len(re.findall(r"-->", code_lower)) + len(re.findall(r"->>", code_lower)) + len(re.findall(r"->", code_lower))

    horizontal_indicators = len(re.findall(r"graph lr", code_lower)) + len(re.findall(r"flowchart lr", code_lower))

    if horizontal_indicators > 0:
        return False

    if vertical_arrows > 2:
        return True

    return False


def find_mmdc_command():
    try:
        result = subprocess.run(["mmdc", "--version"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return "mmdc"
    except FileNotFoundError:
        pass

    npm_bin_paths = []
    try:
        npm_result = subprocess.run(["npm", "config", "get", "prefix"], capture_output=True, text=True, check=False)
        if npm_result.returncode == 0:
            npm_prefix = npm_result.stdout.strip()
            if os.name == "nt":
                npm_bin_paths.extend([os.path.join(npm_prefix, "mmdc.cmd"), os.path.join(npm_prefix, "node_modules", ".bin", "mmdc.cmd")])
            else:
                npm_bin_paths.extend([os.path.join(npm_prefix, "bin", "mmdc"), os.path.join(npm_prefix, "lib", "node_modules", ".bin", "mmdc")])
    except FileNotFoundError:
        pass

    if os.name == "nt":
        user_home = os.path.expanduser("~")
        npm_bin_paths.extend([os.path.join(user_home, "AppData", "Roaming", "npm", "mmdc.cmd"), os.path.join(user_home, "AppData", "Local", "npm", "mmdc.cmd")])
    else:
        npm_bin_paths.extend(["/usr/local/bin/mmdc", "/usr/bin/mmdc"])

    for path in npm_bin_paths:
        if os.path.exists(path):
            return path

    return None


def process_mermaid_diagrams(content: str, build_dir: Path) -> str:
    if "```mermaid" not in content:
        return content

    mmdc_cmd = find_mmdc_command()
    if mmdc_cmd is None:
        Logger.warning("Mermaid-cli not found. Install with: npm install -g @mermaid-js/mermaid-cli")
        return content

    # Count total mermaid diagrams for progress tracking
    total_diagrams = len(re.findall(r'```mermaid\n(.*?)\n```', content, flags=re.DOTALL))
    if total_diagrams > 0:
        Logger.info(f"Processing {total_diagrams} Mermaid diagram(s)...")
    
    diagram_counter = 0

    def replace_mermaid_block(match):
        nonlocal diagram_counter
        diagram_counter += 1
        mermaid_code = match.group(1).strip()

        # Create a hash of the mermaid code for caching
        diagram_hash = hashlib.md5(mermaid_code.encode("utf-8")).hexdigest()[:12]
        image_name = f"mermaid_{diagram_hash}.png"
        image_path = build_dir / image_name
        if not image_path.exists():
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as temp_file:
                    temp_file.write(mermaid_code)
                    temp_mmd_path = Path(temp_file.name)

                is_portrait = detect_portrait_diagram(mermaid_code)

                config_content = {"theme": "neutral", "themeVariables": {"background": "#ffffff", "primaryColor": "#ffffff"}}

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as config_file:
                    json.dump(config_content, config_file, indent=2)
                    temp_config_path = Path(config_file.name)

                if is_portrait:
                    css_content = """
                    .mermaid {
                        max-width: 800px !important;
                        max-height: 800px !important;
                        width: 800px !important;
                        height: 800px !important;
                    }
                    svg {
                        max-width: 800px !important;
                        max-height: 800px !important;
                        width: 800px !important;
                        height: 800px !important;
                    }
                    """
                    viewport_width, viewport_height = 800, 800
                else:
                    css_content = """
                    .mermaid {
                        max-width: 1000px !important;
                        max-height: 600px !important;
                        width: 1000px !important;
                        height: 600px !important;
                    }
                    svg {
                        max-width: 1000px !important;
                        max-height: 600px !important;
                        width: 1000px !important;
                        height: 600px !important;
                    }
                    """
                    viewport_width, viewport_height = 1000, 600

                with tempfile.NamedTemporaryFile(mode="w", suffix=".css", delete=False, encoding="utf-8") as css_file:
                    css_file.write(css_content)
                    temp_css_path = Path(css_file.name)

                cmd = [mmdc_cmd, "-i", str(temp_mmd_path), "-o", str(image_path), "-t", "neutral", "-b", "white", "-c", str(temp_config_path), "--cssFile", str(temp_css_path), "--scale", "2", "--width", str(viewport_width), "--height", str(viewport_height)]

                result = subprocess.run(cmd, capture_output=True, text=True, check=False)

                temp_mmd_path.unlink()
                temp_config_path.unlink()
                temp_css_path.unlink()
                if result.returncode != 0 or not image_path.exists():
                    Logger.warning(f"Failed to generate Mermaid diagram {diagram_counter}/{total_diagrams}")
                    return f"```text\n{mermaid_code}\n```"
                else:
                    Logger.success(f"Generated Mermaid diagram {diagram_counter}/{total_diagrams}: {image_name}")

            except Exception:
                Logger.warning(f"Error processing Mermaid diagram {diagram_counter}/{total_diagrams}")
                return f"```text\n{mermaid_code}\n```"
        else:
            Logger.info(f"Using cached Mermaid diagram {diagram_counter}/{total_diagrams}: {image_name}")
        
        return f"![Mermaid Diagram]({image_name})"

    pattern = r"```mermaid\n(.*?)\n```"
    processed_content = re.sub(pattern, replace_mermaid_block, content, flags=re.DOTALL)

    return processed_content


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

    md_content = re.sub(r"==([^=]+)==", r"\\mdhighlight{\1}", md_content)
    md_content = re.sub(r"~~([^~]+)~~", r"\\mdstrikethrough{\1}", md_content)
    md_content = re.sub(r"\^([^^]+)\^", r"\\textsuperscript{\1}", md_content)
    md_content = re.sub(r"~([^~]+)~", r"\\textsubscript{\1}", md_content)
    md_content = re.sub(r"^(\s*)- \[x\](.*)$", r"\1- \\mdcheckboxchecked{}\2", md_content, flags=re.MULTILINE)
    md_content = re.sub(r"^(\s*)- \[ \](.*)$", r"\1- \\mdcheckboxunchecked{}\2", md_content, flags=re.MULTILINE)

    md_content = escape_signs(md_content, ["%", "&"])
    (build_dir / md_path.name).write_text(md_content, encoding="utf-8")

    shutil.copy(md_dir / f"{md_base}.json", build_dir / f"{md_base}.json")
    if logo.exists():
        shutil.copy(logo, build_dir / logo.name)
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
            Logger.warning(f"LuaLaTeX exited with code {rc} but PDF was produced: {target_pdf}")
        else:
            Logger.success(f"PDF generated: {target_pdf}")
        sys.exit(0)
    else:
        err(f"LuaLaTeX failed (exit code {rc}) and no PDF produced.")
        sys.exit(1)


if __name__ == "__main__":
    main()
