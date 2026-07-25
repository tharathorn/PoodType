param(
  [string]$Version = "0.1.0",
  [string]$ModelSnapshot = "",
  [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

if (-not $ModelSnapshot) {
  $Discovery = & $Py -m thai_voice_bridge discover-cache
  $SnapshotLine = $Discovery | Where-Object { $_ -like "cached_snapshot: *" } |
    Select-Object -First 1
  if ($SnapshotLine -and $SnapshotLine -notlike "*not found*") {
    $ModelSnapshot = $SnapshotLine.Substring("cached_snapshot: ".Length).Trim()
  }
}
if (-not $ModelSnapshot -or -not (Test-Path $ModelSnapshot)) {
  throw "Complete faster-whisper medium snapshot not found. Pass -ModelSnapshot <path>."
}

& "$PSScriptRoot\build_windows.ps1"
$AppDir = Join-Path $Root "dist\PoodType"
if (-not (Test-Path (Join-Path $AppDir "PoodType.exe"))) {
  throw "PyInstaller output is missing PoodType.exe"
}

Copy-Item `
  "README.md", `
  "LICENSE", `
  "PRIVACY.md", `
  "SECURITY.md", `
  "THIRD_PARTY_NOTICES.md", `
  "config.example.yaml" `
  $AppDir -Force
$ModelDir = Join-Path $AppDir "models\faster-whisper-medium"
& $Py "$PSScriptRoot\copy_model_bundle.py" `
  --source $ModelSnapshot `
  --destination $ModelDir `
  --model medium

New-Item -ItemType Directory -Path "release" -Force | Out-Null
$PortableFlag = Join-Path $AppDir "portable.flag"
New-Item -ItemType File -Path $PortableFlag -Force | Out-Null
$PortableZip = Join-Path $Root "release\PoodType-$Version-Windows-x64-Portable.zip"
Remove-Item $PortableZip -Force -ErrorAction SilentlyContinue
& tar.exe -a -cf $PortableZip -C (Join-Path $Root "dist") "PoodType"
if ($LASTEXITCODE -ne 0) {
  throw "Portable ZIP creation failed."
}
Remove-Item $PortableFlag -Force

& tar.exe -tf $PortableZip | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Portable ZIP verification failed."
}

if (-not $SkipInstaller) {
  $InnoCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
  )
  $ISCC = $InnoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $ISCC) {
    throw "Inno Setup 6 not found. Install it or use -SkipInstaller."
  }
  & $ISCC "/DMyAppVersion=$Version" "installer\PoodType.iss"
  if ($LASTEXITCODE -ne 0) {
    throw "Installer build failed."
  }
}

$Portable = Get-Item $PortableZip
Write-Host "Portable: $($Portable.FullName) ($([math]::Round($Portable.Length / 1MB, 1)) MB)"
if (-not $SkipInstaller) {
  Get-Item "release\PoodType-$Version-Windows-x64-Setup.exe" |
    ForEach-Object {
      Write-Host "Installer: $($_.FullName) ($([math]::Round($_.Length / 1MB, 1)) MB)"
    }
}
