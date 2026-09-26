"""Testes unitários para mapeamento, coordenadas, overlay e navegação da tela de Carregar Personagem (state_id == 3)."""
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from torchbridge.config import ConfigManager
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    LOAD_CHAR_BUTTONS,
    LOAD_CHAR_BUTTON_COORDS,
    ControllerState,
    OverlaySnapshot,
    Rect,
    SharedOverlayState,
    load_char_button_point,
)
from torchbridge.overlay import GameOverlay


class FakeInjector:
    def __init__(self) -> None:
        self.moved: list[tuple[int, int]] = []
        self.cursor = (500, 500)
        self.buttons: dict[str, bool] = {}
        self.events: list[tuple] = []

    def move(self, x: int, y: int) -> bool:
        self.moved.append((x, y))
        self.cursor = (x, y)
        self.events.append(("move", x, y))
        return True

    def cursor_position(self) -> tuple[int, int]:
        return self.cursor

    def mouse_button(self, button: str, down: bool) -> bool:
        self.buttons[button] = down
        self.events.append(("mouse", button, down))
        return True

    def key(self, name: str, down: bool) -> bool:
        self.buttons[name] = down
        return True

    def key_pressed(self, name: str) -> bool:
        return self.buttons.get(name, False)

    def tap(self, name: str) -> bool:
        self.events.append(("tap", name))
        return True


class LoadCharacterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_button_coordinates_base_1024x768(self):
        """Valida que todos os pontos calculados batem pixel a pixel com os marcadores calibrados."""
        rect = Rect(left=0, top=0, width=1024, height=768)

        # Slots de personagens (direita)
        self.assertEqual(load_char_button_point(rect, "slot_1"), (971, 227))
        self.assertEqual(load_char_button_point(rect, "slot_2"), (971, 300))
        self.assertEqual(load_char_button_point(rect, "slot_3"), (971, 372))
        self.assertEqual(load_char_button_point(rect, "slot_4"), (971, 445))
        self.assertEqual(load_char_button_point(rect, "slot_5"), (971, 517))

        # Setas de rolagem da lista
        self.assertEqual(load_char_button_point(rect, "scroll_up"), (979, 155))
        self.assertEqual(load_char_button_point(rect, "scroll_down"), (971, 618))

        # Barra inferior
        self.assertEqual(load_char_button_point(rect, "delete"), (558, 663))
        self.assertEqual(load_char_button_point(rect, "back"), (300, 728))
        self.assertEqual(load_char_button_point(rect, "play"), (859, 728))

        # Modal de exclusão (Delete Dialog)
        self.assertEqual(load_char_button_point(rect, "delete_confirm"), (576, 362))
        self.assertEqual(load_char_button_point(rect, "delete_cancel"), (576, 411))

    def test_select_character_and_move_to_play(self):
        """Valida que ao selecionar um personagem (A ou X), o cursor clica e move imediatamente para o Play."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        # Entra na tela de Carregar Personagem (state_id == 3)
        engine._memory_state = GameMemoryState(
            is_connected=True,
            state_id=3,
            state_desc="Carregar Personagem",
            open_menus=["Carregar Personagem"],
            save_count=3,
        )

        # 1. Primeiro tick: foco inicial em slot_1
        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)
        self.assertEqual(engine._load_char_focus, "slot_1")
        self.assertIn(("move", 971, 227), injector.events)

        # 2. Usuário pressiona X (ou A) no controle sobre o slot_1
        btn_x = ControllerState(buttons={"x"})
        engine._previous = empty
        engine._process_active(hub, btn_x, rect, cfg, 0.1, 0.05)

        # Deve ter clicado no slot_1 E movido o cursor para o Play
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)
        self.assertEqual(engine._load_char_focus, "play")
        self.assertEqual(shared.get().load_char_focus, "play")
        self.assertEqual(injector.cursor, (859, 728))

        # 3. Pressiona X novamente em Play: clica no Play para iniciar gameplay
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, btn_x, rect, cfg, 0.2, 0.05)
        self.assertIn(("mouse", "left", True), injector.events)
        self.assertIn(("mouse", "left", False), injector.events)

    def test_dpad_navigation_between_slots_and_bottom_row(self):
        """Valida a navegação D-pad entre a lista e a barra inferior (D-pad Esquerda / Direita)."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            state_id=3,
            state_desc="Carregar Personagem",
            save_count=5,
        )

        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)
        self.assertEqual(engine._load_char_focus, "slot_1")

        # D-pad Baixo: vai para slot_2
        down = ControllerState(buttons={"dpad_down"})
        engine._previous = empty
        engine._process_active(hub, down, rect, cfg, 0.1, 0.05)
        self.assertEqual(engine._load_char_focus, "slot_2")

        # D-pad Esquerda: sai da lista direto para os botões inferiores (foca em Play)
        left = ControllerState(buttons={"dpad_left"})
        engine._previous = empty
        engine._process_active(hub, left, rect, cfg, 0.2, 0.05)
        self.assertEqual(engine._load_char_focus, "play")

        # D-pad Esquerda: de Play vai para Delete
        engine._previous = empty
        engine._process_active(hub, left, rect, cfg, 0.3, 0.05)
        self.assertEqual(engine._load_char_focus, "delete")

        # D-pad Esquerda: de Delete vai para Back
        engine._previous = empty
        engine._process_active(hub, left, rect, cfg, 0.4, 0.05)
        self.assertEqual(engine._load_char_focus, "back")

        # D-pad Direita: de Back vai para Delete
        right = ControllerState(buttons={"dpad_right"})
        engine._previous = empty
        engine._process_active(hub, right, rect, cfg, 0.5, 0.05)
        self.assertEqual(engine._load_char_focus, "delete")

        # D-pad Direita: de Delete vai para Play
        engine._previous = empty
        engine._process_active(hub, right, rect, cfg, 0.6, 0.05)
        self.assertEqual(engine._load_char_focus, "play")

        # D-pad Direita: de Play volta para o último slot visitado (slot_2)
        engine._previous = empty
        engine._process_active(hub, right, rect, cfg, 0.7, 0.05)
        self.assertEqual(engine._load_char_focus, "slot_2")

    def test_delete_character_flow_and_return_to_delete_button(self):
        """Valida que ao cancelar ou confirmar o delete, o cursor retorna exatamente para o botão delete pequeno."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        engine._memory_state = GameMemoryState(
            is_connected=True,
            state_id=3,
            state_desc="Carregar Personagem",
            save_count=3,
        )

        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)

        # Navega até o botão delete pequeno
        left = ControllerState(buttons={"dpad_left"})
        engine._previous = empty
        engine._process_active(hub, left, rect, cfg, 0.1, 0.05)  # Play
        engine._previous = empty
        engine._process_active(hub, left, rect, cfg, 0.2, 0.05)  # Delete
        self.assertEqual(engine._load_char_focus, "delete")

        # 1. Clica no botão delete (com A ou X): abre o modal de confirmação
        injector.events.clear()
        btn_a = ControllerState(buttons={"a"})
        engine._previous = empty
        engine._process_active(hub, btn_a, rect, cfg, 0.3, 0.05)
        self.assertTrue(engine._load_char_delete_dialog_open)
        self.assertEqual(engine._load_char_focus, "delete_cancel")
        self.assertEqual(injector.cursor, (576, 411))
        # Garante que nenhum botão de mouse ficou pressionado sobre delete_cancel (prevenção contra miss-clique)
        self.assertFalse(injector.buttons.get("left", False))
        self.assertFalse(injector.buttons.get("right", False))

        # 1.1 Teste de Debounce: se um botão for acionado durante a janela de debounce (0.4s < 0.55s), deve ser ignorado
        btn_b = ControllerState(buttons={"b"})
        engine._previous = empty
        engine._process_active(hub, btn_b, rect, cfg, 0.4, 0.05)
        self.assertTrue(engine._load_char_delete_dialog_open, "O debounce deve impedir ações prematuras no modal")

        # 2. Cancela com botão B (ou A em Cancel) após o debounce (0.6s > 0.55s): o cursor DEVE voltar para o botão delete pequeno (558, 663)
        engine._previous = empty
        engine._process_active(hub, btn_b, rect, cfg, 0.6, 0.05)
        self.assertFalse(engine._load_char_delete_dialog_open)
        self.assertEqual(engine._load_char_focus, "delete")
        self.assertEqual(injector.cursor, (558, 663))

        # 3. Clica novamente em Delete para abrir o modal (após debounce de retorno: 0.9s > 0.85s)
        engine._previous = empty
        engine._process_active(hub, btn_a, rect, cfg, 0.9, 0.05)
        self.assertTrue(engine._load_char_delete_dialog_open)
        self.assertEqual(engine._load_char_focus, "delete_cancel")

        # 4. Sobe para delete_confirm e clica (após debounce: 1.2s > 1.15s): deve confirmar E voltar para o botão delete pequeno
        up = ControllerState(buttons={"dpad_up"})
        engine._previous = empty
        engine._process_active(hub, up, rect, cfg, 1.2, 0.05)
        self.assertEqual(engine._load_char_focus, "delete_confirm")
        self.assertEqual(injector.cursor, (576, 362))

        engine._previous = empty
        engine._process_active(hub, btn_a, rect, cfg, 1.3, 0.05)
        self.assertFalse(engine._load_char_delete_dialog_open)
        self.assertEqual(engine._load_char_focus, "delete")
        self.assertEqual(injector.cursor, (558, 663))

    def test_dpad_continuous_auto_scroll_down_and_up(self):
        """Valida que o D-pad rola automaticamente 1 personagem por clique no slot_5 (down) e slot_1 (up)."""
        config = ConfigManager()
        shared = SharedOverlayState()
        hub = MagicMock()
        injector = FakeInjector()
        engine = BridgeEngine(config, shared)
        engine.injector = injector

        rect = Rect(left=0, top=0, width=1024, height=768)
        cfg = config.get()
        empty = ControllerState()

        # Usuário possui 7 saves (máximo visível 5, permitindo 2 rolagens para baixo)
        engine._memory_state = GameMemoryState(
            is_connected=True,
            state_id=3,
            state_desc="Carregar Personagem",
            save_count=7,
        )

        engine._process_active(hub, empty, rect, cfg, 0.0, 0.05)
        self.assertEqual(engine._load_char_focus, "slot_1")
        self.assertEqual(engine._load_char_scroll_offset, 0)

        down = ControllerState(buttons={"dpad_down"})

        # Navega de slot_1 até slot_5
        for expected_slot in ("slot_2", "slot_3", "slot_4", "slot_5"):
            engine._previous = empty
            engine._process_active(hub, down, rect, cfg, 0.1, 0.05)
            self.assertEqual(engine._load_char_focus, expected_slot)

        self.assertEqual(injector.cursor, (971, 517))
        self.assertEqual(engine._load_char_scroll_offset, 0)

        # 1. Pressiona D-pad Baixo no slot_5:
        # Deve acionar scroll_down (971, 618), rolar 1 personagem e retornar o cursor para slot_5 (971, 517)
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, down, rect, cfg, 0.2, 0.05)
        self.assertEqual(engine._load_char_scroll_offset, 1)
        self.assertEqual(engine._load_char_focus, "slot_5")
        self.assertEqual(injector.cursor, (971, 517))
        self.assertIn(("move", 971, 618), injector.events)
        self.assertIn(("mouse", "left", True), injector.events)

        # 2. Pressiona D-pad Baixo novamente no slot_5:
        # Rola o 2º personagem (offset vira 2, o máximo para 7 saves)
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, down, rect, cfg, 0.3, 0.05)
        self.assertEqual(engine._load_char_scroll_offset, 2)
        self.assertEqual(engine._load_char_focus, "slot_5")
        self.assertEqual(injector.cursor, (971, 517))

        # 3. Pressiona D-pad Baixo pela 3ª vez:
        # Já está no final da lista (offset 2 == 7 - 5), não deve mais rolar
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, down, rect, cfg, 0.4, 0.05)
        self.assertEqual(engine._load_char_scroll_offset, 2)
        self.assertEqual(engine._load_char_focus, "slot_5")
        self.assertNotIn(("move", 971, 618), injector.events)

        # Agora navega para cima até slot_1
        up = ControllerState(buttons={"dpad_up"})
        for expected_slot in ("slot_4", "slot_3", "slot_2", "slot_1"):
            engine._previous = empty
            engine._process_active(hub, up, rect, cfg, 0.5, 0.05)
            self.assertEqual(engine._load_char_focus, expected_slot)

        self.assertEqual(injector.cursor, (971, 227))
        self.assertEqual(engine._load_char_scroll_offset, 2)

        # 4. Pressiona D-pad Cima no slot_1:
        # Deve acionar scroll_up (979, 155), rolar 1 personagem para cima e retornar para slot_1 (971, 227)
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, up, rect, cfg, 0.6, 0.05)
        self.assertEqual(engine._load_char_scroll_offset, 1)
        self.assertEqual(engine._load_char_focus, "slot_1")
        self.assertEqual(injector.cursor, (971, 227))
        self.assertIn(("move", 979, 155), injector.events)
        self.assertIn(("mouse", "left", True), injector.events)

        # 5. Pressiona D-pad Cima novamente no slot_1:
        # Rola de volta para o topo (offset vira 0)
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, up, rect, cfg, 0.7, 0.05)
        self.assertEqual(engine._load_char_scroll_offset, 0)
        self.assertEqual(engine._load_char_focus, "slot_1")
        self.assertEqual(injector.cursor, (971, 227))

        # 6. Pressiona D-pad Cima uma 3ª vez:
        # Já está no topo (offset == 0), não rola mais
        injector.events.clear()
        engine._previous = empty
        engine._process_active(hub, up, rect, cfg, 0.8, 0.05)
        self.assertEqual(engine._load_char_scroll_offset, 0)
        self.assertEqual(engine._load_char_focus, "slot_1")
        self.assertNotIn(("move", 979, 155), injector.events)

    def test_overlay_draw_calibration_load_char(self):
        """Valida que o overlay renderiza sem erros na tela de Carregar Personagem (normal e modal)."""
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            cfg_path = Path(directory) / "perfil.json"
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"overlay": {"show_calibration": True}}, f)
            config = ConfigManager(cfg_path)
            shared = SharedOverlayState()
            overlay = GameOverlay(shared, config)

            rect = Rect(100, 100, 1024, 768)

            # Caso normal
            snap = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=False,
                memory_state_desc="Carregar Personagem",
                load_char_focus="slot_1",
                load_char_delete_open=False,
            )
            pix = QPixmap(1024, 768)
            painter = QPainter(pix)
            try:
                overlay._draw_calibration(painter, snap, 1.0)
            finally:
                painter.end()

            # Caso modal de delete
            snap_modal = OverlaySnapshot(
                game_rect=rect,
                memory_is_in_game=False,
                memory_state_desc="Carregar Personagem",
                load_char_focus="delete_cancel",
                load_char_delete_open=True,
            )
            pix2 = QPixmap(1024, 768)
            painter2 = QPainter(pix2)
            try:
                overlay._draw_calibration(painter2, snap_modal, 1.0)
            finally:
                painter2.end()


if __name__ == "__main__":
    unittest.main()

