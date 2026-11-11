"""Synthetic PE32 address spaces exercised through BOTH real read transports."""
import ctypes
import math
import struct
import time
import unittest
from unittest.mock import patch

from torchbridge.memory import TorchlightMemoryReader
from torchbridge.world import WorldPosition
from torchbridge.world_memory import MAX_NODES
from test_world import CAMERA


class AddressSpace:
    def __init__(self, base=0x400000):
        self.bytes = {}
        self.next = base + 0x10000
        self.read_count = 0
        self.vtables = {}

    def allocate(self, size):
        address = self.next
        self.next += (size + 15) // 16 * 16
        self.put(address, bytes(size))
        return address

    def put(self, address, data):
        self.bytes.update((address + i, b) for i, b in enumerate(data))

    def u32(self, address, value):
        self.put(address, struct.pack("<I", value))

    def u8(self, address, value):
        self.put(address, bytes([value]))

    def f32(self, address, value):
        self.put(address, struct.pack("<f", value))

    def read(self, address, size):
        self.read_count += 1
        try:
            return bytes(self.bytes[address + i] for i in range(size))
        except KeyError:
            return b""

    def windows_read(self, handle, address, out, size, count):
        raw = self.read(address.value, size)
        ctypes.memmove(out, raw, len(raw))
        count._obj.value = len(raw)
        return bool(raw)

    def string(self, address, value):
        data = value.encode("utf-16-le")
        header = bytearray(28)
        if len(value) < 8:
            header[4:4 + len(data)] = data
            capacity = 7
        else:
            buffer = self.allocate(len(data) + 2)
            self.put(buffer, data)
            struct.pack_into("<I", header, 4, buffer)
            capacity = len(value)
        struct.pack_into("<II", header, 20, len(value), capacity)
        self.put(address, header)

    def unit(self, cls, name="", identifier="", position=(0., 0., -4.)):
        address = self.allocate(0xA20)
        if cls not in self.vtables:
            td = self.allocate(128)
            self.put(td + 8, f".?AV{cls}@@".encode() + b"\0")
            col = self.allocate(24)
            self.u32(col + 12, td)
            vt = self.allocate(16) + 4
            self.u32(vt - 4, col)
            self.vtables[cls] = vt
        self.u32(address, self.vtables[cls])
        self.u8(address + 0x6E, 1)
        self.u8(address + 0x161, 1)
        self.u8(address + 0x19C, 1)
        self.f32(address + 0x394, 100.)
        self.u32(address + 0x28C, 3)
        self.put(address + 0x70, struct.pack("<3f", *position))
        self.string(address + 0x30, identifier)
        self.string(address + (0x420 if cls in ("CPlayer", "CCharacter", "CMonster") else 0x1B0), name)
        return address

    def linked_list(self, level, offset, units):
        container = self.allocate(4)
        node = 0
        for unit in reversed(units):
            new = self.allocate(8)
            self.put(new, struct.pack("<II", unit, node))
            node = new
        self.u32(container, node)
        self.u32(level + offset, container)
        return node

    def tags(self, unit, names, offset=0x114):
        templates = []
        for name in names:
            tag = self.allocate(0x40)
            self.string(tag + 0x18, name)
            templates.append(tag)
        data = self.allocate(len(templates) * 4) if templates else 0
        if templates:
            self.put(data, struct.pack("<" + "I" * len(templates), *templates))
        self.put(unit + offset, struct.pack("<III", data, len(templates), len(templates)))
        return templates


