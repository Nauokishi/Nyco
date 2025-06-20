import discord
from discord.ext import commands
import datetime # Will be useful for date formatting

class UtilityCog(commands.Cog, name="Utility"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="userinfo", aliases=["whois", "memberinfo"], description="Displays information about a user.")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(title=f"User Information - {member.name}", color=member.color or discord.Color.blue())
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="Full Name", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="User ID", value=member.id, inline=True)

        created_at_unix = int(member.created_at.timestamp())
        # member.joined_at can be None if the member information is fetched via userinfo (e.g. from a user not in the current guild)
        # or if the member somehow doesn't have a join date (very unlikely in guild context).
        joined_at_unix = int(member.joined_at.timestamp()) if getattr(member, 'joined_at', None) else None


        embed.add_field(name="Account Created", value=f"<t:{created_at_unix}:F> (<t:{created_at_unix}:R>)", inline=False)
        if joined_at_unix:
            embed.add_field(name="Joined Server", value=f"<t:{joined_at_unix}:F> (<t:{joined_at_unix}:R>)", inline=False)

        # Check if member object has roles (i.e., is a Member, not just User)
        if hasattr(member, 'roles'):
            roles = [role.mention for role in member.roles[1:]] # Exclude @everyone
            if roles:
                embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(reversed(roles)) if roles else "None", inline=False)
            else:
                embed.add_field(name="Roles", value="None", inline=False)
            embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        else: # It's a discord.User, not a discord.Member
            embed.add_field(name="Roles", value="N/A (User not in this server)", inline=False)
            embed.add_field(name="Top Role", value="N/A", inline=True)


        embed.add_field(name="Bot?", value="Yes" if member.bot else "No", inline=True)

        # Status might not be available for discord.User if not in a shared guild or no presence intent
        status_value = "❔ Unknown"
        if hasattr(member, 'status'):
            status_emoji_map = {
                discord.Status.online: "🟢 Online",
                discord.Status.idle: "🟡 Idle",
                discord.Status.dnd: "🔴 Do Not Disturb",
                discord.Status.offline: "⚫ Offline",
                discord.Status.invisible: "⚪ Invisible (shows as Offline)"
            }
            status_value = status_emoji_map.get(member.status, "❔ Unknown")
        embed.add_field(name="Status", value=status_value, inline=True)


        if hasattr(member, 'activity') and member.activity:
            activity_type = member.activity.type.name.capitalize()
            activity_name = member.activity.name

            if isinstance(member.activity, discord.Spotify):
                 embed.add_field(name="Activity", value=f"Listening to {member.activity.title} by {member.activity.artist}", inline=False)
            elif isinstance(member.activity, discord.Game): # discord.Game is a specific type of Activity
                 embed.add_field(name="Activity", value=f"Playing {activity_name}", inline=False)
            elif isinstance(member.activity, discord.Streaming):
                 embed.add_field(name="Activity", value=f"Streaming {activity_name} on {member.activity.platform}", inline=False)
            elif isinstance(member.activity, discord.CustomActivity):
                 custom_activity_name = member.activity.name or ""
                 emoji_str = member.activity.emoji if member.activity.emoji else ""
                 embed.add_field(name="Activity", value=f"{emoji_str} {custom_activity_name}".strip(), inline=False)
            elif isinstance(member.activity, discord.Activity): # Generic discord.Activity
                 embed.add_field(name=f"Activity ({activity_type})", value=activity_name, inline=False)


        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware UTC now

        await ctx.send(embed=embed, ephemeral=False)

    @commands.hybrid_command(name="serverinfo", aliases=["guildinfo"], description="Displays information about the server.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        if not guild:
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Server Information - {guild.name}", color=discord.Color.blue())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Server Name", value=guild.name, inline=True)
        embed.add_field(name="Server ID", value=guild.id, inline=True)

        if guild.owner: # guild.owner can be None if the bot cannot access it or due to Discord API issues
            embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        else: # Attempt to fetch owner if not available, requires GUILD_MEMBERS intent or bot being owner
            try:
                owner = await guild.fetch_owner()
                embed.add_field(name="Owner", value=owner.mention, inline=True)
            except discord.Forbidden:
                 embed.add_field(name="Owner", value="Unknown (Bot lacks permissions to fetch owner)", inline=True)
            except Exception: # Catch other potential errors
                 embed.add_field(name="Owner", value="Unknown (Owner info unavailable)", inline=True)


        created_at_unix = int(guild.created_at.timestamp())
        embed.add_field(name="Created On", value=f"<t:{created_at_unix}:F> (<t:{created_at_unix}:R>)", inline=False)

        # Ensure members are loaded if intents allow, for accurate counts
        # guild.members might not be complete without members intent, guild.member_count is preferred
        if guild.member_count is None and self.bot.intents.members:
            await guild.chunk() # Request members if intent is there and count is missing

        member_count = guild.member_count or len(guild.members)

        # Fetching all members just for counts can be slow on large servers if not already cached.
        # If GUILD_MEMBERS intent is off, guild.members may be incomplete.
        # For simplicity here, we use what's available; for very large bots, consider alternatives.
        humans = sum(1 for member in guild.members if not member.bot and hasattr(member, 'bot')) if self.bot.intents.members or guild.chunked else "N/A (Requires Members Intent)"
        bots = sum(1 for member in guild.members if member.bot and hasattr(member, 'bot')) if self.bot.intents.members or guild.chunked else "N/A (Requires Members Intent)"

        embed.add_field(name="Members", value=f"Total: {member_count}\nHumans: {humans}\nBots: {bots}", inline=True)


        categories = len(guild.categories)
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        embed.add_field(name="Channels", value=f"Total: {text_channels + voice_channels + categories}\nText: {text_channels}\nVoice: {voice_channels}\nCategories: {categories}", inline=True)

        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)

        verification_level_str = str(guild.verification_level).replace("_", " ").capitalize()
        embed.add_field(name="Verification Level", value=verification_level_str, inline=True)

        if guild.premium_tier is not None: # premium_tier can be 0
             embed.add_field(name="Boost Tier", value=f"Tier {guild.premium_tier}", inline=True)
        if guild.premium_subscription_count is not None:
             embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)

        if guild.features:
            embed.add_field(name="Features", value=", ".join(feat.replace("_", " ").title() for feat in guild.features), inline=False)

        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        await ctx.send(embed=embed, ephemeral=False)

    @commands.hybrid_command(name="avatar", aliases=["pfp", "profilepicture"], description="Displays a user's avatar.")
    async def avatar(self, ctx: commands.Context, user: discord.User = None): # Use discord.User
        if user is None:
            user = ctx.author # user will be ctx.author, which is a Member or User

        embed = discord.Embed(title=f"Avatar for {user.name}", color=discord.Color.green())

        # Determine primary avatar to display (server if available and user is member, else global)
        primary_avatar_url = None
        primary_avatar_type = "Global Avatar"

        if isinstance(user, discord.Member) and user.guild_avatar:
            primary_avatar_url = user.guild_avatar.url
            primary_avatar_type = "Server Avatar"
            # Add link to global avatar if it's different and exists
            if user.avatar and user.avatar.url != user.guild_avatar.url:
                 embed.add_field(name="Global Avatar", value=f"[Link]({user.avatar.url})", inline=False)
            elif not user.avatar : # User has guild avatar but no global avatar (using default)
                 embed.add_field(name="Default Global Avatar", value=f"[Link]({user.default_avatar.url})", inline=False)
        elif user.avatar:
            primary_avatar_url = user.avatar.url
            primary_avatar_type = "Global Avatar"
        else:
            primary_avatar_url = user.default_avatar.url
            primary_avatar_type = "Default Avatar"

        embed.set_image(url=primary_avatar_url)
        embed.add_field(name=primary_avatar_type, value=f"[Link]({primary_avatar_url})", inline=False)

        # If the primary display was global avatar and they are a member with a server avatar,
        # ensure the server avatar link is added if it wasn't the primary and is different.
        # This case is mostly covered if server avatar is prioritized as primary.
        # The logic above already prioritizes server avatar as the main image if available.

        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

        await ctx.send(embed=embed, ephemeral=False)

    @commands.Cog.listener()
    async def on_cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Handle errors specific to this cog
        # Default to ephemeral messages for errors to reduce channel noise
        ephemeral_error = True

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in private messages.", ephemeral=ephemeral_error)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"Could not find member: `{error.argument}`. Please check the name/ID or ensure they are in this server.", ephemeral=ephemeral_error)
        elif isinstance(error, commands.UserNotFound): # For commands that take discord.User
            await ctx.send(f"Could not find user: `{error.argument}`. Please check the name/ID.", ephemeral=ephemeral_error)
        elif isinstance(error, commands.BadArgument): # Catches general bad arguments
            await ctx.send(f"Invalid argument provided: {error}\nPlease check the command's help for correct usage.", ephemeral=ephemeral_error)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"You are missing a required argument: `{error.param.name}`.\nPlease check the command's help.", ephemeral=ephemeral_error)
        elif isinstance(error, commands.CommandInvokeError):
            # This can wrap other errors, good to log the original for debugging
            print(f"CommandInvokeError in UtilityCog: {error.original} (command: {ctx.command.qualified_name})")
            await ctx.send(f"An error occurred while executing the command: {error.original}", ephemeral=ephemeral_error)
        else:
            # For other errors, log them and optionally send a generic error message
            print(f"An unexpected error occurred in UtilityCog: {error} (command: {ctx.command.qualified_name})")
            # It's often better not to send a generic "unexpected error" message for every unhandled case
            # unless you have a system to track these (e.g., error reporting service).
            # If the error is not from the categories above, it might be handled by a global error handler or remain unhandled.


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
