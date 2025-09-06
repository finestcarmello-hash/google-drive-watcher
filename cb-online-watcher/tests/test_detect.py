"""Unit tests for the online detection logic."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from detect import OnlineDetector


class TestOnlineDetector:
    """Test cases for the OnlineDetector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = OnlineDetector()
    
    def test_detect_online_with_is_live_true(self):
        """Test detection when is_live:true is present."""
        html = """
        <html>
            <body>
                <script>
                    var is_live = true;
                    var room_status = "public";
                </script>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is True
        assert result['confidence'] > 0
        assert any('is_live' in indicator for indicator in result['indicators'])
    
    def test_detect_offline_with_is_live_false(self):
        """Test detection when is_live:false is present."""
        html = """
        <html>
            <body>
                <script>
                    var is_live = false;
                    var room_status = "offline";
                </script>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] > 0
        assert any('is_live' in indicator for indicator in result['indicators'])
    
    def test_detect_online_with_data_room_status_public(self):
        """Test detection when data-room-status='public' is present."""
        html = """
        <html>
            <body>
                <div data-room-status="public">
                    <div class="player-embed">
                        <video></video>
                    </div>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is True
        assert result['confidence'] > 0
        assert any('data-room-status="public"' in indicator for indicator in result['indicators'])
    
    def test_detect_offline_with_room_offline_text(self):
        """Test detection when 'room is currently offline' text is present."""
        html = """
        <html>
            <body>
                <div class="offline-message">
                    <h2>This room is currently offline</h2>
                    <p>The performer is not broadcasting right now.</p>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] > 0
        assert any('room is currently offline' in indicator for indicator in result['indicators'])
    
    def test_detect_online_with_player_embed(self):
        """Test detection when player-embed class is present."""
        html = """
        <html>
            <body>
                <div class="player-embed">
                    <iframe src="player_url"></iframe>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is True
        assert result['confidence'] > 0
        assert any('player-embed' in indicator for indicator in result['indicators'])
    
    def test_detect_offline_with_offline_class(self):
        """Test detection when offline class is present."""
        html = """
        <html>
            <body>
                <div class="offline">
                    <p>This performer is not currently broadcasting</p>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] > 0
        assert any('offline div found' in indicator for indicator in result['indicators'])
    
    def test_detect_online_with_video_element(self):
        """Test detection when video element is present."""
        html = """
        <html>
            <body>
                <video controls>
                    <source src="stream_url" type="video/mp4">
                </video>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is True
        assert result['confidence'] > 0
        assert any('video element found' in indicator for indicator in result['indicators'])
    
    def test_detect_offline_with_broadcast_ended(self):
        """Test detection when 'broadcast has ended' text is present."""
        html = """
        <html>
            <body>
                <div class="status-message">
                    <h3>Broadcast has ended</h3>
                    <p>Thank you for watching!</p>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] > 0
        assert any('broadcast has ended' in indicator for indicator in result['indicators'])
    
    def test_detect_online_with_multiple_indicators(self):
        """Test detection with multiple online indicators."""
        html = """
        <html>
            <body>
                <script>
                    var is_live = true;
                </script>
                <div data-room-status="public" class="online">
                    <div class="player-embed">
                        <video></video>
                    </div>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is True
        assert result['confidence'] > 0.5  # High confidence with multiple indicators
        assert len(result['indicators']) > 3  # Multiple indicators found
    
    def test_detect_offline_with_multiple_indicators(self):
        """Test detection with multiple offline indicators."""
        html = """
        <html>
            <body>
                <script>
                    var is_live = false;
                </script>
                <div data-room-status="offline" class="offline">
                    <h2>This room is currently offline</h2>
                    <p>Broadcast has ended</p>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] > 0.5  # High confidence with multiple indicators
        assert len(result['indicators']) > 3  # Multiple indicators found
    
    def test_detect_empty_html(self):
        """Test detection with empty HTML."""
        result = self.detector.detect_status("", "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] == 0.0
        assert result['error'] == 'No HTML content provided'
    
    def test_detect_none_html(self):
        """Test detection with None HTML."""
        result = self.detector.detect_status(None, "test_user")
        
        assert result['is_online'] is False
        assert result['confidence'] == 0.0
        assert result['error'] == 'No HTML content provided'
    
    def test_detect_ambiguous_status(self):
        """Test detection with ambiguous indicators (both online and offline)."""
        html = """
        <html>
            <body>
                <script>
                    var is_live = true;
                    var room_status = "offline";
                </script>
                <div class="player-embed">
                    <div class="offline">Room is offline</div>
                </div>
            </body>
        </html>
        """
        
        result = self.detector.detect_status(html, "test_user")
        
        # Should still make a decision based on which side has more indicators
        assert result['is_online'] in [True, False]
        assert result['confidence'] >= 0.0
        assert len(result['indicators']) > 0
    
    def test_detect_multiple_statuses(self):
        """Test detection for multiple performers."""
        fetch_results = {
            "user1": {
                "html": '<script>var is_live = true;</script>',
                "error": None
            },
            "user2": {
                "html": '<div class="offline">Room is offline</div>',
                "error": None
            },
            "user3": {
                "html": None,
                "error": "Fetch error"
            }
        }
        
        results = self.detector.detect_multiple_statuses(fetch_results)
        
        assert "user1" in results
        assert results["user1"]["is_online"] is True
        
        assert "user2" in results
        assert results["user2"]["is_online"] is False
        
        assert "user3" in results
        assert results["user3"]["is_online"] is False
        assert "Fetch error" in results["user3"]["error"]
    
    def test_detect_with_malformed_html(self):
        """Test detection with malformed HTML."""
        html = "<html><body><div>This is malformed <div>HTML</div>"
        
        result = self.detector.detect_status(html, "test_user")
        
        # Should not crash and should return a result
        assert 'is_online' in result
        assert 'confidence' in result
        assert 'indicators' in result
        assert 'error' in result