from __future__ import annotations
import asyncio
import re
import discord
from discord.ext import commands
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
# This is your REAL value-log channel
LEDGER_CH_ID = 1350172182038446184

# Matches:   654338875736588288 77
#            (userid) (value)
LEDGER_REGEX = re.compile(r"^(\d+)\s+(-?\d+)$")
# ----------------------------------------


class DataManager:
    """
    This version stores NO values on disk.
    All values live in memory and get rebuilt
    on startup from your value-log channel.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._cache: dict[str, int] = {}  # in-memory only

        # Rebuild values on startup
        bot.loop.create_task(self._replay_ledger())

    # ----------- STARTUP REPLAY -----------
    async def _replay_ledger(self) -> None:
        """Reads the ENTIRE value-log channel and rebuilds all values."""
        await self.bot.wait_until_ready()
        ch = self.bot.get_channel(LEDGER_CH_ID)

        if not ch:
            logger.warning("Ledger channel not found — starting with empty cache")
            return

        logger.info("[VALUE-LEDGER] Rebuilding values from channel history…")

        # newest → oldest ensures last message is final value
        async for msg in ch.history(limit=None, oldest_first=False):
            if msg.author.bot is False:
                continue

            m = LEDGER_REGEX.match(msg.content)
            if not m:
                continue

            uid, val = m.groups()
            self._cache[uid] = int(val)

        logger.info(f"[VALUE-LEDGER] Rebuild complete — {len(self._cache)} members loaded")

    # ----------- INTERNAL LOGGING ----------
    async def _log(self, user_id: str, value: int) -> None:
        """Write a new value entry to the ledger channel."""
        ch = self.bot.get_channel(LEDGER_CH_ID)
        if ch:
            await ch.send(f"{user_id} {value}")

    # --------------- PUBLIC API --------------

    def ensure_member(self, user_id: str) -> None:
        """Ensure a member exists in cache."""
        self._cache.setdefault(user_id, 0)

    def get_member_value(self, user_id: str) -> int:
        """Return the user's value (0 if missing)."""
        return self._cache.get(user_id, 0)

    async def set_member_value(self, user_id: str, value: int) -> None:
        """Set EXACT value for a user."""
        self._cache[user_id] = max(0, int(value))
        await self._log(user_id, self._cache[user_id])

    async def add_member_value(self, user_id: str, delta: int) -> int:
        """Add/subtract a value amount."""
        self.ensure_member(user_id)

        new_val = max(0, self._cache[user_id] + int(delta))
        self._cache[user_id] = new_val
        await self._log(user_id, new_val)
        return new_val

    def get_all_member_values(self) -> Dict[str, int]:
        """Return full value cache."""
        return self._cache.copy()

    def get_member_ranking(self, user_id: str) -> Tuple[int, int, int]:
        """Return (rank, total, value)."""
        sorted_members = sorted(self._cache.items(), key=lambda x: x[1], reverse=True)
        total = len(sorted_members)
        value = self.get_member_value(user_id)

        for rank, (uid, _) in enumerate(sorted_members, 1):
            if uid == user_id:
                return rank, total, value

        return total + 1, total, value


# -------------- SINGLETON WRAPPERS --------------

_DM = None      # real instance
data_manager = None  # alias for legacy code


class ValueLedgerCog(commands.Cog):
    """Creates the singleton instance at load time."""
    def __init__(self, bot: commands.Bot) -> None:
        global _DM, data_manager
        _DM = DataManager(bot)
        data_manager = _DM


async def setup(bot: commands.Bot):
    await bot.add_cog(ValueLedgerCog(bot))
