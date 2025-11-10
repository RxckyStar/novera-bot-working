from __future__ import annotations
import discord, logging, asyncio, time, random
from discord.ext import commands
import data_manager

log = logging.getLogger(__name__)

# Channels for modes
CH_1V1 = 1351037569592328293
CH_2V2 = 1351037618606964849
CH_3V3 = 1351037659455295570
CH_5V5 = 1351037705961607168
MOD_CH = 1351221346192982046

REGIONS = ["NA", "EU"]
MODES = ["1v1", "2v2", "3v3", "5v5"]
POSITIONS = ["CF", "LW", "RW", "CM", "GK"]

def mode_channel_map(bot: commands.Bot, mode: str):
    mapping = {
        "1v1": bot.get_channel(CH_1V1),
        "2v2": bot.get_channel(CH_2V2),
        "3v3": bot.get_channel(CH_3V3),
        "5v5": bot.get_channel(CH_5V5),
    }
    return mapping.get(mode)

class CollectText(discord.ui.Modal, title="Submit Match Result"):
    screenshot_url = discord.ui.TextInput(label="Screenshot URL", placeholder="https://... (proof of winner)", required=True)
    def __init__(self, on_submit):
        super().__init__()
        self._on_submit = on_submit
    async def on_submit(self, interaction: discord.Interaction):
        await self._on_submit(str(self.screenshot_url), interaction)

class TeamBoard(discord.ui.View):
    def __init__(self, creator_id: int, mode: str, region: str, username: str, ps_link: str, stake_m: int):
        super().__init__(timeout=3600)
        self.creator_id = creator_id
        self.mode = mode
        self.region = region
        self.username = username
        self.ps_link = ps_link
        self.stake_m = stake_m
        self.teamA = []
        self.teamB = []
        self.max_per_team = {"1v1": 1, "2v2": 2, "3v3": 3, "5v5": 5}[mode]
        for pos in POSITIONS:
            disabled = (pos == "GK" and self.max_per_team < 5)
            btnA = discord.ui.Button(label=f"A:{pos}", style=discord.ButtonStyle.primary, disabled=disabled, custom_id=f"join_A_{pos}")
            btnB = discord.ui.Button(label=f"B:{pos}", style=discord.ButtonStyle.secondary, disabled=disabled, custom_id=f"join_B_{pos}")
            btnA.callback = self._join_factory("A", pos)
            btnB.callback = self._join_factory("B", pos)
            self.add_item(btnA); self.add_item(btnB)
        self.start_ts = time.time()
        self.message: discord.Message | None = None

    def _join_factory(self, team: str, pos: str):
        async def _cb(inter: discord.Interaction):
            member = inter.user
            uid = member.id
            if any(uid == u for u, _ in self.teamA + self.teamB):
                await inter.response.send_message("You're already on a team here, sweetie 💖", ephemeral=True); return
            team_list = self.teamA if team == "A" else self.teamB
            if len(team_list) >= self.max_per_team:
                await inter.response.send_message("That team is full, darling.", ephemeral=True); return
            if any(p == pos for _, p in team_list):
                await inter.response.send_message("That position is already taken on this team.", ephemeral=True); return
            team_list.append((uid, pos))
            await inter.response.send_message(f"Joined **Team {team}** as **{pos}** ✅", ephemeral=True)
            await self._refresh_embed()
            await self._check_full()
        return _cb

    async def _refresh_embed(self):
        if not self.message: return
        try:
            await self.message.edit(embed=self._build_embed(), view=self)
        except Exception:
            pass

    def _build_embed(self) -> discord.Embed:
        emb = discord.Embed(
            title="💴 Novera Wager (Ante Up)",
            description=f"**Mode:** {self.mode} • **Region:** {self.region} • **Stake:** ¥{self.stake_m}M per player\n"
                        f"**Creator:** <@{self.creator_id}> • **Username:** {self.username}\n"
                        + (f"**PS Link:** {self.ps_link}\n" if self.ps_link else ""),
            color=discord.Color.gold()
        )
        def fmt(team):
            if not team: return "—"
            return "\n".join(f"<@{uid}> — **{pos}**" for uid, pos in team)
        emb.add_field(name="Team A", value=fmt(self.teamA), inline=True)
        emb.add_field(name="Team B", value=fmt(self.teamB), inline=True)
        emb.set_footer(text="Pick a slot to join. When both teams fill, you'll be DMed to submit results after your match.")
        return emb

    async def _check_full(self):
        if len(self.teamA) == self.max_per_team and len(self.teamB) == self.max_per_team:
            users = list({uid for uid, _ in self.teamA + self.teamB})
            for uid in users:
                user = await self.message.guild.fetch_member(uid)
                try:
                    dm = await user.create_dm()
                    await dm.send("Match is ready! Play your game and then submit a screenshot using the button on the ad.")
                except Exception:
                    pass
            async def open_modal(inter: discord.Interaction):
                await inter.response.send_modal(CollectText(self._on_result_submit))  # <-- FIX: defer inside modal instead
            btn = discord.ui.Button(label="Submit Match Result", style=discord.ButtonStyle.success)
            btn.callback = open_modal
            self.add_item(btn)
            await self._refresh_embed()

    async def _on_result_submit(self, screenshot_url: str, interaction: discord.Interaction):
        try:
            ch = interaction.client.get_channel(MOD_CH)
            if not ch:
                await interaction.followup.send("Couldn't find mod channel.", ephemeral=True); return
            emb = discord.Embed(
                title="📥 Wager Result Submitted",
                description=f"Mode **{self.mode}** • Region **{self.region}** • Stake **¥{self.stake_m}M**\nScreenshot: {screenshot_url}",
                color=discord.Color.blurple()
            )
            def ids(team): return [uid for uid, _ in team]
            emb.add_field(name="Team A", value=", ".join(f"<@{u}>" for u in ids(self.teamA)) or "—", inline=False)
            emb.add_field(name="Team B", value=", ".join(f"<@{u}>" for u in ids(self.teamB)) or "—", inline=False)
            await ch.send(embed=emb, view=ModVerifyView(self))
            await interaction.followup.send("Sent to moderators for review. 💖", ephemeral=True)
        except Exception:
            await interaction.followup.send("Failed sending to moderators.", ephemeral=True)

