#!/usr/bin/env python3
"""Script to freeze specific routes from the Flask application into static HTML files."""
from flask_frozen import Freezer
from americas_essential_data.web.app import create_app, db_instance
import logging
import os
import shutil
from flask import render_template
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create the Flask app
app = create_app()

# Configure Frozen-Flask
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_REMOVE_EXTRA_FILES'] = False  # Don't remove files we don't know about
app.config['FREEZER_IGNORE_MIMETYPE_WARNINGS'] = True
app.config['FREEZER_DEFAULT_MIMETYPE'] = 'text/html'

# Configure Flask for URL building
app.config["SERVER_NAME"] = None  # Remove this line or set to None
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
                # The URL structure should match your blueprint route
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

                    # Create a directory for this resource and save as index.html
                    output_path = os.path.join('build', 'data-and-tools', 'resources', resource_id, 'index.html')
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

    # Create output directories
    os.makedirs(os.path.join("build", "static", "styles"), exist_ok=True)
    os.makedirs(
        os.path.join("build", "data-and-tools", "static", "styles"), exist_ok=True
    )

    # First, process the CSS files that need to be built from partials
    process_css_files()

    # Then copy all other static files
    count = 0

    # Main app static files
    main_static = os.path.join(app.root_path, "static")
    if os.path.exists(main_static):
        count += copy_directory(
            main_static,
            os.path.join("build", "static"),
            skip_dirs=["styles", "styles/_partials"],
        )

    # Blueprint static files
    blueprint_static = os.path.join(
        app.root_path, "blueprints", "data_and_tools", "static"
    )
    if os.path.exists(blueprint_static):
        count += copy_directory(
            blueprint_static,
            os.path.join("build", "data-and-tools", "static"),
            skip_dirs=["styles", "styles/_partials"],
        )

    logging.info(f"Successfully copied {count} static files")
    return count


def copy_directory(src, dest, skip_dirs=None):
    """Copy files from source to destination, skipping specified directories."""
    count = 0
    skip_dirs = skip_dirs or []

    for root, dirs, files in os.walk(src):
        # Skip directories that should be excluded
        for skip_dir in skip_dirs:
            if skip_dir in root:
                continue

        # Get relative path
        rel_path = os.path.relpath(root, src)
        if rel_path == ".":
            dest_dir = dest
        else:
            dest_dir = os.path.join(dest, rel_path)

        # Create destination directory
        os.makedirs(dest_dir, exist_ok=True)

        # Copy files
        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(dest_dir, file)
            shutil.copy2(src_file, dest_file)
            count += 1

    return count


def process_css_files():
    """Process CSS files for the static build."""
    logging.info("Processing CSS files...")

    # Manually create the needed CSS files

    # 1. Create normalize.css
    normalize_src = os.path.join(app.root_path, "static", "styles", "__normalize.css")
    if os.path.exists(normalize_src):
        shutil.copy2(
            normalize_src, os.path.join("build", "static", "styles", "normalize.css")
        )
        logging.info("Created normalize.css")
    else:
        logging.warning("normalize.css source not found!")

    # 2. Create base.css by combining files
    create_base_css()

    # 3. Create resources.css
    resources_src = os.path.join(
        app.root_path,
        "blueprints",
        "data_and_tools",
        "static",
        "styles",
        "resources.css",
    )
    if os.path.exists(resources_src):
        shutil.copy2(
            resources_src,
            os.path.join(
                "build", "data-and-tools", "static", "styles", "resources.css"
            ),
        )
        logging.info("Created resources.css")
    else:
        logging.warning("resources.css source not found!")

    # 4. Create index.css
    index_src = os.path.join(
        app.root_path, "blueprints", "data_and_tools", "static", "styles", "index.css"
    )
    if os.path.exists(index_src):
        shutil.copy2(
            index_src,
            os.path.join("build", "data-and-tools", "static", "styles", "index.css"),
        )
        logging.info("Created index.css")
    else:
        logging.warning("index.css source not found!")


