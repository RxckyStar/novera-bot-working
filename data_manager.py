from __future__ import annotations
import asyncio
import re
import discord
from discord.ext import commands
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
LEDGER_CH_ID = 1350172182038446184
LEDGER_REGEX = re.compile(r"^(\d+)\s+(-?\d+)$")
# ----------------------------------------


# ========== GLOBAL SINGLETON PLACEHOLDERS ==========
# These are populated immediately on bot startup.
_DM: "DataManager" = None
data_manager: "DataManager" = None
# ===================================================


class DataManager:
    """
    Pure in-memory value system rebuilt from your ledger channel.
    NEVER touches disk, so Railway cannot wipe your values.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cache: dict[str, int] = {}
        self.ready = False               # <— NEW: prevents early access

        bot.loop.create_task(self._startup())

    async def _startup(self):
        """Ensure replay completes before any commands run."""
        await self._replay_ledger()
        self.ready = True
        logger.info("[VALUE-LEDGER] DataManager ready — values live.")

    # ----------- LEDGER REPLAY ----------------
    async def _replay_ledger(self):
        await self.bot.wait_until_ready()
        ch = self.bot.get_channel(LEDGER_CH_ID)

        if not ch:
            logger.warning("Ledger channel NOT FOUND — starting with empty table")
            return

        logger.info("[VALUE-LEDGER] Rebuilding values from channel…")

        # newest → oldest (last entry = final value)
        async for msg in ch.history(limit=None, oldest_first=False):
            if not msg.content:
                continue
            m = LEDGER_REGEX.match(msg.content)
            if m:
                uid, val = m.groups()
                self._cache[uid] = int(val)

        logger.info(f"[VALUE-LEDGER] Loaded {len(self._cache)} members.")

    # ----------- INTERNAL LOGGING ----------
    async def _log(self, user_id: str, value: int):
        ch = self.bot.get_channel(LEDGER_CH_ID)
        if ch:
            await ch.send(f"{user_id} {value}")

    # --------------- PUBLIC API --------------
    def ensure_member(self, user_id: str):
        self._cache.setdefault(user_id, 0)

    def get_member_value(self, user_id: str) -> int:
        return self._cache.get(user_id, 0)

    async def set_member_value(self, user_id: str, value: int):
        value = max(0, int(value))
        self._cache[user_id] = value
        await self._log(user_id, value)

    async def add_member_value(self, user_id: str, delta: int) -> int:
        self.ensure_member(user_id)

        new_val = max(0, self._cache[user_id] + int(delta))
        self._cache[user_id] = new_val
        await self._log(user_id, new_val)
        return new_val

    def get_all_member_values(self) -> Dict[str, int]:
        return self._cache.copy()

    def get_member_ranking(self, user_id: str) -> Tuple[int, int, int]:
        sorted_members = sorted(self._cache.items(), key=lambda x: x[1], reverse=True)
        total = len(sorted_members)
        val = self.get_member_value(user_id)

        for rank, (uid, _) in enumerate(sorted_members, 1):
            if uid == user_id:
                return rank, total, val

        return total + 1, total, val


# =====================================================
#                   COG INITIALIZER
# =====================================================
class ValueLedgerCog(commands.Cog):
    """Creates the global DataManager instance on startup."""

    def __init__(self, bot: commands.Bot):
        global _DM, data_manager

        if _DM is None:
            _DM = DataManager(bot)
            data_manager = _DM
            logger.info("[VALUE-LEDGER] Singleton DataManager initialized")
        else:
            # Never create duplicates
            data_manager = _DM
            logger.info("[VALUE-LEDGER] DataManager already existed")


async def setup(bot: commands.Bot):
    await bot.add_cog(ValueLedgerCog(bot))
