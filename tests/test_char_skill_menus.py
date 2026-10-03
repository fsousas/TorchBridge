"""Testes unitários para navegação e leitura dos menus de Personagem (C) e Habilidades (S):
- Leitura de memória: char_class, player_level, attr_points_remaining, skill_points_remaining, skill_upgradeable
- Funções de layout, colunas de ponte e coordenadas dos nós (verde, laranja e rosa)
- Navegação D-pad no Menu C (atributos e botão + rosa quando há pontos)
- Navegação D-pad no Menu S (tabs, slots dinâmicos por classe, nó rosa de upgrade com checagem de nível)
- Navegação em ponte entre Menu C e Menu S quando ambos estão abertos
"""
import unittest
from unittest.mock import MagicMock, patch

import tempfile
from pathlib import Path

from torchbridge.config import ConfigManager
from torchbridge.controller import ControllerState
from torchbridge.engine import BridgeEngine
from torchbridge.memory import GameMemoryState
from torchbridge.models import (
    SKILL_TAB_NAMES,
    SKILL_TREE_LAYOUTS,
    Rect,
    SharedOverlayState,
    char_attr_pink_point,
    char_attr_point,
    skill_bridge_col,
    skill_slot_pink_point,
    skill_slot_point,
    skill_snap_col,
    skill_tab_point,
)


class CharSkillMenuModelsTests(unittest.TestCase):
    def setUp(self):
        self.rect = Rect(left=0, top=0, width=1920, height=1080)

    def test_char_points_calculation(self):
        cx, cy = char_attr_point(self.rect, "strength")
        self.assertGreater(cx, 0)
        self.assertGreater(cy, 0)

        px, py = char_attr_pink_point(self.rect, "strength")
        # Nó rosa fica à direita do nó de atributo
        self.assertGreater(px, cx)
        self.assertAlmostEqual(py, cy, delta=5)

    def test_skill_points_calculation(self):
        tx, ty = skill_tab_point(self.rect, 1)
        self.assertGreater(tx, 0)
        self.assertGreater(ty, 0)

        sx, sy = skill_slot_point(self.rect, 0, 1)
        px, py = skill_slot_pink_point(self.rect, 0, 1)
        # Nó rosa de melhoria fica abaixo do slot de habilidade
        self.assertAlmostEqual(px, sx, delta=5)
        self.assertGreater(py, sy)

    def test_skill_tree_layouts(self):
        # Valida que cada classe possui 3 abas e 6 linhas por aba
        for char_class in ("destroyer", "vanquisher", "alchemist"):
            for tab in (1, 2, 3):
                tab_name = SKILL_TAB_NAMES[char_class][tab]
                layout = SKILL_TREE_LAYOUTS[char_class][tab_name]
                self.assertEqual(len(layout), 6)
                for row in layout:
                    self.assertEqual(len(row), 3)

    def test_destroyer_skill_layouts(self):
        self.assertEqual(
            SKILL_TREE_LAYOUTS["destroyer"]["berserker"],
            [
                [None, 1, 2],
                [None, 1, None],
                [0, None, 2],
                [None, 1, None],
                [None, 1, 2],
                [0, 1, None],
            ],
        )
        self.assertEqual(
            SKILL_TREE_LAYOUTS["destroyer"]["titan"],
            [
                [None, 1, None],
                [None, 1, 2],
                [0, 1, 2],
                [None, 1, None],
                [0, None, 2],
                [None, 1, None],
            ],
        )
        self.assertEqual(
            SKILL_TREE_LAYOUTS["destroyer"]["spectral"],
            [
                [None, 1, None],
                [None, 1, 2],
                [0, 1, 2],
                [0, None, None],
                [None, 1, None],
                [None, 1, 2],
            ],
        )

    def test_vanquisher_skill_layouts(self):
        self.assertEqual(
            SKILL_TREE_LAYOUTS["vanquisher"]["marksman"],
            [
                [0, 1, None],
                [None, 1, 2],
                [0, 1, 2],
                [None, 1, None],
                [None, None, 2],
                [None, 1, None],
            ],
        )
        self.assertEqual(
            SKILL_TREE_LAYOUTS["vanquisher"]["rogue"],
            [
                [None, 1, None],
                [None, 1, 2],
                [None, 1, 2],
                [None, None, 2],
                [0, 1, None],
                [0, 1, None],
            ],
        )
        self.assertEqual(
            SKILL_TREE_LAYOUTS["vanquisher"]["arbiter"],
            [
                [None, 1, None],
                [0, 1, None],
                [None, None, 2],
                [None, 1, 2],
                [0, 1, None],
                [None, 1, 2],
            ],
        )

    def test_alchemist_skill_layouts(self):
        # Aba 2 (lore)
        self.assertEqual(
            SKILL_TREE_LAYOUTS["alchemist"]["lore"],
            [
                [None, 1, None],
                [0, None, 2],
                [None, 1, 2],
                [0, None, 2],
                [0, None, 2],
                [None, 1, 2],
            ],
        )
        # Aba 3 (battle)
        self.assertEqual(
            SKILL_TREE_LAYOUTS["alchemist"]["battle"],
            [
                [None, 1, 2],
                [0, None, 2],
                [None, 1, 2],
                [0, None, 2],
                [0, None, 2],
                [None, 1, None],
            ],
        )

    def test_skill_bridge_col(self):
        # Linha com [A, B, None] -> ponte é col 0 (mais à esquerda preenchida)
        self.assertEqual(skill_bridge_col([1, 2, None]), 0)
        # Linha com [None, B, C] -> ponte é col 1
        self.assertEqual(skill_bridge_col([None, 2, 3]), 1)
        # Linha com [None, None, C] -> ponte é col 2
        self.assertEqual(skill_bridge_col([None, None, 3]), 2)

    def test_skill_snap_col(self):
        target_row = [None, 2, 3]
        # Tentando ir para col 0 onde não há habilidade -> snap para col 1
        self.assertEqual(skill_snap_col(target_row, 0), 1)
        # Tentando ir para col 1 onde há habilidade -> mantém col 1
        self.assertEqual(skill_snap_col(target_row, 1), 1)


class CharSkillMenuEngineTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.injector = MagicMock()
        self.injector.cursor_position.return_value = (500, 500)
        self.engine.injector = self.injector
        self.hub = MagicMock()
        self.rect = Rect(left=0, top=0, width=1920, height=1080)
        self.cfg = self.config.get()

    def tearDown(self):
        self._temp_dir.cleanup()

    def _make_state(self, **kwargs):
        buttons = set()
        for b in ("a", "b", "x", "y", "lb", "rb", "back", "start", "guide", "l3", "r3", "dpad_up", "dpad_down", "dpad_left", "dpad_right"):
            if kwargs.get(b):
                buttons.add(b)
        return ControllerState(
            connected=True,
            lx=kwargs.get("lx", 0.0),
            ly=kwargs.get("ly", 0.0),
            rx=kwargs.get("rx", 0.0),
            ry=kwargs.get("ry", 0.0),
            lt=kwargs.get("lt", 0.0),
            rt=kwargs.get("rt", 0.0),
            buttons=frozenset(buttons),
        )

    def test_char_menu_navigation_without_points(self):
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos"],
            attr_points_remaining=0,
        )
        self.engine._memory_state = mem

        # Tick 1: Inicialização do menu C
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength")
        self.assertFalse(self.engine._char_menu_focus.endswith("_pink"))

        # D-pad down -> dexterity
        s = self._make_state(dpad_down=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "dexterity")

        # D-pad right sem pontos vai para o nó laranja de ponte (dexterity_bridge)
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "dexterity_bridge")
        self.assertFalse(self.engine._char_menu_focus.endswith("_pink"))

        # D-pad left volta para dexterity (verde)
        s = self._make_state(dpad_left=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.15, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "dexterity")

    def test_char_menu_navigation_with_points_and_spending(self):
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos"],
            attr_points_remaining=5,
        )
        self.engine._memory_state = mem

        # Inicializa em strength
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)

        # D-pad right com pontos -> vai para o segundo nó (stat)
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_stat")

        # D-pad right novamente -> entra no nó rosa/botão +
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)
        self.assertTrue(self.engine._char_menu_focus.endswith("_pink"))
        self.assertEqual(self.engine._char_menu_focus, "strength_pink")

        # Pressiona A no nó rosa -> dispara clique esquerdo no botão +
        self.injector.mouse_button.reset_mock()
        s = self._make_state(a=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.15, dt=0.016)
        self.injector.mouse_button.assert_any_call("left", True)
        self.injector.mouse_button.assert_any_call("left", False)

        # D-pad right a partir do nó rosa -> nó laranja de ponte
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.2, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")

        # D-pad left volta para o nó rosa
        s = self._make_state(dpad_left=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.25, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_pink")

    def test_skill_menu_navigation_upgrade_node_logic(self):
        # Cenário: Alchemist, Skill Points = 1, Slot (0, 1) upgradeable, Slot (1, 1) NÃO upgradeable
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="alchemist",
            player_level=2,
            skill_points_remaining=1,
            skill_upgradeable={(0, 1): True, (1, 1): False},
        )
        self.engine._memory_state = mem

        # Tick 1: Inicializa no slot inicial (linha 0, col 1 para alchemist)
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)
        self.assertEqual(self.engine._skill_focus_row, 0)
        self.assertEqual(self.engine._skill_focus_col, 1)
        self.assertFalse(self.engine._skill_in_pink)

        # D-pad down: como slot (0, 1) é upgradeable e skill_points > 0, desce para o nó rosa
        s = self._make_state(dpad_down=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertTrue(self.engine._skill_in_pink)
        self.assertEqual(self.shared.get().skill_focus, "(0, 1, pink)")

        # Pressiona A no nó rosa de upgrade -> clica no botão + da skill
        self.injector.mouse_button.reset_mock()
        s = self._make_state(a=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)
        self.injector.mouse_button.assert_any_call("left", True)
        self.injector.mouse_button.assert_any_call("left", False)

        # D-pad down a partir do nó rosa: passa para a próxima linha (linha 1)
        s = self._make_state(dpad_down=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.15, dt=0.016)
        self.assertFalse(self.engine._skill_in_pink)
        self.assertEqual(self.engine._skill_focus_row, 1)

        # Na linha 1, o slot (1, 1) NÃO é upgradeable. D-pad down deve pular o nó rosa e ir direto para linha 2
        s = self._make_state(dpad_down=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.2, dt=0.016)
        self.assertFalse(self.engine._skill_in_pink)
        self.assertEqual(self.engine._skill_focus_row, 2)

    def test_bridge_navigation_between_menus(self):
        # Ambos os menus abertos
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos", "Habilidades"],
            char_class="alchemist",
            player_level=5,
            attr_points_remaining=0,
            skill_points_remaining=0,
        )
        self.engine._memory_state = mem

        # Cursor começa no lado direito (Menu S)
        self.injector.cursor_position.return_value = (1400, 500)
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)

        # Alchemist linha 0: layout é [None, 2, 3]. Coluna ponte é col 1.
        self.assertEqual(self.engine._skill_focus_col, 1)
        # D-pad left na coluna de ponte deve atravessar para o Menu C (strength_bridge)
        s = self._make_state(dpad_left=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")
        self.assertTrue(self.shared.get().char_menu_open)

        # Cursor agora no lado esquerdo (Menu C)
        self.injector.cursor_position.return_value = (400, 500)
        # D-pad right no Menu C a partir do nó de ponte deve atravessar de volta para o Menu S
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)
        self.assertEqual(self.engine._skill_focus_row, 0)
    def test_char_menu_orange_nodes_navigation(self):
        # Menu C aberto sozinho (sem Menu S)
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos"],
            attr_points_remaining=0,
        )
        self.engine._memory_state = mem

        # Inicializa em strength
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength")

        # 1. D-pad right vai para o nó laranja (strength_bridge)
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")

        # 2. D-pad right quando Menu S não está aberto mantém o foco no nó laranja
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")

        # 3. Navegação para baixo pela coluna laranja:
        # strength_bridge -> dexterity_bridge -> magic_bridge -> defense_bridge -> res_fire -> res_ice
        expected_down = [
            "dexterity_bridge",
            "magic_bridge",
            "defense_bridge",
            "res_fire",
            "res_ice",
        ]
        t = 1.15
        for node in expected_down:
            s = self._make_state(dpad_down=True)
            self.engine._process_active(self.hub, s, self.rect, self.cfg, now=t, dt=0.016)
            self.assertEqual(self.engine._char_menu_focus, node)
            t += 0.05

        # 4. Navegação horizontal na resistência: res_ice (laranja) -> res_electric (verde)
        s = self._make_state(dpad_left=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=t, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "res_electric")
        t += 0.05

        # Volta para res_ice
        s = self._make_state(dpad_right=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=t, dt=0.016)
        self.assertEqual(self.engine._char_menu_focus, "res_ice")
        t += 0.05

        # 5. Navegação para cima pela coluna laranja até o topo:
        # res_ice -> res_fire -> defense_bridge -> magic_bridge -> dexterity_bridge -> strength_bridge -> mp -> fame -> xp
        expected_up = [
            "res_fire",
            "defense_bridge",
            "magic_bridge",
            "dexterity_bridge",
            "strength_bridge",
            "mp",
            "fame",
            "xp",
        ]
        for node in expected_up:
            s = self._make_state(dpad_up=True)
            self.engine._process_active(self.hub, s, self.rect, self.cfg, now=t, dt=0.016)
            self.assertEqual(self.engine._char_menu_focus, node)
            t += 0.05


    def test_skill_tab_switching_debounce_and_sync(self):
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="destroyer",
            player_level=5,
        )
        self.engine._memory_state = mem

        # Inicializa na aba 1 (berserker)
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 1)

        # R2 avança para aba 2 (titan)
        self.injector.mouse_button.reset_mock()
        s = self._make_state(rt=1.0)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 2)
        self.assertEqual(self.shared.get().skill_tab, 2)
        self.injector.mouse_button.assert_any_call("left", True)
        self.injector.mouse_button.assert_any_call("left", False)

        # Trigger rápido durante debounce (< 0.25s) NÃO deve trocar de aba
        s = self._make_state(rt=1.0)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.10, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 2)

        # Solta o gatilho entre cliques
        s = self._make_state(rt=0.0)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.20, dt=0.016)

        # Após vencer o debounce (> 0.25s), novo pressionamento de R2 avança para aba 3 (spectral)
        s = self._make_state(rt=1.0)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.35, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 3)
        self.assertEqual(self.shared.get().skill_tab, 3)

    def test_skill_tab_preserved_on_menu_close_and_reopen(self):
        mem_open = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="alchemist",
            player_level=5,
        )
        mem_closed = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=[],
            char_class="alchemist",
            player_level=5,
        )

        # 1. Abre menu de habilidades e inicializa na aba 1 (arcane)
        self.engine._memory_state = mem_open
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 1)

        # 2. Troca para a aba 2 (lore) via RT
        s = self._make_state(rt=1.0)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 2)
        self.assertEqual(self.shared.get().skill_tab, 2)

        # 3. Fecha o menu (jogo fecha a janela)
        self.engine._memory_state = mem_closed
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.10, dt=0.016)
        self.assertFalse(self.engine._skill_menu_initialized)
        self.assertEqual(self.engine._skill_tab, 2)  # Deve preservar aba 2

        # 4. Reabre o menu de habilidades
        self.engine._memory_state = mem_open
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.15, dt=0.016)
        self.assertTrue(self.engine._skill_menu_initialized)
        # O jogo não reseta para aba 1 ao reabrir: overlay e engine continuam na aba 2
        self.assertEqual(self.engine._skill_tab, 2)
        self.assertEqual(self.shared.get().skill_tab, 2)

    def test_skill_spells_navigation(self):
        mem = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="destroyer",
            player_level=5,
            skill_points_remaining=0,
        )
        self.engine._memory_state = mem

        # Inicializa no menu S
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)

        # Força o foco para a última linha (Row 5, col 1)
        self.engine._skill_focus_row = 5
        self.engine._skill_focus_col = 1
        self.engine._skill_in_tabbar = False
        self.engine._skill_in_pink = False
        self.engine._skill_in_spells = False

        # D-pad down a partir da Row 5 (sem pontos de upgrade) desce para a seção de Spells
        s = self._make_state(dpad_down=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertTrue(self.engine._skill_in_spells)
        # Deve ter dado snap para o slot de spell mais próximo da col 1 (848.5 -> spell 1 ou 2)
        self.assertIn(self.engine._skill_spell_idx, (1, 2))
        self.assertEqual(self.shared.get().skill_focus, f"spell_{self.engine._skill_spell_idx}")

        # Navega para a esquerda até spell_0 (laranja / ponte)
        while self.engine._skill_spell_idx > 0:
            s = self._make_state(dpad_left=True)
            self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)
        self.assertEqual(self.engine._skill_spell_idx, 0)
        self.assertEqual(self.shared.get().skill_focus, "spell_0")

        # Navega para a direita: spell_0 -> spell_1 -> spell_2 -> spell_3
        for expected_idx in (1, 2, 3):
            s = self._make_state(dpad_right=True)
            self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.15, dt=0.016)
            self.assertEqual(self.engine._skill_spell_idx, expected_idx)
            self.assertEqual(self.shared.get().skill_focus, f"spell_{expected_idx}")

        # D-pad up a partir de Spells sobe de volta para a Row 5
        s = self._make_state(dpad_up=True)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.20, dt=0.016)
        self.assertFalse(self.engine._skill_in_spells)
        self.assertEqual(self.engine._skill_focus_row, 5)

    def test_character_change_resets_skill_tab_and_layout(self):
        # 1. Vanquisher começa no jogo com menu de habilidades aberto
        mem_vanq = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="vanquisher",
            player_level=10,
        )
        self.engine._memory_state = mem_vanq
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)
        self.assertEqual(self.engine._char_class, "vanquisher")
        self.assertEqual(self.engine._skill_tab, 1)

        # 2. Muda para aba 2 (rogue) via RT
        s = self._make_state(rt=1.0)
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.05, dt=0.016)
        self.assertEqual(self.engine._skill_tab, 2)
        self.assertEqual(self.shared.get().skill_tab, 2)

        # 3. Jogador sai para a tela de título/carregar (fora do gameplay)
        mem_menu = GameMemoryState(
            is_connected=True,
            is_in_game=False,
            open_menus=["Menu Principal"],
            char_class="",
        )
        self.engine._memory_state = mem_menu
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.35, dt=0.016)
        self.assertEqual(self.engine._char_class, "")
        self.assertEqual(self.engine._skill_tab, 1)

        # 4. Entra no jogo com Destroyer e abre o menu de habilidades
        mem_destr = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="destroyer",
            player_level=5,
        )
        self.engine._memory_state = mem_destr
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.40, dt=0.016)

        # 5. A aba DEVE estar resetada para a primeira aba (1: berserker) e classe deve ser destroyer
        self.assertEqual(self.engine._char_class, "destroyer")
        self.assertEqual(self.engine._skill_tab, 1)
        self.assertEqual(self.shared.get().char_class, "destroyer")
        self.assertEqual(self.shared.get().skill_tab, 1)

    def test_direct_class_switch_in_memory_resets_skill_tab(self):
        # Caso em que a classe muda diretamente na memória RAM (ex: troca rápida de personagem)
        mem_vanq = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="vanquisher",
            player_level=10,
        )
        self.engine._memory_state = mem_vanq
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.0, dt=0.016)

        # Avança para aba 3
        self.engine._skill_tab = 3
        self.shared.update(skill_tab=3)

        # Memória agora reporta Alchemist
        mem_alch = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Habilidades"],
            char_class="alchemist",
            player_level=15,
        )
        self.engine._memory_state = mem_alch
        s = self._make_state()
        self.engine._process_active(self.hub, s, self.rect, self.cfg, now=1.1, dt=0.016)

        self.assertEqual(self.engine._char_class, "alchemist")
        self.assertEqual(self.engine._skill_tab, 1)
        self.assertEqual(self.shared.get().char_class, "alchemist")
        self.assertEqual(self.shared.get().skill_tab, 1)


class PetSkillMenuBridgeTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_pet_to_skill_bridge_jumps(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Habilidades"],
            char_class="destroyer",
        )
        self.engine._pet_inventory_initialized = True
        self.engine._skill_menu_initialized = True
        self.engine._skill_tab = 1
        self.engine._char_class = "destroyer"

        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (200, 500)

        # 1. Pet pet_spell_2 + D-pad Right -> Linha 0 (nó laranja) da Skill Tree
        self.engine._pet_inventory_focus = "pet_spell_2"
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        # Destroyer tab 1 (berserker) row 0: [None, 1, 2] -> bridge col is 1
        self.assertEqual(self.engine._skill_focus_row, 0)
        self.assertEqual(self.engine._skill_focus_col, 1)
        self.assertFalse(self.engine._skill_in_spells)

        # 2. Pet (1, 7) + D-pad Right -> Linha 4 da Skill Tree
        self.engine._pet_inventory_focus = (1, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        # Destroyer tab 1 row 4: [None, 1, 2] -> bridge col is 1
        self.assertEqual(self.engine._skill_focus_row, 4)
        self.assertEqual(self.engine._skill_focus_col, 1)
        self.assertFalse(self.engine._skill_in_spells)

        # 3. Pet (2, 7) + D-pad Right -> Linha 5 da Skill Tree
        self.engine._pet_inventory_focus = (2, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        # Destroyer tab 1 row 5: [0, 1, None] -> bridge col is 0
        self.assertEqual(self.engine._skill_focus_row, 5)
        self.assertEqual(self.engine._skill_focus_col, 0)
        self.assertFalse(self.engine._skill_in_spells)

        # 4. Pet (3, 7) + D-pad Right -> Spells (spell_0 no rodapé)
        self.engine._pet_inventory_focus = (3, 7)
        self.engine._handle_pet_inventory_navigation(state_r, self.rect, self.hub_mock)
        self.assertTrue(self.engine._skill_in_spells)
        self.assertEqual(self.engine._skill_spell_idx, 0)

    def test_skill_to_pet_bridge_jumps(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Habilidades"],
            char_class="destroyer",
        )
        self.engine._pet_inventory_initialized = True
        self.engine._skill_menu_initialized = True
        self.engine._skill_tab = 1
        self.engine._char_class = "destroyer"

        state_l = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (800, 500)

        # 1. Skill Linha 0 (nó laranja) + D-pad Left -> Pet pet_spell_2
        self.engine._skill_focus_row = 0
        self.engine._skill_focus_col = 1
        self.engine._skill_in_spells = False
        self.engine._handle_skill_menu_navigation(
            state_l, self.rect, self.hub_mock,
            char_also_open=False, pet_also_open=True,
            skill_points=0, char_class="destroyer"
        )
        self.assertEqual(self.engine._pet_inventory_focus, "pet_spell_2")

        # 2. Skill Linha 2 (nó laranja col 0) + D-pad Left -> Pet pet_spell_2
        self.engine._skill_focus_row = 2
        self.engine._skill_focus_col = 0
        self.engine._handle_skill_menu_navigation(
            state_l, self.rect, self.hub_mock,
            char_also_open=False, pet_also_open=True,
            skill_points=0, char_class="destroyer"
        )
        self.assertEqual(self.engine._pet_inventory_focus, "pet_spell_2")

        # 3. Skill Linha 4 (nó laranja col 1) + D-pad Left -> Pet (1, 7)
        self.engine._skill_focus_row = 4
        self.engine._skill_focus_col = 1
        self.engine._handle_skill_menu_navigation(
            state_l, self.rect, self.hub_mock,
            char_also_open=False, pet_also_open=True,
            skill_points=0, char_class="destroyer"
        )
        self.assertEqual(self.engine._pet_inventory_focus, (1, 7))

        # 4. Skill Linha 5 (nó laranja col 0) + D-pad Left -> Pet (2, 7)
        self.engine._skill_focus_row = 5
        self.engine._skill_focus_col = 0
        self.engine._handle_skill_menu_navigation(
            state_l, self.rect, self.hub_mock,
            char_also_open=False, pet_also_open=True,
            skill_points=0, char_class="destroyer"
        )
        self.assertEqual(self.engine._pet_inventory_focus, (2, 7))

        # 5. Skill Spells (spell_0) + D-pad Left -> Pet (3, 7)
        self.engine._skill_in_spells = True
        self.engine._skill_spell_idx = 0
        self.engine._handle_skill_menu_navigation(
            state_l, self.rect, self.hub_mock,
            char_also_open=False, pet_also_open=True,
            skill_points=0, char_class="destroyer"
        )
        self.assertEqual(self.engine._pet_inventory_focus, (3, 7))

    def test_dual_pet_skill_dispatch_by_cursor_position(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Pet", "Habilidades"],
            char_class="destroyer",
        )
        self.engine._pet_inventory_initialized = True
        self.engine._pet_inventory_focus = (1, 1)
        self.engine._skill_menu_initialized = True
        self.engine._skill_tab = 1
        self.engine._skill_focus_row = 0
        self.engine._skill_focus_col = 1
        self.engine._char_class = "destroyer"

        cfg = self.config.get()
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)

        # 1. Cursor na esquerda (x=200 < 512): navega no Pet, Skill focus não muda!
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.engine._process_active(self.hub_mock, state_r, self.rect, cfg, 1.0, 0.016)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 2))
        self.assertEqual(self.engine._skill_focus_row, 0)
        self.assertEqual(self.engine._skill_focus_col, 1)

        # 2. Cursor na direita (x=800 >= 512): navega na Skill, Pet focus não muda!
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.engine._previous = ControllerState(connected=True)
        # Destroyer tab 1 row 0: [None, 1, 2]. From col 1 + right -> col 2
        self.engine._process_active(self.hub_mock, state_r, self.rect, cfg, 1.05, 0.016)
        self.assertEqual(self.engine._pet_inventory_focus, (1, 2))
        self.assertEqual(self.engine._skill_focus_row, 0)
        self.assertEqual(self.engine._skill_focus_col, 2)


class CharInventoryMenuBridgeTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = ConfigManager(Path(self._temp_dir.name) / "perfil.json")
        self.shared = SharedOverlayState()
        self.engine = BridgeEngine(self.config, self.shared)
        self.engine.injector = MagicMock()
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.hub_mock = MagicMock()
        self.rect = Rect(left=0, top=0, width=1024, height=768)

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_char_to_inventory_bridge_jumps(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos", "Inventário"],
            char_class="destroyer",
        )
        self.engine._char_menu_initialized = True
        self.engine._inventory_initialized = True
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (200, 500)

        # 1. xp + D-pad Right -> helmet
        self.engine._char_menu_focus = "xp"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, "helmet")

        # 2. mp + D-pad Right -> gloves
        self.engine._char_menu_focus = "mp"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, "gloves")

        # 3. strength_bridge + D-pad Right -> belt
        self.engine._char_menu_focus = "strength_bridge"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, "belt")

        # 4. dexterity_bridge + D-pad Right -> main_hand
        self.engine._char_menu_focus = "dexterity_bridge"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, "main_hand")

        # 5. magic_bridge + D-pad Right -> spell_1
        self.engine._char_menu_focus = "magic_bridge"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, "spell_1")

        # 6. defense_bridge + D-pad Right -> Grid (1, 1)
        self.engine._char_menu_focus = "defense_bridge"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 7. res_fire + D-pad Right -> Grid (2, 1)
        self.engine._char_menu_focus = "res_fire"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, (2, 1))

        # 8. res_ice + D-pad Right -> Grid (3, 1)
        self.engine._char_menu_focus = "res_ice"
        self.engine._handle_char_menu_navigation(
            state_r, self.rect, self.hub_mock,
            skill_also_open=False, inv_also_open=True, attr_points=0
        )
        self.assertEqual(self.engine._inventory_focus, (3, 1))

    def test_inventory_to_char_bridge_jumps(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos", "Inventário"],
            char_class="destroyer",
        )
        self.engine._char_menu_initialized = True
        self.engine._inventory_initialized = True
        state_l = ControllerState(connected=True, buttons={"dpad_left"})
        self.engine._previous = ControllerState(connected=True)
        self.engine.injector.cursor_position.return_value = (800, 500)

        # 1. helmet + D-pad Left -> xp
        self.engine._inventory_focus = "helmet"
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "xp")

        # 2. gloves + D-pad Left -> mp
        self.engine._inventory_focus = "gloves"
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "mp")

        # 3. belt + D-pad Left -> strength_bridge
        self.engine._inventory_focus = "belt"
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")

        # 4. main_hand + D-pad Left -> dexterity_bridge
        self.engine._inventory_focus = "main_hand"
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "dexterity_bridge")

        # 5. spell_1 + D-pad Left -> magic_bridge
        self.engine._inventory_focus = "spell_1"
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "magic_bridge")

        # 6. Grid (1, 1) + D-pad Left -> defense_bridge
        self.engine._inventory_focus = (1, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "defense_bridge")

        # 7. Grid (2, 1) + D-pad Left -> res_fire
        self.engine._inventory_focus = (2, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "res_fire")

        # 8. Grid (3, 1) + D-pad Left -> res_ice
        self.engine._inventory_focus = (3, 1)
        self.engine._handle_inventory_navigation(state_l, self.rect, self.hub_mock)
        self.assertEqual(self.engine._char_menu_focus, "res_ice")

    def test_dual_char_inventory_dispatch_by_cursor_position(self):
        self.engine._memory_state = GameMemoryState(
            is_connected=True,
            is_in_game=True,
            open_menus=["Atributos", "Inventário"],
            char_class="destroyer",
        )
        self.engine._char_menu_initialized = True
        self.engine._char_menu_focus = "strength"
        self.engine._inventory_initialized = True
        self.engine._inventory_focus = (1, 1)

        cfg = self.config.get()
        state_r = ControllerState(connected=True, buttons={"dpad_right"})
        self.engine._previous = ControllerState(connected=True)

        # 1. Cursor na esquerda (x=200 < 512): navega no menu Character, foco do Inventário não muda!
        self.engine.injector.cursor_position.return_value = (200, 500)
        self.engine._process_active(self.hub_mock, state_r, self.rect, cfg, 1.0, 0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")
        self.assertEqual(self.engine._inventory_focus, (1, 1))

        # 2. Cursor na direita (x=800 >= 512): navega no Inventário, foco do Character não muda!
        self.engine.injector.cursor_position.return_value = (800, 500)
        self.engine._previous = ControllerState(connected=True)
        self.engine._process_active(self.hub_mock, state_r, self.rect, cfg, 1.05, 0.016)
        self.assertEqual(self.engine._char_menu_focus, "strength_bridge")
        self.assertEqual(self.engine._inventory_focus, (1, 2))


if __name__ == "__main__":
    unittest.main()


