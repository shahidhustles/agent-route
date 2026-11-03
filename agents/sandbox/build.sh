#!/usr/bin/env bash
# Build the agent-route-opencode image from the host's opencode binary.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
ctx="$(mktemp -d "$here/.ctx.XXXXXX")"
trap 'rm -rf "$ctx"' EXIT
cp "$here/Dockerfile" "$here/preview.py" "$here/sheets_json.py" "$here/look.py" "$here/pptx_helpers.js" "$ctx/"
cp "$(readlink -f "$(command -v opencode)")" "$ctx/opencode"
docker build -t agent-route-opencode "$ctx"
