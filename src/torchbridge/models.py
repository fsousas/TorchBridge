# Modelos de dados compartilhados entre a thread do motor (entrada) e a UI Qt (overlay).
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Lock
import os
import sys
import time

from .mathutils import clamp


@dataclass(frozen=True)
# Área retangular útil (cliente) da janela do jogo, em coordenadas absolutas de tela.
class Rect:
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0

    @property
    # Borda direita (exclusiva), derivada de left + width.
    def right(self) -> int:
        return self.left + self.width

    @property
    # Borda inferior (exclusiva), derivada de top + height.
    def bottom(self) -> int:
        return self.top + self.height

    @property
    # A janela só é utilizável com área positiva; retângulo vazio = 'sem jogo'.
    def valid(self) -> bool:
        return self.width > 0 and self.height > 0

    # Teste de ponto dentro da área [left, right) × [top, bottom).
    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


@dataclass(frozen=True)
# Fotografia imutável do controle em um tick: eixos (-1..1), gatilhos (0..1) e botões.
class ControllerState:
    connected: bool = False
    name: str = ""
    mapping: str = ""
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    lt: float = 0.0
    rt: float = 0.0
    # Botões pressionados como frozenset de nomes lógicos ('a', 'lb', 'dpad_up'...) — imutável e barato de comparar.
    buttons: frozenset[str] = field(default_factory=frozenset)

    # Atalho: o botão lógico está pressionado neste tick?
    def pressed(self, button: str) -> bool:
        return button in self.buttons


# Slots da roda que abrem painéis laterais do jogo, por lateral da tela:
# índice 0 = lado esquerdo (Personagem 'C' e Pet 'P'); índice 1 = lado direito (Inventário 'I',
# Habilidades 'S', Missões 'Q' e Diário 'J').
PANEL_SIDE: dict[str, int] = {
    "C": 0,
    "P": 0,
    "V": 0,
    "B": 0,
    "E": 0,
    "K": 0,
    "T": 0,
    "I": 1,
    "S": 1,
    "Q": 1,
    "J": 1,
    "W": 1,
}


# Alterna o painel 'slot' na lateral correspondente e devolve o novo estado de active_panels
# ([esquerdo, direito], "" = fechado). Selecionar o painel já aberto o fecha; qualquer outro
# abre ou substitui o painel daquela lateral. Slots sem lateral definida não alteram o estado.
def toggle_panel(active_panels: list[str], slot: str) -> list[str]:
    key = slot.strip().upper()
    side = PANEL_SIDE.get(key)
    if side is None:
        return active_panels
    result = list(active_panels)
    result[side] = "" if result[side] == key else key
    return result


# Fração da largura da tela (12,5%) que a roda de atalhos e a âncora de movimento deslocam
# quando um único painel lateral está aberto, mantendo-as na área visível do lado oposto.
PANEL_X_SHIFT = 0.125


# Deslocamento horizontal (fração da largura; positivo = direita) conforme os painéis
# laterais abertos: +12,5% com só o lado esquerdo (índice 0) aberto; -12,5% com só o
# direito (índice 1); 0 quando ambos estão abertos ou ambos fechados.
def panels_x_shift(active_panels: list[str]) -> float:
    left, right = (list(active_panels) + ["", ""])[:2]
    if left and not right:
        return PANEL_X_SHIFT
    if right and not left:
        return -PANEL_X_SHIFT
    return 0.0


# Com os dois painéis laterais abertos de uma vez, a tela útil fica pequena demais para o
# movimento direto: o analógico esquerdo vira cursor livre (sem o clique do click-to-move).
def both_panels_open(active_panels: list[str]) -> bool:
    left, right = (list(active_panels) + ["", ""])[:2]
    return bool(left and right)


# Slot da roda que abre a sublinha de ações do pet: 4 quadradinhos cinza desenhados sob o
# setor selecionado enquanto a roda está aberta e o pet é o setor ativo (toggle no d-pad).
PET_ACTIONS_SLOT = "P"

# Quadrado da sublinha de pet actions que recebe o marcador ao abrir: o 4º (direito),
# alinhado embaixo do ícone do slot 'P'. Navegação horizontal cicla (1..4 com wrap).
PET_SUBMENU_DEFAULT = 4
PET_SUBMENU_COUNT = 4


# A sublinha de pet actions está visível no overlay? Só quando a roda está aberta, o setor
# selecionado é o slot de pet (PET_ACTIONS_SLOT) e o toggle interno está ligado.
# Fonte única consultada pelo engine (ao publicar o snapshot) e pelo overlay (ao desenhar).
def pet_submenu_open(radial_active: bool, selection: int | None, slot: object, open_flag: bool) -> bool:
    if not radial_active or not open_flag or selection is None:
        return False
    return isinstance(slot, str) and slot.strip().upper() == PET_ACTIONS_SLOT


# Largura do painel do jogo medida na própria janela: ela escala com a ALTURA da janela,
# não com a largura — o jogo mantém a interface sem distorção em qualquer proporção de
# tela. Base 7/15 + 20px a mais por painel em 1080p (20/1080) para a área útil do painel.
PANEL_WIDTH_FRACTION_OF_HEIGHT = 7 / 15 + 20.0 / 1080.0

# A aba do botão FECHAR (laranja) do jogo fica ancorada na borda ORIGINAL do painel
# (7/15): quando a área do painel ficou mais larga (+20px), a aba não acompanhou — ela
# fica exatamente onde o jogo a desenha, então o hit-test/polígono dela usa essa fração.
CLOSE_TAB_ANCHOR_FRACTION_OF_HEIGHT = 7 / 15


# HUD inferior do jogo (barra de vida/ícones de habilidade): o que é clicável no jogo —
# o jogador aperta botões ali — é tratado como "área que não fecha painéis". A forma vem
# de um SVG (assets/hud/hud-click-no-reset-variable.svg), desenhado na proporção da tela
# de REFERÊNCIA 1920x1080: o VERDE do arquivo é a área interativa. O hit-test e o
# desenho do modo de calibração usam o MESMO raster (mesmo esquema das abas de fechar).
#
# Posição e tamanho em FRAÇÃO DA ALTURA da janela — MESMO esquema dos painéis
# (PANEL_WIDTH_FRACTION_OF_HEIGHT), porque o jogo escala a HUD pela altura da janela
# (224px em 480 de altura etc.), não pela largura: escalar a largura pela largura da
# janela "espicha" a silhueta pras laterais quando a altura muda (calibracao hud-2).
# Padrão (1080p): HUD centralizada, base colada ao rodapé, SVG 925x136.
# Ajuste fino: rode com show_calibration e veja a silhueta verde alinhada com a HUD real.
HUD_ASSET = "hud-click-no-reset-variable.svg"
HUD_REF_HEIGHT = 1080.0    # altura da tela em que o SVG foi desenhado
# Calibração ago/2026: SVG 942x137 ampliado +7% de largura e +6% de altura em relação
# ao desenho (a área interativa real do jogo é um pouco maior que a silhueta do SVG).
HUD_WIDTH_FRACTION_OF_HEIGHT = 942.0 * 1.07 / 1080.0  # largura da HUD = fração da ALTURA
HUD_HEIGHT_FRACTION = 137.0 * 1.06 / 1080.0           # altura da HUD = fração da altura
HUD_CENTER_FRACTION = 0.501525           # centro horizontal (~3px à direita do miolo em 1080p)
HUD_BOTTOM_FRACTION = 0.996293           # base da HUD (~6px acima do rodapé em 1080p)


