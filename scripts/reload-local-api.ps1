param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$logDirectory = Join-Path $projectRoot 'data/frontend-rebuild'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $apiProcessId = ($listener | Select-Object -First 1).OwningProcess
    $apiProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$apiProcessId"
    if (-not $apiProcess.CommandLine.Contains($projectRoot) -or
        -not $apiProcess.CommandLine.Contains('uvicorn') -or
        -not $apiProcess.CommandLine.Contains('app.main:app')) {
        throw '端口由未确认属于本项目的进程占用，未停止任何进程。'
    }
    Stop-Process -Id $apiProcessId
    Wait-Process -Id $apiProcessId -Timeout 15 -ErrorAction SilentlyContinue
}
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'api-out.log') -RedirectStandardError (Join-Path $logDirectory 'api-error.log') -PassThru
Write-Output "已启动本项目 API，PID=$($apiProcess.Id)，端口=$Port；日志在忽略的 data/frontend-rebuild。"
