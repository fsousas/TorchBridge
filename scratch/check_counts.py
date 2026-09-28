import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from torchbridge.models import SKILL_TREE_LAYOUTS, SKILL_TAB_NAMES

for char_class, tabs in SKILL_TREE_LAYOUTS.items():
    print(f"=== {char_class} ===")
    for tab_name, rows in tabs.items():
        total_skills = sum(1 for r in rows for c in r if c is not None)
        print(f"  Tab {tab_name}: {total_skills} skills")
