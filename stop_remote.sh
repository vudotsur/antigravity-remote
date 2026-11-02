#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$DIR/server.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    PID=$(cat "$PIDFILE")
    echo "Encerrando Antigravity Remote Host (PID $PID)..."
    kill "$PID" 2>/dev/null
    pkill -P "$PID" 2>/dev/null
    rm -f "$PIDFILE"
    echo "Encerrado com sucesso."
else
    echo "Nenhum servidor rodando."
    rm -f "$PIDFILE"
fi
