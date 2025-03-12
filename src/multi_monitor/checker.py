"""Check URLs for availability and changes."""

import requests
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import logging
from bs4 import BeautifulSoup
import re
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse


@dataclass
class LinkedURLCheckResult:
    """Result of checking a linked URL."""

    url: str
    name: str
    status: str  # ok, error, redirect
    status_code: Optional[int] = None
    redirect_url: Optional[str] = None
    last_modified: Optional[datetime] = None
    error_message: Optional[str] = None
    type: Optional[str] = None
    last_success: Optional[datetime] = None  # Added field for last successful check
    content_length: Optional[int] = None  # Added field for content length
    response_time: Optional[float] = None  # Added for consistency with main CheckResult


@dataclass
class APICheckResult:
    """Result of checking an API endpoint."""

    status: str  # ok, error
    last_update: Optional[datetime] = None
    missing_fields: Optional[list[str]] = None
    error_message: Optional[str] = None


@dataclass
class CheckResult:
    """Result of checking a URL."""

    # Required fields (no defaults)
    url: str
    timestamp: datetime
    status: str  # ok, error, redirect, content_stripped

    # Optional fields (with defaults)
    name: Optional[str] = None
    status_code: Optional[int] = None
    redirect_url: Optional[str] = None
    last_modified: Optional[datetime] = None
    error_message: Optional[str] = None
    response_time: Optional[float] = None
    expected_update_frequency: Optional[str] = None
    api_result: Optional[APICheckResult] = None
    linked_url_results: List[LinkedURLCheckResult] = None
    archived_content: Optional[List[str]] = (
        None  # Added field for archived content URLs
    )
    missing_components: Optional[List[str]] = (
        None  # New field for tracking missing components
    )
    content_length: Optional[int] = None  # Added field for content length

    def __post_init__(self):
        """Initialize default values."""
        if self.linked_url_results is None:
            self.linked_url_results = []
        if self.archived_content is None:
            self.archived_content = []


