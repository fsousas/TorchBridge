import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct
from scratch.inspect_grid import safe_u32, read_bytes, reader

head_ptr = 0x10C4D028
print(f"Sentinela _Myhead = 0x{head_ptr:08X}")

# No MSVC STL, _Parent do _Myhead é o ROOT da árvore!
root_ptr = safe_u32(head_ptr + 0x04)
print(f"Raiz da árvore = 0x{root_ptr:08X}")

# Função para ler CEGUI::String no nó
def read_cegui_string(addr: int) -> str:
    # CEGUI::String normalmente tem:
    # buffer/pointer, size, capacity
    # Vamos ler os primeiros 32 bytes
    raw = read_bytes(addr, 32)
    if len(raw) < 16:
        return ""
    # Tenta ver se é string inline ou ponteiro
    p0 = struct.unpack("<I", raw[:4])[0]
    p4 = struct.unpack("<I", raw[4:8])[0]
    # Se p0 for ponteiro
    if 0x00400000 <= p0 <= 0x7FFFFFFF:
        cand = read_bytes(p0, 64)
        null_i = cand.find(b"\x00")
        if null_i > 0:
            try:
                s = cand[:null_i].decode("utf-8", errors="ignore")
                if s.isprintable() and len(s) >= 1:
                    return s
            except Exception:
                pass
    # Se for ASCII inline
    null_i = raw.find(b"\x00")
    if 0 < null_i <= 16:
        try:
            s = raw[:null_i].decode("utf-8", errors="ignore")
            if s.isprintable() and len(s) >= 1:
                return s
        except Exception:
            pass
    return ""

visited = set()
nodes = [root_ptr]
found_windows = []

while nodes and len(visited) < 4000:
    curr = nodes.pop()
    if not curr or curr in visited or curr == head_ptr:
        continue
    visited.add(curr)
    
    left = safe_u32(curr + 0x00)
    parent = safe_u32(curr + 0x04)
    right = safe_u32(curr + 0x08)
    is_nil = safe_u32(curr + 0x0C) & 0xFF
    
    if not is_nil:
        # Lê chave (nome) e valor (Window*)
        # Vamos inspecionar os bytes a partir de +0x10 (chave) e valor
        val_bytes = read_bytes(curr + 0x10, 48)
        # Em std::pair<CEGUI::String, CEGUI::Window*>:
        # onde fica o ponteiro da Window?
        # CEGUI::String tem tamanho ~24 ou 28 bytes ou 32 bytes
        # O último u32 do par é CEGUI::Window*
        w_name = ""
        # Procura strings e ponteiros
        for name_off in range(0x10, 0x30, 4):
            s = read_cegui_string(curr + name_off)
            if s and len(s) >= 2:
                w_name = s
                break
        
        # Procura ponteiro de Window (vtable 0x01BB0D1C)
        w_ptr = 0
        for w_off in range(0x20, 0x40, 4):
            cand_w = safe_u32(curr + w_off)
            if cand_w and safe_u32(cand_w) == 0x01BB0D1C:
                w_ptr = cand_w
                break
        
        if w_name or w_ptr:
            found_windows.append((curr, w_name, w_ptr))
            
    if left and left != head_ptr and left not in visited:
        nodes.append(left)
    if right and right != head_ptr and right not in visited:
        nodes.append(right)

print(f"Total de nós visitados: {len(visited)}")
print(f"Janelas decodificadas: {len(found_windows)}")

# Filtra janelas relevantes
keywords = ["grid", "flyout", "quick", "slot", "popup", "hud", "bar", "skill", "action"]
for curr, name, w in found_windows:
    lower_n = name.lower()
    if any(k in lower_n for k in keywords):
        print(f"Nó 0x{curr:08X} -> Nome: '{name}' | Window: 0x{w:08X}")

