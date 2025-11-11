from __future__ import annotations
import discord, logging, asyncio, random
from discord.ext import commands
import data_manager

log = logging.getLogger(__name__)

# ------------- config -------------
CH_1V1 = 1351037569592328293
CH_2V2 = 1351037618606964849
CH_3V3 = 1351037659455295570
CH_5V5 = 1351037705961607168
MOD_CH = 1351221346192982046
PING_ROLE_ID = 1437677085026943058
AUTO_CLOSE_H = 4  # hours

# ------------- constants ----------
REGIONS = ["NA", "EU"]
MODES = ["1v1", "2v2", "3v3", "5v5"]
POSITIONS_FULL = ["CF", "LW", "RW", "CM", "GK"]

# mommy vibe variants
MOMMY_DM_START = [
    "💋 Mommy’s ready to set your wager ad, sweetie~",
    "🎀 Let’s get your duel listed, darling!",
    "💖 Time to show the server what you’re worth!"
]
MOMMY_CHECK_DMS = [
    "Check your DMs, cutie~ 💌",
    "Mommy slid into your DMs~ 💕",
    "Look at your private messages, sweetie! 💌"
]
MOMMY_PICK_REGION = [
    "Pick your **region**:",
    "Where do you play, darling?",
    "Choose your region, sweetie~"
]
MOMMY_PICK_MODE = [
    "Pick your **mode**:",
    "How many fighters, cutie?",
    "Select the duel size, darling~"
]
MOMMY_USER_NAME = [
    "Type your **Roblox username**:",
    "What name do you go by, sweetie?",
    "Your Roblox username, darling~"
]
MOMMY_PS_LINK = [
    "Paste a **private-server link** (or type `skip`):",
    "Got a PS link, cutie? (or `skip`)",
    "Share your private server, darling~ (or `skip`)"
]
MOMMY_PICK_POS = [
    "Pick your **position**:",
    "Where will you play, sweetie?",
    "Choose your role, darling~"
]
MOMMY_AD_NOTE = "📸 **Screenshot the final stats** – no proof = no payout!"
MOMMY_AD_FOOTER = "Mommy’s watching~ Play fair and come back with proof! 💕"
AD_TITLE_VARIANTS = [
    "💰 Mommy’s Wager Board",
    "💰 Novera Duel Listing",
    "💋 Ante-Up with Mommy"
]
AD_DESC_VARIANTS = [
    "Big stakes, big dreams~ Let’s see who takes the pot!",
    "Put your yen where your boots are, sweetie~",
    "Winner gets richer, loser learns~ Mommy’s rules 💕"
]

# ------------- helpers -------------
def mode_channel_map(bot: commands.Bot, mode: str):
    return {
        "1v1": bot.get_channel(CH_1V1),
        "2v2": bot.get_channel(CH_2V2),
        "3v3": bot.get_channel(CH_3V3),
        "5v5": bot.get_channel(CH_5V5),
    }.get(mode)

def applicable_positions(mode: str) -> list[str]:
    if mode == "1v1":
        return ["CF"]
    if mode in ("2v2", "3v3"):
        return ["CF", "LW", "RW", "CM"]
    return POSITIONS_FULL


