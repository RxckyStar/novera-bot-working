# cogs/anteup.py
# Novera — Ante Up (Wager Lobbies)
# - Command: !anteup <amount:int>
# - DM setup (region, mode, username, optional ps link, position)
# - Posts lobby to correct channel with position buttons per team
# - Prevents join if player value < amount
# - When full, host gets "Submit Result" -> Modal (winner team, screenshot URL)
# - Sends review to mod channel (Approve/Decline). Approve: winners +amount, losers -amount (min 0). Decline: no change.
# - Uses same data_manager functions as checkvalue/rankings/addvalue.

from __future__ import annotations
import asyncio, logging, random, time
from typing import Dict, List, Optional, Tuple

import discord
from discord.ext import commands

# ---------- CHANNELS (provided by you) ----------
CHAN_1V1 = 1351037569592328293
CHAN_2V2 = 1351037618606964849
CHAN_3V3 = 1351037659455295570
CHAN_5V5 = 1351037705961607168
MOD_REVIEW_CHAN = 1351221346192982046

# ---------- POSITIONS ----------
ALL_POS = ["CF", "LW", "RW", "CM", "GK"]
WING_POS = ["LW", "RW"]
CORE_POS = ["CF", "CM"]

# Mode -> team_size and allowed positions (GK only 5v5)
MODE_MAP = {
    "1v1": (1, ["CF"]),                 # simple CF vs CF
    "2v2": (2, ["CF", "LW", "RW", "CM"]),
    "3v3": (3, ["CF", "LW", "RW", "CM"]),
    "5v5": (5, ["CF", "LW", "RW", "CM", "GK"]),
}
REGIONS = ["NA", "EU"]

# Mommy vibes
MOMMY_DM_START = [
    "💖 Hey sweetie! Let’s set up your wager. Mommy will walk you through it, nice and easy~",
    "✨ Hi darling, ready to put some 💴 on the line? Let’s get your lobby set up!",
    "🎀 Welcome back, cutie—time to ante up. Follow Mommy’s prompts below.",
]
MOMMY_DM_DONE = [
    "All set, sweetie! I posted your lobby. Keep an eye on it. 💅",
    "Perfect, darling—your ad is live. Let’s fill those spots. 💖",
    "Lobby’s up and sparkling. Good luck, precious. ✨",
]
MOMMY_JOIN_FAIL_BAL = [
    "Oh no, {mention}—you need **≥ {amt}M** to join this wager, sweetie. 💔",
]
MOMMY_JOIN_TAKEN = [
    "That spot’s already taken, precious. Try another position. 💖",
]
MOMMY_FULL = [
    "Both teams are full! I’ve DM’d the host with the **Submit Result** button. Go have fun. ✨",
]

import data_manager  # must be the SAME module your checkvalue/rankings use

def get_value(uid: int) -> int:
    # These functions must exist in your existing data_manager module (same ones used by checkvalue)
    return int(data_manager.get_member_value(str(uid)))

def set_value(uid: int, new_val: int) -> None:
    data_manager.set_member_value(str(uid), int(max(0, new_val)))

def _team_rows_for(mode: str) -> List[str]:
    # Visual order for buttons per team (just labels; rows are set via Button.row)
    # Row layout (Team 1 left rows 0..2, Team 2 right rows 0..2 with offset)
    #   Row0: LW  CF  RW
    #   Row1:    CM
    #   Row2:    GK (5v5 only)
    return ["LW","CF","RW","CM","GK"]

def _mode_channel(mode: str, bot: commands.Bot) -> Optional[discord.abc.MessageableChannel]:
    mapping = {"1v1":CHAN_1V1, "2v2":CHAN_2V2, "3v3":CHAN_3V3, "5v5":CHAN_5V5}
    ch = bot.get_channel(mapping[mode])
    return ch

# ----------------- Lobby Model -----------------
class Lobby:
    def __init__(self, host_id: int, amount_m: int, region: str, mode: str, username: str, ps_link: Optional[str]):
        self.host_id = host_id
        self.amount_m = amount_m
        self.region = region
        self.mode = mode
        self.username = username
        self.ps_link = ps_link or "—"
        self.message_id: Optional[int] = None
        self.channel_id: Optional[int] = None
        size, allowed = MODE_MAP[mode]
        self.team_size = size
        self.allowed = allowed
        # rosters: dict pos -> user_id
        self.team1: Dict[str, Optional[int]] = {p: None for p in allowed}
        self.team2: Dict[str, Optional[int]] = {p: None for p in allowed}
        # only allow GK in 5v5 (already handled via allowed list)
        # creation time
        self.ts = int(time.time())

    def is_full(self) -> bool:
        return self._count_filled(self.team1) == self.team_size and self._count_filled(self.team2) == self.team_size

    def _count_filled(self, t: Dict[str, Optional[int]]) -> int:
        return sum(1 for v in t.values() if v)

    def team_lists(self) -> Tuple[List[int], List[int]]:
        t1 = [uid for uid in self.team1.values() if uid]
        t2 = [uid for uid in self.team2.values() if uid]
        return t1, t2

