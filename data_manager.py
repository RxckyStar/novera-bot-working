from __future__ import annotations
import asyncio
import re
import discord
from discord.ext import commands
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# ---------- CONFIG ----------
LEDGER_CH_ID = 1350172182038446184   # your private log channel
LEDGER_REGEX = re.compile(r"^(\d+)\s+(-?\d+)$")
# ----------------------------


class DataManager:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._cache: dict[str, int] = {}  # in-memory only
        bot.loop.create_task(self._replay_ledger())

    # ---------- startup replay ----------
    async def _replay_ledger(self) -> None:
        await self.bot.wait_until_ready()
        ch = self.bot.get_channel(LEDGER_CH_ID)
        if not ch:
            logger.warning("Ledger channel not found – starting with empty cache")
            return

        # replay **entire** channel (newest → oldest)
        async for msg in ch.history(limit=None, oldest_first=False):
            if m := LEDGER_REGEX.match(msg.content):
                uid, val = m.groups()
                self._cache[uid] = int(val)

        logger.info("Ledger replayed: %d members cached", len(self._cache))

    # ---------- internal helpers ----------
    async def _log(self, user_id: str, value: int) -> None:
        ch = self.bot.get_channel(LEDGER_CH_ID)
        if ch:
            await ch.send(f"{user_id} {value}")

    # ---------- CRUD (same names as before) ----------
    def ensure_member(self, user_id: str) -> None:
        self._cache.setdefault(user_id, 0)

    def get_member_value(self, user_id: str) -> int:
        return self._cache.get(user_id, 0)

    async def set_member_value(self, user_id: str, value: int) -> None:
        self._cache[user_id] = max(0, int(value))
        await self._log(user_id, self._cache[user_id])

    async def add_member_value(self, user_id: str, delta: int) -> int:
        self.ensure_member(user_id)
        new = max(0, self._cache[user_id] + int(delta))
        self._cache[user_id] = new
        await self._log(user_id, new)
        return new

    def get_all_member_values(self) -> Dict[str, int]:
        return self._cache.copy()

    def get_member_ranking(self, user_id: str) -> Tuple[int, int, int]:
        items = sorted(self._cache.items(), key=lambda x: x[1], reverse=True)
        total = len(items)
        user_val = self.get_member_value(user_id)
        for rank, (uid, _) in enumerate(items, 1):
            if uid == user_id:
                return rank, total, user_val
        return total + 1, total, user_val


# ---------- singleton ----------
_DM = None  # filled on cog load


# ---------- public sync wrappers ----------
def ensure_member(uid: str) -> None:
    _DM.ensure_member(uid)

def get_member_value(uid: str) -> int:
    return _DM.get_member_value(uid)

async def set_member_value(uid: str, value: int) -> int:
    await _DM.set_member_value(uid, value)

async def add_member_value(uid: str, delta: int) -> int:
    return await _DM.add_member_value(uid, delta)

def get_all_member_values() -> Dict[str, int]:
    return _DM.get_all_member_values()

def get_member_ranking(uid: str) -> Tuple[int, int, int]:
    return _DM.get_member_ranking(uid)

def get_data_filename() -> str:
    return ":memory: (ledger channel)"


# ---------- drop-in object ----------
data_manager = None  # filled on cog load


# ---------- cog loader ----------
class ValueLedgerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        global _DM, data_manager
        _DM = DataManager(bot)
        data_manager = _DM  # legacy compat


async def setup(bot: commands.Bot):
    await bot.add_cog(ValueLedgerCog(bot))
