# Build Windows executable with PyInstaller (run manually when ready).
# Does NOT install or deploy anything.
#
# Usage (from repo root, after venv + pip install -e ".[dev]" and pyinstaller):
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

& $Py -m pip install -q "pyinstaller>=6,<7"
& $Py -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name PoodType `
  --icon src/thai_voice_bridge/assets/thai_voice_bridge.ico `
  --add-data "src/thai_voice_bridge/assets;thai_voice_bridge/assets" `
  --add-data "config.example.yaml;." `
  --paths src `
  --hidden-import thai_voice_bridge `
  --hidden-import faster_whisper `
  --collect-all faster_whisper `
  --collect-all av `
  --collect-all ctranslate2 `
  src/thai_voice_bridge/__main__.py

Write-Host "Output: $Root\dist\PoodType\PoodType.exe"
Write-Host "Run tray via: PoodType.exe (tray is the default command)"
