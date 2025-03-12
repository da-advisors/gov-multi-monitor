from flask import Flask, render_template, jsonify
from .db import MonitorDB

# Flask constructor takes the name of
# current module (__name__) as argument.
app = Flask(__name__)

db = MonitorDB("../data/monitor.db", read_only=True)


# The route() function of the Flask class is a decorator,
# which tells the application which URL should call
# the associated function.
@app.route("/")
# ‘/’ URL is bound with hello_world() function.
def landing_home():
    results = db._read_query(
        """
        SELECT count(*) as data_resources_count FROM resources
        """
    )

    data_resources_count = results[0]["data_resources_count"]

    return render_template(
        "multi_page/landing_page.html",
        data_collections_count=100,
        data_resources_count=data_resources_count,
        unavailable_collections_count=1,
        partially_unavailable_collections_count=2,
        stale_collections_count=3,
    )


@app.route("/resources/data")
def list_resources():
    results = db._read_query(
        """
        SELECT * FROM resources
        """
    )
    return results


@app.route("/resources/")
def render_resources_list_page():
    results = list_resources()
    return render_template("multi_page/resource_list.html", resources=results)


@app.route("/resources/<resource_id>")
def show_resource_details(resource_id: str):
    # TODO: Make as safer executition string.
    results = db._read_query(
        f"""
    SELECT * FROM resources
    WHERE id = '{resource_id}';
    """
    )

    status_history = get_status_history_for_resource(resource_id)

    return render_template(
        "multi_page/resource_detail.html",
        resource=results[0],
        status_history=status_history,
    )


@app.route("/resources/<resource_id>/status_history")
def get_status_history_for_resource(resource_id: str):
    results = db._read_query(
        f"""
    SELECT * FROM resource_status
    WHERE resource_id = '{resource_id}'
    ORDER BY checked_at DESC;
    """
    )

    return results


# main driver function
if __name__ == "__main__":

    # run() method of Flask class runs the application
    # on the local development server.
    app.run()
