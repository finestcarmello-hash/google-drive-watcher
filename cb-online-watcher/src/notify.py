"""Telegram notification system for the online watcher."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp
from config import Config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles Telegram notifications for performer status changes."""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot_token = config.telegram_bot_token
        self.chat_ids = config.telegram_chat_ids
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def send_message(self, message: str, chat_id: str) -> bool:
        """
        Send a message to a specific chat.
        
        Args:
            message: The message to send
            chat_id: The chat ID to send to
            
        Returns:
            True if successful, False otherwise
        """
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
                    logger.debug(f"Message sent successfully to chat {chat_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message to chat {chat_id}: "
                               f"status {response.status}, error: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending message to chat {chat_id}: {e}")
            return False
    
    async def send_notification(self, username: str, is_online: bool, 
                              confidence: float = 0.0, indicators: List[str] = None) -> bool:
        """
        Send a notification about a performer's status change.
        
        Args:
            username: The performer's username
            is_online: Whether the performer is online
            confidence: Confidence level of the detection
            indicators: List of indicators that led to this status
            
        Returns:
            True if all messages sent successfully, False otherwise
        """
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
            logger.info(f"Notification sent successfully for {username} to {total_count} chats")
            return True
        else:
            logger.warning(f"Notification partially sent for {username}: "
                          f"{success_count}/{total_count} chats successful")
            return False
    
    async def send_bulk_notification(self, status_changes: Dict[str, Dict[str, Any]]) -> bool:
        """
        Send a bulk notification for multiple status changes.
        
        Args:
            status_changes: Dictionary mapping usernames to their status info
            
        Returns:
            True if all messages sent successfully, False otherwise
        """
        if not status_changes:
            return True
        
        online_performers = [username for username, info in status_changes.items() 
                           if info.get('is_online', False)]
        offline_performers = [username for username, info in status_changes.items() 
                            if not info.get('is_online', False)]
        
        # Create bulk message
        message_parts = []
        
        if online_performers:
            message_parts.append(f"🟢 <b>ONLINE ({len(online_performers)}):</b>")
            for username in online_performers:
                profile_url = f"https://chaturbate.com/{username}/"
                message_parts.append(f"• <a href='{profile_url}'>{username}</a>")
        
        if offline_performers:
            message_parts.append(f"\n🔴 <b>OFFLINE ({len(offline_performers)}):</b>")
            for username in offline_performers:
                profile_url = f"https://chaturbate.com/{username}/"
                message_parts.append(f"• <a href='{profile_url}'>{username}</a>")
        
        message = "\n".join(message_parts)
        
        # Send to all configured chat IDs
        tasks = [self.send_message(message, chat_id) for chat_id in self.chat_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check if all messages were sent successfully
        success_count = sum(1 for result in results if result is True)
        total_count = len(self.chat_ids)
        
        if success_count == total_count:
            logger.info(f"Bulk notification sent successfully to {total_count} chats")
            return True
        else:
            logger.warning(f"Bulk notification partially sent: "
                          f"{success_count}/{total_count} chats successful")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test the Telegram bot connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        url = f"{self.base_url}/getMe"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data.get('result', {})
                        logger.info(f"Telegram bot connected: @{bot_info.get('username', 'unknown')}")
                        return True
                    else:
                        logger.error(f"Telegram API error: {data.get('description', 'Unknown error')}")
                        return False
                else:
                    logger.error(f"Telegram API HTTP error: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error testing Telegram connection: {e}")
            return False