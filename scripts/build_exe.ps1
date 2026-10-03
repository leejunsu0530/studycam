param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$bundleMode = if ($OneFile) { "--onefile" } else { "--onedir" }

& .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean --windowed $bundleMode `
    --name "StudyCam" `
    --icon "assets\studycam.ico" `
    --add-data "assets\studycam.ico:assets" `
    --hidden-import PySide6.QtMultimedia `
    --hidden-import cv2 `
    --collect-all googleapiclient `
    --hidden-import google_auth_oauthlib.flow `
    --hidden-import google.oauth2.credentials `
    --hidden-import google.auth.transport.requests `
    --paths . `
    "studycam_launcher.py"

Write-Host "완료: dist\StudyCam"
