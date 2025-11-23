# cogs/value_admin.py
# Admin-only value tools (setvalue)
# This file is EDIT-ONLY version, designed to work with existing data_manager + checkvalue/addvalue.

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

import data_manager  # uses the same backend as checkvalue/addvalue

logger = logging.getLogger(__name__)

# ====== CONFIG ======
SETVALUE_ROLE_ID = 1350547213717209160      # role allowed to use !setvalue
EVALUATED_ROLE_ID = 1350863646187716640     # role to give after value is set
TRYOUT_PENDING_ROLE_ID = 1350864967674630144  # role to REMOVE when value is finalized

# Mommy-style text variants
SETVALUE_SUCCESS_VARIANTS = [
    "💴 New value locked in, sweetie. Mommy updated your price on the market.",
    "💴 Adjustment complete, darling. Your Novera value has been refreshed.",
    "💴 All done, cutie. Your yen value is now up to date.",
]

SETVALUE_DM_VARIANTS = [
    "💴 Your official Novera value has been set to **{value}M ¥**. Don’t disappoint Mommy now.",
    "💴 Congratulations, sweetie. You’re now valued at **{value}M ¥** in Novera.",
    "💴 Your updated value is **{value}M ¥**. Go prove you’re worth every yen.",
]

SETVALUE_ERROR_VARIANTS = [
    "😔 Oh no darling, something went wrong saving that value. Try again later, okay? 💕",
    "😔 Mommy’s books glitched for a second—couldn’t save that value right now.",
    "😔 Value update failed, sweetie. Let’s try that again in a bit.",
]


def _has_setvalue_role(member: discord.Member) -> bool:
    return any(r.id == SETVALUE_ROLE_ID for r in member.roles)


class ValueAdmin(commands.Cog):
    """Admin-only value management (setvalue)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------- SETVALUE COMMAND --------------

    @commands.guild_only()
    @commands.command(name="setvalue")
    async def setvalue_command(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        amount: Optional[int] = None,
    ):
        """
        Set a player's value in millions of yen.
        Usage: !setvalue @user 77   -> sets value to 77M ¥
        Restricted to SETVALUE_ROLE_ID.
        """
        # Permission check
        if not isinstance(ctx.author, discord.Member) or not _has_setvalue_role(ctx.author):
            await ctx.reply(
                "😼 Oh honey, only Mommy’s little accountants can touch the value board.",
                mention_author=False,
            )
            return

        # Argument validation
        if member is None or amount is None:
            await ctx.reply(
                "💴 Usage: `!setvalue @user 77`\n"
                "That sets their value to **77M ¥**, sweetie.",
                mention_author=False,
            )
            return

        if amount < 0:
            await ctx.reply(
                "💴 Value can’t be negative, darling. Even benchwarmers are worth at least **0M ¥**.",
                mention_author=False,
            )
            return

        target_id = str(member.id)

        # 🔧 Always go through the DataManager INSTANCE, not module-level funcs
        dm = getattr(data_manager, "data_manager", None)
        if dm is None:
            logger.error("[setvalue] data_manager.data_manager is not initialized")
            await ctx.reply(random.choice(SETVALUE_ERROR_VARIANTS), mention_author=False)
            return

        # --- Backend: use the SAME backend as checkvalue/addvalue ---
        try:
            old_value = dm.get_member_value(target_id)
        except Exception as e:
            logger.error(f"[setvalue] get_member_value failed for {target_id}: {e}", exc_info=True)
            await ctx.reply(random.choice(SETVALUE_ERROR_VARIANTS), mention_author=False)
            return

        try:
            # clamp to non-negative int
            new_value = max(0, int(amount))

            # This calls DataManager under the hood (same backend as addvalue / checkvalue)
            await dm.set_member_value(target_id, new_value)
        except Exception as e:
            logger.error(f"[setvalue] set_member_value failed for {target_id}: {e}", exc_info=True)
            await ctx.reply(random.choice(SETVALUE_ERROR_VARIANTS), mention_author=False)
            return

        # Role updates (in guild only)
        if ctx.guild:
            try:
                eval_role = ctx.guild.get_role(EVALUATED_ROLE_ID)
                pending_role = ctx.guild.get_role(TRYOUT_PENDING_ROLE_ID)

                # Give evaluated role
                if eval_role and eval_role not in member.roles:
                    await member.add_roles(eval_role, reason="Novera: value set via !setvalue")

                # Remove pending tryout role
                if pending_role and pending_role in member.roles:
                    await member.remove_roles(pending_role, reason="Novera: value finalized via !setvalue")
            except Exception as e:
                logger.warning(f"[setvalue] Failed updating roles for {member.id}: {e}")

        # Prepare embed (match style / vibe of existing Mommy embeds)
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        diff = new_value - (old_value or 0)
        change_str = f"{'+' if diff >= 0 else ''}{diff}M ¥"

        embed = discord.Embed(
            title="💴 Novera Value Adjustment",
            description=random.choice(SETVALUE_SUCCESS_VARIANTS),
            color=discord.Color.purple(),
        )

        embed.add_field(name="👤 Player", value=f"{member.mention}\n`{member.id}`", inline=False)
        embed.add_field(name="Old Value", value=f"{old_value}M ¥", inline=True)
        embed.add_field(name="New Value", value=f"{new_value}M ¥", inline=True)
        embed.add_field(name="Change", value=change_str, inline=True)
        embed.add_field(name="Adjusted By", value=f"{ctx.author.mention}", inline=True)
        embed.add_field(name="Timestamp", value=now, inline=True)

        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        await ctx.reply(embed=embed, mention_author=False)

        # DM the player about their updated value (if possible)
        try:
            dm_text = random.choice(SETVALUE_DM_VARIANTS).format(value=new_value)
            dm_chan = await member.create_dm()
            await dm_chan.send(dm_text)
        except Exception as e:
            logger.info(f"[setvalue] Could not DM player {member.id} about new value: {e}")

        logger.info(
            f"[setvalue] {ctx.author} set value for {member} ({member.id}) "
            f"from {old_value}M to {new_value}M"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ValueAdmin(bot))
