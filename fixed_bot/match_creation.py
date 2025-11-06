"""Match creation and management functionality"""
from enum import Enum
from typing import Optional, List, Dict
import asyncio
import discord
from discord.ext import commands
import logging
from data_manager import DataManager

logger = logging.getLogger(__name__)

class MatchType(Enum):
    ONE_V_ONE = "1v1"
    TWO_V_TWO = "2v2"
    THREE_V_THREE = "3v3"
    FIVE_V_FIVE = "5v5"

    @property
    def channel_name(self) -> str:
        return {
            "1v1": "⚔-1v1-duels",
            "2v2": "🤝-2v2-battles",
            "3v3": "💨-3v3-showdowns",
            "5v5": "🏆-5v5-warzone"
        }[self.value]

    @property
    def team_size(self) -> int:
        return {
            "1v1": 1,
            "2v2": 2,
            "3v3": 3,
            "5v5": 5
        }[self.value]

class MatchState:
    def __init__(self, creator: discord.Member):
        self.creator = creator
        self.match_type: Optional[MatchType] = None
        self.amount: Optional[int] = None
        self.abilities_enabled: Optional[bool] = None
        self.roblox_username: Optional[str] = None
        self.private_server: Optional[str] = None
        self.region: Optional[str] = None
        self.teammates: List[discord.Member] = []
        self.teammates_pending: List[discord.Member] = []
        self.opponents: List[discord.Member] = []
        self.opponent_id: Optional[str] = None  # Added to store opponent's ID
        self.current_step = 0
        self.creation_message: Optional[discord.Message] = None
        self.timeout_task: Optional[asyncio.Task] = None

    def is_full(self) -> bool:
        """Check if the match has enough players"""
        if not self.match_type:
            return False
        return len(self.opponents) >= self.match_type.team_size

    def add_player(self, player: discord.Member) -> None:
        """Add a player to the match"""
        if player not in self.opponents:
            self.opponents.append(player)

    def needs_teammates(self) -> bool:
        """Check if this match type requires teammates"""
        return self.match_type in [MatchType.TWO_V_TWO, MatchType.THREE_V_THREE, MatchType.FIVE_V_FIVE]

    def required_teammates(self) -> int:
        """Get number of teammates needed"""
        if not self.match_type:
            return 0
        return {
            MatchType.TWO_V_TWO: 1,
            MatchType.THREE_V_THREE: 2,
            MatchType.FIVE_V_FIVE: 4
        }.get(self.match_type, 0)

# Store ongoing match creations
active_matches: Dict[int, MatchState] = {}

async def start_match_creation(ctx: commands.Context) -> None:
    """Start the match creation process"""
    try:
        # Create new match state
        match_state = MatchState(ctx.author)
        active_matches[ctx.author.id] = match_state
        logger.info(f"Starting match creation for {ctx.author} (ID: {ctx.author.id})")
        logger.info(f"Active matches: {list(active_matches.keys())}")

        # Create embed with instructions
        embed = discord.Embed(
            title="🎮 Match Creation",
            description=(
                "Let's create your match! I'll guide you through the process.\n"
                "Please type the number for your match type:\n\n"
                "1. 1v1 Duel\n"
                "2. 2v2 Battle\n"
                "3. 3v3 Showdown\n"
                "4. 5v5 Warzone"
            ),
            color=discord.Color.blue()
        )

        # Send DM
        try:
            dm_channel = await ctx.author.create_dm()
            await dm_channel.send(embed=embed)
            await ctx.send("📩 Check your DMs to set up your match!")
            logger.info(f"Sent initial DM to {ctx.author}")
        except discord.Forbidden:
            logger.warning(f"Could not send DM to {ctx.author}")
            await ctx.send("❌ I couldn't send you a DM! Please enable DMs from server members and try again.")
            del active_matches[ctx.author.id]

    except Exception as e:
        logger.error(f"Error starting match creation: {e}", exc_info=True)
        await ctx.send("An error occurred while starting match creation. Please try again.")
        if ctx.author.id in active_matches:
            del active_matches[ctx.author.id]

