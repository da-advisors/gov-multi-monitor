"""Core URL checking functionality."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import logging
import time
import random

from .config import URLConfig

logger = logging.getLogger(__name__)

@dataclass
class CheckResult:
    """Result of checking a single URL."""
    url: str
    timestamp: datetime
    status: str  # 'ok', 'redirect', '404', 'error'
    status_code: Optional[int] = None
    redirect_url: Optional[str] = None
    last_modified: Optional[datetime] = None
    error_message: Optional[str] = None
    response_time: Optional[float] = None
    raw_headers: Optional[Dict] = None  # Store raw headers for debugging

class URLChecker:
    """Check URLs and detect their status and last modified dates."""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        
        # Rotate between common browser User-Agents
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        
        # Common headers that browsers send
        self.default_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
    
    def _get_random_user_agent(self):
        """Get a random User-Agent string."""
        return random.choice(self.user_agents)
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison by removing trivial differences."""
        # Convert to lowercase
        url = url.lower()
        # Remove trailing slash
        url = url.rstrip('/')
        # Remove default ports
        url = url.replace(':80/', '/').replace(':443/', '/')
        # Standardize http/https
        if url.startswith('http://'):
            url = 'https://' + url[7:]
        return url
    
    def check_url(self, config: URLConfig) -> CheckResult:
        """Check a single URL and return its status."""
        start_time = datetime.now()
        result = CheckResult(
            url=config.url,
            timestamp=start_time,
            status='error'  # Default status
        )
        
        try:
            # Add a small random delay to avoid overwhelming servers
            time.sleep(random.uniform(0.5, 2.0))
            
            # Prepare headers
            headers = self.default_headers.copy()
            headers['User-Agent'] = self._get_random_user_agent()
            
            # Parse URL to get domain for Referer
            parsed_url = urlparse(config.url)
            headers['Host'] = parsed_url.netloc
            
            response = None
            try:
                # First try with GET request
                response = self.session.get(
                    config.url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    headers=headers
                )
            except requests.TooManyRedirects as e:
                # The exception should have the last response
                if hasattr(e, 'response') and e.response is not None:
                    result.status = 'redirect'
                    # Try to get the Location header from the last response
                    result.redirect_url = e.response.headers.get('Location')
                    if not result.redirect_url and e.response.history:
                        # If no Location header, use the URL from the last response in history
                        result.redirect_url = e.response.history[-1].url
                result.error_message = "Exceeded 30 redirects"
                return result
            
            if response:
                # Store raw headers for debugging
                result.raw_headers = dict(response.headers)
                result.status_code = response.status_code
                result.response_time = (datetime.now() - start_time).total_seconds()
                
                # Log response details for debugging
                logger.debug(f"URL: {config.url}")
                logger.debug(f"Status Code: {response.status_code}")
                logger.debug(f"Headers: {response.headers}")
                
                # First check the final status code
                if response.status_code >= 400:
                    result.status = '404'
                    result.error_message = f"HTTP {response.status_code}"
                # Then check for meaningful redirect
                elif len(response.history) > 0:
                    original_url = self._normalize_url(config.url)
                    final_url = self._normalize_url(response.url)
                    
                    if original_url != final_url:
                        result.status = 'redirect'
                        result.redirect_url = response.url
                    else:
                        result.status = 'ok'
                else:
                    result.status = 'ok'
                
                # Try to find last modified date
                if hasattr(response, 'text'):  # Only for GET requests
                    result.last_modified = self._find_last_modified(response)
            
        except requests.Timeout:
            result.error_message = "Request timed out"
        except requests.RequestException as e:
            result.error_message = str(e)
        except Exception as e:
            result.error_message = f"Unexpected error: {str(e)}"
        
        return result
    
    def _find_last_modified(self, response: requests.Response) -> Optional[datetime]:
        """Try various methods to find the last modified date."""
        # 1. Check HTTP headers
        if 'last-modified' in response.headers:
            try:
                return datetime.strptime(
                    response.headers['last-modified'],
                    '%a, %d %b %Y %H:%M:%S %Z'
                )
            except ValueError:
                pass
        
        # 2. Parse HTML for common metadata
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check meta tags
            meta_tags = [
                # Dublin Core
                'DC.date.modified',
                'DCTERMS.modified',
                # Schema.org
                'article:modified_time',
                'og:updated_time',
                # Other common formats
                'last-modified',
                'modified',
                'date'
            ]
            
            for tag in meta_tags:
                meta = soup.find('meta', attrs={'name': tag}) or soup.find('meta', attrs={'property': tag})
                if meta and meta.get('content'):
                    try:
                        # Try ISO format first
                        return datetime.fromisoformat(meta['content'].replace('Z', '+00:00'))
                    except ValueError:
                        pass
            
            # Look for time tags with datetime attribute
            time_tag = soup.find('time', attrs={'datetime': True})
            if time_tag:
                try:
                    return datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                except ValueError:
                    pass
                    
        except Exception as e:
            logger.warning(f"Error parsing HTML for last modified date: {e}")
        
        return None
