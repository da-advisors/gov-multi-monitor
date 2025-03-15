from flask import Flask, render_template

from .db import MonitorDB

app = Flask(__name__)

db = MonitorDB("../data/monitor.db", read_only=True)


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


@app.route("/resources/_data")
def get_raw_resources():
    results = db._read_query(
        """
        SELECT * FROM resources
        """
    )
    return results


@app.route("/resources/")
def list_resources():
    results = get_raw_resources()
    return render_template("multi_page/resource_list.html.jinja", resources=results)


@app.route("/resources/<resource_id>")
def view_resource(resource_id: str):
    # TODO: Make as safer execution string.
    results = db._read_query(
        f"""
    SELECT * FROM resources
    WHERE id = '{resource_id}';
    """
    )

    status_history = view_resource_status_history(resource_id)

    return render_template(
        "multi_page/resource_detail.html.jinja",
        resource=results[0],
        status_history=status_history,
    )


@app.route("/resources/<resource_id>/status_history")
def view_resource_status_history(resource_id: str):
    results = db._read_query(
        f"""
    SELECT * FROM resource_status
    WHERE resource_id = '{resource_id}'
    ORDER BY checked_at DESC;
    """
    )

    return results


if __name__ == "__main__":
    app.run()
