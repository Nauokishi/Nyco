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

2.  **Create `config.py`:**
    In the root directory of the project, create a file named `config.py` with the following content:

    ```python
    # config.py

    # Your Discord Bot Token
    # Replace "YOUR_DISCORD_BOT_TOKEN_HERE" with your actual bot token.
    BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"

    # The prefix for bot commands (e.g., !, ?, bot-)
    PREFIX = "!"
    ```
    *   **Important:** Keep your `BOT_TOKEN` secret. Do not commit `config.py` to public repositories if it contains sensitive information. Consider adding `config.py` to your `.gitignore` file.

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
    *(The `update_and_run.sh` script will also attempt to run this on updates/version switches if `requirements.txt` is present).*

## Running the Bot

The bot is designed to be run using the `update_and_run.sh` script, which handles automatic updates and version control.

1.  **Make the Script Executable (if not already):**
    ```bash
    chmod +x update_and_run.sh
    ```

2.  **Run the Script:**
    ```bash
    ./update_and_run.sh
    ```
    *   The bot will start, and its logs (including output from the `update_and_run.sh` script and `bot.py`) will be saved to `bot.log` in the project's root directory.
    *   The script will periodically check for updates from the `main` branch (configurable in the script) of your Git repository.

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

For running the bot reliably in a production environment, consider using a process manager like `systemd` or `supervisor` to manage the `update_and_run.sh` script. This provides features like auto-restarting on crashes and cleaner log management. An example `systemd` service configuration is commented within the `update_and_run.sh` script or can be found in standard Linux administration guides.
```
