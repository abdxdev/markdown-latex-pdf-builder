# Prerequisites

Before you begin, ensure you have met the following requirements:

- You have installed [Python 3.7+](https://www.python.org/downloads/).
  - Check installation by running `python --version; pip --version` in PowerShell.
- You have installed [VS Code](https://code.visualstudio.com/download).
  - Check installation by running `code --version` in PowerShell.
  - Install [Command Runner](https://marketplace.visualstudio.com/items?itemName=edonet.vscode-command-runner) extension.

# Installation

Launch PowerShell as Administrator and run the following commands:

```powershell
# Set security protocol
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
# Download TinyTeX installer
Invoke-WebRequest -Uri "https://yihui.org/tinytex/install-windows.bat" -OutFile "install-tinytex.bat"
# Run the installer
.\install-tinytex.bat
# Cleanup
Remove-Item install-tinytex.bat
# Add TinyTeX to PATH
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"
# Install Required Packages
tlmgr install adjustbox amsfonts amsmath booktabs endnotes etoolbox fancyhdr float fontspec footmisc geometry hyperref hyphenat markdown minted tcolorbox titling tocloft xcolor
# Install Pygments for syntax highlighting
pip install Pygments
# Download project repository
wget https://github.com/abdxdev/notes-maker/archive/refs/heads/main.zip -OutFile "$env:APPDATA\main.zip"
Expand-Archive -Path "$env:APPDATA\main.zip" -DestinationPath "$env:APPDATA"
Remove-Item "$env:APPDATA\main.zip"
# Install JetBrains Mono font
Copy-Item "$env:APPDATA\notes-maker-main\fonts\JetBrainsMonoNL-Regular.ttf" "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\" -Force; New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "JetBrains Mono NL Regular (TrueType)" -Value "JetBrainsMonoNL-Regular.ttf" -PropertyType String -Force
```

# Workflow Setup

1. Open VS Code and press `Ctrl+Shift+P`.
2. Type `Preferences: Open User Settings (JSON)` and select it.
3. Add the following configuration to your `settings.json` file:

```json
{
  "command-runner.commands": {
    "Build LaTeX Document": "python $env:APPDATA\\notes-maker-main\\script.py \"${file}\""
  }
}
```

4. Save the file.

# Usage

- Open a folder in VS Code
- Create a markdown file (`.md`) and add your content.
- Press `Ctrl+Shift+R` and select `Build LaTeX Document` to generate the PDF.
- The generated PDF will be saved in the same directory as the markdown file.
- To customize the document, edit the `.json` file generated in the directory.

# Change Default Values

To change the default values used in the document generation, you can modify the `default.json` file located in the script directory. This file contains all the default settings for the document generation process.

1. Open the `default.json` file in your preferred text editor (Or by running `code $env:APPDATA\notes-maker-main\default.json` in PowerShell).
2. Update the values as needed. For example, you can change the university name, department, document title, and other settings.
3. Save the changes to the `default.json` file.

The next time you run the document generation script, it will use the updated default values from the `default.json` file.