# Retângulo (x, y, w, h) em coordenadas absolutas onde a HUD inferior do jogo está
# posicionada na janela — a região que a silhueta do SVG ocupa. Fonte única do hit-test
# (hud_mask_hit) e do desenho do modo de calibração (overlay._draw_calibration).
def hud_target_rect(rect: Rect) -> tuple[float, float, float, float]:
    width = rect.height * HUD_WIDTH_FRACTION_OF_HEIGHT
    height = rect.height * HUD_HEIGHT_FRACTION
    left = rect.left + rect.width * HUD_CENTER_FRACTION - width / 2.0
    top = rect.top + rect.height * HUD_BOTTOM_FRACTION - height
    return (left, top, width, height)


# Testa se um ponto (x, y em px) cai numa área VERDE da máscara (2D de bools). Sem máscara
# ou fora da região da HUD: False (o ponto não é "área que não fecha painéis").
def hud_mask_hit(
    mask: tuple[int, int, list[bytes]] | None,
    rect: Rect,
    x: float,
    y: float,
) -> bool:
    if not mask:
        return False
    left, top, width, height = hud_target_rect(rect)
    if not (left <= x < left + width and top <= y < top + height):
        return False
    rows, cols, data = mask
    # Mapeia o ponto absoluto para a grade da máscara (íntero); arredondar pra baixo e
    # conferir a borda direita/inferior evita índice fora do range no último pixel.
    px = int((x - left) / width * cols)
    py = int((y - top) / height * rows)
    if px < 0 or px >= cols or py < 0 or py >= rows:
        return False
    return bool(data[py * cols + px])


# Rasteriza a silhueta VERDE do SVG num bitmap 2D (tuple: rows, cols, data). Lê o arquivo
# via Qt (QSvgRenderer + QPixmap) e converte cada pixel em "preenchido?" (alfa > 0).
# Retorna None se o asset não existir ou o Qt Svg não estiver disponível — o chamador
# trata como "sem HUD" (cliques na área central seguem o comportamento antigo de fechar
# tudo). A máscara é carregada uma única vez (engine __init__) e reutilizada; a resolução
# é a nativa do SVG (sizeAt do QSvgRenderer), o que dá precisão de ~1 px em 1080p.
#
# Cache em módulo: a rasterização custa ~300 ms; o engine/overlay reutilizam o resultado.
# O resultado (mesmo None, asset ausente) é guardado para não re-rasterizar a cada tick
# de teste/inicialização.
_HUD_MASK_CACHE: tuple[int, int, list[bytes]] | None | object = "unloaded"


def load_hud_mask() -> tuple[int, int, list[bytes]] | None:
    global _HUD_MASK_CACHE
    if _HUD_MASK_CACHE != "unloaded":
        return _HUD_MASK_CACHE  # type: ignore[return-value]
    result = _rasterize_hud_mask()
    if result is not None:
        _HUD_MASK_CACHE = result
    return result


# O trabalho pesado do load_hud_mask: rasteriza o SVG e devolve o bitmap 2D (ou None).
# Mantido à parte do cache para só publicar o resultado quando ele for realmente válido.
def _rasterize_hud_mask() -> tuple[int, int, list[bytes]] | None:
    path = hud_asset_path()
    if path is None or not path.exists():
        return None
    try:
        from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QGuiApplication
        from PySide6.QtSvg import QSvgRenderer

        # O Qt precisa de uma aplicação para desenhar pixmaps; preferimos QApplication
        # para que testes unitários possam também instanciar QWidgets sem conflito.
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
                app = QApplication([])
        except Exception:
            app = QGuiApplication.instance()
            if app is None:
                os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
                app = QGuiApplication([])
        renderer = QSvgRenderer()
        if not renderer.load(str(path)):
            return None
        # Grade nativa do SVG (sizeAt): a máscara mantém a resolução do asset.
        target_w, target_h = int(renderer.defaultSize().width()), int(renderer.defaultSize().height())
        pixmap = QPixmap(target_w, target_h)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        # ARGB32 (não-premultiplicado): em little-endian cada pixel ocupa 4 bytes
        # (B, G, R, A) — lemos o canal alpha (offset 3) direto do buffer, sem loop
        # de .pixel() (165 mil iterações seriam lentas na inicialização).
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        rows, cols = image.height(), image.width()
        buffer = image.constBits()
        raw = bytes(buffer)
        data = bytearray(rows * cols)
        for y in range(rows):
            row_offset = y * cols * 4
            for x in range(cols):
                if raw[row_offset + x * 4 + 3] > 0:
                    data[y * cols + x] = 1
        return (rows, cols, list(data))
    except Exception:  # noqa: BLE001 - Qt indisponível não pode derrubar o engine.
        return None


# Caminho do asset da HUD: assets/hud/ do projeto, ou o bundle PyInstaller (sys.frozen).
def hud_asset_path() -> Path | None:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "assets" / "hud" / HUD_ASSET


# Pet actions do jogo (caixinha com os botões de ação do pet) no CANTO SUPERIOR ESQUERDO
# da janela do jogo. A forma vem do SVG assets/hud/Pet-actions.svg (viewBox 156x201,
# desenhado na altura de REFERÊNCIA 1080). Usado SÓ no modo de calibração
# (overlay.show_calibration) como referência visual para ações futuras — ainda SEM
# hit-test/zona de clique.
#
# Mesma filosofia da HUD: largura E altura em FRAÇÃO DA ALTURA da janela, porque o jogo
# escala a interface pela altura (não pela largura). Canto colado: margem esquerda e de
# topo = 0. Ajuste fino (se um dia descolar): rode com show_calibration e veja o
# quadrado roxo alinhado com a caixinha real do jogo.
PET_ACTIONS_ASSET = "Pet-actions.svg"
# Calibração ago/2026: SVG 156x201 ampliado +9% de largura e +8% de altura em
# relação ao desenho — a caixinha real do jogo é um pouco maior que o SVG.
PET_ACTIONS_WIDTH_FRACTION_OF_HEIGHT = 156.0 * 1.09 / 1080.0  # largura = fração da ALTURA
PET_ACTIONS_HEIGHT_FRACTION = 201.0 * 1.08 / 1080.0          # altura = fração da ALTURA
PET_ACTIONS_LEFT_FRACTION = 0.0                        # margem esquerda = 0 (colado ao canto)
PET_ACTIONS_TOP_FRACTION = 0.0                         # margem de topo = 0 (colado ao topo)


