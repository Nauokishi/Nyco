import discord
from discord.ext import commands
import config
import os # Added for cog loading
import asyncio # Added for main async function

# Define intents
intents = discord.Intents.default()
intents.message_content = True # Enable message content intent if needed for your bot
intents.guilds = True # Explicitly enable guilds intent

# Create an instance of the bot
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)
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
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Successfully loaded cog: {filename[:-3]}')
            except Exception as e:
                print(f'Failed to load cog: {filename[:-3]}. Error: {e}')
    print("Cog loading complete.")

async def main():
    """Main function to setup and run the bot."""
    async with bot:
        bot.remove_command('help') # Remove default help command
        await load_all_cogs()
        await bot.start(config.BOT_TOKEN)

# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
