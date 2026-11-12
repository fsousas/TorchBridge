#!/usr/bin/env bash
# Dependencies for the ubuntu-24.04 Actions matrix, using direct official HTTPS
# sources instead of the runner image's Azure mirror redirector. Keep Ubuntu's
# signature verification and the runner's repository configuration intact.
set -euo pipefail

apt_workdir=$(mktemp -d)
trap 'rm -rf -- "$apt_workdir"' EXIT
mkdir "$apt_workdir/empty"

# Probe through the runner's network/proxy before starting APT's longer retries.
# The alternate mirror serves the same Ubuntu-signed releases, including security.
apt_mirror=""
for candidate in https://archive.ubuntu.com/ubuntu https://mirrors.edge.kernel.org/ubuntu; do
    if curl --ipv4 --fail --silent --show-error --location \
        --connect-timeout 15 --max-time 30 \
        --retry 2 --retry-all-errors --retry-delay 2 --retry-max-time 90 \
        "$candidate/dists/noble/InRelease" \
        --output "$apt_workdir/InRelease"; then
        apt_mirror="$candidate"
        break
    fi
done
if [[ -z "$apt_mirror" ]]; then
    echo "No reachable Ubuntu package mirror; dependency installation cannot continue." >&2
    exit 1
fi
echo "Ubuntu package source: $apt_mirror"
cat > "$apt_workdir/ubuntu.sources" <<SOURCES
Types: deb
URIs: $apt_mirror
Suites: noble noble-updates noble-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES

apt_options=(
    -o "Dir::Etc::sourcelist=$apt_workdir/ubuntu.sources"
    -o "Dir::Etc::sourceparts=$apt_workdir/empty"
    -o APT::Update::Error-Mode=any
    -o Acquire::Retries=3
    -o Acquire::https::Timeout=20
    -o Acquire::ForceIPv4=true
)
# sudo normally drops proxy environment variables. APT also does not recognize
# curl's uppercase HTTPS_PROXY/ALL_PROXY automatically; pass only the proxy it
# needs, without logging its value or preserving the whole runner environment.
apt_https_proxy=${https_proxy:-${HTTPS_PROXY:-${all_proxy:-${ALL_PROXY:-}}}}
if [[ -n "$apt_https_proxy" ]]; then
    apt_options+=(-o "Acquire::https::Proxy=$apt_https_proxy")
fi
sudo apt-get "${apt_options[@]}" update
sudo apt-get "${apt_options[@]}" install -y --no-install-recommends \
    libegl1 libgl1 libxkbcommon-x11-0 libwayland-dev libwayland-bin \
    libxkbcommon-dev pkg-config gcc fonts-dejavu-core
