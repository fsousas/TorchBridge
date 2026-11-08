# Linux Wayland transport

`wayland.c` is compiled as `torchbridge._wayland` by setuptools on Linux only.
It is a ctypes library, **not** a Python extension to import directly. `wayland.py`
loads its installed path without executing it as a Python module.

Build requirements: C11 compiler, pkg-config, wayland-scanner, wayland-client and
xkbcommon headers/libraries. No code generation downloads occur at build time.
The vendored protocol XMLs retain their upstream copyright/license notices.
`THIRD_PARTY_NOTICES.txt` reproduces those notices in Linux wheels and portable
bundles, which do not otherwise include the source XMLs.

- `wlr-layer-shell-unstable-v1.xml`, `wlr-virtual-pointer-unstable-v1.xml`:
  https://github.com/swaywm/wlr-protocols/tree/master/unstable
- `virtual-keyboard-unstable-v1.xml`:
  https://github.com/swaywm/wlroots/tree/master/protocol
- `xdg-shell.xml` (interface referenced by layer-shell's popup request):
  https://gitlab.freedesktop.org/wayland/wayland-protocols/-/tree/main/stable/xdg-shell

`tb_open(0)` owns the overlay connection on the Qt thread. `tb_open(1)` owns the
virtual devices on the input thread. Handles, callbacks, outputs and buffers
never cross their owner's thread. Connections disconnect and destroy their
proxies during cleanup. No global event loop, native Python callback or GPU
state is shared with the game.

`wl_buffer.release` protects the three reusable SHM buffers. Input regions are
empty except for the virtual keyboard. Layer keyboard interactivity is always
none. Geometry is logical, raster pixels are an integer multiple of geometry.
The Python side queries Hyprland output scales and revalidates game focus.

The normal test suite uses offscreen rendering and fakes. The explicit live
transport test is `python scripts/smoke_linux.py`; see `docs/LINUX.md` before use.