# ------------- compact DM flow -------------
class DMDuelSetup:
    def __init__(self, user: discord.User, bot: commands.Bot):
        self.user = user
        self.bot = bot
        self.mode: str | None = None
        self.region: str | None = None
        self.username: str | None = None
        self.ps_link: str | None = None
        self.position: str | None = None
        self.stake: int = 10

    async def run(self) -> tuple[str, str, str, str, str, int] | None:
        dm = await self.user.create_dm()
        await dm.send(random.choice(MOMMY_DM_START))

        # region
        await dm.send(random.choice(MOMMY_PICK_REGION))
        self.region = await self._select_menu([discord.SelectOption(label=r) for r in REGIONS], dm)
        if not self.region:
            return None

        # mode
        await dm.send(random.choice(MOMMY_PICK_MODE))
        self.mode = await self._select_menu([discord.SelectOption(label=m) for m in MODES], dm)
        if not self.mode:
            return None

        # username
        await dm.send(random.choice(MOMMY_USER_NAME))
        msg = await self.bot.wait_for(
            "message",
            check=lambda m: m.author == self.user and m.channel == dm,
            timeout=120,
        )
        self.username = msg.content.strip()

        # ps link
        await dm.send(random.choice(MOMMY_PS_LINK))
        msg = await self.bot.wait_for(
            "message",
            check=lambda m: m.author == self.user and m.channel == dm,
            timeout=120,
        )
        self.ps_link = "" if msg.content.strip().lower() == "skip" else msg.content.strip()

        # position
        await dm.send(random.choice(MOMMY_PICK_POS))
        opts = [discord.SelectOption(label=p) for p in applicable_positions(self.mode)]
        self.position = await self._select_menu(opts, dm)
        if not self.position:
            return None

        await dm.send("💖 All set! Mommy created your ad — check the server!")
        return self.region, self.mode, self.username, self.ps_link, self.position, self.stake

    async def _select_menu(self, options: list[discord.SelectOption], dm: discord.DMChannel) -> str | None:
        view = discord.ui.View(timeout=120)
        select = discord.ui.Select(placeholder="Choose…", options=options)
        view.add_item(select)
        chosen: str | None = None

        async def cb(inter: discord.Interaction):
            nonlocal chosen
            chosen = select.values[0]
            await inter.response.send_message(f"Got it: **{chosen}**", ephemeral=True)

        select.callback = cb
        msg = await dm.send(view=view)
        for _ in range(240):
            await asyncio.sleep(0.5)
            if chosen:
                break
        try:
            await msg.edit(view=None)
        except:
            pass
        return chosen


# ------------- sexy grid view -------------
class PositionButton(discord.ui.Button):
    def __init__(self, team: str, pos: str, mode: str):
        super().__init__(label=f"{team}:{pos}", style=discord.ButtonStyle.blurple)
        self.team = team
        self.pos = pos
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        board: "TeamBoard" = self.view
        uid = interaction.user.id

        if uid in [u for u, _ in board.teamA + board.teamB]:
            await interaction.response.send_message("You already picked a spot, sweetie~ 💕", ephemeral=True)
            return

        tgt = board.teamA if self.team == "A" else board.teamB
        if len(tgt) >= board.max_per_team:
            await interaction.response.send_message("Team’s full, darling~", ephemeral=True)
            return

        if any(p == self.pos for _, p in tgt):
            await interaction.response.send_message("Position taken, cutie~", ephemeral=True)
            return

        tgt.append((uid, self.pos))
        self.label = f"{interaction.user.display_name}"
        self.style = discord.ButtonStyle.gray
        self.disabled = True

        await interaction.response.defer()
        await board._refresh_embed()
        await board._check_full()


class LeaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Leave Position", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        board: "TeamBoard" = self.view
        uid = interaction.user.id

        if len(board.teamA) == board.max_per_team and len(board.teamB) == board.max_per_team:
            await interaction.response.send_message("Match is already full — can’t cancel now 💕", ephemeral=True)
            return

        if uid == board.creator_id:
            # host leaving cancels ad
            await board.cancel_ad(interaction)
            return

        if uid in [u for u, _ in board.teamA]:
            board.teamA = [(u, p) for u, p in board.teamA if u != uid]
        elif uid in [u for u, _ in board.teamB]:
            board.teamB = [(u, p) for u, p in board.teamB if u != uid]
        else:
            await interaction.response.send_message("You don't have a position to leave, sweetie~ 💕", ephemeral=True)
            return

        await interaction.response.defer()
        await board._refresh_embed()


