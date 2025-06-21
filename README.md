# Discord Bot with Music, Auto-Updates, and Version Control

A multi-functional Discord bot built with Python using the `discord.py` library. It features a music player, administrative commands, and a system for automatic updates from a Git repository and version switching.

## Features

*   **Music Player:**
    *   Play songs from YouTube (URL or search).
    *   Song queuing, pause, resume, stop, skip.
    *   Volume control.
    *   `nowplaying` and `queue` display.
    *   Autoplay related songs when the queue is empty.
    *   Song suggestions.
    *   Auto-disconnects when idle and alone in a voice channel.
*   **Admin & Version Control:**
    *   Automatic updates from a specified Git branch.
    *   Commands for bot owners to:
        *   Switch the bot to different Git tags, branches, or commits (`!switch_version`).
        *   Tag the current running version locally (`!tag_version`).
        *   View the current Git version details (`!current_version`).
        *   List all local Git tags (`!list_tags`).
        *   View the latest lines from the bot's log file (`!view_log`).
*   **Extensible Cog System:** Easily add more features through cogs.

## Prerequisites

*   Python 3.8+
*   Git
*   FFmpeg (for music playback, typically installed separately and added to PATH)
    *   On Debian/Ubuntu: `sudo apt update && sudo apt install ffmpeg`
    *   On Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-name>
    ```

2.  **Create `config.json`:**
    In the root directory of the project, create a file named `config.json` with the following content:

    ```json
    {
      "BOT_TOKEN": "YOUR_DISCORD_BOT_TOKEN_HERE",
      "PREFIX": "!"
    }
    ```
    *   Replace `"YOUR_DISCORD_BOT_TOKEN_HERE"` with your actual Discord bot token.
    *   You can change the `"PREFIX"` to your desired command prefix.
    *   **Important:** Keep your `BOT_TOKEN` secret. This `config.json` file should ideally be listed in your `.gitignore` file to prevent accidentally committing your token.

3.  **Install Dependencies:**
    Ensure your `requirements.txt` file (located in the root of the repository) includes at least:
    ```txt
    discord.py>=2.0.0
    yt-dlp
    PyNaCl
    ```
    Then install them:
    ```bash
    pip install -r requirements.txt
    ```
    *(The `run_bot_manager.py` script will also attempt to run this on updates/version switches if `requirements.txt` is present).*

## Running the Bot

The bot is designed to be run using the `run_bot_manager.py` script, which handles starting the bot, automatic updates, and version control.

1.  **Configure `run_bot_manager.py` (Optional):**
    Open `run_bot_manager.py` in a text editor. You can adjust variables at the top of the script:
    *   `GIT_BRANCH`: Default branch for auto-updates (e.g., "main").
    *   `CHECK_INTERVAL_SECONDS`: How often to check for updates (e.g., 300 for 5 minutes).

2.  **Run the Bot Manager Script:**
    ```bash
    python3 run_bot_manager.py
    ```
    *   The manager script will start. It will then launch `bot.py` as a subprocess.
    *   Logs from the manager script itself will be saved to `bot_manager.log`.
    *   Logs from `bot.py` (the Discord bot) will be saved to `bot.log`.
    *   The manager script will periodically check for updates from the configured `GIT_BRANCH`.

## Basic Usage Examples

*(Assuming default prefix `!`)*

**Music Commands:**
*   `!join`: Bot joins your voice channel.
*   `!play <song name or youtube url>`: Plays a song or adds it to the queue.
*   `!pause`: Pauses the current song.
*   `!resume`: Resumes the current song.
*   `!skip`: Skips the current song.
*   `!queue`: Shows the current song queue.
*   `!nowplaying`: Shows the song currently playing.
*   `!autoplay`: Toggles autoplay of related songs.
*   `!leave`: Bot leaves the voice channel.

**Admin Commands (Owner Only):**
*   `!current_version`: Shows the bot's current Git version details.
*   `!list_tags`: Lists all local Git tags.
*   `!tag_version v1.0.0`: Tags the current running version as `v1.0.0` locally.
*   `!switch_version develop`: Switches the bot to the `develop` branch (bot will restart).
*   `!switch_version v1.0.0`: Switches the bot to tag `v1.0.0` (bot will restart).
*   `!view_log 50`: Shows the last 50 lines from `bot.log`.

## Production Deployment

For running the bot reliably in a production environment, consider using a process manager like `systemd` (common on Linux) or `supervisor` to manage the `run_bot_manager.py` script. This provides features like auto-restarting the manager (and thus the bot) on crashes or server reboot, and can offer more advanced log management.

The `run_bot_manager.py` script itself logs its operations to `bot_manager.log`, and the Discord bot's (`bot.py`) output is logged to `bot.log`.

Example `systemd` service file (`/etc/systemd/system/discordbot.service`):
```ini
[Unit]
Description=Discord Bot with Python Manager
After=network.target

[Service]
User=your_username          # Replace with the user the bot should run as
Group=your_groupname        # Replace with the group for the user
WorkingDirectory=/path/to/your/bot/repo # Absolute path to the bot's repository root
ExecStart=/usr/bin/python3 /path/to/your/bot/repo/run_bot_manager.py # Adjust python3 path if needed
Restart=always
RestartSec=10
# StandardOutput and StandardError can be managed by systemd's journal
# or redirected to files if preferred, though the script already logs.
# StandardOutput=journal
# StandardError=journal

[Install]
WantedBy=multi-user.target
```
After creating/editing the service file:
1.  Reload systemd: `sudo systemctl daemon-reload`
2.  Enable the service to start on boot: `sudo systemctl enable discordbot.service`
3.  Start the service: `sudo systemctl start discordbot.service`
4.  Check status: `sudo systemctl status discordbot.service`
5.  View logs (if using journal): `journalctl -u discordbot.service -f`
```
