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
    archived_content: Optional[List[str]] = None  # Added field for archived content URLs
    missing_components: Optional[List[str]] = None  # New field for tracking missing components
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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })

    def check_url(self, config) -> CheckResult:
        """Check a URL and return the result."""
        start_time = datetime.now()
        result = CheckResult(
            url=config.url,
            timestamp=start_time,
            status='ok',  # Default to ok instead of error
            name=config.name,
            expected_update_frequency=config.expected_update_frequency,
            archived_content=getattr(config, 'archived_content', [])  # Get archived content from config
        )
        
        try:
            response = self.session.get(config.url, timeout=self.timeout, allow_redirects=True)
            result.status_code = response.status_code
            
            # Get content length either from headers or actual response content
            content_length = response.headers.get('content-length')
            if content_length is None and response.content:
                content_length = len(response.content)
            result.content_length = int(content_length) if content_length else None
            
            result.response_time = (datetime.now() - start_time).total_seconds()
            
            # Check for redirects
            if len(response.history) > 0:
                result.status = 'redirect'
                result.redirect_url = response.url
                if response.status_code != 200:
                    result.error_message = f"HTTP {response.status_code}"
                return result
            
            if response.status_code != 200:
                result.status = 'error'
                result.error_message = f"HTTP {response.status_code}"
                return result
            
            # Check for content stripping and missing components
            missing_components = []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for Trump executive order notice
            exec_order_text = soup.find(string=re.compile(r"Executive Order.*Trump", re.IGNORECASE))
            if exec_order_text:
                result.status = 'content_stripped'
                result.error_message = "Content has been stripped due to executive order"
                missing_components.append("Original content removed due to executive order")
            
            # Check for missing images
            broken_images = soup.find_all('img', src=re.compile(r'^$|^#|error|missing', re.IGNORECASE))
            if broken_images:
                if result.status != 'content_stripped':
                    result.status = 'content_stripped'
                result.error_message = result.error_message or "Page contains missing or broken images"
                missing_components.append(f"{len(broken_images)} missing/broken images")
            
            # Check linked URLs if specified
            if hasattr(config, 'linked_urls'):
                linked_results = []
                has_missing_links = False
                for linked_url in config.linked_urls:
                    linked_result = self._check_linked_url(linked_url)
                    linked_results.append(linked_result)
                    if linked_result.status != 'ok':
                        has_missing_links = True
                        missing_components.append(f"Missing linked resource: {linked_result.name}")
                result.linked_url_results = linked_results
                if has_missing_links:
                    result.status = 'content_stripped'
                    result.error_message = result.error_message or "Some linked resources are unavailable"
            
            # Check API if specified and has a url config
            if hasattr(config, 'api_config') and hasattr(config.api_config, 'url'):
                result.api_result = self._check_api(config.api_config)
                if result.api_result.status != 'ok':
                    result.status = 'error'
                    result.error_message = result.api_result.error_message
            
            if missing_components:
                result.missing_components = missing_components
            
            return result
            
        except requests.TooManyRedirects:
            result.status = 'redirect'
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
        
        result.response_time = (datetime.now() - start_time).total_seconds()
        return result

    def _check_linked_url(self, linked_url) -> LinkedURLCheckResult:
        """Check a linked URL and return the result."""
        start_time = datetime.now()
        try:
            response = self.session.get(
                linked_url.url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # Get content length
            content_length = response.headers.get('content-length')
            if content_length is None and response.content:
                content_length = len(response.content)
            
            result = LinkedURLCheckResult(
                url=linked_url.url,
                name=linked_url.name,
                status='ok' if response.status_code == 200 else 'error',
                status_code=response.status_code,
                redirect_url=str(response.url) if response.url != linked_url.url else None,
                last_modified=parse_http_date(response.headers.get('last-modified')) if response.headers.get('last-modified') else None,
                content_length=int(content_length) if content_length else None,
                response_time=(datetime.now() - start_time).total_seconds(),
                error_message=f"HTTP {response.status_code}" if response.status_code != 200 else None,
                type=linked_url.type
            )
            
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

    def _check_api(self, api_config) -> APICheckResult:
        """Check an API endpoint for availability and data freshness."""
        try:
            response = self.session.get(
                api_config.url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
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
                
                return APICheckResult(
                    status='error',
                    error_message=error_msg
                )
            
            # Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                return APICheckResult(
                    status='error',
                    error_message="Invalid JSON response"
                )
            
            # Check required fields
            if hasattr(api_config, 'expected_fields'):
                missing_fields = []
                for field in api_config.expected_fields:
                    if not self._get_nested_value(data, field, check_exists_only=True):
                        missing_fields.append(field)
                
                if missing_fields:
                    return APICheckResult(
                        status='error',
                        missing_fields=missing_fields,
                        error_message="Missing required fields"
                    )
            
            # All checks passed
            result = APICheckResult(status='ok')
            
            # Check last update field if specified
            if hasattr(api_config, 'date_field'):
                last_update_value = self._get_nested_value(data, api_config.date_field)
                if last_update_value:
                    try:
                        # Try parsing with different date formats
                        for fmt in [
                            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with microseconds
                            '%Y-%m-%dT%H:%M:%SZ',     # ISO format without microseconds
                            '%Y-%m-%d %H:%M:%S',      # Simple datetime
                            '%Y-%m-%d',               # Simple date
                        ]:
                            try:
                                result.last_update = datetime.strptime(last_update_value, fmt)
                                break
                            except ValueError:
                                continue
                        
                        # If none of the formats worked
                        if not result.last_update:
                            logging.warning(f"Could not parse last update value: {last_update_value}")
                    except Exception as e:
                        logging.warning(f"Could not parse last update value: {last_update_value}")
            
            return result
            
        except requests.Timeout:
            return APICheckResult(
                status='error',
                error_message="Request timed out - the API server is not responding"
            )
        except requests.ConnectionError:
            return APICheckResult(
                status='error',
                error_message="Connection error - unable to reach the API server"
            )
        except Exception as e:
            return APICheckResult(
                status='error',
                error_message=str(e)
            )

    def _get_nested_value(self, data: dict, field_path: str, check_exists_only: bool = False):
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
            parts = field_path.split('.')
            value = data
            
            for part in parts:
                if value is None:
                    if check_exists_only:
                        return False
                    return None
                
                # Handle array indices
                if '[' in part and ']' in part:
                    try:
                        array_name = part[:part.index('[')]
                        idx_str = part[part.index('[')+1:part.index(']')]
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