class TeamBoard(discord.ui.View):
    def __init__(self, creator_id: int, mode: str, region: str, username: str, ps_link: str, stake_m: int):
        super().__init__(timeout=AUTO_CLOSE_H * 3600)
        self.creator_id = creator_id
        self.mode = mode
        self.region = region
        self.username = username
        self.ps_link = ps_link
        self.stake_m = stake_m
        self.teamA: list[tuple[int, str]] = []
        self.teamB: list[tuple[int, str]] = []
        self.max_per_team = {"1v1": 1, "2v2": 2, "3v3": 3, "5v5": 5}[mode]
        self.message: discord.Message | None = None
        self._build_grid()
        self._start_auto_close()

    def _build_grid(self):
        positions = applicable_positions(self.mode)
        for pos in positions:
            self.add_item(PositionButton("A", pos, self.mode))
        for pos in positions:
            self.add_item(PositionButton("B", pos, self.mode))
        self.add_item(LeaveButton())

    async def cancel_ad(self, interaction: discord.Interaction):
        if not self.message:
            return
        try:
            await self.message.edit(content="❌ Ad cancelled by host.", embed=None, view=None)
        except:
            pass
        for uid, _ in self.teamA + self.teamB:
            try:
                user = await self.message.guild.fetch_member(uid)
                dm = await user.create_dm()
                await dm.send("❌ The wager ad you joined was cancelled by the host.")
            except:
                pass
        await interaction.response.send_message("Ad cancelled.", ephemeral=True)
        self.stop()

    def _start_auto_close(self):
        async def _close():
            await asyncio.sleep(AUTO_CLOSE_H * 3600)
            if self.message:
                try:
                    await self.message.edit(content="💤 **Ad expired** – Mommy closed it after 4 hours.", embed=None, view=None)
                except:
                    pass
        asyncio.create_task(_close())

    async def _refresh_embed(self):
        if not self.message:
            return
        try:
            for item in self.children:
                if isinstance(item, PositionButton):
                    # grey out taken
                    taken = any(p == item.pos and ((item.team == "A" and u in [x for x, _ in self.teamA]) or (item.team == "B" and u in [x for x, _ in self.teamB])) for u, p in self.teamA + self.teamB)
                    item.disabled = taken
                    item.style = discord.ButtonStyle.gray if taken else discord.ButtonStyle.blurple
            await self.message.edit(embed=self._build_embed(), view=self)
        except:
            pass

    def _build_embed(self) -> discord.Embed:
        title = random.choice(AD_TITLE_VARIANTS)
        desc = (
            random.choice(AD_DESC_VARIANTS)
            + f"\n**Mode:** {self.mode} • **Region:** {self.region} • **Stake:** ¥{self.stake_m}M per player\n**Creator:** <@{self.creator_id}> • **Username:** {self.username}\n"
            + (f"**PS Link:** {self.ps_link}\n" if self.ps_link else "")
            + f"\n{MOMMY_AD_NOTE}"
        )
        emb = discord.Embed(title=title, description=desc, color=discord.Color.gold())

        def fmt(team):
            return "\n".join(f"<@{uid}> — **{pos}**" for uid, pos in team) or "—"

        emb.add_field(name="Team A", value=fmt(self.teamA), inline=True)
        emb.add_field(name="Team B", value=fmt(self.teamB), inline=True)
        emb.set_footer(text=MOMMY_AD_FOOTER)
        return emb

    async def _check_full(self):
        if len(self.teamA) == self.max_per_team and len(self.teamB) == self.max_per_team:
            btn = discord.ui.Button(label="Submit Match Result", style=discord.ButtonStyle.success, emoji="📸")
            btn.callback = self._open_result_modal
            self.add_item(btn)
            await self._refresh_embed()
            for uid in {u for u, _ in self.teamA + self.teamB}:
                try:
                    user = await self.message.guild.fetch_member(uid)
                    dm = await user.create_dm()
                    await dm.send("💋 Match is ready! Play your game, **screenshot the final stats**, then submit results.")
                except:
                    pass

    async def _open_result_modal(self, interaction: discord.Interaction):
        if interaction.user.id not in [u for u, _ in self.teamA + self.teamB]:
            await interaction.response.send_message("Only players in this match can submit, sweetie~", ephemeral=True)
            return
        await interaction.response.send_modal(ResultModal(self))