# Retângulo (x, y, w, h) em coordenadas absolutas da caixinha de pet actions, colada no
# canto superior esquerdo da janela do jogo. Fonte única do desenho do modo de calibração
# (overlay._draw_calibration).
def pet_actions_target_rect(rect: Rect) -> tuple[float, float, float, float]:
    width = rect.height * PET_ACTIONS_WIDTH_FRACTION_OF_HEIGHT
    height = rect.height * PET_ACTIONS_HEIGHT_FRACTION
    left = rect.left + rect.width * PET_ACTIONS_LEFT_FRACTION
    top = rect.top + rect.height * PET_ACTIONS_TOP_FRACTION
    return (left, top, width, height)


# Caminho do asset do pet actions (mesma pasta da HUD).
def pet_actions_asset_path() -> Path | None:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "assets" / "hud" / PET_ACTIONS_ASSET


# Alvos de clique das 4 ações do pet (coordenadas no viewBox 156x201 do Pet-actions.svg):
# centro de cada botão. Ordem = a dos quadradinhos da sublinha: 1 = círculo vermelho
# (agressivo), 2 = azul (defensivo), 3 = branco (passivo), 4 = quadrado amarelo
# (vendedor, centro do rect x=109 y=7 32x32). Não há tecla de teclado para essas ações
# — o motor leva o mouse até o ponto, clica e devolve ao centro.
PET_CLICK_TARGETS = (
    (42.5, 181.5),  # 1 — agressivo (círculo vermelho)
    (75.5, 181.5),  # 2 — defensivo (círculo azul)
    (108.5, 181.5),  # 3 — passivo (círculo branco)
    (125.0, 23.0),  # 4 — vendedor (quadrado amarelo)
)


# Ponto de clique na tela (px absolutos) para o quadrado `index` (1..4): o centro do
# botão no viewBox do SVG projetado na caixinha calibrada (pet_actions_target_rect).
# Escala com a janela junto com a caixinha — o ajuste fino da calibração se propaga.
def pet_click_point(rect: Rect, index: int) -> tuple[int, int]:
    if not 1 <= index <= len(PET_CLICK_TARGETS):
        raise ValueError(f"Índice do botão do pet fora do intervalo: {index}")
    svg_x, svg_y = PET_CLICK_TARGETS[index - 1]
    left, top, width, height = pet_actions_target_rect(rect)
    x = left + svg_x / 156.0 * width
    y = top + svg_y / 201.0 * height
    return (int(round(x)), int(round(y)))


# Botão de fechar (X) do painel: a forma que o JOGO hit-testa é uma aba com base
# RETA na borda interna do painel e ponta em seta voltada para o interior do
# painel (painel esquerdo aponta à esquerda; direito é o espelho). A forma exata
# (8 vértices) vem do botão extraído do jogo em
# docs/proporcao/close-button-shape.svg — ver _CLOSE_TAB_SVG abaixo: base larga e
# reta na borda, "ponta" que é uma aresta reta (não um ponto), topo e base com
# extremidades chanfradas. O ajuste calibrável aqui é o posicionamento: calibracao3
# pediu +8% de tamanho (TOP/BOTTOM expandiram 0.002 cada), depois "sobe 5%" (subiu
# 15.9px a 1080p), que subiu demais — voltou metade (7.95px). Centro em 0.28765
# da altura (0.295 original - 0.00735).
CLOSE_TAB_TOP_FRACTION = 0.26065   # topo da aba, em fração da ALTURA da janela
CLOSE_TAB_BOTTOM_FRACTION = 0.31465 # base da aba, em fração da altura da janela
# Aspecto da forma do SVG (profundidade/altura = 41/73): calibracao1.png mediu
# 13px de profundidade para 23px de altura — mesma razão, então escalar a altura
# escala a largura junto, preservando a forma real do botão.
CLOSE_TAB_ASPECT = 41 / 73
# Vértices exatos da forma no SVG (viewBox 41x73, botão do painel esquerdo sem
# espelhar): x=41 é a borda interna do painel, x=0 é a ponta da seta. Ordem segue
# o path do SVG (fechada, sem auto-interseção).
_CLOSE_TAB_SVG = (
    (30.5, 0), (41, 9.5), (41, 62.5), (30.5, 73),
    (23.5, 73), (0, 49.5), (0, 23.5), (23.5, 0),
)
_SVG_W, _SVG_H = 41, 73


# Largura do painel em pixels, a partir da altura da janela.
def panel_width(rect: Rect) -> int:
    return int(round(rect.height * PANEL_WIDTH_FRACTION_OF_HEIGHT))


# Retângulos de calibração (x, y, w, h) em coordenadas absolutas — fonte única usada pelo
# click_zone (lógica) e pelo overlay (desenho das zonas em modo de calibração).
def panel_regions(rect: Rect) -> dict[str, tuple[int, int, int, int]]:
    w = panel_width(rect)
    return {
        "panel_left": (rect.left, rect.top, w, rect.height),
        "panel_right": (rect.right - w, rect.top, w, rect.height),
        "center": (rect.left + w, rect.top, rect.width - 2 * w, rect.height),
    }


# Vértices (x, y) absolutos da aba do botão fechar, em ordem para o hit-test de
# polígono e para o QPainter. side 'left' = aba do painel esquerdo (borda interna
# original na direita do painel, ponta apontando à esquerda); 'right' = espelho
# horizontal no painel direito. A forma é o path exato do SVG (8 vértices) escalado:
# a altura da aba vem das frações TOP/BOTTOM da janela e a profundidade (largura) vem
# do aspecto do SVG. A âncora horizontal usa CLOSE_TAB_ANCHOR_FRACTION_OF_HEIGHT
# (borda original do painel) porque a aba do jogo não acompanha o alargamento da área.
def close_tab_vertices(rect: Rect, side: str) -> list[tuple[float, float]]:
    top = rect.top + rect.height * CLOSE_TAB_TOP_FRACTION
    bottom = rect.top + rect.height * CLOSE_TAB_BOTTOM_FRACTION
    height = bottom - top
    depth = height * CLOSE_TAB_ASPECT
    if side == "left":
        inner = rect.left + rect.height * CLOSE_TAB_ANCHOR_FRACTION_OF_HEIGHT
        flip = -1.0  # a ponta da seta aponta para a esquerda (interior do painel esq.)
    else:
        inner = rect.right - rect.height * CLOSE_TAB_ANCHOR_FRACTION_OF_HEIGHT
        flip = 1.0
    return [
        (inner + flip * (_SVG_W - sx) / _SVG_W * depth, top + sy / _SVG_H * height)
        for sx, sy in _CLOSE_TAB_SVG
    ]


