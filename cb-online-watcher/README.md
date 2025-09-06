# Chaturbate Online Watcher

A production-ready Python application that monitors Chaturbate performers and sends Telegram notifications when they go online or offline.

## Features

- 🔍 **Real-time Monitoring**: Polls performer profiles every 30 seconds (configurable)
- 📱 **Telegram Notifications**: Instant alerts when performers go online/offline
- 🎯 **Smart Detection**: Advanced HTML parsing to detect online/offline status
- 💾 **State Persistence**: Remembers status between restarts to avoid duplicate notifications
- 🔄 **Debounced Alerts**: Only notifies on actual status changes
- 📊 **Comprehensive Logging**: Console and rotating file logs
- 🐳 **Docker Support**: Easy deployment with Docker
- ⚙️ **Configurable**: Extensive configuration via environment variables
- 🧪 **Tested**: Unit tests for detection logic

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd cb-online-watcher
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Run the Watcher

```bash
python -m src.main
```

## Configuration

Create a `.env` file based on `.env.example`:

### Required Settings

```env
# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Chat IDs to send notifications to (comma-separated)
TELEGRAM_CHAT_IDS=123456789,987654321

# Performers to monitor (comma-separated usernames)
PERFORMERS=username1,username2,username3
```

### Optional Settings

```env
# Polling interval in seconds (default: 30)
POLL_INTERVAL=30

# Jitter range in seconds (default: 5)
JITTER_RANGE=5

# Log level (default: INFO)
LOG_LEVEL=INFO

# Request timeout in seconds (default: 30)
REQUEST_TIMEOUT=30
```

## Getting Started

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Use `/newbot` command and follow instructions
3. Copy the bot token to your `.env` file

### 2. Get Chat IDs

1. Add your bot to a group or start a private chat
2. Send a message to the bot
3. Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the `chat.id` in the response and add it to `TELEGRAM_CHAT_IDS`

### 3. Configure Performers

Add Chaturbate usernames to the `PERFORMERS` variable in your `.env` file:

```env
PERFORMERS=performer1,performer2,performer3
```

### 4. Run the Application

```bash
python -m src.main
```

## Project Structure

```
cb-online-watcher/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
├── .gitignore               # Git ignore rules
├── Dockerfile               # Docker configuration
├── Makefile                 # Build and run commands
├── src/                     # Source code
│   ├── __init__.py
│   ├── main.py              # Main application entry point
│   ├── config.py            # Configuration management
│   ├── fetch.py             # HTML fetching module
│   ├── detect.py            # Online/offline detection
│   ├── state.py             # State persistence
│   ├── notify.py            # Telegram notifications
│   └── selectors.py         # Detection patterns
├── tests/                   # Unit tests
│   └── test_detect.py       # Detection logic tests
└── logs/                    # Log files (created at runtime)
    └── online_watcher.log   # Application logs
```

## Usage

### Command Line

```bash
# Run the watcher
python -m src.main

# Run tests
python -m pytest tests/ -v

# Install dependencies
pip install -r requirements.txt
```

### Using Make

```bash
# Install dependencies
make install

# Run tests
make test

# Run the watcher
make run

# Clean up generated files
make clean
```

### Using Docker

```bash
# Build Docker image
make docker-build

# Run in Docker container
make docker-run

# Stop Docker container
make docker-stop
```

## Detection Logic

The application uses multiple methods to detect online/offline status:

### Online Indicators
- `is_live:true` in JavaScript
- `data-room-status="public"` or `data-room-status="group"`
- Presence of `player-embed`, `video-player`, or `live-player` elements
- Text patterns like "currently broadcasting", "is live now"
- Video elements in the page

### Offline Indicators
- `is_live:false` in JavaScript
- `data-room-status="offline"` or `data-room-status="private"`
- Text patterns like "room is currently offline", "broadcast has ended"
- Offline-specific CSS classes

