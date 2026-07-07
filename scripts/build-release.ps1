$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "ecoute-pc\.venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    Write-Host "Python venv introuvable. Creation de ecoute-pc/.venv..."
    python -m venv (Join-Path $root "ecoute-pc\.venv")
}

Write-Host "Installation des dependances Python..."
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $root "ecoute-pc\requirements.txt")
& $python -m pip install pyinstaller

Write-Host "Build du moteur Python..."
Push-Location (Join-Path $root "ecoute-pc")
& $python -m PyInstaller --clean --onefile --name ia-assistance-moteur serveur.py
Pop-Location

Write-Host "Installation des dependances Electron..."
Push-Location (Join-Path $root "app-electron")
npm install

Write-Host "Build de l'application portable..."
npm run dist
Pop-Location

Write-Host ""
Write-Host "Build termine."
Write-Host "Fichier a publier dans GitHub Releases:"
Write-Host (Join-Path $root "app-electron\dist\IA Assistance-0.1.0-portable.exe")