# Ponto dentro do polígono (ray-casting): dispara um raio horizontal à direita e
# conta interseções com as arestas — ímpar = dentro.
def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


# Região de um clique em relação aos painéis: "close_left" (aba fechar do painel
# esquerdo), "hud" (área interativa da HUD inferior — NÃO fecha painéis), "left",
# "center", "right" ou "close_right" (aba do painel direito). A aba do botão fecha só
# aquele lado; o resto do painel não fecha nada.
#
# hud_mask: bitmap da silhueta verde da HUD (load_hud_mask); quando passado, um clique
# na área verde volta "hud" — o motor usa isso para NÃO zerar os painéis abertos. A
# zona "hud" é checada DEPOIS das abas de fechar (que têm prioridade por serem mais
# específicas) e ANTES dos retângulos de painel/centro.
def click_zone(
    rect: Rect,
    x: int,
    y: int,
    hud_mask: tuple[int, int, list[bytes]] | None = None,
) -> str:
    if not rect.contains(x, y):
        return "outside"
    for name, side in (("close_left", "left"), ("close_right", "right")):
        if point_in_polygon(x, y, close_tab_vertices(rect, side)):
            return name
    if hud_mask is not None and hud_mask_hit(hud_mask, rect, x, y):
        return "hud"
    regions = panel_regions(rect)
    for name, label in (("panel_left", "left"), ("panel_right", "right")):
        bx, by, bw, bh = regions[name]
        if bx <= x < bx + bw and by <= y < by + bh:
            return label
    return "center"


# Coordenadas relativas dos botões da Tela Inicial (Title Screen)
# Base de referência: 768p (1024x768). Proporção ancorada na ALTURA da janela (rect.height).
TITLE_BUTTON_BOTTOM_Y_FRACTION = 0.9466  # Y = rect.top + rect.height * 0.9466 (~727px em 768p)
TITLE_BUTTON_CONTINUE_Y_FRACTION = 0.8464  # Y = rect.top + rect.height * 0.8464 (~650px em 768p)

# Deslocamentos horizontais a partir do CENTRO da janela (rect.left + rect.width * 0.5)
# Escala multiplicada por (rect.height / 768.0)
TITLE_X_OFFSET_NEW_CHARACTER = -299.5
TITLE_X_OFFSET_LOAD_CHARACTER = -44.5
TITLE_X_OFFSET_SETTINGS = 206.5
TITLE_X_OFFSET_QUIT = 457.5
TITLE_X_OFFSET_CONTINUE = 457.5

TITLE_BUTTONS = ("new_character", "load_character", "settings", "quit_game", "continue")


def title_menu_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) absoluta de um botão na Tela Inicial,
    respeitando a proporção da altura da janela (rect.height).
    """
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5

    if button_name == "continue":
        x = center_x + TITLE_X_OFFSET_CONTINUE * scale
        y = rect.top + rect.height * TITLE_BUTTON_CONTINUE_Y_FRACTION
    elif button_name == "new_character":
        x = center_x + TITLE_X_OFFSET_NEW_CHARACTER * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    elif button_name == "load_character":
        x = center_x + TITLE_X_OFFSET_LOAD_CHARACTER * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    elif button_name == "settings":
        x = center_x + TITLE_X_OFFSET_SETTINGS * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    elif button_name == "quit_game":
        x = center_x + TITLE_X_OFFSET_QUIT * scale
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION
    else:
        x = center_x
        y = rect.top + rect.height * TITLE_BUTTON_BOTTOM_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões da Tela de Criação de Personagem (state_id == 1)
# Todas as posições são ancoradas e escaladas proporcionalmente à ALTURA da janela (rect.height),
# garantindo alinhamento sub-pixel idêntico em 4:3, 16:9 ou qualquer outra proporção.
CHAR_CREATE_CLASSES_X_FRACTION = 0.1855  # Âncora na borda esquerda: rect.left + height * 0.1855
CHAR_CREATE_DESTROYER_Y_FRACTION = 0.382
CHAR_CREATE_VANQUISHER_Y_FRACTION = 0.558
CHAR_CREATE_ALCHEMIST_Y_FRACTION = 0.733

CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION = 0.072  # Âncora na borda direita: rect.right - height * 0.072
CHAR_CREATE_PET_DOG_Y_FRACTION = 0.552
CHAR_CREATE_PET_CAT_Y_FRACTION = 0.591
CHAR_CREATE_PET_FERRET_Y_FRACTION = 0.631
CHAR_CREATE_PET_NAME_Y_FRACTION = 0.719

CHAR_CREATE_BOTTOM_Y_FRACTION = 0.948  # Âncora no rodapé / centro
CHAR_CREATE_BACK_X_OFFSET_FRACTION = -0.266
CHAR_CREATE_NAME_X_OFFSET_FRACTION = 0.052
CHAR_CREATE_OK_X_OFFSET_FRACTION = 0.454

CREATE_CHAR_BUTTONS = (
    "destroyer",
    "vanquisher",
    "alchemist",
    "dog",
    "cat",
    "ferret",
    "pet_name",
    "back",
    "character_name",
    "ok",
)


def char_create_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão na Tela de Criação de Personagem."""
    if not rect.valid:
        return (0, 0)

    center_x = rect.left + rect.width * 0.5

    if button_name == "destroyer":
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_DESTROYER_Y_FRACTION
    elif button_name == "vanquisher":
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_VANQUISHER_Y_FRACTION
    elif button_name == "alchemist":
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_ALCHEMIST_Y_FRACTION
    elif button_name == "dog":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_DOG_Y_FRACTION
    elif button_name == "cat":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_CAT_Y_FRACTION
    elif button_name == "ferret":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_FERRET_Y_FRACTION
    elif button_name == "pet_name":
        x = rect.right - rect.height * CHAR_CREATE_PET_X_FROM_RIGHT_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_PET_NAME_Y_FRACTION
    elif button_name == "back":
        x = center_x + rect.height * CHAR_CREATE_BACK_X_OFFSET_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    elif button_name == "character_name":
        x = center_x + rect.height * CHAR_CREATE_NAME_X_OFFSET_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    elif button_name == "ok":
        x = center_x + rect.height * CHAR_CREATE_OK_X_OFFSET_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_BOTTOM_Y_FRACTION
    else:
        x = rect.left + rect.height * CHAR_CREATE_CLASSES_X_FRACTION
        y = rect.top + rect.height * CHAR_CREATE_DESTROYER_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões da Tela de Seleção de Dificuldade (state_id == 2)
