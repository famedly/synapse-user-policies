#!/bin/sh
# Builds the Complement image on a pinned base and runs the Go tests against it.
set -eu
cd "$(dirname "$0")/.."
BASE=ghcr.io/element-hq/synapse/complement-synapse@sha256:d0945d471ebd21abd25bed2f082fb5f2db52596dd330d2aecef99601716c327d
IMAGE=localhost/complement-synapse-user-policies
docker build --platform linux/amd64 --build-arg BASE="$BASE" -f complement/Dockerfile -t "$IMAGE" .
cd complement
COMPLEMENT_SPAWN_HS_TIMEOUT_SECS="${COMPLEMENT_SPAWN_HS_TIMEOUT_SECS:-300}" COMPLEMENT_BASE_IMAGE="$IMAGE" go test ./... -count=1 "$@"
