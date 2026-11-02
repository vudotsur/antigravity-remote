# deploy.ps1
# Faz o commit das alterações e envia para o GitHub Pages (origin main)

param(
    [string]$Message = "feat: updates and enhancements to Antigravity Remote"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "Iniciando processo de deploy para o GitHub Pages..." -ForegroundColor Cyan

# Verifica status do repositório
git status --short

# Adiciona arquivos modificados e novos
git add -A

# Verifica se ha alteracoes para commitar
$status = git status --porcelain
if ($status) {
    Write-Host "Criando commit: '$Message'..." -ForegroundColor Cyan
    git commit -m "$Message"
} else {
    Write-Host "Nenhuma alteracao pendente para commit." -ForegroundColor Yellow
}

# Verifica token ou autenticação
$ghToken = $env:GITHUB_TOKEN
if (-not $ghToken) {
    $tokenFile = Join-Path $ScriptDir ".github_token"
    if (Test-Path $tokenFile) {
        $ghToken = (Get-Content $tokenFile -Raw).Trim()
    }
}

if ($ghToken) {
    Write-Host "Token GitHub detectado. Configurando credencial temporaria para push..." -ForegroundColor Cyan
    $repoUrl = "https://vudotsur:$ghToken@github.com/vudotsur/antigravity-remote.git"
    git push $repoUrl main
} else {
    Write-Host "Enviando commits para origin main..." -ForegroundColor Cyan
    try {
        git push origin main
    } catch {
        Write-Host "`n[ATENCAO] O Git necessita de autenticacao para fazer push." -ForegroundColor Yellow
        Write-Host "Execute uma das opcoes abaixo para autorizar:" -ForegroundColor Cyan
        Write-Host "  1. Autenticar com o GitHub CLI (Recomendado):" -ForegroundColor White
        Write-Host "     gh auth login" -ForegroundColor Green
        Write-Host "  2. Ou defina a variavel de ambiente com um Personal Access Token (PAT):" -ForegroundColor White
        Write-Host "     `$env:GITHUB_TOKEN = 'seu_token_aqui'" -ForegroundColor Green
        Write-Host "     .\deploy.ps1" -ForegroundColor Green
        Write-Host "  3. Ou salve seu token em um arquivo chamado .github_token nesta pasta." -ForegroundColor White
        exit 1
    }
}

Write-Host "`n[SUCESSO] Deploy enviado para o GitHub!" -ForegroundColor Green
Write-Host "O GitHub Pages atualizara a aplicacao automaticamente em alguns instantes:" -ForegroundColor Cyan
Write-Host "URL: https://vudotsur.github.io/antigravity-remote/" -ForegroundColor Green
