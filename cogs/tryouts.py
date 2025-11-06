
# cogs/value_admin.py
# Admin value tools (setvalue) with Novera "mommy" vibe + rich embeds

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

# IDs (update only if you actually change them)
ADMIN_VALUE_ROLE_ID = 1350547213717209160   # who can use !setvalue
ANNOUNCE_CHANNEL_ID = 1350172182038446184   # public "value updates" channel
EVALUATED_ROLE_ID   = 1350863646187716640   # given when a value is set

# --- Mommy text variants ---
MOM_SET_OK = [
    "💋 Value updated, sweetie.",
    "✨ All set, darling.",
    "💞 Done and dusted, cutie.",
]
MOM_SET_FAIL = [
    "😔 Mommy tripped on the cables—couldn’t save that, sweetie.",
    "💔 Something went wrong, angel. Try again in a moment.",
    "🛠️ Mommy’s tools slipped. I’ll fix it, honey—give it another go.",
]

def get_data_manager(bot) -> object:
    """
    Try to use a shared DataManager instance attached to the bot.
    If missing, lazily create one and attach it for consistency.
    """
    dm = getattr(bot, "data_manager", None)
    if dm is not None:
        return dm

    try:
        # Prefer the same class used by the project
        from data_manager import DataManager
        dm = DataManager("member_data.json")
        setattr(bot, "data_manager", dm)
        logging.info("[value_admin] Created local DataManager and attached to bot.")
        return dm
    except Exception as e:
        logging.error(f"[value_admin] Failed to get/create DataManager: {e}")
        return None

def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in getattr(member, "roles", []))


class ValueAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.guild_only()
    @commands.command(name="setvalue")
    async def setvalue(self, ctx: commands.Context, member: discord.Member = None, amount_m: int = None):
        """
        Set a user's value in millions.
        Usage: !setvalue @user 65
        Requires role: ADMIN_VALUE_ROLE_ID
        """
        # Permission check
        if not isinstance(ctx.author, discord.Member) or not has_role(ctx.author, ADMIN_VALUE_ROLE_ID):
            await ctx.reply("You don’t have permission to use this command.", mention_author=False)
            return

        # Validate args
        if member is None or amount_m is None:
            await ctx.reply("Usage: `!setvalue @user <amount-in-millions>`", mention_author=False)
            return
        if member.bot:
            await ctx.reply("Mommy doesn't evaluate robots, sweetie.", mention_author=False)
            return
        try:
            amount_m = int(amount_m)
            if amount_m < 0:
                amount_m = 0
        except Exception:
            await ctx.reply("The amount must be a number, angel.", mention_author=False)
            return

        dm = get_data_manager(self.bot)
        if dm is None:
            await ctx.reply(f"{MOM_SET_FAIL[0]}", mention_author=False)
            return

        try:
            uid = str(member.id)
            old_value = dm.get_member_value(uid)
            dm.set_member_value(uid, amount_m)

            # Try to grant the evaluated role
            try:
                role = ctx.guild.get_role(EVALUATED_ROLE_ID)
                if role and role not in member.roles:
                    await member.add_roles(role, reason="Novera: value set by admin")
            except Exception as e:
                logging.debug(f"[value_admin] could not add evaluated role: {e}")

            # Build a rich embed similar to checkvalue style
            delta = amount_m - old_value
            sign = "+" if delta >= 0 else ""
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            embed = discord.Embed(
                title="💼 Value Adjustment",
                description=f"{member.mention}",
                color=discord.Color.purple()
            )
            embed.add_field(name="Previous", value=f"{old_value}M", inline=True)
            embed.add_field(name="New", value=f"{amount_m}M", inline=True)
            embed.add_field(name="Change", value=f"{sign}{delta}M", inline=True)
            embed.add_field(name="Adjusted by", value=f"{ctx.author.mention}", inline=True)
            embed.add_field(name="Date", value=now, inline=True)

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)

            # Send a pretty confirmation in-channel
            await ctx.reply(f"{MOM_SET_OK[0]}",
                            embed=embed, mention_author=False)

            # Announce in the configured channel (if different from current)
            try:
                ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
                if ch:
                    ann = discord.Embed(
                        title="📣 Novera Value Update",
                        description=f"{member.mention} is now valued at **{amount_m}M**.",
                        color=discord.Color.blurple()
                    )
                    if member.avatar:
                        ann.set_thumbnail(url=member.avatar.url)
                    ann.add_field(name="Changed by", value=ctx.author.mention)
                    ann.add_field(name="Change", value=f"{sign}{delta}M")
                    await ch.send(embed=ann)
            except Exception as e:
                logging.debug(f"[value_admin] announce send failed: {e}")

            # DM the member warmly
            try:
                dm_chan = await member.create_dm()
                await dm_chan.send(
                    f"💖 Hey {member.mention}, Mommy updated your value to **{amount_m}M**. Keep shining, sweetheart!"
                )
            except Exception as e:
                logging.debug(f"[value_admin] DM to member failed: {e}")

        except Exception as e:
            logging.exception(f"setvalue backend error: {e}")
            await ctx.reply(f"{MOM_SET_FAIL[1]}", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ValueAdmin(bot))
