# stop_remote.ps1
# Encerra o Antigravity Remote Host e o túnel no Windows

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PidFile = Join-Path $ScriptDir "server.pid"

if (Test-Path $PidFile) {
    $targetPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($targetPid) {
        Write-Host "Encerrando Antigravity Remote Host (PID $targetPid)..." -ForegroundColor Yellow
        try {
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# Encerra eventuais processos filhos de cloudflared
Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Antigravity Remote Host encerrado com sucesso." -ForegroundColor Green