DIFFICULTY_OPTIONS_X_FRACTION = 0.239  # Âncora na borda esquerda: rect.left + height * 0.239
DIFFICULTY_EASY_Y_FRACTION = 0.378
DIFFICULTY_NORMAL_Y_FRACTION = 0.428
DIFFICULTY_HARD_Y_FRACTION = 0.481
DIFFICULTY_VERY_HARD_Y_FRACTION = 0.532

DIFFICULTY_HARDCORE_X_FRACTION = 0.1068  # Caixa de seleção Hardcore
DIFFICULTY_HARDCORE_Y_FRACTION = 0.631

DIFFICULTY_BOTTOM_Y_FRACTION = 0.948  # Botão Voltar (rodapé/centro)
DIFFICULTY_BACK_X_OFFSET_FRACTION = -0.266

DIFFICULTY_BUTTONS = (
    "easy",
    "normal",
    "hard",
    "very_hard",
    "hardcore",
    "back",
)


def difficulty_menu_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão na Tela de Seleção de Dificuldade."""
    if not rect.valid:
        return (0, 0)

    center_x = rect.left + rect.width * 0.5

    if button_name == "easy":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_EASY_Y_FRACTION
    elif button_name == "normal":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_NORMAL_Y_FRACTION
    elif button_name == "hard":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_HARD_Y_FRACTION
    elif button_name == "very_hard":
        x = rect.left + rect.height * DIFFICULTY_OPTIONS_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_VERY_HARD_Y_FRACTION
    elif button_name == "hardcore":
        x = rect.left + rect.height * DIFFICULTY_HARDCORE_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_HARDCORE_Y_FRACTION
    elif button_name == "back":
        x = center_x + rect.height * DIFFICULTY_BACK_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIFFICULTY_BOTTOM_Y_FRACTION
    else:
        x = rect.left + rect.height * DIFFICULTY_HARDCORE_X_FRACTION
        y = rect.top + rect.height * DIFFICULTY_HARDCORE_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas calibradas para Botões de Diálogos e Telas de História (base 1024x768)
DIALOG_BUTTON_Y_FRACTION = 573.0 / 768.0          # Linha vertical dos botões Ok, Accept, Decline (573/768 = ~0.7461)
DIALOG_ACCEPT_X_OFFSET_FRACTION = -51.0 / 768.0  # -0.0664 (461px - 512px = 51px à esquerda do centro em 768p)
DIALOG_DECLINE_X_OFFSET_FRACTION = 146.0 / 768.0  # +0.1901 (658px - 512px = 146px à direita do centro em 768p)
DIALOG_OK_X_OFFSET_FRACTION = 42.0 / 768.0       # +0.0547 (554px - 512px = 42px à direita do centro em 768p)

DIALOG_REWARD_SLOT_X_OFFSET_FRACTION = -338.0 / 768.0  # -0.4401 (174px - 512px = 338px à esquerda do centro em 768p)
DIALOG_REWARD_SLOT_Y_FRACTION = 506.0 / 768.0         # 0.6589 (506px em 768p)

CINEMATIC_SKIP_X_OFFSET_FRACTION = 0.487          # Botão Skip/Continue na tela de história
CINEMATIC_SKIP_Y_FRACTION = 0.948


def dialog_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão ou slot de recompensa em diálogos de NPCs, missões e tela de história."""
    if not rect.valid:
        return (0, 0)
    center_x = rect.left + rect.width * 0.5
    btn = button_name.lower()
    if btn == "ok":
        x = center_x + rect.height * DIALOG_OK_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION
    elif btn == "accept":
        x = center_x + rect.height * DIALOG_ACCEPT_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION
    elif btn == "decline":
        x = center_x + rect.height * DIALOG_DECLINE_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION
    elif btn in ("reward", "reward_slot", "slot"):
        x = center_x + rect.height * DIALOG_REWARD_SLOT_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_REWARD_SLOT_Y_FRACTION
    elif btn in ("skip", "continue"):
        x = center_x + rect.height * CINEMATIC_SKIP_X_OFFSET_FRACTION
        y = rect.top + rect.height * CINEMATIC_SKIP_Y_FRACTION
    else:
        x = center_x + rect.height * DIALOG_OK_X_OFFSET_FRACTION
        y = rect.top + rect.height * DIALOG_BUTTON_Y_FRACTION

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas calibradas para Pesca e Diálogo Modal de Confirmação (base 1024x768)
FISHING_HOOK_COORD: tuple[float, float] = (512.0, 498.0)
MODAL_OK_COORD: tuple[float, float] = (509.0, 467.0)


def fishing_hook_point(rect: Rect) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão de anzol na interface de pesca."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    base_x, base_y = FISHING_HOOK_COORD
    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def modal_ok_point(rect: Rect) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão Ok no modal de confirmação / mensagem de pesca."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    base_x, base_y = MODAL_OK_COORD
    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)



# Coordenadas base dos botões e slots de interfaces de crafting (painel esquerdo, base 1024x768)
# Calibradas e validadas pixel a pixel a partir dos elementos visuais reais in-game
CRAFTING_BUTTONS: dict[str, dict[str, tuple[float, float]]] = {
    "Transmutador": {
        "decline": (240.0, 405.0),
        "transmute": (240.0, 450.0),
        "accept": (240.0, 450.0),
    },
    "Sockets": {
        "decline": (240.0, 402.0),
        "recover": (240.0, 447.0),
        "accept": (240.0, 447.0),
    },
    "Encantador": {
        "decline": (240.0, 402.0),
        "enchant": (240.0, 447.0),
        "accept": (240.0, 447.0),
    },
}

# Posições dos slots de itens (base 1024x768)
CRAFTING_SLOTS: dict[str, list[tuple[float, float]]] = {
    # 4 slots: 2x2 grid (topo-esq, topo-dir, baixo-esq, baixo-dir)
    "Transmutador": [
        (216.0, 266.0),
        (268.0, 266.0),
        (216.0, 339.0),
        (268.0, 339.0),
    ],
    # 1 slot central quadrado (inner 96x96)
    "Sockets": [
        (240.0, 314.0),
    ],
    # 1 slot central quadrado (inner 96x96)
    "Encantador": [
        (240.0, 314.0),
    ],
}


