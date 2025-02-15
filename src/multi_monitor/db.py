"""
Database module for storing monitoring data using DuckDB.
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import uuid
import json

import duckdb
from dataclasses import asdict

from .checker import CheckResult, LinkedURLCheckResult, APICheckResult


class MonitorDB:
    """Database for storing monitoring data."""
    
    def __init__(self, db_path: Union[str, Path] = "data/monitor.db"):
        """Initialize database connection and ensure tables exist.
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize connection
        self.conn = duckdb.connect(str(self.db_path))
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        # Collections
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id VARCHAR PRIMARY KEY,    -- UUID
                name TEXT NOT NULL,
                description TEXT,
                metadata JSON,             -- Flexible metadata
                tags JSON,                 -- Collection tags
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Resources (URLs and API fields)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id VARCHAR PRIMARY KEY,    -- UUID
                name TEXT NOT NULL,
                type TEXT NOT NULL,        -- 'url' or 'api_field'
                url TEXT,                  -- NULL for api_fields
                metadata JSON,             -- Flexible metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Collection-Resource relationships
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_resources (
                id VARCHAR PRIMARY KEY,    -- UUID
                collection_id VARCHAR NOT NULL,
                resource_id VARCHAR NOT NULL,
                is_primary BOOLEAN,        -- Is this the primary resource for collection
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,        -- When removed from collection
                metadata JSON,             -- Including config_source, end_reason
                FOREIGN KEY (collection_id) REFERENCES collections(id),
                FOREIGN KEY (resource_id) REFERENCES resources(id)
            )
        """)

        # Archived URLs for resources
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS archived_urls (
                id VARCHAR PRIMARY KEY,    -- UUID
                resource_id VARCHAR NOT NULL,
                archive_url TEXT NOT NULL,
                archive_type TEXT NOT NULL, -- e.g., 'wayback', 'local_snapshot'
                archived_at TIMESTAMP,
                metadata JSON,             -- Additional archive info
                FOREIGN KEY (resource_id) REFERENCES resources(id)
            )
        """)

        # Point-in-time resource status
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS resource_status (
                id VARCHAR PRIMARY KEY,    -- UUID
                resource_id VARCHAR NOT NULL,
                status TEXT NOT NULL,      -- 'ok', 'error', 'missing'
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- URL-specific fields
                status_code INTEGER,       -- HTTP status code
                response_time FLOAT,       -- Response time in seconds
                redirect_url TEXT,         -- If redirected
                last_modified TEXT,        -- Last-Modified header
                content_hash TEXT,         -- Hash of content if tracking changes
                content_length BIGINT,     -- Added for tracking response size
                
                -- API field-specific fields
                field_name TEXT,           -- Name of the API field
                field_found BOOLEAN,       -- Whether field was found in response
                field_value TEXT,          -- Current value of field
                expected_value TEXT,       -- Expected value if specified
                parent_url_status_id VARCHAR,  -- Link to parent URL's status
                
                -- Common fields
                error_message TEXT,        -- Error details if status='error'
                metadata JSON,             -- Additional check-specific data
                
                FOREIGN KEY (resource_id) REFERENCES resources(id),
                FOREIGN KEY (parent_url_status_id) REFERENCES resource_status(id)
            )
        """)

        # Status history
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id VARCHAR PRIMARY KEY,    -- UUID
                resource_id VARCHAR NOT NULL,
                status TEXT NOT NULL,      -- 'ok', 'error', 'missing'
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- URL-specific fields
                status_code INTEGER,
                response_time FLOAT,
                redirect_url TEXT,
                last_modified TEXT,
                content_hash TEXT,
                
                -- API field-specific fields
                field_name TEXT,
                field_found BOOLEAN,
                field_value TEXT,
                expected_value TEXT,
                parent_url_status_id VARCHAR,
                
                -- Common fields
                error_message TEXT,
                metadata JSON,
                
                FOREIGN KEY (resource_id) REFERENCES resources(id),
                FOREIGN KEY (parent_url_status_id) REFERENCES status_history(id)
            )
        """)

        # Collection status (aggregated from resources)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_status (
                id VARCHAR PRIMARY KEY,    -- UUID
                collection_id VARCHAR NOT NULL,
                total_resources INTEGER NOT NULL,
                available_resources INTEGER NOT NULL,
                error_resources INTEGER NOT NULL,
                status_summary JSON,       -- Detailed breakdown
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (collection_id) REFERENCES collections(id)
            )
        """)
    
    def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """Create a new collection.
        
        Args:
            name: Collection name
            description: Optional description
            metadata: Optional additional metadata
            tags: Optional list of tags
            
        Returns:
            Collection ID (UUID)
        """
        collection_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO collections (id, name, description, metadata, tags)
            VALUES (?, ?, ?, ?, ?)
        """, [collection_id, name, description, metadata, tags])
        return collection_id
    
    def add_resource(
        self,
        name: str,
        type: str,
        url: Optional[str] = None,
        metadata: Optional[Dict] = None,
        id: Optional[str] = None  # Allow passing explicit ID
    ) -> str:
        """Add a new resource.
        
        Args:
            name: Resource name
            type: Resource type (url, api_field)
            url: Optional URL
            metadata: Optional additional metadata
            id: Optional explicit ID to use (if not provided, will generate UUID)
            
        Returns:
            Resource ID (UUID)
        """
        resource_id = id or str(uuid.uuid4())
        
        # Convert metadata to JSON string if it's not None
        metadata_json = json.dumps(metadata) if metadata is not None else None
        
        self.conn.execute("""
            INSERT INTO resources (id, name, type, url, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [resource_id, name, type, url, metadata_json, datetime.utcnow()])
        return resource_id
    
    def add_resource_to_collection(
        self,
        collection_id: str,
        resource_id: str,
        is_primary: bool = False,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a resource to a collection.
        
        Args:
            collection_id: Collection ID
            resource_id: Resource ID
            is_primary: Whether this is the primary resource for the collection
            metadata: Optional additional metadata
            
        Returns:
            Collection-Resource relationship ID (UUID)
        """
        relationship_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO collection_resources (
                id, collection_id, resource_id, is_primary, metadata
            )
            VALUES (?, ?, ?, ?, ?)
        """, [relationship_id, collection_id, resource_id, is_primary, metadata])
        return relationship_id
    
    def add_archived_url(
        self,
        resource_id: str,
        archive_url: str,
        archive_type: str,
        archived_at: datetime,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add an archived URL for a resource.
        
        Args:
            resource_id: Resource ID
            archive_url: Archived URL
            archive_type: Type of archive (e.g., 'wayback', 'local_snapshot')
            archived_at: Timestamp of archiving
            metadata: Optional additional metadata
            
        Returns:
            Archived URL ID (UUID)
        """
        archived_url_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO archived_urls (
                id, resource_id, archive_url, archive_type, archived_at, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            archived_url_id, resource_id, archive_url, archive_type, archived_at, metadata
        ])
        return archived_url_id
    
    def add_resource_status(
        self,
        resource_id: str,
        status: str,
        checked_at: Optional[datetime] = None,
        url_data: Optional[Dict] = None,
        api_field_data: Optional[Dict] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a point-in-time status for a resource.
        
        Args:
            resource_id: Resource ID
            status: Status ('ok', 'error', 'missing')
            checked_at: When the check was performed
            url_data: Dict of URL-specific status data:
                - status_code: HTTP status code
                - response_time: Response time in seconds
                - redirect_url: URL if redirected
                - last_modified: Last-Modified header
                - content_hash: Hash of content if tracking changes
                - content_length: Length of content in bytes
            api_field_data: Dict of API field-specific status data:
                - field_name: Name of the field
                - field_found: Whether field was found
                - field_value: Current value
                - expected_value: Expected value if any
                - parent_url_status_id: ID of parent URL's status
            error_message: Error details if status='error'
            metadata: Additional check-specific data
            
        Returns:
            Resource status ID (UUID)
        """
        status_id = str(uuid.uuid4())
        
        # Build field values
        values = {
            'id': status_id,
            'resource_id': resource_id,
            'status': status,
            'checked_at': checked_at or datetime.utcnow(),
            'error_message': error_message,
            'metadata': metadata,
            
            # URL fields
            'status_code': None,
            'response_time': None,
            'redirect_url': None,
            'last_modified': None,
            'content_hash': None,
            'content_length': None,
            
            # API fields
            'field_name': None,
            'field_found': None,
            'field_value': None,
            'expected_value': None,
            'parent_url_status_id': None
        }
        
        # Update with URL data if provided
        if url_data:
            values.update(url_data)
            
        # Update with API field data if provided
        if api_field_data:
            values.update(api_field_data)
        
        # Build SQL dynamically to handle NULL values correctly
        fields = list(values.keys())
        placeholders = ['?' for _ in fields]
        
        sql = f"""
            INSERT INTO resource_status (
                {', '.join(fields)}
            )
            VALUES (
                {', '.join(placeholders)}
            )
        """
        
        self.conn.execute(sql, list(values.values()))
        return status_id
    
    def add_collection_status(
        self,
        collection_id: str,
        total_resources: int,
        available_resources: int,
        error_resources: int,
        status_summary: Dict
    ) -> str:
        """Add a point-in-time status for a collection.
        
        Args:
            collection_id: Collection ID
            total_resources: Total number of resources in the collection
            available_resources: Number of available resources in the collection
            error_resources: Number of error resources in the collection
            status_summary: Detailed breakdown of the collection status
            
        Returns:
            Collection status ID (UUID)
        """
        status_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO collection_status (
                id, collection_id, total_resources, available_resources,
                error_resources, status_summary
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            status_id, collection_id, total_resources, available_resources,
            error_resources, status_summary
        ])
        return status_id
    
    def add_check_result(self, resource_id: str, result: CheckResult):
        """Add a check result.
        
        Args:
            resource_id: Resource ID
            result: Check result to store
        """
        status_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO status_history (
                id, resource_id, status, status_code, response_time,
                redirect_url, last_modified, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            status_id, resource_id, result.status, result.status_code,
            result.response_time, result.redirect_url, result.last_modified,
            result.error_message
        ])
        
        # Add API check results if present
        if result.api_result:
            self._add_api_result(resource_id, result.timestamp, result.api_result)
    
    def _add_api_result(
        self,
        resource_id: str,
        timestamp: datetime,
        api_result: APICheckResult
    ):
        """Add API check results.
        
        Args:
            resource_id: Resource ID
            timestamp: Check timestamp
            api_result: API check result
        """
        if api_result.missing_fields:
            for field in api_result.missing_fields:
                field_id = str(uuid.uuid4())
                self.conn.execute("""
                    INSERT INTO api_field_history (
                        id, resource_id, timestamp, field_name,
                        status, error_message
                    )
                    VALUES (?, ?, ?, ?, 'missing', ?)
                """, [
                    field_id, resource_id, timestamp,
                    field, api_result.error_message
                ])
    
    def get_collection_resources(self, collection_id: str) -> List[Dict]:
        """Get all resources for a collection.
        
        Args:
            collection_id: Collection ID
            
        Returns:
            List of resources
        """
        result = self.conn.execute("""
            SELECT r.*
            FROM resources r
            JOIN collection_resources cr ON r.id = cr.resource_id
            WHERE cr.collection_id = ?
            ORDER BY cr.created_at
        """, [collection_id])
        return result.fetchall()
    
    def get_resource_history(
        self,
        resource_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get history for a specific resource.
        
        Args:
            resource_id: Resource ID
            limit: Optional limit on number of results
            
        Returns:
            List of history entries
        """
        query = """
            SELECT * FROM status_history
            WHERE resource_id = ?
            ORDER BY checked_at DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        
        result = self.conn.execute(query, [resource_id])
        return result.fetchall()
    
    def get_collection_by_name(self, name: str) -> Optional[Dict]:
        """Get collection by name.
        
        Args:
            name: Collection name
            
        Returns:
            Collection data or None if not found
        """
        result = self.conn.execute(
            "SELECT * FROM collections WHERE name = ?",
            [name]
        )
        row = result.fetchone()
        return dict(row) if row else None
    
    def get_collection_tags(self, collection_id: str) -> List[str]:
        """Get tags for a collection.
        
        Args:
            collection_id: Collection ID
            
        Returns:
            List of tag names
        """
        result = self.conn.execute("""
            SELECT tags
            FROM collections
            WHERE id = ?
        """, [collection_id])
        row = result.fetchone()
        return row[0] if row else []
