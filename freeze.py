#!/usr/bin/env python3
"""Script to freeze specific routes from the Flask application into static HTML files."""
from flask_frozen import Freezer
from americas_essential_data.web.app import create_app, db_instance
import logging
import os
import shutil
from flask import render_template

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create the Flask app
app = create_app()

# Configure Frozen-Flask
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_REMOVE_EXTRA_FILES'] = False  # Don't remove files we don't know about
app.config['FREEZER_IGNORE_MIMETYPE_WARNINGS'] = True
app.config['FREEZER_DEFAULT_MIMETYPE'] = 'text/html'

# Configure Flask for URL building without request context
app.config['SERVER_NAME'] = 'localhost'  # Required for url_for to work
app.config['APPLICATION_ROOT'] = '/'
app.config['PREFERRED_URL_SCHEME'] = 'http'

# Initialize the freezer with only specific URLs
freezer = Freezer(app, with_no_argument_rules=False, log_url_for=False)

# Register URL generators for the new blueprint-based routes

# Root index - redirects to /data-and-tools
@freezer.register_generator
def index():
    yield {}  # For the root URL '/'

# Data and tools index
@freezer.register_generator
def data_and_tools_index():
    yield {}  # For /data-and-tools/

# Resources index (first page)
@freezer.register_generator
def data_and_tools_resources_index():
    yield {}  # For /data-and-tools/resources/

# Resources pagination
@freezer.register_generator
def data_and_tools_resources_pages():
    with app.app_context():
        try:
            from americas_essential_data.web.data_access.resource import ResourceRepository

            # Get all resources to calculate pagination
            all_resources = ResourceRepository(db_instance).all()
            per_page = 50
            total_resources = len(all_resources)
            total_pages = (total_resources + per_page - 1) // per_page

            # Generate URLs for all pages except the first (which is handled by the index)
            logging.info(f"Generating {total_pages} pages for resource pagination")
            for page in range(2, total_pages + 1):
                yield {'page': page}
        except Exception as e:
            logging.error(f"Error generating resource pagination pages: {e}")

# Resource detail pages
@freezer.register_generator
def data_and_tools_view_resource():
    with app.app_context():
        try:
            from americas_essential_data.web.data_access.resource import ResourceRepository

            # Get all resources
            resources = ResourceRepository(db_instance).all()

            # Print what we're generating for debugging
            logging.info(f"Found {len(resources)} resources to generate detail pages for")

            # Generate a URL for each resource
            for resource in resources:
                resource_id = resource['id']
                logging.info(f"Generating page for resource: {resource_id}")
                yield {'resource_id': resource_id}
        except Exception as e:
            logging.error(f"Error generating resource detail pages: {e}")

def manually_build_all_pages():
    """Manually build all pages as a fallback."""
    with app.app_context():
        pages_built = 0

        try:
            # Build basic pages
            pages = [
                ("/", "index.html"),
                ("/data-and-tools/", "data-and-tools/index.html"),
                ("/data-and-tools/resources/", "data-and-tools/resources/index.html")
            ]

            for url, output_file in pages:
                try:
                    with app.test_request_context(url):
                        # Get the response for this URL
                        response = app.test_client().get(url)
                        html = response.data.decode('utf-8')

                        # Ensure directory exists
                        output_path = os.path.join('build', output_file)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)

                        # Write the file
                        with open(output_path, 'w') as f:
                            f.write(html)

                        logging.info(f"Manually built page: {output_file}")
                        pages_built += 1
                except Exception as e:
                    logging.error(f"Error building page {url}: {e}")

            # Now build resource pages
            resource_count = manually_build_resource_pages()
            pages_built += resource_count

            return pages_built

        except Exception as e:
            logging.error(f"Error in manual page building: {e}")
            return pages_built

