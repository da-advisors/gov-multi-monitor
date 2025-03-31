#!/usr/bin/env python3
"""Script to deduplicate links across multiple JSON files."""

import json
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    """Main function."""
    # Directory containing the JSON files
    input_dir = Path("extracted_links/targeted_pulls/household_pulse_puf")

    # Dictionary to store unique URLs and their first occurrence
    unique_links = {}
    source_files = []

    # Process each JSON file
    for json_file in input_dir.glob("*.json"):
        logging.info(f"Processing {json_file.name}")
        source_files.append(json_file.name)

        with open(json_file) as f:
            data = json.load(f)

            for link in data["links"]:
                url = link["url"]
                if url not in unique_links:
                    unique_links[url] = link

    # Create output with deduplicated links
    output = {
        "source_files": source_files,
        "num_unique_links": len(unique_links),
        "links": list(unique_links.values()),
    }

    # Save to a new file
    output_file = input_dir / "deduplicated_links.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    logging.info(
        f"Found {len(unique_links)} unique links across {len(source_files)} files"
    )
    logging.info(f"Saved deduplicated links to {output_file}")


if __name__ == "__main__":
    main()