class ResultModal(discord.ui.Modal, title="Match Result"):
    def __init__(self, board: TeamBoard):
        super().__init__()
        self.board = board
    proof_url = discord.ui.TextInput(label="Screenshot URL (final stats)", placeholder="https://...", required=True)
    winner = discord.ui.TextInput(label="Which team won? (A or B)", placeholder="A", required=True, min_length=1, max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        winner = self.winner.value.strip().upper()
        if winner not in ("A", "B"):
            await interaction.response.send_message("Type **A** or **B** for the winner.", ephemeral=True)
            return
        ch = interaction.client.get_channel(MOD_CH)
        if not ch:
            await interaction.response.send_message("Mod channel not found.", ephemeral=True)
            return
        emb = discord.Embed(title="📸 Match Result Awaiting Review", color=discord.Color.blurple())
        emb.add_field(name="Mode / Region", value=f"{self.board.mode} • {self.board.region}", inline=False)
        emb.add_field(name="Stake", value=f"¥{self.board.stake_m}M per player", inline=False)
        emb.add_field(name="Winner", value=f"Team {winner}", inline=False)
        emb.add_field(name="Proof", value=self.proof_url.value, inline=False)

        def fmt(team): return ", ".join(f"<@{uid}>" for uid, _ in team) or "—"

        emb.add_field(name="Team A", value=fmt(self.board.teamA), inline=False)
        emb.add_field(name="Team B", value=fmt(self.board.teamB), inline=False)
        emb.set_footer(text="Approve = move values. Decline = no change.")
        await ch.send(embed=emb, view=ModApproveView(self.board, winner))
        await interaction.response.send_message("Proof sent to mods for review. 💖", ephemeral=True)


class ModApproveView(discord.ui.View):
    def __init__(self, board: TeamBoard, winner: str):
        super().__init__(timeout=None)
        self.board = board
        self.winner = winner

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, inter: discord.Interaction, _: discord.ui.Button):
        await self._settle(inter)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline(self, inter: discord.Interaction, _: discord.ui.Button):
        await inter.response.send_message("❌ Declined – no values moved.", ephemeral=True)

    async def _settle(self, inter: discord.Interaction):
        winners = self.board.teamA if self.winner == "A" else self.board.teamB
        losers = self.board.teamB if self.winner == "A" else self.board.teamA
        stake = int(self.board.stake_m)
        try:
            for uid, _ in winners:
                old = data_manager.get_member_value(str(uid))
                data_manager.set_member_value(str(uid), old + stake * len(losers))
            for uid, _ in losers:
                old = data_manager.get_member_value(str(uid))
                data_manager.set_member_value(str(uid), max(0, old - stake * len(winners)))
            await inter.response.send_message("✅ Values updated – winners paid, losers debited.", ephemeral=True)
            for uid, _ in self.board.teamA + self.board.teamB:
                try:
                    user = await self.board.message.guild.fetch_member(uid)
                    dm = await user.create_dm()
                    await dm.send("✅ Your match result has been approved by the mods!")
                except:
                    pass
        except Exception as e:
            await inter.response.send_message(f"Error updating values: {e}", ephemeral=True)


# ------------- cog -------------
class AnteUp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.guild_only()
    @commands.command(name="anteup")
    async def anteup(self, ctx: commands.Context, stake_m: int = 10):
        """Start a wager ad. Usage: !anteup [stake_millions]"""
        user = ctx.author
        try:
            await ctx.send(random.choice(MOMMY_CHECK_DMS), mention_author=False)
            setup = DMDuelSetup(user, self.bot)
            params = await setup.run()
            if not params:
                return await ctx.send("DM setup cancelled, sweetie~ 💕")
            region, mode, username, ps_link, position, stake =_
