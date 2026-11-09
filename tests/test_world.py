"""Map coordinates, projection, classification and public diagnostics."""
from dataclasses import replace
import math
import unittest

from torchbridge.memory import GameMemoryState
from torchbridge.world import WorldCamera, WorldEntity, WorldPosition, WorldSnapshot, classify_prop
from torchbridge.world_inspect import world_report


IDENTITY = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)
# A camera looking down Ogre -Z; project x/height, with the world in front at z < 0.
CAMERA = WorldCamera(IDENTITY, (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., -1.02, -.202, 0., 0., -1., 0.))


def world_fixture(now=10.):
    npc = WorldEntity(0x200000, "npc", "Vasman", WorldPosition(.5, -4.))
    return WorldSnapshot(0x100000, "TOWN", 0x300000, WorldPosition(0., -4.),
                         (npc,), CAMERA, now, True, "Disponível")


class WorldTests(unittest.TestCase):
    def test_requested_categories_and_localized_names(self):
        cases = {"PORTAL": "portal", "STAIRSDOWN": "stairs", "STAIRSUP": "stairs",
                 "HEALINGSHRINE": "health_shrine", "MANASHRINE": "mana_shrine",
                 "ENCHANTSHRINE": "enchant_shrine", "MINE_DOOR": "door",
                 "CRYPTGATE": "door", "SIMPLELEVER": "lever", "FISHINGHOLE": "fishing",
                 "WARPTO": "portal", "CHEST": "chest", "UNKNOWN": "interactive"}
        for identifier, kind in cases.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(classify_prop(identifier, ""), kind)
        self.assertEqual(classify_prop("", "Fonte de melhoria"), "enchant_shrine")
        self.assertEqual(classify_prop("", "Local de pesca"), "fishing")

    def test_map_distance_ignores_height_but_nearby_excludes_other_floors(self):
        self.assertEqual(WorldPosition(0, 0).distance_to(WorldPosition(3, 4, 20)), 5)
        world = world_fixture()
        high = replace(world.entities[0], address=0x200004, position=WorldPosition(0, -4, 10))
        far = replace(world.entities[0], address=0x200008, position=WorldPosition(5, -4))
        world = replace(world, entities=(far, high, *world.entities))
        self.assertEqual(world.nearby(3.5), (world.entities[2],))
        self.assertEqual(world.nearby(math.nan), ())

    def test_project_real_perspective_and_client_coordinates(self):
        self.assertEqual(CAMERA.project(WorldPosition(0, -4), 1920, 1080), (960, 540))
        self.assertEqual(CAMERA.project(WorldPosition(1, -4), 1920, 1080), (1200, 540))
        self.assertEqual(CAMERA.project(WorldPosition(0, -4), 960, 540), (480, 270))
        self.assertEqual(CAMERA.project(WorldPosition(0, -4), 1920, 1080, 1), (960, 405))

    def test_projection_rejects_behind_offscreen_invalid_or_clipped_points(self):
        for position in (WorldPosition(0, 1), WorldPosition(30, -4), WorldPosition(0, -.01),
                         WorldPosition(0, -1000), WorldPosition(math.nan, -4), WorldPosition(0, -4, math.inf)):
            self.assertIsNone(CAMERA.project(position, 1920, 1080))
        self.assertIsNone(replace(CAMERA, view=(0.,) * 16).project(WorldPosition(0, -4), 1920, 1080))
        self.assertIsNone(replace(CAMERA, projection=(math.nan,) * 16).project(WorldPosition(0, -4), 1920, 1080))

    def test_freshness_and_deterministic_nearest(self):
        world = world_fixture()
        self.assertTrue(world.fresh(10.1))
        self.assertFalse(world.fresh(10.3))
        self.assertFalse(world.fresh(9.9))
        tie = replace(world.entities[0], address=0x10000)
        world = replace(world, entities=(*world.entities, tie))
        self.assertEqual(world.nearby(3.5)[0], tie)

    def test_report_exposes_complete_roster_and_map_axes_without_camera_matrices(self):
        report = world_report(GameMemoryState(is_connected=True, game_version="Steam", world=world_fixture()))
        self.assertEqual(report["player_position"], {"x": 0., "y": -4., "height": 0.})
        self.assertEqual(report["entities"][0]["distance"], .5)
        self.assertTrue(report["roster_complete"])
        self.assertTrue(report["camera_available"])
        self.assertNotIn("projection", report)
        self.assertIsNone(world_report(GameMemoryState())["player_position"])

    def test_npc_roles_and_quest_status_are_exposed_in_labels_and_json(self):
        world = world_fixture()
        npc = replace(world.entities[0], npc_role="merchant", quest_status="available")
        world = replace(world, entities=(npc,))
        entity = world_report(GameMemoryState(world=world))["entities"][0]
        self.assertEqual(entity["kind"], "npc")
        self.assertEqual(entity["npc_role"], "merchant")
        self.assertEqual(entity["quest_status"], "available")
        self.assertEqual(entity["label"], "Mercador · Missão disponível (!)")
        for status, text in (("in_progress", "em andamento"), ("ready_to_turn_in", "para entregar"),
                             ("unavailable", "indisponível"), ("unknown", "não verificada")):
            self.assertIn(text, replace(npc, quest_status=status).label)
