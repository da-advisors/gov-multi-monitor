#!/usr/bin/env python3
"""
Migrate data from history.parquet to DuckDB with new schema.
"""
import os
from datetime import datetime
from pathlib import Path
import re
import uuid
import hashlib

import pandas as pd
from tqdm import tqdm

from multi_monitor.db import MonitorDB
from multi_monitor.config import MonitorConfig


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower().replace(' ', '_')
    text = re.sub(r'[^\w_]', '', text)
    return text


def hash_content(content: str) -> str:
    """Create SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def migrate_history(parquet_path: Path, config_path: Path):
    """Migrate history data from Parquet to DuckDB.
    
    Args:
        parquet_path: Path to history.parquet file
        config_path: Path to monitor config file
    """
    print(f"Reading history from {parquet_path}")
    history_df = pd.read_parquet(parquet_path)
    
    print(f"Reading config from {config_path}")
    config = MonitorConfig.from_yaml(config_path)
    
    # Initialize database
    db = MonitorDB()
    
    # Track mappings
    url_to_resource = {}  # Map URLs to resource IDs
    url_to_collection = {}  # Map URLs to collection IDs
    
    print("Processing URL configs...")
    for config_file in tqdm(list(Path('config/url_configs').glob('*.yaml'))):
        url_config = MonitorConfig.from_yaml(config_file)
        
        # Create collection
        collection_id = db.create_collection(
            name=url_config.name or slugify(url_config.url),
            description=f"Monitoring collection from {config_file.name}",
            metadata={
                'config_file': str(config_file),
                'expected_update_frequency': url_config.expected_update_frequency
            },
            tags=url_config.tags
        )
        
        # Create primary URL resource
        resource_id = db.add_resource(
            name=url_config.name or slugify(url_config.url),
            type='url',
            url=url_config.url,
            metadata={
                'expected_update_frequency': url_config.expected_update_frequency,
                'is_primary': True
            }
        )
        
        # Link resource to collection
        db.add_resource_to_collection(
            collection_id=collection_id,
            resource_id=resource_id,
            is_primary=True,
            metadata={
                'config_file': str(config_file)
            }
        )
        
        url_to_resource[url_config.url] = resource_id
        url_to_collection[url_config.url] = collection_id
        
        # Process linked URLs
        if url_config.linked_urls:
            for linked in url_config.linked_urls:
                linked_id = db.add_resource(
                    name=linked.name or slugify(linked.url),
                    type='url',
                    url=linked.url,
                    metadata={
                        'expected_update_frequency': linked.expected_update_frequency,
                        'is_primary': False
                    }
                )
                
                db.add_resource_to_collection(
                    collection_id=collection_id,
                    resource_id=linked_id,
                    is_primary=False,
                    metadata={
                        'config_file': str(config_file)
                    }
                )
                
                url_to_resource[linked.url] = linked_id
                url_to_collection[linked.url] = collection_id
        
        # Process API fields
        if url_config.api_config:
            for field in url_config.api_config.expected_fields:
                field_id = db.add_resource(
                    name=field,
                    type='api_field',
                    metadata={
                        'field_name': field,
                        'expected_value': None  # Could be added to config later
                    }
                )
                
                db.add_resource_to_collection(
                    collection_id=collection_id,
                    resource_id=field_id,
                    is_primary=False,
                    metadata={
                        'config_file': str(config_file),
                        'parent_url': url_config.url
                    }
                )
    
    print("Migrating history data...")
    # Group history by URL to process each resource's history
    for url in tqdm(history_df['url'].unique()):
        if url not in url_to_resource:
            print(f"Warning: No resource found for URL {url}, creating one...")
            # Create standalone resource
            resource_id = db.add_resource(
                name=slugify(url),
                type='url',
                url=url,
                metadata={
                    'auto_created': True,
                    'from_history': True
                }
            )
            url_to_resource[url] = resource_id
        
        resource_id = url_to_resource[url]
        collection_id = url_to_collection.get(url)
        
        # Add history entries
        url_history = history_df[history_df['url'] == url].sort_values('timestamp')
        for _, row in url_history.iterrows():
            # Add to status history
            status_id = db.add_resource_status(
                resource_id=resource_id,
                status=row['status'],
                checked_at=row['timestamp'],
                url_data={
                    'status_code': row['status_code'],
                    'response_time': row.get('response_time'),
                    'redirect_url': row.get('redirect_url'),
                    'last_modified': row.get('last_modified'),
                    'content_hash': hash_content(str(row.get('content', ''))) if row.get('content') else None
                },
                error_message=row.get('error_message'),
                metadata={
                    'from_history': True
                }
            )
            
            # Update collection status if part of collection
            if collection_id:
                resources = db.get_collection_resources(collection_id)
                total = len(resources)
                available = sum(1 for r in resources if r['status'] == 'ok')
                error = total - available
                
                db.add_collection_status(
                    collection_id=collection_id,
                    total_resources=total,
                    available_resources=available,
                    error_resources=error,
                    status_summary={
                        'urls': {
                            'ok': available,
                            'error': error
                        }
                    }
                )
    
    print("Migration complete!")
    print("\nSummary:")
    
    # Print summary statistics
    collection_count = db.conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
    resource_count = db.conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
    history_count = db.conn.execute("SELECT COUNT(*) FROM status_history").fetchone()[0]
    collection_resource_count = db.conn.execute("SELECT COUNT(*) FROM collection_resources").fetchone()[0]
    
    print(f"Collections created: {collection_count}")
    print(f"Resources created: {resource_count}")
    print(f"History entries migrated: {history_count}")
    print(f"Collection-Resource links created: {collection_resource_count}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate history.parquet to DuckDB")
    parser.add_argument(
        "--history",
        default="data/history.parquet",
        help="Path to history.parquet file"
    )
    parser.add_argument(
        "--config",
        default="config/monitor_config.yaml",
        help="Path to monitor config file"
    )
    args = parser.parse_args()
    
    migrate_history(Path(args.history), Path(args.config))
