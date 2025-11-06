
# cogs/tryouts.py
# Tryout flow with position-aware weights and "dribbling" added; richer evaluator summary.

from __future__ import annotations
import asyncio, random, logging, time, traceback
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import discord
from discord.ext import commands

# ======================= CONFIG ==========================
TRYOUT_ROLE_ID       = 1350499731612110929  # who can run !tryout
ANNOUNCE_CHANNEL_ID  = 1350172182038446184  # where to post results
EVALUATED_ROLE_ID    = 1350863646187716640  # role to give after value is set

POSITIONS = ["CF", "LW", "RW", "CM", "GK"]

# Position-specific weights (user-specified)
WEIGHTS = {
    "CF": {"shooting": 0.40, "dribbling": 0.30, "passing": 0.20, "defending": 0.10},
    "LW": {"passing": 0.40, "dribbling": 0.30, "shooting": 0.20, "defending": 0.10},
    "RW": {"passing": 0.40, "dribbling": 0.30, "shooting": 0.20, "defending": 0.10},
    "CM": {"defending": 0.40, "dribbling": 0.30, "passing": 0.20, "shooting": 0.10},
    "GK": {"goalkeeping": 0.60, "defending": 0.25, "passing": 0.15},
}

MAX_VALUE_M = 100  # clamp ceil

WELCOME_VARIANTS = [
    "🎴 **Welcome to Novera Tryouts!** Big day, {mention}—this could be your rise to #1!",
    "🏆 **Novera Tryouts** commencing—{mention}, your moment starts now.",
    "⚡ **Novera Tryouts**: {mention}, show us why you belong at the top.",
]
POSITION_PROMPT_VARIANTS = [
    "Choose your **position**:", "Select the role you’ll represent:", "Pick your position:"
]
INTERVIEW_QS = [
    "What’s your **primary playstyle** (e.g., clinical finisher, creator, two-way workhorse)?",
    "What’s your **goal in Novera** this season?",
    "Describe a moment that shows your **composure under pressure**.",
    "What **strengths** do you bring to a team? (2–3 points)",
    "What’s your biggest **area to improve** and how will you work on it?",
    "How many **scrims** can you commit to weekly?",
]
THANKS_VARIANTS = [
    "Nice—interview recorded. We’ll follow up soon. 💼",
    "Got it. Your answers are locked. 📘",
    "Thanks! The evaluator will score you shortly. 📝",
]
EVAL_HEADER_VARIANTS = [
    "🧪 **Novera Tryout Evaluator Panel**",
    "📊 **Novera Scouting Suite**",
    "🎯 **Novera Evaluations**",
]
EVAL_FOOTER_VARIANTS = [
    "Select ratings (1–10), then submit.",
    "Score the categories below and hit Submit.",
    "Give your objective ratings and finalize.",
]
ANNOUNCE_VARIANTS = [
    "📣 **Novera Tryout Result**: {mention} is now valued at **{value}M**.",
    "🔥 **Evaluation Complete** — {mention} assigned a value of **{value}M**.",
    "🏁 **Tryout Finished**: {mention} set to **{value}M**.",
]

# ================= ECONOMY BACKEND =======================
from data_manager import DataManager  # use the class; instance resolved at runtime

def get_dm(bot) -> DataManager | None:
    dm = getattr(bot, "data_manager", None)
    if isinstance(dm, DataManager):
        return dm
    try:
        dm = DataManager("member_data.json")
        setattr(bot, "data_manager", dm)
        return dm
    except Exception as e:
        logging.error(f"[tryouts] failed to init DataManager: {e}")
        return None

async def add_evaluated_role(bot: commands.Bot, guild_id: int, user_id: int):
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    try:
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        role = guild.get_role(EVALUATED_ROLE_ID)
        if member and role and role not in member.roles:
            await member.add_roles(role, reason="Novera: value set / evaluated")
    except Exception:
        logging.exception("[tryouts] add role failed")

def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in getattr(member, "roles", []))

# ================== MODELS ===============================

from dataclasses import dataclass, field

@dataclass
class TryoutInterview:
    guild_id: int
    candidate_id: int
    evaluator_id: int
    position: Optional[str] = None
    answers: List[str] = field(default_factory=list)  # 6 answers
    created_ts: float = field(default_factory=lambda: time.time())

# ================== UI ELEMENTS ==========================

class PositionSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=p, value=p) for p in POSITIONS]
        super().__init__(
            placeholder=random.choice(POSITION_PROMPT_VARIANTS),
            min_values=1, max_values=1, options=options
        )
        self.choice: Optional[str] = None

    async def callback(self, interaction: discord.Interaction):
        self.choice = self.values[0]
        try:
            await interaction.response.send_message(f"Position set: **{self.choice}**", ephemeral=True)
        except discord.errors.InteractionResponded:
            pass

