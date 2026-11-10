"""Build the independent Torchlight x86 input module (MSVC or llvm-mingw)."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, help="i686-w64-mingw32-clang++ / g++")
    args = parser.parse_args()
    source = ROOT / "native/input"
    build = ROOT / "build/input"
    build.mkdir(parents=True, exist_ok=True)
    if args.compiler:
        compiler = str(args.compiler)
        c_compiler = compiler.replace("clang++", "clang").replace("g++", "gcc")
        objects = []
        for path in sorted((source / "vendor/minhook/src").rglob("*.c")):
            out = build / (path.stem + ".o")
            subprocess.run([c_compiler, "-O2", "-D_WIN32", "-I" + str(source / "vendor/minhook/include"),
                            "-c", str(path), "-o", str(out)], check=True)
            objects.append(str(out))
        binary = build / "winmm.dll"
        subprocess.run([compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-DNOMINMAX", "-DWIN32_LEAN_AND_MEAN", "-shared", "-static",
                        str(source / "proxy.cpp"), str(source / "runtime.cpp"), *objects,
                        str(source / "winmm.def"), "-luser32", "-lws2_32", "-lbcrypt",
                        "-o", str(binary)], check=True)
    else:
        cmake = shutil.which("cmake")
        if not cmake:
            raise SystemExit("Instale CMake e Visual Studio Build Tools (C++ x86).")
        subprocess.run([cmake, "-S", str(source), "-B", str(build), "-A", "Win32"], check=True)
        subprocess.run([cmake, "--build", str(build), "--config", "Release"], check=True)
        binary = build / "Release/winmm.dll"
    data = binary.read_bytes()
    pe = struct.unpack_from("<I", data, 60)[0]
    if data[:2] != b"MZ" or struct.unpack_from("<H", data, pe + 4)[0] != 0x14C:
        raise SystemExit("O módulo precisa ser Windows x86.")
    target = ROOT / "assets/native/x86/winmm.dll"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target)
    print(target)


if __name__ == "__main__":
    main()