class URLChecker:
    """Check URLs for availability and changes."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

        # Add retry logic
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],  # retry on these status codes
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Update headers to more closely match browser behavior
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "DNT": "1",
            }
        )

    def _get_content_type_headers(self, url: str) -> Dict[str, str]:
        """Get content-type specific headers."""
        headers = {}
        lower_url = url.lower()

        if lower_url.endswith(".pdf"):
            headers.update(
                {
                    "Accept": "application/pdf,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                }
            )
        elif any(lower_url.endswith(ext) for ext in [".doc", ".docx", ".xls", ".xlsx"]):
            headers.update(
                {
                    "Accept": "application/msword,application/vnd.openxmlformats-officedocument.*,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                }
            )
        return headers

    def _get_domain_specific_headers(self, url: str) -> Dict[str, str]:
        """Get domain-specific headers based on URL."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        headers = {}

        # Get content-type specific headers first
        headers.update(self._get_content_type_headers(url))

        # Base headers that improve compatibility across sites
        base_headers = {
            "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        headers.update(base_headers)

        if "ed.gov" in domain:
            headers.update(
                {
                    "Host": domain,
                    "Origin": f"https://{domain}",
                    "Referer": f"https://{domain}/",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
        elif "nih.gov" in domain:
            headers.update(
                {
                    "Host": domain,
                    "Origin": f"https://{domain}",
                    "Referer": f"https://{domain}/",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": headers.get(
                        "Accept",
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    ),
                }
            )
            # For NIH PDFs, add specific headers
            if url.lower().endswith(".pdf"):
                headers.update({"Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"})
        elif "oecd.org" in domain:
            headers.update(
                {
                    "Host": domain,
                    "Origin": "https://www.oecd.org",
                    "Referer": "https://www.oecd.org/",
                    "Accept": headers.get(
                        "Accept",
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    ),
                    "Sec-Ch-Ua-Full-Version-List": '"Not A(Brand";v="99.0.0.0", "Google Chrome";v="121.0.6167.85", "Chromium";v="121.0.6167.85"',
                    "Sec-Ch-Ua-Arch": '"x86"',
                    "Sec-Ch-Ua-Bitness": '"64"',
                    "Sec-Ch-Ua-Full-Version": '"121.0.6167.85"',
                    "Sec-Ch-Ua-Platform-Version": '"13.0.0"',
                }
            )

        return headers

    def check_url(self, url_config: Dict[str, Any]) -> CheckResult:
        """Check a URL for availability and changes."""
        # Support both dictionary and object access for url_config
        if isinstance(url_config, dict):
            url = url_config["url"]
            name = url_config.get("name")
            expected_update_frequency = url_config.get("expected_update_frequency")
            archived_content = url_config.get("archived_content", [])
            tags = url_config.get("tags", [])
            linked_urls = url_config.get("linked_urls", [])
            api_config = url_config.get("api_config")
        else:
            url = url_config.url
            name = getattr(url_config, "name", None)
            expected_update_frequency = getattr(
                url_config, "expected_update_frequency", None
            )
            archived_content = getattr(url_config, "archived_content", [])
            tags = getattr(url_config, "tags", [])
            linked_urls = getattr(url_config, "linked_urls", [])
            api_config = getattr(url_config, "api_config", None)

        start_time = datetime.now()
        result = CheckResult(
            url=url,
            timestamp=start_time,
            status="error",  # Default to error
            name=name,
            expected_update_frequency=expected_update_frequency,
            archived_content=archived_content,
        )

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            result.status_code = response.status_code

            # Get content length either from headers or actual response content
            content_length = response.headers.get("content-length")
            if content_length is None and response.content:
                content_length = len(response.content)
            result.content_length = int(content_length) if content_length else None

            result.response_time = (datetime.now() - start_time).total_seconds()

            # Check for redirects
            if len(response.history) > 0:
                result.status = "redirect"
                result.redirect_url = response.url
                return result

            # Check for errors
            if response.status_code != 200:
                result.status = "error"
                result.error_message = f"HTTP {response.status_code}"
                return result

            # All good, mark as ok
            result.status = "ok"

            # Check for last modified date
            if "last-modified" in response.headers:
                try:
                    result.last_modified = parse_http_date(
                        response.headers["last-modified"]
                    )
                except (TypeError, ValueError):
                    pass

            # Check linked URLs if specified
            if linked_urls:
                linked_results = []
                has_missing_links = False
                for linked_url in linked_urls:
                    linked_result = self._check_linked_url(linked_url)
                    linked_results.append(linked_result)
                    if linked_result.status != "ok":
                        has_missing_links = True

                result.linked_url_results = linked_results
                if has_missing_links:
                    result.status = "error"
                    result.error_message = "Some linked resources are unavailable"

            # Check API if specified
            if api_config:
                try:
                    result.api_result = self._check_api(api_config)
                    if result.api_result.status != "ok":
                        result.status = "error"
                        result.error_message = result.api_result.error_message
                except Exception as e:
                    result.status = "error"
                    result.error_message = str(e)

            return result

        except requests.Timeout:
            result.error_message = "Request timed out"
            return result
        except requests.TooManyRedirects as e:
            if hasattr(e, "response") and e.response.history:
                if len(e.response.history) > 0:
                    result.status = "redirect"
                    result.redirect_url = e.response.history[-1].url
            result.error_message = "Exceeded 30 redirects"
            return result
        except requests.RequestException as e:
            result.error_message = str(e)
            return result
        except Exception as e:
            result.error_message = f"Unexpected error: {str(e)}"
            return result

    def _check_linked_url(self, linked_url) -> LinkedURLCheckResult:
        """Check a linked URL and return the result."""
        start_time = datetime.now()
        try:
            response = self.session.get(
                linked_url.url, timeout=self.timeout, allow_redirects=True
            )

            content_length = response.headers.get("content-length")
            if not content_length:
                content_length = len(response.content)

            result = LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status="ok" if response.status_code == 200 else "error",
                status_code=response.status_code,
                redirect_url=(
                    str(response.url) if response.url != linked_url.url else None
                ),
                last_modified=(
                    parse_http_date(response.headers.get("last-modified"))
                    if response.headers.get("last-modified")
                    else None
                ),
                content_length=int(content_length) if content_length else None,
                response_time=(datetime.now() - start_time).total_seconds(),
                type=getattr(linked_url, "type", None),
            )

            return result

        except requests.TooManyRedirects as e:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status="redirect",
                redirect_url=e.response.url if hasattr(e, "response") else None,
                error_message="Too many redirects",
                type=getattr(linked_url, "type", None),
            )
        except requests.Timeout:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status="error",
                error_message="Request timed out",
                type=getattr(linked_url, "type", None),
            )
        except requests.ConnectionError:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status="error",
                error_message="Connection error",
                type=getattr(linked_url, "type", None),
            )
        except Exception as e:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status="error",
                error_message=str(e),
                type=getattr(linked_url, "type", None),
            )

    def _check_api(self, api_config) -> APICheckResult:
        """Check an API endpoint."""
        # Support both dictionary and object access for api_config
        if isinstance(api_config, dict):
            url = api_config["url"]
            expected_fields = api_config.get("expected_fields", [])
            date_field = api_config.get("date_field")
        else:
            url = api_config.url
            expected_fields = getattr(api_config, "expected_fields", [])
            date_field = getattr(api_config, "date_field", None)

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                if response.status_code == 404:
                    error_msg = "API endpoint not found (HTTP 404) - the endpoint may have moved or been deprecated"
                elif response.status_code == 403:
                    error_msg = "Access forbidden (HTTP 403) - check API permissions"
                elif response.status_code == 401:
                    error_msg = "Unauthorized (HTTP 401) - authentication required"
                elif response.status_code >= 500:
                    error_msg = f"Server error (HTTP {response.status_code}) - the API server may be experiencing issues"

                return APICheckResult(status="error", error_message=error_msg)

            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                return APICheckResult(
                    status="error", error_message="Invalid JSON response"
                )

            # Check required fields
            if expected_fields:
                missing_fields = []
                for field in expected_fields:
                    if not self._get_nested_value(data, field, check_exists_only=True):
                        missing_fields.append(field)

                if missing_fields:
                    return APICheckResult(
                        status="error",
                        missing_fields=missing_fields,
                        error_message=f"Missing required fields: {', '.join(missing_fields)}",
                    )

            # All checks passed
            result = APICheckResult(status="ok")

            # Check last update field if specified
            if date_field:
                last_update_value = self._get_nested_value(data, date_field)
                if last_update_value:
                    try:
                        # Try parsing with different date formats
                        for fmt in [
                            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds
                            "%Y-%m-%dT%H:%M:%SZ",  # ISO format without microseconds
                            "%Y-%m-%d %H:%M:%S",  # Simple datetime
                            "%Y-%m-%d",  # Simple date
                        ]:
                            try:
                                result.last_update = datetime.strptime(
                                    last_update_value, fmt
                                )
                                break
                            except ValueError:
                                continue

                        # If none of the formats worked
                        if not result.last_update:
                            logging.warning(
                                f"Could not parse last update value: {last_update_value}"
                            )
                    except Exception as e:
                        logging.warning(
                            f"Could not parse last update value: {last_update_value}"
                        )

            return result

        except requests.Timeout:
            return APICheckResult(
                status="error",
                error_message="Request timed out - the API server is not responding",
            )
        except requests.ConnectionError:
            return APICheckResult(
                status="error",
                error_message="Connection error - unable to reach the API server",
            )
        except Exception as e:
            return APICheckResult(status="error", error_message=str(e))

    def _get_nested_value(
        self, data: dict, field_path: str, check_exists_only: bool = False
    ):
        """Get a nested value from a dictionary using dot notation.

        Args:
            data: Dictionary to search
            field_path: Path to field using dot notation (e.g. "metadata.count")
            check_exists_only: If True, return True if field exists in schema (even if null),
                             False if field doesn't exist. If False, return actual value.
        """
        if data is None or field_path is None:
            if check_exists_only:
                return False
            return None

        try:
            parts = field_path.split(".")
            value = data

            for part in parts:
                if value is None:
                    if check_exists_only:
                        return False
                    return None

                # Handle array indices
                if "[" in part and "]" in part:
                    try:
                        array_name = part[: part.index("[")]
                        idx_str = part[part.index("[") + 1 : part.index("]")]
                        idx = int(idx_str)

                        # First check if array exists
                        if array_name not in value:
                            if check_exists_only:
                                return False
                            return None

                        array_value = value[array_name]

                        # Check if it's actually an array and has enough elements
                        if not isinstance(array_value, (list, tuple)):
                            if check_exists_only:
                                return False
                            return None

                        if idx < 0 or idx >= len(array_value):
                            if check_exists_only:
                                return False
                            return None

                        value = array_value[idx]
                    except (ValueError, IndexError, KeyError, TypeError):
                        if check_exists_only:
                            return False
                        return None
                else:
                    if part not in value:
                        if check_exists_only:
                            return False
                        return None
                    value = value[part]

            if check_exists_only:
                return True
            return value

        except (KeyError, IndexError, TypeError, AttributeError) as e:
            logging.debug(f"Error getting nested value for path {field_path}: {str(e)}")
            if check_exists_only:
                return False
            return None


def parse_http_date(date_str):
    return parsedate_to_datetime(date_str)
