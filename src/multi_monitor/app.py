from flask import Flask, g, render_template
from pathlib import Path
from typing import Optional
from werkzeug.local import LocalProxy

from .db import MonitorDB


def get_db() -> Optional[MonitorDB]:
    """Returns a MonitorDB instance for the database located in <repo>/data."""

    if hasattr(g, "db"):
        return g.db

    DB_RELATIVE_PATH = Path("../../data/monitor.db")

    selfpath = Path(__file__).resolve().parent
    dbpath = selfpath / DB_RELATIVE_PATH

    if not dbpath.exists():
        raise FileNotFoundError(f"Database not found at {dbpath}")

    g.db = MonitorDB(dbpath, read_only=True)
    return g.db


def create_app():
    """Creates a Flask instance for our web app."""
    app = Flask(__name__)
    db = LocalProxy(get_db)

    # START API ROUTES
    @app.route("/resources/_data")
    def get_resources_data():
        results = db._read_query(
            """
            SELECT * FROM resources
            """
        )
        return results

    @app.route("/resources/<resource_id>/status_history")
    def get_resource_status_history(resource_id: str):
        results = db._read_query(
            f"""
        SELECT * FROM resource_status
        WHERE resource_id = '{resource_id}'
        ORDER BY checked_at DESC;
        """
        )

        return results

    # END API ROUTES

    @app.route("/")
    def view_landing():
        results = db._read_query(
            """
            SELECT count(*) as data_resources_count FROM resources
            """
        )

        data_resources_count = results[0]["data_resources_count"]

        return render_template(
            "multi_page/landing_page.html.jinja",
            data_collections_count=100,
            data_resources_count=data_resources_count,
            unavailable_collections_count=1,
            partially_unavailable_collections_count=2,
            stale_collections_count=3,
        )

    @app.route("/status/")
    def list_statuses():
        return render_template("index.html.jinja", tags=None, results=None)

    @app.route("/resources/")
    def list_resources():
        results = get_resources_data()
        return render_template("multi_page/resource_list.html.jinja", resources=results)

    @app.route("/resources/<resource_id>")
    def view_resource(resource_id: str):
        # TODO: Make as safer executition string.
        results = db._read_query(
            f"""
        SELECT * FROM resources
        WHERE id = '{resource_id}';
        """
        )

        status_history = get_resource_status_history(resource_id)

        return render_template(
            "multi_page/resource_detail.html.jinja",
            resource=results[0],
            status_history=status_history,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
