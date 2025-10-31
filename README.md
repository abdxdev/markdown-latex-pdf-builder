Windows | [Linux](README-LINUX.md)

# Automated LaTeX Document Builder

Notes Maker converts your Markdown notes into professional-looking LaTeX PDFs automatically.

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

### Node Package Manager (Optional, for Mermaid diagrams)

Download and install Node.js from [nodejs.org](https://nodejs.org/).

Check installation:

```powershell
node --version; npm --version
```

## Installation

Open PowerShell and run these commands:
_Do NOT run as Administrator_

#### Step 1: Download and install TinyTeX

```powershell
Invoke-WebRequest -Uri "https://yihui.org/tinytex/install-windows.bat" -OutFile "install-tinytex.bat"
.\install-tinytex.bat
Remove-Item install-tinytex.bat
```

#### Step 2: Install LaTeX packages

```powershell
tlmgr install adjustbox amsfonts amsmath booktabs csvsimple endnotes etoolbox fancyhdr float fontspec footmisc geometry grfext hyperref hyphenat lineno listings lua-ul luaotfload markdown minted paralist pdfcol soul tcolorbox tikzfill titlesec titling tocloft ulem upquote xcolor
```

#### Step 3: Install Pygments

```powershell
pip install Pygments
```

#### Step 4: Download Notes Maker

```powershell
wget https://github.com/abdxdev/notes-maker/archive/refs/heads/main.zip -OutFile "$env:APPDATA\main.zip"
Expand-Archive -Path "$env:APPDATA\main.zip" -DestinationPath "$env:APPDATA"
Remove-Item "$env:APPDATA\main.zip"
```

<!-- #### Step 6: Install JetBrains Mono font

```powershell
Copy-Item "$env:APPDATA\notes-maker-main\fonts\JetBrainsMonoNL-Regular.ttf" "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\" -Force
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "JetBrains Mono NL Regular (TrueType)" -Value "JetBrainsMonoNL-Regular.ttf" -PropertyType String -Force
``` -->

#### Step 5 (Optional): Install Mermaid CLI for diagram support

```powershell
npm install -g @mermaid-js/mermaid-cli
```

## VS Code Setup

1. Open VS Code and press `Ctrl + Shift + P`.
2. Search for **Preferences: Open User Settings (JSON)** and open it.
3. Add this to the bottom of your `settings.json` file just before the closing `}`:

   ```jsonc
   // ...other settings...,
   "command-runner.commands": {
       "Build LaTeX Document": "python \"$env:APPDATA\\notes-maker-main\\script.py\" \"${file}\""
   }
   ```

4. Save the file.

## Usage

1. Open any folder in VS Code.
2. Create a new Markdown file (for example, `report.md`).
3. Add your content. Visit the [Markdown Guide](https://www.markdownguide.org/) for syntax help.
4. Press `Ctrl + Shift + R` and select **Build LaTeX Document**.
5. After a few moments, the PDF will be generated along with a `.json` metadata file. Edit this file to change document settings like title, university, and date.
6. Re-run the build command from step 4 to generate the updated PDF.

> You may delete the build folder (`_build_report` in this case) after the PDF is finalized.

## Changing Default Values

You can edit the default settings for document generation by modifying the `default.json` file.

Run this command to open it in VS Code:

```powershell
code $env:APPDATA\notes-maker-main\default.json
```

Edit values such as the university name, department, title, and other settings.  
The next time you generate a document, it will use the updated defaults.

## Changing the University Logo

To replace the default logo, open the script directory:

```powershell
explorer $env:APPDATA\notes-maker-main\
```

Replace the existing `uni-logo.pdf` file with your logo file (use the same name).

## Updating Notes Maker

To update Notes Maker, run these commands in PowerShell:

#### Step 1: Remove old version and download the latest

```powershell
Remove-Item "$env:APPDATA\notes-maker-main" -Recurse -Force
wget https://github.com/abdxdev/notes-maker/archive/refs/heads/main.zip -OutFile "$env:APPDATA\main.zip"
Expand-Archive -Path "$env:APPDATA\main.zip" -DestinationPath "$env:APPDATA"
Remove-Item "$env:APPDATA\main.zip"
```

#### Step 2: Reinstall LaTeX packages

Install latex packages from [step 2](#step-2-install-latex-packages) of the installation section.
