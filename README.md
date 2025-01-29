# Government Sites Multi-Monitor

Monitor multiple URLs for availability and content updates. Features include:

- Regular checking of URLs with configurable frequencies
- Detection of:
  - Site availability
  - Redirects
  - 404 errors
  - Last modified dates (from HTTP headers and HTML metadata)
  - Expected content presence
  - Linked URL availability and status
- History tracking in Parquet format
- Status page generation for GitHub Pages
- Bluesky integration for status updates (coming soon)

## Setup

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate virtual environment:
```bash
uv venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
uv pip install -e .
```

## Development

To install development dependencies:
```bash
uv pip install -e ".[dev]"
```

Run tests:
```bash
pytest
```

Format code:
```bash
black .
ruff check --fix .
```

## Configuration

URL configurations are stored in individual YAML files under `config/url_configs/`. Each file follows a naming convention of `NNN_description.yaml` where NNN is a 3-digit identifier.

Each configuration can include:

- `url`: The URL to check (required)
- `name`: Display name (defaults to domain)
- `check_frequency`: How often to check, e.g. "1d", "4h", "30m" (required)
- `tags`: List of tags for categorization
- `expected_content`: String that should appear in valid content
- `linked_urls`: List of related URLs to monitor, each with:
  - `url`: The linked URL to check
  - `name`: Display name for the linked URL
  - `description`: Optional description
  - `type`: Type of resource (e.g., 'pdf', 'webpage', 'dataset')

Example configuration:
```yaml
url: https://example.com/api
name: Example API
check_frequency: 1d
tags: [api, example]
expected_content: '"status": "ok"'
linked_urls:
  - url: https://example.com/api/docs
    name: API Documentation
    description: Technical documentation for the API
    type: webpage
  - url: https://example.com/api/schema.pdf
    name: API Schema
    type: pdf
```

## Usage

Run a check of all URLs:
```bash
python -m multi_monitor.cli check
```

Generate status page:
```bash
python -m multi_monitor.cli generate-page
```

View recent status changes:
```bash
python -m multi_monitor.cli status
```

## Data Storage

- Check results are stored in Parquet format for efficient storage and querying
- The history file location is configured in `config/monitor_config.yaml`
- GitHub Pages content is generated in the configured status page directory
- Status page shows:
  - Overall URL status
  - Last successful check date
  - Linked URL status and details
  - Last successful check dates for linked URLs that return 404 errors
