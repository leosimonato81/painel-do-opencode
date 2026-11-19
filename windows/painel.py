"""Painel do OpenCode para Windows 10/11.

Liga/desliga o serviço do OpenCode, mostra os endereços, libera o acesso pelo celular,
troca a senha e escolhe o que acontece ao entrar no Windows.
"""

import json
import os
import sys
import threading

import sistema
from sistema import MODOS, NOME_APP

SENHA_MIN = 12
DESCRICAO_MODO = {
    "Com interface": "Abre o app OpenCode (ele liga o serviço)",
    "Sem interface": "Só liga o serviço, para usar pelo celular",
    "Não inicia": "Nada liga sozinho",
}


# --------------------------------------------------------------------------- modo sem janela
def iniciar_servico_e_sair():
    """Usado pelo início automático "Sem interface": liga o serviço e termina, sem abrir janela."""
    exe = sistema.achar_opencode()
    if exe:
        sistema.OpenCode(exe).ligar()


if "--iniciar-servico" in sys.argv:
    iniciar_servico_e_sair()
    sys.exit(0)


# --------------------------------------------------------------------------- interface
from PySide6.QtCore import QLockFile, QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

AZUL = QColor(53, 132, 228)


def caminho_recurso(nome):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


def ler_estado():
    try:
        with open(os.path.join(sistema.pasta_estado(), "estado.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def gravar_estado(**valores):
    estado = ler_estado()
    estado.update(valores)
    os.makedirs(sistema.pasta_estado(), exist_ok=True)
    with open(os.path.join(sistema.pasta_estado(), "estado.json"), "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2)


class Tarefa(QObject):
    """Roda trabalho lento fora da interface e devolve o resultado na thread da interface."""
    pronto = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.pronto.connect(lambda fn, r: fn(r))

    def rodar(self, trabalho, ao_terminar):
        threading.Thread(target=lambda: self.pronto.emit(ao_terminar, trabalho()), daemon=True).start()


# ----- componentes visuais
class Interruptor(QAbstractButton):
    """Interruptor liga/desliga (o Qt não tem um pronto)."""

    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)

    def sizeHint(self):
        return QSize(46, 26)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ligado = self.isChecked()
        fundo = AZUL if ligado else self.palette().mid().color()
        if not self.isEnabled():
            fundo = fundo.lighter(140)
        p.setPen(Qt.NoPen)
        p.setBrush(fundo)
        p.drawRoundedRect(QRectF(0, 0, 46, 26), 13, 13)
        p.setBrush(QColor("white"))
        x = 23 if ligado else 3
        p.drawEllipse(QRectF(x, 3, 20, 20))


def icone_olho(aberto, cor):
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(cor, 1.6))
    caminho = QPainterPath()
    caminho.moveTo(2, 10)
    caminho.quadTo(10, 2, 18, 10)
    caminho.quadTo(10, 18, 2, 10)
    p.drawPath(caminho)
    p.setBrush(cor)
    p.drawEllipse(QPointF(10, 10), 2.6, 2.6)
    if not aberto:
        p.drawLine(QPointF(3, 17), QPointF(17, 3))
    p.end()
    return QIcon(pm)


class CampoSenha(QLineEdit):
    """Campo de senha: o olho de mostrar/ocultar só aparece depois de digitar algo."""

    def __init__(self, dica):
        super().__init__()
        self.setPlaceholderText(dica)
        self.setEchoMode(QLineEdit.Password)
        self.setMinimumHeight(34)
        cor = self.palette().text().color()
        self._icones = (icone_olho(True, cor), icone_olho(False, cor))
        self.olho = QAction(self._icones[0], "Mostrar senha", self)
        self.olho.triggered.connect(self._alternar)
        self.addAction(self.olho, QLineEdit.TrailingPosition)
        self.olho.setVisible(False)  # depois do addAction: antes disso o Windows ignora
        self.textChanged.connect(self._ao_mudar)

    def _alternar(self):
        visivel = self.echoMode() == QLineEdit.Password
        self.setEchoMode(QLineEdit.Normal if visivel else QLineEdit.Password)
        self.olho.setIcon(self._icones[1] if visivel else self._icones[0])
        self.olho.setText("Ocultar senha" if visivel else "Mostrar senha")

    def _ao_mudar(self, texto):
        self.olho.setVisible(bool(texto))
        if not texto and self.echoMode() == QLineEdit.Normal:
            self._alternar()  # volta a ocultar quando o campo é apagado


class Cartao(QFrame):
    """Grupo de linhas com título, no estilo de configurações."""

    def __init__(self, titulo, descricao=None):
        super().__init__()
        fora = QVBoxLayout(self)
        fora.setContentsMargins(0, 0, 0, 0)
        fora.setSpacing(6)
        rotulo = QLabel(titulo)
        rotulo.setObjectName("tituloCartao")
        fora.addWidget(rotulo)
        if descricao:
            d = QLabel(descricao)
            d.setWordWrap(True)
            d.setObjectName("descricao")
            fora.addWidget(d)
        self.caixa = QFrame()
        self.caixa.setObjectName("caixa")
        self.linhas = QVBoxLayout(self.caixa)
        self.linhas.setContentsMargins(0, 0, 0, 0)
        self.linhas.setSpacing(0)
        fora.addWidget(self.caixa)

    def adicionar(self, widget):
        widget.separador = None
        if self.linhas.count():
            sep = QFrame()
            sep.setObjectName("separador")
            sep.setFixedHeight(1)
            self.linhas.addWidget(sep)
            widget.separador = sep
        self.linhas.addWidget(widget)
        return widget


def mostrar_linha(linha, visivel):
    """Mostra/esconde uma linha junto com a divisória dela."""
    linha.setVisible(visivel)
    if getattr(linha, "separador", None) is not None:
        linha.separador.setVisible(visivel)


class Linha(QWidget):
    """Linha com título, subtítulo e um controle à direita."""

    def __init__(self, titulo, subtitulo="", controle=None):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 10, 14, 10)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.titulo = QLabel(titulo)
        self.titulo.setObjectName("tituloLinha")
        self.subtitulo = QLabel(subtitulo)
        self.subtitulo.setObjectName("subtitulo")
        self.subtitulo.setWordWrap(True)
        self.subtitulo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.subtitulo.setVisible(bool(subtitulo))
        textos.addWidget(self.titulo)
        textos.addWidget(self.subtitulo)
        h.addLayout(textos, 1)
        if controle is not None:
            h.addWidget(controle, 0, Qt.AlignVCenter)

    def definir_subtitulo(self, texto):
        self.subtitulo.setText(texto)
        self.subtitulo.setVisible(bool(texto))


