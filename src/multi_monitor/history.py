"""Manage history of URL checks."""
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone
from typing import List, Optional
import numpy as np

from .checker import CheckResult

class CheckHistory:
    """Maintain history of URL check results."""
    
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self._ensure_history_file()
    
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
        df = pd.read_parquet(self.history_file)
        schema = self._get_schema()
        
        # Convert timezone-aware datetimes to naive UTC
        timestamp = result.timestamp.astimezone(timezone.utc).replace(tzinfo=None) if result.timestamp.tzinfo else result.timestamp
        if result.last_modified and result.last_modified.tzinfo:
            last_modified = result.last_modified.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            last_modified = result.last_modified
        
        # Create new row with explicit dtypes
        new_data = {
            'url': result.url,
            'name': result.name,
            'timestamp': timestamp,
            'status': result.status,
            'status_code': result.status_code,
            'redirect_url': result.redirect_url if result.redirect_url else None,
            'last_modified': last_modified if last_modified else None,
            'error_message': result.error_message if result.error_message else None,
            'response_time': result.response_time if result.response_time else None
        }
        
        # Create DataFrame with same schema as existing
        new_row = pd.DataFrame([new_data])
        for col, dtype in schema.items():
            new_row[col] = new_row[col].astype(dtype)
        
        # Add linked URL results if any
        if result.linked_url_results:
            for linked in result.linked_url_results:
                linked_data = {
                    'url': linked.url,
                    'name': linked.name,
                    'timestamp': timestamp,
                    'status': linked.status,
                    'status_code': linked.status_code,
                    'redirect_url': linked.redirect_url if linked.redirect_url else None,
                    'last_modified': linked.last_modified if linked.last_modified else None,
                    'error_message': linked.error_message if linked.error_message else None,
                    'response_time': None  # Linked URLs don't track response time
                }
                linked_row = pd.DataFrame([linked_data])
                for col, dtype in schema.items():
                    linked_row[col] = linked_row[col].astype(dtype)
                new_row = pd.concat([new_row, linked_row], ignore_index=True)
        
        # Concatenate with existing data
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_parquet(self.history_file)
    
    def get_latest_results(self) -> pd.DataFrame:
        """Get the most recent result for each URL."""
        df = pd.read_parquet(self.history_file)
        if df.empty:
            return df
        
        return df.sort_values('timestamp').groupby('url').last().reset_index()
    
    def get_url_history(self, url: str, limit: Optional[int] = None) -> pd.DataFrame:
        """Get history for a specific URL."""
        df = pd.read_parquet(self.history_file)
        url_df = df[df['url'] == url].sort_values('timestamp', ascending=False)
        
        if limit:
            url_df = url_df.head(limit)
        
        return url_df
    
    def get_last_success(self, url: str) -> Optional[datetime]:
        """Get the last time a URL had a successful (200) response."""
        df = pd.read_parquet(self.history_file)
        success_df = df[(df['url'] == url) & (df['status_code'] == 200)].sort_values('timestamp', ascending=False)
        
        if not success_df.empty:
            return success_df.iloc[0]['timestamp'].to_pydatetime()
        return None
    
    def get_status_changes(self, since: datetime) -> pd.DataFrame:
        """Get URLs that have had status changes since given time."""
        df = pd.read_parquet(self.history_file)
        if df.empty:
            return pd.DataFrame()
        
        # Convert input time to naive UTC for comparison
        since_utc = since.astimezone(timezone.utc).replace(tzinfo=None) if since.tzinfo else since
        
        # Get status at 'since' time for each URL
        old_status = df[df['timestamp'] <= since_utc].sort_values('timestamp').groupby('url').last()
        current_status = df.sort_values('timestamp').groupby('url').last()
        
        # Find URLs where current status differs from old status
        changed = current_status[current_status['status'] != old_status['status']]
        
        return changed
