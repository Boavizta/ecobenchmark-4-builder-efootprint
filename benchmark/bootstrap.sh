#!/bin/bash
# Explicit one-time setup on supported, dedicated Ubuntu 24.04/26.04 hosts.
set -euxo pipefail
. /etc/os-release
if [ "$ID" != ubuntu ] || { [ "$VERSION_ID" != 24.04 ] && [ "$VERSION_ID" != 26.04 ]; }; then
    echo 'Automatic setup supports Ubuntu 24.04/26.04 only. Install prerequisites manually elsewhere.' >&2
    exit 1
fi
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    apt-get update
    apt-get install -y docker.io docker-compose-v2
fi
missing=0
for tool in curl python3 lscpu ip pkill flock tar; do
    command -v "$tool" >/dev/null || missing=1
done
if [ "$missing" = 1 ]; then
    apt-get update
    apt-get install -y curl python3 util-linux iproute2 procps tar
fi
systemctl enable --now docker
