from flask import Blueprint, render_template

from ...app import db_instance
from ...data_access.resource import ResourceRepository
from ...data_access.resource_status import ResourceStatusRepository
from ...lib.dotdict import DotDict


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
@data_and_tools.route("/resources/<int:page>")
def resources_index(page=1):
    # Default to page 1 if not specified
    page = max(1, page)  # Ensure page is at least 1
    per_page = 50  # Number of resources per page

    # Get all resources
    all_resources_raw = ResourceRepository(db_instance).all()

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
        "data_and_tools/resources/index.html.jinja",
        resources=current_resources,
        current_page=page,
        total_pages=total_pages,
        total_resources=total_resources,
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
    )
