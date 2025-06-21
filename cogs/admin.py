import discord
from discord.ext import commands
import subprocess
import os

# REPO_PATH should ideally be the root of the git repository.
# If this cog is in ./cogs/ and the script is in ./, then "." is correct.
REPO_PATH = "."

class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="switch_version", aliases=["checkout_version"])
    @commands.is_owner()
    async def switch_version(self, ctx: commands.Context, *, version_identifier: str):
        """Switches the bot to a specified git tag, branch, or commit hash.
        The bot will restart and briefly go offline.
        Usage: !switch_version <tag/branch/commit_hash>
        Example: !switch_version v1.2.0
        Example: !switch_version feature/new-stuff
        Example: !switch_version abc1234
        """
        if not version_identifier:
            await ctx.send("Please provide a version identifier (tag, branch, or commit hash).")
            return

        await ctx.send(f"Attempting to switch to version '{version_identifier}'...")
        try:
            # Use 'git show' which is a safe way to check if a reference is valid
            # without altering the working directory or index.
            # It will error out if the ref is invalid.
            subprocess.check_output(
                ["git", "show", "--quiet", version_identifier], # --quiet suppresses output on success
                cwd=REPO_PATH,
                stderr=subprocess.STDOUT # Redirect stderr to stdout to catch git errors
            )

            # Create the flag file for the update_and_run.sh script
            # Ensure REPO_PATH is correctly pointing to where update_and_run.sh expects the file
            flag_file_path = os.path.join(REPO_PATH, ".version_switch_request")
            with open(flag_file_path, "w") as f:
                f.write(version_identifier)
            await ctx.send(f"Request to switch to version '{version_identifier}' has been sent. The bot will restart shortly if successful. Please monitor `bot.log`.")
            # The update_and_run.sh script will detect this file and handle the switch.
        except subprocess.CalledProcessError as e:
            error_output = e.output.decode(errors='ignore').strip()
            await ctx.send(f"Error: Version '{version_identifier}' not found or is invalid. Git output:\n```\n{error_output}\n```")
        except FileNotFoundError: # If git command itself is not found
            await ctx.send("Error: Git command not found. Ensure git is installed and in PATH on the server.")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}")

    @commands.command(name="tag_version", aliases=["snapshot"])
    @commands.is_owner()
    async def tag_current_version(self, ctx: commands.Context, tag_name: str):
        """Tags the current commit with the given name locally.
        Tags are useful for marking release points (e.g., v1.0, v1.1-stable).
        Usage: !tag_version <tag_name>
        Example: !tag_version v1.0.2
        Note: To share tags with the remote repository, manually run 'git push origin <tag_name>' or 'git push --tags' on the server.
        """
        if ' ' in tag_name or not tag_name: # Basic validation for tag name
            await ctx.send("Tag name cannot contain spaces and must not be empty.")
            return
        try:
            # Check if tag already exists
            existing_tags = subprocess.check_output(["git", "tag"], cwd=REPO_PATH, text=True).splitlines()
            if tag_name in existing_tags:
                await ctx.send(f"Error: Tag '{tag_name}' already exists. Choose a different name.")
                return

            subprocess.check_output(["git", "tag", tag_name], cwd=REPO_PATH, stderr=subprocess.STDOUT)
            await ctx.send(f"Current running version successfully tagged as '{tag_name}' locally. \nTo push this tag to the remote repository (e.g., GitHub), run `git push origin {tag_name}` on the server.")
        except subprocess.CalledProcessError as e:
            await ctx.send(f"Error tagging version. Git output:\n```\n{e.output.decode(errors='ignore').strip()}\n```")
        except FileNotFoundError:
            await ctx.send("Error: Git command not found. Ensure git is installed and in PATH on the server.")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}")

    @commands.command(name="current_version", aliases=["bot_version", "git_status"])
    @commands.is_owner()
    async def current_version_status(self, ctx: commands.Context):
        """Displays the current git branch, commit hash, and any tags pointing to it."""
        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_PATH, text=True).strip()
            commit_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_PATH, text=True).strip()
            tags = subprocess.check_output(["git", "tag", "--points-at", "HEAD"], cwd=REPO_PATH, text=True).strip()

            message = f"**Current Bot Version:**\n"
            message += f"- Branch: `{branch}`\n"
            message += f"- Commit: `{commit_hash}`\n"
            if tags:
                message += f"- Tags: `{tags.replace('\\n', ', ')}`"
            else:
                message += "- Tags: `No tags on current commit.`"

            # Get last commit details
            commit_details = subprocess.check_output(
                ["git", "log", "-1", "--pretty=format:%h %an, %ar : %s"],
                cwd=REPO_PATH, text=True
            ).strip()
            message += f"\n- Last Commit: `{commit_details}`"

            await ctx.send(message)
        except subprocess.CalledProcessError as e:
            await ctx.send(f"Error getting current version details. Git output:\n```\n{e.output.decode(errors='ignore').strip()}\n```")
        except FileNotFoundError:
            await ctx.send("Error: Git command not found. Ensure git is installed and in PATH on the server.")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}")

    @commands.command(name="list_tags", aliases=["get_tags", "show_tags"])
    @commands.is_owner()
    async def list_tags(self, ctx: commands.Context):
        """Lists all local git tags in the repository."""
        try:
            tags_output = subprocess.check_output(["git", "tag"], cwd=REPO_PATH, text=True, stderr=subprocess.STDOUT)
            tags = tags_output.strip().splitlines()

            if not tags:
                await ctx.send("No local tags found in the repository.")
                return

            # Format tags for better readability, especially if many
            if len(tags) > 20: # If more than 20 tags, indicate count and show first 20
                message = f"Found {len(tags)} local tags. Showing the first 20:\n```\n" + "\n".join(tags[:20]) + "\n```"
                if len(tags) > 20:
                    message += "\n(And more...)"
            else:
                message = "Local git tags:\n```\n" + "\n".join(tags) + "\n```"

            await ctx.send(message)

        except subprocess.CalledProcessError as e:
            # This might happen if `git tag` itself fails for some reason, though unlikely for a simple listing.
            # Or if the repo is not a git repo, but other commands would likely fail first.
            error_output = e.output.decode(errors='ignore').strip()
            if "not a git repository" in error_output.lower(): # More specific error
                 await ctx.send("Error: The current directory does not seem to be a git repository.")
            else:
                await ctx.send(f"Error listing tags. Git output:\n```\n{error_output}\n```")
        except FileNotFoundError:
            await ctx.send("Error: Git command not found. Ensure git is installed and in PATH on the server.")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred while listing tags: {str(e)}")

    @commands.command(name="view_log", aliases=["show_log", "botlog"])
    @commands.is_owner()
    async def view_log(self, ctx: commands.Context, lines: int = 20):
        """Displays the last N lines from bot.log.
        Usage: !view_log [number_of_lines]
        Example: !view_log 50
        Defaults to 20 lines if no number is provided.
        """
        if lines <= 0:
            await ctx.send("Number of lines must be a positive integer.")
            return

        log_file_path = os.path.join(REPO_PATH, "bot.log") # Assuming bot.log is in REPO_PATH

        try:
            if not os.path.exists(log_file_path):
                await ctx.send(f"Log file (`{log_file_path}`) not found.")
                return

            if os.path.getsize(log_file_path) == 0:
                await ctx.send(f"Log file (`{log_file_path}`) is empty.")
                return

            # Read the last N lines efficiently
            # Using subprocess to call `tail` is generally robust and efficient for this.
            try:
                log_output = subprocess.check_output(
                    ["tail", "-n", str(lines), log_file_path],
                    text=True,
                    stderr=subprocess.STDOUT
                )
            except FileNotFoundError: # If `tail` command is not found (less likely on Linux/macOS)
                # Fallback to Python read if tail is not available
                with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
                    all_lines = f.readlines()
                log_output = "".join(all_lines[-lines:])


            if not log_output.strip():
                await ctx.send(f"The last {lines} lines of the log are empty or contain only whitespace.")
                return

            # Discord message character limit is 2000.
            # Add triple backticks for code block, and "Last X lines of bot.log:\n"
            header = f"Last {lines} lines of `bot.log`:\n"
            max_len_for_log = 2000 - len(header) - 7 # 7 for ```\n and \n```

            if len(log_output) > max_len_for_log:
                # If too long, send as a file or truncate
                # Sending as file is better for large logs
                try:
                    with open(log_file_path, 'rb') as fp: # Read as bytes for file sending
                        discord_file = discord.File(fp, filename="bot_log_tail.txt")
                    await ctx.send(f"The log output is too long. Here are the last {lines} lines as an attachment:", file=discord_file)
                except Exception as e_file:
                    await ctx.send(f"Log output is too long, and I couldn't send it as a file: {str(e_file)}. Here's a truncated version:\n```\n{log_output[-max_len_for_log:]}\n```")

            else:
                await ctx.send(f"{header}```\n{log_output.strip()}\n```")

        except subprocess.CalledProcessError as e:
            # This could happen if `tail` fails for some reason.
            await ctx.send(f"Error reading log with tail: {e.output.decode(errors='ignore').strip()}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred while viewing the log: {str(e)}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
    print("AdminCog loaded with version control commands.")
