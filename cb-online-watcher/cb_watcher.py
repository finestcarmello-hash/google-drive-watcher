#!/usr/bin/env python3
"""
Chaturbate Online Watcher - Single File Version
A production-ready tool to monitor Chaturbate performers and send Telegram notifications.

Usage:
    python cb_watcher.py

Configuration via environment variables:
    TELEGRAM_BOT_TOKEN - Your Telegram bot token (required)
    TELEGRAM_CHAT_IDS - Comma-separated chat IDs (required)
    PERFORMERS - Comma-separated usernames to monitor (required)
    POLL_INTERVAL - Polling interval in seconds (default: 30)
    JITTER_RANGE - Jitter range in seconds (default: 5)
    LOG_LEVEL - Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
    STATE_FILE - State persistence file (default: .status.json)
"""

import asyncio
import aiohttp
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration management for the Chaturbate online watcher."""
    
    def __init__(self):
        # Telegram configuration
        self.telegram_bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_ids: List[str] = self._parse_chat_ids()
        
        # Performer configuration
        self.performers: List[str] = self._parse_performers()
        
        # Polling configuration
        self.poll_interval: int = int(os.getenv('POLL_INTERVAL', '30'))
        self.jitter_range: int = int(os.getenv('JITTER_RANGE', '5'))
        
        # Logging configuration
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO')
        self.log_file: str = os.getenv('LOG_FILE', 'logs/online_watcher.log')
        self.log_max_bytes: int = int(os.getenv('LOG_MAX_BYTES', '10485760'))  # 10MB
        self.log_backup_count: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))
        
        # State persistence
        self.state_file: str = os.getenv('STATE_FILE', '.status.json')
        
        # Request configuration
        self.request_timeout: int = int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.user_agent: str = os.getenv('USER_AGENT', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Validate configuration
        self._validate()
    
    def _parse_chat_ids(self) -> List[str]:
        """Parse comma-separated chat IDs from environment variable."""
        chat_ids_str = os.getenv('TELEGRAM_CHAT_IDS', '')
        if not chat_ids_str:
            return []
        return [chat_id.strip() for chat_id in chat_ids_str.split(',') if chat_id.strip()]
    
    def _parse_performers(self) -> List[str]:
        """Parse comma-separated performer usernames from environment variable."""
        performers_str = os.getenv('PERFORMERS', '')
        if not performers_str:
            return []
        return [performer.strip() for performer in performers_str.split(',') if performer.strip()]
    
    def _validate(self) -> None:
        """Validate configuration parameters."""
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        if not self.telegram_chat_ids:
            raise ValueError("TELEGRAM_CHAT_IDS is required")
        
        if not self.performers:
            raise ValueError("PERFORMERS is required")
        
        if self.poll_interval < 1:
            raise ValueError("POLL_INTERVAL must be at least 1 second")
        
        if self.jitter_range < 0:
            raise ValueError("JITTER_RANGE must be non-negative")
        
        if self.request_timeout < 1:
            raise ValueError("REQUEST_TIMEOUT must be at least 1 second")
    
    def get_poll_interval_with_jitter(self) -> int:
        """Get poll interval with random jitter applied."""
        import random
        jitter = random.randint(-self.jitter_range, self.jitter_range)
        return max(1, self.poll_interval + jitter)

# ============================================================================
# DETECTION PATTERNS
# ============================================================================

# Offline indicators
OFFLINE_INDICATORS = [
    "room is currently offline",
    "This room is currently offline",
    "The room is currently offline",
    "offline",
    "is_live:false",
    "var is_live = false",
    "is_live = false",
    'data-room-status="offline"',
    'data-room-status="private"',
    'class="offline"',
    'id="offline"',
    "This performer is not currently broadcasting",
    "This model is not currently broadcasting",
    "Broadcast has ended",
    "broadcast has ended",
    "Show has ended"
]

# Online indicators
ONLINE_INDICATORS = [
    "is_live:true",
    "var is_live = true",
    "is_live = true",
    'data-room-status="public"',
    'data-room-status="group"',
    'class="online"',
    'id="online"',
    "player-embed",
    "video-player",
    "live-player",
    "broadcasting",
    "currently broadcasting",
    "is currently live",
    "is live now",
    "live now",
    "online now"
]

# CSS selectors for more precise detection
ONLINE_SELECTORS = [
    '[data-room-status="public"]',
    '[data-room-status="group"]',
    '.online',
    '#online',
    '.player-embed',
    '.video-player',
    '.live-player',
    '.broadcasting',
    '.is-live'
]

OFFLINE_SELECTORS = [
    '[data-room-status="offline"]',
    '[data-room-status="private"]',
    '.offline',
    '#offline',
    '.not-broadcasting',
    '.room-offline'
]

# Text patterns that indicate the performer is online
ONLINE_TEXT_PATTERNS = [
    r"is_live\s*:\s*true",
    r"var\s+is_live\s*=\s*true",
    r"is_live\s*=\s*true",
    r"data-room-status\s*=\s*[\"']public[\"']",
    r"data-room-status\s*=\s*[\"']group[\"']",
    r"currently\s+broadcasting",
    r"is\s+currently\s+live",
    r"is\s+live\s+now",
    r"live\s+now",
    r"online\s+now"
]

# Text patterns that indicate the performer is offline
OFFLINE_TEXT_PATTERNS = [
    r"room\s+is\s+currently\s+offline",
    r"is_live\s*:\s*false",
    r"var\s+is_live\s*=\s*false",
    r"is_live\s*=\s*false",
    r"data-room-status\s*=\s*[\"']offline[\"']",
    r"data-room-status\s*=\s*[\"']private[\"']",
    r"broadcast\s+has\s+ended",
    r"show\s+has\s+ended",
    r"not\s+currently\s+broadcasting",
    r"not\s+broadcasting"
]

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class StateManager:
    """Manages persistent state for the online watcher."""
    
    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self.state: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                self.logger.info(f"Loaded state from {self.state_file}")
            else:
                self.state = {
                    'performers': {},
                    'last_updated': None,
                    'version': '1.0'
                }
                self.logger.info(f"Created new state file: {self.state_file}")
        except Exception as e:
            self.logger.error(f"Error loading state from {self.state_file}: {e}")
            self.state = {
                'performers': {},
                'last_updated': None,
                'version': '1.0'
            }
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Update timestamp
            self.state['last_updated'] = datetime.now().isoformat()
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            self.logger.error(f"Error saving state to {self.state_file}: {e}")
    
    def get_performer_status(self, username: str) -> Optional[bool]:
        """Get the last known online status for a performer."""
        performer_data = self.state.get('performers', {}).get(username, {})
        return performer_data.get('is_online')
    
    def update_performer_status(self, username: str, is_online: bool, 
                              confidence: float = 0.0, indicators: list = None) -> bool:
        """Update the status for a performer and return if status changed."""
        if 'performers' not in self.state:
            self.state['performers'] = {}
        
        performer_data = self.state['performers'].get(username, {})
        previous_status = performer_data.get('is_online')
        
        # Update performer data
        self.state['performers'][username] = {
            'is_online': is_online,
            'confidence': confidence,
            'indicators': indicators or [],
            'last_checked': datetime.now().isoformat(),
            'last_status_change': datetime.now().isoformat() if previous_status != is_online else performer_data.get('last_status_change')
        }
        
        # Save state
        self._save_state()
        
        # Return whether status changed
        status_changed = previous_status is not None and previous_status != is_online
        
        if status_changed:
            self.logger.info(f"Status changed for {username}: {previous_status} -> {is_online}")
        else:
            self.logger.debug(f"Status unchanged for {username}: {is_online}")
        
        return status_changed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the current state."""
        performers = self.state.get('performers', {})
        online_count = sum(1 for p in performers.values() if p.get('is_online', False))
        
        return {
            'total_performers': len(performers),
            'online_performers': online_count,
            'offline_performers': len(performers) - online_count,
            'last_updated': self.state.get('last_updated'),
            'version': self.state.get('version', '1.0')
        }

