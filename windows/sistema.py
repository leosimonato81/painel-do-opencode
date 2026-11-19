"""Tudo o que depende do sistema operacional fica neste arquivo.

O app foi feito para Windows 10/11. O suporte a Linux existe só para desenvolvimento e testes.
"""

import json
import os
import shutil
import socket
import subprocess
import sys

WINDOWS = sys.platform == "win32"
SEM_JANELA = 0x08000000 if WINDOWS else 0  # CREATE_NO_WINDOW: não pisca console no Windows
HOME = os.path.expanduser("~")

NOME_APP = "Painel do OpenCode"
REGRA_FIREWALL = "OpenCodePainelCelular"
ATALHO_INICIO = "OpenCode - inicio automatico.lnk"


def rodar(args, timeout=40):
    """Roda um comando e devolve (código, saída, erro), sem abrir janela de console."""
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=HOME,
            stdin=subprocess.DEVNULL,  # app sem console: sem isto o PowerShell fica esperando entrada
            creationflags=SEM_JANELA, encoding="utf-8", errors="replace",
        )
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


def powershell(comando, timeout=40):
    return rodar(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", comando], timeout)


def pasta_estado():
    base = os.environ.get("APPDATA", HOME) if WINDOWS else os.path.join(HOME, ".config")
    return os.path.join(base, "OpenCodePainel")


# --------------------------------------------------------------------------- OpenCode
def achar_opencode():
    """Procura o executável do OpenCode nos lugares onde os instaladores oficiais o colocam."""
    candidatos = [shutil.which("opencode")]
    if WINDOWS:
        candidatos += [
            os.path.join(HOME, ".opencode", "bin", "opencode.exe"),
            os.path.join(os.environ.get("APPDATA", ""), "npm", "opencode.cmd"),
        ]
    else:
        candidatos += [os.path.join(HOME, ".opencode", "bin", "opencode")]
    for c in candidatos:
        if c and os.path.isfile(c):
            return c
    return None


class OpenCode:
    def __init__(self, exe):
        self.exe = exe
        self._pastas = None

    def _oc(self, *args, timeout=40):
        return rodar([self.exe, *args], timeout)

    def versao(self):
        _, saida, _ = self._oc("--version", timeout=20)
        return saida.replace("opencode", "").strip() or "?"

    def pastas(self):
        """Pastas do OpenCode, como o próprio OpenCode informa (`opencode debug paths`)."""
        if self._pastas is None:
            _, saida, _ = self._oc("debug", "paths", timeout=20)
            pastas = {}
            for linha in saida.splitlines():
                partes = linha.split(None, 1)
                if len(partes) == 2:
                    pastas[partes[0]] = partes[1].strip()
            if "config" not in pastas:
                pastas["config"] = os.path.join(HOME, ".config", "opencode")
            self._pastas = pastas
        return self._pastas

    @property
    def arquivo_servico(self):
        return os.path.join(self.pastas()["config"], "service.json")

    def status_url(self):
        _, saida, _ = self._oc("service", "status")
        linha = saida.splitlines()[0].strip() if saida else ""
        return None if not linha or linha == "stopped" else linha

    def ligar(self):
        self._oc("service", "start")

    def desligar(self):
        self._oc("service", "stop")

    def reiniciar(self):
        self._oc("service", "restart")

    # ----- configuração do serviço (service.json)
    def _ler_config(self):
        try:
            # utf-8-sig: aceita também arquivos gravados pelo PowerShell (com BOM no início)
            with open(self.arquivo_servico, encoding="utf-8-sig") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _gravar_config(self, dados):
        os.makedirs(os.path.dirname(self.arquivo_servico), exist_ok=True)
        tmp = self.arquivo_servico + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2)
        os.replace(tmp, self.arquivo_servico)

    def acesso_rede(self):
        return self._ler_config().get("hostname") == "0.0.0.0"

    def definir_acesso_rede(self, ligado):
        dados = self._ler_config()
        dados["hostname"] = "0.0.0.0" if ligado else "127.0.0.1"
        self._gravar_config(dados)

    def gravar_senha(self, senha):
        dados = self._ler_config()
        dados["password"] = senha
        self._gravar_config(dados)


