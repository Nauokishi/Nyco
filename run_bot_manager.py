import subprocess
import time
import os
import sys
import shlex # For safely splitting command strings if needed, though Popen list args are safer

# --- Configuration ---
BOT_SCRIPT_NAME = "bot.py"  # The actual discord bot script
GIT_BRANCH = "main"  # Default branch for auto-updates
CHECK_INTERVAL_SECONDS = 300  # Check for git updates every 5 minutes
REPO_PATH = "."  # Path to the bot's repository (current directory)
BOT_PID_FILE = ".bot_pid"  # File to store the bot's PID
VERSION_SWITCH_REQUEST_FILE = ".version_switch_request" # File signaling a version switch
MANAGER_LOG_FILE = "bot_manager.log" # Log for this manager script
BOT_LOG_FILE = "bot.log" # Log for the bot.py script

bot_process = None # Holds the bot's subprocess object

# --- Logging ---
def log_message(message):
    """Logs a message to stdout and to the manager's log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    final_message = f"[{timestamp}] [Manager] {message}\n"
    print(final_message.strip())
    try:
        with open(os.path.join(REPO_PATH, MANAGER_LOG_FILE), "a", encoding="utf-8") as f:
            f.write(final_message)
    except Exception as e:
        print(f"[{timestamp}] [Manager] Critical: Failed to write to manager log: {e}")

# --- Subprocess Execution ---
def run_command(command_args, in_repo_path=True, suppress_output=False, timeout=60):
    """Runs a system command, logs its output, and returns stdout, stderr, and return code."""
    log_message(f"Running command: {' '.join(command_args)}")
    try:
        process = subprocess.Popen(
            command_args,
            cwd=REPO_PATH if in_repo_path else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(timeout=timeout)

        if not suppress_output: # Log output unless suppressed
            if stdout: log_message(f"Stdout: {stdout.strip()}")
            if stderr: log_message(f"Stderr: {stderr.strip()}")

        if process.returncode != 0:
            log_message(f"Command failed with code {process.returncode}.")

        return stdout.strip() if stdout else "", stderr.strip() if stderr else "", process.returncode
    except subprocess.TimeoutExpired:
        log_message(f"Command {' '.join(command_args)} timed out after {timeout} seconds.")
        process.kill() # Ensure process is killed on timeout
        return "", f"Command timed out after {timeout} seconds.", -1 # Arbitrary non-zero code for timeout
    except FileNotFoundError:
        log_message(f"Error: Command '{command_args[0]}' not found. Ensure it's installed and in PATH.")
        return "", f"Command '{command_args[0]}' not found.", -1
    except Exception as e:
        log_message(f"Error running command {' '.join(command_args)}: {e}")
        return "", str(e), -1

# --- Bot Process Management ---
def start_bot():
    """Starts the bot.py script as a subprocess."""
    global bot_process
    if bot_process and bot_process.poll() is None:
        log_message("Bot process is already running.")
        return True

    log_message(f"Starting bot script: {BOT_SCRIPT_NAME}")
    try:
        bot_log_path = os.path.join(REPO_PATH, BOT_LOG_FILE)
        with open(bot_log_path, "a", encoding="utf-8") as bot_logfile:
            # Use sys.executable to ensure the same Python interpreter is used for the bot
            bot_process = subprocess.Popen(
                [sys.executable, BOT_SCRIPT_NAME],
                cwd=REPO_PATH,
                stdout=bot_logfile,
                stderr=subprocess.STDOUT # Redirect bot's stderr to its stdout (then to bot_logfile)
            )

        # Store PID
        pid_file_path = os.path.join(REPO_PATH, BOT_PID_FILE)
        with open(pid_file_path, "w", encoding="utf-8") as f:
            f.write(str(bot_process.pid))
        log_message(f"Bot started with PID {bot_process.pid}. Output redirected to {bot_log_path}")
        return True
    except Exception as e:
        log_message(f"Failed to start bot: {e}")
        bot_process = None
        return False

def stop_bot():
    """Stops the bot subprocess gracefully, then forcefully if necessary."""
    global bot_process
    pid_file_path = os.path.join(REPO_PATH, BOT_PID_FILE)

    pid_to_stop = None
    if bot_process and bot_process.poll() is None:
        pid_to_stop = bot_process.pid
        log_message(f"Stopping bot process (PID {pid_to_stop})...")
        bot_process.terminate() # SIGTERM
        try:
            bot_process.wait(timeout=10)
            log_message("Bot process terminated gracefully.")
        except subprocess.TimeoutExpired:
            log_message("Bot process did not terminate gracefully, killing...")
            bot_process.kill() # SIGKILL
            bot_process.wait() # Ensure it's reaped
            log_message("Bot process killed.")
    elif os.path.exists(pid_file_path): # If script restarted and bot_process is None, try PID file
        try:
            with open(pid_file_path, 'r', encoding="utf-8") as f:
                pid_to_stop = int(f.read().strip())
            log_message(f"Found PID {pid_to_stop} in {BOT_PID_FILE}. Attempting to stop external bot process...")
            os.kill(pid_to_stop, 15) # SIGTERM
            time.sleep(5) # Give it time to stop
            os.kill(pid_to_stop, 9) # SIGKILL if still running (will raise ProcessLookupError if not)
            log_message(f"Sent kill signals to PID {pid_to_stop}.")
        except ProcessLookupError:
            log_message(f"Process with PID {pid_to_stop} not found (already stopped).")
        except ValueError:
            log_message(f"Invalid PID found in {BOT_PID_FILE}.")
        except Exception as e:
            log_message(f"Error stopping bot process via PID file: {e}")
    else:
        log_message("Bot process not running or PID unknown.")

    if os.path.exists(pid_file_path):
        try:
            os.remove(pid_file_path)
        except OSError as e:
            log_message(f"Warning: Could not remove PID file {pid_file_path}: {e}")
    bot_process = None

# --- Git and Dependencies ---
def check_and_install_dependencies():
    """Checks and installs dependencies from requirements.txt."""
    requirements_path = os.path.join(REPO_PATH, "requirements.txt")
    if not os.path.exists(requirements_path):
        log_message("requirements.txt not found. Skipping dependency check.")
        return True # Not an error if no requirements file

    log_message("Checking/installing dependencies from requirements.txt...")
    # Use sys.executable to ensure pip is from the correct Python environment
    _, stderr, returncode = run_command(
        [sys.executable, "-m", "pip", "install", "-r", requirements_path],
        timeout=300 # 5 minutes for pip
    )
    if returncode == 0:
        log_message("Dependencies checked/installed successfully.")
        return True
    else:
        log_message(f"Error installing dependencies. Pip stderr: {stderr}")
        return False

def handle_git_operation(operation_args, success_message="Git operation successful.", failure_message="Git operation failed."):
    """Handles a git operation and returns True on success, False on failure."""
    _, stderr, returncode = run_command(["git"] + operation_args)
    if returncode == 0:
        log_message(success_message)
        return True
    else:
        log_message(f"{failure_message} Git stderr: {stderr}")
        return False

# --- Main Application Logic ---
def main_loop():
    """Main operational loop for the bot manager."""
    log_message("Bot manager started.")

    # Initial setup
    if not handle_git_operation(["fetch", "origin"], "Initial git fetch successful.", "Initial git fetch failed."):
        log_message("Exiting due to initial git fetch failure.")
        return # Critical failure

    if not check_and_install_dependencies():
        log_message("Exiting due to dependency installation failure.")
        return

    if not start_bot():
        log_message("Exiting due to initial bot start failure.")
        return

    while True:
        try:
            # 1. Check for version switch request
            version_switch_file_path = os.path.join(REPO_PATH, VERSION_SWITCH_REQUEST_FILE)
            if os.path.exists(version_switch_file_path):
                with open(version_switch_file_path, "r", encoding="utf-8") as f:
                    version_to_switch = f.read().strip()
                try:
                    os.remove(version_switch_file_path)
                except OSError as e:
                     log_message(f"Warning: Could not remove version switch file: {e}")

                if version_to_switch:
                    log_message(f"Version switch requested to: '{version_to_switch}'")
                    stop_bot()
                    if handle_git_operation(["checkout", version_to_switch], f"Successfully checked out '{version_to_switch}'.", f"Failed to checkout '{version_to_switch}'."):
                        if check_and_install_dependencies():
                            start_bot()
                        else:
                            log_message("Dependency installation failed after version switch. Bot not started.")
                    else: # Checkout failed, try to revert to default branch and restart
                        log_message(f"Attempting to revert to default branch '{GIT_BRANCH}'.")
                        handle_git_operation(["checkout", GIT_BRANCH]) # Best effort revert
                        if check_and_install_dependencies(): # Still check deps
                            start_bot()
                        else:
                            log_message("Dependency installation failed after attempting to revert. Bot not started.")
                else:
                    log_message("Version switch file was empty. Ignoring.")

            # 2. Wait for the interval
            log_message(f"Waiting for {CHECK_INTERVAL_SECONDS} seconds before next update check...")
            time.sleep(CHECK_INTERVAL_SECONDS)

            # 3. Check for remote updates
            log_message(f"Checking for updates on remote branch '{GIT_BRANCH}'...")
            if not handle_git_operation(["fetch", "origin"], "Git fetch successful.", "Git fetch failed. Skipping update cycle."):
                continue

            local_commit, _, ret_local = run_command(["git", "rev-parse", "HEAD"], suppress_output=True)
            remote_commit, _, ret_remote = run_command(["git", "rev-parse", f"origin/{GIT_BRANCH}"], suppress_output=True)

            if ret_local != 0 or ret_remote != 0 or not local_commit or not remote_commit:
                log_message("Could not determine local/remote commits for update check. Skipping.")
                continue

            if local_commit != remote_commit:
                current_branch, _, _ = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], suppress_output=True)
                if current_branch == GIT_BRANCH:
                    log_message(f"Updates found on branch '{GIT_BRANCH}'. (Local: {local_commit[:7]}, Remote: {remote_commit[:7]}). Pulling changes...")
                    stop_bot()
                    if handle_git_operation(["pull", "origin", GIT_BRANCH], "Successfully pulled updates.", "Git pull failed."):
                        if check_and_install_dependencies():
                            start_bot()
                        else:
                             log_message("Dependency installation failed after pull. Bot not started.")
                    else: # Pull failed
                        log_message("Git pull failed. Attempting to restart bot on current version.")
                        if check_and_install_dependencies(): # Still check deps just in case
                            start_bot()
                        else:
                            log_message("Dependency installation failed after failed pull. Bot not started.")
                else:
                    log_message(f"Local repo on branch '{current_branch}', not '{GIT_BRANCH}'. Skipping auto-update pull.")
            else:
                log_message("No new updates found on remote branch.")

            # 4. Check if bot subprocess is still alive
            if bot_process and bot_process.poll() is not None:
                log_message(f"Bot process (PID {bot_process.pid if bot_process else 'unknown'}) ended unexpectedly with code {bot_process.returncode}. Restarting...")
                # stop_bot() # Ensure it's fully cleaned up (already called if process ended)
                if check_and_install_dependencies(): # Check deps before restarting
                    start_bot()
                else:
                    log_message("Dependency installation failed after bot crash. Bot not restarted.")
            elif not bot_process: # If bot_process is None, it means it wasn't started or was stopped.
                 log_message("Bot process is not running. Attempting to start it.")
                 if check_and_install_dependencies():
                    start_bot()
                 else:
                    log_message("Dependency installation failed. Bot not started.")


        except KeyboardInterrupt:
            log_message("Keyboard interrupt received. Shutting down manager and bot...")
            stop_bot()
            sys.exit(0)
        except Exception as e:
            log_message(f"CRITICAL ERROR in main loop: {e}. Traceback: {sys.exc_info()}")
            log_message("Attempting to stop bot and exit manager to prevent error loop.")
            stop_bot()
            sys.exit(1) # Exit manager on unhandled critical errors in loop

if __name__ == "__main__":
    # Ensure REPO_PATH is absolute for robustness if script is called from elsewhere
    REPO_PATH = os.path.abspath(REPO_PATH)
    # Change current working directory to REPO_PATH so all file operations are relative to it
    try:
        os.chdir(REPO_PATH)
        log_message(f"Manager working directory set to: {os.getcwd()}")
    except Exception as e:
        log_message(f"Failed to change CWD to {REPO_PATH}: {e}. Exiting.")
        sys.exit(1)

    try:
        main_loop()
    except KeyboardInterrupt:
        log_message("Manager script terminated by user (Ctrl+C at global scope).")
    except Exception as e_global:
        log_message(f"CRITICAL UNHANDLED ERROR in manager script global scope: {e_global}")
        sys.exit(1)
    finally:
        log_message("Bot manager script is shutting down.")
        stop_bot() # Ensure bot is stopped if loop exits for any reason not caught by cleanup
```