async def process_teammate_selection(message: discord.Message, match_state: MatchState) -> bool:
    """Process teammate selection for team matches"""
    if not message.mentions:
        await message.channel.send("Please @ mention your teammate(s)!")
        return False

    required_teammates = match_state.required_teammates()
    if len(message.mentions) != required_teammates:
        await message.channel.send(f"Please mention exactly {required_teammates} teammate{'s' if required_teammates > 1 else ''}!")
        return False

    match_state.teammates_pending = message.mentions
    logger.info(f"Processing teammate selection. Required: {required_teammates}, Mentioned: {len(message.mentions)}")

    # Send DMs to teammates
    team_size = match_state.match_type.team_size
    for teammate in match_state.teammates_pending:
        try:
            dm_channel = await teammate.create_dm()
            await dm_channel.send(
                f"🎮 {message.author.mention} wants you to join their {team_size}v{team_size} team!\n"
                f"💴 Bet amount: ¥{match_state.amount}m\n"
                f"🌍 Region: {match_state.region}\n"
                f"🎯 Abilities: {'✅ Enabled' if match_state.abilities_enabled else '❌ Disabled'}\n\n"
                "Type 'accept' or 'decline' to respond!"
            )
            logger.info(f"Sent team invite DM to {teammate}")
        except discord.Forbidden:
            await message.channel.send(f"❌ Couldn't send DM to {teammate.mention}! Please choose another teammate.")
            return False

    await message.channel.send("✅ Invites sent to your teammates! Waiting for their responses...")
    return True

async def handle_teammate_response(message: discord.Message) -> None:
    """Handle teammate accept/decline responses"""
    try:
        response = message.content.lower()
        # Log for debugging
        logger.info(f"Handling teammate response from {message.author}: {response}")
        logger.info(f"Active matches: {list(active_matches.keys())}")

        # Check each active match for pending teammates
        for creator_id, match_state in active_matches.items():
            if message.author in match_state.teammates_pending:
                if response == 'accept':
                    # Add to teammates and remove from pending
                    match_state.teammates.append(message.author)
                    match_state.teammates_pending.remove(message.author)
                    await message.channel.send("✅ You've joined the team!")
                    logger.info(f"User {message.author} accepted team invite from {creator_id}")

                    # If all teammates accepted, proceed with match creation
                    if not match_state.teammates_pending:
                        creator = match_state.creator
                        dm_channel = await creator.create_dm()
                        await dm_channel.send("✅ All teammates accepted! Please provide your Roblox username:")
                        match_state.current_step = 4  # Skip to Roblox username step
                        logger.info(f"All teammates accepted for match {creator_id}")

                elif response == 'decline':
                    # Remove from pending and notify creator
                    match_state.teammates_pending.remove(message.author)
                    await message.channel.send("❌ You've declined the team invitation.")
                    logger.info(f"User {message.author} declined team invite from {creator_id}")

                    # Notify creator
                    creator = match_state.creator
                    dm_channel = await creator.create_dm()
                    await dm_channel.send(
                        f"❌ {message.author.mention} declined to join your team.\n"
                        "Please mention new teammate(s)!"
                    )
                break

    except Exception as e:
        logger.error(f"Error handling teammate response: {e}")

