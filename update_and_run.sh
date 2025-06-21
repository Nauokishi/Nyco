#!/bin/bash

BOT_SCRIPT="bot.py"
GIT_BRANCH="main" # Or your desired default branch for auto-updates
CHECK_INTERVAL=300 # Check for updates every 5 minutes (300 seconds)
REPO_PATH="." # Path to your bot's repository, defaults to current directory where this script is run

BOT_PID_FILE=".bot_pid" # File to store the bot's PID

# Function to start the bot
start_bot() {
    echo "Starting bot from script: $BOT_SCRIPT in $REPO_PATH"
    # Ensure we are in the repo path context for starting the bot
    # And redirect bot's stdout/stderr to a log file for better debugging
    (cd "$REPO_PATH" && python3 "$BOT_SCRIPT" >> bot.log 2>&1 & echo $! > "$BOT_PID_FILE")

    # Give it a moment to start and write PID
    sleep 1

    if [ -f "$REPO_PATH/$BOT_PID_FILE" ]; then
        BOT_PID=$(cat "$REPO_PATH/$BOT_PID_FILE")
        if ps -p "$BOT_PID" > /dev/null; then
            echo "Bot started successfully with PID $BOT_PID."
        else
            echo "Bot failed to start or PID file ($BOT_PID_FILE) is stale. Check bot.log."
            BOT_PID=""
        fi
    else
        echo "PID file ($BOT_PID_FILE) not found. Bot may not have started."
        BOT_PID=""
    fi
}

# Function to stop the bot
stop_bot() {
    if [ -f "$REPO_PATH/$BOT_PID_FILE" ]; then
        BOT_PID=$(cat "$REPO_PATH/$BOT_PID_FILE")
        if [ ! -z "$BOT_PID" ] && ps -p "$BOT_PID" > /dev/null; then
            echo "Stopping bot (PID $BOT_PID)..."
            kill "$BOT_PID"
            # Wait for a bit for the process to terminate
            for _ in {1..5}; do # Wait up to 5 seconds
                if ! ps -p "$BOT_PID" > /dev/null; then
                    break
                fi
                sleep 1
            done
            if ps -p "$BOT_PID" > /dev/null; then # If still running, force kill
                echo "Bot did not stop gracefully, force killing (PID $BOT_PID)..."
                kill -9 "$BOT_PID"
            fi
            echo "Bot stopped."
        else
            echo "Bot not running or PID $BOT_PID is invalid."
        fi
        rm -f "$REPO_PATH/$BOT_PID_FILE" # Clean up PID file
    else
        echo "Bot PID file not found. Assuming bot is not running."
    fi
    BOT_PID="" # Clear internal PID variable
}

# Function to check and install dependencies
check_dependencies() {
    if [ -f "$REPO_PATH/requirements.txt" ]; then
        echo "Checking/installing dependencies from requirements.txt..."
        # Compare requirements.txt with a stored hash to see if it changed,
        # or just run pip install -r every time for simplicity here.
        # For a more advanced setup, you'd check if requirements.txt was modified by the git pull/checkout.
        pip install -r "$REPO_PATH/requirements.txt"
        if [ $? -ne 0 ]; then
            echo "Error installing dependencies. Please check pip output."
            # Decide if you want to proceed or stop if dependencies fail
        fi
    fi
}

# Initial setup: Navigate to repo path if REPO_PATH is not "."
if [ "$REPO_PATH" != "." ]; then
    cd "$REPO_PATH" || { echo "Error: Could not navigate to REPO_PATH: $REPO_PATH. Exiting."; exit 1; }
fi
echo "Running in directory: $(pwd)"


# Initial git fetch to ensure remote tracking is up to date
echo "Performing initial git fetch..."
git fetch origin
if [ $? -ne 0 ]; then
    echo "Error: Initial git fetch failed. Check your git configuration and network. Exiting."
    exit 1
fi


# Start the bot for the first time
check_dependencies # Check dependencies before first start
start_bot

# Cleanup function for script exit (Ctrl+C, termination signals)
cleanup() {
    echo "Signal received. Exiting update script and stopping bot..."
    stop_bot
    # Remove version switch request file if it exists
    [ -f ".version_switch_request" ] && rm ".version_switch_request"
    echo "Cleanup complete. Exiting."
    exit 0
}
trap cleanup SIGINT SIGTERM # Trap Ctrl+C (SIGINT) and termination (SIGTERM) signals

echo "Update and run script started. Monitoring for updates and version switches."
echo "Bot log will be in bot.log. PID in .bot_pid"

# Main loop for checking updates and version switches
while true; do
    # Check for version switch request first
    if [ -f ".version_switch_request" ]; then
        VERSION_TO_SWITCH=$(cat .version_switch_request)
        # It's crucial to remove the file *before* attempting operations that might fail and loop
        rm ".version_switch_request"
        echo "Version switch requested to: $VERSION_TO_SWITCH"

        stop_bot
        echo "Attempting to checkout version: $VERSION_TO_SWITCH"
        git checkout "$VERSION_TO_SWITCH"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to checkout version '$VERSION_TO_SWITCH'."
            echo "Attempting to revert to branch '$GIT_BRANCH' and pull latest."
            git checkout "$GIT_BRANCH" # Try to revert to the main branch
            git pull origin "$GIT_BRANCH" # And pull its latest
        fi
        check_dependencies # Check dependencies after switching version
        start_bot
    fi

    # Wait for the defined interval before checking for remote updates
    # This sleep is interruptible by signals (like SIGINT/SIGTERM for cleanup)
    sleep "$CHECK_INTERVAL" &
    wait $! # Wait for sleep to complete or be interrupted

    echo "Checking for updates on remote branch '$GIT_BRANCH'..."

    # Fetch latest changes from origin
    git fetch origin
    if [ $? -ne 0 ]; then
        echo "Error: git fetch failed. Skipping this update check."
        continue # Skip to next iteration of the loop
    fi

    LOCAL_COMMIT=$(git rev-parse HEAD) # Current local commit hash
    REMOTE_COMMIT=$(git rev-parse "origin/${GIT_BRANCH}") # Latest commit hash on remote branch

    if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD) # Get current checked-out branch name
        if [ "$CURRENT_BRANCH" == "$GIT_BRANCH" ]; then
            echo "Updates found on branch '$GIT_BRANCH'. Current commit: $LOCAL_COMMIT, Remote commit: $REMOTE_COMMIT."
            echo "Pulling changes..."
            stop_bot
            git pull origin "$GIT_BRANCH"
            if [ $? -ne 0 ]; then
                echo "Error: git pull failed. The repository might be in a conflicted state."
                echo "Attempting to restart the bot on the current (potentially old) version."
                # Bot will restart on whatever state git pull left the repo in, or the old version if pull failed badly.
            fi
            check_dependencies # Check dependencies after pulling updates
            start_bot
        else
            echo "Local repository is currently on branch '$CURRENT_BRANCH', not the auto-update target branch '$GIT_BRANCH'. Skipping automatic pull."
            echo "To resume auto-updates, switch back to '$GIT_BRANCH' and ensure it tracks 'origin/$GIT_BRANCH'."
        fi
    else
        echo "No new updates found on branch '$GIT_BRANCH'. Local and remote are at commit $LOCAL_COMMIT."
    fi
done