# --------------------------------------------------------------------------- rede
def ip_local():
    """IP deste PC na rede local. Não envia nada: só pergunta ao sistema qual rota usaria."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None
    finally:
        s.close()


def porta_da_url(url):
    try:
        return int(url.rsplit(":", 1)[-1].strip("/"))
    except (ValueError, AttributeError):
        return None


# --------------------------------------------------------------------------- firewall
def porta_liberada_firewall():
    """Porta liberada pela regra do painel no firewall do Windows (None se não houver regra)."""
    if not WINDOWS:
        return None
    _, saida, _ = powershell(
        f"(Get-NetFirewallRule -Name '{REGRA_FIREWALL}' -ErrorAction SilentlyContinue"
        " | Get-NetFirewallPortFilter).LocalPort"
    )
    try:
        return int(saida.splitlines()[0])
    except (ValueError, IndexError):
        return None


def liberar_firewall(porta):
    """Cria (ou recria) a regra do firewall. O Windows pede permissão de administrador."""
    if not WINDOWS:
        return False
    import ctypes

    script = (
        f"Remove-NetFirewallRule -Name '{REGRA_FIREWALL}' -ErrorAction SilentlyContinue; "
        f"New-NetFirewallRule -Name '{REGRA_FIREWALL}' -DisplayName 'OpenCode (acesso pelo celular)' "
        f"-Direction Inbound -Protocol TCP -LocalPort {int(porta)} -RemoteAddress LocalSubnet "
        "-Action Allow -Profile Any"
    )
    parametros = f'-NoProfile -WindowStyle Hidden -Command "{script}"'
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", parametros, None, 0)
    return r > 32  # > 32 = o Windows aceitou abrir (a regra aparece em alguns segundos)


# --------------------------------------------------------------------------- app OpenCode (desktop)
def achar_app_desktop():
    """Procura o app OpenCode (versão com interface) instalado."""
    if not WINDOWS:
        p = "/opt/OpenCode/ai.opencode"
        return p if os.path.isfile(p) else None
    local = os.environ.get("LOCALAPPDATA", "")
    candidatos = [
        os.path.join(local, "Programs", "OpenCode", "OpenCode.exe"),
        os.path.join(local, "Programs", "opencode-desktop", "OpenCode.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "OpenCode", "OpenCode.exe"),
    ]
    try:  # programas instalados registrados no Windows
        import winreg

        for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                chave = winreg.OpenKey(raiz, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
            except OSError:
                continue
            for i in range(winreg.QueryInfoKey(chave)[0]):
                try:
                    sub = winreg.OpenKey(chave, winreg.EnumKey(chave, i))
                    nome = winreg.QueryValueEx(sub, "DisplayName")[0]
                    if "opencode" in str(nome).lower():
                        icone = str(winreg.QueryValueEx(sub, "DisplayIcon")[0]).split(",")[0].strip('"')
                        candidatos.insert(0, icone)
                except OSError:
                    continue
    except ImportError:
        pass
    for c in candidatos:
        if c and c.lower().endswith(".exe") and os.path.isfile(c):
            return c
    return None


# --------------------------------------------------------------------------- início automático
MODOS = ["Com interface", "Sem interface", "Não inicia"]


def _pasta_inicializar():
    if WINDOWS:
        return os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    return os.path.join(HOME, ".config", "autostart")


def _comando_proprio(*args):
    """Como chamar este próprio app (executável empacotado ou script em desenvolvimento)."""
    if getattr(sys, "frozen", False):
        return sys.executable, list(args)
    python = sys.executable
    if WINDOWS:
        pythonw = os.path.join(os.path.dirname(python), "pythonw.exe")
        python = pythonw if os.path.isfile(pythonw) else python
    return python, [os.path.abspath(sys.argv[0]), *args]


def modo_inicio():
    pasta = _pasta_inicializar()
    if WINDOWS:
        atalho = os.path.join(pasta, ATALHO_INICIO)
        if not os.path.isfile(atalho):
            return "Não inicia"
        _, alvo, _ = powershell(f"(New-Object -ComObject WScript.Shell).CreateShortcut('{atalho}').Arguments")
        return "Sem interface" if "--iniciar-servico" in alvo else "Com interface"
    arquivo = os.path.join(pasta, "opencode-painel-qt.desktop")
    if not os.path.isfile(arquivo):
        return "Não inicia"
    with open(arquivo, encoding="utf-8") as f:
        return "Sem interface" if "--iniciar-servico" in f.read() else "Com interface"


def gravar_modo_inicio(modo, app_desktop):
    pasta = _pasta_inicializar()
    os.makedirs(pasta, exist_ok=True)
    if modo == "Com interface":
        alvo, argumentos = app_desktop, []
    else:
        alvo, argumentos = _comando_proprio("--iniciar-servico")

    if WINDOWS:
        atalho = os.path.join(pasta, ATALHO_INICIO)
        if modo == "Não inicia":
            if os.path.exists(atalho):
                os.remove(atalho)
            return True
        args = " ".join(f'"{a}"' for a in argumentos).replace("'", "''")
        codigo, _, erro = powershell(
            f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{atalho}'); "
            f"$s.TargetPath = '{alvo}'; $s.Arguments = '{args}'; $s.WindowStyle = 7; "
            "$s.Description = 'Criado pelo Painel do OpenCode'; $s.Save()"
        )
        return codigo == 0

    arquivo = os.path.join(pasta, "opencode-painel-qt.desktop")
    if modo == "Não inicia":
        if os.path.exists(arquivo):
            os.remove(arquivo)
        return True
    comando = " ".join([alvo, *argumentos])
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write(f"[Desktop Entry]\nType=Application\nName=OpenCode (início automático)\nExec={comando}\nNoDisplay=true\n")
    return True
