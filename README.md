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

Create a `.env` file in the root of the project directory. This file will store your sensitive credentials. Add the following variables to the `.env` file, replacing the placeholder values with your actual credentials:

```
DISCORD_TOKEN=your_discord_bot_token_here
CRAFTY_URL=http://your_crafty_controller_url_here
CRAFTY_TOKEN=your_crafty_api_token_here
SERVER_ID=your_minecraft_server_uuid_here
GUILD_ID=your_discord_server_id_here
```

*   `DISCORD_TOKEN`: Your Discord bot's token from the Discord Developer Portal.
*   `CRAFTY_URL`: The URL of your Crafty Controller instance.
*   `CRAFTY_TOKEN`: Your Crafty Controller API token.
*   `SERVER_ID`: The UUID of the Minecraft server you want to manage.
*   `GUILD_ID`: The ID of your Discord server (for instant command syncing).

### 5. Run the Bot

Once you have configured the environment variables, you can run the bot with the following command:

```bash
python src/main.py
```

### 6. Verify the Bot is Running

If the bot starts successfully, you will see output in your terminal indicating that the bot has connected to Discord. You should also see the bot appear as "online" in your Discord server.

## Troubleshooting

*   **`ModuleNotFoundError`**: If you encounter a `ModuleNotFoundError`, ensure that you have activated the virtual environment and installed the dependencies as described in steps 2 and 3.
*   **Authentication Errors**: If you see authentication errors, double-check that your `DISCORD_TOKEN`, `CRAFTY_URL`, and `CRAFTY_TOKEN` in the `.env` file are correct.
*   **Permission Errors**: If the bot is not responding to commands, make sure you have invited it to your Discord server with the correct permissions (applications.commands).

