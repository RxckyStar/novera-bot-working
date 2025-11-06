# cogs/wagers.py
# Novera Wager / Anteup with Team Builder, Positions, Escrow, Mod Verify
# - DM setup (mode, team, position) with channel fallback
# - Lobby ad embed with join buttons
# - GK locked except in 5v5
# - Refund on decline, payout on approval
# - Persistent mod approve/decline buttons
# - Uses data_manager (get/set member value)

from __future__ import annotations
import asyncio, logging, time, traceback, random
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime

import discord
from discord.ext import commands

# ====== CONFIG ================================================================

WAGER_LOG_CHANNEL_ID = 1351221346192982046  # your mod review / receipts channel
MOD_PERMISSIONS_REQUIRE_ADMIN_OR_MANAGE_MESSAGES = True

# Positions
POS_ALL   = ["CF", "LW", "RW", "CM", "GK"]
POS_NO_GK = ["CF", "LW", "RW", "CM"]

MODE_SLOTS = {  # team size per side
    "1v1": 1,
    "2v2": 2,
    "3v3": 3,
    "5v5": 5,
}

# Friendly names
MODE_LIST = ["1v1", "2v2", "3v3", "5v5"]

# ====== INTEGRATIONS ==========================================================

# Adjust this import to your actual module path.
# Must provide:
#   get_member_value(user_id_str) -> int
#   set_member_value(user_id_str, new_value_int) -> None
import data_manager  # <-- change if needed

try:
    from phrases import MOMMY_ERROR_VARIANTS
except Exception:
    MOMMY_ERROR_VARIANTS = [
        "Something glitched—try again in a moment 💖",
        "System hiccup—try again soon 💕",
    ]

log = logging.getLogger(__name__)

# ====== MODELS ================================================================

@dataclass
class PlayerSlot:
    user_id: Optional[int] = None
    position: Optional[str] = None  # CF/LW/RW/CM/GK

@dataclass
class Lobby:
    creator_id: int
    guild_id: int
    channel_id: int
    amount_m: int
    mode: str
    created_ts: float = field(default_factory=lambda: time.time())
    team1: List[PlayerSlot] = field(default_factory=list)
    team2: List[PlayerSlot] = field(default_factory=list)
    message_id: Optional[int] = None   # lobby embed msg id
    escrowed: Dict[int, int] = field(default_factory=dict)  # user_id -> amount_m
    winner_team: Optional[int] = None
    screenshot_url: Optional[str] = None

    def team_size(self) -> int:
        return MODE_SLOTS[self.mode]

    def positions_allowed(self) -> List[str]:
        return POS_ALL if self.mode == "5v5" else POS_NO_GK

    def all_users(self) -> List[int]:
        out = []
        for s in self.team1 + self.team2:
            if s.user_id:
                out.append(s.user_id)
        return out

    def team_users(self, n: int) -> List[int]:
        slots = self.team1 if n == 1 else self.team2
        return [s.user_id for s in slots if s.user_id]

    def is_full(self) -> bool:
        return (len(self.team_users(1)) == self.team_size() and
                len(self.team_users(2)) == self.team_size())

    def has_user(self, uid: int) -> bool:
        return uid in self.all_users()

# ====== UTILITIES ==============================================================

def _embed(title: str, desc: str, color=discord.Color.blurple()) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())

def _user_value(uid: int) -> int:
    return data_manager.get_member_value(str(uid))

def _set_user_value(uid: int, new_val: int):
    data_manager.set_member_value(str(uid), max(0, int(new_val)))

def _ensure_member(uid: int):
    if hasattr(data_manager, "ensure_member"):
        try:
            data_manager.ensure_member(str(uid))
        except Exception:
            pass

async def _log(bot: commands.Bot, text: str):
    ch = bot.get_channel(WAGER_LOG_CHANNEL_ID)
    if ch:
        try:
            await ch.send(text)
            return
        except Exception:
            pass
    log.info(text)

