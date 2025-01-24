"""Configuration for URL monitoring."""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
import logging

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

    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = []

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
        config_dir = Path(data.get('config_dir', path.parent / 'urls'))
        history_file = Path(data.get('history_file', 'data/history.parquet'))
        
        # Load URL configs
        urls = []
        for url_entry in data.get('urls', []):
            if 'config' in url_entry:
                # Load URL config from separate file
                config_file = config_dir / url_entry['config']
                try:
                    with open(config_file) as f:
                        url_data = yaml.safe_load(f)
                except (FileNotFoundError, yaml.YAMLError) as e:
                    logging.error(f"Error loading URL config {config_file}: {e}")
                    continue
            else:
                # URL config is inline
                url_data = url_entry
            
            # Convert API config if present
            api_data = url_data.get('api_config')
            api_config = None
            if api_data:
                api_config = APIConfig(
                    url=api_data['url'],
                    method=api_data.get('method', 'GET'),
                    params=api_data.get('params'),
                    headers=api_data.get('headers'),
                    expected_fields=api_data.get('expected_fields'),
                    date_field=api_data.get('date_field')
                )
            
            urls.append(URLConfig(
                url=url_data['url'],
                name=url_data.get('name'),
                expected_content=url_data.get('expected_content'),
                tags=url_data.get('tags', []),
                expected_update_frequency=url_data.get('expected_update_frequency'),
                api_config=api_config
            ))
        
        return cls(
            urls=urls,
            history_file=history_file,
            config_dir=config_dir,
            status_page_dir=Path(data.get('status_page_dir')) if data.get('status_page_dir') else None,
            bluesky_handle=data.get('bluesky_handle')
        )
