from __future__ import annotations
import discord, logging, random
from discord.ext import commands
import data_manager

log = logging.getLogger(__name__)

# Roles / channels (edit to your IDs)
SETVALUE_ROLE_ID = 1350547213717209160  # who can run !setvalue
ANNOUNCE_CHANNEL_ID = 1350172182038446184  # announcement channel

MOMMY_SET_VARIANTS = [
    "💴 Sweetie, {user} is now valued at **¥{new}M**. Mommy handled it with care.",
    "💴 All set, darling. {user}'s value is **¥{new}M** now~",
    "💴 Update complete, cutie. {user} stands at **¥{new}M**."
]
MOMMY_ADD_VARIANTS = [
    "💴 Adjustment done, love. {user} moved from **¥{old}M** → **¥{new}M** (**+{delta}M**).",
    "💴 Tweak applied, honey. {user}: **¥{old}M** → **¥{new}M** (**+{delta}M**)",
    "💴 Value boosted, sweetie. {user}: **¥{old}M** → **¥{new}M** (**+{delta}M**)"
]

def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)

def mommy_embed(title: str, description: str, user: discord.Member) -> discord.Embed:
    emb = discord.Embed(title=title, description=description, color=discord.Color.purple())
    emb.set_footer(text="Novera • Mommy is watching ✨")
    if user.avatar:
        emb.set_thumbnail(url=user.avatar.url)
    return emb

class ValueAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command(name="addvalue")
    async def addvalue(self, ctx: commands.Context, member: discord.Member, delta: int):
        """Add delta (M) to a player's value (admin-only)."""
        try:
            uid = str(member.id)
            old = data_manager.get_member_value(uid)
            new = max(0, old + int(delta))
            data_manager.set_member_value(uid, new)

            desc = random.choice(MOMMY_ADD_VARIANTS).format(user=member.mention, old=old, new=new, delta=(new-old))
            emb = mommy_embed("✨ Value Adjusted", desc, member)

            # include previous/new/change/date
            emb.add_field(name="Previous", value=f"¥{old}M", inline=True)
            emb.add_field(name="New", value=f"¥{new}M", inline=True)
            emb.add_field(name="Change", value=f"+{new-old}M" if new>=old else f"-{old-new}M", inline=True)

            await ctx.send(embed=emb)

            # also announce
            ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if ch: 
                await ch.send(embed=emb)

        except Exception as e:
            log.exception("addvalue failed")
            await ctx.send("❌ Mommy stumbled applying that change, sweetie. Try again later.")

    @commands.guild_only()
    @commands.command(name="setvalue")
    async def setvalue(self, ctx: commands.Context, member: discord.Member, new_value: int):
        """Set a player's value exactly (role-gated)."""
        if not isinstance(ctx.author, discord.Member) or not has_role(ctx.author, SETVALUE_ROLE_ID):
            await ctx.reply("You don't have permission to use this command.", mention_author=False)
            return
        try:
            uid = str(member.id)
            old = data_manager.get_member_value(uid)
            new = max(0, int(new_value))
            data_manager.set_member_value(uid, new)

            desc = random.choice(MOMMY_SET_VARIANTS).format(user=member.mention, new=new)
            emb = mommy_embed("💜 Value Set", desc, member)
            emb.add_field(name="Previous", value=f"¥{old}M", inline=True)
            emb.add_field(name="New", value=f"¥{new}M", inline=True)
            delta = new - old
            sign = "+" if delta >= 0 else ""
            emb.add_field(name="Change", value=f"{sign}{delta}M", inline=True)

            await ctx.send(embed=emb)

            ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if ch: 
                await ch.send(embed=emb)

        except Exception as e:
            log.exception("setvalue failed")
            await ctx.send("❌ Mommy couldn't set that right now, darling.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ValueAdmin(bot))
