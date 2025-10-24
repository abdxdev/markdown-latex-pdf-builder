# Notes Maker — Automated LaTeX Document Builder

Notes Maker lets you convert Markdown files into formatted LaTeX PDFs directly from VS Code. This guide explains how to install and use it.

---

## Prerequisites

Before starting, make sure you have the following:

### Python 3.7+

Download and install it from [python.org/downloads](https://www.python.org/downloads/).

Check installation:

```powershell
python --version; pip --version
```

### Visual Studio Code

Download from [code.visualstudio.com](https://code.visualstudio.com/download).

Check installation:

```powershell
code --version
```

Install the [Command Runner](https://marketplace.visualstudio.com/items?itemName=edonet.vscode-command-runner) extension for VS Code.

---

## Installation

Open PowerShell as Administrator and run these commands:

```powershell
# Set security protocol
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

# Download and install TinyTeX
Invoke-WebRequest -Uri "https://yihui.org/tinytex/install-windows.bat" -OutFile "install-tinytex.bat"
.\install-tinytex.bat
Remove-Item install-tinytex.bat

# Add TinyTeX to PATH
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"

# Install required LaTeX packages
tlmgr install adjustbox amsfonts amsmath booktabs endnotes etoolbox fancyhdr float fontspec footmisc geometry hyperref hyphenat markdown minted tcolorbox titling tocloft xcolor

# Install Pygments
pip install Pygments

# Download Notes Maker
wget https://github.com/abdxdev/notes-maker/archive/refs/heads/main.zip -OutFile "$env:APPDATA\main.zip"
Expand-Archive -Path "$env:APPDATA\main.zip" -DestinationPath "$env:APPDATA"
Remove-Item "$env:APPDATA\main.zip"

# Install JetBrains Mono font
Copy-Item "$env:APPDATA\notes-maker-main\fonts\JetBrainsMonoNL-Regular.ttf" "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\" -Force
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "JetBrains Mono NL Regular (TrueType)" -Value "JetBrainsMonoNL-Regular.ttf" -PropertyType String -Force
```

After running these commands, TinyTeX, Pygments, and Notes Maker will be installed.

---

## VS Code Setup

1. Open VS Code and press `Ctrl + Shift + P`.
2. Search for **Preferences: Open User Settings (JSON)** and open it.
3. Add this to the bottom of your `settings.json` file just before the closing `}`:

```json
"command-runner.commands": {
    "Build LaTeX Document": "python \"$env:APPDATA\\notes-maker-main\\script.py\" \"${file}\""
}
```

4. Save the file.

---

## Usage

1. Open any folder in VS Code.
2. Create a new Markdown file (for example, `report.md`).
3. Add your content.
4. Press `Ctrl + Shift + R` and select **Build LaTeX Document**.

A PDF will be generated in the same folder as your Markdown file.
A `.json` file with document metadata will also be created.
You can delete the `_build_markdown` folder after the PDF is finalized.

---

## Changing Default Values

You can edit the default settings for document generation by modifying the `default.json` file.

Run this command to open it in VS Code:

```powershell
code $env:APPDATA\notes-maker-main\default.json
```

Edit values such as the university name, department, title, and other settings.
The next time you generate a document, it will use the updated defaults.

---

## Changing the University Logo

To replace the default logo, open the script directory:

```powershell
explorer $env:APPDATA\notes-maker-main\
```

Replace the existing `uni-logo.pdf` file with your logo file (use the same name).
