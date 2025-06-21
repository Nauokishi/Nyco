import discord
from discord.ext import commands
import os
import asyncio
import json # For loading config.json
import sys # For exiting gracefully

# --- Configuration Loading ---
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "BOT_TOKEN": "YOUR_DISCORD_BOT_TOKEN_HERE",
    "PREFIX": "!"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        print(f"Please create it with the following structure:\n{json.dumps(DEFAULT_CONFIG, indent=2)}")
        sys.exit(1) # Exit if config is missing

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding '{CONFIG_FILE}': {e}")
        print("Please ensure it's valid JSON.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while loading '{CONFIG_FILE}': {e}")
        sys.exit(1)

    # Validate critical keys
    if not config.get("BOT_TOKEN") or config["BOT_TOKEN"] == DEFAULT_CONFIG["BOT_TOKEN"]:
        print(f"Error: 'BOT_TOKEN' is missing or not set in '{CONFIG_FILE}'.")
        print("Please add your bot token to the configuration file.")
        sys.exit(1)

    if not config.get("PREFIX"):
        print(f"Warning: 'PREFIX' not found in '{CONFIG_FILE}'. Using default prefix: '{DEFAULT_CONFIG['PREFIX']}'")
        config["PREFIX"] = DEFAULT_CONFIG["PREFIX"]

    return config

config_data = load_config()
# --- End Configuration Loading ---


# Define intents
intents = discord.Intents.default()
intents.message_content = True # Enable message content intent if needed for your bot
intents.guilds = True # Explicitly enable guilds intent

# Create an instance of the bot
bot = commands.Bot(command_prefix=config_data["PREFIX"], intents=intents)
tree = bot.tree # Added for slash commands

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    # Sync application commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

async def load_all_cogs():
    """Loads all cogs from the cogs directory."""
    print("Loading cogs...")
    # Ensure cogs directory exists
    if not os.path.isdir('./cogs'):
        print("Warning: 'cogs' directory not found. No cogs will be loaded.")
        return

    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Successfully loaded cog: {filename[:-3]}')
            except commands.ExtensionNotFound:
                 print(f'Cog not found: {filename[:-3]}. Skipping.')
            except commands.NoEntryPointError:
                print(f'Cog {filename[:-3]} does not have a setup function. Skipping.')
            except commands.ExtensionFailed as e:
                print(f'Failed to load cog: {filename[:-3]}. Error: {e.original}') # Access original error
            except Exception as e:
                print(f'An unexpected error occurred loading cog: {filename[:-3]}. Error: {e}')
    print("Cog loading complete.")

async def main():
    """Main function to setup and run the bot."""
    async with bot:
        # It's good practice to remove the default help command if you have a custom one in a cog
        # bot.remove_command('help')
        # Check if HelpCog is loaded, if so, then remove default.
        # For now, assuming help might be in a cog. If not, this line might cause an error if no custom help is loaded.
        # Let's make it safer:
        try:
            bot.remove_command('help')
            print("Removed default help command. Expecting a custom one from a cog.")
        except Exception: # Default help command might not exist if intents are minimal or already removed
            print("Default help command not found or already removed.")

        await load_all_cogs()
        try:
            await bot.start(config_data["BOT_TOKEN"])
        except discord.LoginFailure:
            print("Error: Failed to log in with the provided BOT_TOKEN. Please check your token in config.json.")
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred while trying to start the bot: {e}")
            sys.exit(1)


# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutdown requested by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"Critical error in main execution: {e}")
        sys.exit(1)
