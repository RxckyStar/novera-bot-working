"""
Interactive Moderation Tooltip Wizard
Provides interactive tooltips and guidance for users about moderation actions
"""

import discord
import asyncio
import logging
import random
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moderation_tooltip")

# Moderation rule explanations grouped by category
RULE_EXPLANATIONS = {
    "profanity": {
        "title": "Language Guidelines",
        "description": "Our server maintains a respectful environment where everyone can feel comfortable. "
                     "We moderate certain language to ensure a positive experience for all members.",
        "examples": [
            "Using explicit language",
            "Name-calling or insulting others",
            "Using slurs or derogatory terms"
        ],
        "tips": [
            "Express yourself without explicit language",
            "Address disagreements respectfully",
            "Consider how your words might affect others"
        ]
    },
    "spam": {
        "title": "Spam Prevention",
        "description": "Spam disrupts conversations and makes it difficult for others to engage meaningfully. "
                     "We moderate excessive message posting to maintain quality discussions.",
        "examples": [
            "Sending many messages in quick succession",
            "Repeatedly posting the same content",
            "Excessive use of caps, emojis, or formatting"
        ],
        "tips": [
            "Take your time between messages",
            "Express your thoughts in a single, well-composed message",
            "Use formatting thoughtfully to enhance, not overwhelm, your message"
        ]
    },
    "harassment": {
        "title": "Respectful Interaction",
        "description": "Everyone deserves to feel safe and respected in our community. "
                     "Harassment of any kind is not tolerated.",
        "examples": [
            "Persistent unwanted targeting of another user",
            "Making threatening or intimidating comments",
            "Following a user across channels to continue arguments"
        ],
        "tips": [
            "Disengage from heated conversations",
            "Focus on ideas rather than individuals when disagreeing",
            "Report serious concerns to moderators rather than escalating"
        ]
    },
    "nsfw": {
        "title": "Age-Appropriate Content",
        "description": "Our server welcomes members of various ages. We keep content appropriate "
                     "for everyone by moderating explicit material.",
        "examples": [
            "Sharing explicit images or videos",
            "Discussing graphic sexual content",
            "Posting suggestive or provocative material"
        ],
        "tips": [
            "Keep all content PG-13 or cleaner",
            "Consider whether content would be appropriate in a school setting",
            "When in doubt, don't post it"
        ]
    },
    "timeout": {
        "title": "Understanding Timeouts",
        "description": "Timeouts are a moderation tool used to give members a chance to cool down "
                     "after rule violations. During a timeout, you can't send messages or react to posts.",
        "examples": [
            "First violations typically result in short timeouts",
            "Repeated violations lead to longer timeouts",
            "Serious violations may result in immediate extended timeouts"
        ],
        "tips": [
            "Use the timeout period to review server rules",
            "When your timeout ends, you can participate normally again",
            "Multiple timeouts may lead to more serious consequences"
        ]
    }
}

