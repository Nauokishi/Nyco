import discord
from discord.ext import commands

class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='ping', description="Responds with pong.")
    async def ping(self, ctx: commands.Context):
        """Responds with pong."""
        await ctx.send('pong')

async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
