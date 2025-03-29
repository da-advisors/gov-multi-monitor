from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import jinja2

from americas_essential_data.resource_monitor.check_history import CheckHistory
from americas_essential_data.resource_monitor.config import MonitorConfig, URLConfig
from americas_essential_data.resource_monitor.url_checker import URLChecker


def generate_multipage_status_report(
    config: MonitorConfig,
    output_path: Path,
    *,
    on_begin_check_url: Optional[Callable[[URLConfig], None]],
):
    # Initialize checker and history
    checker = URLChecker()
    history = CheckHistory(config.history_file)

    # Create output directory structure
    details_path = output_path / "details"
    details_path.mkdir(parents=True, exist_ok=True)

    # Get results for all URLs
    results = []
    all_tags = set()
    for url_config in config.urls:
        if on_begin_check_url is not None:
            on_begin_check_url(url_config)

        result = checker.check_url(url_config)
        result.name = url_config.name or url_config.url  # Ensure we have a name
        result.tags = url_config.tags
        result.archived_content = url_config.archived_content

        if url_config.tags:
            all_tags.update(url_config.tags)

        # Add last successful check date for each linked URL
        if result.linked_url_results:
            for linked_result in result.linked_url_results:
                linked_result.last_success = history.get_last_success(linked_result.url)

        results.append(result)
        history.add_result(result)

    # Sort tags alphabetically
    sorted_tags = sorted(all_tags)

    # Load templates
    template_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )

    # Generate index page
    index_template = env.get_template("index.html.jinja")
    index_html = index_template.render(
        timestamp=datetime.now(), results=results, tags=sorted_tags
    )
    (output_path / "index.html").write_text(index_html)

    # Generate detail pages
    detail_template = env.get_template("detail.html.jinja")
    for result in results:
        # Create a safe filename from the result name
        safe_name = result.name.lower().replace(" ", "_")
        detail_html = detail_template.render(timestamp=datetime.now(), result=result)
        (details_path / f"{safe_name}.html").write_text(detail_html)
