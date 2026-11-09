from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any

from ..mathutils import clamp
from .base import Rect, ControllerState, get_project_root


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
    base = get_project_root()
    return base / "assets" / "hud" / HUD_ASSET


# Ponto roxo (#8A38F5) no viewBox 942x137 do SVG da HUD (assets/hud/hud-click-no-reset-variable.svg):
# Forma octogonal/chanfrada entre X=[271, 319] e Y=[57, 104] — centro exato em (295.0, 80.5).
HUD_PURPLE_TARGET = (295.0, 80.5)


def hud_purple_button_point(rect: Rect) -> tuple[int, int]:
    """Ponto de clique na tela (px absolutos) para o ponto ROXO (#8A38F5) da HUD.

    Calcula a projeção do centro da forma roxa no SVG (viewBox 942x137) sobre o
    retângulo calibrado da HUD inferior (hud_target_rect).
    """
    if not rect.valid:
        return (0, 0)
    svg_x, svg_y = HUD_PURPLE_TARGET
    left, top, width, height = hud_target_rect(rect)
    x = left + (svg_x / 942.0) * width
    y = top + (svg_y / 137.0) * height
    return (int(round(x)), int(round(y)))



# HUD inferior para controles: layouts por tipo de controle (Xbox, PlayStation, Nintendo)
# Imagens PNG em assets/hud/inferior/, dimensão original 1347x242 na referência 1080p.
BOTTOM_HUD_ASSETS: dict[str, str] = {
    "xbox": "hud-xbox.png",
    "playstation": "hud-playstation.png",
    "nintendo": "hud-nitendo.png",
}

BOTTOM_HUD_SHORTCUT_ACTIVE_ASSETS: dict[str, str] = {
    "xbox": "hud-xbox-shortcut-config-active.png",
    "playstation": "hud-playstation-shortcut-config-active.png",
    "nintendo": "hud-nitendo-shortcut-config-active.png",
}

BOTTOM_HUD_REF_HEIGHT = 1080.0
BOTTOM_HUD_WIDTH = 1347.0
BOTTOM_HUD_HEIGHT = 242.0
BOTTOM_HUD_DEFAULT_SCALE = 0.73                                                   # Reduzido em 27% conforme calibração
BOTTOM_HUD_WIDTH_FRACTION_OF_HEIGHT = (BOTTOM_HUD_WIDTH * BOTTOM_HUD_DEFAULT_SCALE) / BOTTOM_HUD_REF_HEIGHT   # ~0.910472
BOTTOM_HUD_HEIGHT_FRACTION = (BOTTOM_HUD_HEIGHT * BOTTOM_HUD_DEFAULT_SCALE) / BOTTOM_HUD_REF_HEIGHT           # ~0.163574
BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION = 0.015                                     # -1.5% da altura da janela


def bottom_hud_asset_path(controller_type: str, shortcut_active: bool = False) -> Path | None:
    """Retorna o caminho do asset PNG do layout do controle especificado."""
    base = get_project_root()
    assets_map = BOTTOM_HUD_SHORTCUT_ACTIVE_ASSETS if shortcut_active else BOTTOM_HUD_ASSETS
    filename = assets_map.get(controller_type, assets_map.get("xbox", "hud-xbox.png"))
    path = base / "assets" / "hud" / "inferior" / filename
    return path if path.is_file() else None


def shortcut_mask_asset_path() -> Path | None:
    """Retorna o caminho do asset PNG da máscara do HUD (mask-hud.png)."""
    base = get_project_root()
    path = base / "assets" / "hud" / "inferior" / "mask-hud.png"
    return path if path.is_file() else None


SHORTCUT_INSTRUCTION_ASSETS = {
    "playstation": "shortcut-instruction-ps.png",
    "nintendo": "shortcut-instruction-nintendo.png",
    "xbox": "shortcut-instruction-xbox.png",
}


