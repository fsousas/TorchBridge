# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

native_overlay = Path(SPECPATH) / "assets" / "native" / "x86" / "d3d9.dll"
native_datas = [(str(native_overlay), "assets/native/x86")] if native_overlay.is_file() else []

analysis = Analysis(
    ["launcher.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("assets/images/radial-menu-icons", "assets/images/radial-menu-icons"),
        ("assets/hud", "assets/hud"),
    ] + native_datas,
    hiddenimports=["pygame._sdl2.controller"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="TorchBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TorchBridge",
)

