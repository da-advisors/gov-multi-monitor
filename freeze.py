#!/usr/bin/env python3
"""Script to freeze specific routes from the Flask application into static HTML files."""
from flask_frozen import Freezer
from multi_monitor.app import create_app
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

# Register all basic pages - define them explicitly here
@freezer.register_generator
def view_data_and_tools():
    yield {}  # For /data-and-tools

# Root URL mapping ('/')
@freezer.register_generator
def index():
    yield {}

@freezer.register_generator
def list_resources():
    yield {}  # For /resources/

# @freezer.register_generator
# def list_statuses():
#     yield {}  # For /status/

@freezer.register_generator
def get_resources_data():
    yield {}  # For API endpoint

@freezer.register_generator
def get_resource_status_history():
    # This needs a resource_id parameter
    # We'll handle this in a more targeted way
    pass

@freezer.register_generator
def view_resource():
    # Get all resource IDs from the database
    with app.app_context():
        try:
            # Set up database access
            from flask import g
            db = None

            # Try different ways to get the database connection
            if hasattr(app, 'extensions') and 'db' in app.extensions:
                db = app.extensions['db']
            else:
                db = g.get('db')

            if not db:
                # If still no db, try to initialize it
                from multi_monitor.app import get_db
                db = get_db()

            if db:
                # Get all resource IDs
                results = db._read_query("SELECT id FROM resources")

                # Print what we're generating for debugging
                logging.info(f"Found {len(results)} resources to generate pages for")

                # Yield each resource ID
                for resource in results:
                    resource_id = resource['id']
                    logging.info(f"Generating page for resource: {resource_id}")
                    yield {'resource_id': resource_id}
            else:
                logging.error("Could not access database")
        except Exception as e:
            logging.error(f"Error getting resources: {e}")

def manually_build_all_pages():
    """Manually build all pages as a fallback."""

    with app.app_context():
        pages_built = 0

        try:
            # Build basic pages
            pages = [
                ("/", "index.html"),
                ("/data-and-tools", "data-and-tools.html"),
                ("/resources/", "resources/index.html"),
                ("/status/", "status/index.html")
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
            # Set up database access
            from flask import g
            db = None

            # Try different ways to get the database connection
            if hasattr(app, 'extensions') and 'db' in app.extensions:
                db = app.extensions['db']
            else:
                db = g.get('db')

            if not db:
                # If still no db, try to initialize it
                from multi_monitor.app import get_db
                db = get_db()

            if db:
                # Get all resource IDs
                results = db._read_query("SELECT id FROM resources")
                count = 0

                for resource in results:
                    resource_id = resource['id']
                    try:
                        # Get the resource details
                        resource_data = db._read_query(
                            f"""
                            SELECT * FROM resources
                            WHERE id = '{resource_id}';
                            """
                        )[0]

                        # Get the status history
                        status_history = db._read_query(
                            f"""
                            SELECT * FROM resource_status
                            WHERE resource_id = '{resource_id}'
                            ORDER BY checked_at DESC;
                            """
                        )

                        # Create a request context for the specific resource URL
                        with app.test_request_context(f'/resources/{resource_id}'):
                            # Render the template
                            html = render_template(
                                "multi_page/resource_detail.html.jinja",
                                resource=resource_data,
                                status_history=status_history
                            )

                        # Write the file to build/resources/resource_id.html
                        output_path = os.path.join('build', 'resources', f"{resource_id}.html")
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)

                        with open(output_path, 'w') as f:
                            f.write(html)

                        count += 1
                        if count % 10 == 0:
                            logging.info(f"Built {count} resource pages")

                    except Exception as e:
                        logging.error(f"Error building page for resource {resource_id}: {e}")

                return count

            else:
                logging.error("Could not access database for manual page building")
                return 0

        except Exception as e:
            logging.error(f"Error in manual page building: {e}")
            return 0

def copy_static_files():
    """Copy all static files to the build directory."""
    logging.info("Copying static files to build directory...")

    # Source directory (Flask static folder)
    static_source = os.path.join(os.path.dirname(app.root_path), 'multi_monitor', 'static')

    # Destination directory
    static_dest = os.path.join('build', 'static')

    if not os.path.exists(static_source):
        logging.error(f"Static source directory not found: {static_source}")
        return 0

    # Create destination if it doesn't exist
    os.makedirs(static_dest, exist_ok=True)

    # Track number of files copied
    count = 0

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

        logging.info(f"Successfully copied {count} static files to {static_dest}")
        return count

    except Exception as e:
        logging.error(f"Error copying static files: {e}")
        return count

if __name__ == '__main__':
    logging.info("Starting to freeze specific routes...")

    # Create the build directories if they don't exist
    os.makedirs('build', exist_ok=True)
    os.makedirs('build/resources', exist_ok=True)
    os.makedirs('build/static', exist_ok=True)
    os.makedirs('build/status', exist_ok=True)

    try:
        # Try the manual approach directly to have more control
        logging.info("Building pages manually...")
        total_pages = manually_build_all_pages()

        # Copy static files
        static_files_count = copy_static_files()

        logging.info(f"Done! Static site generated in the 'build' directory with {total_pages} pages and {static_files_count} static files.")

    except Exception as e:
        logging.error(f"Error in freezing process: {e}")
        # Still try to continue with manual building
        logging.info("Attempting to continue despite errors...")

        # Try to copy static files anyway
        copy_static_files()