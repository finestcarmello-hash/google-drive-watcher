"""Configuration management for the Chaturbate online watcher."""

import os
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for the Chaturbate online watcher."""
    
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