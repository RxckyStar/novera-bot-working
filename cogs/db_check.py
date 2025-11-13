from discord.ext import commands
import sqlite3, pathlib, os

class DBCheck(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(hidden=True)
    @commands.is_owner()
    async def dbtest(self, ctx: commands.Context) -> None:
        path = os.getenv("SQLITE3_RAILWAY_VOLUME_MOUNT_PATH")
        db   = pathlib.Path(path) / "bot.db" if path else ":memory:"
        con  = sqlite3.connect(db, timeout=5)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("INSERT OR REPLACE INTO members(user_id,value) VALUES ('999999',123)")
        con.commit()
        con.close()
        size = db.stat().st_size if db != ":memory:" else 0
        await ctx.send(f"DB path: `{db}`\nSize: `{size}` bytes")

async def setup(bot: commands.Bot):
    await bot.add_cog(DBCheck(bot))
