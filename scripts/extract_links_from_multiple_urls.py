#!/usr/bin/env python3
"""Script to extract links from multiple URLs and save in a single JSON file."""

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
            absolute_url = urljoin(base_url, href)
            if urlparse(absolute_url).scheme in ('http', 'https'):
                links.append({
                    'url': absolute_url,
                    'text': a.get_text(strip=True) or '[No text]',
                    'title': a.get('title', ''),
                })

    return links

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Extract links from multiple URLs and save to JSON')
    parser.add_argument('urls', nargs='+', help='One or more URLs to extract links from')
    parser.add_argument('output', help='Output JSON file path')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    args = parser.parse_args()

    combined_results = []

    for url in args.urls:
        try:
            # Get the page content
            logging.info(f"Fetching {url}...")
            response = requests.get(url, timeout=args.timeout)
            response.raise_for_status()

            # Extract links
            logging.info(f"Extracting links from {url}...")
            links = extract_links(response.text, url)

            # Save links to JSON file
            result = {
                'source_url': url,
                'timestamp': response.headers.get('date', datetime.now().isoformat()),
                'num_links': len(links),
                'links': links
            }

            combined_results.append(result)
            logging.info(f"✓ Found {len(links)} links from {url}")

        except requests.exceptions.RequestException as e:
            logging.error(f"✗ Request failed for {url}: {str(e)}")
        except Exception as e:
            logging.error(f"✗ Error processing {url}: {str(e)}")

    # Save all collected results to JSON
    with open(args.output, 'w') as f:
        json.dump(combined_results, f, indent=2)

    logging.info(f"✓ Saved all results to {args.output}")

if __name__ == '__main__':
    main()

# python scripts/extract_links_from_multiple_urls.py "x" "y" "z" extracted_links/sentinel_pulls/number/number_name.json
