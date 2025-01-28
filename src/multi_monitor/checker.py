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
    status: str  # ok, error, redirect
    
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

    def __post_init__(self):
        """Initialize default values."""
        if self.linked_url_results is None:
            self.linked_url_results = []

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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })
    
    def _get_nested_value(self, data: dict, field_path: str, check_exists_only: bool = False):
        """Get a nested value from a dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            field_path: Path to field using dot notation (e.g. "metadata.count")
            check_exists_only: If True, return True if field exists in schema (even if null),
                             False if field doesn't exist. If False, return actual value.
        """
        try:
            parts = field_path.split('.')
            value = data
            for part in parts:
                # Handle array indices
                if '[' in part:
                    part, idx = part.split('[')
                    idx = int(idx.rstrip(']'))
                    # For existence check, just verify the array and index exist
                    if check_exists_only:
                        if part not in value or not isinstance(value[part], list) or len(value[part]) <= idx:
                            return False
                        value = value[part][idx]
                        continue
                    value = value[part][idx]
                else:
                    # For existence check, just verify the key exists
                    if check_exists_only:
                        if part not in value:
                            return False
                        value = value[part]
                        continue
                    value = value[part]
            return True if check_exists_only else value
        except (KeyError, IndexError, TypeError):
            return False if check_exists_only else None

    def _check_api(self, api_config) -> APICheckResult:
        """Check an API endpoint for availability and data freshness."""
        try:
            response = self.session.request(
                method=api_config.method,
                url=api_config.url,
                params=api_config.params,
                headers=api_config.headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                return APICheckResult(
                    status='error',
                    error_message="Invalid JSON response"
                )
            
            # Check for expected fields in schema
            if api_config.expected_fields:
                missing = []
                for field in api_config.expected_fields:
                    # Only check if field exists in schema, don't care about null values
                    if not self._get_nested_value(data, field, check_exists_only=True):
                        missing.append(field)
                
                if missing:
                    return APICheckResult(
                        status='error',
                        missing_fields=missing,
                        error_message=f"Fields removed from schema: {', '.join(missing)}"
                    )
            
            # Try to get last update time
            last_update = None
            if api_config.date_field:
                value = self._get_nested_value(data, api_config.date_field)
                if value:
                    try:
                        last_update = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        logging.warning(f"Could not parse date from field {api_config.date_field}")
            
            return APICheckResult(
                status='ok',
                last_update=last_update
            )
            
        except requests.RequestException as e:
            return APICheckResult(
                status='error',
                error_message=str(e)
            )

    def _check_linked_url(self, linked_url) -> LinkedURLCheckResult:
        """Check a linked URL and return the result."""
        try:
            response = self.session.get(
                linked_url.url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            result = LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status='error',  # Default status
                type=linked_url.type
            )
            
            result.status_code = response.status_code
            
            # Check for redirect
            if len(response.history) > 0:
                result.status = 'redirect'
                result.redirect_url = response.url
                return result
            
            # Check for errors
            if response.status_code != 200:
                result.status = 'error'
                result.error_message = f"HTTP {response.status_code}"
                return result
            
            # Get last modified date from headers only for successful responses
            if 'last-modified' in response.headers:
                try:
                    result.last_modified = datetime.strptime(
                        response.headers['last-modified'],
                        '%a, %d %b %Y %H:%M:%S %Z'
                    )
                except ValueError:
                    logging.warning(f"Could not parse Last-Modified header: {response.headers['last-modified']}")
            
            result.status = 'ok'
            return result
            
        except requests.TooManyRedirects as e:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status='redirect',
                redirect_url=e.response.url if hasattr(e, 'response') else None,
                error_message="Too many redirects",
                type=linked_url.type
            )
        except requests.Timeout:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status='error',
                error_message="Request timed out",
                type=linked_url.type
            )
        except requests.ConnectionError:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status='error',
                error_message="Connection error",
                type=linked_url.type
            )
        except Exception as e:
            return LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status='error',
                error_message=str(e),
                type=linked_url.type
            )

    def check_url(self, config) -> CheckResult:
        """Check a URL and return the result."""
        start_time = datetime.now()
        result = CheckResult(
            url=config.url,
            timestamp=start_time,
            status='error',  # Default status
            name=config.name,
            expected_update_frequency=config.expected_update_frequency
        )
        
        try:
            response = self.session.get(
                config.url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            result.status_code = response.status_code
            
            # Check for redirect
            if len(response.history) > 0:
                result.status = 'redirect'
                result.redirect_url = response.url
                return result
            
            # Check for errors
            if response.status_code != 200:
                result.status = 'error'
                result.error_message = f"HTTP {response.status_code}"
                return result
            
            # Get last modified date from headers only for successful responses
            if 'last-modified' in response.headers:
                try:
                    result.last_modified = datetime.strptime(
                        response.headers['last-modified'],
                        '%a, %d %b %Y %H:%M:%S %Z'
                    )
                except ValueError:
                    logging.warning(f"Could not parse Last-Modified header: {response.headers['last-modified']}")
            
            # Check content if specified
            if config.expected_content:
                soup = BeautifulSoup(response.text, 'html.parser')
                if not re.search(config.expected_content, soup.get_text()):
                    result.status = 'error'
                    result.error_message = f"Expected content not found: {config.expected_content}"
                    return result
            
            result.status = 'ok'
            
            # Check associated API if configured
            if config.api_config is not None:
                result.api_result = self._check_api(config.api_config)
            
            # Check linked URLs if any
            if config.linked_urls:
                for linked_url in config.linked_urls:
                    result.linked_url_results.append(self._check_linked_url(linked_url))
            
            return result
            
        except requests.TooManyRedirects as e:
            result.status = 'redirect'
            result.redirect_url = e.response.url if hasattr(e, 'response') else None
            result.error_message = "Too many redirects"
        except requests.Timeout:
            result.status = 'error'
            result.error_message = "Request timed out"
        except requests.ConnectionError:
            result.status = 'error'
            result.error_message = "Connection error"
        except Exception as e:
            result.status = 'error'
            result.error_message = str(e)
        
        return result
