#!/usr/bin/env python3
"""Script to freeze specific routes from the Flask application into static HTML files."""
from flask_frozen import Freezer
from americas_essential_data.web.app import create_app, db_instance
import logging
import os
import shutil
from flask import render_template
from pathlib import Path
import traceback

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

    # 2. Create base.css
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
    """Create the base.css file with all variables flattened to their final values."""
    output_file = os.path.join("build", "static", "styles", "base.css")

    # Get the file paths
    css_dir = os.path.join(app.root_path, "static", "styles")
    tokens_path = os.path.join(css_dir, "_tokens.css")
    variables_path = os.path.join(css_dir, "_variables.css")
    navigation_path = os.path.join(css_dir, "_navigation.css")
    resources_path = os.path.join(css_dir, "_resources.css")
    normalize_path = os.path.join(css_dir, "__normalize.css")
    base_path = os.path.join(css_dir, "_base.css")

    # Import missing token values that aren't in the files
    additional_tokens = {
        "--__token__font-family--sans-serif": "'Public Sans', -apple-system, BlinkMacSystemFont, sans-serif",
        "--__token__font-family--serif": "'Merriweather', Georgia, serif",
        "--__token__font-size--base": "16px",
        "--__token__spacing--base": "0.25rem",
        "--__token__radius--base": "4px"
    }

    try:
        import re

        # Step 1: Collect all CSS variables with their values
        all_variables = {}
        all_variables.update(additional_tokens)  # Start with our defaults

        # Extract Google Font imports
        font_imports = []
        if os.path.exists(tokens_path):
            with open(tokens_path, 'r') as f:
                tokens_content = f.read()
                for line in tokens_content.split('\n'):
                    if '@import url(' in line and 'fonts.googleapis.com' in line:
                        font_imports.append(line)
                    elif '--__token__' in line and ':' in line:
                        try:
                            # Use regex to properly extract variable name and value
                            var_match = re.search(r'(--__token__[a-zA-Z0-9_-]+)\s*:\s*([^;]+);', line)
                            if var_match:
                                var_name = var_match.group(1)
                                var_value = var_match.group(2).strip()
                                all_variables[var_name] = var_value
                        except Exception as e:
                            logging.warning(f"Error parsing token variable: {line} - {e}")

        # Now process the variables CSS file (which references tokens)
        if os.path.exists(variables_path):
            with open(variables_path, 'r') as f:
                variables_content = f.read()
                for line in variables_content.split('\n'):
                    if '--' in line and ':' in line and '@import' not in line and 'root' not in line:
                        try:
                            # Use regex to properly extract variable name and value
                            var_match = re.search(r'(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);', line)
                            if var_match:
                                var_name = var_match.group(1)
                                var_value = var_match.group(2).strip()
                                all_variables[var_name] = var_value
                        except Exception as e:
                            logging.warning(f"Error parsing variable: {line} - {e}")

        # Step 2: Recursively resolve all variable references
        def resolve_variable_references(variables):
            """Resolve all variable references until no more can be resolved."""
            made_changes = True
            max_iterations = 10  # Safety limit to prevent infinite loops
            iterations = 0

            while made_changes and iterations < max_iterations:
                made_changes = False
                iterations += 1

                for var_name, var_value in variables.items():
                    if 'var(' in var_value:
                        new_value = var_value
                        # Find all variable references in this value
                        var_refs = re.findall(r'var\((--[^)]+)\)', var_value)

                        for ref in var_refs:
                            if ref in variables:
                                # Replace this reference with its value
                                new_value = new_value.replace(f'var({ref})', variables[ref])
                                made_changes = True

                        variables[var_name] = new_value

            return variables, iterations

        # Resolve all variable references
        resolved_variables, iterations = resolve_variable_references(all_variables)
        logging.info(f"Resolved CSS variables in {iterations} iterations")

        # Step 3: Combine everything into one file with resolved variables
        combined_content = []

        # Add font imports first
        for import_line in font_imports:
            combined_content.append(import_line)

        # Add normalize.css (no variables to resolve)
        if os.path.exists(normalize_path):
            with open(normalize_path, 'r') as f:
                combined_content.append(f"/* normalize.css */")
                combined_content.append(f.read())

        # Add the CSS custom properties root with all resolved variables
        vars_content = [":root {"]
        for var_name, var_value in sorted(resolved_variables.items()):
            if var_name.startswith('--') and not var_name.startswith('--__token__'):
                vars_content.append(f"  {var_name}: {var_value};")
        vars_content.append("}")

        combined_content.append(f"/* All variables with resolved values */")
        combined_content.append('\n'.join(vars_content))

        # Function to replace variable references in CSS content
        def replace_var_references(content):
            """Replace all var() references with their final values."""
            for var_name, var_value in resolved_variables.items():
                # Use regex to match exact var(...) patterns
                pattern = re.compile(r'var\(' + re.escape(var_name) + r'\)')
                content = pattern.sub(var_value, content)
            return content

        # Process and add each CSS file with variables resolved
        css_files = [
            ("navigation.css", navigation_path),
            ("resources.css", resources_path),
            ("base.css", base_path)
        ]

        for file_name, file_path in css_files:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    css_content = f.read()

                    # Remove imports and root blocks since we already have all variables
                    processed_lines = []
                    skip_line = False
                    root_block_depth = 0

                    for line in css_content.split('\n'):
                        # Skip @import lines
                        if '@import' in line:
                            continue

                        # Track :root block
                        if ':root' in line and '{' in line:
                            root_block_depth += 1
                            skip_line = True
                            continue

                        # Count braces to track nested blocks
                        if '{' in line:
                            root_block_depth += line.count('{')
                        if '}' in line:
                            root_block_depth -= line.count('}')
                            # If we're exiting the root block, skip this line too
                            if root_block_depth == 0 and skip_line:
                                skip_line = False
                                continue

                        # Only include lines that aren't in a :root block
                        if not skip_line:
                            processed_lines.append(line)

                    css_content = '\n'.join(processed_lines)

                    # Replace variable references with actual values
                    css_content = replace_var_references(css_content)
                    combined_content.append(f"/* {file_name} (with variables resolved) */")
                    combined_content.append(css_content)

        # Write the combined file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write('\n\n'.join(combined_content))

        logging.info(f"Created flattened base.css at {output_file}")

        # Also create a standalone normalize.css for templates that reference it directly
        if os.path.exists(normalize_path):
            normalize_output = os.path.join("build", "static", "styles", "normalize.css")
            shutil.copy2(normalize_path, normalize_output)
            logging.info(f"Created standalone normalize.css at {normalize_output}")

        return True
    except Exception as e:
        logging.error(f"Error creating flattened base.css: {e}")
        traceback_info = traceback.format_exc()
        logging.error(f"Traceback: {traceback_info}")

        # Create minimal fallback CSS as emergency solution
        try:
            with open(output_file, 'w') as f:
                f.write("""
/* Emergency fallback CSS */
:root {
  --color--blue-dark: #1a3952;
  --color--text-primary: #171717;
  --color--text-inverse: #fafafa;
  --surface--page-background: #f5f5f5;
  --surface--primary: white;
  --spacing--4: 1rem;
  --spacing--2: 0.5rem;
  --font-size--body: 16px;
}

body {
  font-family: -apple-system, sans-serif;
  font-size: 16px;
  line-height: 1.5;
  color: #171717;
  background-color: #f5f5f5;
  margin: 0;
  padding: 0;
}

.site-header {
  background-color: #1a3952;
  color: white;
  padding: 1rem;
}

.site-header a {
  color: white;
  text-decoration: none;
}
""")
            logging.info("Created emergency fallback CSS")
        except Exception as fallback_error:
            logging.error(f"Failed to create emergency CSS: {fallback_error}")

        return False


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
