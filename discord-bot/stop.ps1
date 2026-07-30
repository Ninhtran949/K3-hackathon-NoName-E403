$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$projectPattern = "*$projectDir*.venv*python*main.py*"
$botProcesses = @(
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -like "python*" -and
            $_.CommandLine -like $projectPattern
        }
)

if ($botProcesses.Count -eq 0) {
    Write-Host "Bot hiện không chạy."
    exit 0
}

foreach ($botProcess in $botProcesses) {
    $processStillRunning = Get-Process -Id $botProcess.ProcessId -ErrorAction SilentlyContinue
    if ($processStillRunning) {
        Stop-Process -Id $botProcess.ProcessId -Force
        Write-Host "Đã dừng bot PID $($botProcess.ProcessId)."
    }
}
