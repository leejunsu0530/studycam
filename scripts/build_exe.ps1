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
    --paths . `
    "studycam_launcher.py"

Write-Host "완료: dist\StudyCam"
