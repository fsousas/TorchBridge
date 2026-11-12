"""Inspect the loaded world's positions without injecting any input.

Usage: python -m torchbridge.world_inspect [--pid PID] [--json] [--watch]
On Omarchy, launch the game via TorchBridge's --launch for memory permissions.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
import time

from .memory import GameMemoryState, TorchlightMemoryReader


def world_report(state: GameMemoryState) -> dict:
    world = state.world
    player = world.player_position
    return {
        "connected": state.is_connected, "pid": state.pid, "version": state.game_version,
        "state": state.state_desc, "status": world.status,
        "level": world.level_name, "level_address": world.level_address,
        "player_position": asdict(player) if player else None,
        "sampled_at": world.sampled_at, "roster_complete": world.roster_complete,
        "camera_available": world.camera is not None,
        "entities": [dict(asdict(entity), label=entity.label,
                          distance=player.distance_to(entity.position) if player else None)
                     for entity in world.entities],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="PID do Torchlight.exe selecionado")
    parser.add_argument("--json", action="store_true", help="JSON; com --watch, um objeto por linha")
    parser.add_argument("--watch", action="store_true", help="Atualiza a cada 100 ms; Ctrl+C encerra")
    args = parser.parse_args(argv)
    if args.pid is not None and args.pid <= 0:
        parser.error("--pid precisa ser positivo")
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    reader = TorchlightMemoryReader()
    try:
        while True:
            state = reader.update(target_pid=args.pid)
            report = world_report(state)
            if args.json:
                print(json.dumps(report, ensure_ascii=False), flush=True)
            else:
                print(f"{state.state_desc} | {report['level']} | {report['status']}")
                if report["player_position"]:
                    p = state.world.player_position
                    print(f"Jogador: X={p.x:.3f} Y={p.y:.3f} altura={p.height:.3f}")
                for entity in report["entities"]:
                    p = entity["position"]
                    print(f"  {entity['label']}: {entity['name'] or entity['identifier']} "
                          f"X={p['x']:.3f} Y={p['y']:.3f} altura={p['height']:.3f} "
                          f"distância={entity['distance']:.2f}")
                if reader.last_error:
                    print(reader.last_error, file=sys.stderr)
            if not args.watch:
                return 0 if state.world.roster_complete else 1
            time.sleep(0.1)
    except KeyboardInterrupt:
        return 0
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
