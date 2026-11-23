#!/bin/sh
# Apply our om-emu patch set to an om-emu clone at the base commit (om-emu is MIT; see README.md here).
# usage: sh apply.sh OM_EMU_CLONE
set -e
D=$(cd "$(dirname "$0")" && pwd)
cd "$1"
git checkout -q ccfe2e0 2>/dev/null || echo "apply.sh: base ccfe2e0 not checked out (shallow clone?); applying to the current tree"
# one at a time: 0003 builds on 0001 (a single git apply of all three checks each against the base and fails)
for p in 0001-kind2-img-planes 0002-vsc-write-log-hook 0003-live-view-backdrop 0004-bitmap-no-table 0005-olyfw-checks-dcache-secmon 0006-heap-fill 0007-olyfw-kernel-checks 0008-olyfw-cpu2-e137 0009-olyfw-cpu1-e137; do git apply "$D/$p.patch"; done
echo "applied: kind-2 IMG planes, VSC write-log hook, live-view backdrop (OM_BACKDROP), run-length bitmaps without a table, cache model + section monitor (OM_DCACHE, OM_SECMON), heap fill (OM_HEAP_FILL), kernel checks (OM_KCHECK), CPU 2 natively on the E-M5 III (OM_CPU2), CPU 1 natively on the E-M5 III (OM_CPU1)"