def shortcut_instruction_asset_path(controller_type: str) -> Path | None:
    """Retorna o caminho do asset PNG com instruções de atalhos conforme o layout do controle."""
    base = get_project_root()
    filename = SHORTCUT_INSTRUCTION_ASSETS.get(controller_type.lower(), "shortcut-instruction-xbox.png")
    path = base / "assets" / "images" / "instructions" / filename
    return path if path.is_file() else None


def shortcut_config_info_asset_path() -> Path | None:
    """Retorna o caminho do asset PNG da aba superior de informações (config-info.png)."""
    base = get_project_root()
    path = base / "assets" / "hud" / "superior" / "config-info.png"
    return path if path.is_file() else None


SHORTCUT_CONFIG_INFO_TOOLTIP_ASSETS = {
    "playstation": "config-info-tooltip-ps.png",
    "nintendo": "config-info-tooltip-nintendo.png",
    "xbox": "config-info-tooltip-xbox.png",
}


def shortcut_config_info_tooltip_asset_path(controller_type: str) -> Path | None:
    """Retorna o caminho do asset PNG do tooltip de informações de atalhos por tipo de controle."""
    base = get_project_root()
    filename = SHORTCUT_CONFIG_INFO_TOOLTIP_ASSETS.get(controller_type.lower(), "config-info-tooltip-xbox.png")
    path = base / "assets" / "hud" / "superior" / filename
    return path if path.is_file() else None


def shortcut_info_node_point(rect: Rect) -> tuple[int, int]:
    """Retorna o ponto central do cursor sobre a aba superior de informações (config-info.png)."""
    if not rect.valid or rect.height <= 0:
        return (0, 0)
    scale = rect.height / 960.0
    cx = rect.left + rect.width / 2.0
    cy = rect.top + 34.0 * scale
    return int(round(cx)), int(round(cy))


# Mapeamento dos nós da HUD inferior para configuração de atalhos (assets/hud/inferior/nodes.png).
# Coordenadas relativas ao canvas da HUD (948x171) na resolução de referência 1280x960:
SHORTCUT_HUD_NODES: tuple[tuple[int, str, float, float], ...] = (
    (0, "yellow", 65.0, 118.0),   # Slot 1 (Amarelo #E6C12A - Início / Foco padrão)
    (1, "green", 111.0, 118.0),   # Slot 2 (Verde #09B200)
    (2, "green", 156.0, 118.0),   # Slot 3
    (3, "green", 201.0, 118.0),   # Slot 4
    (4, "green", 245.0, 118.0),   # Slot 5
    (5, "green", 584.0, 118.0),   # Slot 6
    (6, "green", 629.0, 118.0),   # Slot 7
    (7, "green", 666.0, 111.0),   # Slot 8
    (8, "green", 728.0, 118.0),   # Slot 9
    (9, "green", 774.0, 118.0),   # Slot 10
    (10, "green", 819.0, 118.0),  # Slot 11
    (11, "green", 864.0, 118.0),  # Slot 12
    (12, "green", 908.0, 118.0),  # Slot 13
)


def shortcut_nodes_asset_path() -> Path | None:
    """Retorna o caminho do asset PNG com os nós da HUD inferior (nodes.png)."""
    base = get_project_root()
    path = base / "assets" / "hud" / "inferior" / "nodes.png"
    return path if path.is_file() else None


def shortcut_node_point(rect: Rect, index: int) -> tuple[int, int]:
    """Calcula a coordenada (x, y) absoluta na tela de um nó da HUD inferior."""
    if not rect.valid or index < 0 or index >= len(SHORTCUT_HUD_NODES):
        return (0, 0)
    scale = rect.height / 960.0
    mw = 948.0 * scale
    mh = 171.0 * scale
    mx = rect.left + (rect.width - mw) / 2.0
    my = rect.bottom - mh
    _, _, base_x, base_y = SHORTCUT_HUD_NODES[index]
    x = int(round(mx + base_x * scale))
    y = int(round(my + base_y * scale))
    return (x, y)