class ModTooltipButton(discord.ui.Button):
    """Button for accessing moderation tooltips"""
    
    def __init__(self, category: str, emoji: str, row: int = 0):
        """
        Initialize a moderation tooltip button
        
        Args:
            category: The moderation category this button represents
            emoji: The emoji to display on the button
            row: The row to place this button in the view
        """
        self.category = category
        title = RULE_EXPLANATIONS[category]["title"]
        
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=title,
            emoji=emoji,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle button click to show the tooltip"""
        # Create embed with rule information
        rule_info = RULE_EXPLANATIONS[self.category]
        
        embed = discord.Embed(
            title=f"📝 {rule_info['title']}",
            description=rule_info["description"],
            color=discord.Color.blue()
        )
        
        # Add examples of violations
        examples = "\n".join([f"• {example}" for example in rule_info["examples"]])
        embed.add_field(
            name="📋 Examples",
            value=examples,
            inline=False
        )
        
        # Add helpful tips
        tips = "\n".join([f"• {tip}" for tip in rule_info["tips"]])
        embed.add_field(
            name="💡 Helpful Tips",
            value=tips,
            inline=False
        )
        
        embed.set_footer(text="Click the buttons below to learn about other moderation topics")
        
        # Show the tooltip as an ephemeral message to avoid cluttering the channel
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ModTooltipView(discord.ui.View):
    """Interactive view for moderation tooltips"""
    
    def __init__(self, timeout: int = 300):
        """
        Initialize the moderation tooltip view
        
        Args:
            timeout: How long the view should be active (in seconds)
        """
        super().__init__(timeout=timeout)
        
        # Row 1: Language and Spam
        self.add_item(ModTooltipButton("profanity", "🔤", row=0))
        self.add_item(ModTooltipButton("spam", "🔁", row=0))
        
        # Row 2: Harassment and NSFW
        self.add_item(ModTooltipButton("harassment", "🛡️", row=1))
        self.add_item(ModTooltipButton("nsfw", "🔞", row=1))
        
        # Row 3: Timeout info
        self.add_item(ModTooltipButton("timeout", "⏱️", row=2))
    
    async def on_timeout(self):
        """Handle the view timing out"""
        # Disable all buttons when the view times out
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


async def send_moderation_tooltip(ctx_or_channel, user_id: Optional[int] = None, ephemeral: bool = False) -> None:
    """
    Send the interactive moderation tooltip wizard
    
    Args:
        ctx_or_channel: Either a command context or a discord channel
        user_id: Optional user ID to restrict interaction to a specific user
        ephemeral: Whether to send as an ephemeral message (only works with slash commands)
    """
    # Create the embed for the tooltip
    embed = discord.Embed(
        title="📚 Moderation Guidelines",
        description=(
            "Welcome to our moderation guidelines wizard! "
            "Click the buttons below to learn more about our server's rules and moderation practices."
        ),
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="💬 Interactive Guide",
        value="Each button will show you detailed information about a specific aspect of our moderation system.",
        inline=False
    )
    
    embed.set_footer(text="These tooltips help everyone understand our community standards")
    
    # Create the view with tooltip buttons
    view = ModTooltipView()
    
    # Send the message with the view
    if hasattr(ctx_or_channel, 'send'):
        # It's a channel or context
        await ctx_or_channel.send(embed=embed, view=view, ephemeral=ephemeral)
    else:
        # It's probably a Discord Interaction
        await ctx_or_channel.response.send_message(embed=embed, view=view, ephemeral=ephemeral)


class UserGuideView(discord.ui.View):
    """Interactive view for new user guides with moderation info"""
    
    def __init__(self, user_id: int):
        """
        Initialize the user guide view
        
        Args:
            user_id: The user ID this guide is for
        """
        super().__init__(timeout=1800)  # 30 minute timeout
        self.user_id = user_id
    
    @discord.ui.button(label="Moderation Guidelines", emoji="📋", style=discord.ButtonStyle.primary)
    async def moderation_guidelines_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show the moderation guidelines tooltip"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This guide is not for you!", ephemeral=True)
            return
        
        # Send the moderation tooltip
        await send_moderation_tooltip(interaction)
    
    @discord.ui.button(label="Server Rules", emoji="📜", style=discord.ButtonStyle.success)
    async def server_rules_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show server rules"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This guide is not for you!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📜 Server Rules",
            description="Here are the important rules to follow in our server:",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Core Rules",
            value=(
                "1. Be respectful to all members\n"
                "2. No spamming or excessive mentions\n"
                "3. Keep content appropriate\n"
                "4. Follow Discord's Terms of Service\n"
                "5. Listen to staff members"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Timeout FAQ", emoji="⏱️", style=discord.ButtonStyle.secondary)
    async def timeout_faq_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show timeout FAQ"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This guide is not for you!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⏱️ Timeout FAQ",
            description="Frequently asked questions about timeouts:",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="What is a timeout?",
            value="A timeout temporarily prevents you from sending messages, adding reactions, joining voice channels, or using forum features.",
            inline=False
        )
        
        embed.add_field(
            name="How long do timeouts last?",
            value=(
                "• First violation: Warning only\n"
                "• Second violation: 1 minute\n"
                "• Third violation: 2 minutes\n"
                "• Fourth+ violation: 10 minutes\n\n"
                "Serious violations may result in longer timeouts or immediate bans."
            ),
            inline=False
        )
        
        embed.add_field(
            name="What happens after a timeout?",
            value="Once your timeout expires, you'll automatically regain the ability to participate normally.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Example command implementation for bot.py
"""
@bot.command(name="modhelp")
async def modhelp_command(ctx):
    '''Show the interactive moderation tooltip wizard'''
    await send_moderation_tooltip(ctx)
"""

# For direct integration with welcome messages
"""
# Add this to your welcome message view
@discord.ui.button(label="Moderation Guide", emoji="📋", style=discord.ButtonStyle.secondary)
async def moderation_guide_button(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.user_id:
        await interaction.response.send_message("This guide is not for you!", ephemeral=True)
        return
        
    await send_moderation_tooltip(interaction)
"""