"""Command-line interface for multi-monitor."""

from typing import Optional
import click
import logging
from pathlib import Path
from rich.console import Console
import sys

from americas_essential_data import web
from americas_essential_data.resource_monitor.config import MonitorConfig
from .check_urls import check_urls
from .generate_multipage_status_report import generate_multipage_status_report
from .generate_single_status_page import generate_single_status_page

console = Console()


@click.group()
def cli():
    """Helpful commands related to America's Essential Data."""
    pass


@cli.command()
@click.option("--debug", is_flag=True, help="Enable debug mode")
def web(debug: bool = False):
    """Start the web application server."""
    webapp = web.create_webapp()
    webapp.run(debug=debug)


@cli.command()
@click.option(
    "--config", default="config/monitor_config.yaml", help="Path to config file"
)
@click.option("--url", help="Check only this URL")
@click.option("--verbose", is_flag=True, help="Show detailed output")
def check(config: str, url: Optional[str] = None, verbose: bool = False):
    """Check URLs and record their status."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        monitor_config = MonitorConfig.from_yaml(Path(config))
        table = check_urls(monitor_config, url, verbose, console)

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--config", default="config/monitor_config.yaml", help="Path to config file"
)
@click.option("--output", default="docs/index.html", help="Output HTML file")
@click.option("--template", default=None, help="Custom template file")
def generate_page(config: str, output: str, template: Optional[str] = None):
    """Generate a single status page."""
    try:
        monitor_config = MonitorConfig.from_yaml(Path(config))
        output_path = Path(output)

        if template is None:
            template_path = (
                Path(__file__).parent / "templates" / "single_status_page.html.jinja"
            )
        else:
            template_path = Path(template)

        generate_single_status_page(monitor_config, output_path, template_path)

        console.print(f"Status page generated: {output_path}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--config", default="config/monitor_config.yaml", help="Path to config file"
)
@click.option(
    "--output-dir", default="docs/status", help="Output directory for HTML files"
)
def generate_multi_page(config: str, output_dir: str):
    """Generate a multi-page status report."""
    try:
        monitor_config = MonitorConfig.from_yaml(Path(config))
        output_path = Path(output_dir)

        generate_multipage_status_report(monitor_config, output_path)

        console.print(f"Multi-page status report generated in: {output_path}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