def create_base_css():
    """Create the base.css file by combining partials."""
    output_file = os.path.join("build", "static", "styles", "base.css")

    # List of files to combine in order
    source_files = [
        os.path.join(app.root_path, "static", "styles", "__normalize.css"),
        os.path.join(app.root_path, "static", "styles", "_variables.css"),
        os.path.join(app.root_path, "static", "styles", "_navigation.css"),
        os.path.join(app.root_path, "static", "styles", "_base.css"),
    ]

    combined_content = []

    # Read and combine each file
    for file_path in source_files:
        if os.path.exists(file_path):
            logging.info(f"Adding {os.path.basename(file_path)} to base.css")
            with open(file_path, "r") as f:
                combined_content.append(f"/* {os.path.basename(file_path)} */")
                combined_content.append(f.read())
        else:
            logging.warning(f"CSS partial not found: {file_path}")

    # Write the combined file
    if combined_content:
        with open(output_file, "w") as f:
            f.write("\n\n".join(combined_content))
        logging.info(f"Created base.css at {output_file}")
    else:
        logging.error("No content found for base.css!")


def fix_static_urls():
    """Fix static URLs in all HTML files to use root-relative paths."""
    logging.info("Fixing static URLs in HTML files...")

    # Get all HTML files
    html_files = []
    for root, _, files in os.walk("build"):
        for file in files:
            if file.endswith(".html"):
                html_files.append(os.path.join(root, file))

    count = 0
    for html_file in html_files:
        try:
            with open(html_file, "r") as f:
                content = f.read()

            # Fix relative static URLs
            modified = content.replace('href="../static/', 'href="/static/')
            modified = modified.replace('href="../../static/', 'href="/static/')
            modified = modified.replace('href="../../../static/', 'href="/static/')

            # Fix blueprint static URLs
            modified = modified.replace(
                'href="../data-and-tools/static/', 'href="/data-and-tools/static/'
            )
            modified = modified.replace(
                'href="../../data-and-tools/static/', 'href="/data-and-tools/static/'
            )
            modified = modified.replace(
                'href="../../../data-and-tools/static/', 'href="/data-and-tools/static/'
            )

            # Fix image URLs
            modified = modified.replace('src="../static/', 'src="/static/')
            modified = modified.replace('src="../../static/', 'src="/static/')
            modified = modified.replace('src="../../../static/', 'src="/static/')

            # Only write if changes were made
            if modified != content:
                with open(html_file, "w") as f:
                    f.write(modified)
                count += 1
        except Exception as e:
            logging.error(f"Error fixing URLs in {html_file}: {e}")

    logging.info(f"Fixed URLs in {count} HTML files")


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

        # Check if resources were generated properly - look for index.html files in subdirectories
        resource_dirs = [d for d in Path(os.path.join('build', 'data-and-tools', 'resources')).iterdir()
                        if d.is_dir() and (d / 'index.html').exists()]

        if len(resource_dirs) < 1:  # No resource detail pages found
            logging.warning("No resource detail pages generated automatically. Trying manual approach...")
            total_pages = manually_build_all_pages()
            logging.info(f"Manually built {total_pages} pages")

        # Copy static files either way
        static_files_count = copy_static_files()

        # Fix static URLs
        fix_static_urls()

        logging.info(f"Done! Static site generated in the 'build' directory with {static_files_count} static files.")

    except Exception as e:
        logging.error(f"Error in freezing process: {e}")
        # Still try to continue with manual building
        logging.info("Attempting to continue with manual approach...")

        # Try manual building
        total_pages = manually_build_all_pages()

        # Try to copy static files anyway
        static_files_count = copy_static_files()

        # Fix static URLs
        fix_static_urls()

        if total_pages > 0:
            logging.info(f"Completed with some errors. Generated {total_pages} pages and {static_files_count} static files.")
        else:
            logging.error("Failed to generate static site.")
            exit(1)

    # Fix static URLs in HTML files after everything else is done
    fix_static_urls()

    logging.info("Static site generation complete!")
