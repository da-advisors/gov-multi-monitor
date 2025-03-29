"""Entry point for the webapp package."""

import sys
from .app import create_app

if __name__ == "__main__":
    app = create_app()

    debug_mode = "--debug" in sys.argv
    app.run(debug=debug_mode)