def crafting_button_point(rect: Rect, menu_name: str, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão nas telas de Transmutador, Sockets e Encantador."""
    if not rect.valid:
        return (0, 0)
    buttons = CRAFTING_BUTTONS.get(menu_name, CRAFTING_BUTTONS.get("Encantador", {}))
    bx, by = buttons.get(button_name.lower(), (200.0, 274.0))
    scale = rect.height / 768.0
    x = rect.left + bx * scale
    y = rect.top + by * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def crafting_slot_point(rect: Rect, menu_name: str, slot_index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot de item nas telas de Transmutador (0..3) ou Sockets/Encantador (0)."""
    if not rect.valid:
        return (0, 0)
    slots = CRAFTING_SLOTS.get(menu_name, CRAFTING_SLOTS.get("Encantador", []))
    if not slots:
        return (0, 0)
    idx = max(0, min(slot_index, len(slots) - 1))
    sx, sy = slots[idx]
    scale = rect.height / 768.0
    x = rect.left + sx * scale
    y = rect.top + sy * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões do Menu de Pause (COptionsMenu / Options) em jogo (base 1024x768)
# Calibradas e validadas a partir dos quadradinhos em assets/images/menus/in-game paused.png
PAUSE_BUTTONS: tuple[str, ...] = ("settings", "exit_to_title", "return_to_game")

PAUSE_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "settings": (599.0, 233.0),
    "exit_to_title": (599.0, 323.0),
    "return_to_game": (599.0, 413.0),
}


def pause_menu_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) central do quadradinho mapeado no Menu de Pause."""
    if not rect.valid:
        return (0, 0)
    bx, by = PAUSE_BUTTON_COORDS.get(button_name.lower(), (599.0, 413.0))
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    # Offset horizontal em relacao ao centro da tela (512 em 1024x768)
    x = center_x + (bx - 512.0) * scale
    y = rect.top + by * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões e slots da tela de Carregar Personagem (state_id == 3) (base 1024x768)
# Calibradas e validadas a partir de assets/images/sreensXcursor/load-char
LOAD_CHAR_BUTTONS: tuple[str, ...] = (
    "slot_1", "slot_2", "slot_3", "slot_4", "slot_5",
    "scroll_up", "scroll_down",
    "delete", "back", "play",
    "delete_confirm", "delete_cancel",
)

LOAD_CHAR_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "slot_1": (971.0, 227.0),
    "slot_2": (971.0, 299.5),
    "slot_3": (971.0, 372.0),
    "slot_4": (971.0, 445.0),
    "slot_5": (971.0, 517.0),
    "scroll_up": (979.0, 155.0),
    "scroll_down": (971.0, 618.0),
    "delete": (558.0, 663.0),
    "back": (300.0, 728.0),
    "play": (859.0, 728.0),
    "delete_confirm": (576.0, 362.0),
    "delete_cancel": (576.0, 411.0),
}


def load_char_button_point(rect: Rect, button_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão/slot na tela de Carregar Personagem."""
    if not rect.valid:
        return (0, 0)
    btn = button_name.lower()
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5

    # Slots e setas de rolagem da lista de personagens (ancorados a borda direita)
    if btn.startswith("slot_") or btn in ("scroll_up", "scroll_down"):
        base_x, base_y = LOAD_CHAR_BUTTON_COORDS.get(btn, (971.0, 227.0))
        right_dist = (1024.0 - base_x) * scale
        x = rect.right - right_dist
        y = rect.top + base_y * scale
    else:
        # Botoes centralizados/inferiores e modal de delete (ancorados ao centro horizontal)
        base_x, base_y = LOAD_CHAR_BUTTON_COORDS.get(btn, (859.0, 728.0))
        x = center_x + (base_x - 512.0) * scale
        y = rect.top + base_y * scale

    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


# Coordenadas dos botões e controles da tela de Configurações (Settings) (base 1024x768)
# Calibradas e validadas a partir de assets/images/sreensXcursor/settings
SETTINGS_BUTTONS: tuple[str, ...] = (
    "row1_col1", "row1_col2", "row1_col3",
    "row2_col1", "row2_col2", "row2_col3",
    "resolution", "shadows",
    "music_slider", "music_mute", "particle_detail",
    "row5_col3",
    "sound_slider", "sound_mute", "row6_col3",
    "row7_col1", "row7_col3",
    "cancel", "apply",
)

SETTINGS_BUTTON_COORDS: dict[str, tuple[float, float]] = {
    "row1_col1": (238.0, 132.0),
    "row1_col2": (437.0, 132.0),
    "row1_col3": (636.0, 132.0),
    "row2_col1": (238.0, 184.0),
    "row2_col2": (437.0, 184.0),
    "row2_col3": (636.0, 184.0),
    "resolution": (398.0, 247.0),
    "shadows": (800.0, 247.0),
    "music_slider": (272.0, 344.0),
    "music_mute": (486.0, 346.0),
    "particle_detail": (800.0, 346.0),
    "row5_col3": (636.0, 401.0),
    "sound_slider": (304.0, 445.0),
    "sound_mute": (486.0, 448.0),
    "row6_col3": (636.0, 444.0),
    "row7_col1": (238.0, 488.0),
    "row7_col3": (636.0, 488.0),
    "cancel": (465.0, 552.0),
    "apply": (657.0, 552.0),
}

SETTINGS_SLIDER_X_MIN = 228.0
SETTINGS_SLIDER_X_MAX = 447.0
SETTINGS_MUSIC_SLIDER_Y = 344.0
SETTINGS_SOUND_SLIDER_Y = 445.0

SETTINGS_DROPDOWNS: dict[str, dict[str, Any]] = {
    "resolution": {
        "opener": (398.0, 247.0),
        "options": [
            (385.0, 293.0),
            (385.0, 309.5),
            (385.0, 326.0),
            (385.0, 342.5),
            (385.0, 359.0),
            (385.0, 375.5),
            (385.0, 392.0),
            (385.0, 408.5),
            (385.0, 425.0),
            (385.0, 441.5),
            (385.0, 458.0),
            (385.0, 474.5),
            (385.0, 491.0),
            (385.0, 507.5),
            (385.0, 524.0),
            (385.0, 540.5),
            (385.0, 557.0),
            (385.0, 573.5),
        ],
    },
    "shadows": {
        "opener": (800.0, 247.0),
        "options": [
            (780.0, 293.0),
            (780.0, 310.0),
            (780.0, 329.0),
            (780.0, 346.0),
            (780.0, 363.0),
            (780.0, 380.0),
        ],
    },
    "particle_detail": {
        "opener": (800.0, 346.0),
        "options": [
            (785.0, 396.0),
            (785.0, 413.0),
            (785.0, 431.0),
        ],
    },
}

