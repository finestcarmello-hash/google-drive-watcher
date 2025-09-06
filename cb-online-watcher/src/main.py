"""Main application for the Chaturbate online watcher."""

import asyncio
import logging
import signal
import sys
from typing import Dict, Any
from pathlib import Path

from config import Config
from fetch import ProfileFetcher
from detect import OnlineDetector
from state import StateManager
from notify import TelegramNotifier


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
        """
        Check all performers and return status changes.
        
        Returns:
            Dictionary of performers with status changes
        """
        status_changes = {}
        
        async with ProfileFetcher(self.config) as fetcher:
            # Fetch all profiles concurrently
            fetch_results = await fetcher.fetch_multiple_profiles(self.config.performers)
            
            # Detect status for all performers
            detection_results = self.detector.detect_multiple_statuses(fetch_results)
            
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
        """
        Send notifications for status changes.
        
        Args:
            status_changes: Dictionary of performers with status changes
        """
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


async def main():
    """Main entry point."""
    watcher = OnlineWatcher()
    await watcher.run()


if __name__ == "__main__":
    asyncio.run(main())