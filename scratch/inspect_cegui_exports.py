import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ctypes
from ctypes import wintypes
from src.torchbridge.memory import TorchlightMemoryReader, kernel32

reader = TorchlightMemoryReader()
reader._ensure_handle()

# Carrega CEGUIBase.dll no nosso processo para ver os nomes exportados e RVA!
cegui_dll_path = Path(reader._exe_path).parent / "CEGUIBase.dll"
print(f"Caminho CEGUIBase.dll: {cegui_dll_path}")

raw_dll = cegui_dll_path.read_bytes()
import re
matches = re.findall(rb"\?getSingleton[^\x00]+", raw_dll)
for m in matches[:20]:
    print("Export getSingleton:", m.decode("latin1", errors="ignore"))

