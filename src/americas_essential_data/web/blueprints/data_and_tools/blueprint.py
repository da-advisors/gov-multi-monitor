from flask import Blueprint, render_template

from ...app import db_instance
from ...data_access.resource import ResourceRepository
from ...data_access.resource_status import ResourceStatusRepository
from ...data_access.collection import CollectionRepository
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

    # Get all resources from the view that includes joined preview information
    all_resources_raw = ResourceRepository(db_instance).all_previews()

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


@data_and_tools.route("/collections/")
@data_and_tools.route("/collections/<int:page>")
def collections_index(page=1):
    # Default to page 1 if not specified
    page = max(1, page)  # Ensure page is at least 1
    per_page = 50  # Number of results per page

    # Get all collections from the view that includes joined preview information
    all_collections_raw = CollectionRepository(db_instance).all_previews()

    # Convert to dot notation objects
    all_collections = [DotDict(collection) for collection in all_collections_raw]

    # Calculate pagination
    total_collections = len(all_collections)
    total_pages = (total_collections + per_page - 1) // per_page  # Ceiling division

    # Slice the results for the current page
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_collections)
    current_collections = all_collections[start_idx:end_idx]

    return render_template(
        "data_and_tools/collections/index.html.jinja",
        collections=current_collections,
        current_page=page,
        total_pages=total_pages,
        total_collections=total_collections,
    )


@data_and_tools.route("/collections/<collection_id>")
def view_collection(collection_id: str):
    collection = CollectionRepository(db_instance).find_by_id(collection_id)
    resource_list = CollectionRepository(db_instance).find_resources_by_collection_id(
        collection_id
    )

    return render_template(
        "data_and_tools/resources/view_resource.html.jinja",
        collection=collection[0],
        resource_list=resource_list,
    )
