# cogs/tryouts.py
# Novera Tryout + Value System
# - !tryout @user <amount>
# - Interview in DM (position + 5 Qs), evaluator gets a rating UI in DM
# - Rates: Shooting / Passing / Defending (+ Goalkeeping only if GK)
# - Calculates player's value (in millions) and sets it via data_manager
# - Announces in channel 1350172182038446184
# - Permissions: tryout role 1350499731612110929, setvalue role 1350547213717209160

from __future__ import annotations
import asyncio, random, logging, time, traceback
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import discord
from discord.ext import commands

# ====== CONFIG ======
TRYOUT_ROLE_ID = 1350499731612110929
SETVALUE_ROLE_ID = 1350547213717209160
ANNOUNCE_CHANNEL_ID = 1350172182038446184

POSITIONS = ["CF", "LW", "RW", "CM", "GK"]
OUTFIELD_POS = ["CF", "LW", "RW", "CM"]

# Value weights (tweakable)
WEIGHTS_OUTFIELD = {"shooting": 0.35, "passing": 0.35, "defending": 0.30}
WEIGHTS_GK      = {"goalkeeping": 0.60, "defending": 0.25, "passing": 0.15}

# Max output cap (millions) safeguard (optional)
MAX_VALUE_M = 200

# Message variants (fun)
WELCOME_VARIANTS = [
    "🎴 **Welcome to Novera Tryouts!** Big day, {mention}—this could be your rise to #1!",
    "🏆 **Novera Tryouts** commencing—{mention}, your moment starts now.",
    "⚡ **Novera Tryouts**: {mention}, show us why you belong at the top."
]
POSITION_PROMPT_VARIANTS = [
    "Choose your **position**:",
    "Select the role you’ll represent:",
    "Pick your position, champ:"
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
    "📣 **Novera Tryout Result**: {mention} is now valued at **{value}M**.",
    "🔥 **Evaluation Complete** — {mention} assigned a value of **{value}M**.",
    "🏁 **Tryout Finished**: {mention} set to **{value}M**."
]

# ====== ECONOMY BACKEND ======
# Adjust to your actual module path if needed
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

# ====== MODELS ======
@dataclass
class TryoutInterview:
    guild_id: int
    candidate_id: int
    evaluator_id: int
    amount_m: int
    position: Optional[str] = None
    answers: List[str] = field(default_factory=list)  # 6 answers
    created_ts: float = field(default_factory=lambda: time.time())

# ====== UI ELEMENTS ======

class PositionSelect(discord.ui.Select):
    def __init__(self, allowed: List[str]):
        options = [discord.SelectOption(label=p, value=p) for p in allowed]
        super().__init__(placeholder=random.choice(POSITION_PROMPT_VARIANTS), min_values=1, max_values=1, options=options)
        self.choice: Optional[str] = None

    async def callback(self, interaction: discord.Interaction):
        self.choice = self.values[0]
        await interaction.response.send_message(f"Position set: **{self.choice}**", ephemeral=True)

class RatingSelect(discord.ui.Select):
    def __init__(self, label: str):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)]
        super().__init__(placeholder=f"{label} (1–10)", min_values=1, max_values=1, options=options)
        self.metric = label.lower()  # "shooting", "passing", "defending", "goalkeeping"
        self.score: Optional[int] = None

    async def callback(self, interaction: discord.Interaction):
        self.score = int(self.values[0])
        await interaction.response.send_message(f"{self.metric.capitalize()} = **{self.score}**", ephemeral=True)

class EvaluatorView(discord.ui.View):
    def __init__(self, candidate_id: int, candidate_pos: str, callback_done):
        super().__init__(timeout=300)
        self.candidate_id = candidate_id
        self.candidate_pos = candidate_pos
        self.callback_done = callback_done
        # Always include these:
        self.sel_shoot = RatingSelect("Shooting")
        self.sel_pass  = RatingSelect("Passing")
        self.sel_def   = RatingSelect("Defending")
        self.add_item(self.sel_shoot)
        self.add_item(self.sel_pass)
        self.add_item(self.sel_def)
        # GK only if GK position
        self.sel_gk: Optional[RatingSelect] = None
        if candidate_pos == "GK":
            self.sel_gk = RatingSelect("Goalkeeping")
            self.add_item(self.sel_gk)

    @discord.ui.button(label="Submit Ratings", style=discord.ButtonStyle.success)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Validate
        miss = []
        for sel in [self.sel_shoot, self.sel_pass, self.sel_def]:
            if sel.score is None:
                miss.append(sel.metric)
        if self.sel_gk and self.sel_gk.score is None:
            miss.append(self.sel_gk.metric)
        if miss:
            await interaction.response.send_message(
                f"Missing: {', '.join(miss)}. Please select all scores.", ephemeral=True
            )
            return
        # Return ratings
        payload = {
            "shooting": self.sel_shoot.score,
            "passing":  self.sel_pass.score,
            "defending": self.sel_def.score,
            "goalkeeping": self.sel_gk.score if self.sel_gk else None
        }
        await interaction.response.send_message("Submitted. ✅", ephemeral=True)
        await self.callback_done(payload)

# ====== COG ======

