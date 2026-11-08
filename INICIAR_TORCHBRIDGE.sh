#!/usr/bin/env bash
set -euo pipefail
TORCHBRIDGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -x "$TORCHBRIDGE_DIR/.venv/bin/python" ]; then
  echo 'Execute ./INSTALAR.sh primeiro.' >&2
  exit 1
fi
exec "$TORCHBRIDGE_DIR/.venv/bin/python" -m torchbridge "$@"