def memory_fixture(base=0x400000):
    space = AddressSpace(base)
    client = space.allocate(0x2500)
    level = space.allocate(0x500)
    player = space.unit("CPlayer", "Hero", "Destroyer", (10., 2., 20.))
    pet = space.unit("CMonster", "Dog")
    npc = space.unit("CMonster", "Vasman", position=(11., 2., 20.))
    space.u32(client + 0x2C, player)
    space.u32(client + 0x30, pet)
    space.u32(client + 0x38, level)
    space.string(level + 0x1F0, "TOWN")
    node = space.linked_list(level, 0x5C, [player, pet, npc])
    props = [space.unit("CTriggerUnit", name, identifier, (12., 2., 20.))
             for name, identifier in (("Portal", "PORTAL"), ("Stairs", "STAIRSUP"),
                                      ("Healing Shrine", "HEALINGSHRINE"), ("Mana Shrine", "MANASHRINE"),
                                      ("Enchanting Shrine", "ENCHANTSHRINE"), ("Door", "MINE_DOOR"),
                                      ("Lever", "SIMPLELEVER"), ("Fishing Hole", "FISHINGHOLE"))]
    space.linked_list(level, 0x68, props)
    control, camera = space.allocate(16), space.allocate(0x600)
    space.u32(client + 0x10, control)
    space.u32(control + 8, camera)
    space.put(camera + 0x25C, struct.pack("<16f", *CAMERA.view))
    space.put(camera + 0x21C, struct.pack("<16f", *CAMERA.projection))
    reader = TorchlightMemoryReader()
    reader._handle = 1
    reader._linux = space
    return space, reader, client, level, player, pet, npc, props, node


