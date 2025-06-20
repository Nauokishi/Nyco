import discord
from discord.ext import commands
from discord import app_commands # Required for app_commands.Command

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Shows help for commands.")
    async def help(self, ctx: commands.Context, command_name: str = None):
        """Shows help for a specific command or lists all commands."""
        embed = discord.Embed(title="Bot Help", color=discord.Color.blue())

        if command_name is None:
            # General help: List all cogs and their commands
            embed.description = "Here's a list of available commands and cogs:"

            # Iterate through cogs
            for cog_name, cog in self.bot.cogs.items():
                cog_commands = []
                # Get hybrid commands and regular commands from the cog
                for cmd in cog.get_commands():
                    if isinstance(cmd, commands.HybridCommand):
                        cog_commands.append(f"`{cmd.name}` (Hybrid)")
                    elif isinstance(cmd, commands.Command):
                        cog_commands.append(f"`{cmd.name}` (Prefix only)")

                # Get slash commands (app_commands) registered directly to the tree, if any are associated with this cog logic
                # This part is a bit tricky as app_commands are not directly part of cogs in the same way
                # For simplicity, we'll primarily list commands registered via commands.Cog.
                # App commands directly added to bot.tree and not in cogs need separate listing if desired.

                if cog_commands:
                    embed.add_field(name=f"**{cog_name}**", value="\n".join(cog_commands), inline=False)

            # Listing app_commands (slash commands not necessarily in cogs)
            # This might duplicate if hybrid commands are also fetched via bot.tree.get_commands()
            # and not filtered. For now, focusing on cog-based commands for general help.
            # A more sophisticated approach would be needed to de-duplicate.

        else:
            # Specific command help
            found_cmd = None
            # Check hybrid/prefix commands
            found_cmd = self.bot.get_command(command_name)

            # Check slash commands (app_commands)
            if not found_cmd:
                for cmd_obj in self.bot.tree.get_commands():
                    if cmd_obj.name == command_name:
                        found_cmd = cmd_obj # This will be an app_commands.Command or app_commands.Group
                        break

            if found_cmd:
                embed.title = f"Help: `{found_cmd.name}`"
                description = ""
                if isinstance(found_cmd, commands.HybridCommand):
                    description = found_cmd.help or found_cmd.description or "No description available."
                    if found_cmd.aliases:
                        description += f"\n**Aliases:** {', '.join(found_cmd.aliases)}"
                    # Usage for hybrid commands can be complex; signature is a good start
                    description += f"\n**Usage:** `{self.bot.command_prefix}{found_cmd.name} {found_cmd.signature}` (Prefix)"
                    description += f"\n**Usage (Slash):** `/{found_cmd.name} {found_cmd.signature}`" # Approx usage
                elif isinstance(found_cmd, commands.Command): # Prefix-only command
                    description = found_cmd.help or "No description available."
                    if found_cmd.aliases:
                        description += f"\n**Aliases:** {', '.join(found_cmd.aliases)}"
                    description += f"\n**Usage:** `{self.bot.command_prefix}{found_cmd.name} {found_cmd.signature}`"
                elif isinstance(found_cmd, app_commands.Command): # Slash-only command
                    description = found_cmd.description or "No description available."
                    # Parameters for slash commands
                    if found_cmd.parameters:
                        params = " ".join([f"<{param.name}>" for param in found_cmd.parameters])
                        description += f"\n**Usage (Slash):** `/{found_cmd.name} {params}`"
                else: # Potentially an app_commands.Group or other type
                     description = found_cmd.description or "Details not available for this command type."

                embed.description = description
            else:
                embed.description = f"Command `{command_name}` not found."
                embed.color = discord.Color.red()

        await ctx.send(embed=embed, ephemeral=True if command_name else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
