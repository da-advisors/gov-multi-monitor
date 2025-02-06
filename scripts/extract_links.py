#!/usr/bin/env python3
"""Script to extract links from URLs defined in config files."""

import sys
from pathlib import Path
import json
import requests
from bs4 import BeautifulSoup
import yaml
from urllib.parse import urljoin, urlparse
from multi_monitor.checker import URLChecker
from datetime import datetime
import logging
from dataclasses import dataclass
from typing import List, Optional

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class URLConfig:
    url: str
    name: str
    tags: List[str]
    linked_urls: Optional[List[dict]] = None

def load_url_config(config_file: Path) -> URLConfig:
    """Load URL config from YAML file."""
    with open(config_file, 'r') as f:
        data = yaml.safe_load(f)
    return URLConfig(
        url=data['url'],
        name=data['name'],
        tags=data.get('tags', []),
        linked_urls=data.get('linked_urls', [])
    )

def extract_links(html_content, base_url):
    """Extract all links from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []
    
    for a in soup.find_all('a', href=True):
        href = a.get('href')
        if href:
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            # Only include http(s) URLs
            if urlparse(absolute_url).scheme in ('http', 'https'):
                links.append({
                    'url': absolute_url,
                    'text': a.get_text(strip=True) or '[No text]',
                    'title': a.get('title', ''),
                })
    
    return links

def main():
    """Main function."""
    config_dir = Path('config/url_configs')
    if not config_dir.exists():
        logging.error(f"Directory {config_dir} does not exist")
        sys.exit(1)
    
    # Create timestamped output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path('extracted_links') / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Extracting links to: {output_dir}")
    
    # Initialize checker with our existing configuration
    checker = URLChecker()
    
    # Process all yaml files in config directory
    for config_file in config_dir.glob('*.yaml'):
        logging.info(f"Processing config file: {config_file}")
        
        try:
            # Load config
            url_config = load_url_config(config_file)
            logging.info(f"Processing URL: {url_config.url}")
            
            try:
                # Get the page content
                logging.info(f"  Fetching {url_config.url}...")
                response = checker.session.get(url_config.url, timeout=checker.timeout)
                response.raise_for_status()
                
                # Extract links
                logging.info("  Extracting links...")
                links = extract_links(response.text, url_config.url)
                
                # Use the config filename (without .yaml extension) for the output
                output_file = output_dir / f"{config_file.stem}.json"
                
                # Save links to JSON file
                with output_file.open('w') as f:
                    json.dump({
                        'source_yaml': config_file.name,
                        'source_url': url_config.url,
                        'name': url_config.name,
                        'timestamp': response.headers.get('date', ''),
                        'num_links': len(links),
                        'links': links,
                        'linked_urls': url_config.linked_urls
                    }, f, indent=2)
                
                logging.info(f"  ✓ Found {len(links)} links. Saved to {output_file}")
            
            except requests.exceptions.RequestException as e:
                logging.error(f"  ✗ Request failed for {url_config.url}: {str(e)}")
            except Exception as e:
                logging.error(f"  ✗ Error processing {url_config.url}: {str(e)}")
        
        except Exception as e:
            logging.error(f"Error processing config file {config_file}: {e}")

if __name__ == '__main__':
    main()
