#!/bin/sh
# Apply our om-emu patch set to an om-emu clone at the base commit (om-emu is MIT; see README.md here).
# usage: sh apply.sh OM_EMU_CLONE
set -e
D=$(cd "$(dirname "$0")" && pwd)
cd "$1"
git checkout -q ccfe2e0 2>/dev/null || echo "apply.sh: base ccfe2e0 not checked out (shallow clone?); applying to the current tree"
# one at a time: 0003 builds on 0001 (a single git apply of all three checks each against the base and fails)
for p in 0001-kind2-img-planes 0002-vsc-write-log-hook 0003-live-view-backdrop; do git apply "$D/$p.patch"; done
echo "applied: kind-2 IMG planes, VSC write-log hook, live-view backdrop (OM_BACKDROP)"
