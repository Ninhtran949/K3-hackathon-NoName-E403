$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$venvPython = Join-Path $projectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Chưa có môi trường ảo. Hãy chạy .\setup.ps1 trước."
}

Push-Location $projectDir
try {
    & $venvPython "main.py"
}
finally {
    Pop-Location
}
