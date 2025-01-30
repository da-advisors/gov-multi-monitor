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
    archived_content: Optional[List[str]] = None  # Added field for archived content URLs

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
            status='error',  # Default status
            name=config.name,
            expected_update_frequency=config.expected_update_frequency,
            archived_content=getattr(config, 'archived_content', [])  # Get archived content from config
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
            if hasattr(config, 'expected_content') and config.expected_content:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check text content
                if not any(text in response.text for text in config.expected_content):
                    result.status = 'error'
                    result.error_message = "Expected content not found"
                    return result
            
            # Check linked URLs if specified
            if hasattr(config, 'linked_urls') and config.linked_urls:
                for linked_url in config.linked_urls:
                    linked_result = self._check_linked_url(linked_url)
                    result.linked_url_results.append(linked_result)
            
            # Check API if specified
            if hasattr(config, 'api') and config.api:
                result.api_result = self._check_api(config.api)
                if result.api_result.status == 'error':
                    result.status = 'error'
                    result.error_message = result.api_result.error_message
                    return result
            
            result.status = 'ok'
            result.response_time = (datetime.now() - start_time).total_seconds()
            return result
            
        except requests.TooManyRedirects:
            result.status = 'redirect'
            result.error_message = "Too many redirects"
        except requests.Timeout:
            result.error_message = "Request timed out"
        except requests.ConnectionError:
            result.error_message = "Connection error"
        except Exception as e:
            result.error_message = str(e)
        
        result.response_time = (datetime.now() - start_time).total_seconds()
        return result

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
                status_code=response.status_code,
                type=linked_url.type
            )
            
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

    def _check_api(self, api_config) -> APICheckResult:
        """Check an API endpoint for availability and data freshness."""
        try:
            response = self.session.get(
                api_config.url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                return APICheckResult(
                    status='error',
                    error_message=f"HTTP {response.status_code}"
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
            if api_config.required_fields:
                missing_fields = []
                for field in api_config.required_fields:
                    if not self._get_nested_value(data, field, check_exists_only=True):
                        missing_fields.append(field)
                
                if missing_fields:
                    return APICheckResult(
                        status='error',
                        missing_fields=missing_fields,
                        error_message="Missing required fields"
                    )
            
            # Check last update field if specified
            if api_config.last_update_field:
                last_update_value = self._get_nested_value(data, api_config.last_update_field)
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
                                last_update = datetime.strptime(last_update_value, fmt)
                                return APICheckResult(
                                    status='ok',
                                    last_update=last_update
                                )
                            except ValueError:
                                continue
                        
                        # If none of the formats worked
                        return APICheckResult(
                            status='error',
                            error_message=f"Could not parse last update date: {last_update_value}"
                        )
                    except Exception as e:
                        return APICheckResult(
                            status='error',
                            error_message=f"Error parsing last update date: {str(e)}"
                        )
            
            return APICheckResult(status='ok')
            
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
        try:
            parts = field_path.split('.')
            value = data
            for part in parts:
                # Handle array indices
                if '[' in part:
                    part, idx = part.split('[')
                    idx = int(idx.rstrip(']'))
                    value = value[part][idx]
                else:
                    value = value[part]
            
            if check_exists_only:
                return True
            return value
        except (KeyError, IndexError, TypeError):
            if check_exists_only:
                return False
            return None
