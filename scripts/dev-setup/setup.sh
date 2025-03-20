#!/usr/bin/env bash
set -euo pipefail  # Exit immediately if a command fails

# Get the dev-setup directory's base path
# (<repo root>/scripts/dev-setup)
DEVSETUP_BASEPATH="$(dirname "$(readlink -f "$0")")"

"$DEVSETUP_BASEPATH"/ensure_uv.sh
"$DEVSETUP_BASEPATH"/ensure_venv.sh
"$DEVSETUP_BASEPATH"/ensure_dependencies.sh