class RatingSelect(discord.ui.Select):
    def __init__(self, label: str):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)]
        super().__init__(placeholder=f"{label} (1–10)", min_values=1, max_values=1, options=options)
        self.metric = label.lower()
        self.score: Optional[int] = None

    async def callback(self, interaction: discord.Interaction):
        self.score = int(self.values[0])
        try:
            await interaction.response.send_message(f"{self.metric.capitalize()} = **{self.score}**", ephemeral=True)
        except discord.errors.InteractionResponded:
            pass

class EvaluatorView(discord.ui.View):
    def __init__(self, candidate_id: int, candidate_pos: str, callback_done):
        super().__init__(timeout=300)
        self.candidate_id = candidate_id
        self.candidate_pos = candidate_pos
        self.callback_done = callback_done

        # Core metrics
        self.sel_shoot = RatingSelect("Shooting")
        self.sel_pass  = RatingSelect("Passing")
        self.sel_def   = RatingSelect("Defending")
        self.add_item(self.sel_shoot)
        self.add_item(self.sel_pass)
        self.add_item(self.sel_def)

        # Dribbling for all outfield positions
        self.sel_drib: Optional[RatingSelect] = None
        if candidate_pos != "GK":
            self.sel_drib = RatingSelect("Dribbling")
            self.add_item(self.sel_drib)

        # GK-specific
        self.sel_gk: Optional[RatingSelect] = None
        if candidate_pos == "GK":
            self.sel_gk = RatingSelect("Goalkeeping")
            self.add_item(self.sel_gk)

    @discord.ui.button(label="Submit Ratings", style=discord.ButtonStyle.success)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer immediately to avoid "interaction failed"
        try:
            await interaction.response.defer(ephemeral=True, thinking=False)
        except discord.errors.InteractionResponded:
            pass

        # Validate selections
        missing = []
        for sel in [self.sel_shoot, self.sel_pass, self.sel_def]:
            if sel.score is None:
                missing.append(sel.metric)
        if self.sel_drib and self.sel_drib.score is None:
            missing.append(self.sel_drib.metric)
        if self.sel_gk and self.sel_gk.score is None:
            missing.append(self.sel_gk.metric)

        if missing:
            await interaction.followup.send(
                f"Missing: {', '.join(missing)}. Please select all scores.", ephemeral=True
            )
            return

        payload = {
            "shooting": self.sel_shoot.score,
            "passing":  self.sel_pass.score,
            "defending": self.sel_def.score,
            "dribbling": self.sel_drib.score if self.sel_drib else None,
            "goalkeeping": self.sel_gk.score if self.sel_gk else None,
        }
        await interaction.followup.send("Submitted. ✅", ephemeral=True)
        await self.callback_done(payload)

# ================== COG =================================

