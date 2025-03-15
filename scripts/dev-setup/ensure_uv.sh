#!/usr/bin/env bash
set -euo pipefail  # Exit immediately if any command fails

# Checks to see if the 'uv' command exists.
# Returns 0 if true, 1 if false (per standard Bash convention).
check_uv() {
    command -v uv &> /dev/null
}

# Installs uv, using Astral's official script.
install_uv() {
    echo "Downloading the uv installer ..."
    local UV_INSTALLER
    UV_INSTALLER=$(curl -LsSf https://astral.sh/uv/install.sh)

    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to download the uv installer." >&2
        return 1
    fi
    echo "Installer downloaded."
    
    echo "$UV_INSTALLER" | sh
    return $?
}

if ! check_uv; then
    echo "'uv' is not installed. Attempting to install it now ..."

    if ! install_uv; then
        echo "Error: 'uv' installation failed." >&2
        exit 1
    fi
else
    echo "'uv' is already installed."
fi