# ----------------- Views & Buttons -----------------
class PositionButton(discord.ui.Button):
    def __init__(self, lobby_id: int, team: int, pos: str, row: int, label: Optional[str]=None):
        super().__init__(style=discord.ButtonStyle.secondary, label=label or pos, row=row, custom_id=f"ante_{lobby_id}_{team}_{pos}")
        self.lobby_id = lobby_id
        self.team = team
        self.pos = pos

    async def callback(self, interaction: discord.Interaction):
        view: LobbyView = self.view  # type: ignore
        if not view or not view.lobby:
            return
        lobby = view.lobby
        # deny if spot taken
        target = lobby.team1 if self.team == 1 else lobby.team2
        if target.get(self.pos):
            await interaction.response.send_message(random.choice(MOMMY_JOIN_TAKEN), ephemeral=True)
            return
        # balance check
        user_id = interaction.user.id
        if get_value(user_id) < lobby.amount_m:
            msg = random.choice(MOMMY_JOIN_FAIL_BAL)[0 if True else 0]  # keep variant indexing simple
            await interaction.response.send_message(
                msg.format(mention=interaction.user.mention, amt=lobby.amount_m),
                ephemeral=True
            )
            return
        # place
        target[self.pos] = user_id
        # update label & disable
        self.label = f"{self.pos} • {interaction.user.display_name}"
        self.style = discord.ButtonStyle.success if self.team == 1 else discord.ButtonStyle.primary
        self.disabled = True
        await interaction.response.edit_message(embed=view.render_embed(interaction.client), view=view)
        # if full -> DM host with submit button
        if lobby.is_full():
            await view.on_full(interaction.client)

class SubmitResultButton(discord.ui.Button):
    def __init__(self, lobby_id: int):
        super().__init__(style=discord.ButtonStyle.success, label="Submit Result", custom_id=f"submit_{lobby_id}")

    async def callback(self, interaction: discord.Interaction):
        # Only the host can submit
        view: HostPanelView = self.view  # type: ignore
        if not view or interaction.user.id != view.host_id:
            await interaction.response.send_message("Only the host can submit results, sweetie. 💖", ephemeral=True)
            return
        await interaction.response.send_modal(ResultModal(view))

class ResultModal(discord.ui.Modal, title="Match Result"):
    def __init__(self, host_view: HostPanelView):
        super().__init__()
        self.host_view = host_view
        # winner input (1 or 2)
        self.winner_in = discord.ui.TextInput(
            label="Winner Team (1 or 2)", placeholder="1", required=True, max_length=1
        )
        # screenshot link
        self.link_in = discord.ui.TextInput(
            label="Screenshot URL", placeholder="https://...", required=True
        )
        self.add_item(self.winner_in)
        self.add_item(self.link_in)

    async def on_submit(self, interaction: discord.Interaction):
        winner_str = str(self.winner_in.value).strip()
        link = str(self.link_in.value).strip()
        if winner_str not in ("1", "2"):
            await interaction.response.send_message("Winner must be **1** or **2**, darling.", ephemeral=True)
            return
        await interaction.response.send_message("Got it! Sent to staff for review. ✨", ephemeral=True)
        await self.host_view.forward_to_staff(interaction.client, int(winner_str), link)

class HostPanelView(discord.ui.View):
    def __init__(self, lobby_id: int, host_id: int, lobby: Lobby):
        super().__init__(timeout=None)
        self.lobby_id = lobby_id
        self.host_id = host_id
        self.lobby = lobby
        self.add_item(SubmitResultButton(lobby_id))

    def build_summary_embed(self, bot: commands.Bot) -> discord.Embed:
        t1, t2 = self.lobby.team_lists()
        def mention_list(ids): return ", ".join(f"<@{i}>" for i in ids) if ids else "—"
        e = discord.Embed(
            title="🧾 Match Summary",
            description=f"Region **{self.lobby.region}** · Mode **{self.lobby.mode}** · Wager **💴 {self.lobby.amount_m}M**",
            color=discord.Color.purple()
        )
        e.add_field(name="Team 1", value=mention_list(t1), inline=False)
        e.add_field(name="Team 2", value=mention_list(t2), inline=False)
        e.add_field(name="PS Link", value=self.lobby.ps_link or "—", inline=False)
        host_user = bot.get_user(self.lobby.host_id)
        e.set_footer(text=f"Host: {host_user} • Lobby #{self.lobby.ts}")
        return e

    async def forward_to_staff(self, bot: commands.Bot, winner_team: int, screenshot_url: str):
        ch = bot.get_channel(MOD_REVIEW_CHAN)
        if not ch:
            return
        t1, t2 = self.lobby.team_lists()
        # pack review embed
        review = discord.Embed(
            title="🛡️ Wager Result Review",
            description=f"**Region:** {self.lobby.region} • **Mode:** {self.lobby.mode} • **Wager:** 💴 {self.lobby.amount_m}M\n"
                        f"**Winner Claimed:** Team {winner_team}",
            color=discord.Color.gold()
        )
        review.add_field(name="Team 1", value=", ".join(f"<@{i}>" for i in t1) or "—", inline=False)
        review.add_field(name="Team 2", value=", ".join(f"<@{i}>" for i in t2) or "—", inline=False)
        review.add_field(name="Screenshot", value=screenshot_url or "—", inline=False)
        review.set_footer(text=f"Host ID: {self.lobby.host_id} • Lobby #{self.lobby.ts}")

        view = StaffReviewView(self.lobby, winner_team, screenshot_url)
        await ch.send(embed=review, view=view)

