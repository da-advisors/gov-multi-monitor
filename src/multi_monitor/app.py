from flask import Flask, g, render_template
from pathlib import Path
import sys
from typing import Optional
from werkzeug.local import LocalProxy

from .db import MonitorDB

# Add this class near the top of the file, before create_app()
class DotDict:
    """Class that converts a dictionary to an object with dot notation access"""
    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                value = DotDict(value)
            setattr(self, key, value)


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
    @app.route("/api/resources/_data")
    def get_resources_data():
        results = db._read_query(
            """
            SELECT * FROM resources
            """
        )
        return results

    @app.route("/api/resources/<resource_id>/status_history")
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

    @app.route("/data-and-tools")
    def view_data_and_tools():
        statuses = [
            dict(
                dataset="Workplace Fatality Investigations Data",
                source="Occupational Safety and Health Administration",
                status_type="resources_offline",
                count=4,
                updated_at="February 13, 2025 9:14 AM EST",
            ),
            dict(
                dataset="Demographic and Health Survey STATCompiler",
                source="U.S. Agency for International Development",
                status_type="source_offline",
                updated_at="February 12, 2025 12:30 AM EST",
            ),
            dict(
                dataset="American Community Survey",
                source="U.S. Census Bureau",
                status_type="resources_not_updated",
                count=2,
                updated_at="February 12, 2025 10:20 PM EST",
            ),
        ]
        return render_template("data-and-tools.html.jinja", statuses=statuses)

    @app.route("/status/")
    def list_statuses():
        return render_template("index.html.jinja", tags=None, results=None)

    @app.route("/resources/")
    @app.route("/resources/<int:page>")
    def list_resources(page=1):
        # Default to page 1 if not specified
        page = max(1, page)  # Ensure page is at least 1
        per_page = 50  # Number of resources per page

        # Get all resources
        all_resources_raw = get_resources_data()

        # Convert to dot notation objects
        all_resources = [DotDict(resource) for resource in all_resources_raw]

        # Calculate pagination
        total_resources = len(all_resources)
        total_pages = (total_resources + per_page - 1) // per_page  # Ceiling division

        # Slice the resources for the current page
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_resources)
        current_resources = all_resources[start_idx:end_idx]

        return render_template(
            "multi_page/resource_list.html.jinja",
            resources=current_resources,
            current_page=page,
            total_pages=total_pages,
            total_resources=total_resources
        )

    @app.route("/resources/<resource_id>")
    def view_resource(resource_id: str):
        # TODO: Make as safer execution string.
        results = db._read_query(
            f"""
        SELECT * FROM resources
        WHERE id = '{resource_id}';
        """
        )

        status_history_raw = get_resource_status_history(resource_id)

        # Convert dictionaries to dot-accessible objects
        resource = DotDict(results[0])
        status_history = [DotDict(status) for status in status_history_raw]

        # Calculate status counts
        status_counts = {}
        if status_history:
            for status in status_history:
                status_type = status.status
                if status_type in status_counts:
                    status_counts[status_type] += 1
                else:
                    status_counts[status_type] = 1

        return render_template(
            "multi_page/resource_detail.html.jinja",
            resource=resource,
            status_history=status_history,
            status_counts=DotDict(status_counts)  # Make status_counts dot-accessible too
        )

    return app


if __name__ == "__main__":
    app = create_app()

    debug_mode = "--debug" in sys.argv
    app.run(debug=debug_mode)
