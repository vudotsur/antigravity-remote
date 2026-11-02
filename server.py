#!/usr/bin/env python3
"""
antigravity_remote_host.py / server.py
Host Daemon para o Antigravity Remote Client.
Gerencia:
1. Servidor WebSocket/HTTP na porta configurada (padrão: 8765).
2. Despacho de mensagens em tempo real via `agy agentapi send-message`.
3. Monitoramento e streaming em tempo real do transcript.jsonl.
4. Criação de túnel seguro Cloudflare (HTTPS/WSS) para acesso externo (celular/navegador).
5. Sincronização automática do endpoint no GitHub Pages via git/token se configurado.
"""

import argparse
import asyncio
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# Configure UTF-8 encoding for stdout/stderr to avoid Windows charmap encoding issues
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Paths & Directories
REPO_DIR = Path(__file__).resolve().parent
GEMINI_DIR = Path.home() / ".gemini" / "antigravity-cli"

def detect_active_conversation_id(override_id=None):
    """Detecta automaticamente o ID da sessão ativa do Antigravity."""
    if override_id:
        return override_id
    if os.environ.get("CONVERSATION_ID"):
        return os.environ.get("CONVERSATION_ID").strip()
    
    # 1. Verifica arquivo de lock em presence/
    presence_dir = GEMINI_DIR / "presence"
    if presence_dir.exists():
        locks = list(presence_dir.glob("*.lock"))
        if locks:
            locks.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return locks[0].stem

    # 2. Verifica o diretório brain mais recentemente modificado
    brain_dir = GEMINI_DIR / "brain"
    if brain_dir.exists():
        dirs = [d for d in brain_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if dirs:
            dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return dirs[0].name

    return "516bf843-c3ad-4899-890f-8a2b45a4866a"

def find_github_token():
    """Busca o token do GitHub por variáveis de ambiente, arquivos locais ou GitHub CLI."""
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ.get("GITHUB_TOKEN").strip()
    if os.environ.get("GH_TOKEN"):
        return os.environ.get("GH_TOKEN").strip()
    
    candidate_files = [
        REPO_DIR / ".github_token",
        Path.home() / ".github_token",
        Path.home() / "trafego" / "data" / ".github_token"
    ]
    for c in candidate_files:
        if c.exists():
            try:
                t = c.read_text(encoding="utf-8").strip()
                if t:
                    return t
            except Exception:
                pass
    
    gh_bin = shutil.which("gh")
    if gh_bin:
        try:
            res = subprocess.run([gh_bin, "auth", "token"], capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
            
    return None

# Command-line configuration
parser = argparse.ArgumentParser(description="Antigravity Remote Host Daemon")
parser.add_argument("--conversation-id", default=None, help="ID da conversa do Antigravity")
parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")), help="Porta WebSocket local")
parser.add_argument("--password", default=os.environ.get("ANTIGRAVITY_REMOTE_PASSWORD", "fleipe2026"), help="Senha mestra de acesso")
parser.add_argument("--no-tunnel", action="store_true", help="Não iniciar túnel Cloudflare")
parser.add_argument("--host", default="0.0.0.0", help="Endereço de bind do servidor")
args, _ = parser.parse_known_args()

CONVERSATION_ID = detect_active_conversation_id(args.conversation_id)
PORT = args.port
PASSWORD = args.password
HOST = args.host
USE_TUNNEL = not args.no_tunnel

AGY_BIN = shutil.which("agy") or "agy"
CLOUDFLARED_BIN = shutil.which("cloudflared") or "cloudflared"
GIT_BIN = shutil.which("git") or "git"

active_clients = set()
transcript_last_pos = 0

def get_transcript_path():
    return GEMINI_DIR / "brain" / CONVERSATION_ID / ".system_generated" / "logs" / "transcript.jsonl"

def get_recent_history(n=10):
    t_path = get_transcript_path()
    if not t_path.exists():
        return []
    history = []
    try:
        with open(t_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        for line in lines[-n:]:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            src = data.get("source", "")
            step_type = data.get("type", "")
            content = data.get("content", "")
            tools = data.get("tool_calls", [])
            created_at = data.get("created_at", "")
            time_str = created_at[11:16] if len(created_at) >= 16 else ""

            if src == "USER" or step_type == "USER_INPUT":
                history.append({
                    "source": "USER",
                    "type": "USER_INPUT",
                    "content": content or "Comando do Usuário",
                    "time": time_str
                })
            elif tools:
                for t in tools:
                    t_name = t.get("name", "tool")
                    t_args = t.get("args", {})
                    summary = t_args.get("toolSummary", t_name)
                    history.append({
                        "source": "MODEL",
                        "type": "TOOL_CALL",
                        "tool_name": t_name,
                        "summary": summary,
                        "content": json.dumps(t_args, indent=2, ensure_ascii=False),
                        "time": time_str
                    })
            elif content and step_type == "PLANNER_RESPONSE":
                history.append({
                    "source": "MODEL",
                    "type": "PLANNER_RESPONSE",
                    "content": content,
                    "time": time_str
                })
    except Exception as e:
        print(f"[HISTORY] Erro ao carregar histórico: {e}")
    return history

async def handle_ws_client(websocket):
    authenticated = False
    active_clients.add(websocket)
    client_addr = getattr(websocket, "remote_address", "client")
    print(f"[WS] Novo cliente conectado: {client_addr}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except Exception:
                continue

            msg_type = data.get("type")

            if msg_type == "auth":
                client_pass = data.get("password", "")
                if client_pass == PASSWORD:
                    authenticated = True
                    hist = get_recent_history(10)
                    host_label = f"{socket.gethostname()} ({platform.system()})"
                    await websocket.send(json.dumps({
                        "type": "auth_ok",
                        "host": host_label,
                        "conversation_id": CONVERSATION_ID,
                        "history": hist
                    }))
                    print(f"[WS] Cliente autenticado com sucesso! Host: {host_label}")
                else:
                    await websocket.send(json.dumps({
                        "type": "auth_fail"
                    }))
                    print("[WS] Falha de autenticação (senha incorreta)!")
                    await websocket.close()
                    break

            elif msg_type == "user_message" and authenticated:
                user_text = data.get("content", "").strip()
                if user_text:
                    print(f"[WS] Mensagem recebida: {user_text}")
                    # Dispatch to running session via agy agentapi
                    cmd = [AGY_BIN, "agentapi", "send-message", CONVERSATION_ID, user_text]
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                        print(f"[AGENTAPI] Despachado: code={res.returncode}")
                    except Exception as err:
                        print(f"[AGENTAPI] Erro ao despachar: {err}")

    except Exception as e:
        print(f"[WS] Conexão encerrada: {e}")
    finally:
        active_clients.discard(websocket)
        print("[WS] Cliente desconectado.")

async def transcript_monitor():
    global transcript_last_pos
    t_path = get_transcript_path()
    if t_path.exists():
        transcript_last_pos = t_path.stat().st_size

    while True:
        await asyncio.sleep(0.5)
        t_path = get_transcript_path()
        if not active_clients or not t_path.exists():
            continue
        try:
            cur_size = t_path.stat().st_size
            if cur_size > transcript_last_pos:
                with open(t_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(transcript_last_pos)
                    new_lines = f.readlines()
                    transcript_last_pos = f.tell()

                for line in new_lines:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        step_type = data.get("type", "")
                        content = data.get("content", "")
                        tools = data.get("tool_calls", [])
                        created_at = data.get("created_at", "")
                        time_str = created_at[11:16] if len(created_at) >= 16 else ""

                        item = None
                        if tools:
                            t = tools[0]
                            item = {
                                "source": "MODEL",
                                "type": "TOOL_CALL",
                                "tool_name": t.get("name", ""),
                                "summary": t.get("args", {}).get("toolSummary", t.get("name", "")),
                                "content": json.dumps(t.get("args", {}), indent=2, ensure_ascii=False),
                                "time": time_str
                            }
                        elif content and step_type == "PLANNER_RESPONSE":
                            item = {
                                "source": "MODEL",
                                "type": "PLANNER_RESPONSE",
                                "content": content,
                                "time": time_str
                            }

                        if item:
                            payload = json.dumps({"type": "msg_chunk", "item": item})
                            for ws in list(active_clients):
                                asyncio.create_task(ws.send(payload))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[MONITOR] Erro: {e}")

def push_endpoint_to_github(tunnel_url, host_info):
    """Grava o endpoint.json localmente e sincroniza com o GitHub Pages de forma assíncrona/segura."""
    endpoint_file = REPO_DIR / "endpoint.json"
    try:
        with open(endpoint_file, "w", encoding="utf-8") as f:
            json.dump({
                "url": tunnel_url,
                "updated_at": time.time(),
                "host": host_info
            }, f, indent=2)
        print(f"[ENDPOINT] Atualizado localmente ({host_info}): {tunnel_url}")
    except Exception as e:
        print(f"[ENDPOINT] Erro ao gravar endpoint.json: {e}")

    token = find_github_token()
    if not token:
        print("[GITHUB] GITHUB_TOKEN não configurado. O endpoint foi salvo localmente.")
        return

    try:
        remote_url = f"https://vudotsur:{token}@github.com/vudotsur/antigravity-remote.git"
        subprocess.run([GIT_BIN, "-C", str(REPO_DIR), "remote", "set-url", "origin", remote_url], capture_output=True, timeout=5)
        # Adiciona e commita ANTES do pull para evitar conflito de "unstaged changes"
        subprocess.run([GIT_BIN, "-C", str(REPO_DIR), "add", "endpoint.json"], capture_output=True, timeout=5)
        commit_res = subprocess.run([GIT_BIN, "-C", str(REPO_DIR), "commit", "-m", "chore: sync tunnel endpoint [skip ci]"], capture_output=True, timeout=5)
        if commit_res.returncode != 0:
            # Se não há nada para commitar (working tree clean), tudo bem — apenas faz push
            pass
        # Pull rebase silencioso após o commit local
        subprocess.run([GIT_BIN, "-C", str(REPO_DIR), "pull", "--rebase", "origin", "main"], capture_output=True, timeout=12)
        res = subprocess.run([GIT_BIN, "-C", str(REPO_DIR), "push", "origin", "main"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            print("[GITHUB] endpoint.json sincronizado com o GitHub Pages com sucesso!")
        else:
            print(f"[GITHUB] Aviso na sincronização: {res.stderr[:200]}")
    except Exception as e:
        print(f"[GITHUB] Falha não-bloqueante na sincronização do endpoint: {e}")

current_tunnel_url = None
tunnel_process = None

async def cloudflared_watchdog():
    """Watchdog permanente do túnel Cloudflare: auto-inicia, captura URL e auto-recupera se cair."""
    global current_tunnel_url, tunnel_process
    if not USE_TUNNEL:
        print("[TUNNEL] Modo local (--no-tunnel ativado).")
        return

    while True:
        print("[TUNNEL] Iniciando túnel Cloudflare seguro...")
        try:
            tunnel_process = subprocess.Popen(
                [CLOUDFLARED_BIN, "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        except Exception as e:
            print(f"[TUNNEL] Erro ao executar cloudflared: {e}. Tentando novamente em 10s...")
            await asyncio.sleep(10)
            continue

        captured_url = None
        start = time.time()
        while time.time() - start < 20:
            line = tunnel_process.stderr.readline()
            if "trycloudflare.com" in line:
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    captured_url = m.group(0)
                    break

        if captured_url:
            current_tunnel_url = captured_url
            host_info = f"{socket.gethostname()} ({platform.system()})"
            print(f"\n" + "="*60)
            print(f"🚀 TÚNEL ONLINE: {current_tunnel_url}")
            print(f"🔗 Acesse no celular / navegador: https://vudotsur.github.io/antigravity-remote/")
            print(f"="*60 + "\n")

            # Executa push em thread separada para não bloquear o servidor assíncrono
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, push_endpoint_to_github, current_tunnel_url, host_info)
        else:
            print("[TUNNEL] Aviso: URL do túnel não foi capturada. Monitorando processo...")

        # Monitora o processo do Cloudflare: se for desconectado, reinicia imediatamente
        while tunnel_process and tunnel_process.poll() is None:
            await asyncio.sleep(2)

        exit_code = tunnel_process.poll() if tunnel_process else -1
        print(f"[TUNNEL] Conexão Cloudflare encerrada (code={exit_code}). Reiniciando túnel em 3s...")
        await asyncio.sleep(3)

async def main():
    try:
        import websockets
    except ImportError:
        print("[ERRO] Pacote websockets não encontrado. Execute: pip install websockets")
        sys.exit(1)

    print(f"\nIniciando Antigravity Remote Host...")
    print(f"• Conversa Ativa: {CONVERSATION_ID}")
    print(f"• Diretório do Repositório: {REPO_DIR}")
    print(f"• Log do Transcript: {get_transcript_path()}")

    # 1. Inicia o servidor WebSocket PRIMEIRO (garante porta aberta)
    print(f"[SERVER] Abrindo WebSocket na porta {PORT} ({HOST})...")
    server = await websockets.serve(handle_ws_client, HOST, PORT)
    print(f"[SERVER] Servidor WebSocket ativo e aguardando conexões na porta {PORT}!")

    # 2. Inicia o monitor de transcrição e o watchdog do Cloudflare em background
    monitor_task = asyncio.create_task(transcript_monitor())
    tunnel_task = asyncio.create_task(cloudflared_watchdog())

    print("\n" + "="*60)
    print("💎 ANTIGRAVITY REMOTE HOST ATIVO")
    print(f"🔑 Senha mestra de acesso: {PASSWORD}")
    print(f"🌐 WebSocket local: ws://localhost:{PORT}")
    print("="*60 + "\n")

    try:
        await asyncio.gather(server.wait_closed(), monitor_task, tunnel_task)
    finally:
        if tunnel_process:
            try:
                tunnel_process.terminate()
            except Exception:
                pass
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
