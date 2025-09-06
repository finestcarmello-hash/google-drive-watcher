"""HTML fetching module for Chaturbate profiles."""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from urllib.parse import urljoin
from config import Config

logger = logging.getLogger(__name__)


class ProfileFetcher:
    """Handles fetching of Chaturbate profile pages."""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://chaturbate.com"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _build_profile_url(self, username: str) -> str:
        """Build the full URL for a performer's profile."""
        return urljoin(self.base_url, f"/{username}/")
    
    async def fetch_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a performer's profile page.
        
        Args:
            username: The performer's username
            
        Returns:
            Dictionary with 'html', 'status_code', 'url', and 'error' keys
        """
        url = self._build_profile_url(username)
        
        try:
            logger.debug(f"Fetching profile for {username}: {url}")
            
            async with self.session.get(url) as response:
                html_content = await response.text()
                
                result = {
                    'html': html_content,
                    'status_code': response.status,
                    'url': url,
                    'error': None
                }
                
                logger.debug(f"Successfully fetched {username}: status {response.status}, "
                           f"content length {len(html_content)}")
                
                return result
                
        except asyncio.TimeoutError:
            error_msg = f"Timeout fetching profile for {username}"
            logger.warning(error_msg)
            return {
                'html': None,
                'status_code': None,
                'url': url,
                'error': error_msg
            }
            
        except aiohttp.ClientError as e:
            error_msg = f"Client error fetching profile for {username}: {str(e)}"
            logger.warning(error_msg)
            return {
                'html': None,
                'status_code': None,
                'url': url,
                'error': error_msg
            }
            
        except Exception as e:
            error_msg = f"Unexpected error fetching profile for {username}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'html': None,
                'status_code': None,
                'url': url,
                'error': error_msg
            }
    
    async def fetch_multiple_profiles(self, usernames: list) -> Dict[str, Dict[str, Any]]:
        """
        Fetch multiple profiles concurrently.
        
        Args:
            usernames: List of performer usernames
            
        Returns:
            Dictionary mapping usernames to their fetch results
        """
        tasks = [self.fetch_profile(username) for username in usernames]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        fetch_results = {}
        for i, (username, result) in enumerate(zip(usernames, results)):
            if isinstance(result, Exception):
                logger.error(f"Exception fetching {username}: {result}")
                fetch_results[username] = {
                    'html': None,
                    'status_code': None,
                    'url': self._build_profile_url(username),
                    'error': str(result)
                }
            else:
                fetch_results[username] = result
        
        return fetch_results