from discord.ext import commands
import discord
import random


class Tips(commands.Cog):
    """Commands for providing tips about using the bot."""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config[__name__.split(".")[-1]]
        self.tips = ["Tip of this dick in your ass"]

    @commands.command()
    async def tip(self, ctx):
        """Get a random tip about using the bot."""
        index = random.randrange(len(self.tips))
        await ctx.send(f"**Tip #{index+1}:** {self.tips[index]}")
