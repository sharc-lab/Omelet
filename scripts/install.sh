#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

: "${OMELET_GEM5_DIR:=$REPO_ROOT/gem5}"
: "${OMELET_FULL_BUILD:=1}"
: "${OMELET_BUILD_JOBS:=32}"
: "${OMELET_NUMBER_BITS_PER_SET:=256}"

GEM5_TAG="v22.1.0.0"
GEM5_URL="https://gem5.googlesource.com/public/gem5"
PATCHES_DIR="$REPO_ROOT/gem5_patch"

echo "=== install.sh started at $(date -Iseconds) ==="
echo "REPO_ROOT=$REPO_ROOT"
echo "OMELET_GEM5_DIR=$OMELET_GEM5_DIR"
echo "OMELET_FULL_BUILD=$OMELET_FULL_BUILD"
echo "OMELET_BUILD_JOBS=$OMELET_BUILD_JOBS"
echo "OMELET_NUMBER_BITS_PER_SET=$OMELET_NUMBER_BITS_PER_SET"

# ---- 0/5 prerequisite check ----
echo "[0/5] prerequisite check"
for tool in gcc g++ git python3 scons; do
    if command -v "$tool" >/dev/null 2>&1; then
        echo "  $tool: $(command -v "$tool")"
    else
        echo "ERROR: $tool not found on PATH"
        exit 1
    fi
done

# ---- 1/5 ensure the gem5 submodule is present at the pinned tag ----
echo "[1/5] gem5 $GEM5_TAG at $OMELET_GEM5_DIR"
if [[ ! -e "$OMELET_GEM5_DIR/SConstruct" ]]; then
    if [[ "$OMELET_GEM5_DIR" == "$REPO_ROOT/gem5" && -f "$REPO_ROOT/.gitmodules" ]]; then
        echo "  submodule not initialized — running 'git submodule update --init gem5' ..."
        git -C "$REPO_ROOT" submodule update --init gem5
    elif [[ ! -d "$OMELET_GEM5_DIR/.git" ]]; then
        echo "  no gem5 tree found — cloning $GEM5_URL @ $GEM5_TAG ..."
        git clone --branch "$GEM5_TAG" "$GEM5_URL" "$OMELET_GEM5_DIR"
    fi
fi
[[ -e "$OMELET_GEM5_DIR/SConstruct" ]] || {
    echo "ERROR: $OMELET_GEM5_DIR is not a gem5 source tree (no SConstruct)."
    echo "       Clone with --recurse-submodules, or run 'git submodule update --init gem5'."
    exit 1
}
echo "  gem5 HEAD: $(git -C "$OMELET_GEM5_DIR" describe --tags --always 2>/dev/null || echo '?')"

# ---- 2/5 apply patches (idempotent) ----
# Numeric order:
#   001-004 garnet latency-breakdown instrumentation
#   005     BasicLink serdes/off-chip base params (required by 003)
#   006     SConstruct conda/gcc build-env fix
#   007     addr_range non-power-of-2 directory interleaving (12-chiplet 3D only)
echo "[2/5] applying omelet garnet patches from $PATCHES_DIR"
for pf in "$PATCHES_DIR"/00*.patch; do
    pname="$(basename "$pf")"
    if git -C "$OMELET_GEM5_DIR" apply --check --reverse "$pf" >/dev/null 2>&1; then
        echo "  SKIP $pname (already applied)"
    elif git -C "$OMELET_GEM5_DIR" apply --check "$pf" >/dev/null 2>&1; then
        echo "  APPLY $pname"
        git -C "$OMELET_GEM5_DIR" apply "$pf"
    else
        echo "ERROR: patch $pname does not apply cleanly against $GEM5_TAG"
        echo "       Ensure $OMELET_GEM5_DIR is a clean $GEM5_TAG checkout"
        echo "       (cd $OMELET_GEM5_DIR && git checkout -f $GEM5_TAG && git clean -fdx)."
        exit 1
    fi
done
echo "  all patches applied"

# ---- 3/5 link omelet's gem5-side configs into the gem5 tree ----
echo "[3/5] linking omelet configs into $OMELET_GEM5_DIR/configs"
"$SCRIPT_DIR/link_addon_configs.sh" "$OMELET_GEM5_DIR"

# ---- 4/5 install the omelet python package ----
echo "[4/5] pip install -e . (omelet package)"
if python3 -m pip install -e "$REPO_ROOT" ; then
    echo "  omelet installed (editable)"
else
    echo "  WARNING: 'pip install -e .' failed; the gem5 run path still works via"
    echo "           experiments/*/run.sh, but the omelet-run CLI will be unavailable."
fi

# ---- 5/5 build gem5.opt ----
if [[ "$OMELET_FULL_BUILD" == "1" ]]; then
    echo "[5/5] scons build (jobs=$OMELET_BUILD_JOBS, NUMBER_BITS_PER_SET=$OMELET_NUMBER_BITS_PER_SET) — ~6-10 min ..."
    ( cd "$OMELET_GEM5_DIR" && scons build/Garnet_standalone/gem5.opt \
        NUMBER_BITS_PER_SET="$OMELET_NUMBER_BITS_PER_SET" \
        -j"$OMELET_BUILD_JOBS" )
    echo "  build complete: $OMELET_GEM5_DIR/build/Garnet_standalone/gem5.opt"
else
    echo "[5/5] skipping scons build (OMELET_FULL_BUILD=0)"
    echo "  To build later:"
    echo "    cd $OMELET_GEM5_DIR && scons build/Garnet_standalone/gem5.opt \\"
    echo "        NUMBER_BITS_PER_SET=$OMELET_NUMBER_BITS_PER_SET -j\$(nproc)"
fi

echo ""
echo "=== install.sh complete ==="
echo "Patches applied: $(ls "$PATCHES_DIR"/00*.patch | wc -l) on $GEM5_TAG"
if [[ "$OMELET_FULL_BUILD" == "1" ]]; then
    echo "gem5.opt: $OMELET_GEM5_DIR/build/Garnet_standalone/gem5.opt"
    echo "Next: run a simulation, e.g. omelet-run --topology mesh --material org --injectionrate 0.1"
else
    echo "Next: build gem5.opt (see [5/5] above), then run omelet-run"
fi