def _pack_footer_ctx(amount: int, winner: int, team1_ids: List[int], team2_ids: List[int]) -> str:
    return f"amount={amount};winner={winner};team1={','.join(map(str,team1_ids))};team2={','.join(map(str,team2_ids))}"

def _unpack_footer_ctx(msg: discord.Message) -> Optional[Dict[str, Any]]:
    try:
        if not msg.embeds: return None
        f = msg.embeds[0].footer.text or ""
        parts = dict(p.split("=",1) for p in f.split(";") if "=" in p)
        for k in ("amount","winner","team1","team2"):
            if k not in parts: return None
        parts["amount"] = int(parts["amount"])
        parts["winner"] = int(parts["winner"])
        parts["team1"]  = [int(x) for x in parts["team1"].split(",") if x]
        parts["team2"]  = [int(x) for x in parts["team2"].split(",") if x]
        return parts
    except Exception:
        return None

def _first_url(text: str) -> Optional[str]:
    for t in text.split():
        if t.startswith("http://") or t.startswith("https://"):
            return t
    return None

# ====== VIEWS =================================================================

class ModeSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=m, description=f"{m} wager", value=m) for m in MODE_LIST]
        super().__init__(placeholder="Select match mode", min_values=1, max_values=1, options=options)
        self.value_selected: Optional[str] = None

    async def callback(self, interaction: discord.Interaction):
        self.value_selected = self.values[0]
        await interaction.response.send_message(f"Mode selected: **{self.value_selected}**", ephemeral=True)

class TeamSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Team 1", value="1"),
            discord.SelectOption(label="Team 2", value="2"),
        ]
        super().__init__(placeholder="Choose your team", min_values=1, max_values=1, options=options)
        self.team: Optional[int] = None

    async def callback(self, interaction: discord.Interaction):
        self.team = int(self.values[0])
        await interaction.response.send_message(f"You chose **Team {self.team}**", ephemeral=True)

class PositionSelect(discord.ui.Select):
    def __init__(self, allowed_positions: List[str]):
        options = [discord.SelectOption(label=p, value=p) for p in allowed_positions]
        super().__init__(placeholder="Choose your position", min_values=1, max_values=1, options=options)
        self.position: Optional[str] = None

    async def callback(self, interaction: discord.Interaction):
        self.position = self.values[0]
        await interaction.response.send_message(f"Position selected: **{self.position}**", ephemeral=True)

class LobbyJoinView(discord.ui.View):
    def __init__(self, cog: "Wagers", lobby_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.lobby_id = lobby_id

    @discord.ui.button(label="Join Team 1", style=discord.ButtonStyle.primary, custom_id="join_t1")
    async def join_t1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_join(interaction, self.lobby_id, team=1)

    @discord.ui.button(label="Join Team 2", style=discord.ButtonStyle.primary, custom_id="join_t2")
    async def join_t2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_join(interaction, self.lobby_id, team=2)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, custom_id="leave_lobby")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_leave(interaction, self.lobby_id)

    @discord.ui.button(label="Close & Submit Result", style=discord.ButtonStyle.success, custom_id="close_submit")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_close_submit(interaction, self.lobby_id)

