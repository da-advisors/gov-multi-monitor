#!/usr/bin/env python3
"""Script to freeze specific routes from the Flask application into static HTML files."""
from flask_frozen import Freezer
from multi_monitor.app import create_app
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create the Flask app
app = create_app()

# Configure Frozen-Flask
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_REMOVE_EXTRA_FILES'] = False  # Don't remove files we don't know about
app.config['FREEZER_IGNORE_MIMETYPE_WARNINGS'] = True

# Initialize the freezer with only specific URLs
freezer = Freezer(app, with_no_argument_rules=False, log_url_for=False)

# Explicitly define only the routes we want to freeze
@freezer.register_generator
def view_landing():
    yield {}  # For the root URL '/'

@freezer.register_generator
def list_resources():
    yield {}  # For /resources/

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

if __name__ == '__main__':
    logging.info("Starting to freeze specific routes...")
    
    # Create the build directories if they don't exist
    os.makedirs('build', exist_ok=True)
    os.makedirs('build/resources', exist_ok=True)
    
    # Make sure static files directory exists
    os.makedirs('build/static', exist_ok=True)
    
    try:
        # Run the freezer
        freezer.freeze()
        logging.info("Done! Static site generated in the 'build' directory.")
    except Exception as e:
        logging.error(f"Error freezing: {e}")
        # Continue with other URLs if one fails
        logging.info("Attempting to continue despite errors...")