
import discord
from discord.ext import commands

PUBLIC_CATEGORIES = {
    "General": ["help", "value", "activity", "rankings"],
    "Match": ["match", "matchresult", "matchcancel", "anteup"],
    "Fun": ["spank", "headpat", "spill", "shopping", "tipjar", "confess"]
}

HIDE_COMMANDS = {"eval", "getevaluated", "tryoutsresults", "tryoutresults"}

DESCRIPTIONS = {
    "help": "Show this help menu",
    "value": "Check your value or someone else's",
    "activity": "See your activity",
    "rankings": "Top players by value",
    "match": "Create a new match",
    "matchresult": "Report match results",
    "matchcancel": "Cancel a match you created",
    "anteup": "Join an existing match",
    "spank": "Playful spank",
    "headpat": "Give a headpat",
    "spill": "Get the tea",
    "shopping": "See Mommy's purchases",
    "tipjar": "Check Mommy's special fund",
    "confess": "Make Mommy confess"
}

class HelpPublic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx, category: str | None = None):
        # Build a fancy embed with dropdown
        if category:
            cat = category.capitalize()
            cmds = PUBLIC_CATEGORIES.get(cat)
            if not cmds:
                return await ctx.send(f"Unknown category `{category}`.")
            embed = discord.Embed(
                title=f"📖 Novera Help — {cat}",
                color=discord.Color.blurple(),
                description="Click the buttons below or type the commands."
            )
            for c in cmds:
                if c in HIDE_COMMANDS:
                    continue
                desc = DESCRIPTIONS.get(c, "—")
                embed.add_field(name=f"`!{c}`", value=desc, inline=False)
            return await ctx.send(embed=embed)

        # main menu
        embed = discord.Embed(
            title="📖 Novera Help",
            description="Pick a category to see commands.\nYou can also type `!help <category>`.",
            color=discord.Color.blurple()
        )
        for cat, cmds in PUBLIC_CATEGORIES.items():
            count = len([c for c in cmds if c not in HIDE_COMMANDS])
            embed.add_field(name=f"**{cat}**", value=f"{count} commands", inline=True)

        class CatView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                options=[]
                for cat in PUBLIC_CATEGORIES:
                    options.append(discord.SelectOption(label=cat, description=f"Show {cat} commands"))
                self.select = discord.ui.Select(placeholder="Choose category…", options=options)
                self.select.callback = self.on_select
                self.add_item(self.select)
            async def on_select(self, interaction: discord.Interaction):
                cat = self.select.values[0]
                cmds = PUBLIC_CATEGORIES[cat]
                e = discord.Embed(
                    title=f"📖 Novera Help — {cat}",
                    color=discord.Color.blurple()
                )
                for c in cmds:
                    if c in HIDE_COMMANDS:
                        continue
                    e.add_field(name=f"`!{c}`", value=DESCRIPTIONS.get(c, "—"), inline=False)
                await interaction.response.edit_message(embed=e, view=self)

        await ctx.send(embed=embed, view=CatView())

async def setup(bot):
    await bot.add_cog(HelpPublic(bot))