class Tryouts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[str, TryoutInterview] = {}  # key = f"{guild}-{candidate}"

    def _key(self, guild_id: int, user_id: int) -> str:
        return f"{guild_id}-{user_id}"

    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="tryout")
    async def tryout(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        Start a tryout for a user.
        Usage: !tryout @user
        """
        if not isinstance(ctx.author, discord.Member) or not has_role(ctx.author, TRYOUT_ROLE_ID):
            await ctx.reply("You don’t have permission to use this command.", mention_author=False)
            return

        if member is None or member.bot:
            await ctx.reply("Usage: `!tryout @user` (cannot try out bots).", mention_author=False)
            return

        sess = TryoutInterview(
            guild_id=ctx.guild.id,
            candidate_id=member.id,
            evaluator_id=ctx.author.id
        )
        self.sessions[self._key(ctx.guild.id, member.id)] = sess

        # ==== Candidate DM flow ====
        try:
            dm = await member.create_dm()
            await dm.send(random.choice(WELCOME_VARIANTS).format(mention=member.mention))

            # Position select
            pos_view = discord.ui.View(timeout=180)
            pos_sel = PositionSelect()
            pos_view.add_item(pos_sel)
            pos_msg = await dm.send("—", view=pos_view)

            # wait for position
            for _ in range(360):
                await asyncio.sleep(0.5)
                if pos_sel.choice:
                    sess.position = pos_sel.choice
                    break
            try: await pos_msg.edit(view=None)
            except: pass

            if not sess.position:
                await dm.send("Tryout cancelled (no position chosen).")
                await ctx.reply("Candidate did not select a position.", mention_author=False)
                del self.sessions[self._key(ctx.guild.id, member.id)]
                return

            # 6 interview questions
            await dm.send("Answer these quick questions (reply as messages):")
            for idx, q in enumerate(INTERVIEW_QS, start=1):
                await dm.send(f"**Q{idx}. {q}**")
                def check(m: discord.Message): return m.author.id == member.id and m.channel.id == dm.id
                try:
                    msg = await self.bot.wait_for("message", timeout=180, check=check)
                    sess.answers.append(msg.content.strip())
                except asyncio.TimeoutError:
                    await dm.send("Timeout waiting for your response. Tryout cancelled.")
                    await ctx.reply("Candidate timed out answering.", mention_author=False)
                    del self.sessions[self._key(ctx.guild.id, member.id)]
                    return

            await dm.send(random.choice(THANKS_VARIANTS))

        except discord.Forbidden:
            await ctx.reply("I couldn’t DM the candidate. Ask them to enable DMs and retry.", mention_author=False)
            del self.sessions[self._key(ctx.guild.id, member.id)]
            return
        except Exception as e:
            logging.error(f"Tryout DM error: {e}\n{traceback.format_exc()}")
            await ctx.reply("Something went wrong DMing the candidate. Check logs.", mention_author=False)
            del self.sessions[self._key(ctx.guild.id, member.id)]
            return

        # ==== Evaluator panel ====
        try:
            evaluator_dm = await ctx.author.create_dm()
            # summary embed (show question text AND answers)
            emb = discord.Embed(
                title=random.choice(EVAL_HEADER_VARIANTS),
                description=f"Candidate: **{member}** ({member.mention})\nPosition: **{sess.position}**",
                color=discord.Color.blurple()
            )
            for i, (q, ans) in enumerate(zip(INTERVIEW_QS, sess.answers), start=1):
                display = ans if len(ans) <= 512 else ans[:509] + "..."
                emb.add_field(name=f"Q{i}: {q}", value=display, inline=False)
            emb.set_footer(text=random.choice(EVAL_FOOTER_VARIANTS))

            async def done_cb(scores: Dict[str, int]):
                value_m = self._compute_value(sess.position, scores)
                dm_backend = get_dm(self.bot)
                if dm_backend is None:
                    await evaluator_dm.send("Backend error while saving value. Check logs.")
                    return

                uid = str(member.id)
                old_val = dm_backend.get_member_value(uid)
                dm_backend.set_member_value(uid, value_m)

                # Give evaluated role
                try:
                    await add_evaluated_role(self.bot, sess.guild_id, member.id)
                except Exception:
                    logging.exception("Role add failed after tryout set")

                # DM evaluator confirmation (pretty)
                delta = value_m - old_val
                sign = "+" if delta >= 0 else ""
                conf = discord.Embed(
                    title="✅ Evaluation Saved",
                    description=f"{member.mention}",
                    color=discord.Color.green()
                )
                conf.add_field(name="Previous", value=f"{old_val}M", inline=True)
                conf.add_field(name="New", value=f"{value_m}M", inline=True)
                conf.add_field(name="Change", value=f"{sign}{delta}M", inline=True)
                await evaluator_dm.send(embed=conf)

                # Announce in channel
                ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
                if ch:
                    try:
                        msg_txt = random.choice(ANNOUNCE_VARIANTS).format(mention=member.mention, value=value_m)
                        await ch.send(msg_txt)
                    except Exception:
                        logging.exception("Announce failed")

                # DM candidate, mommy vibe
                try:
                    cdm = await member.create_dm()
                    await cdm.send(
                        f"🏅 Mommy set your Novera value to **{value_m}M**. Keep working hard, sweetie!"
                    )
                except Exception:
                    logging.exception("Candidate DM failed")

                # cleanup
                self.sessions.pop(self._key(ctx.guild.id, member.id), None)

            view = EvaluatorView(candidate_id=member.id, candidate_pos=sess.position, callback_done=done_cb)
            await evaluator_dm.send(embed=emb, view=view)

        except Exception as e:
            logging.error(f"Evaluator DM error: {e}\n{traceback.format_exc()}")
            await ctx.reply("Couldn’t open the evaluator panel. Check logs.", mention_author=False)
            return

        await ctx.reply(f"Tryout started for {member.mention}. Check your DMs for the evaluator panel.", mention_author=False)

    # ---------- value math ----------
    def _compute_value(self, position: str, s: Dict[str, int]) -> int:
        """
        Convert 1–10 ratings to a final value (millions) using position-aware weights.
        Scaled to ~15..100M and clamped.
        """
        def g(name, default=5):
            v = s.get(name)
            if v is None:
                return default
            return max(1, min(10, int(v)))

        w = WEIGHTS.get(position, WEIGHTS["CF"])
        total = 0.0
        for k, weight in w.items():
            total += g(k) * weight

        value = int(round(total * 10))           # 1..10 -> 10..100
        value = max(15, min(value, MAX_VALUE_M))  # clamp 15..100
        return value


async def setup(bot: commands.Bot):
    await bot.add_cog(Tryouts(bot))
