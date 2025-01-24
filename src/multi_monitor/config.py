"""Configuration management for multi-monitor."""
from pathlib import Path
import yaml
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class URLConfig:
    """Configuration for a single URL to monitor."""
    url: str
    check_frequency: timedelta
    name: Optional[str] = None
    tags: List[str] = None
    expected_content: Optional[str] = None  # String that should appear in valid content
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.name is None:
            # Use domain as default name
            from urllib.parse import urlparse
            self.name = urlparse(self.url).netloc

@dataclass
class MonitorConfig:
    """Overall configuration for the monitoring system."""
    urls: List[URLConfig]
    history_file: Path
    status_page_dir: Optional[Path] = None  # For GitHub Pages
    bluesky_handle: Optional[str] = None
    
    @classmethod
    def from_yaml(cls, config_path: Path) -> 'MonitorConfig':
        """Load configuration from YAML file."""
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        # Convert frequency strings to timedelta
        for url in data['urls']:
            freq = url['check_frequency']
            if isinstance(freq, str):
                # Parse strings like "1d", "4h", "30m"
                unit = freq[-1]
                value = int(freq[:-1])
                if unit == 'd':
                    url['check_frequency'] = timedelta(days=value)
                elif unit == 'h':
                    url['check_frequency'] = timedelta(hours=value)
                elif unit == 'm':
                    url['check_frequency'] = timedelta(minutes=value)
            
            # Create URLConfig objects
            url['tags'] = url.get('tags', [])
            url_configs = [URLConfig(**url) for url in data['urls']]
        
        return cls(
            urls=url_configs,
            history_file=Path(data['history_file']),
            status_page_dir=Path(data['status_page_dir']) if data.get('status_page_dir') else None,
            bluesky_handle=data.get('bluesky_handle')
        )
