param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) { Write-Output '本项目API端口未监听。'; return }
$apiProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
if (-not $apiProcess.CommandLine -or -not $apiProcess.CommandLine.Contains($projectRoot) -or
    -not $apiProcess.CommandLine.Contains('uvicorn') -or -not $apiProcess.CommandLine.Contains('app.main:app')) {
    throw '端口由未确认属于本项目的进程占用，未停止任何进程。'
}
Stop-Process -Id $listener.OwningProcess
Wait-Process -Id $listener.OwningProcess -Timeout 15 -ErrorAction SilentlyContinue
Write-Output '已停止本项目API。'
