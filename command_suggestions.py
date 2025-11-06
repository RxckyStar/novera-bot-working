"""
Command suggestion system for the Novera bot
Provides interactive command suggestions when users type the command prefix
"""

import discord
from discord.ext import commands
import logging
import asyncio
from typing import List, Dict, Optional
from server_config import is_command_disabled, uses_sassy_language

# Configure logging
logger = logging.getLogger(__name__)

# Command categories for better organization
COMMAND_CATEGORIES = {
    "General": ["value", "activity", "rankings", "help"],
    "Match": ["match", "matchresult", "matchcancel", "anteup"],
    "Skills": ["getevaluated", "tryoutsresults", "tryoutcancel"],
    "Fun": ["spank", "headpat", "spill", "shopping", "tipjar", "confess"]
}

# Command descriptions
COMMAND_DESCRIPTIONS = {
    "value": "Check your value or someone else's value",
    "activity": "Check your activity or someone else's activity",
    "rankings": "View the top player rankings",
    "help": "Show help information",
    "match": "Create a new match",
    "matchresult": "Report match results",
    "matchcancel": "Cancel an ongoing match",
    "anteup": "Join an existing match",
    "getevaluated": "Request a player evaluation",
    "tryoutsresults": "Evaluate a player (staff only)",
    "tryoutcancel": "Cancel an evaluation (staff only)",
    "spank": "Spank someone",
    "headpat": "Give someone a headpat",
    "spill": "Get juicy gossip",
    "shopping": "See Mommy's purchases",
    "tipjar": "Check Mommy's special fund",
    "confess": "Make Mommy confess"
}

