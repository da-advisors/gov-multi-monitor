#!/usr/bin/env python3
"""Extract links from multiple URLs and output to JSON and custom YAML.

If --yaml is omitted, YAML filename is auto-created from JSON filename.
Automatically creates any missing directories in output paths.
"""

import sys
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import argparse
from datetime import datetime
import logging
import re
import html
import os

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

def escape_yaml_string(s):
    """Escape YAML-sensitive characters."""
    s = html.unescape(s)
    if re.search(r'[:\-\[\]{}#&*!|>\'"]', s):
        return f'"{s}"'
    return s

def main():
    parser = argparse.ArgumentParser(description='Extract and export links from URLs to JSON and custom YAML.')
    parser.add_argument('urls', nargs='+', help='One or more URLs to extract links from')
    parser.add_argument('--json', required=True, help='Output JSON file path')
    parser.add_argument('--yaml', help='Output YAML file path (optional). If omitted, will use JSON filename with .yaml extension')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    args = parser.parse_args()

    # Auto-generate YAML filename if not provided
    if not args.yaml:
        if args.json.lower().endswith('.json'):
            args.yaml = args.json[:-5] + '.yaml'
        else:
            args.yaml = args.json + '.yaml'
    logging.info(f"Using YAML output file: {args.yaml}")

    all_data_for_json = []
    yaml_sections = []

    source_urls = args.urls

    for url in source_urls:
        try:
            logging.info(f"Fetching {url}...")
            response = requests.get(url, timeout=args.timeout)
            response.raise_for_status()

            logging.info(f"Extracting links from {url}...")
            links = extract_links(response.text, url)

            # Deduplicate links while preserving all unique text values
            deduped = {}
            for link in links:
                link_url = link['url']
                link_text = link.get('text', '').strip()

                if link_url in deduped:
                    if link_text not in deduped[link_url]:
                        deduped[link_url].append(link_text)
                else:
                    deduped[link_url] = [link_text]

            grouped_links = []
            for link_url, names in deduped.items():
                for name in names:
                    grouped_links.append({
                        'url': link_url,
                        'name': name,
                        'resource_type': '',
                        'key_resource': ''
                    })

            # Save for JSON output
            all_data_for_json.append({
                'source_url': url,
                # 'timestamp': response.headers.get('date', datetime.now().isoformat()),
                'links': grouped_links
            })

            # Build YAML section for this URL
            section = f"{url}\nlinked_urls:\n"
            for link in grouped_links:
                section += f"  - url: {escape_yaml_string(link['url'])}\n"
                section += f"    name: {escape_yaml_string(link['name'])}\n"
                section += f"    resource_type: \n"
                section += f"    key_resource: \n"
            yaml_sections.append(section)

            logging.info(f"✓ Found {len(grouped_links)} unique links from {url}")

        except requests.exceptions.RequestException as e:
            logging.error(f"✗ Request failed for {url}: {str(e)}")
        except Exception as e:
            logging.error(f"✗ Error processing {url}: {str(e)}")

    # Ensure output directories exist
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    os.makedirs(os.path.dirname(args.yaml), exist_ok=True)

    # JSON output
    json_output = {
        "source_urls": source_urls,
        "data": all_data_for_json
    }
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2)
    logging.info(f"✓ Saved full JSON to {args.json}")

    # YAML output
    yaml_header = "\n".join(source_urls) + "\n\n"
    with open(args.yaml, 'w', encoding='utf-8') as f:
        f.write(yaml_header)
        f.write("\n\n".join(yaml_sections))
    logging.info(f"✓ Saved custom YAML to {args.yaml}")

if __name__ == '__main__':
    main()

# python scripts/scrape_and_clean_links_from_multiple_urls.py "url1" "url2" "url3" --json extracted_links/sentinel_pulls/number/number_name.json
# python scripts/scrape_and_clean_links_from_multiple_urls.py "url1" "url2" "url3" --json extracted_links/sentinel_pulls/number/number_name.json --yaml extracted_links/sentinel_pulls/number/number_name.yaml

# \[.*?\] regex for cleaning up names

# python scripts/scrape_and_clean_links_from_multiple_urls.py \
# "url" \
# "url" \
# "url" \
# --json extracted_links/sentinel_pulls/num/num_name.json

