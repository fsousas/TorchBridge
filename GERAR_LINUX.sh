#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if command -v uv >/dev/null; then
  uv pip install --python .venv/bin/python -e . -r requirements-dev.txt
else
  .venv/bin/python -m pip install -e . -r requirements-dev.txt
fi
.venv/bin/python -m PyInstaller --noconfirm --clean TorchBridge.spec
printf 'Distribua a pasta dist/TorchBridge inteira. Veja docs/LINUX.md.\n'
