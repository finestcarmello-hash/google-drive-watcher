"""State persistence for tracking performer online/offline status."""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistent state for the online watcher."""
    
    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self.state: Dict[str, Any] = {}
        self._load_state()
    
    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded state from {self.state_file}")
            else:
                self.state = {
                    'performers': {},
                    'last_updated': None,
                    'version': '1.0'
                }
                logger.info(f"Created new state file: {self.state_file}")
        except Exception as e:
            logger.error(f"Error loading state from {self.state_file}: {e}")
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
            
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state to {self.state_file}: {e}")
    
    def get_performer_status(self, username: str) -> Optional[bool]:
        """
        Get the last known online status for a performer.
        
        Args:
            username: The performer's username
            
        Returns:
            True if online, False if offline, None if unknown
        """
        performer_data = self.state.get('performers', {}).get(username, {})
        return performer_data.get('is_online')
    
    def update_performer_status(self, username: str, is_online: bool, 
                              confidence: float = 0.0, indicators: list = None) -> bool:
        """
        Update the status for a performer and return if status changed.
        
        Args:
            username: The performer's username
            is_online: Current online status
            confidence: Confidence level of the detection
            indicators: List of indicators that led to this status
            
        Returns:
            True if status changed, False if unchanged
        """
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
            logger.info(f"Status changed for {username}: {previous_status} -> {is_online}")
        else:
            logger.debug(f"Status unchanged for {username}: {is_online}")
        
        return status_changed
    
    def get_all_performers(self) -> Dict[str, Dict[str, Any]]:
        """Get all performer data."""
        return self.state.get('performers', {})
    
    def clear_performer(self, username: str) -> None:
        """Remove a performer from state."""
        if 'performers' in self.state and username in self.state['performers']:
            del self.state['performers'][username]
            self._save_state()
            logger.info(f"Cleared state for performer: {username}")
    
    def clear_all_performers(self) -> None:
        """Clear all performer data."""
        self.state['performers'] = {}
        self._save_state()
        logger.info("Cleared all performer data")
    
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