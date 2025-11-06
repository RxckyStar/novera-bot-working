"""
Animated Server Walkthrough and Welcome System for Novera Assistant
This module provides an interactive onboarding experience for new server members
with step-by-step guides, command tutorials, and animated welcome messages.
"""

import discord
import asyncio
import random
import logging
from discord.ext import commands
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime, timedelta

# Animation frames for welcome message (emoji-based animation)
WELCOME_ANIMATION_FRAMES = [
    "✨ Welcome! ✨",
    "✨ Welcome! 🌟",
    "✨ Welcome! 🌟 ✨",
    "🌟 Welcome! 🌟 ✨",
    "🌟 ✨ Welcome! 🌟 ✨",
    "🌟 ✨ 🎉 Welcome! 🎉 ✨ 🌟",
    "🌟 ✨ 🎉 Welcome! 🎉 ✨ 🌟 ✨",
    "🌟 ✨ 🎉 💖 Welcome! 💖 🎉 ✨ 🌟 ✨"
]

# Animated tutorial emojis
TUTORIAL_ANIMATION = [
    "⏳", "⌛", "⏳", "⌛", "✅"
]

# Command categories for the walkthrough
COMMAND_CATEGORIES = {
    "General": ["checkvalue", "activity", "rankings", "mommy"],
    "Fun": ["spank", "headpat", "confess", "spill", "shopping", "tipjar"],
    "Evaluation": ["eval", "tryoutsresults", "addvalue", "sm"],
    "Matches": ["anteup"]
}

# Command descriptions for the walkthrough
COMMAND_DESCRIPTIONS = {
    "checkvalue": "Check your current value or someone else's value",
    "activity": "View your or someone else's activity statistics",
    "rankings": "See the top-valued members in the server",
    "mommy": "Get help and information about available commands",
    "spank": "Playfully spank another member (requires Spank role)",
    "headpat": "Give headpats to members (requires Headpat role)",
    "confess": "Hear what Mommy has been up to behind the scenes",
    "spill": "Get juicy gossip about server members",
    "shopping": "See what luxury items Mommy has purchased recently",
    "tipjar": "Check Mommy's special fund status",
    "eval": "Evaluate a player's performance (in BLR server)",
    "tryoutsresults": "Submit tryouts results for a player (evaluator role only)",
    "addvalue": "Add or subtract value from a member (trainer role only)",
    "sm": "Set a member's value directly (admin/trainer role only)",
    "anteup": "Ante up for a match with your value"
}

