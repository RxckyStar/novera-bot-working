"""Tryout evaluation functionality"""
from typing import Optional, Dict
import asyncio
import discord
from discord.ext import commands
import logging
import sys
from discord_asyncio_fix import safe_wait_for

logger = logging.getLogger(__name__)

# We'll use a global variable that will be populated by bot.py
# This avoids circular imports
active_tryouts = {}

def set_active_tryouts(tryouts_dict):
    """Set the active tryouts dictionary from outside this module"""
    global active_tryouts
    active_tryouts = tryouts_dict
    logger.info("Active tryouts dictionary has been set externally")

# Note: calculate_value function is now defined in bot.py to avoid circular imports
# The following is the reference implementation for documentation purposes only
"""
def calculate_value(ratings: Dict[str, Optional[int]], is_goalkeeper: bool) -> int:
    # Calculate player value based on ratings
    # For implementation, see bot.py
    pass
"""

async def process_player_evaluation(channel, evaluator_id: int, bot) -> Optional[Dict]:
    """Process a single player evaluation"""
    try:
        def check(m):
            return m.author.id == evaluator_id and m.channel == channel

        # Get player position
        await channel.send(
            "**📊 Player Position**\n\n"
            "> Type `1` for GK (Goalkeeper)\n"
            "> Type `2` for CM (Central Midfielder)\n"
            "> Type `3` for LW/RW (Winger)\n"
            "> Type `4` for CF (Center Forward)"
        )

        msg = await safe_wait_for(bot.wait_for('message', check=check), 300.0)
        position = msg.content
        
        # Determine position type
        is_goalkeeper = position == "1"
        is_cm = position == "2"
        is_winger = position == "3"
        is_forward = position == "4"
        
        # Store position for later use
        position_name = {
            "1": "GK (Goalkeeper)",
            "2": "CM (Central Midfielder)",
            "3": "LW/RW (Winger)",
            "4": "CF (Center Forward)"
        }.get(position, "Unknown")
        
        logger.info(f"Received position response: {position}, position: {position_name}")

        # Clear transition to skill ratings
        await asyncio.sleep(1)  # Brief pause for readability
        await channel.send(
            "**🎯 Player Skills Evaluation**\n\n"
            "Let's rate their skills on a scale from 0 to 10!\n"
            "For each skill, please enter a number between 0 and 10."
        )
        logger.info("Starting skill ratings evaluation")

        # Get skill ratings
        skills = {
            'shooting': '⚽ Rate their shooting ability (0-10):',
            'dribbling': '👟 Rate their dribbling ability (0-10):',
            'passing': '🎯 Rate their passing ability (0-10):',
            'defense': '🛡️ Rate their defensive ability (0-10):',
            'goalkeeping': '🧤 Rate their goalkeeping ability (0-10) or type "skip":'
        }

        ratings = {}
        for skill, prompt in skills.items():
            await channel.send(f"**{prompt}**")
            logger.info(f"Sending prompt for {skill} rating")

            while True:
                msg = await safe_wait_for(bot.wait_for('message', check=check), 300.0)
                logger.info(f"Received response for {skill}: {msg.content}")

                if skill == "goalkeeping" and msg.content.lower() == "skip":
                    ratings[skill] = None
                    logger.info("Goalkeeping rating skipped")
                    break

                try:
                    rating = int(msg.content)
                    if 0 <= rating <= 10:
                        ratings[skill] = rating
                        logger.info(f"Received valid {skill} rating: {rating}")
                        break
                    await channel.send("❌ Please enter a number between 0 and 10!")
                except ValueError:
                    await channel.send("❌ Please enter a valid number!")

        # Get feedback
        await channel.send(
            "**📝 Final Feedback**\n\n"
            "Please provide your detailed feedback about the player's performance.\n"
            "Type your feedback message:"
        )
        logger.info("Waiting for feedback...")

        msg = await safe_wait_for(bot.wait_for('message', check=check), 300.0)
        feedback = msg.content

        logger.info("Completed player evaluation")
        return {
            "ratings": ratings,
            "feedback": feedback,
            "is_goalkeeper": is_goalkeeper,
            "position": position,
            "position_name": position_name,
            "is_cm": is_cm,
            "is_winger": is_winger,
            "is_forward": is_forward
        }

    except asyncio.TimeoutError:
        logger.warning(f"Evaluation timed out for evaluator {evaluator_id}")
        await channel.send("❌ You took too long to respond. Please start over with !tryout @player")
        return None
    except Exception as e:
        logger.error(f"Error in process_player_evaluation: {e}", exc_info=True)
        await channel.send("An error occurred during the evaluation. Please try again.")
        return None

