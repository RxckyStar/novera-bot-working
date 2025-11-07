# cogs/tryouts.py
# Novera Tryout System
# - Command: !tryout @user
# - DM interview for the candidate (position + 6 questions)
# - DM evaluator panel with ratings (1–10)
# - Computes a value (15–¥100 million 💴), saves it via data_manager,
#   gives the Evaluated role, announces in a channel, and DMs the player.

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
OUTFIELD_POS = ["CF", "LW", "RW", "CM"]

# (kept; not used for final weights but harmless)
WEIGHTS_OUTFIELD = {"shooting": 0.35, "passing": 0.35, "defending": 0.30}
WEIGHTS_GK      = {"goalkeeping": 0.60, "defending": 0.25, "passing": 0.15}

MAX_VALUE_M = 100  # hard cap (min is enforced at 15 below)

WELCOME_VARIANTS = [
    "🎴 **Welcome to Novera Tryouts!** Big day, {mention}—this could be your rise to #1!",
    "🏆 **Novera Tryouts** commencing—{mention}, your moment starts now.",
    "⚡ **Novera Tryouts**: {mention}, show us why you belong at the top."
]
POSITION_PROMPT_VARIANTS = [
    "Choose your **position**:",
    "Select the role you’ll represent:",
    "Pick your position:"
]
INTERVIEW_QS = [
    "What’s your **primary playstyle** (e.g., clinical finisher, creator, two-way workhorse)?",
    "What’s your **goal in Novera** this season?",
    "Describe a moment that shows your **composure under pressure**.",
    "What **strengths** do you bring to a team? (2–3 points)",
    "What’s your biggest **area to improve** and how will you work on it?",
    "How many **scrims** can you commit to weekly?"
]
THANKS_VARIANTS = [
    "Nice—interview recorded. We’ll follow up soon. 💼",
    "Got it. Your answers are locked. 📘",
    "Thanks! The evaluator will score you shortly. 📝"
]
EVAL_HEADER_VARIANTS = [
    "🧪 **Novera Tryout Evaluator Panel**",
    "📊 **Novera Scouting Suite**",
    "🎯 **Novera Evaluations**"
]
EVAL_FOOTER_VARIANTS = [
    "Select ratings (1–10), then submit.",
    "Score the categories below and hit Submit.",
    "Give your objective ratings and finalize."
]
ANNOUNCE_VARIANTS = [
    "📣 **Novera Tryout Result**: {mention} is now valued at **¥{value} million 💴 million 💴**.",
    "🔥 **Evaluation Complete** — {mention} assigned a value of **¥¥{value} million 💴**.",
    "🏁 **Tryout Finished**: {mention} set to **¥{value} million 💴**."
]

# ================= ECONOMY BACKEND =======================
import data_manager

def get_value(uid: int) -> int:
    return int(data_manager.get_member_value(str(uid)))

def set_value(uid: int, new_m: int):
    data_manager.set_member_value(str(uid), max(0, int(new_m)))

def ensure_member(uid: int):
    if hasattr(data_manager, "ensure_member"):
        try:
            data_manager.ensure_member(str(uid))
        except Exception:
            pass

# ================== HELPERS/UTILS ========================

async def add_evaluated_role(bot: commands.Bot, guild_id: int, user_id: int):
    """Give the evaluated role (ignore errors if perms/position block it)."""
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    try:
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        role = guild.get_role(EVALUATED_ROLE_ID)
        if member and role and role not in member.roles:
            await member.add_roles(role, reason="Novera: value set / evaluated")
    except Exception:
        logging.exception("Failed to add evaluated role")

def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)

def _in_dm(interaction: discord.Interaction) -> bool:
    return isinstance(interaction.channel, discord.DMChannel) or interaction.guild is None

# ================== MODELS ===============================

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
    def __init__(self, allowed: List[str]):
        options = [discord.SelectOption(label=p, value=p) for p in allowed]
        super().__init__(
            placeholder=random.choice(POSITION_PROMPT_VARIANTS),
            min_values=1, max_values=1, options=options
        )
        self.choice: Optional[str] = None

    async def callback(self, interaction: discord.Interaction):
        # Ephemeral is NOT supported in DMs -> use defer + followup
        if not interaction.response.is_done():
            await interaction.response.defer()
        self.choice = self.values[0]
        try:
            await interaction.followup.send(f"Position set: **{self.choice}**")
        except Exception:
            pass

