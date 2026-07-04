#!/usr/bin/env bash

set -euo pipefail

GEM5_DIR="${1:?usage: link_addon_configs.sh <gem5_dir>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ADDON="$REPO_ROOT/omelet/backends/gem5/configs"
GCFG="$GEM5_DIR/configs"

[[ -d "$ADDON" ]] || { echo "addon configs not found: $ADDON" >&2; exit 1; }
[[ -d "$GCFG"  ]] || { echo "gem5 configs/ not found: $GCFG (is '$GEM5_DIR' a gem5 source tree?)" >&2; exit 1; }

linked=0
while IFS= read -r -d '' f; do
    rel="${f#"$ADDON"/}"
    dst="$GCFG/$rel"
    mkdir -p "$(dirname "$dst")"
    ln -sfn "$f" "$dst"
    linked=$((linked + 1))
done < <(find "$ADDON" -type f -not -name '*.pyc' -print0)

# Drop stale bytecode in the overlaid dirs so Python recompiles from the omelet
# sources rather than reusing a vanilla-derived .pyc.
for d in topologies network ruby example; do
    rm -rf "$GCFG/$d/__pycache__"
done

echo "[link_addon_configs] linked $linked omelet config file(s) into $GCFG"
