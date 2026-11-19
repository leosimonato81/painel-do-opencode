# Gera "Painel do OpenCode.exe" na pasta dist\
# Precisa do Python 3 instalado. Rode no PowerShell, dentro desta pasta:
#   powershell -ExecutionPolicy Bypass -File .\gerar-exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --disable-pip-version-check -q -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile `
    --name "Painel do OpenCode" `
    --icon icone.ico `
    --add-data "icone.png;." `
    painel.py

Write-Host ""
Write-Host "Pronto: dist\Painel do OpenCode.exe"
