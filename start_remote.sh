#!/usr/bin/env bash
# start_remote.sh
# Inicia o daemon do Antigravity Remote Host em background

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$DIR/server.pid"
LOGFILE="$DIR/server.log"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Servidor já está rodando (PID $(cat "$PIDFILE"))."
    exit 0
fi

echo "Iniciando Antigravity Remote Host..."
nohup python3 "$DIR/server.py" > "$LOGFILE" 2>&1 &
PID=$!
echo $PID > "$PIDFILE"
echo "Servidor iniciado com PID $PID."

# Aguarda a captura da URL do túnel no log
echo "Aguardando túnel seguro Cloudflare..."
for i in {1..20}; do
    if grep -q "trycloudflare.com" "$LOGFILE" 2>/dev/null; then
        grep "TÚNEL ONLINE" -A 1 "$LOGFILE" | head -n 2
        break
    fi
    sleep 1
done

echo "Status: Ativo!"
echo "Acesse: https://vudotsur.github.io/antigravity-remote/"