class Tryouts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[str, TryoutInterview] = {}  # key = f"{guild}-{candidate}"

    def _key(self, guild_id: int, user_id: int) -> str:
        return f"{guild_id}-{user_id}"

    def _has_role(self, member: discord.Member, role_id: int) -> bool:
        return any(r.id == role_id for r in member.roles)

    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="tryout")
    async def tryout(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """
        Start a tryout for a user.
        Usage: !tryout @user <amount>
        """
        if not isinstance(ctx.author, discord.Member) or not self._has_role(ctx.author, TRYOUT_ROLE_ID):
            await ctx.reply("You don’t have permission to use this command.", mention_author=False)
            return

        if member is None or amount is None or amount <= 0:
            await ctx.reply("Usage: `!tryout @user <amount>` — amount is in **millions**.", mention_author=False)
            return

        if member.bot:
            await ctx.reply("You can’t try out a bot.", mention_author=False)
            return

        # Create session
        sess = TryoutInterview(
            guild_id=ctx.guild.id,
            candidate_id=member.id,
            evaluator_id=ctx.author.id,
            amount_m=int(amount)
        )
        self.sessions[self._key(ctx.guild.id, member.id)] = sess

        # DM candidate
        welcome = random.choice(WELCOME_VARIANTS).format(mention=member.mention)
        try:
            dm = await member.create_dm()
            await dm.send(welcome)

            # Position select
            pos_view = discord.ui.View(timeout=180)
            pos_sel = PositionSelect(POSITIONS)
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

        # DM evaluator the answers + rating UI
        try:
            evaluator_dm = await ctx.author.create_dm()
            # summary embed
            summ = discord.Embed(
                title=random.choice(EVAL_HEADER_VARIANTS),
                description=f"Candidate: **{member}** ({member.mention})\nPosition: **{sess.position}**",
                color=discord.Color.blurple()
            )
            for i, ans in enumerate(sess.answers, start=1):
                # keep fields concise
                display = ans if len(ans) <= 512 else ans[:509] + "..."
                summ.add_field(name=f"Q{i}", value=display, inline=False)
            summ.set_footer(text=random.choice(EVAL_FOOTER_VARIANTS))

            async def done_cb(scores: Dict[str, int]):
                # compute value
                value_m = self._compute_value(sess.position, scores)
                ensure_member(member.id)
                set_value(member.id, value_m)

                # DM evaluator confirmation
                conf = discord.Embed(
                    title="✅ Evaluation Saved",
                    description=f"Set **{member}** to **{value_m}M**.",
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
                        pass

                # DM candidate
                try:
                    cdm = await member.create_dm()
                    await cdm.send(f"🏅 Your Novera value has been set to **{value_m}M**. Congratulations!")
                except Exception:
                    pass

                # clean up
                self.sessions.pop(self._key(ctx.guild.id, member.id), None)

            # build evaluator view
            ev_view = EvaluatorView(candidate_id=member.id, candidate_pos=sess.position, callback_done=done_cb)
            await evaluator_dm.send(embed=summ, view=ev_view)

        except Exception as e:
            logging.error(f"Evaluator DM error: {e}\n{traceback.format_exc()}")
            await ctx.reply("Couldn’t open the evaluator panel. Check logs.", mention_author=False)
            return

        await ctx.reply(f"Tryout started for {member.mention}. Check your DMs for the evaluator panel.", mention_author=False)

    def _compute_value(self, position: str, scores: Dict[str, int]) -> int:
        """
        Convert 1–10 ratings to a final 'millions' value.
        Simple weighted sum -> scaled to [~15M .. ~100M] range, clamped by MAX_VALUE_M.
        """
        def clamp01(x): return max(1, min(10, int(x)))
        if position == "GK":
            w = WEIGHTS_GK
            gk = clamp01(scores.get("goalkeeping", 5))
            df = clamp01(scores.get("defending", 5))
            ps = clamp01(scores.get("passing", 5))
            raw = gk*w["goalkeeping"] + df*w["defending"] + ps*w["passing"]  # max 10
        else:
            w = WEIGHTS_OUTFIELD
            sh = clamp01(scores.get("shooting", 5))
            ps = clamp01(scores.get("passing", 5))
            df = clamp01(scores.get("defending", 5))
            raw = sh*w["shooting"] + ps*w["passing"] + df*w["defending"]     # max 10

        # scale: raw(1..10) → value ~ (15..100)M
        value = int(round(raw * 10))
        value = max(15, min(value, MAX_VALUE_M))
        return value

    # ====== setvalue command ======
    @commands.guild_only()
    @commands.command(name="setvalue")
    async def setvalue(self, ctx: commands.Context, member: Optional[discord.Member] = None, amount: Optional[int] = None):
        """
        Manually set a user's value (in millions).
        Usage: !setvalue @user <amount>
        """
        if not isinstance(ctx.author, discord.Member) or not self._has_role(ctx.author, SETVALUE_ROLE_ID):
            await ctx.reply("You don’t have permission to use this command.", mention_author=False)
            return

        if member is None or amount is None or amount < 0:
            await ctx.reply("Usage: `!setvalue @user <amount>` — amount is in **millions**.", mention_author=False)
            return

        try:
            ensure_member(member.id)
            set_value(member.id, int(amount))
            await ctx.reply(f"Set {member.mention} to **{int(amount)}M**.", mention_author=False)
            # announce too (optional)
            ch = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
            if ch:
                try:
                    await ch.send(f"🛠️ Admin updated {member.mention} to **{int(amount)}M**.")
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"setvalue error: {e}\n{traceback.format_exc()}")
            await ctx.reply("Failed to set value. Check logs.", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tryouts(bot))