# ============================================================================
# DETECTION LOGIC
# ============================================================================

class OnlineDetector:
    """Detects online/offline status from HTML content."""
    
    def __init__(self):
        self.online_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in ONLINE_TEXT_PATTERNS]
        self.offline_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in OFFLINE_TEXT_PATTERNS]
        self.logger = logging.getLogger(__name__)
    
    def detect_status(self, html_content: str, username: str) -> Dict[str, Any]:
        """Detect if a performer is online or offline based on HTML content."""
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
            
            self.logger.debug(f"Status detection for {username}: online_score={online_score}, "
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
            self.logger.error(error_msg, exc_info=True)
            return {
                'is_online': False,
                'confidence': 0.0,
                'indicators': [],
                'error': error_msg
            }
    
    def _check_online_indicators(self, html_content: str, soup: BeautifulSoup) -> Tuple[float, List[str]]:
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
    
    def _check_offline_indicators(self, html_content: str, soup: BeautifulSoup) -> Tuple[float, List[str]]:
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

# ============================================================================
# HTTP FETCHING
# ============================================================================

class ProfileFetcher:
    """Handles fetching of Chaturbate profile pages."""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = "https://chaturbate.com"
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
    
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
        """Fetch a performer's profile page."""
        url = self._build_profile_url(username)
        
        try:
            self.logger.debug(f"Fetching profile for {username}: {url}")
            
            async with self.session.get(url) as response:
                html_content = await response.text()
                
                result = {
                    'html': html_content,
                    'status_code': response.status,
                    'url': url,
                    'error': None
                }
                
                self.logger.debug(f"Successfully fetched {username}: status {response.status}, "
                           f"content length {len(html_content)}")
                
                return result
                
        except asyncio.TimeoutError:
            error_msg = f"Timeout fetching profile for {username}"
            self.logger.warning(error_msg)
            return {
                'html': None,
                'status_code': None,
                'url': url,
                'error': error_msg
            }
            
        except aiohttp.ClientError as e:
            error_msg = f"Client error fetching profile for {username}: {str(e)}"
            self.logger.warning(error_msg)
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
        """Fetch multiple profiles concurrently."""
        tasks = [self.fetch_profile(username) for username in usernames]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        fetch_results = {}
        for i, (username, result) in enumerate(zip(usernames, results)):
            if isinstance(result, Exception):
                self.logger.error(f"Exception fetching {username}: {result}")
                fetch_results[username] = {
                    'html': None,
                    'status_code': None,
                    'url': self._build_profile_url(username),
                    'error': str(result)
                }
            else:
                fetch_results[username] = result
        
        return fetch_results

# ============================================================================
# TELEGRAM NOTIFICATIONS
# ============================================================================

class TelegramNotifier:
    """Handles Telegram notifications for performer status changes."""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot_token = config.telegram_bot_token
        self.chat_ids = config.telegram_chat_ids
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def send_message(self, message: str, chat_id: str) -> bool:
        """Send a message to a specific chat."""
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    self.logger.debug(f"Message sent successfully to chat {chat_id}")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to send message to chat {chat_id}: "
                               f"status {response.status}, error: {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error sending message to chat {chat_id}: {e}")
            return False
    
    async def send_notification(self, username: str, is_online: bool, 
                              confidence: float = 0.0, indicators: List[str] = None) -> bool:
        """Send a notification about a performer's status change."""
        status_emoji = "🟢" if is_online else "🔴"
        status_text = "ONLINE" if is_online else "OFFLINE"
        
        # Create the main message
        message = f"{status_emoji} <b>{username}</b> is {status_text}"
        
        if confidence > 0:
            message += f" (confidence: {confidence:.1%})"
        
        # Add indicators if provided
        if indicators:
            indicator_text = ", ".join(indicators[:3])  # Show first 3 indicators
            if len(indicators) > 3:
                indicator_text += f" (+{len(indicators) - 3} more)"
            message += f"\n\n<i>Indicators: {indicator_text}</i>"
        
        # Add profile link
        profile_url = f"https://chaturbate.com/{username}/"
        message += f"\n\n🔗 <a href='{profile_url}'>View Profile</a>"
        
        # Send to all configured chat IDs
        tasks = [self.send_message(message, chat_id) for chat_id in self.chat_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check if all messages were sent successfully
        success_count = sum(1 for result in results if result is True)
        total_count = len(self.chat_ids)
        
        if success_count == total_count:
            self.logger.info(f"Notification sent successfully for {username} to {total_count} chats")
            return True
        else:
            self.logger.warning(f"Notification partially sent for {username}: "
                          f"{success_count}/{total_count} chats successful")
            return False
    
    async def test_connection(self) -> bool:
        """Test the Telegram bot connection."""
        url = f"{self.base_url}/getMe"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data.get('result', {})
                        self.logger.info(f"Telegram bot connected: @{bot_info.get('username', 'unknown')}")
                        return True
                    else:
                        self.logger.error(f"Telegram API error: {data.get('description', 'Unknown error')}")
                        return False
                else:
                    self.logger.error(f"Telegram API HTTP error: {response.status}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error testing Telegram connection: {e}")
            return False

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class OnlineWatcher:
    """Main application class for monitoring Chaturbate performers."""
    
    def __init__(self):
        self.config = Config()
        self.state_manager = StateManager(self.config.state_file)
        self.detector = OnlineDetector()
        self.running = False
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        # Create logs directory if it doesn't exist
        log_file = Path(self.config.log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=self.config.log_max_bytes,
                    backupCount=self.config.log_backup_count
                )
            ]
        )
        
        # Set specific loggers
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging configured successfully")
    
    async def check_performers(self) -> Dict[str, Dict[str, Any]]:
        """Check all performers and return status changes."""
        status_changes = {}
        
        async with ProfileFetcher(self.config) as fetcher:
            # Fetch all profiles concurrently
            fetch_results = await fetcher.fetch_multiple_profiles(self.config.performers)
            
            # Detect status for all performers
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
                    detection_results[username] = self.detector.detect_status(
                        fetch_result.get('html', ''), username
                    )
            
            # Process each performer
            for username in self.config.performers:
                detection_result = detection_results.get(username, {})
                
                if detection_result.get('error'):
                    self.logger.warning(f"Error detecting status for {username}: {detection_result['error']}")
                    continue
                
                is_online = detection_result.get('is_online', False)
                confidence = detection_result.get('confidence', 0.0)
                indicators = detection_result.get('indicators', [])
                
                # Update state and check if status changed
                status_changed = self.state_manager.update_performer_status(
                    username, is_online, confidence, indicators
                )
                
                if status_changed:
                    status_changes[username] = {
                        'is_online': is_online,
                        'confidence': confidence,
                        'indicators': indicators
                    }
        
        return status_changes
    
    async def send_notifications(self, status_changes: Dict[str, Dict[str, Any]]) -> None:
        """Send notifications for status changes."""
        if not status_changes:
            return
        
        async with TelegramNotifier(self.config) as notifier:
            # Test connection first
            if not await notifier.test_connection():
                self.logger.error("Failed to connect to Telegram. Skipping notifications.")
                return
            
            # Send individual notifications
            for username, info in status_changes.items():
                success = await notifier.send_notification(
                    username,
                    info['is_online'],
                    info['confidence'],
                    info['indicators']
                )
                
                if success:
                    self.logger.info(f"Notification sent for {username}")
                else:
                    self.logger.error(f"Failed to send notification for {username}")
    
    async def run_cycle(self) -> None:
        """Run a single monitoring cycle."""
        try:
            self.logger.info("Starting monitoring cycle")
            
            # Check all performers
            status_changes = await self.check_performers()
            
            # Send notifications for changes
            if status_changes:
                await self.send_notifications(status_changes)
                self.logger.info(f"Processed {len(status_changes)} status changes")
            else:
                self.logger.debug("No status changes detected")
            
            # Log current stats
            stats = self.state_manager.get_stats()
            self.logger.info(f"Current stats: {stats['online_performers']} online, "
                           f"{stats['offline_performers']} offline out of {stats['total_performers']} total")
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
    
    async def run(self) -> None:
        """Run the main monitoring loop."""
        self.logger.info("Starting Chaturbate Online Watcher")
        self.logger.info(f"Monitoring {len(self.config.performers)} performers: {', '.join(self.config.performers)}")
        self.logger.info(f"Poll interval: {self.config.poll_interval}s (with ±{self.config.jitter_range}s jitter)")
        
        # Test Telegram connection
        async with TelegramNotifier(self.config) as notifier:
            if not await notifier.test_connection():
                self.logger.error("Failed to connect to Telegram. Exiting.")
                return
        
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running:
                await self.run_cycle()
                
                if self.running:
                    # Wait for next cycle with jitter
                    wait_time = self.config.get_poll_interval_with_jitter()
                    self.logger.debug(f"Waiting {wait_time}s until next cycle")
                    await asyncio.sleep(wait_time)
        
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
        finally:
            self.running = False
            self.logger.info("Chaturbate Online Watcher stopped")

# ============================================================================
# ENTRY POINT
# ============================================================================

async def main():
    """Main entry point."""
    try:
        watcher = OnlineWatcher()
        await watcher.run()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease check your .env file or environment variables.")
        print("Required variables:")
        print("  TELEGRAM_BOT_TOKEN - Your Telegram bot token")
        print("  TELEGRAM_CHAT_IDS - Comma-separated chat IDs")
        print("  PERFORMERS - Comma-separated usernames to monitor")
        print("\nSee the script header for all available configuration options.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())