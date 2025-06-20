import discord
from discord.ext import commands

class ModerationCog(commands.Cog, name="Moderation"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Kick Command
    @commands.hybrid_command(name="kick", aliases=["yeet"], description="Kicks a member from the server.")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        """Kicks a specified member from the server.

        Args:
            member: The member to kick.
            reason: The reason for kicking the member.
        """
        if member == ctx.author:
            await ctx.send("You cannot kick yourself!", ephemeral=True)
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             await ctx.send("You cannot kick a member with higher or equal role hierarchy.", ephemeral=True)
             return
        if member.guild_permissions.administrator and not ctx.guild.owner == ctx.author :
            await ctx.send("You cannot kick an administrator unless you are the guild owner.", ephemeral=True)
            return


        guild_name = ctx.guild.name
        try:
            await member.send(f"You have been kicked from **{guild_name}**. Reason: {reason or 'No reason provided.'}")
        except discord.Forbidden:
            # Failed to send DM, but proceed with kick
            pass

        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} has been kicked. Reason: {reason or 'No reason provided.'}", ephemeral=True)

    @kick.error
    async def kick_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have the required permissions to kick members.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"Member `{error.argument}` not found. Please check the name or ID.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions to kick members. Please check my roles.", ephemeral=True)
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.Forbidden):
             await ctx.send(f"I could not kick {error.original.text}. I might lack permissions or they have a higher role.", ephemeral=True)
        else:
            await ctx.send(f"An unexpected error occurred: {error}", ephemeral=True)
            print(f"Error in kick command: {error}")


    # Ban Command
    @commands.hybrid_command(name="ban", aliases=["exile"], description="Bans a member from the server.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        """Bans a specified member from the server.

        Args:
            member: The member to ban.
            reason: The reason for banning the member.
        """
        if member == ctx.author:
            await ctx.send("You cannot ban yourself!", ephemeral=True)
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner :
             await ctx.send("You cannot ban a member with higher or equal role hierarchy.", ephemeral=True)
             return
        if member.guild_permissions.administrator and not ctx.guild.owner == ctx.author :
            await ctx.send("You cannot ban an administrator unless you are the guild owner.", ephemeral=True)
            return

        guild_name = ctx.guild.name
        try:
            await member.send(f"You have been banned from **{guild_name}**. Reason: {reason or 'No reason provided.'}")
        except discord.Forbidden:
            # Failed to send DM, but proceed with ban
            pass

        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} has been banned. Reason: {reason or 'No reason provided.'}", ephemeral=True)

    @ban.error
    async def ban_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have the required permissions to ban members.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"Member `{error.argument}` not found. Please check the name or ID.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions to ban members. Please check my roles.", ephemeral=True)
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, discord.Forbidden):
             await ctx.send(f"I could not ban {error.original.text}. I might lack permissions or they have a higher role.", ephemeral=True)
        else:
            await ctx.send(f"An unexpected error occurred: {error}", ephemeral=True)
            print(f"Error in ban command: {error}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
