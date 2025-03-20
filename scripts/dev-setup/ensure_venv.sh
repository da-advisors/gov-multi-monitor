#!/usr/bin/env bash
set -euo pipefail  # Exit immediately if any command fails

# Get the repository's base path (two levels up from "scripts/dev-setup")
SELF_BASEPATH="$(dirname "$(readlink -f "$0")")"
REPO_BASEPATH="$(dirname "$(dirname "$SELF_BASEPATH")")"

# Put the venv in a hidden directory
VENV_DIR=".venv"

# Combine the base directory path with the venv directory name
VENV_PATH="$REPO_BASEPATH/$VENV_DIR"

# Create the venv if it doesn't exist
if [[ ! -d "$VENV_PATH" ]]; then
    echo "Virtual environment not found at '$VENV_PATH'. Creating it now ..."
    if ! uv venv "$VENV_PATH"; then
        echo "Error: Failed to create virtual environment at '$VENV_PATH'." >&2
        exit 1
    else
        echo "Virtual environment created at '$VENV_PATH'."
    fi
else
    echo "Virtual environment found at '$VENV_PATH'."
fi
