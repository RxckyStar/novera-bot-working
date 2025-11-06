#!/usr/bin/env python3
"""
Moderation Tooltips Module
--------------------------
This module provides interactive tooltips and guides for moderators to help with common tasks.
"""

import discord
import logging
import random
from typing import Dict, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("moderation_tooltips")

# Tooltip categories and content
MODERATION_TOOLTIPS = {
    "warning": {
        "title": "⚠️ Warning a Member",
        "description": "How to properly warn a member for rule violations",
        "steps": [
            "1. Identify the specific rule that was violated",
            "2. Provide clear evidence of the violation (screenshots, message links)",
            "3. Use a neutral, professional tone when addressing the member",
            "4. Explain the potential consequences if behavior continues",
            "5. Document the warning in the moderation logs channel"
        ],
        "examples": [
            "@username I'm giving you a formal warning for breaking Rule #3 (No Spamming). Please refrain from posting the same message repeatedly in multiple channels. Further violations may result in a timeout.",
            "@username This is a warning for violating our server's Rule #6 (Respectful Communication). Your recent comments were unnecessarily aggressive. Please keep discussions civil or we may need to take further action."
        ],
        "tips": [
            "Always remain calm and don't engage in arguments",
            "Be specific about which rule was broken",
            "Give the user a chance to explain themselves",
            "Consider cultural or language differences",
            "Follow up in private DMs for sensitive issues"
        ],
        "color": discord.Color.gold()
    },
    "timeout": {
        "title": "⏰ Timing Out a Member",
        "description": "How to properly issue a temporary timeout",
        "steps": [
            "1. Determine an appropriate timeout duration based on severity",
            "2. Right-click the user's name and select 'Timeout'",
            "3. Select the appropriate duration (5min, 10min, 1hr, 1day, 1wk)",
            "4. Inform the user why they've been timed out",
            "5. Document the timeout in the moderation logs channel"
        ],
        "examples": [
            "Applied a 10-minute timeout to @username for spamming emoji in #general-chat",
            "Issued a 1-hour timeout to @username for continued disruptive behavior after multiple warnings"
        ],
        "tips": [
            "Start with shorter timeouts for minor offenses",
            "Explain the duration and reason for the timeout",
            "Use timeouts rather than kicks for temporary issues",
            "Always document why the timeout was applied",
            "Check previous moderation history before deciding on duration"
        ],
        "color": discord.Color.orange()
    },
    "kick": {
        "title": "👢 Kicking a Member",
        "description": "When and how to kick a member from the server",
        "steps": [
            "1. Verify that a kick is the appropriate action (vs warning or timeout)",
            "2. Right-click the user's name and select 'Kick'",
            "3. Provide a detailed reason in the prompt",
            "4. Document the kick in the moderation logs channel",
            "5. Be prepared to explain your decision to other moderators"
        ],
        "examples": [
            "Kicked @username for creating multiple spam accounts to advertise",
            "Kicked @username for repeatedly rejoining on alternate accounts to evade timeouts"
        ],
        "tips": [
            "Kicks should typically follow warnings or timeouts for repeat offenses",
            "Users can rejoin with a new invite after being kicked",
            "Consider a temporary ban instead for more serious issues",
            "Always document clear evidence before kicking",
            "Discuss with other moderators for borderline cases"
        ],
        "color": discord.Color.red()
    },
    "ban": {
        "title": "🔨 Banning a Member",
        "description": "When and how to permanently ban someone from the server",
        "steps": [
            "1. Verify that a ban is the appropriate action (serious/repeated violations)",
            "2. Collect and document evidence of the violations",
            "3. Right-click the user's name and select 'Ban'",
            "4. Choose whether to delete their recent messages",
            "5. Document the ban with evidence in the moderation logs channel"
        ],
        "examples": [
            "Banned @username for posting NSFW content in multiple channels after warnings",
            "Permanently banned @username for threatening behavior toward other members"
        ],
        "tips": [
            "Bans should be used only for serious violations or pattern of misconduct",
            "Consider temporary bans (with set durations) for less severe cases",
            "Always document extensive evidence before permanent bans",
            "Discuss permanent bans with other moderators/admins first",
            "Ensure ban reasons are detailed enough for appeals review"
        ],
        "color": discord.Color.dark_red()
    },
    "raids": {
        "title": "🛡️ Handling Raids",
        "description": "How to respond to server raids and mass spam",
        "steps": [
            "1. Enable 'Slowmode' in affected channels immediately (Server Settings → Channels)",
            "2. Temporarily increase verification level (Server Settings → Moderation)",
            "3. Ban obvious raid accounts and delete their messages",
            "4. Use @everyone only if absolutely necessary to warn members",
            "5. Coordinate with other online moderators in the mod channel"
        ],
        "examples": [
            "RAID ALERT: Multiple spam accounts detected. Enabled slowmode in all channels and increased verification level. Other mods please assist with banning accounts.",
            "Coordinated response to raid: @Mod1 handle bans, @Mod2 clean up messages, @Mod3 communicate with members"
        ],
        "tips": [
            "Don't panic - stay calm and methodical",
            "Focus on containing the damage first before cleanup",
            "Consider temporarily disabling new member joins during active raids",
            "Document raid patterns to block similar attacks in future",
            "After the raid, review security settings and bot configurations"
        ],
        "color": discord.Color.dark_purple()
    },
    "cleanup": {
        "title": "🧹 Message Cleanup",
        "description": "How to efficiently clean up inappropriate messages",
        "steps": [
            "1. Identify the scope of messages needing removal",
            "2. For individual messages: Hover → Three dots → Delete",
            "3. For bulk deletion: Use moderation bot commands (e.g. `/cleanup 10`)",
            "4. Remember Discord's 14-day limit for bulk deletion",
            "5. Document significant cleanups in the moderation logs"
        ],
        "examples": [
            "Deleted 15 spam messages from #general-chat using MEE6 clean command",
            "Removed inappropriate thread in #questions and informed the user via DM about our content policy"
        ],
        "tips": [
            "Learn your moderation bot's commands for efficient cleanup",
            "For extensive spam, consider temporarily locking the channel",
            "Always document why messages were removed (screenshot before deletion)",
            "Messages older than 14 days must be deleted manually one-by-one",
            "Consider if a timeout is needed in addition to message removal"
        ],
        "color": discord.Color.green()
    },
    "disputes": {
        "title": "⚖️ Handling Member Disputes",
        "description": "How to effectively mediate conflicts between members",
        "steps": [
            "1. Move the dispute to a private channel or DMs",
            "2. Listen to both sides equally without showing bias",
            "3. Identify if any server rules were violated",
            "4. Help members find a resolution they both accept",
            "5. Apply appropriate moderation actions only if necessary"
        ],
        "examples": [
            "Addressed dispute between @user1 and @user2 regarding tournament rules. Moved discussion to #mod-help and clarified the official rules.",
            "Mediated heated argument in #general by creating a private thread to discuss with both members separately before rejoining the conversation"
        ],
        "tips": [
            "Remain neutral and don't take sides publicly",
            "Focus on de-escalation before punishment",
            "Separate the members if the dispute is getting heated",
            "Avoid making public judgments about who started it",
            "Document resolution approaches that work for future reference"
        ],
        "color": discord.Color.blue()
    },
    "appeals": {
        "title": "📝 Handling Moderation Appeals",
        "description": "How to fairly process appeals for moderation actions",
        "steps": [
            "1. Review the original moderation action and evidence",
            "2. Read the appeal with an open mind",
            "3. Consult with the moderator who took the original action",
            "4. Consider if the user understands what they did wrong",
            "5. Make a decision based on evidence, not emotion"
        ],
        "examples": [
            "Appeal from @username was approved after they demonstrated understanding of why their behavior violated our rules",
            "Denied appeal from @username as they continue to argue that rule-breaking behavior should be allowed"
        ],
        "tips": [
            "Have a standardized appeal format for users to follow",
            "Set a cooling-off period before allowing appeals",
            "Be willing to admit if a moderation action was too harsh",
            "Consider probationary returns for borderline cases",
            "Document all appeal decisions for consistency"
        ],
        "color": discord.Color.teal()
    }
}