SETTINGS_NAV_MAP: dict[str, dict[str, str]] = {
    # Row 1 (y=132)
    "row1_col1": {"right": "row1_col2", "down": "row2_col1"},
    "row1_col2": {"left": "row1_col1", "right": "row1_col3", "down": "row2_col2"},
    "row1_col3": {"left": "row1_col2", "down": "row2_col3"},

    # Row 2 (y=184)
    "row2_col1": {"up": "row1_col1", "right": "row2_col2", "down": "resolution"},
    "row2_col2": {"up": "row1_col2", "left": "row2_col1", "right": "row2_col3", "down": "resolution"},
    "row2_col3": {"up": "row1_col3", "left": "row2_col2", "down": "shadows"},

    # Row 3 (y=247)
    "resolution": {"up": "row2_col2", "right": "shadows", "down": "music_slider"},
    "shadows": {"up": "row2_col3", "left": "resolution", "down": "particle_detail"},

    # Row 4 (y=344..346)
    "music_slider": {"up": "resolution", "right": "music_mute", "down": "sound_slider"},
    "music_mute": {"up": "resolution", "left": "music_slider", "right": "particle_detail", "down": "sound_mute"},
    "particle_detail": {"up": "shadows", "left": "music_mute", "down": "row5_col3"},

    # Row 5 (y=401)
    "row5_col3": {"up": "particle_detail", "left": "music_mute", "down": "row6_col3"},

    # Row 6 (y=444..448)
    "sound_slider": {"up": "music_slider", "right": "sound_mute", "down": "row7_col1"},
    "sound_mute": {"up": "music_mute", "left": "sound_slider", "right": "row6_col3", "down": "cancel"},
    "row6_col3": {"up": "row5_col3", "left": "sound_mute", "down": "row7_col3"},

    # Row 7 (y=488)
    "row7_col1": {"up": "sound_slider", "right": "row7_col3", "down": "cancel"},
    "row7_col3": {"up": "row6_col3", "left": "row7_col1", "down": "apply"},

    # Row 8 (y=552)
    "cancel": {"up": "row7_col1", "right": "apply"},
    "apply": {"up": "row7_col3", "left": "cancel"},
}


def settings_button_point(rect: Rect, button_name: str, volume: float | None = None) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um botão/controle na tela de Configurações."""
    if not rect.valid:
        return (0, 0)
    btn = button_name.lower()
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5

    if btn == "music_slider":
        vol = 0.5 if volume is None else clamp(volume, 0.0, 1.0)
        base_x = SETTINGS_SLIDER_X_MIN + vol * (SETTINGS_SLIDER_X_MAX - SETTINGS_SLIDER_X_MIN)
        base_y = SETTINGS_MUSIC_SLIDER_Y
    elif btn == "sound_slider":
        vol = 0.5 if volume is None else clamp(volume, 0.0, 1.0)
        base_x = SETTINGS_SLIDER_X_MIN + vol * (SETTINGS_SLIDER_X_MAX - SETTINGS_SLIDER_X_MIN)
        base_y = SETTINGS_SOUND_SLIDER_Y
    else:
        base_x, base_y = SETTINGS_BUTTON_COORDS.get(btn, (238.0, 132.0))

    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def settings_dropdown_option_point(rect: Rect, dropdown_name: str, option_idx: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de uma opção dentro de um dropdown aberto na tela de Configurações."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    data = SETTINGS_DROPDOWNS.get(dropdown_name.lower())
    if not data:
        return (0, 0)
    options = data["options"]
    idx = int(clamp(option_idx, 0, len(options) - 1))
    base_x, base_y = options[idx]
    x = center_x + (base_x - 512.0) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def settings_slider_bounds(rect: Rect, is_music: bool = True) -> tuple[tuple[int, int], tuple[int, int]]:
    """Retorna os pontos (x1, y1) e (x2, y2) da linha ciano do slider na tela de Configurações."""
    if not rect.valid:
        return ((0, 0), (0, 0))
    scale = rect.height / 768.0
    center_x = rect.left + rect.width * 0.5
    base_y = SETTINGS_MUSIC_SLIDER_Y if is_music else SETTINGS_SOUND_SLIDER_Y
    y = rect.top + base_y * scale

    x1 = center_x + (SETTINGS_SLIDER_X_MIN - 512.0) * scale
    x2 = center_x + (SETTINGS_SLIDER_X_MAX - 512.0) * scale
    p1 = (int(clamp(round(x1), rect.left + 2, rect.right - 2)), int(clamp(round(y), rect.top + 2, rect.bottom - 2)))
    p2 = (int(clamp(round(x2), rect.left + 2, rect.right - 2)), int(clamp(round(y), rect.top + 2, rect.bottom - 2)))
    return (p1, p2)


# ==============================================================================
# Inventário do Jogador (Base de referência 1024x768 - painel direito)
# ==============================================================================
# Calibrado a partir de assets/images/inventário/
# O painel direito do inventário é ancorado à borda direita da tela (rect.right):
# dist_from_right = (1024.0 - base_x) * scale
# x = rect.right - dist_from_right
# y = rect.top + base_y * scale

INVENTORY_TAB_COORDS: dict[int, tuple[float, float]] = {
    1: (752.5, 492.5),
    2: (852.5, 492.5),
    3: (952.5, 492.5),
}

INVENTORY_GRID_ORIGIN = (739.5, 520.5)
INVENTORY_GRID_STEP_X = 40.0
INVENTORY_GRID_STEP_Y = 55.0
INVENTORY_GRID_ROWS = 3
INVENTORY_GRID_COLS = 7

INVENTORY_UPPER_COORDS: dict[str, tuple[float, float]] = {
    # Fileira de Feitiços / Spells (y=409.5)
    "spell_1": (779.5, 409.5),
    "spell_2": (831.5, 409.5),
    "spell_3": (883.5, 409.5),
    "spell_4": (935.5, 409.5),
    # Armas e Bugiganga (y ~ 350)
    "main_hand": (729.5, 354.5),
    "trinket": (859.5, 347.5),
    "off_hand": (965.5, 354.5),
    # Cinto e Botas (y=257.5)
    "belt": (729.5, 257.5),
    "boots": (962.5, 257.5),
    # Luvas e Peito (y=182.5)
    "gloves": (729.5, 182.5),
    "chest": (962.5, 182.5),
    # Elmo e Ombros (y=107.5)
    "helmet": (729.5, 107.5),
    "shoulders": (962.5, 107.5),
    # Anéis e Colar (y=100.5)
    "ring_1": (801.5, 100.5),
    "necklace": (845.5, 100.5),
    "ring_2": (889.5, 100.5),
}

INVENTORY_UPPER_NAV_MAP: dict[str, dict[str, Any]] = {
    # Spells (y=409.5)
    "spell_1": {"left": "main_hand", "right": "spell_2", "up": "main_hand", "down": (1, 1)},
    "spell_2": {"left": "spell_1", "right": "spell_3", "up": "trinket", "down": (1, 3)},
    "spell_3": {"left": "spell_2", "right": "spell_4", "up": "trinket", "down": (1, 5)},
    "spell_4": {"left": "spell_3", "right": "off_hand", "up": "off_hand", "down": (1, 7)},
    # Armas / Trinket (y ~ 350)
    "main_hand": {"up": "belt", "down": "spell_1", "right": "trinket", "left": "main_hand"},
    "trinket": {"left": "main_hand", "right": "off_hand", "down": "spell_2", "up": "necklace"},
    "off_hand": {"up": "boots", "down": "spell_4", "left": "trinket", "right": "off_hand"},
    # Cinto e Botas (y=257.5)
    "belt": {"up": "gloves", "down": "main_hand", "right": "boots", "left": "belt"},
    "boots": {"up": "chest", "down": "off_hand", "left": "belt", "right": "boots"},
    # Luvas e Peito (y=182.5)
    "gloves": {"up": "helmet", "down": "belt", "right": "chest", "left": "gloves"},
    "chest": {"up": "shoulders", "down": "boots", "left": "gloves", "right": "chest"},
    # Elmo, Anéis, Colar, Ombros (y ~ 100-107)
    "helmet": {"down": "gloves", "right": "ring_1", "left": "helmet", "up": "helmet"},
    "ring_1": {"left": "helmet", "right": "necklace", "down": "main_hand", "up": "ring_1"},
    "necklace": {"left": "ring_1", "right": "ring_2", "down": "trinket", "up": "necklace"},
    "ring_2": {"left": "necklace", "right": "shoulders", "down": "off_hand", "up": "ring_2"},
    "shoulders": {"left": "ring_2", "down": "chest", "right": "shoulders", "up": "shoulders"},
}


def inventory_slot_point(rect: Rect, row: int, col: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot do grid do inventário (row 1..3, col 1..7)."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    r = int(clamp(row, 1, INVENTORY_GRID_ROWS))
    c = int(clamp(col, 1, INVENTORY_GRID_COLS))
    base_x = INVENTORY_GRID_ORIGIN[0] + (c - 1) * INVENTORY_GRID_STEP_X
    base_y = INVENTORY_GRID_ORIGIN[1] + (r - 1) * INVENTORY_GRID_STEP_Y
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def inventory_tab_point(rect: Rect, tab_index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) do botão da aba (1, 2 ou 3) do inventário."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    idx = int(clamp(tab_index, 1, 3))
    base_x, base_y = INVENTORY_TAB_COORDS.get(idx, (752.5, 492.5))
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


def inventory_upper_point(rect: Rect, slot_name: str) -> tuple[int, int]:
    """Calcula a coordenada (x, y) de um slot da parte superior de equipamentos do inventário."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0
    base_x, base_y = INVENTORY_UPPER_COORDS.get(slot_name.lower(), (779.5, 409.5))
    x = rect.right - (1024.0 - base_x) * scale
    y = rect.top + base_y * scale
    clamped_x = int(clamp(round(x), rect.left + 2, rect.right - 2))
    clamped_y = int(clamp(round(y), rect.top + 2, rect.bottom - 2))
    return (clamped_x, clamped_y)


