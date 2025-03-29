from typing import Optional
from rich.table import Table
from rich.console import Console

from americas_essential_data.resource_monitor.check_history import CheckHistory
from americas_essential_data.resource_monitor.url_checker import URLChecker
from americas_essential_data.resource_monitor.config import MonitorConfig


def check_urls(config: MonitorConfig, url: Optional[str], verbose: bool = False, console: Optional[Console] = None):
    """Check URLs and record their status."""

    # Initialize checker and history
    url_checker = URLChecker()
    check_history = CheckHistory(config.history_file)

    # Use provided console or create a new one if not provided
    if console is None:
        console = Console()

    # Create main results table
    table = Table(title="URL Check Results")
    table.add_column("Name")
    table.add_column("URL")
    table.add_column("Status")
    table.add_column("Expected Updates")
    table.add_column("Last Modified")
    table.add_column("API Status", justify="right")
    table.add_column("Linked URLs", justify="right")
    table.add_column("Details")

    # Filter URLs if specific one requested
    urls = [u for u in config.urls if not url or u.url == url]

    for url_config in urls:
        if verbose:
            console.print(f"Checking [bold]{url_config.name or url_config.url}[/bold]...")
        
        result = url_checker.check_url(url_config)
        check_history.add_result(result)

        # Format API status
        api_status = "-"
        if result.api_result:
            if result.api_result.status == "ok":
                api_status = "✓"
                if result.api_result.last_update:
                    api_status += (
                        f" ({result.api_result.last_update.strftime('%Y-%m-%d')})"
                    )
            else:
                api_status = f"✗ ({result.api_result.error_message})"

        # Format linked URLs status
        linked_status = "-"
        if result.linked_url_results:
            ok_count = sum(1 for r in result.linked_url_results if r.status == "ok")
            total = len(result.linked_url_results)
            linked_status = f"{ok_count}/{total} OK"

        # Format status with color and proper text
        status_style = {
            "ok": "green",
            "error": "red",
            "redirect": "yellow",
            "content_stripped": "red",
        }

        status_text = result.status
        if status_text == "content_stripped":
            status_text = "Content Stripped"

        table.add_row(
            url_config.name or url_config.url,
            result.url,
            f"[{status_style.get(result.status, 'white')}]{status_text}[/{status_style.get(result.status, 'white')}]",
            result.expected_update_frequency or "-",
            (
                result.last_modified.strftime("%Y-%m-%d %H:%M:%S")
                if result.last_modified
                else "-"
            ),
            api_status,
            linked_status,
            result.error_message or result.redirect_url or "-",
        )

        # If there are linked URLs and they have issues, show details
        if result.linked_url_results and any(
            r.status != "ok" for r in result.linked_url_results
        ):
            linked_table = Table(show_header=False, box=None, padding=(0, 4))
            for linked_result in result.linked_url_results:
                if linked_result.status != "ok":
                    status_color = (
                        "red" if linked_result.status == "error" else "yellow"
                    )
                    # Show name and status
                    linked_table.add_row(
                        "",
                        f"[{status_color}]→ {linked_result.name}[/{status_color}]",
                    )
                    # Show URL and error if present
                    error_text = (
                        f" - {linked_result.error_message}"
                        if linked_result.error_message
                        else ""
                    )
                    linked_table.add_row(
                        "", f"  [dim]{linked_result.url}{error_text}[/dim]"
                    )
            table.add_row("", linked_table, "", "", "", "", "", "")

    return table
