# America's Essential Data

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

## Development setup (the easy way)

If you're running a Mac or Linux system, you should be able to set up for
development with just one command:

```sh
./scripts/dev-setup/setup.sh
```

If you use Visual Studio Code, we also recommend installing the suggested
extensions for this workspace. They'll help with syntax highlighting, code
formatting, and other nice things to have during development.

## Development setup (the DIY way)

1. Make sure you're in the repository's root directory.

2. Install uv if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Create and activate a Python virtual environment:

```bash
uv venv
source .venv/bin/activate
```

4. Install all dependencies:

```bash
uv pip install -e ".[dev]"
```

## Helpful commands

### Run tests

```bash
pytest
```

### Format code

If you use Visual Studio Code, you should see a list of recommended extensions
to install. These will automatically format your code whenever you save.

To format all Python code on your own, though:

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
- `archived_content`: List of URLs to archived versions of the content (e.g., Wayback Machine snapshots)
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
archived_content:
  - https://web.archive.org/web/20250122002715/https://example.com/api
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
python -m americas_essential_data.cli check
```

Generate the main status page:

```bash
python -m americas_essential_data.cli generate-page
```

View recent status changes:

```bash
python -m americas_essential_data.cli status
```

Run the web app:

```bash
python -m americas_essential_data.cli web --debug
```

OR

```bash
python -m americas_essential_data.web --debug
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
