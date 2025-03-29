#!/usr/bin/env python3
"""Script to migrate URL configurations from urls.yaml to individual files."""
import yaml
from pathlib import Path
import shutil
import logging

logging.basicConfig(level=logging.INFO)


def migrate_configs():
    """Migrate configurations from urls.yaml to individual files."""
    # Load urls.yaml
    config_dir = Path(__file__).parent.parent / "config"
    urls_yaml = config_dir / "urls.yaml"
    with open(urls_yaml) as f:
        data = yaml.safe_load(f)

    # Create backup of url_configs if it exists
    url_configs_dir = config_dir / "url_configs"
    if url_configs_dir.exists():
        backup_dir = url_configs_dir.with_name("url_configs_backup")
        shutil.move(str(url_configs_dir), str(backup_dir))
        logging.info(f"Backed up existing url_configs to {backup_dir}")

    # Create url_configs directory
    url_configs_dir.mkdir(exist_ok=True)

    # Write each URL config to its own file
    for i, url_config in enumerate(data["urls"], 1):
        # Extract name for filename
        name = url_config.get("name", "").lower()
        if not name:
            name = url_config["url"].split("/")[-1]
        name = name.replace(" ", "_").replace("(", "").replace(")", "")
        filename = f"{i:03d}_{name}.yaml"

        # Write config to file
        output_file = url_configs_dir / filename
        with open(output_file, "w") as f:
            yaml.dump(url_config, f, sort_keys=False, allow_unicode=True)
        logging.info(f"Created {filename}")

    # Create new monitor_config.yaml
    monitor_config = {
        "history_file": data.get("history_file", "data/history.parquet"),
        "status_page_dir": data.get("status_page_dir"),
        "active_configs": None,  # Set to None to load all configs, or list specific ones to load
    }

    with open(config_dir / "monitor_config.yaml", "w") as f:
        yaml.dump(monitor_config, f, sort_keys=False)
    logging.info("Created monitor_config.yaml")


if __name__ == "__main__":
    migrate_configs()