@dataclass(frozen=True)
# Estado visual imutável que o motor publica para o overlay Qt desenhar.
class OverlaySnapshot:
    enabled: bool = True
    game_found: bool = False
    game_active: bool = False
    game_rect: Rect = field(default_factory=Rect)
    controller_connected: bool = False
    controller_name: str = ""
    controller_mapping: str = ""
    mode: str = "direct"
    radial_active: bool = False
    radial_selection: int | None = None
    # Sublinha de pet actions (4 quadradinhos) visível sob o slot 'P' da roda.
    pet_submenu_open: bool = False
    # Quadrado (1..4) com o marcador na sublinha de pet actions; None quando fechada.
    pet_submenu_selection: int | None = None
    # Painéis laterais abertos pela roda: índice 0 = esquerdo (C/P), 1 = direito (I/S/Q/J); "" = fechado.
    active_panels: list[str] = field(default_factory=lambda: ["", ""])
    aim_x: int | None = None
    aim_y: int | None = None
    toast_text: str = ""
    toast_until: float = 0.0
    # Estado do jogo lido diretamente da memória RAM
    memory_state_desc: str = ""
    memory_is_in_game: bool = False
    memory_is_loading: bool = False
    memory_is_menu_open: bool = False
    memory_open_menus: list[str] = field(default_factory=list)
    char_name_len: int = 0
    title_menu_focus: str | None = None
    char_create_focus: str | None = None
    difficulty_focus: str | None = None
    dialog_focus: str | None = None
    dialog_type: str = ""
    dialog_buttons: list[str] = field(default_factory=list)
    dialog_has_reward: bool = False
    pause_menu_focus: str | None = None
    load_char_focus: str | None = None
    load_char_delete_open: bool = False
    settings_focus: str | None = None
    settings_dropdown: str | None = None
    settings_dropdown_idx: int = 0
    settings_slider_dragging: bool = False
    settings_sound_vol: float = 1.0
    settings_music_vol: float = 1.0
    fishing_focus: str | None = None
    modal_confirm_focus: str | None = None
    inventory_open: bool = False
    inventory_tab: str | None = None
    inventory_focus: str | None = None


# Ponte thread-safe entre o motor (thread 'TorchBridgeInput') e a thread da UI (Qt).
class SharedOverlayState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot = OverlaySnapshot()

    # Leitura atômica do último snapshot publicado.
    def get(self) -> OverlaySnapshot:
        with self._lock:
            return self._snapshot

    # Publica um novo snapshot com apenas os campos alterados (dataclasses.replace).
    def update(self, **changes: object) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, **changes)

    # Publica uma mensagem temporária com validade em segundos; o overlay apaga sozinho.
    def toast(self, text: str, seconds: float = 2.2) -> None:
        self.update(toast_text=text, toast_until=time.monotonic() + seconds)

