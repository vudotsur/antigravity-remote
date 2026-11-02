#!/usr/bin/env bash
# deploy.sh
# Faz o commit das alterações e envia para o GitHub Pages (origin main)

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

MESSAGE="${1:-feat: updates and enhancements to Antigravity Remote}"

echo "Iniciando processo de deploy para o GitHub Pages..."

git status --short
git add -A

if [ -n "$(git status --porcelain)" ]; then
    echo "Criando commit: '$MESSAGE'..."
    git commit -m "$MESSAGE"
else
    echo "Nenhuma alteração pendente para commit."
fi

GH_TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$GH_TOKEN" ] && [ -f "$DIR/.github_token" ]; then
    GH_TOKEN="$(cat "$DIR/.github_token" | tr -d '\r\n')"
fi

if [ -n "$GH_TOKEN" ]; then
    echo "Token GitHub detectado. Enviando via token..."
    REPO_URL="https://vudotsur:${GH_TOKEN}@github.com/vudotsur/antigravity-remote.git"
    git push "$REPO_URL" main
else
    echo "Enviando commits para origin main..."
    if ! git push origin main; then
        echo ""
        echo "[ATENÇÃO] O Git necessita de autenticação para fazer push."
        echo "Opções para autorizar:"
        echo "  1. Autenticar com o GitHub CLI: gh auth login"
        echo "  2. Ou defina: export GITHUB_TOKEN='seu_token'"
        echo "  3. Ou salve seu token em .github_token"
        exit 1
    fi
fi

echo ""
echo "[SUCESSO] Deploy enviado para o GitHub!"
echo "URL: https://vudotsur.github.io/antigravity-remote/"
