from __future__ import annotations
import asyncio
import random
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Optional, Dict, List

import discord
from discord.ext import commands

# ✅ FIXED IMPORT — pulls the singleton instance created in ValueLedgerCog
from data_manager import data_manager

log = logging.getLogger(__name__)

# -------------------- CONFIG --------------------
TRYOUT_ROLE_ID       = 1350499731612110929
ANNOUNCE_CHANNEL_ID  = 1350172182038446184
RESULTS_CHANNEL_ID   = 1350182176007917739
EVALUATED_ROLE_ID    = 1350863646187716640
REMOVE_THIS_ROLE_ID  = 1350864967674630144

POSITIONS = ["CF", "LW", "RW", "CM", "GK"]
OUTFIELD  = ["CF", "LW", "RW", "CM"]

WEIGHTS = {
    "CF": {"shooting": 0.45, "dribbling": 0.30, "passing": 0.15, "defending": 0.10},
    "LW": {"passing": 0.40, "dribbling": 0.30, "shooting": 0.20, "defending": 0.10},
    "RW": {"passing": 0.40, "dribbling": 0.30, "shooting": 0.20, "defending": 0.10},
    "CM": {"defending": 0.40, "dribbling": 0.30, "passing": 0.20, "shooting": 0.10},
    "GK": {"goalkeeping": 0.60, "defending": 0.25, "passing": 0.15}
}
MIN_VALUE, MAX_VALUE = 15, 100

WELCOME_VARIANTS = [
    "🎴 **Welcome to Novera Tryouts!** Big day, {mention}—this could be your rise to #1!",
    "🏆 **Novera Tryouts** commencing—{mention}, your moment starts now.",
    "⚡ **Novera Tryouts**: {mention}, show us why you belong at the top."
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
# -----------------------------------------------


def has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)


@dataclass
class TryoutInterview:
    guild_id: int
    candidate_id: int
    evaluator_id: int
    position: Optional[str] = None
    answers: List[str] = field(default_factory=list)
    created_ts: float = field(default_factory=time.time)


class PositionSelect(discord.ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label=p, value=p) for p in POSITIONS]
        super().__init__(
            placeholder=random.choice(
                ["Choose your **position**:", "Select the role you’ll represent:", "Pick your position:"]
            ),
            min_values=1, max_values=1, options=opts
        )
        self.choice: Optional[str] = None

    async def callback(self, interaction: discord.Interaction):
        self.choice = self.values[0]
        await interaction.response.send_message(f"Position set: **{self.choice}**", ephemeral=True)


class RatingSelect(discord.ui.Select):
    def __init__(self, label: str, row: int = 0):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)]
        super().__init__(placeholder=f"{label} (1–10)", min_values=1, max_values=1, options=options, row=row)
        self.metric = label.lower()
        self.score: Optional[int] = None

    async def callback(self, interaction: discord.Interaction):
        self.score = int(self.values[0])
        await interaction.response.send_message(f"{self.metric.capitalize()} = **{self.score}**", ephemeral=True)


