#!/usr/bin/env python3
"""Script to fix YAML indentation in config files."""
import yaml
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)


class IndentedDumper(yaml.Dumper):
    def increase_indent(self, flow=False, *args, **kwargs):
        return super().increase_indent(flow=flow, indentless=False)


def fix_yaml_files():
    """Fix indentation in all YAML files."""
    config_dir = Path(__file__).parent.parent / "config"
    url_configs_dir = config_dir / "url_configs"

    # Fix monitor_config.yaml
    monitor_config = config_dir / "monitor_config.yaml"
    if monitor_config.exists():
        fix_yaml_file(monitor_config)

    # Fix all URL config files
    for yaml_file in url_configs_dir.glob("*.yaml"):
        fix_yaml_file(yaml_file)


def represent_list(dumper, data):
    """Custom representer for lists to ensure proper indentation."""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=False)


def fix_yaml_file(file_path: Path):
    """Fix indentation in a single YAML file."""
    try:
        # Read and parse YAML
        with open(file_path) as f:
            data = yaml.safe_load(f)

        # Add custom list representation
        yaml.add_representer(list, represent_list)

        # Write back with consistent indentation
        with open(file_path, "w") as f:
            yaml.dump(
                data,
                f,
                Dumper=IndentedDumper,
                sort_keys=False,
                indent=2,
                default_flow_style=False,
                allow_unicode=True,
            )

        logging.info(f"Fixed indentation in {file_path}")
    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")


if __name__ == "__main__":
    fix_yaml_files()
