"""Manage history of URL checks."""
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone
from typing import List, Optional
import numpy as np
import uuid

from .checker import CheckResult
from .db import MonitorDB

class CheckHistory:
    """Maintain history of URL check results."""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.db = MonitorDB('data/monitor.db')
    
    def _get_schema(self):
        """Get DataFrame schema."""
        return {
            'url': 'string',
            'name': 'string',
            'timestamp': 'datetime64[ns]',
            'status': 'string',
            'status_code': pd.Int32Dtype(),
            'redirect_url': 'string',
            'last_modified': 'datetime64[ns]',
            'error_message': 'string',
            'response_time': 'float64'
        }
    
    def _ensure_history_file(self):
        """Create history file if it doesn't exist."""
        if not self.history_file.exists():
            schema = self._get_schema()
            df = pd.DataFrame({k: pd.Series(dtype=v) for k, v in schema.items()})
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(self.history_file)
    
    def add_result(self, result: CheckResult):
        """Add a new check result to history."""
        # First, ensure resource exists
        resource_id = None
        resources = self.db.conn.execute(
            'SELECT id FROM resources WHERE url = ?',
            (result.url,)
        ).fetchall()
        
        if resources:
            resource_id = resources[0][0]
        else:
            # Generate UUID first
            resource_id = str(uuid.uuid4())
            # Create resource
            self.db.add_resource(
                id=resource_id,  # Pass the ID explicitly
                name=result.name or result.url,
                type='url',
                url=result.url,
                metadata={}
            )
            print(f"Created resource with ID: {resource_id}")
        
        # Then add the status
        url_data = {
            'status_code': result.status_code,
            'response_time': result.response_time,
            'redirect_url': result.redirect_url,
            'last_modified': result.last_modified.isoformat() if result.last_modified else None,
            'content_hash': None,  # Not tracking content hash yet
            'content_length': result.content_length  # Add content length
        }
        
        status_id = self.db.add_resource_status(
            resource_id=resource_id,
            status=result.status,
            checked_at=result.timestamp,
            url_data=url_data,
            error_message=result.error_message,
            metadata={}
        )
        print(f"Added status {status_id} for resource {resource_id}")
        
        # Add linked URL results if any
        if result.linked_url_results:
            for linked in result.linked_url_results:
                linked_resource_id = None
                linked_resources = self.db.conn.execute(
                    'SELECT id FROM resources WHERE url = ?',
                    (linked.url,)
                ).fetchall()
                
                if linked_resources:
                    linked_resource_id = linked_resources[0][0]
                else:
                    # Generate UUID first
                    linked_resource_id = str(uuid.uuid4())
                    # Create linked resource
                    self.db.add_resource(
                        id=linked_resource_id,  # Pass the ID explicitly
                        name=linked.name or linked.url,
                        type='url',
                        url=linked.url,
                        metadata={'is_linked': True, 'parent_resource_id': resource_id}
                    )
                    print(f"Created linked resource with ID: {linked_resource_id}")
                
                linked_url_data = {
                    'status_code': linked.status_code,
                    'response_time': linked.response_time,
                    'redirect_url': linked.redirect_url,
                    'last_modified': linked.last_modified.isoformat() if linked.last_modified else None,
                    'content_hash': None,  # Not tracking content hash yet
                    'content_length': linked.content_length  # Add content length
                }
                
                linked_status_id = self.db.add_resource_status(
                    resource_id=linked_resource_id,
                    status=linked.status,
                    checked_at=result.timestamp,
                    url_data=linked_url_data,
                    error_message=linked.error_message,
                    metadata={'parent_status_id': status_id}
                )
                print(f"Added linked status {linked_status_id} for resource {linked_resource_id}")
    
    def get_latest_results(self) -> pd.DataFrame:
        """Get the most recent result for each URL."""
        results = self.db.conn.execute(
            'SELECT r.url, r.name, rs.checked_at, rs.status, rs.status_code, rs.redirect_url, rs.last_modified, rs.error_message, rs.response_time '
            'FROM resources r '
            'JOIN resource_statuses rs ON r.id = rs.resource_id '
            'WHERE rs.checked_at = ( '
            '    SELECT MAX(checked_at) '
            '    FROM resource_statuses '
            '    WHERE resource_id = r.id '
            ')'
        ).fetchall()
        
        if not results:
            return pd.DataFrame()
        
        data = {
            'url': [r[0] for r in results],
            'name': [r[1] for r in results],
            'timestamp': [r[2] for r in results],
            'status': [r[3] for r in results],
            'status_code': [r[4] for r in results],
            'redirect_url': [r[5] for r in results],
            'last_modified': [r[6] for r in results],
            'error_message': [r[7] for r in results],
            'response_time': [r[8] for r in results]
        }
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['last_modified'] = pd.to_datetime(df['last_modified'])
        
        return df
    
    def get_url_history(self, url: str, limit: Optional[int] = None) -> pd.DataFrame:
        """Get history for a specific URL."""
        results = self.db.conn.execute(
            'SELECT r.url, r.name, rs.checked_at, rs.status, rs.status_code, rs.redirect_url, rs.last_modified, rs.error_message, rs.response_time '
            'FROM resources r '
            'JOIN resource_statuses rs ON r.id = rs.resource_id '
            'WHERE r.url = ? '
            'ORDER BY rs.checked_at DESC',
            (url,)
        ).fetchall()
        
        if not results:
            return pd.DataFrame()
        
        data = {
            'url': [r[0] for r in results],
            'name': [r[1] for r in results],
            'timestamp': [r[2] for r in results],
            'status': [r[3] for r in results],
            'status_code': [r[4] for r in results],
            'redirect_url': [r[5] for r in results],
            'last_modified': [r[6] for r in results],
            'error_message': [r[7] for r in results],
            'response_time': [r[8] for r in results]
        }
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['last_modified'] = pd.to_datetime(df['last_modified'])
        
        if limit:
            df = df.head(limit)
        
        return df
    
    def get_last_success(self, url: str) -> Optional[datetime]:
        """Get the last time a URL had a successful (200) response."""
        result = self.db.conn.execute(
            'SELECT MAX(rs.checked_at) '
            'FROM resources r '
            'JOIN resource_statuses rs ON r.id = rs.resource_id '
            'WHERE r.url = ? AND rs.status_code = 200',
            (url,)
        ).fetchone()
        
        if result and result[0]:
            return result[0]
        return None
    
    def get_status_changes(self, since: datetime) -> pd.DataFrame:
        """Get URLs that have had status changes since given time."""
        results = self.db.conn.execute(
            'SELECT r.url, r.name, rs.checked_at, rs.status, rs.status_code, rs.redirect_url, rs.last_modified, rs.error_message, rs.response_time '
            'FROM resources r '
            'JOIN resource_statuses rs ON r.id = rs.resource_id '
            'WHERE rs.checked_at > ?',
            (since,)
        ).fetchall()
        
        if not results:
            return pd.DataFrame()
        
        data = {
            'url': [r[0] for r in results],
            'name': [r[1] for r in results],
            'timestamp': [r[2] for r in results],
            'status': [r[3] for r in results],
            'status_code': [r[4] for r in results],
            'redirect_url': [r[5] for r in results],
            'last_modified': [r[6] for r in results],
            'error_message': [r[7] for r in results],
            'response_time': [r[8] for r in results]
        }
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['last_modified'] = pd.to_datetime(df['last_modified'])
        
        return df
