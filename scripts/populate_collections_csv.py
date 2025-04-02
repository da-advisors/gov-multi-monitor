#!/usr/bin/env python
"""
Script to populate CSV files with collections, resources, collection_resources, and collection_tags from YAML files.
Those CSVs can then be uploaded to our postgres db.
** Be aware that this is much better suited for an initial population since it generates brand new uuid's for anything it processes **
"""

import os
import sys
import uuid
import json
import yaml
import logging
import argparse
import csv
from datetime import datetime
from urllib.parse import urlparse
import mimetypes
from typing import Dict, List, Optional, Set, Tuple
import glob
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize mimetypes
mimetypes.init()


class CollectionPopulator:
    """Populates collections, resources, collection_resources, and collection_tags CSV files from YAML files."""

    def __init__(self, csv_exporter):
        """
        Initialize the collection populator.
        
        Args:
            csv_exporter: CSVExporter instance to use for CSV output
        """
        self.csv_exporter = csv_exporter
        self.duplicate_resource_names = {}
        
        # Track resources by normalized URL
        self.url_to_resource_id = {}

    def _normalize_url(self, url: str) -> str:
        """
        Normalize a URL for comparison.
        
        This removes trailing slashes, normalizes http vs https, and www vs non-www.
        
        Args:
            url: The URL to normalize
            
        Returns:
            Normalized URL
        """
        if not url:
            return ""
        
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.rstrip('/')

    def _determine_resource_type(self, url: str) -> str:
        """
        Determine the resource type based on the URL.
        
        Args:
            url: Resource URL
        
        Returns:
            Resource type (e.g., 'html', 'pdf', etc.)
        """
        if not url:
            return "unknown"
            
        # Check for API endpoints
        if '/api/' in url or 'api.' in urlparse(url).netloc:
            return "api"
            
        # Get file extension
        parsed = urlparse(url)
        path = parsed.path
        extension = os.path.splitext(path)[1].lower()
        
        if extension:
            # Remove the dot
            extension = extension[1:]
            
            # Map common extensions
            if extension in ['html', 'htm']:
                return 'html'
            elif extension in ['json']:
                return 'json'
            elif extension in ['xml']:
                return 'xml'
            elif extension in ['csv']:
                return 'csv'
            elif extension in ['pdf']:
                return 'pdf'
            elif extension in ['xlsx', 'xls']:
                return 'excel'
            elif extension in ['zip', 'gz', 'tar']:
                return 'archive'
            else:
                return extension
        
        # If no extension, try to guess from the URL
        if 'json' in url:
            return 'json'
        elif 'xml' in url:
            return 'xml'
        elif 'csv' in url:
            return 'csv'
        elif 'excel' in url or 'xlsx' in url or 'xls' in url:
            return 'excel'
        
        # Default to url
        return 'url'

    def _insert_resource(self, name: str, url: str, is_primary: bool = False, resource_type: str = None) -> str:
        """
        Insert a resource into the CSV export.
        
        Args:
            name: Resource name
            url: Resource URL
            is_primary: Whether this is a primary resource
            resource_type: Resource type (e.g., 'html', 'pdf', etc.)
        
        Returns:
            Resource ID if successful, None otherwise
        """
        try:
            # Normalize URL
            normalized_url = self._normalize_url(url)
            
            # Determine resource type if not provided
            if not resource_type:
                resource_type = self._determine_resource_type(url)
            
            # Check for existing resource by normalized URL
            if normalized_url in self.url_to_resource_id:
                resource_id = self.url_to_resource_id[normalized_url]
                logger.info(f"Found existing resource with URL {url}, reusing ID {resource_id}")
                return resource_id
            
            # Generate a new resource ID
            resource_id = str(uuid.uuid4())
            
            # Add to CSV exporter
            if self.csv_exporter:
                self.csv_exporter.add_resource(
                    resource_id, name, resource_type, url, normalized_url
                )
                logger.info(f"Added resource to CSV export: {name} ({url})")
                
            # Track this resource
            self.url_to_resource_id[normalized_url] = resource_id
            return resource_id
            
        except Exception as e:
            logger.error(f"Error inserting resource {name}: {e}")
            return None

    def _insert_collection(self, collection_id: str, name: str, description: str, omb_control_number: str, config_file_name: str) -> None:
        """
        Insert a collection into the CSV export.
        
        Args:
            collection_id: Collection ID
            name: Collection name
            description: Collection description
            omb_control_number: OMB control number
            config_file_name: Config file name
        """
        try:
            if self.csv_exporter:
                self.csv_exporter.add_collection(
                    collection_id, name, description, omb_control_number, config_file_name
                )
                logger.info(f"Added collection to CSV export: {name}")
        except Exception as e:
            logger.error(f"Error inserting collection {name}: {e}")

    def _insert_relationship(self, collection_id: str, resource_id: str, is_primary: bool) -> None:
        """
        Insert a relationship between a collection and a resource into the CSV export.
        
        Args:
            collection_id: Collection ID
            resource_id: Resource ID
            is_primary: Whether this is a primary resource
        """
        try:
            if self.csv_exporter:
                self.csv_exporter.add_relationship(
                    collection_id, resource_id, is_primary
                )
                logger.info(f"Added relationship to CSV export: {collection_id} -> {resource_id}")
        except Exception as e:
            logger.error(f"Error inserting relationship: {e}")

    def _insert_tag(self, collection_id: str, tag: str) -> None:
        """
        Insert a tag for a collection into the CSV export.
        
        Args:
            collection_id: Collection ID
            tag: Tag to insert
        """
        try:
            if self.csv_exporter:
                self.csv_exporter.add_tag(
                    collection_id, tag
                )
                logger.info(f"Added tag to CSV export: {collection_id} -> {tag}")
        except Exception as e:
            logger.error(f"Error inserting tag: {e}")

    def process_yaml_file(self, yaml_file_path: str) -> None:
        """
        Process a YAML file and insert the collection and resources into the CSV export.
        
        Args:
            yaml_file_path: Path to the YAML file
        """
        try:
            # Load YAML file
            with open(yaml_file_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Skip if no config
            if not config:
                logger.warning(f"Empty or invalid YAML file: {yaml_file_path}")
                return
                
            # Get collection info
            name = config.get('name', '')
            description = config.get('description', '')
            omb_control_number = config.get('omb_control_number', '')
            
            # Skip if no name
            if not name:
                logger.warning(f"No name in YAML file: {yaml_file_path}")
                return
                
            # Generate a collection ID
            collection_id = str(uuid.uuid4())
            
            # Get the config file name
            config_file_name = os.path.basename(yaml_file_path)
            
            # Insert the collection
            self._insert_collection(
                collection_id, name, description, omb_control_number, config_file_name
            )
            
            # Process main URL
            main_url = config.get('url', '')
            if main_url:
                resource_id = self._insert_resource(
                    name=name,
                    url=main_url,
                    is_primary=True
                )
                
                if resource_id:
                    self._insert_relationship(
                        collection_id=collection_id,
                        resource_id=resource_id,
                        is_primary=True
                    )
            
            # Process linked URLs
            linked_urls = config.get('linked_urls', [])
            if linked_urls:
                for linked_url in linked_urls:
                    if isinstance(linked_url, dict):
                        url = linked_url.get('url', '')
                        url_name = linked_url.get('name', '')
                    else:
                        url = linked_url
                        url_name = f"Linked URL for {name}"
                    
                    if url:
                        resource_id = self._insert_resource(
                            name=url_name,
                            url=url,
                            is_primary=False
                        )
                        
                        if resource_id:
                            self._insert_relationship(
                                collection_id=collection_id,
                                resource_id=resource_id,
                                is_primary=False
                            )
            
            # Process tags
            tags = config.get('tags', [])
            if tags:
                for tag in tags:
                    self._insert_tag(
                        collection_id=collection_id,
                        tag=tag
                    )
            
            logger.info(f"Processed YAML file: {yaml_file_path}")
        except Exception as e:
            logger.error(f"Error processing YAML file {yaml_file_path}: {e}")

    def process_yaml_directory(self, yaml_dir, specific_file=None) -> None:
        """
        Process all YAML files in a directory.
        
        Args:
            yaml_dir: Directory containing YAML files
            specific_file: Optional specific file to process
        """
        try:
            if specific_file:
                # Process a specific file
                yaml_file_path = os.path.join(yaml_dir, specific_file)
                if os.path.exists(yaml_file_path):
                    self.process_yaml_file(yaml_file_path)
                else:
                    logger.error(f"File not found: {yaml_file_path}")
            else:
                # Process all YAML files in the directory
                yaml_files = glob.glob(os.path.join(yaml_dir, '*.yaml'))
                yaml_files.extend(glob.glob(os.path.join(yaml_dir, '*.yml')))
                
                for yaml_file in yaml_files:
                    self.process_yaml_file(yaml_file)
                
                logger.info(f"Processed {len(yaml_files)} YAML files")
        except Exception as e:
            logger.error(f"Error processing YAML directory {yaml_dir}: {e}")

    def save_duplicate_names(self, output_file: str) -> None:
        """
        Save duplicate resource names to a file for curation.
        
        Args:
            output_file: Output file path
        """
        if not self.duplicate_resource_names:
            logger.info("No duplicate resource names found")
            return
            
        try:
            with open(output_file, 'w') as f:
                yaml.dump(self.duplicate_resource_names, f)
            
            logger.info(f"Saved {len(self.duplicate_resource_names)} duplicate resource names to {output_file}")
        except Exception as e:
            logger.error(f"Error saving duplicate resource names: {e}")


class CSVExporter:
    """Exports collections, resources, and collection_resources to CSV files."""
    
    def __init__(self, output_dir):
        """
        Initialize the CSV exporter.
        
        Args:
            output_dir: Directory to write CSV files to
        """
        self.output_dir = output_dir
        self.collections = []
        self.resources = []
        self.collection_resources = []
        self.collection_tags = []
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
    
    def add_collection(self, collection_id, name, description, omb_control_number, config_file_name):
        """Add a collection to the export list."""
        self.collections.append({
            'id': collection_id,
            'name': name,
            'description': description,
            'omb_control_number': omb_control_number,
            'config_file_name': config_file_name,
            'created_at': datetime.now().isoformat()
        })
    
    def add_resource(self, resource_id, name, resource_type, url, normalized_url):
        """Add a resource to the export list."""
        self.resources.append({
            'id': resource_id,
            'name': name,
            'type': resource_type,
            'url': url,
            'normalized_url': normalized_url,
            'created_at': datetime.now().isoformat()
        })
    
    def add_relationship(self, collection_id, resource_id, is_primary):
        """Add a collection-resource relationship to the export list."""
        self.collection_resources.append({
            'id': str(uuid.uuid4()),
            'collection_id': collection_id,
            'resource_id': resource_id,
            'is_primary': is_primary,
            'begin_date': datetime.now().isoformat(),
            'end_date': None
        })
    
    def add_tag(self, collection_id, tag):
        """Add a collection tag to the export list."""
        self.collection_tags.append({
            'id': str(uuid.uuid4()),
            'collection_id': collection_id,
            'tag': tag,
            'begin_date': datetime.now().isoformat(),
            'end_date': None
        })
    
    def write_csv_files(self):
        """Write all data to CSV files."""
        # Write collections
        collections_file = os.path.join(self.output_dir, 'collections.csv')
        if self.collections:
            with open(collections_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.collections[0].keys())
                writer.writeheader()
                writer.writerows(self.collections)
            logger.info(f"Wrote {len(self.collections)} collections to {collections_file}")
        
        # Write resources
        resources_file = os.path.join(self.output_dir, 'resources.csv')
        if self.resources:
            with open(resources_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.resources[0].keys())
                writer.writeheader()
                writer.writerows(self.resources)
            logger.info(f"Wrote {len(self.resources)} resources to {resources_file}")
        
        # Write collection_resources
        relationships_file = os.path.join(self.output_dir, 'collection_resources.csv')
        if self.collection_resources:
            with open(relationships_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.collection_resources[0].keys())
                writer.writeheader()
                writer.writerows(self.collection_resources)
            logger.info(f"Wrote {len(self.collection_resources)} relationships to {relationships_file}")
        
        # Write collection_tags
        tags_file = os.path.join(self.output_dir, 'collection_tags.csv')
        if self.collection_tags:
            with open(tags_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.collection_tags[0].keys())
                writer.writeheader()
                writer.writerows(self.collection_tags)
            logger.info(f"Wrote {len(self.collection_tags)} tags to {tags_file}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Export collections and resources from YAML files to CSV')
    
    # CSV options
    parser.add_argument('--csv-output-dir', default='data/csv_exports', 
                      help='Directory to write CSV files to')
    
    # Input options
    parser.add_argument('--config-dir', default='config/url_configs', 
                      help='Directory containing YAML config files')
    parser.add_argument('--specific-file', 
                      help='Process only a specific YAML file')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )
    
    # Create CSV exporter
    csv_exporter = CSVExporter(args.csv_output_dir)
    
    # Create populator
    logger.info("Running CSV export")
    populator = CollectionPopulator(csv_exporter=csv_exporter)
    
    try:
        # Process the YAML files
        populator.process_yaml_directory(
            yaml_dir=args.config_dir,
            specific_file=args.specific_file
        )
        
        # Save duplicate resource names
        populator.save_duplicate_names("duplicate_resource_names.yaml")
        
        # Write CSV files
        csv_exporter.write_csv_files()
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
