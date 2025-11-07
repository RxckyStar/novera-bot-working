# cogs/value_admin.py
from __future__ import annotations
import re
import random
import logging
from typing import Optional

import discord
from discord.ext import commands

import data_manager

SETVALUE_ROLE_ID     = 1350547213717209160  # allowed to use !setvalue
EVALUATED_ROLE_ID    = 1350863646187716640  # role to give after value is set
ANNOUNCE_CHANNEL_ID  = 1350172182038446184  # announcement channel

CONFIRM_VARIANTS = [
    "All set, sweetie — {user} is now valued at **{amount}M**. 💖",
    "Done and dusted! {user} sits pretty at **{amount}M**. ✨",
    "Value updated: {user} → **{amount}M**. Mommy approves. 💅",
]
ANNOUNCE_VARIANTS = [
    "📣 **Valuation Update**: {mention} is now **{amount}M**.",
    "🏷️ New value for {mention}: **{amount}M**.",
    "💫 {mention} has been set to **{amount}M**.",
]
DM_VARIANTS = [
    "Hi darling — your value is now **{amount}M**. Keep shining! 💖",
    "Update time, sweetie: you’re **{amount}M**. Let’s make it climb. ✨",
    "Mommy set your value to **{amount}M**. Proud of you already. 💋",
]

def _parse_amount_to_m(text: str) -> Optional[int]:
    text = text.strip().lower().replace(',', '')
    m = re.fullmatch(r'(\d+(?:\.\d+)?)(m)?', text)
    if not m:
        return None
    val = float(m.group(1))
    val = max(0.0, min(val, 10000.0))
    return int(round(val))

async def _give_role_if_needed(bot: commands.Bot, guild: discord.Guild, member: discord.Member):
    try:
        role = guild.get_role(EVALUATED_ROLE_ID)
        if role and role not in member.roles:
            await member.add_roles(role, reason="Novera: setvalue granted Evaluated role")
    except Exception as e:
        logging.debug(f"setvalue: failed to add role: {e}")

class ValueAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _has_setvalue_role(self, m: discord.Member) -> bool:
        return any(r.id == SETVALUE_ROLE_ID for r in getattr(m, "roles", []))

    @commands.guild_only()
    @commands.command(name="setvalue")
    async def setvalue(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[str] = None, *, reason: str = ""):
        """
        !setvalue @user <amountM> [reason...]
        amount can be '25', '25m', '25.5', etc. (interpreted as millions)
        """
        author = ctx.author
        if not isinstance(author, discord.Member) or not self._has_setvalue_role(author):
            return await ctx.reply("You don’t have permission to use this command.", mention_author=False)

        if member is None or member.bot:
            return await ctx.reply("Usage: `!setvalue @user <amount>` (cannot target bots).", mention_author=False)

        if amount is None:
            return await ctx.reply("Missing amount. Example: `!setvalue @user 25m`", mention_author=False)

        parsed = _parse_amount_to_m(amount)
        if parsed is None:
            return await ctx.reply("Couldn’t parse that amount. Examples: `25`, `25m`, `25.5`", mention_author=False)

        # write to backend
        try:
            data_manager.set_member_value(str(member.id), parsed)
        except Exception as e:
            logging.error(f"setvalue backend error: {e}")
            return await ctx.reply("Backend error while saving value. Check logs.", mention_author=False)

        # role
        await _give_role_if_needed(self.bot, ctx.guild, member)

        # confirm to admin
        conf = random.choice(CONFIRM_VARIANTS).format(user=member.mention, amount=parsed)
        if reason:
            conf += f"\n📝 Reason: {reason}"
        await ctx.reply(conf, mention_author=False)

        # announce
        ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if ch:
            try:
                line = random.choice(ANNOUNCE_VARIANTS).format(mention=member.mention, amount=parsed)
                if reason:
                    line += f"\n📝 Reason: {reason}"
                await ch.send(line)
            except Exception as e:
                logging.debug(f"announce failed: {e}")

        # DM the user
        try:
            dm = await member.create_dm()
            await dm.send(random.choice(DM_VARIANTS).format(amount=parsed))
        except Exception as e:
            logging.debug(f"dm failed: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ValueAdmin(bot))
