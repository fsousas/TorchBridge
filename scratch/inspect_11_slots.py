import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER, OFFSET_GAMEUI

reader = TorchlightMemoryReader()
reader.update()

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_ui = reader.read_u32(p_client + OFFSET_GAMEUI)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    p_skill_menu = reader.read_u32(p_ui + 0x030C)
    
    # In CSkillMenu, remember earlier we saw 11 pointers:
    # +0x04C: 0x17153758
    # +0x050: 0x16FB6090
    # +0x054: 0x16FB66D8
    # +0x058: 0x16FB5400
    # +0x05C: 0x17153110
    # +0x060: 0x16B13678
    # +0x064: 0x16C47018
    # +0x068: 0x16C47640
    # +0x06C: 0x16FB0EE8
    # +0x070: 0x16FB4DB8
    # +0x074: 0x16FB1530
    # Notice: exactly 11 pointers!
    # And how many skills does Alchemist Tab 1 ("Arcane") have in SKILL_TREE_LAYOUTS?
    # L1: col-1, col-2 (2)
    # L2: col-0, col-2 (2)
    # L3: col-0, col-1, col-2 (3)
    # L4: col-1 (1)
    # L5: col-0, col-2 (2)
    # L6: col-1 (1)
    # Total: 2 + 2 + 3 + 1 + 2 + 1 = 11 SKILLS!
    print("Exact number of skills in Alchemist Tab 1 is 11!")
    
    # Let's inspect these 11 pointers in CSkillMenu!
    for idx, off in enumerate(range(0x04C, 0x078, 4)):
        ptr = reader.read_u32(p_skill_menu + off)
        # Check what is inside ptr
        # Each pointer is a CEGUI Window for that skill slot!
        # In CEGUI Window, does it have a plus button child?
        # Let's check d_children of this window (+0x58)
        vec_ch = reader.read_u32(ptr + 0x58)
        num_ch = (reader.read_u32(ptr + 0x5C) - vec_ch) // 4 if vec_ch else 0
        
        # Check if plus button is visible:
        # In CEGUI::Window, d_visible is at +0x1A0 or +0x80 or +0xAC
        # Let's check children
        ch_names = []
        if vec_ch:
            for c_i in range(num_ch):
                c_ptr = reader.read_u32(vec_ch + c_i * 4)
                # Read child window name or visibility
                vis = reader.read_u8(c_ptr + 0x1A0)
                ch_names.append((c_i, hex(c_ptr), vis))
        print(f"Slot [{idx:2d}] at 0x{ptr:08X}: num_children={num_ch}, children={ch_names}")

reader.close()