def botao(texto, principal=False, plano=False):
    b = QPushButton(texto)
    b.setCursor(Qt.PointingHandCursor)
    if principal:
        b.setObjectName("principal")
    if plano:
        b.setObjectName("plano")
    return b


ESTILO = """
QWidget#raiz { background: palette(window); }
QLabel#tituloCartao { font-weight: 600; font-size: 10.5pt; margin-left: 2px; }
QLabel#descricao, QLabel#subtitulo { color: palette(placeholder-text); }
QLabel#tituloLinha { font-size: 10pt; }
QFrame#caixa { background: palette(base); border: 1px solid palette(mid); border-radius: 10px; }
QFrame#separador { background: palette(midlight); margin: 0 12px; }
QPushButton { padding: 6px 14px; border-radius: 6px; }
QPushButton#principal { background: #3584e4; color: white; border: none; font-weight: 600; }
QPushButton#principal:disabled { background: palette(mid); color: palette(placeholder-text); }
QPushButton#plano { background: transparent; border: none; color: #3584e4; }
QPushButton#plano:hover { text-decoration: underline; }
QLabel#aviso { background: #323232; color: white; border-radius: 8px; padding: 8px 14px; }
QLabel#alerta { color: #c01c28; }
QLineEdit { border: 1px solid palette(mid); border-radius: 6px; padding: 4px 8px; background: palette(base); }
QLineEdit[erro="true"] { border-color: #c01c28; }
"""


