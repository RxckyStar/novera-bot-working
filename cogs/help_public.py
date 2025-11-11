from __future__ import annotations
import discord
from discord.ext import commands
import random

# ------------- mommy-vibe text -------------
TITLE_VARIANTS = [
    "💕 Mommy’s Command List",
    "✨ Novera Help – Mommy’s Guide",
    "💋 Need help, sweetie?",
    "🎀 Mommy’s here to explain~"
]
DESC_VARIANTS = [
    "Pick a topic and Mommy will show you the commands~ 💖",
    "Lost? Let Mommy hold your hand~ 💕",
    "Choose what you wanna learn, darling~ ✨"
]
CATEGORY_VARIANTS = [
    "Let’s look at **{cat}** commands, cutie~",
    "Mommy gathered the **{cat}** commands for you~ 💕",
    "Here are the **{cat}** things you can do, sweetie~"
]

# ------------- real command list -------------
PUBLIC_CATEGORIES = {
    "General": ["help", "value", "activity", "rankings"],
    "Wagers":  ["anteup"],
    "Fun":     ["spank", "headpat", "spill", "shopping", "tipjar", "confess"]
}
HIDE_COMMANDS = {"eval", "getevaluated", "tryoutsresults", "tryoutresults", "match", "matchresult", "matchcancel"}

DESCRIPTIONS = {
    "help":     "Mommy shows you all the commands~ 💕",
    "value":    "Check your value or someone else’s 💰",
    "activity": "See how active you’ve been 📊",
    "rankings": "Top valued players leaderboard 👑",
    "anteup":   "Create or join a wager duel 💴",
    "spank":    "Playful spank ~ 👋",
    "headpat":  "Give someone a headpat 💖",
    "spill":    "Get the latest tea ☕",
    "shopping": "See Mommy’s purchases 🛍️",
    "tipjar":   "Check Mommy’s special fund 🪙",
    "confess":  "Make Mommy confess her secrets 💋"
}

# ------------- embed colours -------------
PINK  = 0xf47fff
NEON  = 0xff00ff

class HelpPublic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx, category: str | None = None):
        """Mommy’s help menu~"""
        if category:
            cat = category.capitalize()
            cmds = PUBLIC_CATEGORIES.get(cat)
            if not cmds:
                embed = discord.Embed(
                    title="😔 Mommy doesn’t know that category…",
                    description=f"Try one of these: {', '.join(PUBLIC_CATEGORIES)}",
                    color=PINK
                )
                return await ctx.send(embed=embed)

            title = f"💕 {cat} Commands"
            desc  = random.choice(CATEGORY_VARIANTS).format(cat=cat)
            embed = discord.Embed(title=title, description=desc, color=NEON)
            for c in cmds:
                if c in HIDE_COMMANDS:
                    continue
                embed.add_field(
                    name=f"**!{c}**  {DESCRIPTIONS.get(c, '—')}",
                    value="\u200b",
                    inline=False
                )
            embed.set_footer(text="Need more? Ask Mommy anytime~ 💖")
            return await ctx.send(embed=embed)

        # main menu
        title = random.choice(TITLE_VARIANTS)
        desc  = random.choice(DESC_VARIANTS)
        embed = discord.Embed(title=title, description=desc, color=PINK)
        for cat, cmds in PUBLIC_CATEGORIES.items():
            visible = [c for c in cmds if c not in HIDE_COMMANDS]
            if not visible:
                continue
            emoji = {"General": "📖", "Wagers": "💴", "Fun": "🎀"}.get(cat, "✨")
            embed.add_field(
                name=f"{emoji} **{cat}** ({len(visible)} commands)",
                value=", ".join(f"`{c}`" for c in visible),
                inline=False
            )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Choose a category below or type !help <category> ~ Mommy’s watching 💕")

        class CatView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                opts = [
                    discord.SelectOption(label=cat, emoji={"General": "📖", "Wagers": "💴", "Fun": "🎀"}.get(cat),
                                         description=f"Show {cat} commands")
                    for cat in PUBLIC_CATEGORIES
                ]
                select = discord.ui.Select(placeholder="Pick a topic…", options=opts)
                select.callback = self.on_select
                self.add_item(select)

            async def on_select(self, interaction: discord.Interaction):
                cat = interaction.data["values"][0]
                cmds = PUBLIC_CATEGORIES[cat]
                visible = [c for c in cmds if c not in HIDE_COMMANDS]
                e = discord.Embed(
                    title=f"💕 {cat} Commands",
                    description=random.choice(CATEGORY_VARIANTS).format(cat=cat),
                    color=NEON
                )
                for c in visible:
                    e.add_field(name=f"**!{c}**", value=DESCRIPTIONS.get(c, "—"), inline=False)
                e.set_footer(text="Mommy’s always here if you need more help~ 💖")
                await interaction.response.edit_message(embed=e, view=self)

        await ctx.send(embed=embed, view=CatView())

async def setup(bot):
    await bot.add_cog(HelpPublic(bot))
