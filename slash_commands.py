"""
Slash commands for Novera Discord bot
This module implements the Discord application commands (slash commands) interface
"""

import discord
from discord import app_commands
from typing import Optional, List, Dict, Any
import logging
import random

from data_manager import DataManager
from utils import has_value_management_role, format_ranking_message
from server_config import is_command_disabled, uses_sassy_language, get_message_style

# Configure logging
logger = logging.getLogger(__name__)

# Command groups
novera_group = app_commands.Group(name="nova", description="Novera bot commands")
admin_group = app_commands.Group(name="admin", description="Administrative commands for Novera bot")


# =============================
# COMMAND SETUP FUNCTION
# =============================
def setup_slash_commands(bot, data_manager):
    """
    Set up all slash commands and link them to the bot
    This should be called once the bot is ready
    """
    logger.info("Setting up slash commands...")
    
    # Store the data manager for use in command callbacks
    global dm
    dm = data_manager
    
    # Add command groups
    try:
        bot.tree.add_command(novera_group)
    except Exception as e:
        logger.warning(f"Group 'novera' already registered: {e}")
        
    try:
        bot.tree.add_command(admin_group)
    except Exception as e:
        logger.warning(f"Group 'admin' already registered: {e}")
    
    # Only add subgroups if they haven't been registered already
    if 'fun_group' not in getattr(novera_group, '_children', {}):
        try:
            novera_group.add_command(fun_group)
            logger.info("Added fun commands group")
        except Exception as e:
            logger.warning(f"Fun group already registered: {e}")
    
    # Sync commands - this sends commands to Discord
    # We'll sync later to limit API calls
    
    logger.info("Slash commands registered successfully")
    return True


# =============================
# NOVA GROUP COMMANDS - PUBLIC
# =============================

# Fun Commands Group
fun_group = app_commands.Group(name="fun", description="Fun and entertainment commands", parent=novera_group)

