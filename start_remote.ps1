# start_remote.ps1
# Inicia o Antigravity Remote Host no Windows

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Recarrega o PATH do sistema e do usuário para garantir acesso a python, cloudflared, agy e git
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

$PidFile = Join-Path $ScriptDir "server.pid"
$LogFile = Join-Path $ScriptDir "server.log"
$ErrFile = Join-Path $ScriptDir "server.err.log"

# Verifica se já está em execução
if (Test-Path $PidFile) {
    $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        Write-Host "Servidor ja esta em execucao (PID $existingPid)." -ForegroundColor Yellow
        exit 0
    }
}

# Verifica Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error "Python nao foi encontrado no PATH. Instale o Python ou execute: winget install Python.Python.3.12"
}

# Inicia o servidor em background
Write-Host "Iniciando Antigravity Remote Host..." -ForegroundColor Cyan
$process = Start-Process -FilePath "python" -ArgumentList "-u server.py" -WorkingDirectory $ScriptDir -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile -PassThru -NoNewWindow

$process.Id | Out-File -FilePath $PidFile -Encoding ascii
Write-Host "Servidor iniciado em background (PID $($process.Id))." -ForegroundColor Green

# Aguarda URL do túnel no log
Write-Host "Aguardando tunel seguro Cloudflare..." -ForegroundColor Cyan
$tunnelFound = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    $logContent = ""
    if (Test-Path $LogFile) {
        $logContent += Get-Content $LogFile -Raw -ErrorAction SilentlyContinue
    }
    if (Test-Path $ErrFile) {
        $logContent += Get-Content $ErrFile -Raw -ErrorAction SilentlyContinue
    }
    if ($logContent -match "(https://[a-zA-Z0-9-]+\.trycloudflare\.com)") {
        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host "TUNEL ONLINE: $($Matches[1])" -ForegroundColor Green
        Write-Host "=======================================================`n" -ForegroundColor Cyan
        $tunnelFound = $true
        break
    }
}

if (-not $tunnelFound) {
    Write-Host "Verifique os detalhes no arquivo server.log" -ForegroundColor Yellow
}

Write-Host "Status: Ativo!" -ForegroundColor Green
Write-Host "Acesse no celular: https://vudotsur.github.io/antigravity-remote/" -ForegroundColor Cyan