class ModVerifyView(discord.ui.View):
    """Persistent approval buttons in the log channel."""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Approve Results", style=discord.ButtonStyle.success, custom_id="persistent_approve_match")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_mod_perms(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        data = _unpack_footer_ctx(interaction.message)
        if not data:
            await interaction.response.send_message("Missing context.", ephemeral=True)
            return
        await _payout_approve(self.bot, interaction, data)

    @discord.ui.button(label="Decline & Refund", style=discord.ButtonStyle.danger, custom_id="persistent_decline_match")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_mod_perms(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        data = _unpack_footer_ctx(interaction.message)
        if not data:
            await interaction.response.send_message("Missing context.", ephemeral=True)
            return
        await _refund_decline(self.bot, interaction, data)

def _has_mod_perms(user: discord.abc.User) -> bool:
    if not isinstance(user, discord.Member):
        return False
    if MOD_PERMISSIONS_REQUIRE_ADMIN_OR_MANAGE_MESSAGES:
        p = user.guild_permissions
        return bool(p.administrator or p.manage_messages)
    return True

# ====== COG ===================================================================

class Wagers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # lobby_id -> Lobby
        self.lobbies: Dict[str, Lobby] = {}
        # keep view alive
        try:
            bot.add_view(ModVerifyView(bot))
            log.info("Registered persistent ModVerifyView.")
        except Exception as e:
            log.debug(f"ModVerifyView register: {e}")

    def _new_lobby(self, ctx: commands.Context, amount_m: int, mode: str) -> str:
        lobby_id = f"{ctx.guild.id}-{ctx.author.id}-{int(time.time())}"
        L = Lobby(
            creator_id=ctx.author.id,
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            amount_m=amount_m,
            mode=mode,
            team1=[PlayerSlot() for _ in range(MODE_SLOTS[mode])],
            team2=[PlayerSlot() for _ in range(MODE_SLOTS[mode])],
        )
        # put creator on Team 1 temporarily (position picked during join flow)
        self.lobbies[lobby_id] = L
        return lobby_id

    def _lobby_embed(self, lobby: Lobby) -> discord.Embed:
        def fmt_team(slots: List[PlayerSlot]) -> str:
            out = []
            for s in slots:
                if s.user_id:
                    out.append(f"<@{s.user_id}> — {s.position or '—'}")
                else:
                    out.append("• [empty]")
            return "\n".join(out) or "—"

        e = discord.Embed(
            title=f"Wager Ad — {lobby.mode} — {lobby.amount_m}M per player",
            description=(
                "Click **Join Team 1** or **Join Team 2** to claim a slot.\n"
                "You’ll pick your **position** on join."
            ),
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        e.add_field(name="Team 1", value=fmt_team(lobby.team1), inline=True)
        e.add_field(name="Team 2", value=fmt_team(lobby.team2), inline=True)
        e.add_field(name="Creator", value=f"<@{lobby.creator_id}>", inline=False)
        return e

    async def _refresh_lobby_message(self, lobby_id: str):
        lobby = self.lobbies.get(lobby_id)
        if not lobby or not lobby.message_id: return
        ch = self.bot.get_channel(lobby.channel_id)
        if not ch: return
        try:
            msg = await ch.fetch_message(lobby.message_id)
            await msg.edit(embed=self._lobby_embed(lobby), view=LobbyJoinView(self, lobby_id))
        except Exception as e:
            log.debug(f"refresh lobby failed: {e}")

    async def _dm_or_channel(self, user: discord.User, channel: discord.abc.Messageable):
        try:
            dm = await user.create_dm()
            return dm
        except discord.Forbidden:
            return channel

    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="anteup")
    async def anteup(self, ctx: commands.Context, amount: Optional[int] = None):
        """Start a wager ad builder (DM-first)."""
        if amount is None or not isinstance(amount, int) or amount <= 0:
            await ctx.reply("Usage: `!anteup <amount>` — amount is a positive whole number in **millions**.")
            return

        # funds check for creator (must be able to escrow later)
        _ensure_member(ctx.author.id)
        creator_value = _user_value(ctx.author.id)
        if creator_value < amount:
            await ctx.reply(f"You need at least **{amount}M** to start this wager. Your value: **{creator_value}M**.")
            return

        # DM setup
        dest = await self._dm_or_channel(ctx.author, ctx.channel)
        mode_select = ModeSelect()
        team_select = TeamSelect()
        pos_select  = PositionSelect(POS_NO_GK)  # default; we’ll update after mode selection
        setup_view  = discord.ui.View(timeout=300)
        setup_view.add_item(mode_select)
        setup_view.add_item(team_select)
        setup_view.add_item(pos_select)

        msg = await dest.send(
            embed=_embed("Wager Setup",
                         f"Amount per player: **{amount}M**\n"
                         f"1) Select **mode**\n2) Select **team**\n3) Select **position**"),
            view=setup_view
        )

        # wait for choices (simple polling loop)
        end_ts = time.time() + 300
        chosen_mode: Optional[str] = None
        chosen_team: Optional[int]  = None
        chosen_pos: Optional[str]   = None

        while time.time() < end_ts:
            await asyncio.sleep(0.5)
            # update positions list if mode changed
            if mode_select.value_selected and mode_select.value_selected != chosen_mode:
                chosen_mode = mode_select.value_selected
                # update position options dynamically
                pos_allowed = POS_ALL if chosen_mode == "5v5" else POS_NO_GK
                new_pos = PositionSelect(pos_allowed)
                # replace the third child
                setup_view.children[2] = new_pos  # type: ignore
                await msg.edit(view=setup_view)
                pos_select = new_pos  # swap reference

            if team_select.team:
                chosen_team = team_select.team
            if pos_select.position:
                chosen_pos = pos_select.position
            if chosen_mode and chosen_team and chosen_pos:
                break

        if not (chosen_mode and chosen_team and chosen_pos):
            await dest.send("Setup timed out. Run `!anteup` again when ready.")
            return

        # Create lobby with initial self-join
        lobby_id = self._new_lobby(ctx, amount_m=amount, mode=chosen_mode)
        lobby = self.lobbies[lobby_id]

        # place creator in chosen team (if slot free) without escrow yet (escrow on “join” click too)
        slots = lobby.team1 if chosen_team == 1 else lobby.team2
        # find first empty slot
        placed = False
        for s in slots:
            if not s.user_id:
                s.user_id = ctx.author.id
                s.position = chosen_pos
                placed = True
                break
        if not placed:
            await dest.send("Chosen team is already full. You can still post the ad and let others fill.")
        else:
            # escrow creator immediately for clarity
            if await self._escrow_player(ctx.author.id, lobby.amount_m):
                lobby.escrowed[ctx.author.id] = lobby.amount_m
            else:
                await dest.send("Couldn’t escrow your amount. Check your value and try again.")
                del self.lobbies[lobby_id]
                return

        # Post lobby ad to the channel where command was run
        embed = self._lobby_embed(lobby)
        posted = await ctx.channel.send(embed=embed, view=LobbyJoinView(self, lobby_id))
        lobby.message_id = posted.id
        await _log(self.bot, f"[Lobby] {lobby.mode} {lobby.amount_m}M by <@{lobby.creator_id}> (msg {posted.id})")

    async def handle_join(self, interaction: discord.Interaction, lobby_id: str, team: int):
        lobby = self.lobbies.get(lobby_id)
        if not lobby:
            await interaction.response.send_message("This lobby no longer exists.", ephemeral=True)
            return
        if interaction.guild_id != lobby.guild_id:
            await interaction.response.send_message("Wrong server for this lobby.", ephemeral=True)
            return
        uid = interaction.user.id
        if lobby.has_user(uid):
            await interaction.response.send_message("You’re already in this lobby.", ephemeral=True)
            return

        # position selection (respect GK rule)
        allowed = lobby.positions_allowed()
        select = PositionSelect(allowed)
        ask = await interaction.response.send_message("Pick your **position**:", view=discord.ui.View().add_item(select), ephemeral=True)
        # wait until they pick (poll)
        chosen = None
        for _ in range(60):
            await asyncio.sleep(0.5)
            if select.position:
                chosen = select.position
                break
        if not chosen:
            try:
                await interaction.followup.send("Join cancelled (no position chosen).", ephemeral=True)
            except Exception:
                pass
            return

        # find empty slot in team
        slots = lobby.team1 if team == 1 else lobby.team2
        empty = None
        for s in slots:
            if not s.user_id:
                empty = s
                break
        if not empty:
            await interaction.followup.send(f"Team {team} is already full.", ephemeral=True)
            return

        # escrow (deduct stake)
        if not await self._escrow_player(uid, lobby.amount_m):
            await interaction.followup.send("Insufficient value to join.", ephemeral=True)
            return

        empty.user_id  = uid
        empty.position = chosen
        lobby.escrowed[uid] = lobby.amount_m
        await self._refresh_lobby_message(lobby_id)
        await interaction.followup.send(f"You joined **Team {team}** as **{chosen}**. Escrowed **{lobby.amount_m}M**.", ephemeral=True)

    async def handle_leave(self, interaction: discord.Interaction, lobby_id: str):
        lobby = self.lobbies.get(lobby_id)
        if not lobby:
            await interaction.response.send_message("This lobby no longer exists.", ephemeral=True)
            return
        uid = interaction.user.id
        # remove from slots
        removed = False
        for s in lobby.team1:
            if s.user_id == uid:
                s.user_id, s.position = None, None
                removed = True
                break
        if not removed:
            for s in lobby.team2:
                if s.user_id == uid:
                    s.user_id, s.position = None, None
                    removed = True
                    break
        if not removed:
            await interaction.response.send_message("You’re not in this lobby.", ephemeral=True)
            return

        # refund escrow (only if match not closed)
        if uid in lobby.escrowed:
            _set_user_value(uid, _user_value(uid) + lobby.escrowed[uid])
            del lobby.escrowed[uid]

        await self._refresh_lobby_message(lobby_id)
        await interaction.response.send_message("You left the lobby and your stake was refunded.", ephemeral=True)

    async def handle_close_submit(self, interaction: discord.Interaction, lobby_id: str):
        lobby = self.lobbies.get(lobby_id)
        if not lobby:
            await interaction.response.send_message("This lobby no longer exists.", ephemeral=True)
            return
        if interaction.user.id != lobby.creator_id:
            await interaction.response.send_message("Only the lobby creator can submit results.", ephemeral=True)
            return
        if not lobby.is_full():
            await interaction.response.send_message("Teams are not full yet.", ephemeral=True)
            return

        # ask for winner first (simple two buttons)
        v = discord.ui.View(timeout=120)
        chosen = {"winner": None}
        async def _set_w(team):
            async def fn(i: discord.Interaction):
                if i.user.id != lobby.creator_id:
                    await i.response.send_message("Only the creator can choose the winner.", ephemeral=True); return
                chosen["winner"] = team
                await i.response.send_message(f"Winner selected: **Team {team}**", ephemeral=True)
            return fn
        b1 = discord.ui.Button(label="Team 1 Wins", style=discord.ButtonStyle.success)
        b2 = discord.ui.Button(label="Team 2 Wins", style=discord.ButtonStyle.success)
        b1.callback = await _set_w(1)
        b2.callback = await _set_w(2)
        v.add_item(b1); v.add_item(b2)
        await interaction.response.send_message("Select **winner**:", view=v, ephemeral=True)

        # wait for selection
        for _ in range(120):
            await asyncio.sleep(0.5)
            if chosen["winner"]: break
        if not chosen["winner"]:
            await interaction.followup.send("Result submission cancelled (no winner selected).", ephemeral=True)
            return
        lobby.winner_team = chosen["winner"]

        # ask for screenshot URL (next message by creator in same channel)
        await interaction.followup.send("Paste a **screenshot URL** that shows the result clearly.", ephemeral=True)
        def check(m: discord.Message) -> bool:
            return m.author.id == lobby.creator_id and m.channel.id == interaction.channel_id
        try:
            m = await self.bot.wait_for("message", timeout=180, check=check)
            url = _first_url(m.content or "")
            if not url:
                await interaction.followup.send("No valid URL found. Submission cancelled.", ephemeral=True); return
            lobby.screenshot_url = url
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for screenshot URL.", ephemeral=True); return

        # Build verify embed to mod/log channel
        verify = discord.Embed(
            title="Wager Result Submitted",
            description="Approve to payout winners. Decline to refund all stakes.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        verify.add_field(name="Mode", value=lobby.mode, inline=True)
        verify.add_field(name="Amount (per player)", value=f"{lobby.amount_m}M", inline=True)
        verify.add_field(name="Winner", value=f"Team {lobby.winner_team}", inline=True)
        t1 = ", ".join(f"<@{uid}>" for uid in lobby.team_users(1))
        t2 = ", ".join(f"<@{uid}>" for uid in lobby.team_users(2))
        verify.add_field(name="Team 1", value=t1 or "—", inline=False)
        verify.add_field(name="Team 2", value=t2 or "—", inline=False)
        if lobby.screenshot_url:
            verify.set_image(url=lobby.screenshot_url)
        verify.set_footer(text=_pack_footer_ctx(
            amount=lobby.amount_m,
            winner=lobby.winner_team,
            team1_ids=lobby.team_users(1),
            team2_ids=lobby.team_users(2),
        ))

        log_ch = self.bot.get_channel(WAGER_LOG_CHANNEL_ID)
        if not log_ch:
            await interaction.followup.send("Mod log channel not found; ask admin to set it up.", ephemeral=True)
            return
        sent = await log_ch.send(embed=verify, view=ModVerifyView(self.bot))
        await interaction.followup.send(f"Submitted to <#{WAGER_LOG_CHANNEL_ID}> for moderator review.", ephemeral=True)

    async def _escrow_player(self, uid: int, amount_m: int) -> bool:
        try:
            _ensure_member(uid)
            cur = _user_value(uid)
            if cur < amount_m: return False
            _set_user_value(uid, cur - amount_m)
            return True
        except Exception as e:
            log.error(f"escrow fail for {uid}: {e}")
            return False

# ====== APPROVAL / DECLINE HANDLERS ===========================================

async def _payout_approve(bot: commands.Bot, interaction: discord.Interaction, data: Dict[str, Any]):
    amount = data["amount"]
    winner = data["winner"]
    t1, t2 = data["team1"], data["team2"]
    winners = t1 if winner == 1 else t2
    losers  = t2 if winner == 1 else t1

    # Winners gain +amount (losers already escrowed -amount on join)
    for uid in winners:
        try:
            _set_user_value(uid, _user_value(uid) + amount)
        except Exception as e:
            log.error(f"winner payout failed {uid}: {e}")

    # Update embed + disable buttons
    e = interaction.message.embeds[0]
    e.title = "✅ Match Results Approved"
    e.color = discord.Color.green()
    e.add_field(name="Approved by", value=interaction.user.display_name, inline=True)
    for c in interaction.message.components:
        for a in c.children:
            if isinstance(a, discord.ui.Button):
                a.disabled = True
    await interaction.response.edit_message(embed=e, view=ModVerifyView(bot))

    # DM receipts
    await _notify(bot, winners, f"🎉 You WON your wager! +{amount}M")
    await _notify(bot, losers,  f"💔 You LOST your wager. -{amount}M")

    await _log(bot, f"[APPROVED] +{amount}M to winners {winners}, losers {losers} keep -{amount}M escrow")

async def _refund_decline(bot: commands.Bot, interaction: discord.Interaction, data: Dict[str, Any]):
    amount = data["amount"]
    everyone = set(data["team1"] + data["team2"])
    # Refund all participants their escrow
    for uid in everyone:
        try:
            _set_user_value(uid, _user_value(uid) + amount)
        except Exception as e:
            log.error(f"refund failed {uid}: {e}")

    e = interaction.message.embeds[0]
    e.title = "❌ Match Results Declined — All Stakes Refunded"
    e.color = discord.Color.red()
    e.add_field(name="Declined by", value=interaction.user.display_name, inline=True)
    for c in interaction.message.components:
        for a in c.children:
            if isinstance(a, discord.ui.Button):
                a.disabled = True
    await interaction.response.edit_message(embed=e, view=ModVerifyView(bot))

    await _notify(bot, list(everyone), f"⚠️ Match declined by moderation — your stake **+{amount}M** was refunded.")
    await _log(bot, f"[DECLINED] Refunded {amount}M to each participant: {sorted(list(everyone))}")

async def _notify(bot: commands.Bot, uids: List[int], text: str):
    for uid in uids:
        try:
            u = await bot.fetch_user(uid)
            if not u: continue
            try:
                await u.send(text)
            except discord.Forbidden:
                pass
        except Exception:
            pass

# ====== SETUP =================================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Wagers(bot))
    # ensure persistent mod view is available after reload
    try:
        bot.add_view(ModVerifyView(bot))
    except Exception:
        pass
