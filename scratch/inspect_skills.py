import sys
import io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.memory import TorchlightMemoryReader, ADDR_CGAME_GLOBAL, OFFSET_GAMECLIENT, OFFSET_PLAYER

reader = TorchlightMemoryReader()
reader.update()

def read_str(addr, max_len=64):
    if not addr or addr < 0x10000:
        return ""
    import ctypes
    buf = ctypes.create_string_buffer(max_len)
    read = ctypes.c_size_t()
    if ctypes.windll.kernel32.ReadProcessMemory(reader._handle, ctypes.c_void_p(addr), buf, max_len, ctypes.byref(read)):
        raw = buf.raw[:read.value].split(b"\x00")[0]
        try:
            return raw.decode("latin1")
        except Exception:
            pass
    return ""

def read_wstring(addr, max_len=64):
    return reader.read_wstring(addr, max_len)

if reader._handle:
    p_game = reader.read_u32(reader._cgame_address or ADDR_CGAME_GLOBAL)
    p_client = reader.read_u32(p_game + OFFSET_GAMECLIENT)
    p_player = reader.read_u32(p_client + OFFSET_PLAYER)
    p_skill_mgr = reader.read_u32(p_player + 0x184)
    
    vec_skills = reader.read_u32(p_skill_mgr + 0x3C)
    num_skills = reader.read_u32(p_skill_mgr + 0x40)
    print(f"CSkillManager: vector of {num_skills} skills at 0x{vec_skills:08X}")
    
    for i in range(min(num_skills, 40)):
        p_skill = reader.read_u32(vec_skills + i * 4)
        if p_skill:
            # Let's inspect fields in CSkill
            # Try reading name or id from p_skill
            # Check vtable
            vt = reader.read_u32(p_skill)
            
            # Let's check some candidate string offsets in CSkill:
            # e.g. +0x04, +0x08, +0x0C, +0x10, etc.
            name = ""
            for name_off in [0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34]:
                s = read_wstring(reader.read_u32(p_skill + name_off))
                if not s:
                    s = read_str(reader.read_u32(p_skill + name_off))
                if s and len(s) >= 3 and any(c.isalpha() for c in s):
                    name = f"[+0x{name_off:02X}]: {s}"
                    break
            
            # Read rank / level in CSkill:
            # Remember earlier in 0x005A58EF:
            # mov edx, dword ptr [esi + 0xa4]
            # inc edx
            # call 0x5de550 ; UpgradeSkill(esi, edx)
            # So +0xA4 in CSkill is the CURRENT RANK (0, 1, 2...)!
            rank = reader.read_u32(p_skill + 0xA4)
            print(f"Skill [{i:2d}] at 0x{p_skill:08X}: rank={rank}, name={name}")

reader.close()