# ----- janela principal
class Painel(QWidget):
    def __init__(self, oc):
        super().__init__()
        self.oc = oc
        self.tarefa = Tarefa()
        self.ocupado = False
        self.atualizando = False
        self.url = None
        self.app_desktop = sistema.achar_app_desktop()
        self.ajuda_pendente = not ler_estado().get("ajuda_celular_vista", False)

        self.setObjectName("raiz")
        self.setWindowTitle(NOME_APP)
        self.setWindowIcon(QIcon(caminho_recurso("icone.png")))
        self.resize(500, 720)
        self.setStyleSheet(ESTILO)

        rolagem = QScrollArea(self)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        conteudo.setObjectName("raiz")
        self.coluna = QVBoxLayout(conteudo)
        self.coluna.setContentsMargins(22, 18, 22, 22)
        self.coluna.setSpacing(22)
        rolagem.setWidget(conteudo)
        base = QVBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)
        base.addWidget(rolagem)

        self._montar_servico()
        self._montar_celular()
        self._montar_inicio()
        self._montar_senha()
        self.coluna.addStretch(1)

        rodape = QLabel(f"OpenCode {oc.versao()}")
        rodape.setObjectName("descricao")
        rodape.setAlignment(Qt.AlignCenter)
        self.coluna.addWidget(rodape)

        self.aviso_label = QLabel(self)
        self.aviso_label.setObjectName("aviso")
        self.aviso_label.hide()
        self._timer_aviso = QTimer(self, singleShot=True, timeout=self.aviso_label.hide)

        self.atualizar()
        QTimer(self, interval=4000, timeout=self._periodico).start()

    # ----- montagem das seções
    def _montar_servico(self):
        c = Cartao("Serviço")
        self.chave = Interruptor()
        self.chave.toggled.connect(self.ao_alternar)
        self.linha_chave = c.adicionar(Linha("Serviço do OpenCode", "Verificando…", self.chave))
        self.bt_reiniciar = botao("Reiniciar")
        self.bt_reiniciar.clicked.connect(self.ao_reiniciar)
        c.adicionar(Linha("Reiniciar", "Aplica mudanças de configuração", self.bt_reiniciar))
        bt_pc = botao("Copiar")
        bt_pc.clicked.connect(lambda: self.copiar(self.linha_pc.subtitulo.text()))
        self.linha_pc = c.adicionar(Linha("Endereço neste PC", "—", bt_pc))
        self.coluna.addWidget(c)

    def _montar_celular(self):
        c = Cartao("Acesso pelo celular", "Use o OpenCode no celular, conectado ao mesmo Wi-Fi deste PC.")
        self.chave_rede = Interruptor()
        self.chave_rede.toggled.connect(self.ao_alternar_rede)
        self.linha_rede = c.adicionar(Linha("Permitir acesso pela rede", "", self.chave_rede))

        self.bt_firewall = botao("Liberar")
        self.bt_firewall.clicked.connect(self.ao_liberar_firewall)
        self.linha_firewall = c.adicionar(Linha("Firewall do Windows", "", self.bt_firewall))
        mostrar_linha(self.linha_firewall, False)  # aparece quando o status carregar

        controles = QWidget()
        h = QHBoxLayout(controles)
        h.setContentsMargins(0, 0, 0, 0)
        bt_copiar = botao("Copiar")
        bt_copiar.clicked.connect(lambda: self.copiar(self.linha_cel.subtitulo.text()))
        bt_ajuda = botao("Como configurar", plano=True)
        bt_ajuda.clicked.connect(lambda: self.mostrar_ajuda_celular())
        h.addWidget(bt_ajuda)
        h.addWidget(bt_copiar)
        self.linha_cel = c.adicionar(Linha("Endereço para o celular", "—", controles))
        self.cartao_celular = c
        self.coluna.addWidget(c)

    def _montar_inicio(self):
        c = Cartao("Ao entrar no Windows")
        self.combo = QComboBox()
        self.combo.addItems(MODOS)
        if not self.app_desktop:
            item = self.combo.model().item(0)
            item.setEnabled(False)
            item.setToolTip("O app OpenCode (com interface) não foi encontrado neste PC")
        atual = sistema.modo_inicio()
        self.combo.setCurrentText(atual)
        self.combo.currentTextChanged.connect(self.ao_escolher_modo)
        self.linha_modo = c.adicionar(Linha("Ao fazer login", DESCRICAO_MODO[atual], self.combo))
        self.coluna.addWidget(c)

    def _montar_senha(self):
        c = Cartao(
            "Trocar senha",
            f"Senha do serviço. Mínimo de {SENHA_MIN} caracteres. "
            "Depois de trocar, atualize no app do celular.",
        )
        caixa = QWidget()
        v = QVBoxLayout(caixa)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        self.senha1 = CampoSenha("Nova senha")
        self.senha2 = CampoSenha("Repita a nova senha")
        for campo in (self.senha1, self.senha2):
            campo.textChanged.connect(self.ao_digitar_senha)
            v.addWidget(campo)
        self.bt_senha = botao("Salvar nova senha", principal=True)
        self.bt_senha.setEnabled(False)
        self.bt_senha.clicked.connect(self.ao_salvar_senha)
        v.addWidget(self.bt_senha)
        c.adicionar(caixa)
        self.coluna.addWidget(c)

    # ----- utilidades
    def aviso(self, texto):
        self.aviso_label.setText(texto)
        self.aviso_label.adjustSize()
        x = (self.width() - self.aviso_label.width()) // 2
        self.aviso_label.move(x, self.height() - self.aviso_label.height() - 18)
        self.aviso_label.show()
        self.aviso_label.raise_()
        self._timer_aviso.start(3000)

    def copiar(self, texto):
        if texto and texto.startswith("http"):
            QGuiApplication.clipboard().setText(texto)
            self.aviso("Endereço copiado")

    def endereco_celular(self):
        if not self.url or not self.oc.acesso_rede():
            return None
        ip = sistema.ip_local()
        porta = sistema.porta_da_url(self.url)
        return f"http://{ip}:{porta}" if ip and porta else None

    # ----- estado
    def _periodico(self):
        if not self.ocupado:
            self.atualizar()

    def atualizar(self):
        def trabalho():
            url = self.oc.status_url()
            porta = sistema.porta_da_url(url) if url else None
            return url, self.oc.acesso_rede(), porta, sistema.porta_liberada_firewall()

        self.tarefa.rodar(trabalho, self._mostrar_status)

    def _mostrar_status(self, resultado):
        if self.ocupado:
            return
        url, rede, porta, porta_fw = resultado
        self.url = url
        ligado = url is not None
        self.atualizando = True
        self.chave.setChecked(ligado)
        self.chave_rede.setChecked(rede)
        self.atualizando = False

        self.linha_chave.definir_subtitulo("Ligado" if ligado else "Desligado")
        self.bt_reiniciar.setEnabled(ligado)
        self.linha_pc.definir_subtitulo(f"http://127.0.0.1:{porta}" if ligado else "Ligue o serviço")

        self.linha_rede.definir_subtitulo(
            "Ligado: aparelhos do seu Wi-Fi podem acessar (com a senha)" if rede
            else "Desligado: só este PC acessa"
        )
        mostrar_linha(self.linha_firewall, sistema.WINDOWS and rede)
        if porta and porta_fw == porta:
            self.linha_firewall.definir_subtitulo("Liberado para a sua rede local ✓")
            self.bt_firewall.setVisible(False)
        elif not porta:
            self.linha_firewall.definir_subtitulo("Ligue o serviço para conferir")
            self.bt_firewall.setVisible(False)
        else:
            self.linha_firewall.definir_subtitulo("A porta está bloqueada: o celular não vai conectar")
            self.bt_firewall.setVisible(True)

        end = self.endereco_celular()
        self.linha_cel.definir_subtitulo(
            end or ("Ligue o serviço" if not ligado else "Ative o acesso pela rede")
        )

        if self.ajuda_pendente:
            self.ajuda_pendente = False
            QTimer.singleShot(300, lambda: self.mostrar_ajuda_celular(primeira_vez=True))

    def _executar(self, rotulo, acao, mensagem_ok, conferir):
        self.ocupado = True
        self.chave.setEnabled(False)
        self.bt_reiniciar.setEnabled(False)
        self.linha_chave.definir_subtitulo(rotulo)

        def trabalho():
            acao()
            return self.oc.status_url()

        def fim(url):
            self.ocupado = False
            self.chave.setEnabled(True)
            self.aviso(mensagem_ok if conferir(url) else "Não funcionou como esperado: veja o status")
            self.atualizar()

        self.tarefa.rodar(trabalho, fim)

    # ----- ações
    def ao_alternar(self, ligado):
        if self.atualizando or self.ocupado:
            return
        if ligado:
            self._executar("Ligando…", self.oc.ligar, "Serviço ligado", lambda u: u is not None)
        else:
            self._executar("Desligando…", self.oc.desligar, "Serviço desligado", lambda u: u is None)

    def ao_reiniciar(self):
        if not self.ocupado:
            self._executar("Reiniciando…", self.oc.reiniciar, "Serviço reiniciado", lambda u: u is not None)

    def ao_alternar_rede(self, ligado):
        if self.atualizando or self.ocupado:
            return
        try:
            self.oc.definir_acesso_rede(ligado)
        except OSError as e:
            self.aviso(f"Erro ao salvar: {e.strerror}")
            return
        msg = "Acesso pela rede ligado" if ligado else "Acesso pela rede desligado"
        if self.url:
            self._executar("Reiniciando…", self.oc.reiniciar, msg, lambda u: u is not None)
        else:
            self.aviso(msg + " (vale quando o serviço ligar)")
            self.atualizar()

    def ao_liberar_firewall(self):
        porta = sistema.porta_da_url(self.url)
        if not porta:
            return
        if sistema.liberar_firewall(porta):
            self.aviso("Confirme a permissão do Windows…")
            for atraso in (3000, 6000, 10000):
                QTimer.singleShot(atraso, self.atualizar)
        else:
            self.aviso("O Windows não liberou (permissão negada?)")

    def ao_escolher_modo(self, modo):
        ok = sistema.gravar_modo_inicio(modo, self.app_desktop)
        if not ok:
            self.aviso("Não consegui salvar a opção")
            self.combo.blockSignals(True)
            self.combo.setCurrentText(sistema.modo_inicio())
            self.combo.blockSignals(False)
            return
        self.linha_modo.definir_subtitulo(DESCRICAO_MODO[modo])
        self.aviso(f"Ao entrar no Windows: {modo}")

    def ao_digitar_senha(self):
        s1, s2 = self.senha1.text(), self.senha2.text()
        self.bt_senha.setEnabled(len(s1) >= SENHA_MIN and s1 == s2)
        erro = bool(s2) and s1 != s2
        self.senha2.setProperty("erro", "true" if erro else "false")
        self.senha2.style().unpolish(self.senha2)
        self.senha2.style().polish(self.senha2)

    def ao_salvar_senha(self):
        try:
            self.oc.gravar_senha(self.senha1.text())
        except (OSError, ValueError) as e:
            self.aviso(f"Erro ao salvar a senha: {e}")
            return
        self.senha1.clear()
        self.senha2.clear()
        if self.url:
            self._executar("Reiniciando…", self.oc.reiniciar,
                           "Senha trocada: atualize no celular", lambda u: u is not None)
        else:
            self.aviso("Senha trocada: vale quando o serviço ligar")

    # ----- ajuda: configurar no celular
    def mostrar_ajuda_celular(self, primeira_vez=False):
        AjudaCelular(self, self.endereco_celular(), self.url is not None,
                     self.oc.acesso_rede(), primeira_vez).exec()
        gravar_estado(ajuda_celular_vista=True)


