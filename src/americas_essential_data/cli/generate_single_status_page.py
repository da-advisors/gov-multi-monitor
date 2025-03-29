from datetime import datetime
import logging
from pathlib import Path
from typing import Optional

import jinja2

from americas_essential_data.resource_monitor.check_history import CheckHistory
from americas_essential_data.resource_monitor.config import MonitorConfig
from americas_essential_data.resource_monitor.url_checker import URLChecker


def generate_single_status_page(
    config: MonitorConfig, output_path: Path, template_path: Path
):
    # Initialize checker and history
    checker = URLChecker()
    history = CheckHistory(config.history_file)

    # Get results for all URLs
    results = []
    all_tags = set()  # Keep track of all unique tags
    for url_config in config.urls:
        result = checker.check_url(url_config)
        result.tags = url_config.tags  # Add tags to result for display
        result.archived_content = (
            url_config.archived_content
        )  # Add archived content links
        if url_config.tags:  # Add tags to our set if they exist
            all_tags.update(url_config.tags)

        # Add last successful check date for each linked URL
        if result.linked_url_results:
            for linked_result in result.linked_url_results:
                linked_result.last_success = history.get_last_success(linked_result.url)

        results.append(result)
        history.add_result(result)

    # Sort tags alphabetically for consistent display
    sorted_tags = sorted(all_tags)

    # Load template
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_path.parent),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_path.name)

    # Generate HTML
    for result in results:
        if result.api_result:
            logging.debug(f"API Result for {result.name}: {result.api_result}")
        if result.linked_url_results:
            logging.debug(f"Linked URLs for {result.name}: {result.linked_url_results}")

    html = template.render(
        timestamp=datetime.now(),
        results=results,
        tags=sorted_tags,  # Pass sorted tags to template
    )

    # Write output
    output_path.write_text(html)