@fun_group.command(name="spill", description="Share juicy gossip about Novarians")
async def spill_cmd(interaction: discord.Interaction):
    """Share juicy gossip about Novarians"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("spill", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return
        
        # Import utils to access the gossip generator functions
        import utils
        response = utils.get_spill_response(interaction, dm)
            
        # Send response
        sent_message = await interaction.response.send_message(response)
        
        # Log the command
        logger.info(f"Sent spill response in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova fun spill: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )

@fun_group.command(name="shopping", description="Reveal Mommy's latest luxury purchases")
async def shopping_cmd(interaction: discord.Interaction):
    """Reveal Mommy's latest luxury purchases"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("shopping", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return
        
        # Import utils to access the response generator functions
        import utils
        response = utils.get_shopping_response(interaction, dm)
            
        # Send response
        sent_message = await interaction.response.send_message(response)
        
        # Log the command
        logger.info(f"Sent shopping response in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova fun shopping: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )

@fun_group.command(name="tipjar", description="Check Mommy's special fund status")
async def tipjar_cmd(interaction: discord.Interaction):
    """Check Mommy's special fund status"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("tipjar", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return
        
        # Import utils to access the response generator functions
        import utils
        response = utils.get_tipjar_response(interaction, dm)
            
        # Send response
        sent_message = await interaction.response.send_message(response)
        
        # Log the command
        logger.info(f"Sent tipjar response in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova fun tipjar: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )

@fun_group.command(name="confess", description="Mommy admits what she's been up to behind the scenes")
async def confess_cmd(interaction: discord.Interaction):
    """Mommy admits what she's been up to behind the scenes"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("confess", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return
        
        # Import utils to access the response generator functions
        import utils
        response = utils.get_confess_response(interaction, dm)
            
        # Send response
        sent_message = await interaction.response.send_message(response)
        
        # Log the command
        logger.info(f"Sent confess response in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova fun confess: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )

@novera_group.command(name="value", description="Check your current value or the value of another member")
@app_commands.describe(member="The member whose value you want to check")
async def value_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    """Check your current value or the value of another member"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("checkvalue", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return
        
        # Use requester if no member is specified
        if not member:
            member = interaction.user
        
        # Get member value
        if not member:
            # Fallback to interaction user if member is None
            member = interaction.user
            
        member_id = str(member.id) if member else str(interaction.user.id)
        value = dm.get_member_value(member_id)
        
        # Get server language style
        use_sassy = uses_sassy_language(server_id)
        
        # Handle zero and low values differently
        if value == 0:
            if use_sassy:
                # Get random response from zero value variants
                from bot import MOMMY_ZERO_VALUE_VARIANTS
                response = random.choice(MOMMY_ZERO_VALUE_VARIANTS)
            else:
                display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
                response = f"{display_name} has not been evaluated yet. Value: ¥0 million."
        elif value < 100:
            if use_sassy:
                # Get random response from low value variants
                from bot import MOMMY_LOW_VALUE_VARIANTS
                response = random.choice(MOMMY_LOW_VALUE_VARIANTS).format(value=value)
            else:
                display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
                response = f"{display_name}'s value: ¥{value} million."
        else:
            if use_sassy:
                # Get random response from standard variants
                from bot import MOMMY_CHECKVALUE_VARIANTS
                response = random.choice(MOMMY_CHECKVALUE_VARIANTS).format(value=value)
            else:
                display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
                response = f"{display_name}'s value: ¥{value} million."
        
        # Get ranking info
        rank, total, top_percent = dm.get_member_ranking(member_id)
        
        # Add ranking information
        ranking_text = format_ranking_message(rank, total, top_percent, use_sassy)
        
        # Create an embed for better presentation
        if use_sassy:
            display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
            embed_title = f"✨ {display_name}'s Value ✨"
            embed_color = discord.Color.purple()
        else:
            display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
            embed_title = f"{display_name}'s Value"
            embed_color = discord.Color.blue()
            
        embed = discord.Embed(
            title=embed_title,
            description=response,
            color=embed_color
        )
        
        # Add ranking field
        embed.add_field(name="Ranking", value=ranking_text, inline=False)
        
        # Add member avatar
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Send the response
        await interaction.response.send_message(embed=embed)
        
        # Log the command
        logger.info(f"Checked value for {member.id} (value: {value}) in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova value: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )


@novera_group.command(name="activity", description="Check your activity or the activity of another member")
@app_commands.describe(member="The member whose activity you want to check")
async def activity_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    """Check your activity or the activity of another member"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("activity", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return
        
        # Use requester if no member is specified
        if not member:
            member = interaction.user
        
        # Get activity data
        member_id = str(member.id)
        activity = dm.get_activity(member_id)
        
        # Calculate activity score
        message_count = activity.get('messages', 0)
        reaction_count = activity.get('reactions', 0)
        activity_score = message_count + (reaction_count // 2)
        
        # Get server language style
        use_sassy = uses_sassy_language(server_id)
        
        # Create response based on server style
        if use_sassy:
            from bot import MOMMY_ACTIVITY_VARIANTS
            response = random.choice(MOMMY_ACTIVITY_VARIANTS).format(activity=activity_score)
            display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
            embed_title = f"🌟 {display_name}'s Activity 🌟"
            embed_color = discord.Color.gold()
        else:
            display_name = member.display_name if member and hasattr(member, 'display_name') else "This user"
            response = f"{display_name}'s activity score: {activity_score}"
            embed_title = f"{display_name}'s Activity"
            embed_color = discord.Color.blue()
        
        # Create an embed for better presentation
        embed = discord.Embed(
            title=embed_title,
            description=response,
            color=embed_color
        )
        
        # Add activity details
        embed.add_field(name="Messages", value=str(message_count), inline=True)
        embed.add_field(name="Reactions", value=str(reaction_count), inline=True)
        embed.add_field(name="Total Score", value=str(activity_score), inline=True)
        
        # Add member avatar
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Send the response
        await interaction.response.send_message(embed=embed)
        
        # Log the command
        logger.info(f"Checked activity for {member.id} (score: {activity_score}) in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova activity: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )


@novera_group.command(name="help", description="Get help on how to use the bot")
async def help_cmd(interaction: discord.Interaction):
    """Display help information for the bot"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # Get server language style
        use_sassy = uses_sassy_language(server_id)
        
        # Basic commands that work in all servers
        basic_commands = [
            "`/nova value [@member]` - Check your value or another member's value",
            "`/nova activity [@member]` - See activity statistics",
            "`/nova help` - Get help with commands"
        ]
        
        # BLR server-specific commands
        blr_commands = []
        if server_id == "1345538548027232307":
            blr_commands = [
                "`/nova request-evaluation` - Request to have your skills evaluated (for new players)",
                "`/nova rankings` - See the top ranked players"
            ]
        
        # Create main embed based on server style
        if use_sassy:
            embed_title = "💖 Mommy's Command List 💖"
            embed_description = "Hello, my sweet Novarian! Here are all the ways you can interact with me!"
            embed_color = discord.Color.purple()
        else:
            embed_title = "Novera Bot Commands"
            embed_description = "Here are the available commands for this server:"
            embed_color = discord.Color.blue()
        
        embed = discord.Embed(
            title=embed_title,
            description=embed_description,
            color=embed_color
        )
        
        # Add basic commands
        embed.add_field(
            name="Basic Commands", 
            value="\n".join(basic_commands),
            inline=False
        )
        
        # Add server-specific commands if any
        if blr_commands:
            embed.add_field(
                name="Server-Specific Commands", 
                value="\n".join(blr_commands),
                inline=False
            )
        
        # Add footer
        if use_sassy:
            embed.set_footer(text="Remember, darling - Mommy is always here to help you shine! 💖")
        else:
            embed.set_footer(text="For more detailed help, contact a server administrator.")
        
        # Send the response
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error in slash command /nova help: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )


@novera_group.command(name="request-evaluation", description="Request to have your skills evaluated (BLR server only)")
async def request_evaluation_cmd(interaction: discord.Interaction):
    """Request to have your skills evaluated (BLR server only)"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # This command is only for the BLR server
        if server_id != "1345538548027232307":
            await interaction.response.send_message(
                "This command is only available on the BLR: NoVera E-Sports League server.",
                ephemeral=True
            )
            return
        
        # Get server language style
        use_sassy = uses_sassy_language(server_id)
        
        # Run the same functionality as the !getevaluated command
        # Get player's current value
        current_value = dm.get_member_value(str(interaction.user.id))
        
        # Only players with value=0 can use this command
        if current_value > 0:
            if use_sassy:
                await interaction.response.send_message(
                    f"Oh darling, you already have a value of ¥{current_value} million! You don't need another evaluation! 💅",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"You already have a value of ¥{current_value} million. No additional evaluation is needed.",
                    ephemeral=True
                )
            return
        
        # Create evaluation request button view
        from bot import EvaluationRequestButton
        view = EvaluationRequestButton(interaction.user.id)
        
        # Send message based on server language style
        if use_sassy:
            await interaction.response.send_message(
                "💖 **Want to be evaluated, my precious?** 💖\n\n"
                "Mommy's evaluation system will assess your skills and determine your value!\n"
                "Click the button below to request an evaluation from our team. An evaluator will be with you soon!\n\n"
                "Remember, darling - only players who have not been evaluated yet can use this feature.",
                view=view
            )
        else:
            await interaction.response.send_message(
                "**Player Evaluation Request**\n\n"
                "The evaluation system will assess your skills and determine your market value.\n"
                "Click the button below to request an evaluation from our team. An evaluator will review your request soon.\n\n"
                "Note: This feature is only available for players who have not yet been evaluated.",
                view=view
            )
        
        logger.info(f"Evaluation button created for player {interaction.user.id} in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova request-evaluation: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.response.send_message(
                random.choice(MOMMY_ERROR_VARIANTS),
                ephemeral=True
            )
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"Error processing your request. {error_msg}",
                ephemeral=True
            )


@novera_group.command(name="rankings", description="View the top player rankings")
async def rankings_cmd(interaction: discord.Interaction):
    """View the top player rankings"""
    try:
        # Get server-specific configuration
        server_id = str(interaction.guild.id)
        
        # If command is disabled for this server, return
        if is_command_disabled("rankings", server_id):
            error_msg = get_message_style("error", server_id)
            await interaction.response.send_message(
                f"This command is not available on this server. {error_msg}", 
                ephemeral=True
            )
            return

        # Defer the response since this might take a moment
        await interaction.response.defer()
            
        # The rankings command implementation
        from server_config import get_server_name
        server_name = get_server_name(server_id) or "Novera"
        
        # Get all values
        all_values = dm.get_all_member_values()
        if not all_values:
            await interaction.followup.send("No player values found yet!")
            return
            
        # Sort by value
        sorted_by_value = sorted(all_values.items(), key=lambda x: x[1], reverse=True)
        
        # Get top 3 for this server
        top_three = []
        members_in_server = 0
        
        # Filter for members in this server only
        for member_id, value in sorted_by_value:
            # Check if this member is in this server
            member = interaction.guild.get_member(int(member_id))
            if member:
                top_three.append((member_id, value))
                members_in_server += 1
                # Only need top 3
                if len(top_three) >= 3:
                    break
        
        if not top_three:
            await interaction.followup.send(f"No valued members found in this server!")
            return
            
        # Get growth data for trending player
        growth_data = dm.get_value_growth_3days()
        trending_member_id = None
        
        # Filter growth data for members in this server
        if growth_data:
            filtered_growth = {mid: val for mid, val in growth_data.items() if interaction.guild.get_member(int(mid))}
            if filtered_growth:
                trending_member_id, _ = max(filtered_growth.items(), key=lambda x: x[1])
            
        # If no trending member found, use top player
        if not trending_member_id and top_three:
            trending_member_id = top_three[0][0]
            
        # Create server-specific embed style
        use_sassy = uses_sassy_language(server_id)
        if use_sassy:
            embed_title = f"🏆 {server_name} Rankings"
            embed_description = f"Here are the top players in {server_name} according to Mommy's records!"
            embed_color = discord.Color.gold()
        else:
            embed_title = f"{server_name} Player Rankings"
            embed_description = f"Top players in {server_name} by market value:"
            embed_color = discord.Color.blue()
            
        embed = discord.Embed(
            title=embed_title,
            description=embed_description,
            color=embed_color
        )
        
        # Add rankings
        rank_emojis = ["🥇", "🥈", "🥉"]
        for i, (member_id, value) in enumerate(top_three):
            member_obj = interaction.guild.get_member(int(member_id))
            if member_obj:
                embed.add_field(name=f"{rank_emojis[i]} Rank {i+1}", value=f"{member_obj.mention} – ¥{value} million", inline=False)
                
        # Add trending player if found
        if trending_member_id:
            trending_member = interaction.guild.get_member(int(trending_member_id))
            if trending_member:
                embed.set_footer(text=f"🌟 Trending: {trending_member.display_name}")
                
        # Send the response
        await interaction.followup.send(embed=embed)
        logger.info(f"Displayed rankings in server {server_id} with {members_in_server} members")
        
    except Exception as e:
        logger.error(f"Error in slash command /nova rankings: {e}", exc_info=True)
        
        # Use server-specific error style
        server_id = str(interaction.guild.id)
        if uses_sassy_language(server_id):
            from bot import MOMMY_ERROR_VARIANTS
            await interaction.followup.send(random.choice(MOMMY_ERROR_VARIANTS))
        else:
            error_msg = get_message_style("error", server_id)
            await interaction.followup.send(f"Error processing your request. {error_msg}")


# =============================
# ADMIN GROUP COMMANDS
# =============================

@admin_group.command(name="sync", description="Sync slash commands with Discord")
async def sync_cmd(interaction: discord.Interaction):
    """Sync slash commands with Discord (admin only)"""
    try:
        # Check if the user has management permissions
        if not has_value_management_role(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        # Defer the response since syncing can take time
        await interaction.response.defer(ephemeral=True)
        
        # Get the bot from the client
        bot = interaction.client
        
        # Sync commands globally
        await bot.tree.sync()
        
        # Respond with success
        await interaction.followup.send(
            "Slash commands have been synced globally! They should appear in the slash command menu within a few minutes.",
            ephemeral=True
        )
        
        logger.info(f"Slash commands synced by {interaction.user.id}")
        
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}", exc_info=True)
        await interaction.followup.send(
            f"Error syncing commands: {str(e)}",
            ephemeral=True
        )


@admin_group.command(name="set-value", description="Set a member's value (admin only)")
@app_commands.describe(
    member="The member whose value you want to set",
    amount="The value amount in millions"
)
async def set_value_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    """Set a member's value (admin only)"""
    try:
        # Check if the user has management permissions
        if not has_value_management_role(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        # Make sure amount is positive
        if amount < 0:
            await interaction.response.send_message(
                "Value must be a positive number.",
                ephemeral=True
            )
            return
            
        # Set the value
        member_id = str(member.id)
        dm.set_member_value(member_id, amount)
        
        # Get server-specific style
        server_id = str(interaction.guild.id)
        use_sassy = uses_sassy_language(server_id)
        
        # Create response message
        if use_sassy:
            response = f"💖 {member.mention}'s value has been set to ¥{amount} million, darling! So fancy! ✨"
        else:
            response = f"{member.mention}'s value has been set to ¥{amount} million."
            
        # Send the response
        await interaction.response.send_message(response)
        
        logger.info(f"User {interaction.user.id} set value for {member.id} to {amount}")
        
    except Exception as e:
        logger.error(f"Error in admin set-value command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"Error setting value: {str(e)}",
            ephemeral=True
        )


@admin_group.command(name="evaluate", description="Evaluate a player (admin only)")
@app_commands.describe(member="The member to evaluate")
async def evaluate_cmd(interaction: discord.Interaction, member: discord.Member):
    """Start an evaluation for a player (admin only)"""
    try:
        # Check if the user has management permissions
        if not has_value_management_role(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        # Get server ID
        server_id = str(interaction.guild.id)
            
        # Defer the response
        await interaction.response.defer(ephemeral=True)
        
        # Get the eval function from the bot
        from bot import tryoutsresults_cmd
        
        # Execute the original function
        # This is just a trigger - the function will handle sending its own messages
        await tryoutsresults_cmd(await interaction.client.get_context(interaction.message), member)
        
        # Send a confirmation to the admin
        await interaction.followup.send(
            f"Started evaluation process for {member.mention}. Check your DMs to complete the evaluation.",
            ephemeral=True
        )
        
        logger.info(f"User {interaction.user.id} started evaluation for {member.id} in server {server_id}")
        
    except Exception as e:
        logger.error(f"Error in admin evaluate command: {e}", exc_info=True)
        await interaction.followup.send(
            f"Error starting evaluation: {str(e)}",
            ephemeral=True
        )