class EvaluatorView(discord.ui.View):
    def __init__(self, position: str, on_submit):
        super().__init__(timeout=600)
        self.on_submit = on_submit
        
        # selects
        self.sel_shoot = None
        self.sel_pass = None
        self.sel_def = None
        self.sel_drib = None
        self.sel_gk = None

        if position == "GK":
            self.sel_gk = RatingSelect("Goalkeeping", row=0)
            self.sel_def = RatingSelect("Defending", row=1)
            self.sel_pass = RatingSelect("Passing", row=2)
            self.add_item(self.sel_gk)
            self.add_item(self.sel_def)
            self.add_item(self.sel_pass)
            button_row = 3
        else:
            self.sel_shoot = RatingSelect("Shooting", row=0)
            self.sel_drib = RatingSelect("Dribbling", row=1)
            self.sel_pass = RatingSelect("Passing", row=2)
            self.sel_def = RatingSelect("Defending", row=3)
            self.add_item(self.sel_shoot)
            self.add_item(self.sel_drib)
            self.add_item(self.sel_pass)
            self.add_item(self.sel_def)
            button_row = 4

        button = discord.ui.Button(
            label="Submit Ratings",
            style=discord.ButtonStyle.success,
            row=button_row
        )
        button.callback = self._submit
        self.add_item(button)

    async def _submit(self, interaction: discord.Interaction):
        try:
            if self.sel_gk is not None:
                need = [self.sel_gk, self.sel_def, self.sel_pass]
            else:
                need = [self.sel_shoot, self.sel_drib, self.sel_pass, self.sel_def]

            missing = [s.metric for s in need if s.score is None]
            if missing:
                await interaction.response.send_message(f"Missing: {', '.join(missing)}", ephemeral=True)
                return

            payload = {s.metric: s.score for s in need}
            
            await interaction.response.send_message("Submitted. ✅", ephemeral=True)
            await self.on_submit(payload)

        except Exception as e:
            log.error(f"Error in _submit: {e}\n{traceback.format_exc()}")
            await interaction.response.send_message("Error processing submission.", ephemeral=True)


def mommy_embed(title: str, description: str, user: discord.Member) -> discord.Embed:
    emb = discord.Embed(title=title, description=description, color=discord.Color.purple())
    if user and user.avatar:
        emb.set_thumbnail(url=user.avatar.url)
    emb.set_footer(text="Novera • Mommy is watching ✨")
    return emb


