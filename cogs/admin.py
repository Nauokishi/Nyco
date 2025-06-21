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

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
    print("AdminCog loaded with version control commands.")
