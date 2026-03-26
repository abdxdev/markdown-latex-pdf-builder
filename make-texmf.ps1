$base = "$env:APPDATA\markdown-latex-pdf-builder\markdown-latex-pdf-builder-main"
cd $base
md texmf -ea 0

python script.py "test\COMPREHENSIVE-GUIDE.md" --show
cd "test\_build_COMPREHENSIVE-GUIDE"

lualatex --recorder --shell-escape -interaction=nonstopmode template.tex

sls '^INPUT (.*\.(sty|cls|def|fd|clo|ldf|lua))$' template.fls | % { $_.Matches.Groups[1].Value } | ? { Test-Path $_ } | sort -u | cp -Dest "$base\texmf" -ea 0

cd $base
