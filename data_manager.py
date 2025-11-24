from __future__ import annotations
import asyncio
import re
from typing import Dict, Tuple
import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
LEDGER_CH_ID = 1350172182038446184
LEDGER_REGEX = re.compile(r"^(\d+)\s+(-?\d+)$")
# ----------------------------------------


class DataManager:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._cache: dict[str, int] = {}
        self._activity: dict[str, dict[str, int]] = {}
        bot.loop.create_task(self._replay_ledger())

    async def _replay_ledger(self) -> None:
        await self.bot.wait_until_ready()
        ch = self.bot.get_channel(LEDGER_CH_ID)
        if not ch:
            logger.warning("Ledger channel not found — starting with empty cache")
            return
        logger.info("[VALUE-LEDGER] Rebuilding values from channel history…")
        async for msg in ch.history(limit=None, oldest_first=False):
            if msg.author.bot is False:
                continue
            m = LEDGER_REGEX.match(msg.content)
            if not m:
                continue
            uid, val = m.groups()
            self._cache[uid] = int(val)
        logger.info(f"[VALUE-LEDGER] Rebuild complete — {len(self._cache)} members loaded")

    async def _log(self, user_id: str, value: int) -> None:
        ch = self.bot.get_channel(LEDGER_CH_ID)
        if ch:
            await ch.send(f"{user_id} {value}")

    def ensure_member(self, user_id: str) -> None:
        self._cache.setdefault(user_id, 0)

    def get_member_value(self, user_id: str) -> int:
        return self._cache.get(user_id, 0)

    async def set_member_value(self, user_id: str, value: int) -> None:
        self._cache[user_id] = max(0, int(value))
        await self._log(user_id, self._cache[user_id])

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
        value = self.get_member_value(user_id)
        for rank, (uid, _) in enumerate(sorted_members, 1):
            if uid == user_id:
                return rank, total, value
        return total + 1, total, value

    def update_activity(self, user_id: str, kind: str, amount: int = 1) -> None:
        store = self._activity.setdefault(user_id, {"messages": 0, "reactions": 0})
        if kind not in store:
            store[kind] = 0
        store[kind] += amount

    def get_activity(self, user_id: str) -> Dict[str, int]:
        return self._activity.get(user_id, {"messages": 0, "reactions": 0})


_DM: DataManager | None = None
data_manager: DataManager | None = None


class ValueLedgerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        global _DM, data_manager
        _DM = DataManager(bot)
        data_manager = _DM
        bot.data_manager = _DM          # 🔥 THE ONE-LINE FIX
        logger.info("[VALUE-LEDGER] DataManager singleton created and attached to bot")


async def setup(bot: commands.Bot):
    await bot.add_cog(ValueLedgerCog(bot))
