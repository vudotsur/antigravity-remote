# ⚡ Antigravity Remote Host & Client

> **Google Antigravity Proprietary Remote Control Client (Real-Time Web Terminal)**

O **Antigravity Remote** transforma qualquer celular, tablet ou outro computador em um terminal remoto de controle em tempo real para o seu ambiente local do **Google Antigravity (AGY)**.

---

## 🌟 Funcionalidades

- **Controle Remoto em Tempo Real**: Envie comandos e prompts para a sessão ativa do Antigravity direto do celular.
- **Streaming de Respostas & Tool Calls**: Visualize mensagens, comandos executados, diffs e respostas do agente instantaneamente via WebSocket.
- **Túnel Seguro Automático**: Criação automática de túnel HTTPS/WSS via Cloudflare (`trycloudflare.com`), sem precisar abrir portas no roteador ou configurar IP público.
- **Auto-Discovery do Endpoint**: A interface web busca automaticamente o endereço do túnel via `endpoint.json`, sem necessidade de copiar e colar URLs manuais.
- **Cross-Platform**: Suporte nativo completo para **Windows**, **Linux** e **macOS**.
- **Autenticação Segura**: Proteção por senha mestra para conexões WebSocket.
- **Deploy Automático no GitHub Pages**: O client estático roda direto no GitHub Pages (`https://<user>.github.io/antigravity-remote/`).

---

## 🚀 Como Clonar, Configurar e Executar

### 1. Clonar o Repositório

```bash
git clone https://github.com/vudotsur/antigravity-remote.git
cd antigravity-remote
```

### 2. Instalar Dependências

Certifique-se de ter o **Python 3.10+** e o pacote `websockets` instalado:

```bash
pip install -r requirements.txt
```

Além disso, para acesso remoto externo, tenha o **cloudflared** instalado:
- **Windows**: `winget install Cloudflare.cloudflared`
- **Linux**: `sudo apt install cloudflared` ou baixe do repositório oficial da Cloudflare.

---

## 💻 Como Iniciar o Servidor

### No Windows:
Você pode simplesmente dar um duplo clique em:
- `start_remote.bat`

Ou rodar via PowerShell:
```powershell
.\start_remote.ps1
```

Para encerrar o servidor e o túnel:
- Execute `stop_remote.bat` ou `.\stop_remote.ps1`

---

### No Linux / macOS:
```bash
chmod +x start_remote.sh stop_remote.sh deploy.sh
./start_remote.sh
```

Para encerrar:
```bash
./stop_remote.sh
```

---

## 📱 Acessando no Celular

1. Abra o navegador no seu smartphone e acesse:
   **[https://vudotsur.github.io/antigravity-remote/](https://vudotsur.github.io/antigravity-remote/)**
2. O campo **URL do Túnel** será preenchido automaticamente graças ao auto-discovery de `endpoint.json`.
3. Digite sua senha mestra (padrão: `fleipe2026` ou configurada via `ANTIGRAVITY_REMOTE_PASSWORD`).
4. Clique em **Conectar ao Terminal** e pronto! Você está conectado ao Antigravity da sua máquina.

---

## 🛠️ Como Editar e Personalizar

### Estrutura dos Arquivos:
- `server.py`: O daemon Python que gerencia o WebSocket, monitora o log `transcript.jsonl`, despacha prompts via `agy agentapi send-message` e cria o túnel Cloudflare.
- `index.html`: A aplicação Single Page responsiva (HTML5, CSS moderno e JS com Marked.js para markdown).
- `endpoint.json`: Arquivo que armazena a URL ativa do túnel Cloudflare atual.
- `start_remote.ps1` / `start_remote.bat`: Scripts de inicialização para Windows.
- `stop_remote.ps1` / `stop_remote.bat`: Scripts de parada para Windows.
- `start_remote.sh` / `stop_remote.sh`: Scripts para Linux/macOS.
- `deploy.ps1` / `deploy.sh`: Scripts automatizados para deploy no GitHub Pages.

### Opções do Servidor (`server.py`):
```bash
python server.py --help

Opções:
  --conversation-id ID   Define manualmente o ID da sessão do Antigravity
  --port PORT            Porta local do servidor WebSocket (padrão: 8765)
  --password SENHA       Define a senha mestra de autenticação
  --no-tunnel            Executa apenas em localhost/rede local (sem Cloudflare)
```

Variáveis de Ambiente suportadas:
- `ANTIGRAVITY_REMOTE_PASSWORD`: Senha de acesso customizada.
- `CONVERSATION_ID`: ID forçado da conversa.
- `PORT`: Porta do servidor.
- `GITHUB_TOKEN`: Token para push automático do `endpoint.json` ao iniciar o servidor.

---

## 🚢 Como Fazer Deploy

Todas as alterações feitas na interface web (`index.html`) ou na aplicação podem ser enviadas diretamente para o **GitHub Pages**:

### No Windows (PowerShell):
```powershell
.\deploy.ps1 -Message "Sua mensagem de commit aqui"
```

### No Linux / macOS:
```bash
./deploy.sh "Sua mensagem de commit aqui"
```

> **Autenticação para Push**:
> Se ainda não autenticou o Git ou GitHub CLI, basta rodar uma única vez:
> ```bash
> gh auth login
> ```
> Ou definir a variável `$env:GITHUB_TOKEN = 'seu_token'` antes de rodar o deploy.

---

## 🔒 Segurança

- O túnel Cloudflare gera uma URL randômica com criptografia TLS de ponta a ponta (`https://` e `wss://`).
- Nenhuma porta precisa ser aberta no firewall ou roteador.
- Somente clientes com a senha mestra correta têm acesso a enviar mensagens ou ler a saída do terminal.
