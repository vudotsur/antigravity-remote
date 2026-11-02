#!/usr/bin/env python3
"""
antigravity_remote_host.py / server.py
Host Daemon para o Antigravity Remote Client (TeamViewer Proprietário).
Gerencia:
1. Servidor WebSocket/HTTP na porta 8765.
2. Injeção de mensagens na sessão atual via `agy agentapi send-message`.
3. Streaming em tempo real do transcript.jsonl.
4. Túnel seguro Cloudflare (HTTPS/WSS).
5. Sincronização automática do endpoint no GitHub Pages.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CONVERSATION_ID = "516bf843-c3ad-4899-890f-8a2b45a4866a"
PORT = 8765
PASSWORD_DEFAULT = "fleipe2026"
TRANSCRIPT_PATH = Path(f"/home/fleipe/.gemini/antigravity-cli/brain/{CONVERSATION_ID}/.system_generated/logs/transcript.jsonl")
GITHUB_TOKEN_PATH = Path("/home/fleipe/trafego/data/.github_token")
REPO_DIR = Path("/home/fleipe/antigravity-remote")

active_clients = set()
transcript_last_pos = 0

def get_recent_history(n=10):
    if not TRANSCRIPT_PATH.exists():
        return []
    history = []
    try:
        with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-n:]:
            data = json.loads(line)
            src = data.get("source", "")
            step_type = data.get("type", "")
            content = data.get("content", "")
            tools = data.get("tool_calls", [])
            
            if src == "USER" or step_type == "USER_INPUT":
                history.append({
                    "source": "USER",
                    "type": "USER_INPUT",
                    "content": content or "Comando do Usuário",
                    "time": data.get("created_at", "")[11:16]
                })
            elif tools:
                for t in tools:
                    t_name = t.get("name", "tool")
                    args = t.get("args", {})
                    summary = args.get("toolSummary", t_name)
                    history.append({
                        "source": "MODEL",
                        "type": "TOOL_CALL",
                        "tool_name": t_name,
                        "summary": summary,
                        "content": json.dumps(args, indent=2),
                        "time": data.get("created_at", "")[11:16]
                    })
            elif content and step_type == "PLANNER_RESPONSE":
                history.append({
                    "source": "MODEL",
                    "type": "PLANNER_RESPONSE",
                    "content": content,
                    "time": data.get("created_at", "")[11:16]
                })
    except Exception as e:
        print(f"Erro ao ler histórico: {e}")
    return history

async def handle_ws_client(websocket):
    authenticated = False
    active_clients.add(websocket)
    print(f"[WS] Novo cliente conectado: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "auth":
                client_pass = data.get("password", "")
                if client_pass == PASSWORD_DEFAULT:
                    authenticated = True
                    hist = get_recent_history(8)
                    await websocket.send(json.dumps({
                        "type": "auth_ok",
                        "host": "fleipe-pc (Linux)",
                        "history": hist
                    }))
                    print("[WS] Cliente autenticado com sucesso!")
                else:
                    await websocket.send(json.dumps({
                        "type": "auth_fail"
                    }))
                    print("[WS] Falha de autenticação!")
                    await websocket.close()
                    break
                    
            elif msg_type == "user_message" and authenticated:
                user_text = data.get("content", "").strip()
                if user_text:
                    print(f"[WS] Mensagem recebida do cliente: {user_text}")
                    # Dispatch to running session via agy agentapi
                    cmd = ["agy", "agentapi", "send-message", CONVERSATION_ID, user_text]
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                        print(f"[AGENTAPI] Despachado: code={res.returncode}")
                    except Exception as err:
                        print(f"[AGENTAPI] Erro ao despachar: {err}")
                        
    except Exception as e:
        print(f"[WS] Exceção na conexão: {e}")
    finally:
        active_clients.discard(websocket)
        print("[WS] Cliente desconectado.")

async def transcript_monitor():
    global transcript_last_pos
    if TRANSCRIPT_PATH.exists():
        transcript_last_pos = TRANSCRIPT_PATH.stat().st_size
    
    while True:
        await asyncio.sleep(0.5)
        if not active_clients or not TRANSCRIPT_PATH.exists():
            continue
        try:
            cur_size = TRANSCRIPT_PATH.stat().st_size
            if cur_size > transcript_last_pos:
                with open(TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
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
                        
                        item = None
                        if tools:
                            t = tools[0]
                            item = {
                                "source": "MODEL",
                                "type": "TOOL_CALL",
                                "tool_name": t.get("name", ""),
                                "summary": t.get("args", {}).get("toolSummary", t.get("name", "")),
                                "content": json.dumps(t.get("args", {}), indent=2),
                                "time": data.get("created_at", "")[11:16]
                            }
                        elif content and step_type == "PLANNER_RESPONSE":
                            item = {
                                "source": "MODEL",
                                "type": "PLANNER_RESPONSE",
                                "content": content,
                                "time": data.get("created_at", "")[11:16]
                            }
                            
                        if item:
                            payload = json.dumps({"type": "msg_chunk", "item": item})
                            for ws in list(active_clients):
                                asyncio.create_task(ws.send(payload))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[MONITOR] Erro: {e}")

async def start_cloudflared_and_sync():
    print("[TUNNEL] Iniciando túnel seguro Cloudflare...")
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    tunnel_url = None
    start = time.time()
    while time.time() - start < 15:
        line = proc.stderr.readline()
        if "trycloudflare.com" in line:
            m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if m:
                tunnel_url = m.group(0)
                break
                
    if not tunnel_url:
        print("[TUNNEL] Não foi possível capturar a URL do túnel automaticamente.")
        return proc, None
        
    print(f"\n=======================================================")
    print(f"🚀 TÚNEL ONLINE: {tunnel_url}")
    print(f"=======================================================\n")
    
    # Save endpoint.json in repo
    endpoint_file = REPO_DIR / "endpoint.json"
    with open(endpoint_file, "w") as f:
        json.dump({"url": tunnel_url, "updated_at": time.time()}, f, indent=2)
        
    # Push to GitHub Pages
    if GITHUB_TOKEN_PATH.exists():
        token = open(GITHUB_TOKEN_PATH).read().strip()
        try:
            remote_url = f"https://vudotsur:{token}@github.com/vudotsur/antigravity-remote.git"
            subprocess.run(["git", "-C", str(REPO_DIR), "remote", "remove", "origin"], stderr=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(REPO_DIR), "remote", "add", "origin", remote_url], check=True)
            subprocess.run(["git", "-C", str(REPO_DIR), "branch", "-M", "main"], check=True)
            subprocess.run(["git", "-C", str(REPO_DIR), "add", "."], check=True)
            subprocess.run(["git", "-C", str(REPO_DIR), "commit", "-m", "chore: sync tunnel endpoint and UI"], check=True)
            subprocess.run(["git", "-C", str(REPO_DIR), "push", "-u", "origin", "main", "--force"], check=True)
            print("[GITHUB] Repositório sincronizado com sucesso!")
        except Exception as e:
            print(f"[GITHUB] Erro ao sincronizar git: {e}")
            
    return proc, tunnel_url

async def main():
    import websockets
    
    tunnel_proc, tunnel_url = await start_cloudflared_and_sync()
    
    print(f"[SERVER] Abrindo WebSocket na porta {PORT}...")
    server = await websockets.serve(handle_ws_client, "0.0.0.0", PORT)
    
    monitor_task = asyncio.create_task(transcript_monitor())
    
    print("\n" + "="*60)
    print("💎 ANTIGRAVITY REMOTE (TEAMVIEWER PROPRIETÁRIO) ATIVO")
    print(f"🔗 Acesse no celular: https://vudotsur.github.io/antigravity-remote/")
    print(f"🔑 Senha mestra padrão: {PASSWORD_DEFAULT}")
    if tunnel_url:
        print(f"🌐 Túnel Cloudflare: {tunnel_url}")
    print("="*60 + "\n")
    
    try:
        await asyncio.gather(server.wait_closed(), monitor_task)
    finally:
        if tunnel_proc:
            tunnel_proc.terminate()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
