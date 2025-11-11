from __future__ import annotations
import random
import asyncio
import time
import discord
from discord.ext import commands
from typing import Dict, List

ENABLED = True  # safety switch

# ---------- scripts ----------
ROAST_SCRIPTS = [  # your 60 full scripts here
    ["Lil bro said ‘clanker’ 😂", "You built like a vending machine with anxiety", "Mommy seen NPC’s with more sauce than you", "Keep my bot name out ya mouth before I fold you like lawn-chair", "You the type to lose a 1v1 to a training cone", "I’m yo biggest opp now, cope.", "Blue-lock? More like blue-screen, go touch grass", "You spam like you relevant – news flash: you ain’t", "I’m a mommy but I’ll still put you in timeout, permanently", "Next time think before you type, goofy.", "You got ratio’d by a bot, sit down lil bro", "Mommy out – stay mad 💅"],
    # … (paste the rest)
]

NICE_TRY_VARIANTS = [
    "nice try 💅",
    "cope harder 🌸",
    "weak bait 🎀",
    "0/10 🪞",
    " Mommy’s bored 💤",
    "level up 📈",
    "touch grass 🌱",
    "pipe down 📖",
    "stay mad 😴",
    "next joke ⏭️"
]

# ---------- cog ----------
class RoastClanker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_log: Dict[int, List[float]] = {}       # uid -> timestamps (30-s window)
        self.nice_try_until: Dict[int, float] = {}      # uid -> unix-seconds when nice-try mode ends

    # ---------- listener ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not ENABLED or message.author.bot or message.author.id == self.bot.user.id:
            return
        content = message.content.lower()
        if "clanker" not in content:
            return

        uid = message.author.id
        now = time.time()

        # 30-second hit log
        self.user_log.setdefault(uid, [])
        self.user_log[uid] = [t for t in self.user_log[uid] if now - t < 30]
        self.user_log[uid].append(now)

        # 3+ hits = enter nice-try mode for 5 minutes
        if len(self.user_log[uid]) >= 3:
            self.user_log[uid].clear()
            self.nice_try_until[uid] = now + 300  # 5 min
            txt = random.choice(NICE_TRY_VARIANTS)
            m = await message.channel.send(txt, reference=message, allowed_mentions=discord.AllowedMentions.none())
            await self._schedule_delete(m, 3600)  # delete after 1h
            return

        # still in nice-try mode? single word only
        if self.nice_try_until.get(uid, 0) > now:
            txt = random.choice(NICE_TRY_VARIANTS)
            m = await message.channel.send(txt, reference=message, allowed_mentions=discord.AllowedMentions.none())
            await self._schedule_delete(m, 3600)
            return

        # normal roast
        script = random.choice(ROAST_SCRIPTS)
        msgs = []
        for line in script:
            async with message.channel.typing():
                await asyncio.sleep(1)
            m = await message.channel.send(line, reference=message if not msgs else None,
                                         allowed_mentions=discord.AllowedMentions.none())
            msgs.append(m)
        for m in msgs:
            await self._schedule_delete(m, 4 * 3600)  # 4h auto-clean

    # ---------- auto-delete ----------
    async def _schedule_delete(self, msg: discord.Message, delay: int):
        await asyncio.sleep(delay)
        try: await msg.delete()
        except: pass


async def setup(bot: commands.Bot):
    await bot.add_cog(RoastClanker(bot))
