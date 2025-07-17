# Crafty Controller Discord Bot

A Discord bot for managing Minecraft servers through Crafty Controller using Discord's slash commands.

## Features

- **Slash Commands**: Modern Discord slash commands for all server management
- **Server Management**: Start, stop, restart, and kill servers
- **Status Monitoring**: Get detailed server statistics and status
- **Rich Embeds**: Beautiful formatted responses with server information
- **Error Handling**: Comprehensive error handling with user-friendly messages

## Requirements

- Python 3.8+
- discord.py >= 2.3
- A running Crafty Controller instance
- Discord bot token with appropriate permissions

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd crafty-discord-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
- `DISCORD_TOKEN`: Your Discord bot token
- `CRAFTY_URL`: URL to your Crafty Controller instance
- `CRAFTY_TOKEN`: API token for Crafty Controller

## Discord Bot Setup

### Required Permissions

Your Discord bot needs the following permissions:

#### OAuth2 Scopes
- `bot`: Basic bot permissions
- `applications.commands`: **Required for slash commands**

#### Bot Permissions
- Send Messages
- Use Slash Commands
- Embed Links
- Read Message History

### Bot Invitation URL

Use this URL format to invite your bot (replace `YOUR_CLIENT_ID` with your bot's client ID):

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2048&scope=bot%20applications.commands
```

## Slash Commands

The bot provides the following slash commands:

**Important**: All commands require a `server_id` parameter, which must be a UUID string (not an integer). Server IDs in Crafty Controller are UUID-formatted strings like `f1bf6997-9f43-4f36-b06f-9d3daefc7a8a`.

### `/start <server_id>`
Start a Crafty Controller server
- **Parameter**: `server_id` (UUID string) - UUID of the server in Crafty Controller (e.g., `f1bf6997-9f43-4f36-b06f-9d3daefc7a8a`)

### `/stop <server_id>`
Stop a Crafty Controller server
- **Parameter**: `server_id` (UUID string) - UUID of the server in Crafty Controller (e.g., `f1bf6997-9f43-4f36-b06f-9d3daefc7a8a`)

### `/restart <server_id>`
Restart a Crafty Controller server
- **Parameter**: `server_id` (UUID string) - UUID of the server in Crafty Controller (e.g., `f1bf6997-9f43-4f36-b06f-9d3daefc7a8a`)

### `/kill <server_id>`
Force kill a Crafty Controller server
- **Parameter**: `server_id` (UUID string) - UUID of the server in Crafty Controller (e.g., `f1bf6997-9f43-4f36-b06f-9d3daefc7a8a`)

### `/status <server_id>`
Check server status and statistics
- **Parameter**: `server_id` (UUID string) - UUID of the server in Crafty Controller (e.g., `f1bf6997-9f43-4f36-b06f-9d3daefc7a8a`)
- **Returns**: Detailed server information including CPU, memory, players, and world details via the `/stats` endpoint

### `/help`
Show available commands and usage information

## Usage Examples

```
/start f1bf6997-9f43-4f36-b06f-9d3daefc7a8a
/status f1bf6997-9f43-4f36-b06f-9d3daefc7a8a
/restart f1bf6997-9f43-4f36-b06f-9d3daefc7a8a
/stop f1bf6997-9f43-4f36-b06f-9d3daefc7a8a
```

## Migration Notes

### For Existing Bot Installations

If you already have this bot invited to your Discord server **before** the slash command implementation, you need to:

1. **Update Bot Permissions**: The bot now requires the `applications.commands` scope
2. **Re-invite the Bot**: Use the new invitation URL with the `applications.commands` scope
3. **Remove Old Invite (Optional)**: You can remove the old bot invitation and use the new one

### Migration Steps

1. **Update your bot invitation URL** to include the `applications.commands` scope:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2048&scope=bot%20applications.commands
   ```

2. **Visit the URL** and re-authorize the bot for your server

3. **Command Sync**: The bot will automatically sync slash commands when it starts up

4. **Verify Commands**: Type `/` in Discord to see if the bot's commands appear in the autocomplete

### Troubleshooting Migration

- **Commands not appearing**: Ensure the bot has the `applications.commands` scope
- **Permission errors**: Make sure the bot has "Use Slash Commands" permission in the server
- **Commands not syncing**: Check bot logs for sync errors on startup

## Development

### Running the Bot

```bash
python src/main.py
```

### Testing

#### Quick Testing
```bash
# Run all CI tests
python run_tests.py

# Run specific test types
python -m pytest tests/test_crafty_api.py -v
python -m pytest tests/test_crafty_api.py::TestCraftyAPIWithAioresponses -v
```

#### Manual Testing
```bash
# Follow the comprehensive manual testing guide
# See MANUAL_TESTING.md for detailed instructions
```

### Type Checking

```bash
mypy src/utils/crafty_api.py --ignore-missing-imports
```

## Configuration

The bot uses environment variables for configuration. Create a `.env` file in the root directory:

```env
DISCORD_TOKEN=your_discord_bot_token
CRAFTY_URL=http://your-crafty-controller:8443
CRAFTY_TOKEN=your_crafty_api_token
```

## Error Handling

The bot includes comprehensive error handling:

- **API Errors**: Crafty Controller API failures are handled gracefully
- **Permission Errors**: Users receive clear messages about missing permissions
- **Command Cooldowns**: Built-in cooldown handling prevents spam
- **Invalid Arguments**: User-friendly messages for invalid server IDs or parameters

## Logging

The bot logs important events including:
- Bot startup and shutdown
- Command executions
- API interactions
- Error conditions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]
