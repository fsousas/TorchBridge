#!/usr/bin/env bash
# Dependencies for the ubuntu-24.04 Actions matrix, using direct official HTTPS
# sources instead of the runner image's Azure mirror redirector. Leave the
# runner's repository configuration intact and fail if any index cannot refresh.
set -euo pipefail

apt_workdir=$(mktemp -d)
trap 'rm -rf -- "$apt_workdir"' EXIT
mkdir "$apt_workdir/empty"
cat > "$apt_workdir/ubuntu.sources" <<'SOURCES'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu
Suites: noble noble-updates
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://security.ubuntu.com/ubuntu
Suites: noble-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES

apt_options=(
    -o "Dir::Etc::sourcelist=$apt_workdir/ubuntu.sources"
    -o "Dir::Etc::sourceparts=$apt_workdir/empty"
    -o APT::Update::Error-Mode=any
    -o Acquire::Retries=3
    -o Acquire::https::Timeout=20
)
sudo apt-get "${apt_options[@]}" update
sudo apt-get "${apt_options[@]}" install -y --no-install-recommends \
    libegl1 libgl1 libxkbcommon-x11-0 libwayland-dev libwayland-bin \
    libxkbcommon-dev pkg-config gcc