class RatingSelect(discord.ui.Select):
    def __init__(self, label: str):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)]
        super().__init__(placeholder=f"{label} (1–10)", min_values=1, max_values=1, options=options)
        self.metric = label.lower()
        self.score: Optional[int] = None

    async def callback(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        self.score = int(self.values[0])
        try:
            await interaction.followup.send(f"{self.metric.capitalize()} = **{self.score}**")
        except Exception:
            pass

class EvaluatorView(discord.ui.View):
    def __init__(self, candidate_id: int, candidate_pos: str, callback_done):
        super().__init__(timeout=900)  # 15 minutes
        self.candidate_id = candidate_id
        self.candidate_pos = candidate_pos
        self.callback_done = callback_done

        # Always include these three
        self.sel_shoot = RatingSelect("Shooting")
        self.sel_pass  = RatingSelect("Passing")
        self.sel_def   = RatingSelect("Defending")
        self.add_item(self.sel_shoot)
        self.add_item(self.sel_pass)
        self.add_item(self.sel_def)

        # NEW: Dribbling for all outfield
        self.sel_drib: Optional[RatingSelect] = None
        self.sel_gk:   Optional[RatingSelect] = None

        if candidate_pos == "GK":
            self.sel_gk = RatingSelect("Goalkeeping")
            self.add_item(self.sel_gk)
        else:
            self.sel_drib = RatingSelect("Dribbling")
            self.add_item(self.sel_drib)

    @discord.ui.button(label="Submit Ratings", style=discord.ButtonStyle.success)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()

        missing = []
        for sel in [self.sel_shoot, self.sel_pass, self.sel_def]:
            if sel.score is None:
                missing.append(sel.metric)
        if self.candidate_pos == "GK":
            if not self.sel_gk or self.sel_gk.score is None:
                missing.append("goalkeeping")
        else:
            if not self.sel_drib or self.sel_drib.score is None:
                missing.append("dribbling")

        if missing:
            try:
                await interaction.followup.send(
                    f"Missing: {', '.join(missing)}. Please select all scores."
                )
            except Exception:
                pass
            return

        payload = {
            "shooting": self.sel_shoot.score,
            "passing":  self.sel_pass.score,
            "defending": self.sel_def.score,
            "dribbling": self.sel_drib.score if self.sel_drib else None,
            "goalkeeping": self.sel_gk.score if self.sel_gk else None
        }
        try:
            await interaction.followup.send("Submitted. ✅")
        except Exception:
            pass
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
            pos_sel = PositionSelect(POSITIONS)
            pos_view.add_item(pos_sel)
            pos_msg = await dm.send("—", view=pos_view)

            # also nudge public channel
            try:
                await ctx.send(
                    f"{member.mention} check your **DMs** to start the tryout "
                    f"(enable *Privacy > Allow DMs from server members* if you don’t see it).",
                    delete_after=25
                )
            except Exception:
                pass

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
                await dm.send(f"**Q{idx}.** {q}")
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
            # summary embed (now shows question text + answer)
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
                ensure_member(member.id)
                set_value(member.id, value_m)

                # Give evaluated role (ignore errors)
                try:
                    await add_evaluated_role(self.bot, sess.guild_id, member.id)
                except Exception:
                    logging.exception("Role add failed after tryout set")

                # DM evaluator confirmation
                conf = discord.Embed(
                    title="✅ Evaluation Saved",
                    description=f"Set **{member}** to **¥{value_m} million 💴**.",
                    color=discord.Color.green()
                )
                await evaluator_dm.send(embed=conf)

                # Announce in channel
                ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
                if ch:
                    try:
                        msg_txt = random.choice(ANNOUNCE_VARIANTS).format(mention=member.mention, value=value_m)
                        await ch.send(msg_txt)
                    except Exception:
                        logging.exception("Announce failed")

                # DM candidate
                try:
                    cdm = await member.create_dm()
                    await cdm.send(f"🏅 Your Novera value has been set to **¥¥{value_m} million 💴**. Congratulations!")
                except Exception:
                    logging.exception("Candidate DM failed")

                # cleanup
                self.sessions.pop(self._key(sess.guild_id, member.id), None)

            view = EvaluatorView(candidate_id=member.id, candidate_pos=sess.position, callback_done=done_cb)
            await evaluator_dm.send(embed=emb, view=view)

        except Exception as e:
            logging.error(f"Evaluator DM error: {e}\n{traceback.format_exc()}")
            await ctx.reply("Couldn’t open the evaluator panel. Check logs.", mention_author=False)
            return

        await ctx.reply(f"Tryout started for {member.mention}. Check your DMs for the evaluator panel.", mention_author=False)

    # ---------- value math ----------
    def _compute_value(self, position: str, scores: Dict[str, int]) -> int:
        """
        Convert 1–10 ratings to a final value (millions).
        NEW weights by role with Dribbling:
          CF  : Shooting>Dribbling>Passing>Defending
          LW/RW: Passing>Dribbling>Shooting>Defending
          CM  : Defending>Dribbling>Passing>Shooting
          GK  : Goalkeeping only (others ignored)
        Scaled to ~15..¥100 million 💴 and clamped.
        """
        def clamp10(x): return max(1, min(10, int(x)))

        if position == "GK":
            gk = clamp10(scores.get("goalkeeping", 5))
            df = clamp10(scores.get("defending",   5))
            ps = clamp10(scores.get("passing",     5))
            raw = gk*0.60 + df*0.25 + ps*0.15
        elif position == "CF":
            sh = clamp10(scores.get("shooting",   5))
            dr = clamp10(scores.get("dribbling",  5))
            ps = clamp10(scores.get("passing",    5))
            df = clamp10(scores.get("defending",  5))
            raw = sh*0.40 + dr*0.30 + ps*0.20 + df*0.10
        elif position in ("LW", "RW"):
            ps = clamp10(scores.get("passing",    5))
            dr = clamp10(scores.get("dribbling",  5))
            sh = clamp10(scores.get("shooting",   5))
            df = clamp10(scores.get("defending",  5))
            raw = ps*0.35 + dr*0.30 + sh*0.20 + df*0.15
        elif position == "CM":
            df = clamp10(scores.get("defending",  5))
            dr = clamp10(scores.get("dribbling",  5))
            ps = clamp10(scores.get("passing",    5))
            sh = clamp10(scores.get("shooting",   5))
            raw = df*0.35 + dr*0.30 + ps*0.20 + sh*0.15
        else:
            # Fallback (shouldn't happen)
            sh = clamp10(scores.get("shooting",   5))
            ps = clamp10(scores.get("passing",    5))
            dr = clamp10(scores.get("dribbling",  5))
            df = clamp10(scores.get("defending",  5))
            raw = sh*0.30 + ps*0.30 + dr*0.20 + df*0.20

        value = int(round(raw * 10))           # 1..10 -> 10..100
        value = max(15, min(value, MAX_VALUE_M))  # clamp 15..100
        return value


async def setup(bot: commands.Bot):
    await bot.add_cog(Tryouts(bot))
