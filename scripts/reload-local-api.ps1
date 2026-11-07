param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$logDirectory = Join-Path $projectRoot 'data/frontend-rebuild'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
& (Join-Path $PSScriptRoot 'stop-local-api.ps1') -Port $Port
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory 'api-out.log') -RedirectStandardError (Join-Path $logDirectory 'api-error.log') -PassThru
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $apiProcess.Refresh()
    if ($apiProcess.HasExited) { break }
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 2
        if ($health.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) {
    throw 'API尚未就绪，请查看data/frontend-rebuild/api-error.log；未操作数据库。'
}
Write-Output "本项目 API 已就绪，PID=$($apiProcess.Id)，端口=$Port；日志在忽略的 data/frontend-rebuild。"
