param(
    [string]$ReleaseId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if ($ReleaseId -notmatch '^[A-Za-z0-9_-]+$') { throw 'Invalid release identifier.' }
$releaseRoot = Join-Path $root "dist\release-$ReleaseId"
$workRoot = Join-Path $root "build\release-$ReleaseId"
$zipPath = Join-Path $root "dist\StudyCam-Windows-$ReleaseId.zip"
if ((Test-Path -LiteralPath $releaseRoot) -or (Test-Path -LiteralPath $workRoot) -or (Test-Path -LiteralPath $zipPath)) {
    throw 'Release output already exists. Choose a different release identifier.'
}
New-Item -ItemType Directory -Path $releaseRoot, $workRoot -ErrorAction Stop | Out-Null
$icon = Join-Path $root 'assets\studycam.ico'
$extension = Join-Path $root 'studycam\browser_extension'
$launcher = Join-Path $root 'studycam_launcher.py'
$projectFile = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root 'pyproject.toml')
$versionMatch = [regex]::Match($projectFile, '(?m)^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"\s*$')
if (-not $versionMatch.Success) { throw 'Could not read the project version from pyproject.toml.' }
$projectVersion = $versionMatch.Groups[1].Value

& .\.venv\Scripts\python.exe -m PyInstaller `
    --windowed --onedir --name StudyCam `
    --distpath $releaseRoot --workpath $workRoot --specpath $workRoot `
    --icon $icon `
    --add-data "${icon}:assets" `
    --add-data "${extension}:studycam\browser_extension" `
    --hidden-import PySide6.QtMultimedia --hidden-import cv2 `
    --collect-all googleapiclient `
    --hidden-import google_auth_oauthlib.flow `
    --hidden-import google.oauth2.credentials `
    --hidden-import google.auth.transport.requests `
    --paths $root $launcher
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

$appDir = Join-Path $releaseRoot 'StudyCam'
if (-not (Test-Path -LiteralPath (Join-Path $appDir 'StudyCam.exe'))) { throw 'The executable was not produced.' }
Move-Item -LiteralPath (Join-Path $appDir 'StudyCam.exe') -Destination (Join-Path $appDir "studycam v$projectVersion.exe")
Copy-Item -LiteralPath 'studycam\browser_extension' -Destination (Join-Path $appDir 'browser_extension') -Recurse
Copy-Item -LiteralPath 'scripts\사용 안내.txt' -Destination $appDir
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($appDir, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $true)
Write-Host "Release ZIP: $zipPath"
