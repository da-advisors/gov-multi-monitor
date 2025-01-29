"""Command-line interface for multi-monitor."""
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from datetime import datetime
import sys
import logging
import jinja2
import pandas as pd

from .config import MonitorConfig
from .checker import URLChecker
from .history import CheckHistory

console = Console()

@click.group()
def cli():
    """Monitor URLs for availability and updates."""
    pass

@cli.command()
@click.option('--config', default='config/monitor_config.yaml', help='Path to config file')
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
        urls = [u for u in cfg.urls if not url or u.url == url]
        
        for url_config in urls:
            result = checker.check_url(url_config)
            history.add_result(result)
            
            # Format API status
            api_status = "-"
            if result.api_result:
                if result.api_result.status == 'ok':
                    api_status = "✓"
                    if result.api_result.last_update:
                        api_status += f" ({result.api_result.last_update.strftime('%Y-%m-%d')})"
                else:
                    api_status = f"✗ ({result.api_result.error_message})"
            
            # Format linked URLs status
            linked_status = "-"
            if result.linked_url_results:
                ok_count = sum(1 for r in result.linked_url_results if r.status == 'ok')
                total = len(result.linked_url_results)
                linked_status = f"{ok_count}/{total} OK"
            
            # Add row to results table
            table.add_row(
                url_config.name or url_config.url,
                result.url,
                result.status,
                result.expected_update_frequency or "-",
                result.last_modified.strftime("%Y-%m-%d %H:%M:%S") if result.last_modified else "-",
                api_status,
                linked_status,
                result.error_message or result.redirect_url or "-"
            )
            
            # If there are linked URLs and they have issues, show details
            if result.linked_url_results and any(r.status != 'ok' for r in result.linked_url_results):
                linked_table = Table(show_header=False, box=None, padding=(0, 4))
                for linked_result in result.linked_url_results:
                    if linked_result.status != 'ok':
                        status_color = 'red' if linked_result.status == 'error' else 'yellow'
                        # Show name and status
                        linked_table.add_row(
                            "",
                            f"[{status_color}]→ {linked_result.name}[/{status_color}]"
                        )
                        # Show URL
                        linked_table.add_row(
                            "",
                            f"  [dim]{linked_result.url}[/dim]"
                        )
                        # Show error and last success
                        last_success = history.get_last_success(linked_result.url)
                        error_msg = linked_result.error_message or linked_result.status
                        if last_success:
                            error_msg += f" (Last successful: {last_success.strftime('%Y-%m-%d')})"
                        linked_table.add_row(
                            "",
                            f"  [{status_color}]{error_msg}[/{status_color}]"
                        )
                table.add_row("", linked_table, "", "", "", "", "", "")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

@cli.command()
@click.option('--config', default='config/monitor_config.yaml', help='Path to config file')
@click.option('--output', default='docs/index.html', help='Output HTML file')
@click.option('--template', default=None, help='Custom template file')
def generate_page(config: str, output: str, template: str = None):
    """Generate a status page."""
    try:
        config_path = Path(config)
        cfg = MonitorConfig.from_yaml(config_path)
        
        # Initialize checker and history
        checker = URLChecker()
        history = CheckHistory(cfg.history_file)
        
        # Get results for all URLs
        results = []
        all_tags = set()  # Keep track of all unique tags
        for url_config in cfg.urls:
            result = checker.check_url(url_config)
            result.tags = url_config.tags  # Add tags to result for display
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
        if template:
            template_path = Path(template)
            template_dir = template_path.parent
            template_file = template_path.name
        else:
            template_dir = Path(__file__).parent / 'templates'
            template_file = 'status.html'
        
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        template = env.get_template(template_file)
        
        # Generate HTML
        html = template.render(
            timestamp=datetime.now(),
            results=results,
            tags=sorted_tags  # Pass sorted tags to template
        )
        
        # Write output
        output_path = Path(output)
        output_path.write_text(html)
        console.print(f"Status page generated: {output_path}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    cli()
