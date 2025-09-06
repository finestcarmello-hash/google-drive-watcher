"""CSS selectors and patterns for detecting online/offline status."""

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