class CommandTutorialView(discord.ui.View):
    """Interactive command tutorial view for new members"""
    
    def __init__(self, user_id: int, category: str = "General"):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.category = category
        self.current_step = 0
        self.steps_complete = False
        self._add_category_select()
        self._add_navigation_buttons()
    
    def _add_category_select(self):
        """Add the category selection dropdown"""
        select = discord.ui.Select(
            placeholder="Choose a command category",
            options=[
                discord.ui.SelectOption(
                    label=category,
                    description=f"Learn about {category.lower()} commands",
                    value=category,
                    default=(category == self.category)
                ) for category in COMMAND_CATEGORIES.keys()
            ],
            custom_id=f"category_select_{self.user_id}"
        )
        
        select.callback = self.category_select_callback
        self.add_item(select)
    
    def _add_navigation_buttons(self):
        """Add the next and previous buttons"""
        previous_button = discord.ui.Button(
            label="Previous Step",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"previous_{self.user_id}"
        )
        previous_button.callback = self.previous_callback
        self.add_item(previous_button)
        
        next_button = discord.ui.Button(
            label="Next Step",
            style=discord.ButtonStyle.primary,
            custom_id=f"next_{self.user_id}"
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)
        
        finish_button = discord.ui.Button(
            label="Finish",
            style=discord.ButtonStyle.success,
            disabled=True,
            custom_id=f"finish_{self.user_id}"
        )
        finish_button.callback = self.finish_callback
        self.add_item(finish_button)
    
    async def category_select_callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This tutorial is not for you!", ephemeral=True)
                return
                
            self.category = interaction.data["values"][0]
            self.current_step = 0
            self.steps_complete = False
            
            # Update button states
            self._update_button_states()
            
            # Create the new embed for this category
            embed = self._create_current_embed()
            
            logging.info(f"User {interaction.user.id} selected category {self.category}")
            await interaction.response.edit_message(embed=embed, view=self)
            logging.info(f"Successfully updated message with new category {self.category}")
        except Exception as e:
            logging.error(f"Error in category select callback: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error processing your selection. Please try again.", ephemeral=True)
            except Exception as inner_e:
                logging.error(f"Error sending error message: {inner_e}")
    
    async def previous_callback(self, interaction: discord.Interaction):
        """Handle previous button press"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This tutorial is not for you!", ephemeral=True)
                return
                
            self.current_step -= 1
            if self.current_step < 0:
                self.current_step = 0
                
            # Update button states
            self._update_button_states()
            
            # Create the new embed for this step
            embed = self._create_current_embed()
            
            logging.info(f"User {interaction.user.id} navigated to step {self.current_step}")
            await interaction.response.edit_message(embed=embed, view=self)
            logging.info(f"Successfully updated message with step {self.current_step}")
        except Exception as e:
            logging.error(f"Error in previous button callback: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error navigating to the previous step. Please try again.", ephemeral=True)
            except Exception as inner_e:
                logging.error(f"Error sending error message: {inner_e}")
    
    async def next_callback(self, interaction: discord.Interaction):
        """Handle next button press"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This tutorial is not for you!", ephemeral=True)
                return
                
            # Get commands for the current category
            commands = COMMAND_CATEGORIES[self.category]
            
            self.current_step += 1
            if self.current_step >= len(commands):
                self.current_step = len(commands) - 1
                self.steps_complete = True
                
            # Update button states
            self._update_button_states()
            
            # Create the new embed for this step
            embed = self._create_current_embed()
            
            # Show loading feedback instead of animation which may be causing issues
            await interaction.response.defer(ephemeral=False)
            
            logging.info(f"User {interaction.user.id} navigated to step {self.current_step}")
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            logging.info(f"Successfully updated message with step {self.current_step}")
        except Exception as e:
            logging.error(f"Error in next button callback: {e}", exc_info=True)
            try:
                await interaction.followup.send("There was an error navigating to the next step. Please try again.", ephemeral=True)
            except Exception as inner_e:
                logging.error(f"Error sending error message: {inner_e}")
    
    async def finish_callback(self, interaction: discord.Interaction):
        """Handle finish button press"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This tutorial is not for you!", ephemeral=True)
                return
                
            # Create completion embed
            embed = discord.Embed(
                title="✅ Walkthrough Complete!",
                description=(
                    f"You've completed the {self.category} commands tutorial!\n\n"
                    "Feel free to explore other command categories or start using the commands in the server."
                ),
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🎮 Try It Out!",
                value=f"Try using some of these commands in the server now!",
                inline=False
            )
            
            embed.set_footer(text="Thank you for completing the tutorial!")
            
            logging.info(f"User {interaction.user.id} completed the tutorial")
            await interaction.response.edit_message(embed=embed, view=None)
            logging.info(f"Successfully updated message with completion")
        except Exception as e:
            logging.error(f"Error in finish button callback: {e}", exc_info=True)
            try:
                await interaction.response.send_message("There was an error completing the tutorial. Please try again.", ephemeral=True)
            except Exception as inner_e:
                logging.error(f"Error sending error message: {inner_e}")
    
    def _update_button_states(self):
        """Update the state of the navigation buttons"""
        # Get the children that are buttons
        buttons = [child for child in self.children if isinstance(child, discord.ui.Button)]
        
        # Previous button - first item
        buttons[1].disabled = (self.current_step <= 0)
        
        # Finish button - last item
        buttons[3].disabled = not self.steps_complete
    
    def _create_current_embed(self) -> discord.Embed:
        """Create an embed for the current step"""
        commands = COMMAND_CATEGORIES[self.category]
        current_command = commands[self.current_step]
        
        embed = discord.Embed(
            title=f"📚 {self.category} Commands - {self.current_step + 1}/{len(commands)}",
            description=f"Learn about the `!{current_command}` command:",
            color=discord.Color.blue()
        )
        
        # Command description
        embed.add_field(
            name=f"!{current_command}",
            value=COMMAND_DESCRIPTIONS.get(current_command, "No description available"),
            inline=False
        )
        
        # Command usage
        usage_examples = self._get_command_usage(current_command)
        embed.add_field(
            name="📝 Usage Examples",
            value=usage_examples,
            inline=False
        )
        
        # Command tips
        tips = self._get_command_tips(current_command)
        if tips:
            embed.add_field(
                name="💡 Tips",
                value=tips,
                inline=False
            )
        
        # Progress tracker
        progress = "🔘" * self.current_step + "⚪" * (len(commands) - self.current_step - 1) + "🔘"
        embed.set_footer(text=f"Progress: {progress}")
        
        return embed
    
    def _get_command_usage(self, command: str) -> str:
        """Get usage examples for a specific command"""
        usage_examples = {
            "checkvalue": "!checkvalue\n!checkvalue @user",
            "activity": "!activity\n!activity @user",
            "rankings": "!rankings",
            "mommy": "!mommy",
            "spank": "!spank @user",
            "headpat": "!headpat",
            "confess": "!confess",
            "spill": "!spill",
            "shopping": "!shopping",
            "tipjar": "!tipjar",
            "eval": "!eval @user",
            "tryoutsresults": "!tryoutsresults @user",
            "addvalue": "!addvalue @user +5\n!addvalue @user -3",
            "sm": "!sm @user 100",
            "anteup": "!anteup 5"
        }
        return usage_examples.get(command, "No usage examples available")
    
    def _get_command_tips(self, command: str) -> str:
        """Get tips for a specific command"""
        tips = {
            "checkvalue": "Your value increases based on activity and evaluations!",
            "activity": "Stay active to increase your activity score and value!",
            "rankings": "The top 10 valued members get special roles!",
            "spank": "You need the spank role to use this command!",
            "headpat": "Get the headpat role to use this command! Get 3 headpats to become the Headpat Champion!",
            "eval": "Only available in the BLR server for player evaluations",
            "tryoutsresults": "Only evaluators can use this command",
            "addvalue": "Only trainers can adjust member values",
            "sm": "Only admins and trainers can set values directly",
            "anteup": "Your ante amount must be less than or equal to your current value"
        }
        return tips.get(command, "")

class ServerGuideView(discord.ui.View):
    """Interactive server guide view for the welcome message"""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.user_id = user_id
    
    @discord.ui.button(label="Command Tutorial", style=discord.ButtonStyle.primary, emoji="📚", row=0, custom_id="cmd_tutorial")
    async def command_tutorial_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Start the command tutorial"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This tutorial is not for you!", ephemeral=True)
                return
                
            # Create the tutorial view
            view = CommandTutorialView(self.user_id)
            
            # Create the initial embed
            embed = discord.Embed(
                title="📚 Command Tutorial",
                description="Welcome to the command tutorial! Let's learn about the different commands available.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="🎮 Getting Started",
                value="Select a category below to learn about different types of commands.",
                inline=False
            )
            
            embed.add_field(
                name="⬇️ Categories",
                value="\n".join([f"• **{category}**: {', '.join(['!' + cmd for cmd in cmds[:3]])}" for category, cmds in COMMAND_CATEGORIES.items()]),
                inline=False
            )
            
            embed.set_footer(text="Use the buttons below to navigate through the tutorial")
            
            # Add debug logging
            logging.info(f"Sending command tutorial to user {interaction.user.id}")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logging.info(f"Successfully sent command tutorial to user {interaction.user.id}")
        except Exception as e:
            logging.error(f"Error in command_tutorial button: {e}", exc_info=True)
            try:
                # Fallback response if the original interaction fails
                await interaction.response.send_message("Command tutorial is being prepared. Please try again in a moment!", ephemeral=True)
            except Exception as inner_e:
                logging.error(f"Error in command tutorial fallback: {inner_e}")
    
    @discord.ui.button(label="Server Guide", style=discord.ButtonStyle.success, emoji="🗺️", row=0, custom_id="server_guide")
    async def server_guide_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show the server guide"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This guide is not for you!", ephemeral=True)
                return
                
            # Determine server-specific guide
            if interaction.guild and interaction.guild.id == 1350165280940228629:  # Novera Team Hub
                embed = self._get_novera_guide()
            elif interaction.guild and interaction.guild.id == 1345538548027232307:  # BLR server
                embed = self._get_blr_guide()
            else:
                guild_name = interaction.guild.name if interaction.guild else "the server"
                embed = self._get_generic_guide(guild_name)
            
            logging.info(f"Sending server guide to user {interaction.user.id}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logging.info(f"Successfully sent server guide to user {interaction.user.id}")
        except Exception as e:
            logging.error(f"Error in server_guide button: {e}", exc_info=True)
            try:
                # Fallback response if the original interaction fails
                await interaction.response.send_message("Server guide is being prepared. Please try again in a moment!", ephemeral=True)
            except Exception as inner_e:
                logging.error(f"Error in server guide fallback: {inner_e}")
    
    @discord.ui.button(label="My Profile", style=discord.ButtonStyle.secondary, emoji="👤", row=1, custom_id="profile")
    async def my_profile_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Show the user's profile"""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This profile is not for you!", ephemeral=True)
                return
                
            # Create the profile embed
            embed = discord.Embed(
                title=f"👤 {interaction.user.display_name}'s Profile",
                description="Here's your current profile information:",
                color=discord.Color.purple()
            )
            
            # Add member information
            embed.add_field(
                name="🆔 User ID",
                value=f"{interaction.user.id}",
                inline=True
            )
            
            if hasattr(interaction.user, 'joined_at') and interaction.user.joined_at:
                embed.add_field(
                    name="📅 Joined Server",
                    value=f"<t:{int(interaction.user.joined_at.timestamp())}:R>",
                    inline=True
                )
            
            embed.add_field(
                name="📅 Account Created",
                value=f"<t:{int(interaction.user.created_at.timestamp())}:R>",
                inline=True
            )
            
            # Add roles if in a guild context
            if interaction.guild:
                roles = [role.mention for role in interaction.user.roles if role.name != "@everyone"]
                if roles:
                    embed.add_field(
                        name=f"🏷️ Roles ({len(roles)})",
                        value=" ".join(roles) if len(roles) <= 10 else " ".join(roles[:10]) + f" (+{len(roles) - 10} more)",
                        inline=False
                    )
            
            # Set thumbnail to user's avatar
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logging.error(f"Error in my_profile button: {e}", exc_info=True)
            try:
                # Fallback response if the original interaction fails
                await interaction.response.send_message("Your profile is being prepared. Please try again in a moment!", ephemeral=True)
            except:
                pass
    
    def _get_novera_guide(self) -> discord.Embed:
        """Get the Novera server guide embed"""
        embed = discord.Embed(
            title="🗺️ Novera Team Hub Guide",
            description="Welcome to the Novera Team Hub! Here's everything you need to know:",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="📜 Server Rules",
            value=(
                "1. Be respectful to all members\n"
                "2. No spamming or excessive mention\n"
                "3. Keep content appropriate\n"
                "4. Follow Discord's Terms of Service\n"
                "5. Listen to staff members"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Value System",
            value=(
                "• Your **value** represents your worth in the server\n"
                "• Increase your value through activity and evaluations\n"
                "• Use `!checkvalue` to see your current value\n"
                "• Top valued members receive special roles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏆 Rankings",
            value=(
                "• Use `!rankings` to see the top players\n"
                "• Rankings update automatically with values\n"
                "• Top 10 players get special ranking roles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Getting Evaluated",
            value=(
                "• Ask an evaluator to assess your skills\n"
                "• Evaluations affect your value\n"
                "• Work on improving based on feedback"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use !mommy to see all available commands")
        
        return embed
    
    def _get_blr_guide(self) -> discord.Embed:
        """Get the BLR server guide embed"""
        embed = discord.Embed(
            title="🗺️ OFFICIAL BL:R E-SPORTS | [NATIONAL] Guide",
            description="Welcome to the BLR server! Here's what you need to know:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📜 Server Rules",
            value=(
                "1. Be respectful to all members\n"
                "2. No spamming or excessive mention\n"
                "3. Keep content appropriate\n"
                "4. Follow Discord's Terms of Service\n"
                "5. Listen to staff members"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎮 Evaluations",
            value=(
                "• Get evaluated by team managers\n"
                "• Use `!eval` command for player evaluations\n"
                "• Evaluators can use `!tryoutsresults` to submit results"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 Value System",
            value=(
                "• Your **value** represents your worth as a player\n"
                "• Managers can adjust your value based on performance\n"
                "• Use `!checkvalue` to see your current value"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use !mommy to see all available commands")
        
        return embed
    
    def _get_generic_guide(self, server_name: str) -> discord.Embed:
        """Get a generic server guide embed"""
        embed = discord.Embed(
            title=f"🗺️ {server_name} Guide",
            description=f"Welcome to {server_name}! Here's what you need to know:",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📜 Server Rules",
            value=(
                "1. Be respectful to all members\n"
                "2. No spamming or excessive mention\n"
                "3. Keep content appropriate\n"
                "4. Follow Discord's Terms of Service\n"
                "5. Listen to staff members"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🤖 Bot Commands",
            value=(
                "• Use `!mommy` to see all available commands\n"
                "• Use `!checkvalue` to see your value\n"
                "• Use `!activity` to check your activity"
            ),
            inline=False
        )
        
        embed.set_footer(text="Enjoy your time in the server!")
        
        return embed

async def send_animated_welcome(channel, member, server_name):
    """Send an animated welcome message for a new member"""
    # First, send initial placeholder embed
    embed = discord.Embed(
        title="Preparing your welcome...",
        description="Loading...",
        color=discord.Color.gold()
    )
    
    message = await channel.send(content=f"A new member is joining...", embed=embed)
    
    # Animate welcome message
    for frame in WELCOME_ANIMATION_FRAMES:
        embed = discord.Embed(
            title=frame,
            description=f"<a:sparkles:1357689412903845989> {member.mention} has joined {server_name}! <a:sparkles:1357689412903845989>",
            color=discord.Color.gold()
        )
        
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        embed.set_footer(text=f"Member #{len(member.guild.members)}")
        embed.timestamp = datetime.now()
        
        if server_name == "Novera Team Hub":
            embed.set_image(url="https://media.discordapp.net/attachments/1350182132043223090/1351324498662555678/novera_banner.png")
        
        await message.edit(content="", embed=embed)
        await asyncio.sleep(0.7)  # Short delay between frames
    
    # Final welcome message with server guide button
    final_embed = discord.Embed(
        title=f"✨ Welcome to {server_name}! ✨",
        description=(
            f"{member.mention} has joined us!\n\n"
            f"We're excited to have you here! Use the buttons below to get started."
        ),
        color=discord.Color.gold()
    )
    
    if member.avatar:
        final_embed.set_thumbnail(url=member.avatar.url)
    
    final_embed.set_footer(text=f"Member #{len(member.guild.members)}")
    final_embed.timestamp = datetime.now()
    
    if server_name == "Novera Team Hub":
        final_embed.set_image(url="https://media.discordapp.net/attachments/1350182132043223090/1351324498662555678/novera_banner.png")
    
    # Create view with server guide buttons
    view = ServerGuideView(member.id)
    
    # Replace message with final version
    await message.edit(content="", embed=final_embed, view=view)

async def send_welcome_dm(member, server_config):
    """Send an interactive welcome DM to a new member"""
    server_id = str(member.guild.id)
    server_name = server_config.get("name", member.guild.name)
    
    try:
        # Create DM channel
        dm_channel = await member.create_dm()
        
        # Create the initial DM embed
        embed = discord.Embed(
            title=f"🎉 Welcome to {server_name}! 🎉",
            description=(
                f"Hello {member.name}! I'm Novera Assistant, your helpful bot!\n\n"
                f"I'll help you navigate {server_name} and learn about all of our features."
            ),
            color=discord.Color.blue()
        )
        
        # Add server-specific information
        if server_id == "1350165280940228629":  # Novera Team Hub
            embed.add_field(
                name="💎 About Novera",
                value=(
                    "Novera is a community focused on player value and development.\n"
                    "Your journey begins with an evaluation, and you'll grow your value through activity and performance!"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🌟 Getting Started",
                value=(
                    "1. Check out the server guide button below\n"
                    "2. Learn about commands with the tutorial\n"
                    "3. Get evaluated by an evaluator\n"
                    "4. Start interacting and increase your value!"
                ),
                inline=False
            )
        elif server_id == "1345538548027232307":  # BLR server
            embed.add_field(
                name="💎 About BL:R E-SPORTS",
                value=(
                    "This is the official server for BL:R E-SPORTS national league.\n"
                    "Player evaluations and team management are our focus!"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🌟 Getting Started",
                value=(
                    "1. Check out the server guide button below\n"
                    "2. Learn about commands with the tutorial\n"
                    "3. Connect with team managers\n"
                    "4. Participate in evaluations and team activities!"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="🌟 Getting Started",
                value=(
                    "1. Check out the server guide button below\n"
                    "2. Learn about commands with the tutorial\n"
                    "3. Start chatting with other members\n"
                    "4. Have fun!"
                ),
                inline=False
            )
        
        # Create server guide view
        view = ServerGuideView(member.id)
        
        # Send the DM with buttons
        await dm_channel.send(embed=embed, view=view)
        
        logging.info(f"Sent interactive welcome DM to new member {member.id} in server {server_id}")
        return True
    except Exception as e:
        logging.error(f"Error sending welcome DM to {member.id}: {e}", exc_info=True)
        return False

# Function to handle new member joins
async def handle_member_join(member, server_config):
    """Main function to handle new member joins with animated welcome"""
    server_id = str(member.guild.id)
    server_name = server_config.get("name", member.guild.name)
    welcome_channel_id = server_config.get("welcome_channel_id")
    new_member_role_id = server_config.get("new_member_role_id")
    
    # Assign new member role if specified
    if new_member_role_id:
        try:
            new_member_role = discord.utils.get(member.guild.roles, id=int(new_member_role_id))
            if new_member_role:
                await member.add_roles(new_member_role)
                logging.info(f"Added new member role {new_member_role.name} to {member.id} in server {server_id}")
        except Exception as e:
            logging.error(f"Error adding new member role: {e}", exc_info=True)
    
    # Find welcome channel
    welcome_channel = None
    if welcome_channel_id:
        welcome_channel = member.guild.get_channel(int(welcome_channel_id))
    
    if not welcome_channel:
        # Try to find a channel with 'welcome' in the name
        for channel in member.guild.text_channels:
            if 'welcome' in channel.name.lower():
                welcome_channel = channel
                break
    
    # Send animated welcome message if we have a channel
    if welcome_channel:
        try:
            await send_animated_welcome(welcome_channel, member, server_name)
            logging.info(f"Sent animated welcome message for {member.id} in server {server_id}")
        except Exception as e:
            logging.error(f"Error sending animated welcome: {e}", exc_info=True)
    
    # Send interactive welcome DM
    await send_welcome_dm(member, server_config)