### Confidence Scoring
The detection system uses a scoring mechanism where different indicators have different weights:
- CSS selectors: 2.0 points
- Regex patterns: 1.5 points
- Text indicators: 1.0 points
- Special elements (video, player-embed): 2.0-3.0 points

## State Management

The application maintains state in `.status.json` to:
- Remember the last known status of each performer
- Only send notifications when status actually changes
- Persist state across application restarts
- Avoid duplicate notifications

## Logging

Logs are written to both console and file (`logs/online_watcher.log`):
- **Console**: Real-time monitoring
- **File**: Persistent logs with rotation (10MB max, 5 backups)

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_detect.py -v

# Run with coverage
python -m pytest tests/ --cov=src
```

The tests cover:
- Online/offline detection with various HTML patterns
- Error handling for malformed HTML
- Multiple performer detection
- Edge cases and ambiguous status

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t cb-online-watcher .

# Run with environment file
docker run -d \
  --name cb-watcher \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.status.json:/app/.status.json \
  cb-online-watcher
```

### Docker Compose (Optional)

Create a `docker-compose.yml`:

```yaml
version: '3.8'
services:
  cb-watcher:
    build: .
    env_file: .env
    volumes:
      - ./logs:/app/logs
      - ./.status.json:/app/.status.json
    restart: unless-stopped
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | - | **Required** - Telegram bot token |
| `TELEGRAM_CHAT_IDS` | - | **Required** - Comma-separated chat IDs |
| `PERFORMERS` | - | **Required** - Comma-separated usernames |
| `POLL_INTERVAL` | 30 | Polling interval in seconds |
| `JITTER_RANGE` | 5 | Jitter range in seconds |
| `REQUEST_TIMEOUT` | 30 | HTTP request timeout |
| `LOG_LEVEL` | INFO | Logging level |
| `LOG_FILE` | logs/online_watcher.log | Log file path |
| `LOG_MAX_BYTES` | 10485760 | Max log file size (10MB) |
| `LOG_BACKUP_COUNT` | 5 | Number of backup log files |
| `STATE_FILE` | .status.json | State persistence file |
| `USER_AGENT` | Mozilla/5.0... | HTTP User-Agent string |

## Troubleshooting

### Common Issues

1. **"TELEGRAM_BOT_TOKEN is required"**
   - Make sure you've created a bot with @BotFather
   - Check that the token is correctly set in `.env`

2. **"TELEGRAM_CHAT_IDS is required"**
   - Get chat IDs from the Telegram API
   - Ensure chat IDs are comma-separated without spaces

3. **"No status changes detected"**
   - Check that performer usernames are correct
   - Verify the performers are actually going online/offline
   - Check logs for fetch errors

4. **Notifications not working**
   - Test bot connection: the app will log connection status
   - Ensure the bot is added to the target chats
   - Check that chat IDs are correct

### Debug Mode

Enable debug logging to see detailed information:

```env
LOG_LEVEL=DEBUG
```

This will show:
- Detailed detection indicators
- HTTP request/response information
- State changes and persistence
- Telegram API responses

## Development

### Adding New Detection Patterns

Edit `src/selectors.py` to add new online/offline indicators:

```python
# Add to ONLINE_INDICATORS
ONLINE_INDICATORS = [
    "your_new_indicator",
    # ... existing indicators
]

# Add to OFFLINE_INDICATORS
OFFLINE_INDICATORS = [
    "your_offline_indicator",
    # ... existing indicators
]
```

### Running in Development

```bash
# Install in development mode
pip install -e .

# Run with debug logging
LOG_LEVEL=DEBUG python -m src.main

# Run tests
python -m pytest tests/ -v
```

## License

This project is for educational and personal use only. Please respect Chaturbate's terms of service and use responsibly.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Disclaimer

This tool is for personal use only. Users are responsible for complying with all applicable terms of service and laws. The authors are not responsible for any misuse of this software.