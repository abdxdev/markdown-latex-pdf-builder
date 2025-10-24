# Markdown to LaTeX PDF Converter

A powerful script that converts Markdown files to beautifully formatted PDFs using LuaLaTeX. Perfect for creating university assignments, reports, and technical documents with professional styling.

## Features

- ✨ **Markdown Support**: Write in Markdown, get professional PDFs
- 🎨 **Syntax Highlighting**: Beautiful code blocks with Pygments
- 📊 **Tables & Images**: Auto-scaling for perfect fit
- 📝 **Footnotes**: Support for both page footnotes and endnotes
- 🎯 **Customizable**: Toggle title page, table of contents, credits, and more
- 📚 **Professional Layout**: University-ready formatting with headers and page numbers
- 🔗 **Hyperlinks**: Clickable URLs and cross-references
- 💬 **Blockquotes**: Styled with gray background boxes
- 📐 **Math Support**: Full LaTeX math equation support

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Installing TinyTeX](#installing-tinytex)
  - [Installing Required Packages](#installing-required-packages)
  - [Installing Python Dependencies](#installing-python-dependencies)
- [Project Setup](#project-setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

## Prerequisites

- **Python 3.7+**
- **TinyTeX** (lightweight LaTeX distribution)
- **Pygments** (for syntax highlighting)

## Installation

### Installing TinyTeX

TinyTeX is a lightweight, cross-platform LaTeX distribution that's perfect for this project.

#### Windows (PowerShell)

```powershell
# Install TinyTeX
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri "https://yihui.org/tinytex/install-windows.bat" -OutFile "install-tinytex.bat"
.\install-tinytex.bat
Remove-Item install-tinytex.bat
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"

# Install Required Packages
```

After installation, restart your terminal and verify:

```powershell
lualatex --version
```

### Installing Required Packages

After installing TinyTeX, install the required LaTeX packages:

```bash

```

### Installing Python Dependencies

Install Pygments for syntax highlighting:

```bash
pip install Pygments
```

Verify Pygments is installed:

```bash
python -c "import pygments; print(pygments.__version__)"
```

## Project Setup

1. **Clone or download this repository**

2. **Install the JetBrains Mono font** (for code blocks):
   - The font files are in the `fonts/` directory
   - Windows: Right-click `JetBrainsMonoNL-Regular.ttf` → Install
   - Linux: Copy to `~/.local/share/fonts/` and run `fc-cache -f -v`
   - macOS: Double-click the font file and click "Install Font"

3. **Add your university logo**:
   - Replace `uni-logo.pdf` with your university's logo
   - Or update the template to use a different image format (PNG, JPG, etc.)

## Usage

### Basic Usage

1. Create your content in a Markdown file (e.g., `content.md`)

2. Create a JSON configuration file with the same name (e.g., `content.json`):

```json
{
  "title": "My Assignment",
  "subtitle": "Course Name",
  "submittedby": [
    {
      "name": "Your Name",
      "roll": "Your Roll Number"
    }
  ],
  "submittedto": "Professor Name",
  "date": "January 1, 2025"
}
```

3. Run the script:

```bash
python script.py content.md
```

4. Your PDF will be generated as `content.pdf` in the same directory!

### Advanced Usage

The script automatically:
- Creates a build directory (`_build_<filename>/`) for compilation
- Copies all necessary files
- Processes markdown footnotes to LaTeX format
- Handles image references
- Generates the final PDF

To regenerate after changes, simply run the script again. The build directory is cached for faster compilation.

## Configuration

### JSON Metadata Options

Your `.json` file supports the following options:

```json
{
  "title": "Document Title",
  "subtitle": "Course/Subject Name",
  "submittedby": [
    {
      "name": "Student Name",
      "roll": "Registration Number"
    }
  ],
  "submittedto": "Instructor Name",
  "date": "Submission Date",
  
  // Toggle features (all default to true except enableFootnotesAtEnd)
  "enableTitlePage": true,          // Show cover page
  "enableContentPage": true,        // Show table of contents
  "enableLastPageCredits": true,    // Show credits footer
  "enableThatsAllPage": true,       // Show "That's all for now" page
  "enableFootnotesAtEnd": false     // Convert footnotes to endnotes
}
```

### Multiple Authors

Add multiple students in the `submittedby` array:

```json
{
  "submittedby": [
    {
      "name": "Student One",
      "roll": "2023-CS-001"
    },
    {
      "name": "Student Two",
      "roll": "2023-CS-002"
    }
  ]
}
```

## Customization

### Markdown Features

#### Code Blocks

Use fenced code blocks with language specification:

````markdown
```python
def hello_world():
    print("Hello, World!")
```
````

#### Inline Code

Use backticks for inline code: `code here`

#### Footnotes

Two styles are supported:

```markdown
Here's a reference footnote[^1].

Here's an inline footnote^[This is inline].

[^1]: This is the footnote content.
```

#### Blockquotes

```markdown
> This is a blockquote.
> It will be styled with a gray background.
```

#### Images

```markdown
![Alt text](image.png)
```

Images are automatically scaled to fit the page width.

#### Tables

```markdown
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

Tables automatically scale to fit the page width.

#### Line Breaks

Use HTML `<br>` tags for manual line breaks:

```markdown
Line 1<br>
Line 2
```

### Template Customization

Edit `template.tex` to customize:

- **Colors**: Modify color definitions (search for `\definecolor`)
- **Fonts**: Change font settings (search for `\setmonofont`)
- **Margins**: Adjust page geometry (search for `\usepackage[margin=1in]{geometry}`)
- **Headers/Footers**: Modify `fancyhdr` settings
- **University Info**: Update `\newcommand{\university}` and `\newcommand{\department}`

## Troubleshooting

### Common Issues

#### "lualatex not found"

**Solution**: Ensure TinyTeX is installed and added to your PATH. Restart your terminal.

```bash
# Verify installation
lualatex --version

# If not found, add to PATH (example for Windows)
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"
```

#### "Package X not found"

**Solution**: Install missing packages with `tlmgr`:

```bash
tlmgr install <package-name>
```

#### "Pygments not found" or syntax highlighting issues

**Solution**: Install Pygments and ensure it's in PATH:

```bash
pip install Pygments

# Verify
pygmentize -V
```

#### Font not found errors

**Solution**: Ensure JetBrains Mono is installed system-wide, not just in the fonts/ directory.

#### Images not appearing

**Solution**: 
- Check that image paths in markdown are correct
- Ensure images are in the same directory or use relative paths
- Supported formats: PNG, JPG, PDF, SVG, EPS

#### Compilation errors

**Solution**: 
- Check the log file in `_build_<filename>/template.log`
- Ensure your markdown syntax is valid
- Look for special characters that need escaping (%, $, &, etc.)

### Cleaning Build Files

To start fresh, delete the build directory:

```bash
# PowerShell
Remove-Item -Recurse -Force _build_content

# Linux/macOS
rm -rf _build_content
```

## Examples

### Example 1: Simple Assignment

**content.md**:
```markdown
# Introduction

This is my assignment about **algorithms**.

## Bubble Sort

Here's an implementation:

```python
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr
```

The time complexity is O(n²)[^1].

[^1]: Worst and average case complexity.
```

**content.json**:
```json
{
  "title": "Sorting Algorithms",
  "subtitle": "Data Structures and Algorithms",
  "submittedby": [{"name": "John Doe", "roll": "2023-CS-001"}],
  "submittedto": "Dr. Smith",
  "date": "January 15, 2025",
  "enableContentPage": false
}
```

### Example 2: Technical Report with Math

**report.md**:
```markdown
# Mathematical Analysis

The quadratic formula is:

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$

Where $a \neq 0$.

## Results

| Input | Output | Time (ms) |
|-------|--------|-----------|
| 100   | 4950   | 1.2       |
| 1000  | 499500 | 15.7      |
```

## File Structure

```
md-to-luatex/
├── script.py              # Main conversion script
├── template.tex           # LaTeX template
├── default.json           # Default metadata
├── uni-logo.pdf          # University logo
├── fonts/                # Custom fonts
│   └── JetBrainsMonoNL-Regular.ttf
├── content.md            # Your markdown file
├── content.json          # Your metadata
└── _build_content/       # Build directory (auto-generated)
```

## Credits

This template was carefully crafted to provide professional-looking PDFs from Markdown with minimal effort.

- **Author**: abd
- **Website**: [abd-dev.studio](https://abd-dev.studio/blogs/how-i-create-assignments-and-notes)
- **Contact**: abdulrahman.abd.dev@gmail.com

## License

Feel free to use and modify for your academic and personal projects!

---

**Happy Writing! 📝✨**
