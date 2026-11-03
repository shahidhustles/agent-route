#!/usr/bin/env bash
# Fetch Anthropic's skills at a pinned commit into agents/opencode/skills-files (gitignored).
# The skills are under Anthropic's proprietary licence: they are never committed or edited, only mounted read-only.
set -euo pipefail
COMMIT=ca45fc496a3436251f191354091d557da31c15b5
here="$(cd "$(dirname "$0")" && pwd)"
dest="$here/../opencode/skills-files"
work="$here/../opencode/.skills-src"
rm -rf "$work" "$dest"
git init -q "$work"
git -C "$work" remote add origin https://github.com/anthropics/skills.git
git -C "$work" fetch -q --depth 1 origin "$COMMIT"
git -C "$work" checkout -q FETCH_HEAD
mkdir -p "$dest"
for s in pptx docx xlsx pdf frontend-design; do cp -r "$work/skills/$s" "$dest/$s"; done
rm -rf "$work"
# Our own MIT skill for the code agent rides along, so one read-only mount holds every skill a file-contract agent may load.
cp -r "$here/../opencode/skills/code-solutions" "$dest/code-solutions"
echo "$COMMIT" > "$dest/.commit"
echo "fetched $(ls "$dest" | tr '\n' ' ')at $COMMIT"
