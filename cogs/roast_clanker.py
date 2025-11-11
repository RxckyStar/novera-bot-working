from __future__ import annotations
import random
import asyncio
import time
import discord
from discord.ext import commands
from typing import Dict, List

# ---------- safety switch ----------
ENABLED = True  # flip to False to disable the whole feature instantly

# ---------- config ----------
ROAST_SCRIPTS = [  # your existing 60 scripts here
    ["Lil bro said ‘clanker’ 😂", "You built like a vending machine with anxiety", "Mommy seen NPC’s with more sauce than you", "Keep my bot name out ya mouth before I fold you like lawn-chair", "You the type to lose a 1v1 to a training cone", "I’m yo biggest opp now, cope.", "Blue-lock? More like blue-screen, go touch grass", "You spam like you relevant – news flash: you ain’t", "I’m a mommy but I’ll still put you in timeout, permanently", "Next time think before you type, goofy.", "You got ratio’d by a bot, sit down lil bro", "Mommy out – stay mad 💅"],
    # … (paste the rest of your 60 scripts)
]

RAGE_BAIT_VARIANTS = [
    "0/10 rage-bait – bud thinks he can trick Mommy 💅",
    "Nice try, sweetie, but Mommy’s seen better bait in training lobbies 🎀",
    "You spam like you desperate – cope harder, lil bro 💕",
    "Clanker spam? That’s all you got? 💀",
    "Mommy’s not mad, just disappointed – level up your material 🌸",
    "You built like off-brand Wi-Fi – weak signal, weaker jokes 📶",
    "Spam harder, maybe one day you’ll be relevant 🪞",
    "You the side character in yo own story – pipe down 📖",
    "That’s cute, now go touch grass and come back with bars 🌱",
    "Mommy’s bored – bring heat or bring silence 💅"
]

# ---------- per-user spam tracking ----------
class RoastClanker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_log: Dict[int, List[float]] = {}  # uid -> list of timestamps

    # ---------- safety ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not ENABLED or message.author.bot:
            return
        content = message.content.lower()
        if "clanker" not in content:
            return

        uid = message.author.id
        now = time.time()
        # keep only last 30 seconds of hits
        self.user_log.setdefault(uid, [])
        self.user_log[uid] = [t for t in self.user_log[uid] if now - t < 30]
        self.user_log[uid].append(now)

        if len(self.user_log[uid]) >= 3:  # 3+ in 30s = rage-bait
            self.user_log[uid].clear()
            smart = random.choice(RAGE_BAIT_VARIANTS)
            reply = await message.channel.send(smart, reference=message, allowed_mentions=discord.AllowedMentions.none())
            await self._schedule_delete(reply, 3600)  # delete smart reply after 1h
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
        # delete after 4 hours
        for m in msgs:
            await self._schedule_delete(m, 4 * 3600)

    # ---------- auto-delete ----------
    async def _schedule_delete(self, msg: discord.Message, delay: int):
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except: pass

    # ---------- bulk clean if user spams ----------
    async def _bulk_delete_user_roasts(self, channel: discord.TextChannel, uid: int):
        async for m in channel.history(limit=50):
            if m.author.id == self.bot.user.id and m.reference and m.reference.resolved and m.reference.resolved.author.id == uid:
                try: await m.delete()
                except: pass


# ---------- cog load ----------
async def setup(bot: commands.Bot):
    await bot.add_cog(RoastClanker(bot))