class Tryouts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: Dict[str, TryoutInterview] = {}

    def _key(self, gid: int, uid: int) -> str:
        return f"{gid}-{uid}"

    # -------------------- COMMAND --------------------
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="tryout")
    async def tryout(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if not isinstance(ctx.author, discord.Member) or not has_role(ctx.author, TRYOUT_ROLE_ID):
            await ctx.reply("You don’t have permission to use this command.", mention_author=False)
            return
        if member is None or member.bot:
            await ctx.reply("Usage: `!tryout @user`", mention_author=False)
            return

        # remove pending role
        try:
            role_rm = ctx.guild.get_role(REMOVE_THIS_ROLE_ID)
            if role_rm and role_rm in member.roles:
                await member.remove_roles(role_rm)
        except:
            pass

        sess = TryoutInterview(ctx.guild.id, member.id, ctx.author.id)
        self.sessions[self._key(ctx.guild.id, member.id)] = sess

        # CANDIDATE DM
        try:
            dm = await member.create_dm()
            await dm.send(random.choice(WELCOME_VARIANTS).format(mention=member.mention))
            v = discord.ui.View(timeout=300)
            sel = PositionSelect()
            v.add_item(sel)
            pos_msg = await dm.send("—", view=v)
            for _ in range(600):
                await asyncio.sleep(0.5)
                if sel.choice:
                    sess.position = sel.choice
                    break
            try:
                await pos_msg.edit(view=None)
            except:
                pass

            if not sess.position:
                await dm.send("Tryout cancelled.")
                await ctx.reply("Candidate did not select a position.", mention_author=False)
                self.sessions.pop(self._key(ctx.guild.id, member.id), None)
                return

            await dm.send("Answer these questions:")

            for idx, q in enumerate(INTERVIEW_QS, start=1):
                await dm.send(f"**Q{idx}.** {q}")

                def check(m):
                    return m.author.id == member.id and m.channel.id == dm.id

                try:
                    msg = await self.bot.wait_for("message", timeout=240, check=check)
                    sess.answers.append(msg.content.strip())
                except asyncio.TimeoutError:
                    await dm.send("Timeout. Cancelled.")
                    await ctx.reply("Candidate timed out.", mention_author=False)
                    self.sessions.pop(self._key(ctx.guild.id, member.id), None)
                    return

            await dm.send(random.choice(THANKS_VARIANTS))

        except discord.Forbidden:
            await ctx.reply("Candidate has DMs disabled.", mention_author=False)
            self.sessions.pop(self._key(ctx.guild.id, member.id), None)
            return

        # EVALUATOR PANEL
        try:
            eval_dm = await ctx.author.create_dm()
        except discord.Forbidden:
            await ctx.reply("Evaluator DMs disabled.", mention_author=False)
            return

        try:
            emb = discord.Embed(
                title="🧪 Novera Tryout Evaluator Panel",
                description=f"Candidate: {member.mention}\nPosition: **{sess.position}**",
                color=discord.Color.blurple()
            )
            for i, q in enumerate(INTERVIEW_QS, start=1):
                ans = sess.answers[i-1]
                display = ans if len(ans) <= 512 else ans[:509] + "..."
                emb.add_field(name=f"Q{i}. {q}", value=display, inline=False)

            async def on_submit(scores):
                value_m = self._compute_value(sess.position, scores)

                uid = str(member.id)
                data_manager.ensure_member(uid)
                await data_manager.set_member_value(uid, value_m)

                role_ok = ctx.guild.get_role(EVALUATED_ROLE_ID)
                if role_ok:
                    mem = ctx.guild.get_member(member.id)
                    if mem and role_ok not in mem.roles:
                        await mem.add_roles(role_ok)

                results_ch = self.bot.get_channel(RESULTS_CHANNEL_ID)
                if results_ch:
                    bar = lambda v: "🟨"*v + "⬜"*(10-v)
                    emb2 = discord.Embed(
                        title="💋 Mommy’s verdict is in~",
                        description=f"{member.mention} completed their tryout!",
                        color=discord.Color.purple()
                    )
                    for metric, val in scores.items():
                        emb2.add_field(name=f"{metric.capitalize()} {val}/10", value=bar(val), inline=False)
                    emb2.add_field(name="💰 Final valuation", value=f"**¥{value_m:,}M**")
                    if member.avatar:
                        emb2.set_thumbnail(url=member.avatar.url)
                    await results_ch.send(embed=emb2)

                ann = self.bot.get_channel(ANNOUNCE_CHANNEL_ID)
                if ann:
                    msg = random.choice([
                        f"💕 Mommy’s proud~ {member.mention} is now worth **¥{value_m:,}M**!",
                        f"🌸 Congrats sweetie, your new price tag is **¥{value_m:,}M**!",
                        f"💖 You're valued at **¥{value_m:,}M**!",
                        f"🎀 Mommy stamped your forehead: **¥{value_m:,}M**!"
                    ])
                    await ann.send(msg)

                try:
                    dm = await member.create_dm()
                    await dm.send(f"Your Novera value has been set to **¥{value_m:,}M**!")
                except:
                    pass

                self.sessions.pop(self._key(ctx.guild.id, member.id), None)

            view = EvaluatorView(sess.position, on_submit)
            await eval_dm.send(embed=emb, view=view)

        except Exception as e:
            log.error(f"Evaluator panel error: {e}")
            await ctx.reply("Error opening evaluator panel.", mention_author=False)
            return

        await ctx.reply(f"Tryout started for {member.mention}. Evaluator panel sent.", mention_author=False)

    # ---------------- VALUE CALC ------------------
    def _compute_value(self, pos: str, s: Dict[str, int]) -> int:
        def g(k): return max(1, min(10, int(s.get(k, 5))))
        w = WEIGHTS.get(pos, WEIGHTS["CF"])

        if pos == "GK":
            raw = g("goalkeeping")*w["goalkeeping"] + g("defending")*w["defending"] + g("passing")*w["passing"]
        else:
            raw = (g("shooting")*w["shooting"] +
                   g("dribbling")*w["dribbling"] +
                   g("passing")*w["passing"] +
                   g("defending")*w["defending"])

        val = int(round(raw * 10))
        return max(MIN_VALUE, min(MAX_VALUE, val))


async def setup(bot):
    await bot.add_cog(Tryouts(bot))
