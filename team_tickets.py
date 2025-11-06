"""
Team Tickets System for Novera Discord Bot
This module handles team creation requests through an interactive button system.
"""
import discord
from discord.ext import commands
import logging
import asyncio
import os
from datetime import datetime
import json

# Owner ID for DM notifications
OWNER_ID = 654338875736588288
# Target channel ID for the ticket system
TICKET_CHANNEL_ID = 1350177702778245172

class TeamModal(discord.ui.Modal):
    """Modal for team creation details with player position information"""
    def __init__(self, team_type="regular"):
        # Add unique custom_id to the modal based on type and timestamp
        # Use milliseconds for more unique identifiers
        timestamp = int(datetime.now().timestamp() * 1000)
        modal_id = f"team_modal_{team_type}_{timestamp}"
        
        super().__init__(
            title="Team Creation" if team_type == "regular" else "Tournament Registration",
            custom_id=modal_id
        )
        
        self.team_type = team_type
        self.timestamp = timestamp
        
        # Add the team name input field with unique ID
        self.team_name_input = discord.ui.TextInput(
            label="Team Name",
            placeholder="Enter your team name",
            required=True,
            max_length=50,
            style=discord.TextStyle.short,
            custom_id=f"team_name_{timestamp}"
        )
        self.add_item(self.team_name_input)
        
        # Different fields based on team type
        if team_type == "regular":
            # Add fields for regular team creation with player positions
            self.cf_player = discord.ui.TextInput(
                label="CF Player",
                placeholder="Enter the name of your Center Forward player",
                required=True,
                max_length=100,
                style=discord.TextStyle.short,
                custom_id=f"cf_player_{timestamp}"
            )
            self.add_item(self.cf_player)
            
            self.wings_players = discord.ui.TextInput(
                label="LW/RW Players",
                placeholder="Enter the names of your Left and Right Wingers",
                required=True,
                max_length=100,
                style=discord.TextStyle.short,
                custom_id=f"wings_players_{timestamp}"
            )
            self.add_item(self.wings_players)
            
            self.cm_player = discord.ui.TextInput(
                label="CM Player",
                placeholder="Enter the name of your Center Midfielder",
                required=True,
                max_length=100,
                style=discord.TextStyle.short,
                custom_id=f"cm_player_{timestamp}"
            )
            self.add_item(self.cm_player)
            
            self.gk_player = discord.ui.TextInput(
                label="GK Player",
                placeholder="Enter the name of your Goalkeeper",
                required=True,
                max_length=100,
                style=discord.TextStyle.short,
                custom_id=f"gk_player_{timestamp}"
            )
            self.add_item(self.gk_player)
        else:
            # For 3v3 tournament registration, ask for player names
            self.player_names = discord.ui.TextInput(
                label="Player Names (Must have 3)",
                placeholder="Enter the names of all 3 players participating in the tournament",
                required=True,
                max_length=200,
                style=discord.TextStyle.paragraph,
                custom_id=f"player_names_{timestamp}"
            )
            self.add_item(self.player_names)
    
    # In Discord.py 2.5.2, we need to implement on_submit instead of callback
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission with robust error handling for Discord.py 2.5.2"""
        logging.info(f"Modal submission received from user {interaction.user.name} (ID: {interaction.user.id})")
        try:
            # Extract the input values
            team_name = self.team_name_input.value
            
            # Make sure we have a reference to active_team_creations
            global active_team_creations
            if 'active_team_creations' not in globals():
                active_team_creations = {}
            
            # Make detailed logging of the process
            logging.info(f"Processing team modal submission - Type: {self.team_type}, User: {interaction.user.name} (ID: {interaction.user.id})")
            
            if self.team_type == "regular":
                # Extract player position data
                cf_player = self.cf_player.value
                wings_players = self.wings_players.value
                cm_player = self.cm_player.value
                gk_player = self.gk_player.value
                
                # Log what we're doing
                logging.info(f"Regular team creation - Name: '{team_name}', Players: CF={cf_player}, Wings={wings_players}, CM={cm_player}, GK={gk_player}")
                
                try:
                    # First, send response confirming receipt
                    await interaction.response.send_message(
                        f"✅ Thanks for your team information! Your team **{team_name}** has been created with the following players:\n"
                        f"• **CF**: {cf_player}\n"
                        f"• **LW/RW**: {wings_players}\n"
                        f"• **CM**: {cm_player}\n"
                        f"• **GK**: {gk_player}\n\n"
                        "Please contact Novera to get your team logo setup.",
                        ephemeral=True
                    )
                    
                    # Store team data
                    active_team_creations[interaction.user.id] = {
                        "type": "regular",
                        "step": "complete",  # Mark as complete, no logo upload needed
                        "data": {
                            "name": team_name,
                            "cf_player": cf_player,
                            "wings_players": wings_players,
                            "cm_player": cm_player,
                            "gk_player": gk_player
                        },
                        "timestamp": datetime.now().timestamp()
                    }
                    
                    # Get the bot instance
                    bot = interaction.client
                    
                    # Notify owner
                    try:
                        await send_team_request_to_owner(bot, interaction.user.id, active_team_creations[interaction.user.id])
                        logging.info(f"Owner notified about team creation for team '{team_name}'")
                        # Remove from active creations after notification
                        del active_team_creations[interaction.user.id]
                    except Exception as e:
                        logging.error(f"Failed to notify owner about team creation: {e}")
                    
                    logging.info(f"Completed team creation process for user ID {interaction.user.id}, name: {team_name}")
                except discord.errors.InteractionResponded:
                    # If we already responded (somehow), use followup
                    logging.warning(f"Interaction already responded, using followup for user {interaction.user.id}")
                    await interaction.followup.send(
                        f"✅ Thanks for your team information! Your team **{team_name}** has been created with the following players:\n"
                        f"• **CF**: {cf_player}\n"
                        f"• **LW/RW**: {wings_players}\n"
                        f"• **CM**: {cm_player}\n"
                        f"• **GK**: {gk_player}\n\n"
                        "Please contact Novera to get your team logo setup.",
                        ephemeral=True
                    )
                except Exception as response_error:
                    logging.error(f"Error responding to team modal: {response_error}")
                    # If all fails, at least store the team data
                    active_team_creations[interaction.user.id] = {
                        "type": "regular",
                        "step": "complete",
                        "data": {
                            "name": team_name,
                            "cf_player": cf_player,
                            "wings_players": wings_players,
                            "cm_player": cm_player,
                            "gk_player": gk_player
                        },
                        "timestamp": datetime.now().timestamp()
                    }
                
            else:  # Tournament registration
                # Get player names for tournament
                player_names = self.player_names.value
                
                # Verify we have 3 players for 3v3 tournament
                players_list = [p.strip() for p in player_names.split("\n") if p.strip()]
                player_count = len(players_list)
                
                logging.info(f"Tournament team registration - Name: '{team_name}', Players: {player_names}")
                
                # Check if we have exactly 3 players
                if player_count != 3:
                    await interaction.response.send_message(
                        f"⚠️ Your tournament team needs exactly 3 players. You provided {player_count}.\n"
                        "Please try again and enter exactly 3 player names.",
                        ephemeral=True
                    )
                    return
                
                try:
                    # First, try to respond to the interaction
                    await interaction.response.send_message(
                        f"✅ Your 3v3 tournament team **{team_name}** has been registered successfully with players:\n"
                        f"• **Player 1**: {players_list[0]}\n"
                        f"• **Player 2**: {players_list[1]}\n"
                        f"• **Player 3**: {players_list[2]}",
                        ephemeral=True
                    )
                    
                    # Store in active creations briefly to use existing owner notification
                    active_team_creations[interaction.user.id] = {
                        "type": "tournament",
                        "step": "complete",
                        "data": {
                            "name": team_name,
                            "players": players_list
                        },
                        "timestamp": datetime.now().timestamp()
                    }
                    
                    # Get the bot instance
                    bot = interaction.client
                    
                    # Notify owner
                    try:
                        await send_team_request_to_owner(bot, interaction.user.id, active_team_creations[interaction.user.id])
                        logging.info(f"Owner notified about tournament registration for team '{team_name}'")
                    except Exception as e:
                        logging.error(f"Failed to notify owner about tournament registration: {e}")
                    
                    # Remove from active creations
                    del active_team_creations[interaction.user.id]
                    
                except discord.errors.InteractionResponded:
                    # If already responded, use followup
                    logging.warning(f"Interaction already responded, using followup for tournament registration")
                    await interaction.followup.send(
                        f"✅ Your 3v3 tournament team **{team_name}** has been registered successfully with players:\n"
                        f"• **Player 1**: {players_list[0]}\n"
                        f"• **Player 2**: {players_list[1]}\n"
                        f"• **Player 3**: {players_list[2]}",
                        ephemeral=True
                    )
                except Exception as response_error:
                    logging.error(f"Error responding to tournament modal: {response_error}")
                
        except Exception as e:
            logging.error(f"Error in team modal on_submit: {e}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "There was an error processing your information. Please try again later.",
                    ephemeral=True
                )
            except:
                try:
                    await interaction.followup.send(
                        "There was an error processing your information. Please try again later.",
                        ephemeral=True
                    )
                except:
                    logging.error(f"Failed to send any error message to user {interaction.user.id}")
                    pass
    
    # Keep the old callback for backward compatibility and debugging purposes
    async def callback(self, interaction: discord.Interaction):
        """Deprecated callback method - redirecting to on_submit"""
        logging.info(f"Deprecated callback method called, redirecting to on_submit for user {interaction.user.name}")
        await self.on_submit(interaction)

class TeamRequestView(discord.ui.View):
    """Interactive view for team request buttons"""
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view that doesn't timeout
    
    @discord.ui.button(label="Create Team", style=discord.ButtonStyle.primary, custom_id="create_team", emoji="🏆")
    async def create_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle create team button by showing modal"""
        try:
            # Log the interaction attempt
            logging.info(f"Create Team button clicked by {interaction.user.name} (ID: {interaction.user.id})")
            
            # Create and send the modal with a unique timestamp-based ID
            modal = TeamModal(team_type="regular")
            
            # Extended error handling with more diagnostic info
            try:
                await interaction.response.send_modal(modal)
                logging.info(f"Successfully sent team creation modal to {interaction.user.name}")
            except discord.errors.NotFound as nf_error:
                logging.error(f"Interaction not found error: {nf_error} - User: {interaction.user.name}")
                try:
                    # Try to send a followup if response is already done
                    await interaction.followup.send(
                        "The interaction expired. Please try clicking the button again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after NotFound error")
            except discord.errors.InteractionResponded as ir_error:
                logging.error(f"Interaction already responded error: {ir_error} - User: {interaction.user.name}")
                try:
                    await interaction.followup.send(
                        "There was an error processing your request. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after InteractionResponded error")
        except Exception as e:
            logging.error(f"Error showing team creation modal: {e}")
            # Try multiple approaches to respond to the interaction
            try:
                # First attempt - standard response
                await interaction.response.send_message(
                    "There was an error starting the team creation process. Please try again later.",
                    ephemeral=True
                )
            except discord.errors.NotFound:
                logging.error("Interaction not found, trying followup")
                try:
                    # Second attempt - followup
                    await interaction.followup.send(
                        "There was an error. Please try again later.",
                        ephemeral=True
                    )
                except:
                    logging.error("All attempts to respond to the interaction failed")
    
    @discord.ui.button(label="Join 3v3 Tournament", style=discord.ButtonStyle.success, custom_id="join_tournament", emoji="🎮")
    async def join_tournament_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle tournament registration button by showing modal"""
        try:
            # Log the interaction attempt
            logging.info(f"Tournament registration button clicked by {interaction.user.name} (ID: {interaction.user.id})")
            
            # Create and send the modal with a unique timestamp-based ID
            modal = TeamModal(team_type="tournament")
            
            # Extended error handling with more diagnostic info
            try:
                await interaction.response.send_modal(modal)
                logging.info(f"Successfully sent tournament registration modal to {interaction.user.name}")
            except discord.errors.NotFound as nf_error:
                logging.error(f"Interaction not found error: {nf_error} - User: {interaction.user.name}")
                try:
                    # Try to send a followup if response is already done
                    await interaction.followup.send(
                        "The interaction expired. Please try clicking the button again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after NotFound error")
            except discord.errors.InteractionResponded as ir_error:
                logging.error(f"Interaction already responded error: {ir_error} - User: {interaction.user.name}")
                try:
                    await interaction.followup.send(
                        "There was an error processing your request. Please try again.",
                        ephemeral=True
                    )
                except:
                    logging.error("Failed to send followup message after InteractionResponded error")
        except Exception as e:
            logging.error(f"Error showing tournament registration modal: {e}")
            # Try multiple approaches to respond to the interaction
            try:
                # First attempt - standard response
                await interaction.response.send_message(
                    "There was an error starting the tournament registration. Please try again later.",
                    ephemeral=True
                )
            except discord.errors.NotFound:
                logging.error("Interaction not found, trying followup")
                try:
                    # Second attempt - followup
                    await interaction.followup.send(
                        "There was an error. Please try again later.",
                        ephemeral=True
                    )
                except:
                    logging.error("All attempts to respond to the interaction failed")

def create_team_embed(team_type):
    """Create an embed for team creation or tournament registration"""
    if team_type == "regular":
        embed = discord.Embed(
            title="🏆 Team Creation Request",
            description="You've successfully created a team request! Your request has been sent to Novera.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Next Steps",
            value="Novera will review your team request and contact you to set up your team logo and finalize the team creation process.",
            inline=False
        )
        embed.set_footer(text="Thank you for using the team creation system!")
    else:
        embed = discord.Embed(
            title="🎮 3v3 Tournament Team Registration",
            description="You've successfully registered for the 3v3 tournament! Your request has been sent to Novera.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Next Steps",
            value="Novera will review your tournament registration and contact you with further details about the tournament.",
            inline=False
        )
        embed.set_footer(text="Thank you for registering for the tournament!")
    
    return embed

# Dictionary to track active team creation processes
active_team_creations = {}

async def start_team_creation_process(user_id, team_type, dm_channel):
    """Start the team creation process and track it"""
    active_team_creations[user_id] = {
        "type": team_type,
        "step": "name",
        "data": {},
        "timestamp": datetime.now().timestamp()
    }
    
    logging.info(f"Started team creation process for user ID {user_id}, type: {team_type}")

async def process_team_creation_message(message, bot):
    """Process messages for ongoing team creations"""
    try:
        # Only process DM messages
        if not isinstance(message.channel, discord.DMChannel):
            return False
        
        user_id = message.author.id
        logging.info(f"Processing potential team creation message from user ID: {user_id}")
        
        # Check if this user has an ongoing team creation
        if user_id not in active_team_creations:
            return False
        
        logging.info(f"Found active team creation for user ID {user_id}")
        
        # Get the team creation state
        state = active_team_creations[user_id]
        
        # Check for cancellation
        if message.content.lower() == "cancel":
            del active_team_creations[user_id]
            await message.channel.send(embed=discord.Embed(
                title="❌ Request Cancelled",
                description="Your team creation request has been cancelled.",
                color=discord.Color.red()
            ))
            logging.info(f"User ID {user_id} cancelled team creation")
            return True
    except Exception as e:
        logging.error(f"Error in initial team creation message processing: {e}")
        # Send error message to user
        try:
            await message.channel.send("There was an error processing your request. Please try again or contact an admin.")
        except:
            pass
        return True
    
    # Process based on the current step
    if state["step"] == "name":
        try:
            # Validate team name (not empty, not too long)
            if not message.content or len(message.content) > 50:
                await message.channel.send("Please provide a valid team name (between 1-50 characters).")
                return True
            
            # Store the team name
            state["data"]["name"] = message.content
            logging.info(f"Stored team name '{message.content}' for user {user_id}")
            
            # Move to the next step based on team type
            if state["type"] == "regular":
                state["step"] = "logo"
                await message.channel.send(embed=discord.Embed(
                    title="✅ Team Name Received",
                    description=f"Great! Your team name will be: **{message.content}**\n\nNow, please upload a team logo image.",
                    color=discord.Color.blue()
                ))
            else:
                # For tournament teams, we're done after the name
                state["step"] = "complete"
                team_data = state["data"]
                
                # Send completion message
                await message.channel.send(embed=discord.Embed(
                    title="✅ Tournament Team Registration Complete",
                    description=f"Thank you! Your 3v3 tournament team **{team_data['name']}** has been submitted for approval.",
                    color=discord.Color.green()
                ))
                
                try:
                    # Notify the owner
                    await send_team_request_to_owner(bot, user_id, state)
                except Exception as e:
                    logging.error(f"Failed to notify owner, but team still created: {e}")
                
                # Remove from active creations
                del active_team_creations[user_id]
                
            return True
        except Exception as e:
            logging.error(f"Error processing team name: {e}")
            try:
                await message.channel.send("There was an error processing your team name. Please try again or contact an admin.")
            except:
                pass
            return True
    
    elif state["step"] == "logo":
        try:
            # Check if a file was attached
            if not message.attachments:
                await message.channel.send("Please upload an image file for your team logo. Type 'cancel' to cancel.")
                return True
            
            # Check if the attachment is an image
            attachment = message.attachments[0]
            logging.info(f"Received attachment: {attachment.filename} ({attachment.content_type}) from user {user_id}")
            
            # Verify it's an image with proper error handling
            if not attachment.content_type or not attachment.content_type.startswith('image/'):
                await message.channel.send("That doesn't appear to be an image file. Please upload a valid image for your team logo (JPG, PNG, GIF).")
                return True
            
            # Store logo URL
            state["data"]["logo_url"] = attachment.url
            state["step"] = "complete"
            logging.info(f"Stored team logo URL for user {user_id}: {attachment.url}")
            
            # Send completion message with robust error handling
            team_data = state["data"]
            try:
                completion_embed = discord.Embed(
                    title="✅ Team Creation Request Complete",
                    description=f"Thank you! Your team **{team_data['name']}** has been submitted for approval with the provided logo.",
                    color=discord.Color.green()
                )
                
                # Only set thumbnail if URL exists with multiple checks
                if attachment and hasattr(attachment, 'url') and attachment.url:
                    try:
                        completion_embed.set_thumbnail(url=attachment.url)
                    except Exception as thumbnail_err:
                        logging.error(f"Error setting thumbnail: {thumbnail_err}")
                
                await message.channel.send(embed=completion_embed)
            except Exception as e:
                logging.error(f"Error sending completion message: {e}")
                # Fallback plain message if embed fails
                try:
                    await message.channel.send(f"✅ Your team **{team_data['name']}** has been submitted for approval with the provided logo!")
                except Exception as msg_err:
                    logging.error(f"Even fallback message failed: {msg_err}")
            
            # Notify the owner with robust error catching
            owner_notified = False
            try:
                await send_team_request_to_owner(bot, user_id, state)
                owner_notified = True
            except Exception as e:
                logging.error(f"Failed to notify owner but team is still created: {e}")
                try:
                    # Second attempt with simplified data
                    owner = await bot.fetch_user(OWNER_ID)
                    if owner:
                        await owner.send(f"EMERGENCY BACKUP NOTIFICATION: New team created: {team_data['name']} by user ID {user_id}")
                        owner_notified = True
                except Exception as backup_err:
                    logging.error(f"Even backup owner notification failed: {backup_err}")
            
            if owner_notified:
                logging.info(f"Successfully notified owner about team creation for user {user_id}")
            
            # Remove from active creations
            del active_team_creations[user_id]
            return True
        except Exception as e:
            logging.error(f"Error processing team logo: {e}")
            
            try:
                # Send error message to user
                await message.channel.send("There was an error processing your team logo. Please try again or contact an admin.")
                
                # Don't remove from active creations to allow retry
                return True
            except:
                logging.error("Failed to send error message to user")
                return True
    
    return False

async def send_team_request_to_owner(bot, user_id, state):
    """Send the team request notification to the owner"""
    try:
        # Get the owner user
        owner = await bot.fetch_user(OWNER_ID)
        
        # Get the requesting user
        requester = await bot.fetch_user(user_id)
        
        # Create the appropriate embed based on team type
        if state["type"] == "regular":
            embed = discord.Embed(
                title="🏆 New Team Creation Request",
                description=f"User {requester.mention} ({requester.name}) has requested to create a new team!",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Team Name",
                value=state["data"]["name"],
                inline=False
            )
            
            # Add player positions if they exist in data
            if "cf_player" in state["data"]:
                embed.add_field(
                    name="CF Player",
                    value=state["data"]["cf_player"],
                    inline=True
                )
            
            if "wings_players" in state["data"]:
                embed.add_field(
                    name="LW/RW Players",
                    value=state["data"]["wings_players"],
                    inline=True
                )
                
            if "cm_player" in state["data"]:
                embed.add_field(
                    name="CM Player",
                    value=state["data"]["cm_player"],
                    inline=True
                )
                
            if "gk_player" in state["data"]:
                embed.add_field(
                    name="GK Player",
                    value=state["data"]["gk_player"],
                    inline=True
                )
            
            # Add the logo as a thumbnail
            if "logo_url" in state["data"]:
                embed.set_thumbnail(url=state["data"]["logo_url"])
                
            embed.add_field(
                name="Logo Setup",
                value="User has been instructed to contact you for logo setup",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="🎮 New 3v3 Tournament Team Registration",
                description=f"User {requester.mention} ({requester.name}) has registered a team for the 3v3 tournament!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Tournament Team Name",
                value=state["data"]["name"],
                inline=False
            )
            
            # Add player names if they exist in data
            if "players" in state["data"]:
                players = state["data"]["players"]
                if len(players) == 3:
                    embed.add_field(
                        name="Player 1",
                        value=players[0],
                        inline=True
                    )
                    embed.add_field(
                        name="Player 2",
                        value=players[1],
                        inline=True
                    )
                    embed.add_field(
                        name="Player 3",
                        value=players[2],
                        inline=True
                    )
                else:
                    player_list = "\n".join([f"• {p}" for p in players])
                    embed.add_field(
                        name=f"Players ({len(players)})",
                        value=player_list or "No players listed",
                        inline=False
                    )
        
        # Add timestamp and user ID for reference
        embed.add_field(
            name="User ID",
            value=str(user_id),
            inline=True
        )
        
        embed.timestamp = datetime.now()
        
        # DM the owner
        await owner.send(embed=embed)
        
        logging.info(f"Sent team request notification to owner for user ID {user_id}")
    except Exception as e:
        logging.error(f"Error sending team request to owner: {e}")

async def setup_ticket_system(bot):
    """Set up the ticket system in the designated channel"""
    try:
        # Get the ticket channel
        channel = bot.get_channel(TICKET_CHANNEL_ID)
        
        if not channel:
            logging.error(f"Could not find ticket channel with ID {TICKET_CHANNEL_ID}")
            return
        
        # Check if there's an existing ticket message
        async for message in channel.history(limit=50):
            if message.author == bot.user and message.components:
                for component in message.components:
                    for child in component.children:
                        if child.custom_id in ["create_team", "join_tournament"]:
                            logging.info(f"Found existing ticket message with ID {message.id}")
                            return
        
        # Create embed for the ticket system
        embed = discord.Embed(
            title="🏆 Novera Team Creation & Tournament Registration",
            description=(
                "Use the buttons below to create a team or register for the 3v3 tournament.\n\n"
                "**Team Creation**\n"
                "• Create a permanent team with a name and logo\n"
                "• Requires owner approval\n\n"
                "**3v3 Tournament Registration**\n"
                "• Register a team for the upcoming 3v3 tournament\n"
                "• Only requires a team name\n"
                "• Submit registrations before the deadline"
            ),
            color=discord.Color.gold()
        )
        
        # Set a footer with instructions
        embed.set_footer(text="Click a button to begin. You'll receive a DM with further instructions.")
        
        # Add server icon if available
        if channel.guild.icon:
            embed.set_thumbnail(url=channel.guild.icon.url)
        
        # Create and send the ticket message with the view
        await channel.send(embed=embed, view=TeamRequestView())
        logging.info(f"Created new ticket system message in channel {channel.name}")
    
    except Exception as e:
        logging.error(f"Error setting up ticket system: {e}")

def setup(bot):
    """Set up the team tickets module"""
    bot.team_tickets = True  # Mark that team tickets is enabled
    
    # Set up the ticket system
    bot.loop.create_task(setup_ticket_system(bot))
    logging.info("Team tickets module has been set up")