async def handle_match_creation_step(match_state: MatchState, message: discord.Message) -> None:
    """Handle the current step of match creation"""
    try:
        logger.info(f"Processing step {match_state.current_step} for {message.author}")
        logger.info(f"Active matches before step: {list(active_matches.keys())}")

        if match_state.current_step == 0:
            # Match type selection
            match_types = {
                "1": MatchType.ONE_V_ONE,
                "2": MatchType.TWO_V_TWO,
                "3": MatchType.THREE_V_THREE,
                "4": MatchType.FIVE_V_FIVE
            }

            if message.content not in match_types:
                await message.channel.send("Please enter a number between 1 and 4 to select your match type.")
                return

            match_state.match_type = match_types[message.content]
            match_state.current_step = 1
            logger.info(f"Selected match type: {match_state.match_type.value}")
            await message.channel.send(
                "💴 How much would you like to bet? (in millions)\n"
                "Example: Enter 5 for 5 million"
            )

        elif match_state.current_step == 1:
            # Amount selection
            try:
                amount = int(message.content)
                if amount <= 0:
                    await message.channel.send("Please enter a positive amount!")
                    return

                # Check if user has enough value
                data_manager = DataManager("member_data.json")
                user_value = data_manager.get_member_value(str(message.author.id))
                logger.info(f"Match creation: User {message.author} (ID: {message.author.id}) trying to bet {amount}m with value {user_value}m")

                if user_value == 0:
                    await message.channel.send(
                        "❌ You don't have a value set yet!\n"
                        "Please contact a Founder, Co-Founder, or Trainer to get your value set."
                    )
                    return

                if amount > user_value:
                    await message.channel.send(
                        f"❌ You don't have enough value to place this bet!\n"
                        f"Your current value: ¥{user_value}m 💴\n"
                        f"Bet amount: ¥{amount}m 💴"
                    )
                    return

                match_state.amount = amount
                match_state.current_step = 2
                logger.info(f"Set bet amount: {amount}m for user {message.author}")
                await message.channel.send(
                    "🌍 What region will you be playing in?\n"
                    "Type 1 for NA\n"
                    "Type 2 for EU"
                )

            except ValueError:
                await message.channel.send("Please enter a valid number!")

        elif match_state.current_step == 2:
            # Region selection
            if message.content not in ["1", "2"]:
                await message.channel.send("Please type 1 for NA or 2 for EU.")
                return

            match_state.region = "NA" if message.content == "1" else "EU"
            match_state.current_step = 3
            logger.info(f"Set region: {match_state.region}")

            if match_state.needs_teammates():
                # For team matches, ask for teammates first
                required = match_state.required_teammates()
                await message.channel.send(
                    f"👥 Please @ mention your {required} teammate{'s' if required > 1 else ''}!"
                )
            else:
                # For 1v1, go straight to abilities
                await message.channel.send(
                    "🎯 Should abilities be enabled?\n"
                    "Type 1 for Yes\n"
                    "Type 2 for No"
                )

        elif match_state.current_step == 3:
            if match_state.needs_teammates():
                # Handle teammate selection for team matches
                if not await process_teammate_selection(message, match_state):
                    return
            else:
                # Abilities selection for 1v1
                if message.content not in ["1", "2"]:
                    await message.channel.send("Please type 1 for Yes or 2 for No.")
                    return

                match_state.abilities_enabled = message.content == "1"
                match_state.current_step = 4
                logger.info(f"Set abilities enabled: {match_state.abilities_enabled}")
                await message.channel.send("👤 What's your Roblox username?")

        elif match_state.current_step == 4:
            # Roblox username
            match_state.roblox_username = message.content
            match_state.current_step = 5
            logger.info(f"Set Roblox username: {match_state.roblox_username}")
            await message.channel.send(
                "🔗 Please provide your private server link\n"
                "Type 'skip' if you don't have one"
            )

        elif match_state.current_step == 5:
            # Private server (optional)
            if message.content.lower() != 'skip':
                match_state.private_server = message.content
                logger.info(f"Set private server link: {match_state.private_server}")
            else:
                logger.info("Skipped private server link")

            # Create match advertisement
            await finalize_match_creation(message.channel, match_state)

        logger.info(f"Active matches after step: {list(active_matches.keys())}")

    except Exception as e:
        logger.error(f"Error in match creation step: {e}", exc_info=True)

async def finalize_match_creation(channel: discord.DMChannel, match_state: MatchState) -> None:
    """Create the match advertisement and post it"""
    try:
        logger.info(f"Finalizing match creation for {match_state.creator}")
        logger.info(f"Active matches before finalization: {list(active_matches.keys())}")

        # Find the appropriate channel
        match_channel = discord.utils.get(
            match_state.creator.guild.text_channels,
            name=match_state.match_type.channel_name
        )

        if not match_channel:
            logger.error(f"Could not find channel: {match_state.match_type.channel_name}")
            await channel.send(f"❌ Couldn't find the {match_state.match_type.channel_name} channel!")
            if match_state.creator.id in active_matches:
                del active_matches[match_state.creator.id]
            return

        # Create match advertisement
        embed = discord.Embed(
            title=f"🎮 New {match_state.match_type.value} Match [{match_state.region}]",
            description=(
                f"**Bet Amount:** ¥{match_state.amount}m 💴\n"
                f"**Region:** {match_state.region} 🌍\n"
                f"**Abilities:** {'✅ Enabled' if match_state.abilities_enabled else '❌ Disabled'}\n"
                f"**Creator:** {match_state.creator.mention}\n\n"
                f"React with ✅ to join! ({match_state.match_type.team_size} players per team)"
            ),
            color=discord.Color.green()
        )

        # Post advertisement
        ad_message = await match_channel.send(embed=embed)
        match_state.creation_message = ad_message
        await ad_message.add_reaction("✅")
        logger.info(f"Posted match advertisement in {match_channel.name}")

        # Deduct bet amount
        data_manager = DataManager("member_data.json")
        current_value = data_manager.get_member_value(str(match_state.creator.id))
        data_manager.set_member_value(str(match_state.creator.id), current_value - match_state.amount)
        logger.info(f"Deducted {match_state.amount}m from creator's value")

        await channel.send(
            "✅ Match created successfully!\n"
            "Watch the channel for opponents.\n"
            "Your bet amount has been deducted."
        )

        # Start timeout task
        match_state.timeout_task = asyncio.create_task(
            handle_match_timeout(ad_message, match_state, data_manager)
        )

        logger.info(f"Active matches after finalization: {list(active_matches.keys())}")

    except Exception as e:
        logger.error(f"Error finalizing match: {e}", exc_info=True)
        await channel.send("An error occurred while creating the match. Please try again.")
        if match_state.creator.id in active_matches:
            del active_matches[match_state.creator.id]

