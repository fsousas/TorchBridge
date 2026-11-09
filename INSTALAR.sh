#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v wayland-scanner >/dev/null || ! pkg-config --exists wayland-client xkbcommon; then
  echo 'Instale as dependências: omarchy pkg add base-devel pkgconf python wayland libxkbcommon xorg-xwayland libx11 libxtst'
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python -e .
else
  .venv/bin/python -m pip install -e .
fi
.venv/bin/python scripts/install_linux_desktop.py
printf 'Instalado. Abra TorchBridge no launcher ou execute ./INICIAR_TORCHBRIDGE.sh\n'
