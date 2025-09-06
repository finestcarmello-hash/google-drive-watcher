#!/usr/bin/env python3
"""
Chaturbate Watch Bot
Monitors specific performers and sends Telegram notifications when they go online.
"""

import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typing import Dict, Set, List
import json
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ChaturbateWatchBot:
    def __init__(self):
        self.usernames = self._load_usernames()
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_ids = self._load_chat_ids()
        self.poll_interval = int(os.getenv('POLL_INTERVAL', '30'))
        self.user_agent = os.getenv('USER_AGENT', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # State tracking for debouncing
        self.performer_states: Dict[str, bool] = {}
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"Bot initialized. Monitoring {len(self.usernames)} performers: {', '.join(self.usernames)}")
        logger.info(f"Polling every {self.poll_interval} seconds")

    def _load_usernames(self) -> List[str]:
        """Load and parse usernames from environment variable."""
        usernames_str = os.getenv('USERNAMES', '')
        if not usernames_str:
            raise ValueError("USERNAMES environment variable is required")
        
        usernames = [username.strip() for username in usernames_str.split(',') if username.strip()]
        if not usernames:
            raise ValueError("No valid usernames found in USERNAMES")
        
        return usernames

    def _load_chat_ids(self) -> List[str]:
        """Load and parse Telegram chat IDs from environment variable."""
        chat_ids_str = os.getenv('TELEGRAM_CHAT_IDS', '')
        if not chat_ids_str:
            raise ValueError("TELEGRAM_CHAT_IDS environment variable is required")
        
        chat_ids = [chat_id.strip() for chat_id in chat_ids_str.split(',') if chat_id.strip()]
        if not chat_ids:
            raise ValueError("No valid chat IDs found in TELEGRAM_CHAT_IDS")
        
        return chat_ids

    def _validate_config(self):
        """Validate that all required configuration is present."""
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        if not self.telegram_chat_ids:
            raise ValueError("TELEGRAM_CHAT_IDS environment variable is required")
        
        if self.poll_interval < 5:
            logger.warning("Poll interval is very low (< 5s), consider increasing to avoid rate limiting")

    def _get_performer_status(self, username: str) -> bool:
        """
        Check if a performer is online by fetching their page and parsing for online indicators.
        Returns True if online, False if offline.
        """
        url = f"https://chaturbate.com/{username}/"
        
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for offline indicators
            offline_indicators = [
                "room is currently offline",
                "currently offline",
                "offline",
                "is_live\":false",
                "data-room-status=\"offline\""
            ]
            
            page_text = response.text.lower()
            for indicator in offline_indicators:
                if indicator in page_text:
                    return False
            
            # Check for online indicators
            online_indicators = [
                "is_live\":true",
                "data-room-status=\"public\"",
                "player-embed",
                "hls_url",
                "room_status\":\"public\""
            ]
            
            for indicator in online_indicators:
                if indicator in page_text:
                    return True
            
            # Additional check: look for specific elements that indicate online status
            if soup.find('div', {'class': 'player-embed'}) or soup.find('video'):
                return True
            
            # If no clear indicators found, assume offline
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {username}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking {username}: {e}")
            return False

    def _send_telegram_notification(self, username: str, is_online: bool):
        """Send notification to all configured Telegram chat IDs."""
        status = "ONLINE" if is_online else "OFFLINE"
        message = f"🔔 Chaturbate Alert\n\nPerformer: {username}\nStatus: {status}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        for chat_id in self.telegram_chat_ids:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                data = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }
                
                response = requests.post(url, data=data, timeout=10)
                response.raise_for_status()
                
                logger.info(f"Notification sent to chat {chat_id} for {username} ({status})")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send notification to chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending notification to chat {chat_id}: {e}")

    def _check_performers(self):
        """Check all performers and send notifications for status changes."""
        for username in self.usernames:
            try:
                is_online = self._get_performer_status(username)
                previous_status = self.performer_states.get(username, None)
                
                # Update state
                self.performer_states[username] = is_online
                
                # Log status
                status_text = "ONLINE" if is_online else "OFFLINE"
                logger.info(f"{username}: {status_text}")
                
                # Send notification only on OFFLINE -> ONLINE transition
                if previous_status is not None and not previous_status and is_online:
                    logger.info(f"🚨 Status change detected: {username} went ONLINE!")
                    self._send_telegram_notification(username, is_online)
                elif previous_status is None:
                    # First time checking this performer
                    logger.info(f"Initial status for {username}: {status_text}")
                
            except Exception as e:
                logger.error(f"Error processing {username}: {e}")

    def run(self):
        """Main loop to continuously monitor performers."""
        logger.info("Starting Chaturbate Watch Bot...")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                self._check_performers()
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            raise

def main():
    """Entry point for the script."""
    try:
        bot = ChaturbateWatchBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())