class CommandSuggestionView(discord.ui.View):
    """Interactive view for command suggestions"""
    
    def __init__(self, prefix: str, commands_list: List[str], 
                 descriptions: Dict[str, str], server_id: str, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.prefix = prefix
        self.server_id = server_id
        self.use_sassy = uses_sassy_language(server_id)
        
        # Add buttons for each command (max 25 per view due to Discord limitations)
        for i, cmd in enumerate(commands_list[:25]):
            # Skip disabled commands for this server
            if is_command_disabled(cmd, server_id):
                continue
                
            # Create button with appropriate styling
            btn = discord.ui.Button(
                label=cmd,
                style=discord.ButtonStyle.primary,
                custom_id=f"cmd_{cmd}"
            )
            
            # Set the callback
            btn.callback = self.create_callback(cmd)
            
            # Add tooltip description
            if cmd in descriptions:
                btn.tooltip = descriptions[cmd]
                
            # Add the button to the view
            self.add_item(btn)
    
    def create_callback(self, command_name: str):
        """Create a callback function for a command button"""
        async def callback(interaction: discord.Interaction):
            # Delete the suggestion message
            await interaction.message.delete()
            
            # Send a confirmation message
            if self.use_sassy:
                await interaction.response.send_message(
                    f"💖 Using command `{self.prefix}{command_name}`, darling! Check your input! 💖",
                    ephemeral=True,
                    delete_after=3.0
                )
            else:
                await interaction.response.send_message(
                    f"Selected command: `{self.prefix}{command_name}`",
                    ephemeral=True,
                    delete_after=3.0
                )
            
            # Log command selection
            logger.info(f"User {interaction.user.id} selected command '{command_name}' via suggestion UI")
            
        return callback
    
    async def on_timeout(self):
        """Handle timeout by disabling all buttons"""
        # Disable all buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                
        # Try to update the message with disabled buttons
        try:
            if hasattr(self, 'message') and self.message:
                await self.message.edit(view=self)
        except Exception as e:
            logger.error(f"Error updating suggestion view on timeout: {e}")


class CategorySelect(discord.ui.Select):
    """Category selection dropdown for command filters"""
    
    def __init__(self, categories: Dict[str, List[str]], descriptions: Dict[str, str], 
                 command_prefix: str, server_id: str):
        # Create options for each category
        options = [
            discord.SelectOption(
                label=category,
                description=f"{len(commands)} commands in this category",
                value=category
            )
            for category, commands in categories.items()
            # Only include categories with at least one enabled command
            if any(not is_command_disabled(cmd, server_id) for cmd in commands)
        ]
        
        # Add "All Commands" option
        all_commands = sum(categories.values(), [])
        enabled_count = sum(1 for cmd in all_commands if not is_command_disabled(cmd, server_id))
        
        options.insert(0, discord.SelectOption(
            label="All Commands",
            description=f"{enabled_count} available commands",
            value="all"
        ))
        
        super().__init__(
            placeholder="Select command category...",
            options=options,
        )
        
        self.categories = categories
        self.descriptions = descriptions
        self.command_prefix = command_prefix
        self.server_id = server_id
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        # Get the selected category
        selected = self.values[0]
        
        # Get commands for the category
        if selected == "all":
            # Get all commands
            commands = sum(self.categories.values(), [])
        else:
            # Get commands for the specific category
            commands = self.categories.get(selected, [])
        
        # Filter out disabled commands
        commands = [cmd for cmd in commands if not is_command_disabled(cmd, self.server_id)]
        
        # Create a new suggestion view with the filtered commands
        view = CommandSuggestionView(
            self.command_prefix, 
            commands, 
            self.descriptions, 
            self.server_id
        )
        
        # Add the category select back
        view.add_item(CategorySelect(
            self.categories, 
            self.descriptions, 
            self.command_prefix, 
            self.server_id
        ))
        
        # Get appropriate message style
        use_sassy = uses_sassy_language(self.server_id)
        if use_sassy:
            content = f"💖 **{selected} Commands** 💖\nClick a button to use that command, sweetie!"
        else:
            content = f"**{selected} Commands**\nClick a button to use a command."
        
        # Update the message
        await interaction.response.edit_message(content=content, view=view)


class CommandSuggestionSystem:
    """Manager for command suggestions"""
    
    def __init__(self, bot, command_prefix: str = "!"):
        self.bot = bot
        self.command_prefix = command_prefix
        self.pending_suggestion_users = set()
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Command suggestion system initialized with prefix: {command_prefix}")
        
    async def handle_potential_command(self, message: discord.Message) -> bool:
        """Handle a message that might be a command attempt
        
        Returns:
            bool: True if this was a suggestion trigger, False otherwise
        """
        # Skip if not in a guild
        if not message.guild:
            return False
            
        # Get message content
        content = message.content.strip()
        
        # Check if message is just the prefix or prefix + partial command
        if not content.startswith(self.command_prefix):
            return False
            
        # Skip if the user is already getting suggestions (prevent spam)
        if message.author.id in self.pending_suggestion_users:
            return False
            
        # Get the potential partial command (after prefix)
        partial_cmd = content[len(self.command_prefix):].strip().lower()
        
        # Only show suggestions for prefix-only or short partial commands
        if len(partial_cmd) > 3:
            return False
            
        # Show suggestions for the user
        await self.show_command_suggestions(message, partial_cmd)
        return True
    
    async def show_command_suggestions(self, message: discord.Message, partial_cmd: str = ""):
        """Show command suggestions for a user"""
        try:
            # Mark user as pending
            self.pending_suggestion_users.add(message.author.id)
            
            # Get server ID
            server_id = str(message.guild.id)
            
            # Check if we're using sassy language
            use_sassy = uses_sassy_language(server_id)
            
            # Filter commands based on the partial input
            filtered_categories = {}
            
            # If we have a partial command, filter all categories
            if partial_cmd:
                for category, commands in COMMAND_CATEGORIES.items():
                    matching = [cmd for cmd in commands if cmd.startswith(partial_cmd)]
                    if matching:
                        filtered_categories[category] = matching
            else:
                # Otherwise use all categories
                filtered_categories = COMMAND_CATEGORIES
            
            # If we have no matching commands, don't show suggestions
            if not filtered_categories:
                self.pending_suggestion_users.remove(message.author.id)
                return
                
            # Create suggestion view
            all_commands = sum(filtered_categories.values(), [])
            view = CommandSuggestionView(
                self.command_prefix, 
                all_commands, 
                COMMAND_DESCRIPTIONS, 
                server_id
            )
            
            # Add category selector if we have multiple categories
            if len(filtered_categories) > 1:
                view.add_item(CategorySelect(
                    filtered_categories, 
                    COMMAND_DESCRIPTIONS, 
                    self.command_prefix, 
                    server_id
                ))
            
            # Create appropriate message based on server style
            if use_sassy:
                if partial_cmd:
                    content = f"💖 **Commands starting with '{partial_cmd}'** 💖\nClick a button to use that command, sweetie!"
                else:
                    content = f"💖 **Available Commands** 💖\nHere are all the commands Mommy knows, darling! Click one to use it!"
            else:
                if partial_cmd:
                    content = f"**Commands starting with '{partial_cmd}'**\nClick a button to use a command."
                else:
                    content = f"**Available Commands**\nClick a button to use a command."
            
            # Send the suggestion message
            suggestion_msg = await message.channel.send(content=content, view=view)
            
            # Store the message for timeout handling
            view.message = suggestion_msg
            
            # Log suggestion display
            self.logger.info(f"Showing command suggestions to {message.author.id} in {message.guild.id}")
            
            # Wait for a short period then delete the original trigger message
            await asyncio.sleep(1)
            try:
                await message.delete()
            except Exception as e:
                self.logger.debug(f"Failed to delete trigger message: {e}")
                
        except Exception as e:
            self.logger.error(f"Error showing command suggestions: {e}", exc_info=True)
        finally:
            # Remove user from pending after a short delay
            await asyncio.sleep(3)
            try:
                self.pending_suggestion_users.remove(message.author.id)
            except KeyError:
                pass
                
    def register_with_bot(self):
        """Register our message handler with the bot"""
        # Store original on_message handler
        if hasattr(self.bot, 'on_message'):
            original_on_message = self.bot.on_message
        else:
            original_on_message = None
            
        # Create new handler
        @self.bot.event
        async def on_message(message):
            # Ignore bot messages
            if message.author.bot:
                return
                
            # Try to handle as command suggestion
            if await self.handle_potential_command(message):
                # If it was handled as a suggestion, don't process as command
                return
                
            # Otherwise pass to original handler
            if original_on_message:
                await original_on_message(message)
            else:
                # If there was no original handler, process commands
                await self.bot.process_commands(message)
                
        self.logger.info("Command suggestion handler registered with bot")