#!/usr/bin/env bash
set -euo pipefail  # Exit immediately if any command fails

# Get the repository's base path (two levels up from "scripts/dev-setup")
SELF_BASEPATH="$(dirname "$(readlink -f "$0")")"
REPO_BASEPATH="$(dirname "$(dirname "$SELF_BASEPATH")")"

VENV_DIR="$REPO_BASEPATH/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Error: Virtual environment not found at '$VENV_DIR'." >&2
    exit 1
fi

PYPROJECT_FILE="$REPO_BASEPATH/pyproject.toml"
if [[ ! -f "$PYPROJECT_FILE" ]]; then
    echo "Error: pyproject.toml not found. This file is required." >&2
    exit 1
fi

echo "Activating virtual environment at '$VENV_DIR' ..."
source "$VENV_DIR/bin/activate"

echo "Installing production and development dependencies in editable mode from pyproject.toml ..."

uv pip install -e "$REPO_BASEPATH" -r "$PYPROJECT_FILE" --extra dev

echo "Dependencies installed successfully."
