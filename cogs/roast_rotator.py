from __future__ import annotations
import asyncio
import random
from discord.ext import commands, tasks
import logging

log = logging.getLogger(__name__)

# ---------- CONFIG ----------
TARGET_A = 1262293201990062095  # “bud who thinks he can be #1”
TARGET_B = 975952195352686642   # “tough-guy wannabe”
INTERVAL = 120                  # seconds
# ---------------------------


class RoastRotator(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.roast_a = [
            "Bud thinks he can be #1… keep dreaming lil bro 💭",
            "You’re climbing the ranks? That’s cute. Call me when you hit double digits 🍼",
            "Plot-twist: the only thing you’re #1 at is copium consumption 📈😮‍💨",
            "You’re like a participation trophy with extra steps 🏅➡️🗑️",
            "Rankings updated! You moved up… one pixel. Congrats on the altitude sickness 🏔️",
            "If effort were ELO you’d still be on the loading screen 🕹️",
            "You’re the main character… in a filler episode nobody asked for 📺",
            "Keep grinding king, the top 10 ain’t ready for your 2-for-1 coupon energy 🧾",
            "You’re the human equivalent of a ‘coming soon’ banner that never drops 🚧",
            "You chase #1 like it owes you child-support 💸👶",
            "Your leaderboard push is slower than internet explorer on a Sunday 🐌",
            "You’re not the underdog, you’re the under-dog-toy squeaking in the corner 🧸",
            "Rising star? More like rising *‘meh’* ✨🫤",
            "You’re on the come-up… the short bus come-up 🚌",
            "Call NASA, your grindset just entered low-earth orbit 🚀🗑️",
            "You’re the main event… at the concession stand 🌭",
            "You’re so far from #1 Google Maps gave up 🗺️❌",
            "Keep hustling champ, participation ribbons don’t laminate themselves 🏅",
            "You’re the protagonist… of a tutorial level 🎮",
            "You’re like a pre-season boss fight – scripted to lose 📝",
            "Your ‘climb’ is flatter than week-old soda 🥤",
            "You’re the DLC nobody bought 🎮💳",
            "You’re the loading bar that goes backwards 📊↩️",
            "You’re the demo version of a better player 🥉",
            "You’re the human equivalent of a 404 page 🚫",
            "You’re the ‘skip intro’ button everyone slams ⏭️",
            "You’re the backup dancer in your own highlight reel 🕺",
            "You’re the ‘Are you still watching?’ pop-up 📺",
            "You’re the beta test that never made it to release 🐞",
            "You’re the ‘low power mode’ of competition 🔋",
            "You’re the ‘skip ad’ button – ignored in 5 seconds 🚫",
            "You’re the human equivalent of a typo 💬",
            "You’re the ‘retry’ button on a boss you can’t beat 🔄",
            "You’re the ‘meh’ emoji in human form 🫤",
            "You’re the ‘cancel’ button on a dialogue box 📤",
            "You’re the ‘demo expired’ watermark 🌊",
            "You’re the ‘please wait’ screen that never ends ⏳",
            "You’re the ‘error 404: skill not found’ page 🔍",
            "You’re the ‘low graphics’ setting in real life 🎮",
            "You’re the ‘skip tutorial’ regret 🎮",
            "You’re the ‘are you sure you want to continue?’ pop-up 🛑",
            "You’re the ‘backup save’ that got corrupted 💾",
            "You’re the ‘demo’ that crashes on launch 💥",
            "You’re the ‘please insert coin’ screen 🪙",
            "You’re the ‘low battery’ warning during the final boss 🔋",
            "You’re the ‘retry’ button on a level you can’t pass 🔄",
            "You’re the ‘skip intro’ cut-scene that had the tutorial 📺",
            "You’re the ‘demo’ with locked features 🔒",
            "You’re the ‘cancel download’ button 📥❌",
            "You’re the ‘please update’ notification 🔄",
            "You’re the ‘low spec’ version of yourself 🖥️",
            "You’re the ‘beta’ that never became alpha 🐶",
            "You’re the ‘error: skill ceiling reached’ message 📈🚫",
        ]

        self.roast_b = [
            "Acting tough on Discord? Bro you’re on Wi-Fi, not the streets 📶🚫",
            "You’re so hard… boiled – and still soft in the middle 🥚",
            "Cool story bro, needs a better main character 🎬",
            "You’re the main villain… in a Roblox RP 🧱",
            "You’re not edgy, you’re just circle-shaped ♟️",
            "You’re the final boss… of the tutorial island 🏝️",
            "You’re so intimidating my Wi-Fi dropped… from second-hand embarrassment 📶💀",
            "You’re the ‘skip cut-scene’ button incarnate ⏭️",
            "You’re the human equivalent of a CAPTCHA – nobody wants to deal with you 🤖",
            "You’re the ‘demo’ version of a villain – no real powers 🦹‍♂️❌",
            "You’re the ‘low graphics’ boss fight 🎮",
            "You’re the ‘please wait’ screen of bad guys ⏳",
            "You’re the ‘error 404: intimidation not found’ page 🔍",
            "You’re the ‘retry’ button on a boss you can’t beat 🔄",
            "You’re the ‘meh’ emoji in villain form 🫤",
            "You’re the ‘cancel’ button on a dialogue box 📤",
            "You’re the ‘demo expired’ watermark 🌊",
            "You’re the ‘please insert coin’ screen 🪙",
            "You’re the ‘low battery’ warning during the final boss 🔋",
            "You’re the ‘backup save’ that got corrupted 💾",
            "You’re the ‘demo’ that crashes on launch 💥",
            "You’re the ‘low spec’ version of a bad guy 🖥️",
            "You’re the ‘beta’ that never became alpha 🐶",
            "You’re the ‘error: evil not found’ message 🚫",
            "You’re the ‘skip ad’ button – ignored in 5 seconds 🚫",
            "You’re the ‘low power mode’ of evil 🔋",
            "You’re the ‘retry’ button on a level you can’t pass 🔄",
            "You’re the ‘skip intro’ cut-scene that had the tutorial 📺",
            "You’re the ‘demo’ with locked features 🔒",
            "You’re the ‘cancel download’ button 📥❌",
            "You’re the ‘please update’ notification 🔄",
            "You’re the ‘low graphics’ setting in real life 🎮",
            "You’re the ‘beta’ that never became alpha 🐶",
            "You’re the ‘error: skill ceiling reached’ message 📈🚫",
            "You’re the ‘please wait’ screen that never ends ⏳",
            "You’re the ‘error 404: evil not found’ page 🔍",
            "You’re the ‘low battery’ warning during the final boss 🔋",
            "You’re the ‘backup save’ that got corrupted 💾",
            "You’re the ‘demo’ that crashes on launch 💥",
            "You’re the ‘please insert coin’ screen 🪙",
            "You’re the ‘low spec’ version of yourself 🖥️",
            "You’re the ‘beta’ that never became alpha 🐶",
            "You’re the ‘error: evil not found’ message 🚫",
            "You’re the ‘skip ad’ button – ignored in 5 seconds 🚫",
            "You’re the ‘low power mode’ of evil 🔋",
            "You’re the ‘retry’ button on a level you can’t pass 🔄",
            "You’re the ‘skip intro’ cut-scene that had the tutorial 📺",
            "You’re the ‘demo’ with locked features 🔒",
            "You’re the ‘cancel download’ button 📥❌",
            "You’re the ‘please update’ notification 🔄",
            "You’re the ‘low graphics’ setting in real life 🎮",
            "You’re the ‘beta’ that never became alpha 🐶",
            "You’re the ‘error: evil not found’ message 🚫",
        ]

    @tasks.loop(minutes=2)
    async def roast_cycle(self):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        if self.index % 2 == 0:
            user_id, roasts = TARGET_A, self.roast_a
        else:
            user_id, roasts = TARGET_B, self.roast_b

        member = guild.get_member(user_id)
        if member and member.status != discord.Status.offline:
            channel = member.voice.channel or guild.system_channel or guild.text_channels[0]
            if channel:
                msg = random.choice(roasts)
                await channel.send(f"{member.mention} {msg}")
                log.info(f"Roasted {member.display_name}: {msg}")

        self.index += 1

    @roast_cycle.before_loop
    async def before_roast(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.roast_cycle.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(RoastRotator(bot))
