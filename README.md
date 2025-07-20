# Crafty-Discord-Bot Deployment Guide

This guide will walk you through the process of setting up and running the Crafty Discord Bot on your local system.

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python 3.10 or higher**
*   **Git**

## Step-by-Step Deployment

### 1. Clone the Repository

First, clone the repository to your local machine using Git:

```bash
git clone https://github.com/oxon1um/crafty-discord-bot.git
cd crafty-discord-bot
```   

### 2. Create a Virtual Environment

It is highly recommended to use a virtual environment to manage the project's dependencies. Create and activate a virtual environment by running the following commands in the project's root directory:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

Install the required Python packages using the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root of the project directory. This file will store your sensitive credentials. The bot supports two authentication modes for Crafty Controller:

#### Static Token Mode (Recommended)

```
DISCORD_TOKEN=your_discord_bot_token_here
CRAFTY_URL=http://your_crafty_controller_url_here
CRAFTY_TOKEN=your_crafty_api_token_here
SERVER_ID=your_minecraft_server_uuid_here
GUILD_ID=your_discord_server_id_here
```

#### Automatic Authentication Mode

```
DISCORD_TOKEN=your_discord_bot_token_here
CRAFTY_URL=http://your_crafty_controller_url_here
CRAFTY_USERNAME=your_crafty_username_here
CRAFTY_PASSWORD=your_crafty_password_here
SERVER_ID=your_minecraft_server_uuid_here
GUILD_ID=your_discord_server_id_here
```

#### Environment Variables

*   `DISCORD_TOKEN`: Your Discord bot's token from the Discord Developer Portal.
*   `CRAFTY_URL`: The URL of your Crafty Controller instance.
*   `SERVER_ID`: The UUID of the Minecraft server you want to manage.
*   `GUILD_ID`: The ID of your Discord server (optional - for instant command syncing).

**Authentication Variables (choose one mode):**

*   `CRAFTY_TOKEN`: Your Crafty Controller API token (static token mode).
*   `CRAFTY_USERNAME` + `CRAFTY_PASSWORD`: Your Crafty Controller credentials (automatic mode).

## Authentication Modes

### Static Token Mode

Uses a pre-generated API token from Crafty Controller. This is the simplest and most secure method:

**Advantages:**
- Simple configuration
- No credential storage
- Immediate authentication
- No token expiration management

**Example:**
```bash
DISCORD_TOKEN=your_discord_bot_token_here
CRAFTY_URL=http://localhost:8443
CRAFTY_TOKEN=your_static_api_token_here
SERVER_ID=12345678-1234-1234-1234-123456789abc
GUILD_ID=987654321098765432
```

### Automatic Authentication Mode

Uses username and password to automatically obtain and manage API tokens:

**Advantages:**
- Automatic token refresh
- Handles token expiration
- Persistent token caching
- Proactive refresh before expiration

**Example:**
```bash
DISCORD_TOKEN=your_discord_bot_token_here
CRAFTY_URL=http://localhost:8443
CRAFTY_USERNAME=your_crafty_username
CRAFTY_PASSWORD=your_crafty_password
SERVER_ID=12345678-1234-1234-1234-123456789abc
GUILD_ID=987654321098765432
```

**Note:** If both `CRAFTY_TOKEN` and username/password are provided, the static token takes precedence.

## Token Caching and Security

When using automatic authentication mode, the bot implements secure token caching:

### Cache Location
- Tokens are cached in `~/.crafty_token_cache.json`
- File permissions are automatically set to owner-only (0600)
- Cache persists across bot restarts

### Security Practices
- Cache files have restricted permissions (readable/writable only by the owner)
- Tokens are automatically refreshed before expiration
- Cache is validated on startup and cleared if corrupted or expired
- Correlation IDs are used for secure logging without exposing sensitive data

### Cache Management
- Tokens are proactively refreshed 4 hours before expiration
- Background refresh tasks handle token renewal automatically
- Failed authentication attempts use exponential backoff retry
- Cache can be manually cleared by deleting the cache file

### 5. Run the Bot

Once you have configured the environment variables, you can run the bot with the following command:

```bash
python src/main.py
```

### 6. Verify the Bot is Running

If the bot starts successfully, you will see output in your terminal indicating that the bot has connected to Discord. You should also see the bot appear as "online" in your Discord server.

## Troubleshooting

### General Issues

*   **`ModuleNotFoundError`**: If you encounter a `ModuleNotFoundError`, ensure that you have activated the virtual environment and installed the dependencies as described in steps 2 and 3.
*   **Permission Errors**: If the bot is not responding to commands, make sure you have invited it to your Discord server with the correct permissions (applications.commands).

### Authentication Issues

#### Static Token Mode
*   **Authentication Errors**: Double-check that your `DISCORD_TOKEN`, `CRAFTY_URL`, and `CRAFTY_TOKEN` are correct in the `.env` file.
*   **Token Invalid**: Ensure your Crafty API token hasn't expired or been revoked in the Crafty Controller interface.

#### Automatic Authentication Mode
*   **Login Failures**: Verify your `CRAFTY_USERNAME` and `CRAFTY_PASSWORD` are correct and the account has API access.
*   **Token Cache Issues**: If authentication fails repeatedly, try deleting the cache file: `rm ~/.crafty_token_cache.json`
*   **Permission Issues**: Ensure the cache directory is writable and the cache file has proper permissions (should be set automatically).

### Configuration Issues
*   **Missing Variables**: Ensure you have either `CRAFTY_TOKEN` OR both `CRAFTY_USERNAME` and `CRAFTY_PASSWORD` configured.
*   **Invalid SERVER_ID**: The `SERVER_ID` must be a valid UUID format. Check the Crafty Controller interface for the correct server ID.
*   **Connection Issues**: Verify that the `CRAFTY_URL` is accessible and Crafty Controller is running.

### Startup Validation

The bot performs comprehensive validation on startup. Check the logs for detailed error messages if startup fails:

```bash
python src/main.py
```

Look for validation messages that will help identify specific configuration issues.