class ModVerifyView(discord.ui.View):
    def __init__(self, board: TeamBoard):
        super().__init__(timeout=None)
        self.board = board

    @discord.ui.button(label="Approve Results (Team A Won)", style=discord.ButtonStyle.success)
    async def approve_a(self, inter: discord.Interaction, btn: discord.ui.Button):
        await self._settle(inter, winner="A")

    @discord.ui.button(label="Approve Results (Team B Won)", style=discord.ButtonStyle.success)
    async def approve_b(self, inter: discord.Interaction, btn: discord.ui.Button):
        await self._settle(inter, winner="B")

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, inter: discord.Interaction, btn: discord.ui.Button):
        await inter.response.send_message("❌ Declined. No value changes were applied. Refunds not needed (no pre-hold).", ephemeral=True)

    async def _settle(self, inter: discord.Interaction, winner: str):
        try:
            winners = self.board.teamA if winner == "A" else self.board.teamB
            losers  = self.board.teamB if winner == "A" else self.board.teamA
            stake = int(self.board.stake_m)
            for uid, _ in winners:
                s = str(uid)
                old = data_manager.get_member_value(s)
                data_manager.set_member_value(s, old + stake)   # <-- FIX: add, not overwrite
            for uid, _ in losers:
                s = str(uid)
                old = data_manager.get_member_value(s)
                data_manager.set_member_value(s, max(0, old - stake))
            await inter.response.send_message("✅ Results approved and values updated.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"Error settling match: {e}", ephemeral=True)

class AnteUp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.guild_only()
    @commands.command(name="anteup")
    async def anteup(self, ctx: commands.Context, stake_m: int = 10):
        """Start a wager ad via DMs. Usage: !anteup [stake_in_millions]"""
        user = ctx.author
        try:
            dm = await user.create_dm()
            await dm.send("💴 Let's set your wager ad, sweetie.")
            # (all the long DM flow stays identical)
            region_select = discord.ui.Select(placeholder="Region", options=[discord.SelectOption(label=r) for r in REGIONS])
            region_value = {"val": None}
            async def region_cb(i: discord.Interaction):
                region_value["val"] = region_select.values[0]
                await i.response.send_message(f"Region: **{region_value['val']}**", ephemeral=True)
            region_select.callback = region_cb
            v1 = discord.ui.View(); v1.add_item(region_select)
            m1 = await dm.send("Pick your **region**:", view=v1)
            for _ in range(600):
                await asyncio.sleep(0.5)
                if region_value["val"]: break
            try: await m1.edit(view=None)
            except: pass
            if not region_value["val"]:
                await dm.send("Cancelled (no region)."); return
            mode_select = discord.ui.Select(placeholder="Mode", options=[discord.SelectOption(label=m) for m in MODES])
            mode_value = {"val": None}
            async def mode_cb(i: discord.Interaction):
                mode_value["val"] = mode_select.values[0]
                await i.response.send_message(f"Mode: **{mode_value['val']}**", ephemeral=True)
            mode_select.callback = mode_cb
            v2 = discord.ui.View(); v2.add_item(mode_select)
            m2 = await dm.send("Pick your **mode**:", view=v2)
            for _ in range(600):
                await asyncio.sleep(0.5)
                if mode_value["val"]: break
            try: await m2.edit(view=None)
            except: pass
            if not mode_value["val"]:
                await dm.send("Cancelled (no mode)."); return
            await dm.send("Type your **Roblox username**:")
            def check(me: discord.Message): return me.author.id == user.id and me.channel.id == dm.id
            msg_user = await self.bot.wait_for("message", timeout=240, check=check)
            username = msg_user.content.strip()
            await dm.send("Paste a **private server link** (or type `skip`)")
            msg_ps = await self.bot.wait_for("message", timeout=240, check=check)
            ps_link = "" if msg_ps.content.strip().lower() == "skip" else msg_ps.content.strip()
            pos_select = discord.ui.Select(placeholder="Your position", options=[discord.SelectOption(label=p) for p in POSITIONS])
            pos_value = {"val": None}
            async def pos_cb(i: discord.Interaction):
                pos_value["val"] = pos_select.values[0]
                await i.response.send_message(f"Position: **{pos_value['val']}**", ephemeral=True)
            pos_select.callback = pos_cb
            v3 = discord.ui.View(); v3.add_item(pos_select)
            m3 = await dm.send("Pick your **position**:", view=v3)
            for _ in range(600):
                await asyncio.sleep(0.5)
                if pos_value["val"]: break
            try: await m3.edit(view=None)
            except: pass
            if not pos_value["val"]:
                await dm.send("Cancelled (no position)."); return
            ch = mode_channel_map(self.bot, mode_value["val"])
            if not ch:
                await dm.send("I couldn't find the channel for that mode."); return
            board = TeamBoard(creator_id=user.id, mode=mode_value["val"], region=region_value["val"],
                              username=username, ps_link=ps_link, stake_m=int(stake_m))
            board.teamA.append((user.id, pos_value["val"]))
            emb = board._build_embed()
            msg = await ch.send(embed=emb, view=board)
            board.message = msg
            await dm.send(f"Your wager ad is live in {ch.mention}!")
        except asyncio.TimeoutError:
            await user.send("Timed out. Start again with `!anteup`.")
        except discord.Forbidden:
            await ctx.reply("I couldn't DM you. Enable DMs and try again.", mention_author=False)
        except Exception as e:
            log.exception("anteup failed")
            await ctx.reply("Something went wrong starting the wager. Try again.", mention_author=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(AnteUp(bot))