class StaffReviewView(discord.ui.View):
    def __init__(self, lobby: Lobby, winner_team: int, screenshot_url: str):
        super().__init__(timeout=None)
        self.lobby = lobby
        self.winner_team = winner_team
        self.screenshot_url = screenshot_url

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button):
        # Only let mods/admins use this (manage_messages privilege is enough)
        if not getattr(interaction.user.guild_permissions, "manage_messages", False):
            await interaction.response.send_message("You don’t have permission to approve, sweetie.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=False)
        winners, losers = (self.lobby.team_lists() if self.winner_team == 1 else (self.lobby.team_lists()[1], self.lobby.team_lists()[0]))
        # Adjust values
        amt = self.lobby.amount_m
        for uid in winners:
            try: set_value(uid, get_value(uid) + amt)
            except Exception: pass
        for uid in losers:
            try: set_value(uid, max(0, get_value(uid) - amt))
            except Exception: pass
        # Confirm in thread
        done = discord.Embed(
            title="✅ Results Approved",
            description=f"Team {self.winner_team} awarded **💴 {amt}M** each. Losers deducted the same (min 0).",
            color=discord.Color.green()
        )
        await interaction.message.edit(embed=done, view=None)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not getattr(interaction.user.guild_permissions, "manage_messages", False):
            await interaction.response.send_message("You don’t have permission to decline, darling.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=False)
        done = discord.Embed(
            title="❌ Results Declined",
            description="No value changes were applied. (No escrow.)",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=done, view=None)

class LobbyView(discord.ui.View):
    def __init__(self, lobby: Lobby, lobby_id: int):
        super().__init__(timeout=None)
        self.lobby = lobby
        self.lobby_id = lobby_id
        self._build_buttons()

    def _build_buttons(self):
        # Build two mirrored sides: Team1 rows 0..2, Team2 rows 0..2 (offset +3)
        # Row mapping: 0:[LW,CF,RW], 1:[CM], 2:[GK (5v5 only)]
        layout = ["LW","CF","RW","CM","GK"]
        allowed = self.lobby.allowed
        # Team 1
        for pos in layout:
            if pos not in allowed: 
                continue
            row = 0 if pos in ("LW","CF","RW") else (1 if pos=="CM" else 2)
            self.add_item(PositionButton(self.lobby.ts, 1, pos, row=row, label=pos))
        # Team 2 (offset rows)
        for pos in layout:
            if pos not in allowed: 
                continue
            row = (0 if pos in ("LW","CF","RW") else (1 if pos=="CM" else 2)) + 3
            self.add_item(PositionButton(self.lobby.ts, 2, pos, row=row, label=pos))

    def render_embed(self, bot: commands.Bot) -> discord.Embed:
        def fmt_team(team: Dict[str, Optional[int]]) -> str:
            rows = []
            for pos in ["LW","CF","RW","CM","GK"]:
                if pos not in self.lobby.allowed:
                    continue
                uid = team.get(pos)
                rows.append(f"**{pos}** — {('<@'+str(uid)+'>') if uid else '`Open`'}")
            return "\n".join(rows)

        e = discord.Embed(
            title="🎮 Ante Up Lobby",
            description=f"**Region:** {self.lobby.region} • **Mode:** {self.lobby.mode} • **Wager:** 💴 {self.lobby.amount_m}M\n"
                        f"**Host:** <@{self.lobby.host_id}> • **PS:** {self.lobby.ps_link}",
            color=discord.Color.purple()
        )
        e.add_field(name="Team 1", value=fmt_team(self.lobby.team1), inline=True)
        e.add_field(name="Team 2", value=fmt_team(self.lobby.team2), inline=True)
        e.set_footer(text=f"Lobby #{self.lobby.ts} • Click a position to join")
        return e

    async def on_full(self, bot: commands.Bot):
        # DM host with submit button & summary
        try:
            host = bot.get_user(self.lobby.host_id) or await bot.fetch_user(self.lobby.host_id)
            if host:
                dm = await host.create_dm()
                await dm.send(random.choice(MOMMY_FULL))
                panel = HostPanelView(self.lobby.ts, self.lobby.host_id, self.lobby)
                await dm.send(embed=panel.build_summary_embed(bot), view=panel)
        except Exception:
            logging.exception("Failed to DM host with submit panel")

# ----------------- Cog -----------------
class AnteUp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lobbies: Dict[int, Lobby] = {}  # key: lobby.ts

    @commands.command(name="anteup")
    @commands.guild_only()
    async def anteup(self, ctx: commands.Context, amount: Optional[int] = None):
        """Start wager setup via DMs."""
        if amount is None or amount <= 0:
            await ctx.reply("Use: `!anteup <amount_millions>` e.g. `!anteup 10`", mention_author=False)
            return

        # DM flow
        try:
            dm = await ctx.author.create_dm()
            await dm.send(random.choice(MOMMY_DM_START))

            # Region
            region = await self.ask_select(dm, ctx.author, "Pick your **Region**", REGIONS)
            # Mode
            mode = await self.ask_select(dm, ctx.author, "Pick **Mode**", list(MODE_MAP.keys()))
            # Username
            username = await self.ask_text(dm, ctx.author, "Your in-game **username**?", required=True)
            # Private server link (optional)
            ps_link = await self.ask_text(dm, ctx.author, "Private server link (optional). Send `skip` to skip.", required=False)
            if ps_link and ps_link.lower().strip() == "skip":
                ps_link = None
            # Position (GK available only for 5v5)
            allowed = MODE_MAP[mode][1]
            position = await self.ask_select(dm, ctx.author, "Pick your **starting position** (you can still choose any spot later)", allowed)

            # Create lobby
            lobby = Lobby(ctx.author.id, amount, region, mode, username, ps_link)
            lobby_id = lobby.ts

            # Post to correct channel
            ch = _mode_channel(mode, self.bot)
            if not ch:
                await dm.send("I couldn’t find the lobby channel, sweetie. Tell your admin to check channel IDs.")
                return

            # Build view and embed
            view = LobbyView(lobby, lobby_id)
            msg = await ch.send(embed=view.render_embed(self.bot), view=view)
            lobby.message_id = msg.id
            lobby.channel_id = ch.id
            # Pre-fill the host’s first slot if open for that position (Team 1)
            if position in lobby.allowed and lobby.team1.get(position) is None:
                lobby.team1[position] = ctx.author.id
                # Update the two matching buttons (team1 position) to show taken
                for item in view.children:
                    if isinstance(item, PositionButton) and item.team == 1 and item.pos == position:
                        item.label = f"{position} • {ctx.author.display_name}"
                        item.style = discord.ButtonStyle.success
                        item.disabled = True
                await msg.edit(embed=view.render_embed(self.bot), view=view)

            self.lobbies[lobby_id] = lobby
            await dm.send(random.choice(MOMMY_DM_DONE))

        except discord.Forbidden:
            await ctx.reply("I couldn’t DM you—please open your DMs and try again.", mention_author=False)
            return
        except Exception:
            logging.exception("anteup DM flow error")
            await ctx.reply("Something went wrong setting up your wager.", mention_author=False)

    # ---- small DM helpers ----
    async def ask_select(self, dm: discord.DMChannel, user: discord.User, prompt: str, options: List[str]) -> str:
        view = _OneSelect(options)
        m = await dm.send(prompt, view=view)
        for _ in range(300):
            await asyncio.sleep(0.5)
            if view.choice:
                try: await m.edit(view=None)
                except: pass
                return view.choice
        raise TimeoutError("select timeout")

    async def ask_text(self, dm: discord.DMChannel, user: discord.User, prompt: str, required: bool) -> Optional[str]:
        await dm.send(prompt)
        def check(message: discord.Message):
            return message.author.id == user.id and message.channel.id == dm.id
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=300)
            return msg.content.strip() if (required or msg.content.strip()) else None
        except asyncio.TimeoutError:
            raise

class _OneSelect(discord.ui.View):
    def __init__(self, options: List[str]):
        super().__init__(timeout=300)
        self.choice: Optional[str] = None
        opts = [discord.SelectOption(label=o, value=o) for o in options]
        self.select = discord.ui.Select(placeholder="Select…", options=opts, min_values=1, max_values=1)
        self.select.callback = self._on_select
        self.add_item(self.select)
    async def _on_select(self, interaction: discord.Interaction):
        self.choice = self.select.values[0]
        await interaction.response.send_message(f"Selected **{self.choice}**", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AnteUp(bot))
