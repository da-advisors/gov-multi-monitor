"""Command-line interface for multi-monitor."""
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from datetime import datetime
import sys
import logging

from .config import MonitorConfig
from .checker import URLChecker
from .history import CheckHistory

console = Console()

@click.group()
def cli():
    """Monitor URLs for availability and updates."""
    pass

@cli.command()
@click.option('--config', default='config/urls.yaml', help='Path to config file')
@click.option('--url', help='Check only this URL')
@click.option('--verbose', is_flag=True, help='Show detailed output')
def check(config: str, url: str = None, verbose: bool = False):
    """Check URLs and record their status."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        config_path = Path(config)
        cfg = MonitorConfig.from_yaml(config_path)
        
        # Initialize checker and history
        checker = URLChecker()
        history = CheckHistory(cfg.history_file)
        
        # Create results table
        table = Table(title="URL Check Results")
        table.add_column("Name")
        table.add_column("URL")
        table.add_column("Status")
        table.add_column("Response Time", justify="right")
        table.add_column("Last Modified")
        table.add_column("Details")
        
        # Filter URLs if specific one requested
        urls = [u for u in cfg.urls if not url or u.url == url]
        
        with console.status("[bold green]Checking URLs..."):
            for url_config in urls:
                result = checker.check_url(url_config)
                history.add_result(result)
                
                # Add row to table
                status_color = {
                    'ok': 'green',
                    'redirect': 'yellow',
                    '404': 'red',
                    'error': 'red'
                }.get(result.status, 'white')
                
                details = []
                if result.redirect_url:
                    details.append(f"→ {result.redirect_url}")
                if result.error_message:
                    details.append(result.error_message)
                if result.status_code:
                    details.append(f"HTTP {result.status_code}")
                
                table.add_row(
                    url_config.name or url_config.url,
                    result.url,
                    f"[{status_color}]{result.status}[/{status_color}]",
                    f"{result.response_time:.2f}s" if result.response_time else "-",
                    result.last_modified.strftime("%Y-%m-%d %H:%M:%S") if result.last_modified else "-",
                    "\n".join(details)
                )
                
                # Show headers if verbose and there was an error
                if verbose and (result.status in ['404', 'error']):
                    console.print(Panel(
                        "\n".join([f"{k}: {v}" for k, v in (result.raw_headers or {}).items()]),
                        title=f"Response Headers for {url_config.name or url_config.url}",
                        title_align="left"
                    ))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        if verbose:
            import traceback
            console.print(Panel(traceback.format_exc(), title="Traceback"))
        sys.exit(1)

if __name__ == "__main__":
    cli()