def shortcut_grid_cell_point(
    rect: Rect,
    slot_index: int,
    row: int,
    col: int,
    num_cols: int = 8,
    num_rows: int = 3,
) -> tuple[int, int]:
    """Calcula a coordenada (x, y) absoluta na tela do centro de uma célula (row, col) do grid de atalhos."""
    if not rect.valid:
        return (0, 0)
    scale = rect.height / 768.0

    pitch_x = 50.0 * scale
    pitch_y = 50.0 * scale

    # O grid repousa logo acima da barra inferior de atalhos e se expande PARA CIMA:
    # A linha inferior do popup fica centralizada em rect.bottom - (112.12 * scale) (subido mais 50% de um bloco)
    bottom_row_y = rect.bottom - (112.12 * scale)
    cy = bottom_row_y - (num_rows - 1 - row) * pitch_y

    slot_x, _ = shortcut_node_point(rect, slot_index)

    # O jogo abre o popup deslocado para a direita em relação ao slot selecionado (+78.12 * scale, recuado 50% para a esquerda)
    start_x = float(slot_x) + (78.12 * scale)

    # Clamping na borda direita: no Torchlight o popup alinha-se perto da borda direita da HUD/janela
    max_right = rect.right - (44.0 * scale)
    if start_x + (num_cols - 1) * pitch_x > max_right:
        start_x = max_right - (num_cols - 1) * pitch_x

    # Clamping na borda esquerda
    min_left = rect.left + (24.0 * scale)
    if start_x < min_left:
        start_x = min_left

    cx = start_x + col * pitch_x
    return (int(round(cx)), int(round(cy)))




def bottom_hud_target_rect(
    rect: Rect,
    offset_y_fraction: float = BOTTOM_HUD_DEFAULT_OFFSET_Y_FRACTION,
    scale_multiplier: float = 1.0,
) -> tuple[float, float, float, float]:
    """Calcula (left, top, width, height) absolutos do HUD inferior para controles.

    - Escala proporcionalmente à altura da janela (rect.height), preservando o aspect ratio original (1347x242).
    - Proporção base reduzida em 27% (fator 0.73) para perfeito encaixe sobre a barra do jogo.
    - Centralizada horizontalmente no eixo X.
    - No eixo Y, na parte inferior da janela menos offset_y_fraction da altura da janela (padrão: 1.5%).
    """
    if not rect.valid:
        return (0.0, 0.0, 0.0, 0.0)
    width = rect.height * BOTTOM_HUD_WIDTH_FRACTION_OF_HEIGHT * scale_multiplier
    height = rect.height * BOTTOM_HUD_HEIGHT_FRACTION * scale_multiplier
    left = rect.left + (rect.width - width) / 2.0
    top = rect.bottom - height - rect.height * offset_y_fraction
    return (left, top, width, height)


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
    base = get_project_root()
    return base / "assets" / "hud" / PET_ACTIONS_ASSET


# Ícones do aplicativo para a bandeja do sistema por estado (ativo, calibração).
APP_ICON_ASSETS: dict[tuple[bool, bool], str] = {
    (False, False): "torchbridge-ativo-false-calibration-false.png",
    (False, True): "torchbridge-ativo-false-calibration-false.png",
    (True, False): "torchbridge-ativo-true-calibration-false.png",
    (True, True): "torchbridge-ativo-true-calibration-true.png",
}


def app_icon_path(ativo: bool = True, calibration: bool = False) -> Path | None:
    """Retorna o caminho do ícone do TorchBridge na bandeja do sistema.

    Estados:
    - Desativado: torchbridge-ativo-false-calibration-false.png
    - Ativado sem calibração: torchbridge-ativo-true-calibration-false.png
    - Ativado com calibração: torchbridge-ativo-true-calibration-true.png
    """
    base = get_project_root()
    filename = APP_ICON_ASSETS.get(
        (bool(ativo), bool(calibration)),
        "torchbridge-ativo-true-calibration-false.png",
    )
    path = base / "assets" / "images" / "app" / filename
    return path if path.is_file() else None



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


