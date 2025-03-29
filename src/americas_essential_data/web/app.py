from flask import Flask, g, render_template
from pathlib import Path
import sys
from werkzeug.local import LocalProxy

from .data_access.db import DatabaseInstance


def get_db_instance() -> DatabaseInstance:
    """Returns a DatabaseInstance for the database located in <repo>/data."""

    if hasattr(g, "db"):
        return g.db

    DB_RELATIVE_PATH = Path("../../../data/monitor.db")

    selfpath = Path(__file__).resolve().parent
    dbpath = selfpath / DB_RELATIVE_PATH

    if not dbpath.exists():
        raise FileNotFoundError(f"Database not found at {dbpath}")

    g.db = DatabaseInstance(dbpath)
    return g.db


db_instance = LocalProxy(get_db_instance)


def create_app():
    """Creates a Flask instance for our web app."""
    app = Flask(__name__)

    SITE_NAME = "America's Essential Data"

    @app.context_processor
    def context_vars():
        return dict(SITE_NAME=SITE_NAME)

    @app.template_filter("safe_title")
    def safe_title(title: str):
        if title:
            return f"{title.strip()} | {SITE_NAME}"

        return SITE_NAME

    from .blueprints.data_and_tools.blueprint import data_and_tools

    app.register_blueprint(data_and_tools)

    return app


if __name__ == "__main__":
    app = create_app()

    debug_mode = "--debug" in sys.argv
    app.run(debug=debug_mode)
