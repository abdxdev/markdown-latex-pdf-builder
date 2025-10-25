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

## Installation

Open PowerShell and run these commands:

#### Step 1: Set security protocol

```powershell
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
```

#### Step 2: Download and install TinyTeX

```powershell
Invoke-WebRequest -Uri "https://yihui.org/tinytex/install-windows.bat" -OutFile "install-tinytex.bat"
.\install-tinytex.bat
Remove-Item install-tinytex.bat
```

#### Step 3: Add TinyTeX to PATH

```powershell
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"
```

#### Step 4: Install LaTeX packages

```powershell
tlmgr install adjustbox amsfonts amsmath booktabs endnotes etoolbox fancyhdr float fontspec footmisc geometry hyperref hyphenat markdown minted tcolorbox tikzfill titlesec titling tocloft xcolor
```

#### Step 5: Install Pygments

```powershell
pip install Pygments
```

#### Step 6: Download Notes Maker

```powershell
wget https://github.com/abdxdev/notes-maker/archive/refs/heads/main.zip -OutFile "$env:APPDATA\main.zip"
Expand-Archive -Path "$env:APPDATA\main.zip" -DestinationPath "$env:APPDATA"
Remove-Item "$env:APPDATA\main.zip"
```

#### Step 7: Install JetBrains Mono font

```powershell
Copy-Item "$env:APPDATA\notes-maker-main\fonts\JetBrainsMonoNL-Regular.ttf" "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\" -Force
New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "JetBrains Mono NL Regular (TrueType)" -Value "JetBrainsMonoNL-Regular.ttf" -PropertyType String -Force
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
3. Add your content.
4. Press `Ctrl + Shift + R` and select **Build LaTeX Document**.
5. After a few moments, the PDF will be generated along with a `.json` metadata file. Edit this file to change document settings like title, university, and date.
6. Re-run the build command to generate the updated PDF from step 4.

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

Install latex packages from [step 4](#step-4-install-latex-packages) of the installation section.