class AjudaCelular(QDialog):
    def __init__(self, pai, endereco, ligado, rede, primeira_vez):
        super().__init__(pai)
        self.pai = pai
        self.setWindowTitle("Configurar no celular")
        self.setStyleSheet(ESTILO)
        self.setObjectName("raiz")
        self.resize(470, 680)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 14)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        conteudo.setObjectName("raiz")
        rolagem.setWidget(conteudo)
        externo.addWidget(rolagem, 1)
        v = QVBoxLayout(conteudo)
        v.setContentsMargins(20, 18, 20, 8)
        v.setSpacing(18)

        if primeira_vez:
            c = Cartao("Bem-vindo! 👋",
                       "Este guia mostra como acessar o OpenCode pelo celular. Ele fica disponível "
                       "depois no botão \"Como configurar\", ao lado do endereço do celular.")
            v.addWidget(c)

        c = Cartao("Antes de começar")
        c.adicionar(Linha("Celular no mesmo Wi-Fi do PC", "Fora de casa não funciona sem uma VPN como o Tailscale"))
        c.adicionar(Linha("Serviço ligado", "Ligado ✓" if ligado else "Desligado: ligue no interruptor do painel"))
        c.adicionar(Linha("Acesso pela rede", "Ligado ✓" if rede else "Desligado: ligue em \"Acesso pelo celular\""))
        v.addWidget(c)

        c = Cartao("No app OpenCode Mobile",
                   "Configure uma vez; depois é só abrir. Para trocar de PC ou se o IP mudar, edite o servidor.")
        c.adicionar(Linha("Nome", "Escolha o que quiser (ex.: PC de casa)"))
        bt = botao("Copiar")
        bt.setEnabled(bool(endereco))
        bt.clicked.connect(lambda: self.pai.copiar(endereco))
        c.adicionar(Linha("Endereço do servidor", endereco or "Ligue o serviço e o acesso pela rede", bt))
        c.adicionar(Linha("Senha", "A que você definiu (seção Trocar senha)"))
        v.addWidget(c)

        c = Cartao("Não conectou?")
        if endereco:
            c.adicionar(Linha("Teste no navegador do celular", f"{endereco}/global/health"))
        c.adicionar(Linha("Alerta do firewall com o nome \"Bun\"",
                          "É o OpenCode (ele é feito com o Bun). Clique em \"Permitir acesso\". "
                          "Se clicou em Cancelar: Painel de Controle → Firewall do Windows → "
                          "Permitir um aplicativo → marque \"Bun\" em Particular."))
        c.adicionar(Linha("Firewall", "Confira no painel se aparece \"Liberado para a sua rede local\"."))
        c.adicionar(Linha("IP mudou?", "O roteador pode trocar o IP do PC. Confira o endereço no painel."))
        v.addWidget(c)
        v.addStretch(1)

        ok = botao("Entendi", principal=True)
        ok.clicked.connect(self.accept)
        externo.addWidget(ok, 0, Qt.AlignHCenter)


# --------------------------------------------------------------------------- início
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(NOME_APP)
    app.setWindowIcon(QIcon(caminho_recurso("icone.png")))

    trava = QLockFile(os.path.join(sistema.pasta_estado(), "painel.lock"))
    os.makedirs(sistema.pasta_estado(), exist_ok=True)
    if not trava.tryLock(100):
        return 0  # já existe um painel aberto

    exe = sistema.achar_opencode()
    if not exe:
        QMessageBox.critical(None, NOME_APP,
                             "Não encontrei o OpenCode neste PC.\n\nInstale o OpenCode e abra o painel de novo.")
        return 1

    janela = Painel(sistema.OpenCode(exe))
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