async def start_tryout_evaluation(ctx, player: discord.Member):
    """Start the tryout evaluation process"""
    try:
        logger.info(f"[TRYOUTS] Started evaluation for {ctx.author}, evaluating {player}")

        # Create DM channel with evaluator
        try:
            dm_channel = await ctx.author.create_dm()
            logger.info(f"[TRYOUTS] Successfully created DM channel for {ctx.author}")
        except discord.Forbidden:
            logger.error(f"[TRYOUTS] Could not create DM channel for {ctx.author} - DMs might be disabled")
            await ctx.send("❌ I couldn't send you a DM! Please enable DMs from server members and try again.")
            return
        except Exception as e:
            logger.error(f"[TRYOUTS] Error creating DM channel: {e}", exc_info=True)
            await ctx.send("An error occurred while starting the evaluation. Please try again.")
            return

        # Send notification to the player being evaluated
        try:
            player_dm = await player.create_dm()
            await player_dm.send(
                "🎮 **Welcome to Novera Tryouts!**\n"
                f"{ctx.author.mention} is evaluating your skills.\n"
                "Stay tuned - your results will be posted soon in the 📋-tryout-results channel! 🌟"
            )
            logger.info(f"[TRYOUTS] Sent notification to tryout player {player}")
        except discord.Forbidden:
            logger.warning(f"[TRYOUTS] Could not send DM to tryout player {player}")
            # Continue anyway since this is not critical

        # Initialize tryout state
        active_tryouts[ctx.author.id] = {"member": player, "evaluation": None}
        logger.info(f"[TRYOUTS] Initialized tryout state for {ctx.author}")

        # Start evaluation process
        await ctx.send("📩 Check your DMs to start the player evaluation!")
        await dm_channel.send(
            f"Welcome to the Novera Tryouts Evaluation System! 📋\n"
            f"Let's evaluate {player.name}'s skills.\n\n"
        )

        # Process evaluation
        evaluation = await process_player_evaluation(dm_channel, ctx.author.id, ctx.bot)
        if evaluation:
            try:
                # Find tryouts results channel
                tryouts_channel = discord.utils.get(ctx.guild.text_channels, name='📋-tryout-results')
                if not tryouts_channel:
                    logger.error("[TRYOUTS] Could not find 📋-tryout-results channel")
                    await ctx.send("❌ Couldn't find the tryout results channel!")
                    return

                # Calculate value based on player position and ratings
                def calculate_player_value(ratings, position_data):
                    """Calculate player value based on position and ratings"""
                    # Get position flags
                    is_goalkeeper = position_data["is_goalkeeper"]
                    is_cm = position_data["is_cm"]
                    is_winger = position_data["is_winger"]
                    is_forward = position_data["is_forward"]
                    
                    # Define weights based on position
                    if is_goalkeeper:
                        # GK - Goalkeeping is extremely important, passing secondary
                        weights = {
                            'goalkeeping': 6.0,  # Extremely important
                            'passing': 1.0,      # Secondary importance
                            'shooting': 0.1,     # Almost irrelevant
                            'dribbling': 0.1,    # Almost irrelevant
                            'defense': 0.3       # Minor importance
                        }
                    elif is_cm:
                        # CM - Defense and passing are most important
                        weights = {
                            'defense': 3.0,      # Very important
                            'passing': 3.0,      # Very important
                            'dribbling': 1.5,    # Moderate importance
                            'shooting': 1.0,     # Less important
                            'goalkeeping': 0.1   # Not relevant
                        }
                    elif is_winger:
                        # LW/RW - Dribbling and passing most important
                        weights = {
                            'dribbling': 3.5,    # Most important
                            'passing': 2.5,      # Very important
                            'shooting': 2.0,     # Important
                            'defense': 0.5,      # Minor importance
                            'goalkeeping': 0.1   # Not relevant
                        }
                    elif is_forward:
                        # CF - Shooting is extremely important
                        weights = {
                            'shooting': 5.0,     # Extremely important
                            'dribbling': 1.5,    # Secondary
                            'passing': 1.0,      # Tertiary
                            'defense': 0.2,      # Almost irrelevant
                            'goalkeeping': 0.1   # Not relevant
                        }
                    else:
                        # Fallback - balanced weights
                        weights = {
                            'shooting': 1.0,
                            'dribbling': 1.0,
                            'passing': 1.0,
                            'defense': 1.0,
                            'goalkeeping': 0.5
                        }
                
                    # Calculate value based on weighted ratings
                    base_value = 0
                    for skill, rating in ratings.items():
                        if rating is not None:
                            base_value += rating * weights[skill]
                
                    # Calculate maximum possible points
                    max_points = sum(weight for skill, weight in weights.items() 
                                    if ratings.get(skill) is not None) * 10
                    
                    # Return value as percentage of max (scaled to 50)
                    if max_points > 0:
                        return int((base_value / max_points) * 50)
                    else:
                        return 0
                    
                # Pass all position data to calculate correct value
                position_data = {
                    "is_goalkeeper": evaluation["is_goalkeeper"],
                    "is_cm": evaluation["is_cm"],
                    "is_winger": evaluation["is_winger"],
                    "is_forward": evaluation["is_forward"]
                }
                
                value = calculate_player_value(evaluation["ratings"], position_data)
                logger.info(f"[TRYOUTS] Calculated value for {player}: {value}m")

                # Post results in tryouts-results channel
                results_message = (
                    f"🎮 **Tryout Results for {player.mention}**\n"
                    f"Evaluated by: {ctx.author.mention}\n"
                    f"Position: **{evaluation['position_name']}**\n\n"
                    f"**Skills Assessment:**\n"
                    f"⚽ Shooting: {evaluation['ratings'].get('shooting', 'N/A')}/10\n"
                    f"👟 Dribbling: {evaluation['ratings'].get('dribbling', 'N/A')}/10\n"
                    f"🎯 Passing: {evaluation['ratings'].get('passing', 'N/A')}/10\n"
                    f"🛡️ Defense: {evaluation['ratings'].get('defense', 'N/A')}/10\n"
                    f"🧤 Goalkeeping: {evaluation['ratings'].get('goalkeeping', 'N/A')}/10\n\n"
                    f"💭 **Evaluator's Feedback:**\n{evaluation['feedback']}\n\n"
                    f"💰 **Calculated Value:** ¥{value}m"
                )

                await tryouts_channel.send(results_message)
                logger.info(f"[TRYOUTS] Posted results in tryout results channel for {player}")

                # Set player value directly
                try:
                    # Get data manager from bot context instead of importing
                    # to avoid circular imports
                    if hasattr(ctx.bot, 'data_manager'):
                        data_manager = ctx.bot.data_manager
                        # Set the value directly
                        data_manager.set_member_value(str(player.id), value)
                        logger.info(f"[TRYOUTS] Directly set value for {player.id}: {value}m")
                    else:
                        logger.error("[TRYOUTS] Could not access data_manager from bot context")
                        await ctx.send("❌ An error occurred while setting the player's value. Please use !setvalue manually.")
                    
                    # Update player roles
                    try:
                        # Remove tryout role and add regular player role
                        tryout_role_id = 1350864967674630144  # Tryout Squad role
                        player_role_id = 1350863646187716640  # Regular Player role
                        
                        # Get role objects
                        tryout_role = discord.utils.get(ctx.guild.roles, id=tryout_role_id)
                        player_role = discord.utils.get(ctx.guild.roles, id=player_role_id)
                        
                        if tryout_role and player_role:
                            # Remove tryout role
                            if tryout_role in player.roles:
                                await player.remove_roles(tryout_role)
                                logger.info(f"[TRYOUTS] Removed tryout role from {player.id}")
                            
                            # Add player role
                            await player.add_roles(player_role)
                            logger.info(f"[TRYOUTS] Added player role to {player.id}")
                        else:
                            logger.error(f"[TRYOUTS] Could not find roles: tryout_role={tryout_role}, player_role={player_role}")
                    except Exception as e:
                        logger.error(f"[TRYOUTS] Error updating roles: {e}", exc_info=True)
                    
                    # Post success message in player-value channel
                    value_channel = discord.utils.get(ctx.guild.text_channels, name='💸-player-values')
                    if value_channel:
                        await value_channel.send(f"💰 {player.mention}'s value has been set to ¥{value} million! Welcome to the team! 🎉")
                        logger.info(f"[TRYOUTS] Posted value confirmation for {player}: {value}m")
                    else:
                        logger.error("[TRYOUTS] Could not find player values channel")
                        await ctx.send("⚠️ Could not find player values channel to announce value!")
                
                except Exception as e:
                    logger.error(f"[TRYOUTS] Error setting player value: {e}", exc_info=True)
                    await ctx.send("❌ An error occurred while setting the player's value. Please use !setvalue manually.")

                # Cleanup
                if ctx.author.id in active_tryouts:
                    del active_tryouts[ctx.author.id]
                logger.info(f"[TRYOUTS] Completed evaluation for {player}")

            except Exception as e:
                logger.error(f"[TRYOUTS] Error posting results: {e}", exc_info=True)
                await ctx.send("An error occurred while posting the evaluation results. Please try again.")
                if ctx.author.id in active_tryouts:
                    del active_tryouts[ctx.author.id]

    except Exception as e:
        logger.error(f"[TRYOUTS] Unhandled error in start_tryout_evaluation: {e}", exc_info=True)
        await ctx.send("An error occurred while starting the evaluation. Please try again.")
        if ctx.author.id in active_tryouts:
            del active_tryouts[ctx.author.id]

# We don't define active_tryouts here - it's imported from bot.py
# This prevents conflicts between the two dictionaries