# OPTIONAL: install a Current-User Startup shortcut for Thai Voice Bridge.
# DO NOT run automatically — owner must approve and execute manually.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_startup.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\install_startup.ps1 -Remove
#
# This script does NOT modify HKLM or create scheduled tasks.
# It only creates/removes a shortcut under the current user's Startup folder.

param(
    [switch]$Remove,
    [string]$ExePath = "",
    [string]$PythonwPath = ""
)

$ErrorActionPreference = "Stop"
$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "ThaiVoiceBridge.lnk"

if ($Remove) {
    if (Test-Path $ShortcutPath) {
        Remove-Item $ShortcutPath -Force
        Write-Host "Removed: $ShortcutPath"
    } else {
        Write-Host "Nothing to remove."
    }
    exit 0
}

$Root = Split-Path -Parent $PSScriptRoot
$Target = $null
$Arguments = "tray"

if ($ExePath -and (Test-Path $ExePath)) {
    $Target = (Resolve-Path $ExePath).Path
    $Arguments = "tray"
} elseif ($PythonwPath -and (Test-Path $PythonwPath)) {
    $Target = (Resolve-Path $PythonwPath).Path
    $Arguments = "-m thai_voice_bridge tray"
} else {
    $venvPythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
    if (Test-Path $venvPythonw) {
        $Target = (Resolve-Path $venvPythonw).Path
        $Arguments = "-m thai_voice_bridge tray"
    } else {
        throw "Provide -ExePath or -PythonwPath, or create .venv first."
    }
}

$Wsh = New-Object -ComObject WScript.Shell
$Sc = $Wsh.CreateShortcut($ShortcutPath)
$Sc.TargetPath = $Target
$Sc.Arguments = $Arguments
$Sc.WorkingDirectory = $Root
$Sc.WindowStyle = 7
$Sc.Description = "Thai Voice Bridge (local Faster Whisper dictation)"
$Sc.Save()

Write-Host "Installed Startup shortcut: $ShortcutPath"
Write-Host "Target: $Target $Arguments"
Write-Host "To remove: powershell -ExecutionPolicy Bypass -File .\scripts\install_startup.ps1 -Remove"
