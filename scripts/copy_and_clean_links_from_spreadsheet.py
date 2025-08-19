#!/usr/bin/env python3
"""Read a Google Sheet tab, save CSV and custom YAML in extracted_links/sentinel_pulls/{tab_name}."""

import argparse
import csv
import html
import logging
import os
import re
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def escape_yaml_string(s):
    """Escape YAML-sensitive characters."""
    s = html.unescape(str(s))
    if re.search(r'[:\-\[\]{}#&*!|>\'"]', s):
        return f'"{s}"'
    return s


def fetch_google_sheet_csv(sheet_url, tab_name):
    """
    Fetch CSV export of a Google Sheet tab.
    sheet_url: the Google Sheet "edit" URL (e.g., https://docs.google.com/spreadsheets/d/FILE_ID/edit)
    tab_name: name of the tab to fetch
    """
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        raise ValueError("Invalid Google Sheet URL")
    file_id = match.group(1)

    csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/gviz/tq?tqx=out:csv&sheet={tab_name}"
    logging.info(f"Fetching CSV for tab '{tab_name}' from {csv_url}")
    response = requests.get(csv_url)
    response.raise_for_status()
    return response.text


def save_csv_and_yaml(csv_content, tab_name, sheet_url):
    """Save CSV and YAML in extracted_links/sentinel_pulls/{tab_name} with YAML header."""
    base_folder = os.path.join("extracted_links", "sentinel_pulls", tab_name)
    os.makedirs(base_folder, exist_ok=True)

    csv_path = os.path.join(base_folder, f"{tab_name}.csv")
    yaml_path = os.path.join(base_folder, f"{tab_name}.yaml")

    # Save CSV (overwrites if exists)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write(csv_content)
    logging.info(f"✓ Saved CSV to {csv_path}")

    # Parse CSV and build YAML in desired format
    rows = list(csv.DictReader(csv_content.splitlines()))
    yaml_lines = []

    # Add header with sheet URL and tab name
    yaml_lines.append(f"sheet_url: \"{sheet_url}\"")
    yaml_lines.append(f"tab_name: \"{tab_name}\"\n")

    for row in rows:
        yaml_lines.append(f"  - url: {escape_yaml_string(row.get('url', ''))}")
        yaml_lines.append(f"    name: {escape_yaml_string(row.get('name', ''))}")
        yaml_lines.append(f"    resource_type: {escape_yaml_string(row.get('resource_type', ''))}")
        yaml_lines.append(f"    key_resource: {escape_yaml_string(row.get('key_resource', ''))}")

    # Save YAML (overwrites if exists)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
    logging.info(f"✓ Saved YAML to {yaml_path}")


def main():
    parser = argparse.ArgumentParser(description="Fetch a Google Sheet tab and save CSV and YAML locally")
    parser.add_argument("sheet_url", help="Google Sheet URL")
    parser.add_argument("tab_name", help="Tab name to fetch")
    args = parser.parse_args()

    csv_content = fetch_google_sheet_csv(args.sheet_url, args.tab_name)
    save_csv_and_yaml(csv_content, args.tab_name, args.sheet_url)


if __name__ == "__main__":
    main()

# python scripts/copy_and_clean_links_from_spreadsheet.py "url" "tab name"

# python scripts/copy_and_clean_links_from_spreadsheet.py "https://docs.google.com/spreadsheets/d/1cWsUQB8rdpaigqU2DRQXsgBlAJUyRWg2Idhe36Eahhc/edit?usp=sharing" "127"