async def handle_match_join(reaction: discord.Reaction, user: discord.Member, match_state: MatchState) -> None:
    """Handle a user joining a match"""
    try:
        # Check if match is already full
        if match_state.is_full():
            return

        # Add user to opponents
        match_state.add_player(user)
        logger.info(f"Added {user} to match opponents. Current count: {len(match_state.opponents)}")

        # Check if match is now full
        if match_state.is_full():
            # Send DMs to all participants
            all_participants = [match_state.creator] + match_state.teammates + match_state.opponents

            # Prepare match details message
            details_msg = (
                "🎮 **Match Details**\n"
                f"💫 Match Type: {match_state.match_type.value}\n"
                f"💴 Bet Amount: ¥{match_state.amount}m\n"
                f"🌍 Region: {match_state.region}\n"
                f"🎯 Abilities: {'✅ Enabled' if match_state.abilities_enabled else '❌ Disabled'}\n\n"
                f"👥 **Players**\n"
                f"Host: {match_state.creator.mention}\n"
                f"Roblox Username: {match_state.roblox_username}\n"
            )

            if match_state.private_server:
                details_msg += f"\n🔗 **Private Server Link**\n{match_state.private_server}"

            # Send DMs to all participants
            for participant in all_participants:
                try:
                    dm_channel = await participant.create_dm()
                    await dm_channel.send(details_msg)
                except discord.Forbidden:
                    logger.warning(f"Could not send match details DM to {participant}")

            # Send match started message in the channel
            channel_msg = (
                "🎮 **Match Has Begun!** 🎮\n"
                f"Good luck to {match_state.creator.mention} "
                f"and {', '.join(opponent.mention for opponent in match_state.opponents)}! "
                "May the best player win! ⚔️✨\n\n"
                "📢 **Novarians:** When your match is complete, use `!matchresult challengers` "
                "or `!matchresult challenged` in DMs or any channel, then follow the instructions "
                "to submit your proof! 📸"
            )
            await reaction.message.channel.send(channel_msg)

            # Clean up the advertisement
            await reaction.message.delete()
            del active_matches[match_state.creator.id]

    except Exception as e:
        logger.error(f"Error handling match join: {e}", exc_info=True)

async def handle_match_timeout(message: discord.Message, match_state: MatchState, data_manager: DataManager) -> None:
    """Handle match timeout after 24 hours"""
    try:
        await asyncio.sleep(86400)  # 24 hours

        # Check if match_state still exists
        if match_state.creator.id in active_matches:
            await message.delete()
            logger.info(f"Match timed out for {match_state.creator}")

            # Refund creator
            current_value = data_manager.get_member_value(str(match_state.creator.id))
            data_manager.set_member_value(
                str(match_state.creator.id),
                current_value + match_state.amount
            )
            logger.info(f"Refunded {match_state.amount}m to creator")

            try:
                dm_channel = await match_state.creator.create_dm()
                await dm_channel.send(
                    "⏰ Your match has timed out after 24 hours and been cancelled.\n"
                    "Your bet has been refunded."
                )
            except discord.Forbidden:
                logger.warning(f"Could not send timeout DM to {match_state.creator}")

            # Clean up the match state
            del active_matches[match_state.creator.id]

    except asyncio.CancelledError:
        logger.info(f"Match timeout cancelled for {match_state.creator}")
    except Exception as e:
        logger.error(f"Error in match timeout: {e}", exc_info=True)