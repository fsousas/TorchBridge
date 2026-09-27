"""Compila a DLL Windows x86 com MSVC/CMake ou um compilador MinGW explícito."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from torchbridge.fullscreen import validate_x86


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", help="Caminho do i686-w64-mingw32-g++ ou clang++ (cross build)")
    args = parser.parse_args()
    source = ROOT / "native" / "fullscreen"
    build = ROOT / "build" / "fullscreen"
    build.mkdir(parents=True, exist_ok=True)
    if args.compiler:
        binary = build / "d3d9.dll"
        subprocess.run([
            args.compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-DWIN32_LEAN_AND_MEAN", "-DNOMINMAX", "-shared", "-static",
            str(source / "proxy.cpp"), str(source / "renderer.cpp"), str(source / "d3d9.def"),
            "-luser32", "-o", str(binary),
        ], check=True)
    else:
        cmake = shutil.which("cmake")
        if not cmake:
            raise SystemExit("Instale CMake e Visual Studio Build Tools com C++ (x86).")
        subprocess.run([cmake, "-S", str(source), "-B", str(build), "-A", "Win32"], check=True)
        subprocess.run([cmake, "--build", str(build), "--config", "Release"], check=True)
        binary = build / "Release" / "d3d9.dll"
    data = binary.read_bytes()
    validate_x86(data, dll=True)
    destination = ROOT / "assets" / "native" / "x86" / "d3d9.dll"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, destination)
    print(f"DLL x86: {destination}\nSHA256: {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
