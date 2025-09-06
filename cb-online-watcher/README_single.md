# Chaturbate Online Watcher - Single File Version

A production-ready Python script that monitors Chaturbate performers and sends Telegram notifications when they go online/offline.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_single.txt
```

### 2. Configure Environment

```bash
cp .env.example.single .env
# Edit .env with your configuration
```

### 3. Run the Watcher

```bash
python cb_watcher.py
```

## Configuration

Create a `.env` file based on `.env.example.single`:

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

# State persistence file (default: .status.json)
STATE_FILE=.status.json
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
python cb_watcher.py
```

## Features

- 🔍 **Smart Detection**: Multiple detection methods for reliable online/offline status
- 📱 **Telegram Notifications**: Instant alerts with profile links
- 💾 **State Persistence**: Remembers status between restarts
- 🔄 **Debounced Alerts**: Only notifies on actual status changes
- 📊 **Comprehensive Logging**: Console and rotating file logs
- ⚙️ **Configurable**: Extensive configuration via environment variables

## Detection Methods

The script uses multiple methods to detect online/offline status:

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

## State Management

The script maintains state in `.status.json` to:
- Remember the last known status of each performer
- Only send notifications when status actually changes
- Persist state across application restarts
- Avoid duplicate notifications

## Logging

Logs are written to both console and file (`logs/online_watcher.log`):
- **Console**: Real-time monitoring
- **File**: Persistent logs with rotation (10MB max, 5 backups)

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Example Usage

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python cb_watcher.py

# Run with custom state file
STATE_FILE=my_status.json python cb_watcher.py

# Run with custom poll interval
POLL_INTERVAL=60 python cb_watcher.py
```

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
   - Test bot connection: the script will log connection status
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

## File Structure

```
cb_watcher.py              # Main application (single file)
requirements_single.txt    # Python dependencies
.env.example.single        # Configuration template
README_single.md          # This file
```

## License

This project is for educational and personal use only. Please respect Chaturbate's terms of service and use responsibly.

## Disclaimer

This tool is for personal use only. Users are responsible for complying with all applicable terms of service and laws. The authors are not responsible for any misuse of this software.