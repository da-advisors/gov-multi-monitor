from flask import Blueprint, render_template

from ...app import db_instance
from ...data_access.resource import ResourceRepository
from ...data_access.resource_status import ResourceStatusRepository

data_and_tools = Blueprint(
    "data-and-tools",
    __name__,
    static_folder="static",
    template_folder="templates",
    url_prefix="/data-and-tools",
)


@data_and_tools.route("/")
def index():
    statuses = ResourceStatusRepository(db_instance).find_latest_changes()
    return render_template(
        "data_and_tools/index/index.html.jinja", statuses=statuses, title="Data & Tools"
    )


@data_and_tools.route("/resources/")
def resources_index():
    resources = ResourceRepository(db_instance).all()
    return render_template(
        "data_and_tools/resources/index.html.jinja",
        resources=resources,
        title="Data Collections",
    )


@data_and_tools.route("/resources/<resource_id>")
def view_resource(resource_id: str):
    resource = ResourceRepository(db_instance).find_by_id(resource_id)
    status_history = ResourceStatusRepository(db_instance).find_by_resource_id(
        resource_id
    )

    return render_template(
        "data_and_tools/resources/view_resource.html.jinja",
        resource=resource[0],
        status_history=status_history,
        title=resource[0]["name"],
    )
