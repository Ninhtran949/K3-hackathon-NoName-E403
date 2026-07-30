$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot

function Find-WorkingPython {
    foreach ($commandName in @("python", "py")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }

        # WindowsApps/python.exe có thể chỉ là alias mở Microsoft Store.
        if ($command.Source -like "*\Microsoft\WindowsApps\*") {
            continue
        }

        & $command.Source --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return $command.Source
        }
    }

    $localPythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path -LiteralPath $localPythonRoot) {
        $localInstall = Get-ChildItem -LiteralPath $localPythonRoot -Directory |
            Sort-Object Name -Descending |
            ForEach-Object {
                Join-Path $_.FullName "python.exe"
            } |
            Where-Object {
                Test-Path -LiteralPath $_
            } |
            Select-Object -First 1

        if ($localInstall) {
            & $localInstall --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $localInstall
            }
        }
    }

    return $null
}

$pythonExecutable = Find-WorkingPython
if (-not $pythonExecutable) {
    throw "Chưa tìm thấy Python. Hãy cài Python 3.11 trở lên từ https://www.python.org/downloads/"
}

$venvDir = Join-Path $projectDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

& $pythonExecutable -m venv $venvDir
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
    throw "Không thể tạo môi trường ảo tại $venvDir"
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Không thể nâng cấp pip"
}

& $venvPython -m pip install -r (Join-Path $projectDir "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Không thể cài dependencies"
}

Write-Host "Cài đặt hoàn tất."
Write-Host "Điền DISCORD_TOKEN trong file .env, sau đó chạy: .\run.ps1"