class WorldMemoryTests(unittest.TestCase):
    def test_live_native_nameplate_tracks_visibility_and_rect_on_both_transports(self):
        for transport in ("Windows", "Proton"):
            with self.subTest(transport=transport), patch("torchbridge.memory.kernel32") as kernel:
                space, reader, client, level, player, _, _, props, _ = memory_fixture()
                if transport == "Windows":
                    reader._linux = None
                    kernel.ReadProcessMemory.side_effect = space.windows_read
                ui = space.allocate(0x1700)
                space.u32(client + 0x3C, ui)
                space.put(ui + 0x13E4, struct.pack("<2f", 1920., 1080.))
                window, parent = space.allocate(0x400), space.allocate(0x400)
                space.u32(window + 0x80, parent)
                space.u8(window + 0x1A1, 1)
                space.u8(parent + 0x1A1, 1)
                space.u32(props[0] + 0x198, window)
                space.put(window + 0x360, struct.pack("<4f", 600., 300., 800., 330.))

                def label():
                    return next(e for e in reader._world_reader.read(client, player, 10.).entities
                                if e.address == props[0]).native_label_rect

                self.assertIsNone(label())
                space.u8(props[0] + 0x1A4, 1)  # Alt/HUD made this native label visible.
                self.assertEqual(label(), (600/1920, 300/1080, 800/1920, 330/1080))
                # Read native overlap avoidance/camera changes, never a projected guess.
                space.put(window + 0x360, struct.pack("<4f", 700., 350., 900., 380.))
                self.assertEqual(label(), (700/1920, 350/1080, 900/1920, 380/1080))
                space.u8(parent + 0x1A1, 0)
                self.assertIsNone(label())
                space.u8(parent + 0x1A1, 1)
                space.u8(props[0] + 0x1A4, 0)  # Alt/HUD hid it again, window still allocated.
                self.assertIsNone(label())

    def test_native_label_rejects_unreadable_cyclic_and_invalid_geometry(self):
        space, reader, client, _, player, _, _, props, _ = memory_fixture()
        ui, window = space.allocate(0x1700), space.allocate(0x400)
        space.u32(client + 0x3C, ui)
        space.put(ui + 0x13E4, struct.pack("<2f", 1280., 720.))
        space.u32(props[0] + 0x198, window)
        space.u8(props[0] + 0x1A4, 1)
        space.u8(window + 0x1A1, 1)
        for rect in ((0., 0., 0., 0.), (300., 20., 200., 40.), (math.nan, 20., 200., 40.),
                     (20., 20., 1400., 40.)):
            space.put(window + 0x360, struct.pack("<4f", *rect))
            world = reader._world_reader.read(client, player, 10.)
            self.assertTrue(world.roster_complete)
            self.assertIsNone(next(e for e in world.entities if e.address == props[0]).native_label_rect)
        space.put(window + 0x360, struct.pack("<4f", 20., 20., 200., 40.))
        space.u32(window + 0x80, window)
        world = reader._world_reader.read(client, player, 10.)
        self.assertIsNone(next(e for e in world.entities if e.address == props[0]).native_label_rect)

    def test_fishing_radius_is_read_without_giving_other_objects_extra_reach(self):
        space, reader, client, level, player, *_ = memory_fixture()
        hole = space.unit("CTriggerUnit", "Fishing Hole", "FISHINGHOLE")
        door = space.unit("CTriggerUnit", "Door", "DOOR")
        space.u32(hole + 0x174, 122)
        for address in (hole, door):
            space.f32(address + 0x15C, 3.25)
        space.linked_list(level, 0x68, [hole, door])
        entities = {e.address: e for e in reader._world_reader.read(client, player, 10.).entities}
        self.assertEqual(entities[hole].interaction_radius, 3.25)
        self.assertEqual(entities[hole].action_radius(4.5), 7.75)
        self.assertEqual(entities[door].interaction_radius, 0.)
        self.assertEqual(entities[door].action_radius(4.5), 4.5)

    def test_interactive_subclasses_are_discovered_through_rtti_bases(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        custom=space.unit("CCustomDoor", "Porta", "CUSTOM_DOOR")
        vt=space.vtables["CCustomDoor"]
        col=struct.unpack("<I",space.read(vt-4,4))[0]
        descriptors=[]
        for base in ("CTriggerUnit","CItem"):
            space.unit(base)
            base_col=struct.unpack("<I",space.read(space.vtables[base]-4,4))[0]
            td=struct.unpack("<I",space.read(base_col+12,4))[0]
            descriptor=space.allocate(28);space.u32(descriptor,td);descriptors.append(descriptor)
        array=space.allocate(8);space.put(array,struct.pack("<2I",*descriptors))
        hierarchy=space.allocate(16)
        space.u32(hierarchy+8,2);space.u32(hierarchy+12,array);space.u32(col+16,hierarchy)
        space.linked_list(level,0x68,[custom])
        world=reader._world_reader.read(client,player,10.)
        entity=next(e for e in world.entities if e.address==custom)
        self.assertEqual(entity.kind,"door")
        self.assertEqual(entity.interaction_method,"item")

    def test_unreadable_interactive_position_marks_the_roster_incomplete(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        space.f32(npc+0x70,math.nan)
        self.assertFalse(reader._world_reader.read(client,player,10.).roster_complete)

    def test_barrel_variants_and_other_destructibles_use_their_base_class(self):
        space, reader, client, level, player, *_ = memory_fixture()
        destructibles = []
        for cls, name in (("CBreakable", "Barrel"), ("CExplosiveBarrel", "Explosive Barrel"),
                          ("CModdedUrn", "Portal")):
            address = space.unit(cls, name, "CHEST")
            destructibles.append(address)
            if cls == "CBreakable":
                continue
            vt = space.vtables[cls]
            col = struct.unpack("<I", space.read(vt - 4, 4))[0]
            descriptors = []
            for base in ("CBreakable", "CItem"):
                space.unit(base)
                base_col = struct.unpack("<I", space.read(space.vtables[base] - 4, 4))[0]
                td = struct.unpack("<I", space.read(base_col + 12, 4))[0]
                descriptor = space.allocate(28)
                space.u32(descriptor, td)
                descriptors.append(descriptor)
            bases = space.allocate(8)
            space.put(bases, struct.pack("<2I", *descriptors))
            hierarchy = space.allocate(16)
            space.u32(hierarchy + 8, 2)
            space.u32(hierarchy + 12, bases)
            space.u32(col + 16, hierarchy)
        space.linked_list(level, 0x68, destructibles)
        world = reader._world_reader.read(client, player, 10.)
        self.assertEqual({e.address for e in world.entities if e.kind == "breakable"}, set(destructibles))
        self.assertFalse(any(e.is_pickup for e in world.entities))

    def test_merchant_roles_use_unit_types_on_both_transports_without_name_guesses(self):
        roles = {41: "merchant", 127: "gambler", 130: "enchanter", 134: "transmuter",
                 132: "gem_recover", 133: "gem_destroy", 128: "stash",
                 170: "shared_stash", 175: "retirement", 104: ""}
        for transport in ("Windows", "Proton"):
            with self.subTest(transport=transport):
                space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
                space.string(npc + 0x420, "Unknown localized name")
                with patch("torchbridge.memory.kernel32") as kernel:
                    if transport == "Windows":
                        reader._linux = None
                        kernel.ReadProcessMemory.side_effect = space.windows_read
                    for unit_type, role in roles.items():
                        space.u32(npc + 0x174, unit_type)
                        entity = next(e for e in reader._world_reader.read(client, player, 10.).entities
                                      if e.address == npc)
                        self.assertEqual(entity.npc_role, role)
                        self.assertEqual(entity.is_merchant, unit_type in (41, 127))
                space.string(npc + 0x420, "Tarn the Merchant")
                space.u32(npc + 0x174, 104)
                reader._linux = space
                entity = next(e for e in reader._world_reader.read(client, player, 10.).entities if e.address == npc)
                self.assertEqual(entity.npc_role, "")

    def test_quest_status_tracks_live_marker_changes_and_removal_on_both_transports(self):
        for transport in ("Windows", "Proton"):
            space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
            with self.subTest(transport=transport), patch("torchbridge.memory.kernel32") as kernel:
                if transport == "Windows":
                    reader._linux = None
                    kernel.ReadProcessMemory.side_effect = space.windows_read
                for marker, status in (("QUEST GIVING", "available"), ("QUEST INCOMPLETE", "in_progress"),
                                       ("QUEST COMPLETE", "ready_to_turn_in"), ("QUEST PASSIVE", "unavailable"),
                                       ("INVINCIBLE", "")):
                    space.tags(npc, [marker])
                    entity = next(e for e in reader._world_reader.read(client, player, 10.).entities if e.address == npc)
                    self.assertEqual(entity.quest_status, status)
                space.tags(npc, [])
                entity = next(e for e in reader._world_reader.read(client, player, 10.02).entities if e.address == npc)
                self.assertEqual(entity.quest_status, "")

    def test_pending_quest_tags_and_merchant_with_a_quest_preserve_both_roles(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        space.u32(npc + 0x174, 41)
        space.tags(npc, ["INVINCIBLE"])
        space.tags(npc, ["QUEST GIVING"], offset=0x124)
        entity = next(e for e in reader._world_reader.read(client, player, 10.).entities if e.address == npc)
        self.assertTrue(entity.is_merchant)
        self.assertEqual(entity.quest_status, "available")
        self.assertIn("Mercador", entity.label)
        self.assertIn("Missão disponível", entity.label)
        space.tags(npc, ["QUEST COMPLETE"])
        entity = next(e for e in reader._world_reader.read(client, player, 10.02).entities if e.address == npc)
        self.assertEqual(entity.quest_status, "ready_to_turn_in")

    def test_invalid_or_truncated_tag_lists_report_unknown_without_hiding_the_npc(self):
        for data, count, capacity in ((0, 129, 129), (0, 2, 1), (0x12345678, 2, 2), (0, 1, 1)):
            with self.subTest(count=count, capacity=capacity):
                space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
                space.put(npc + 0x114, struct.pack("<III", data, count, capacity))
                entity = next(e for e in reader._world_reader.read(client, player, 10.).entities if e.address == npc)
                self.assertEqual(entity.quest_status, "unknown")
                self.assertLess(space.read_count, 150)
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        space.tags(npc, ["QUEST GIVING"])
        data = reader.read_u32(npc + 0x114)
        space.u32(data, 3)
        entity = next(e for e in reader._world_reader.read(client, player, 10.).entities if e.address == npc)
        self.assertEqual(entity.quest_status, "unknown")

    def test_enemies_and_pets_are_not_classified_as_quest_npcs_or_merchants(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        for unit in (pet, npc):
            space.u32(unit + 0x174, 41)
            space.tags(unit, ["QUEST GIVING"])
        space.u32(npc + 0x28C, 2)
        world = reader._world_reader.read(client, player, 10.)
        self.assertFalse(any(e.kind == "npc" for e in world.entities))

    def test_both_transports_and_relocated_addresses_read_all_requested_types(self):
        for transport in ("Windows", "Proton"):
            for base in (0x400000, 0x900000):
                with self.subTest(transport=transport, base=base):
                    space, reader, client, level, player, pet, npc, props, _ = memory_fixture(base)
                    with patch("torchbridge.memory.kernel32") as kernel:
                        if transport == "Windows":
                            reader._linux = None
                            kernel.ReadProcessMemory.side_effect = space.windows_read
                        world = reader._world_reader.read(client, player, 10.)
                    self.assertTrue(world.roster_complete)
                    self.assertEqual(world.player_position, WorldPosition(10., 20., 2.))
                    self.assertEqual(world.level_name, "TOWN")
                    self.assertEqual(len(world.entities), 9)
                    self.assertEqual({e.kind for e in world.entities},
                                     {"npc", "portal", "stairs", "health_shrine", "mana_shrine",
                                      "enchant_shrine", "door", "lever", "fishing"})
                    self.assertNotIn(pet, [e.address for e in world.entities])
                    self.assertIsNotNone(world.camera)

    def test_live_positions_and_objects_are_not_cached(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        first = reader._world_reader.read(client, player, 10.)
        space.put(player + 0x70, struct.pack("<3f", 30., 3., 40.))
        space.put(npc + 0x70, struct.pack("<3f", 31., 3., 40.))
        space.u8(props[0] + 0x19C, 0)  # consumed/closed prop
        second = reader._world_reader.read(client, player, 10.02)
        self.assertEqual(second.player_position, WorldPosition(30., 40., 3.))
        self.assertEqual(second.entities[0].position, WorldPosition(31., 40., 3.))
        self.assertNotIn(props[0], [e.address for e in second.entities])
        self.assertEqual(first.player_position.x, 10.)

    def test_parented_objects_use_derived_world_position_and_reject_dirty_nodes(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        node = space.allocate(0x200)
        parent = space.allocate(16)
        space.u32(props[0] + 0x50, parent)
        space.u32(props[0] + 0x58, node)
        space.put(node + 0x10C, struct.pack("<3f", 100., 7., 200.))
        world = reader._world_reader.read(client, player, 10.)
        portal = next(e for e in world.entities if e.kind == "portal")
        self.assertEqual(portal.position, WorldPosition(100., 200., 7.))
        space.u8(node + 0xA0, 1)
        world = reader._world_reader.read(client, player, 10.02)
        self.assertNotIn(props[0], [e.address for e in world.entities])

    def test_corrupt_string_lengths_and_short_string_buffers_are_not_followed(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        field = props[0] + 0x1B0
        space.u32(field + 20, 0xFFFFFFFF)
        self.assertEqual(reader._world_reader._string(field), "")
        space.u32(field + 20, 20)
        space.u32(field + 24, 20)
        space.u32(field + 4, 0x12345678)
        self.assertEqual(reader._world_reader._string(field), "")

    def test_camera_invalid_data_and_alternate_culling_frustum(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        camera = reader.read_u32(reader.read_u32(client + 0x10) + 8)
        alternate = space.allocate(0x300)
        view = list(CAMERA.view)
        view[3] = -10.
        space.put(alternate + 0x25C, struct.pack("<16f", *view))
        space.u32(camera + 0x4F0, alternate)
        self.assertEqual(reader._world_reader.read(client, player, 10.).camera.view[3], -10.)
        space.f32(camera + 0x21C, math.nan)
        self.assertIsNone(reader._world_reader.read(client, player, 10.).camera)

    def test_corrupt_cycle_and_excessive_list_are_bounded(self):
        space, reader, client, level, player, pet, npc, props, node = memory_fixture()
        space.u32(node + 4, node)
        world = reader._world_reader.read(client, player, 10.)
        self.assertFalse(world.roster_complete)
        self.assertLess(space.read_count, 250)
        # Each node has a different address, so only the global node budget stops it.
        space.linked_list(level, 0x5C, [npc] * (MAX_NODES + 3))
        addresses, complete = reader._world_reader._list(level, 0x5C, [MAX_NODES])
        self.assertFalse(complete)
        self.assertEqual(len(addresses), MAX_NODES)

    def test_unreadable_list_is_distinct_from_an_empty_scene(self):
        space, reader, client, level, player, pet, npc, props, node = memory_fixture()
        space.u32(level + 0x68, 0)
        self.assertFalse(reader._world_reader.read(client, player, 10.).roster_complete)
        space.linked_list(level, 0x68, [])
        space.linked_list(level, 0x5C, [])
        world = reader._world_reader.read(client, player, 10.)
        self.assertTrue(world.roster_complete)
        self.assertEqual(world.entities, ())

    def test_hostile_dead_minions_and_hidden_units_are_excluded_but_all_items_are_mapped(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        enemies = [space.unit("CMonster", "Enemy") for _ in range(4)]
        space.u32(enemies[0] + 0x28C, 2)
        space.u32(enemies[1] + 0x284, 6)
        space.f32(enemies[2] + 0x394, 0)
        space.u32(enemies[3] + 0x5B4, player)
        space.linked_list(level, 0x5C, [*enemies, npc, player, pet])
        loot = [space.unit(cls, "Item") for cls in ("CItem", "CEquipment", "CItemGold", "CBreakable")]
        space.u8(props[0] + 0x6E, 0)
        space.u8(props[1] + 0x161, 0)
        space.u8(props[2] + 0x19D, 1)
        space.linked_list(level, 0x68, [*loot, *props])
        world = reader._world_reader.read(client, player, 10.)
        self.assertEqual({e.address for e in world.entities}, {npc, *loot, *props[3:]})

    def test_unrecognized_player_invalid_coordinates_and_transition_drop_data(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        space.f32(player + 0x70, math.nan)
        self.assertIsNone(reader._world_reader.read(client, player, 10.).player_position)
        space.f32(player + 0x70, 0.)
        original = reader.read_u32
        reads = 0
        def switching(address):
            nonlocal reads
            if address == client + 0x38:
                reads += 1
                if reads > 1:
                    return level + 4
            return original(address)
        reader.read_u32 = switching
        self.assertEqual(reader._world_reader.read(client, player, 10.).entities, ())
        reader.read_u32 = original
        self.assertIsNone(reader._world_reader.read(client, npc, 10.).player_position)

    def test_short_reads_and_invalid_sizes_do_not_escape_either_backend(self):
        reader = TorchlightMemoryReader()
        reader._handle = 1
        for linux in (None, AddressSpace()):
            reader._linux = linux
            with patch("torchbridge.memory.kernel32") as kernel:
                kernel.ReadProcessMemory.return_value = False
                for address, size in ((1, 4), (0x10000, 0), (0x10000, 2**32),
                                      (0xFFFFFFFC, 8), (0x10000, 16)):
                    self.assertEqual(reader.read_bytes(address, size), b"")

    def test_update_publishes_world_and_discards_it_during_loading_and_menus(self):
        space, reader, client, level, player, pet, npc, props, _ = memory_fixture()
        root, global_ptr = space.allocate(0x100), space.allocate(4)
        ui, manager = space.allocate(0x1800), space.allocate(0xE00)
        space.u32(global_ptr, root)
        space.u32(root + 0x64, client)
        space.u32(client + 0x3C, ui)
        space.u32(ui + 0x324, manager)
        space.u32(manager + 0xD84, 6)
        space.u32(ui + 0x169C, 6)
        space.u32(client + 0x1BC, props[0])
        space.u32(client + 0x1C0, 1)
        reader._ensure_handle = lambda target_pid=None: True
        reader._resolve_cgame_address = lambda: global_ptr
        reader._exe_path, reader._module_base = "Torchlight.exe", 0x400000
        reader._last_disk_check = time.monotonic()
        state = reader.update()
        self.assertEqual(state.hover_entity, props[0])
        self.assertEqual(len(state.world.entities), 9)
        # Portals/stairs use the separate item hover pointer in the real game.
        space.u32(client + 0x1BC, 0)
        space.u32(client + 0x1C0, 0)
        space.u32(client + 0x1C4, props[0])
        state = reader.update()
        self.assertEqual(state.hover_entity, props[0])
        self.assertTrue(state.is_hover_interactive)
        space.u32(ui + 0x169C, 5)
        state = reader.update()
        self.assertTrue(state.is_loading)
        self.assertEqual(state.world.entities, ())
        space.u32(ui + 0x169C, 6)
        menu = space.allocate(0x100)
        space.u32(ui + 0x2EC, menu)
        space.u8(menu + 0x18, 1)
        self.assertIsNone(reader.update().world.player_position)
