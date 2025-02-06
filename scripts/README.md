# Scripts

## extract_links.py

This script extracts links from URLs defined in YAML configuration files located in `config/url_configs/`. For each URL, it:

1. Fetches the page content
2. Extracts all links using BeautifulSoup
3. Saves results to a JSON file in a timestamped directory under `extracted_links/`

### Output Format

Each JSON output file contains:
- `source_yaml`: Name of the source YAML config file
- `source_url`: URL that was scraped
- `name`: Name from the config
- `timestamp`: When the page was fetched
- `num_links`: Number of links found
- `links`: Array of extracted links, each containing:
  - `url`: Absolute URL
  - `text`: Link text content
  - `title`: Link title attribute if present
- `linked_urls`: Any explicitly linked URLs from the config file

### Known Limitations

1. Currently only handles static HTML content. Pages that require JavaScript for rendering may return incomplete results.
2. No retry logic for failed requests
3. Basic error handling for 404s and other HTTP errors

### Usage

```bash
python scripts/extract_links.py
```

Results will be saved in `extracted_links/YYYYMMDD_HHMMSS/`
