from discord.ext import commands

class Janitor(commands.Cog):
    """One-off cleanup tools."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="cleanupClanker")
    @commands.has_permissions(manage_messages=True)
    async def cleanup_clanker(self, ctx: commands.Context):
        """Bulk-delete old bot roast spam (one-time use)."""
        cleaned = 0
        async for m in ctx.channel.history(limit=200):
            if (
                m.author.id == self.bot.user.id
                and m.reference
                and "clanker" in m.content.lower()
            ):
                try:
                    await m.delete()
                    cleaned += 1
                except: pass
        await ctx.send(f"🧹 Janitor swept {cleaned} old roast messages.", delete_after=5)


async def setup(bot: commands.Bot):
    await bot.add_cog(Janitor(bot))
