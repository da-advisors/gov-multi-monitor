#!/usr/bin/env python3
"""Script to extract links from a single URL."""

import sys
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import argparse
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    parser = argparse.ArgumentParser(description='Extract links from a URL and save to JSON')
    parser.add_argument('url', help='URL to extract links from')
    parser.add_argument('output', help='Output JSON file path')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    args = parser.parse_args()
    
    try:
        # Get the page content
        logging.info(f"Fetching {args.url}...")
        response = requests.get(args.url, timeout=args.timeout)
        response.raise_for_status()
        
        # Extract links
        logging.info("Extracting links...")
        links = extract_links(response.text, args.url)
        
        # Save links to JSON file
        result = {
            'source_url': args.url,
            'timestamp': response.headers.get('date', datetime.now().isoformat()),
            'num_links': len(links),
            'links': links
        }
        
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        
        logging.info(f"✓ Found {len(links)} links. Saved to {args.output}")
    
    except requests.exceptions.RequestException as e:
        logging.error(f"✗ Request failed: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"✗ Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
