"""Configuration for URL monitoring."""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
import logging

@dataclass
class ArchivedContent:
    """Configuration for an archived version of content."""
    url: str
    name: Optional[str] = None
    date: Optional[str] = None

@dataclass
class LinkedURL:
    """Configuration for a linked URL to monitor."""
    url: str
    name: str
    description: Optional[str] = None
    type: Optional[str] = None  # e.g. pdf, excel, csv
    expected_update_frequency: Optional[str] = None
    archived_content: List[ArchivedContent] = None  # List of archived versions of the content
    status: Optional[str] = None
    status_code: Optional[int] = None
    redirect_url: Optional[str] = None
    last_modified: Optional[str] = None
    error_message: Optional[str] = None
    content_length: Optional[int] = None
    response_time: Optional[float] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.archived_content is None:
            self.archived_content = []

@dataclass
class APIConfig:
    """Configuration for checking an associated API."""
    url: str
    method: str = "GET"
    params: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    expected_fields: Optional[List[str]] = None
    date_field: Optional[str] = None  # Field to check for most recent update

@dataclass
class URLConfig:
    """Configuration for a single URL to monitor."""
    url: str
    name: Optional[str] = None
    expected_content: Optional[str] = None
    tags: List[str] = None
    expected_update_frequency: Optional[str] = None  # e.g. "daily", "weekly", "monthly", "quarterly", "yearly"
    api_config: Optional[APIConfig] = None
    linked_urls: List[LinkedURL] = None
    archived_content: List[ArchivedContent] = None  # List of archived versions of the content

    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
        if self.linked_urls is None:
            self.linked_urls = []
        if self.archived_content is None:
            self.archived_content = []
        # Convert string URLs to ArchivedContent objects for backward compatibility
        if self.archived_content and isinstance(self.archived_content[0], str):
            self.archived_content = [ArchivedContent(url=url) for url in self.archived_content]

@dataclass
class MonitorConfig:
    """Overall configuration for URL monitoring."""
    urls: List[URLConfig]
    history_file: Path = Path('data/history.parquet')
    config_dir: Optional[Path] = None
    status_page_dir: Optional[Path] = None  # For GitHub Pages
    bluesky_handle: Optional[str] = None
    
    @classmethod
    def from_yaml(cls, path: Path) -> 'MonitorConfig':
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        
        # Get config directory and history file
        history_file = Path(data.get('history_file', 'data/history.parquet'))
        status_page_dir = data.get('status_page_dir')
        bluesky_handle = data.get('bluesky_handle')

        # Load URLs either from individual files or from urls list
        urls = []
        if 'urls' in data:
            # Load from single file
            for url_data in data['urls']:
                if 'api_config' in url_data:
                    url_data['api_config'] = APIConfig(**url_data['api_config'])
                if 'linked_urls' in url_data:
                    url_data['linked_urls'] = [LinkedURL(**linked_url_data) for linked_url_data in url_data['linked_urls']]
                if 'archived_content' in url_data:
                    url_data['archived_content'] = [ArchivedContent(**archived_content_data) for archived_content_data in url_data['archived_content']]
                urls.append(URLConfig(**url_data))
        else:
            # Load from individual files in url_configs directory
            url_configs_dir = path.parent / 'url_configs'
            if url_configs_dir.exists():
                # Get list of active configs if specified
                active_configs = data.get('active_configs')
                
                for config_file in sorted(url_configs_dir.glob('*.yaml')):
                    # Skip if not in active_configs (if specified)
                    if active_configs is not None and config_file.stem not in active_configs:
                        continue
                        
                    try:
                        with open(config_file) as f:
                            url_data = yaml.safe_load(f)
                            if 'api_config' in url_data:
                                url_data['api_config'] = APIConfig(**url_data['api_config'])
                            if 'linked_urls' in url_data:
                                url_data['linked_urls'] = [LinkedURL(**linked_url_data) for linked_url_data in url_data['linked_urls']]
                            if 'archived_content' in url_data:
                                url_data['archived_content'] = [ArchivedContent(**archived_content_data) for archived_content_data in url_data['archived_content']]
                            urls.append(URLConfig(**url_data))
                    except Exception as e:
                        logging.error(f"Error loading {config_file}: {e}")
                        continue

        return cls(
            urls=urls,
            history_file=history_file,
            status_page_dir=Path(status_page_dir) if status_page_dir else None,
            bluesky_handle=bluesky_handle
        )
