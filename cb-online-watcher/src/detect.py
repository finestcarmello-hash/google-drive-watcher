"""Online/offline detection logic for Chaturbate performers."""

import re
import logging
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from patterns import (
    OFFLINE_INDICATORS, ONLINE_INDICATORS, 
    ONLINE_SELECTORS, OFFLINE_SELECTORS,
    ONLINE_TEXT_PATTERNS, OFFLINE_TEXT_PATTERNS
)

logger = logging.getLogger(__name__)


class OnlineDetector:
    """Detects online/offline status from HTML content."""
    
    def __init__(self):
        self.online_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in ONLINE_TEXT_PATTERNS]
        self.offline_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in OFFLINE_TEXT_PATTERNS]
    
    def detect_status(self, html_content: str, username: str) -> Dict[str, Any]:
        """
        Detect if a performer is online or offline based on HTML content.
        
        Args:
            html_content: The HTML content of the profile page
            username: The performer's username for logging
            
        Returns:
            Dictionary with 'is_online', 'confidence', 'indicators', and 'error' keys
        """
        if not html_content:
            return {
                'is_online': False,
                'confidence': 0.0,
                'indicators': [],
                'error': 'No HTML content provided'
            }
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for online indicators
            online_score, online_indicators = self._check_online_indicators(html_content, soup)
            
            # Check for offline indicators
            offline_score, offline_indicators = self._check_offline_indicators(html_content, soup)
            
            # Determine status based on scores
            is_online = online_score > offline_score
            confidence = abs(online_score - offline_score) / max(online_score + offline_score, 1)
            
            # Combine indicators for debugging
            all_indicators = online_indicators + offline_indicators
            
            logger.debug(f"Status detection for {username}: online_score={online_score}, "
                        f"offline_score={offline_score}, is_online={is_online}, "
                        f"confidence={confidence:.2f}")
            
            return {
                'is_online': is_online,
                'confidence': confidence,
                'indicators': all_indicators,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error parsing HTML for {username}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'is_online': False,
                'confidence': 0.0,
                'indicators': [],
                'error': error_msg
            }
    
    def _check_online_indicators(self, html_content: str, soup: BeautifulSoup) -> tuple[float, List[str]]:
        """Check for online indicators and return score and found indicators."""
        score = 0.0
        indicators = []
        
        # Check text-based indicators
        for indicator in ONLINE_INDICATORS:
            if indicator.lower() in html_content.lower():
                score += 1.0
                indicators.append(f"text: {indicator}")
        
        # Check CSS selectors
        for selector in ONLINE_SELECTORS:
            elements = soup.select(selector)
            if elements:
                score += 2.0  # CSS selectors are more reliable
                indicators.append(f"selector: {selector} (found {len(elements)} elements)")
        
        # Check regex patterns
        for pattern in self.online_patterns:
            matches = pattern.findall(html_content)
            if matches:
                score += 1.5
                indicators.append(f"pattern: {pattern.pattern} (found {len(matches)} matches)")
        
        # Special checks for common online elements
        if soup.find('div', {'class': 'player-embed'}):
            score += 3.0
            indicators.append("player-embed div found")
        
        if soup.find('video'):
            score += 2.0
            indicators.append("video element found")
        
        if soup.find('iframe', {'src': lambda x: x and 'player' in x.lower()}):
            score += 2.0
            indicators.append("player iframe found")
        
        return score, indicators
    
    def _check_offline_indicators(self, html_content: str, soup: BeautifulSoup) -> tuple[float, List[str]]:
        """Check for offline indicators and return score and found indicators."""
        score = 0.0
        indicators = []
        
        # Check text-based indicators
        for indicator in OFFLINE_INDICATORS:
            if indicator.lower() in html_content.lower():
                score += 1.0
                indicators.append(f"text: {indicator}")
        
        # Check CSS selectors
        for selector in OFFLINE_SELECTORS:
            elements = soup.select(selector)
            if elements:
                score += 2.0  # CSS selectors are more reliable
                indicators.append(f"selector: {selector} (found {len(elements)} elements)")
        
        # Check regex patterns
        for pattern in self.offline_patterns:
            matches = pattern.findall(html_content)
            if matches:
                score += 1.5
                indicators.append(f"pattern: {pattern.pattern} (found {len(matches)} matches)")
        
        # Special checks for common offline elements
        if soup.find('div', {'class': 'offline'}):
            score += 3.0
            indicators.append("offline div found")
        
        if soup.find('div', {'id': 'offline'}):
            score += 3.0
            indicators.append("offline id found")
        
        return score, indicators
    
    def detect_multiple_statuses(self, fetch_results: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Detect status for multiple performers.
        
        Args:
            fetch_results: Dictionary mapping usernames to their fetch results
            
        Returns:
            Dictionary mapping usernames to their detection results
        """
        detection_results = {}
        
        for username, fetch_result in fetch_results.items():
            if fetch_result.get('error'):
                detection_results[username] = {
                    'is_online': False,
                    'confidence': 0.0,
                    'indicators': [],
                    'error': f"Fetch error: {fetch_result['error']}"
                }
            else:
                detection_results[username] = self.detect_status(
                    fetch_result.get('html', ''), username
                )
        
        return detection_results