def manually_build_resource_pages():
    """Manually build resource detail pages as a fallback."""
    logging.info("Manually building resource detail pages")

    with app.app_context():
        try:
            from americas_essential_data.web.data_access.resource import ResourceRepository
            from americas_essential_data.web.data_access.resource_status import ResourceStatusRepository

            # Get all resources
            resources = ResourceRepository(db_instance).all()
            count = 0

            for resource in resources:
                resource_id = resource['id']
                try:
                    # Get the status history
                    status_history = ResourceStatusRepository(db_instance).find_by_resource_id(resource_id)

                    # Create a request context for the specific resource URL
                    with app.test_request_context(f'/data-and-tools/resources/{resource_id}'):
                        # Render the template
                        html = render_template(
                            "data_and_tools/resources/view_resource.html.jinja",
                            resource=resource,
                            status_history=status_history
                        )

                    # Write the file
                    output_path = os.path.join('build', 'data-and-tools', 'resources', f"{resource_id}.html")
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)

                    with open(output_path, 'w') as f:
                        f.write(html)

                    count += 1
                    if count % 10 == 0:
                        logging.info(f"Built {count} resource pages")

                except Exception as e:
                    logging.error(f"Error building page for resource {resource_id}: {e}")

            return count

        except Exception as e:
            logging.error(f"Error in manual page building: {e}")
            return 0

def copy_static_files():
    """Copy all static files to the build directory."""
    logging.info("Copying static files to build directory...")

    # Calculate source directories based on the new package structure
    sources = [
        # Main app static files
        os.path.join(os.path.dirname(app.root_path), 'static'),
        # Blueprint static files
        os.path.join(app.root_path, 'blueprints', 'data_and_tools', 'static')
    ]

    # Track number of files copied
    count = 0

    for static_source in sources:
        # Skip if the source doesn't exist
        if not os.path.exists(static_source):
            logging.warning(f"Static source directory not found: {static_source}")
            continue

        # Determine target directory
        if 'data_and_tools' in static_source:
            static_dest = os.path.join('build', 'data-and-tools', 'static')
        else:
            static_dest = os.path.join('build', 'static')

        # Create destination if it doesn't exist
        os.makedirs(static_dest, exist_ok=True)

        try:
            # Walk through all files in the static directory
            for root, dirs, files in os.walk(static_source):
                # Get the relative path from the static source directory
                rel_path = os.path.relpath(root, static_source)

                # Create the corresponding directory in the destination
                if rel_path != '.':
                    dest_dir = os.path.join(static_dest, rel_path)
                    os.makedirs(dest_dir, exist_ok=True)
                else:
                    dest_dir = static_dest

                # Copy all files
                for file in files:
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(dest_dir, file)

                    # Copy the file
                    shutil.copy2(src_file, dest_file)
                    count += 1

                    if count % 50 == 0:
                        logging.info(f"Copied {count} static files...")

        except Exception as e:
            logging.error(f"Error copying static files from {static_source}: {e}")

    logging.info(f"Successfully copied {count} static files")
    return count

if __name__ == '__main__':
    logging.info("Starting to freeze specific routes...")

    # Create the build directories if they don't exist
    os.makedirs('build', exist_ok=True)
    os.makedirs(os.path.join('build', 'data-and-tools'), exist_ok=True)
    os.makedirs(os.path.join('build', 'data-and-tools', 'resources'), exist_ok=True)
    os.makedirs(os.path.join('build', 'static'), exist_ok=True)

    try:
        # Try the automatic freezing approach first
        logging.info("Freezing routes automatically...")
        freezer.freeze()

        # Check if resources were generated properly
        resource_pages = list(os.path.join('build', 'data-and-tools', 'resources').glob('*.html'))
        if len(resource_pages) < 2:  # Just index.html or nothing
            logging.warning("Few or no resource pages generated automatically. Trying manual approach...")
            total_pages = manually_build_all_pages()
            logging.info(f"Manually built {total_pages} pages")

        # Copy static files either way
        static_files_count = copy_static_files()

        logging.info(f"Done! Static site generated in the 'build' directory with {static_files_count} static files.")

    except Exception as e:
        logging.error(f"Error in freezing process: {e}")
        # Still try to continue with manual building
        logging.info("Attempting to continue with manual approach...")

        # Try manual building
        total_pages = manually_build_all_pages()

        # Try to copy static files anyway
        static_files_count = copy_static_files()

        if total_pages > 0:
            logging.info(f"Completed with some errors. Generated {total_pages} pages and {static_files_count} static files.")
        else:
            logging.error("Failed to generate static site.")
            exit(1)