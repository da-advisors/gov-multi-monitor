#!/usr/bin/env python3
"""
Combine resource status data from a CSV file and a DuckDB database into a single CSV file.
"""

import argparse
import csv
import datetime
import duckdb
import json
import logging
import os
import pandas as pd
import uuid
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StatusDataCombiner:
    """Combine resource status data from a CSV file and a DuckDB database."""
    
    def __init__(self, duckdb_path: str, csv_path: str, resources_csv_path: str, output_csv_path: str):
        """
        Initialize the status data combiner.
        
        Args:
            duckdb_path: Path to the DuckDB database file
            csv_path: Path to the CSV file with status data
            resources_csv_path: Path to the CSV file with resource data
            output_csv_path: Path to the output CSV file
        """
        self.duckdb_path = duckdb_path
        self.csv_path = csv_path
        self.resources_csv_path = resources_csv_path
        self.output_csv_path = output_csv_path
        
        # Dictionary to store URL to resource_id mapping
        self.url_to_resource_id = {}
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_csv_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize a URL by removing trailing slashes and query parameters.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL
        """
        if not url:
            return ""
        
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized.rstrip('/')
    
    def _load_resource_mapping(self):
        """
        Load mapping of URLs to resource IDs from the resources CSV file.
        """
        try:
            if not os.path.exists(self.resources_csv_path):
                logger.error(f"Resources CSV file not found: {self.resources_csv_path}")
                return
            
            with open(self.resources_csv_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    normalized_url = self._normalize_url(row['url'])
                    self.url_to_resource_id[normalized_url] = row['id']
            
            logger.info(f"Loaded {len(self.url_to_resource_id)} resources from CSV")
        except Exception as e:
            logger.error(f"Error loading resource mapping: {e}")
            raise
    
    def _extract_duckdb_status(self) -> pd.DataFrame:
        """
        Extract resource status data from the DuckDB database.
        
        Returns:
            DataFrame with status data
        """
        try:
            # Connect to DuckDB
            conn = duckdb.connect(self.duckdb_path)
            
            # Extract resource status data
            query = """
            SELECT 
                rs.id,
                r.url,
                r.name,
                rs.status,
                rs.status_code,
                rs.error_message AS status_text,
                rs.checked_at,
                'duckdb' AS source,
                '' AS run_id,
                '' AS run_url,
                rs.content_length
            FROM 
                resource_status rs
            JOIN 
                resources r ON rs.resource_id = r.id
            """
            
            df = conn.execute(query).df()
            
            # Close connection
            conn.close()
            
            logger.info(f"Extracted {len(df)} status entries from DuckDB")
            return df
        except Exception as e:
            logger.error(f"Error extracting DuckDB status: {e}")
            raise
    
    def _extract_csv_status(self) -> pd.DataFrame:
        """
        Extract status data from the CSV file.
        
        Returns:
            DataFrame with status data
        """
        try:
            if not os.path.exists(self.csv_path):
                logger.error(f"CSV file not found: {self.csv_path}")
                return pd.DataFrame()
            
            # Read CSV file
            df = pd.read_csv(self.csv_path)
            
            # Rename columns if needed
            if 'file_size' in df.columns:
                df = df.rename(columns={'file_size': 'content_length'})
            
            # Add id column if not present
            if 'id' not in df.columns:
                df['id'] = [str(uuid.uuid4()) for _ in range(len(df))]
            
            logger.info(f"Extracted {len(df)} status entries from CSV")
            return df
        except Exception as e:
            logger.error(f"Error extracting CSV status: {e}")
            raise
    
    def combine_data(self):
        """
        Combine status data from the DuckDB database and CSV file.
        """
        try:
            # Load resource mapping
            self._load_resource_mapping()
            
            # Extract status data
            duckdb_df = self._extract_duckdb_status()
            csv_df = self._extract_csv_status()
            
            # Combine data
            combined_df = pd.concat([duckdb_df, csv_df], ignore_index=True)
            
            # Map URLs to resource IDs
            def map_url_to_resource_id(url):
                normalized_url = self._normalize_url(url)
                return self.url_to_resource_id.get(normalized_url)
            
            combined_df['resource_id'] = combined_df['url'].apply(map_url_to_resource_id)
            
            # Filter out entries without a resource ID
            filtered_df = combined_df[combined_df['resource_id'].notna()]
            
            # Simplify error messages
            def simplify_error_message(msg):
                if not isinstance(msg, str):
                    return msg
                
                if "Max retries exceeded" in msg:
                    return "max retries exceeded"
                elif "Connection refused" in msg:
                    return "connection refused"
                elif "Connection timed out" in msg:
                    return "connection timeout"
                elif "Name or service not known" in msg or "NameResolutionError" in msg:
                    return "name resolution error"
                elif "certificate verify failed" in msg:
                    return "ssl certificate error"
                elif "Read timed out" in msg:
                    return "read timeout"
                elif len(msg) > 100:  # If it's a very long message
                    return "error: " + msg[:97] + "..."
                return msg
            
            if 'status_text' in filtered_df.columns:
                filtered_df['status_text'] = filtered_df['status_text'].apply(simplify_error_message)
            
            # Format data for output
            output_df = pd.DataFrame({
                'id': filtered_df['id'],
                'resource_id': filtered_df['resource_id'],
                'status': filtered_df['status'],
                'checked_at': filtered_df['checked_at'],
                'status_code': filtered_df['status_code'],
                'status_text': filtered_df['status_text'] if 'status_text' in filtered_df.columns else None,
                'response_time': None,
                'redirect_url': None,
                'last_modified': None,
                'content_hash': None,
                'content_length': filtered_df['content_length'],
                'field_name': None,
                'field_found': None,
                'field_value': None,
                'expected_value': None,
                'parent_url_status_id': None,
                'error_message': None,
                'source': filtered_df['source'],
                'run_id': filtered_df['run_id'] if 'run_id' in filtered_df.columns else None,
                'run_url': filtered_df['run_url'] if 'run_url' in filtered_df.columns else None,
                'metadata': '{}'
            })
            
            # Write to CSV
            output_df.to_csv(self.output_csv_path, index=False)
            
            logger.info(f"Combined {len(output_df)} status entries and wrote to {self.output_csv_path}")
            logger.info(f"Filtered out {len(combined_df) - len(filtered_df)} entries without a resource ID")
        except Exception as e:
            logger.error(f"Error combining data: {e}")
            raise

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Combine resource status data from a CSV file and a DuckDB database')
    
    parser.add_argument('--duckdb-path', required=True,
                        help='Path to the DuckDB database file')
    parser.add_argument('--csv-path', required=True,
                        help='Path to the CSV file with status data')
    parser.add_argument('--resources-csv-path', required=True,
                        help='Path to the CSV file with resource data')
    parser.add_argument('--output-csv-path', required=True,
                        help='Path to the output CSV file')
    
    args = parser.parse_args()
    
    # Create combiner
    combiner = StatusDataCombiner(
        duckdb_path=args.duckdb_path,
        csv_path=args.csv_path,
        resources_csv_path=args.resources_csv_path,
        output_csv_path=args.output_csv_path
    )
    
    # Combine data
    combiner.combine_data()

if __name__ == '__main__':
    main()
