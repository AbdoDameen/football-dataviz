#!/usr/bin/env bash
# Regenerate every figure in the project, then run the engine self-test.
#
#   ./run_all.sh              # all figures
#   ./run_all.sh shooting     # only fig_shooting
#
# Requires: .venv/bin/python with numpy, pandas, matplotlib, scipy.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
    cat >&2 <<'EOF'
No .venv found. Set up the environment first:

    python3 -m venv .venv
    .venv/bin/pip install numpy pandas matplotlib scipy
    .venv/bin/python football-data-visualisation/scripts/fetch_statsbomb.py --core
EOF
    exit 1
fi

# Keep matplotlib's cache inside the project: the user's home may not be writable,
# and a shared cache avoids rebuilding fonts on every run.
export MPLCONFIGDIR="$ROOT/.mplcache"
mkdir -p "$ROOT/.mplcache" "$ROOT/figures"

FILTER="${1:-}"
shopt -s nullglob
ok=0
fail=0

for script in fig_*/plot_*.py; do
    if [ -n "$FILTER" ] && [[ "$script" != *"$FILTER"* ]]; then
        continue
    fi
    echo "=== $script"
    if "$PY" "$script" 2>&1 | grep -v '^findfont:' | sed 's/^/    /'; then
        ok=$((ok + 1))
    else
        echo "    FAILED" >&2
        fail=$((fail + 1))
    fi
done

echo
echo "=== self-test"
if "$PY" football-data-visualisation/scripts/selftest.py 2>&1 | tail -20; then
    echo "    self-test ok"
else
    fail=$((fail + 1))
fi

echo
echo "scripts run: $ok   failures: $fail"
echo "figures:     $(ls -1 figures/*.png 2>/dev/null | wc -l | tr -d ' ') PNG, $(ls -1 figures/*.pdf 2>/dev/null | wc -l | tr -d ' ') PDF"
exit "$fail"