class TooltipSelectView(discord.ui.View):
    """Dropdown view for selecting moderation tooltips"""
    
    def __init__(self, author_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.author_id = author_id
        
        # Add tooltip selector
        self.add_item(TooltipSelect())
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can interact with this view"""
        return interaction.user.id == self.author_id
    
    async def on_timeout(self):
        """Handle view timeout"""
        for item in self.children:
            item.disabled = True

class TooltipSelect(discord.ui.Select):
    """Dropdown for selecting moderation tooltip categories"""
    
    def __init__(self):
        options = []
        for key, tooltip in MODERATION_TOOLTIPS.items():
            options.append(
                discord.SelectOption(
                    label=tooltip["title"],
                    description=tooltip["description"][:100],  # Truncate if too long
                    value=key,
                    emoji=tooltip["title"].split()[0]  # Use the first character (emoji) from the title
                )
            )
        
        super().__init__(
            placeholder="Select a moderation topic...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle the tooltip selection"""
        # Get the selected tooltip
        selected_key = self.values[0]
        tooltip = MODERATION_TOOLTIPS[selected_key]
        
        # Create the detailed tooltip embed
        embed = discord.Embed(
            title=tooltip["title"],
            description=tooltip["description"],
            color=tooltip["color"]
        )
        
        # Add steps field
        embed.add_field(
            name="📋 Step-by-Step Process",
            value="\n".join(tooltip["steps"]),
            inline=False
        )
        
        # Add examples field
        embed.add_field(
            name="💬 Example Messages",
            value="\n\n".join([f"• *{example}*" for example in tooltip["examples"]]),
            inline=False
        )
        
        # Add tips field
        embed.add_field(
            name="💡 Pro Tips",
            value="\n".join([f"• {tip}" for tip in tooltip["tips"]]),
            inline=False
        )
        
        # Add footer
        embed.set_footer(text=f"Moderation Tooltip | Use the dropdown to view other topics")
        
        # Send the detailed tooltip
        await interaction.response.edit_message(embed=embed, view=self.view)
        
        # Log the interaction
        logger.info(f"User {interaction.user.name} viewed the '{selected_key}' moderation tooltip")

async def send_moderation_tooltip_wizard(ctx):
    """Send the interactive moderation tooltip wizard"""
    # Create initial embed
    embed = discord.Embed(
        title="🛡️ Moderation Tooltip Wizard",
        description="Welcome to the interactive moderation guide! Select a topic below to learn best practices for various moderation scenarios.",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="Available Topics",
        value="\n".join([f"• {tooltip['title']}" for tooltip in MODERATION_TOOLTIPS.values()]),
        inline=False
    )
    
    embed.set_footer(text="Select a topic from the dropdown menu below")
    
    # Create and send the view with the dropdown
    view = TooltipSelectView(ctx.author.id)
    await ctx.send(embed=embed, view=view)
    
    # Log the command usage
    logger.info(f"Moderation tooltip wizard was started by {ctx.author.name} (ID: {ctx.author.id})")

# More complex dropdown with sub-categories could be added here