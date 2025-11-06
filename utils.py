try:
    import discord
except ImportError:
    import discord.py as discord
from typing import Optional
import logging
import random
from spank_responses import SPANK_RESPONSES
from headpat_responses import HEADPAT_RESPONSES, SPANK_WARNING_RESPONSES, HEADPAT_WARNING_RESPONSES
from mute_responses import MUTE_RESPONSES, UNMUTE_RESPONSES
from joke_response import get_random_joke, get_random_secret_joke
from joke_manager import joke_manager, JokeCategory
from joke_reactions import register_joke_message, get_joke_with_difficulty
from spill_responses import ALL_SPILL_RESPONSES
from shopping_responses import ALL_SHOPPING_RESPONSES
from tipjar_responses import ALL_TIPJAR_RESPONSES
from confess_responses import ALL_CONFESS_RESPONSES
from player_drama import PlayerDramaGenerator

def has_value_management_role(member: discord.Member) -> bool:
    """Check if member has permission to manage values using server-specific configuration"""
    # Import server config function
    from server_config import has_management_permission
    
    # Check if the member has management permissions in their server
    server_id = str(member.guild.id)
    
    member_role_ids = [str(role.id) for role in member.roles]
    logging.debug(f"Checking value management permission for {member.name} (ID: {member.id}) in server {server_id}")
    logging.debug(f"Member role IDs: {', '.join(member_role_ids)}")
    
    has_permission = has_management_permission(member.roles, server_id)
    logging.debug(f"Permission check result for {member.name}: {has_permission}")
    return has_permission

def has_spank_permission(member: discord.Member) -> bool:
    """Check if member has permission to use spank command using server-specific configuration"""
    if not member.guild:
        return False
        
    # Check if the member has spank permissions in their server
    server_id = str(member.guild.id)
    member_role_ids = [str(role.id) for role in member.roles]
    
    # Required spank permission role ID
    spank_role_id = "1350743813143924800"
    has_permission = spank_role_id in member_role_ids
    
    # Allow bot owner
    if member.id == 859413883420016640:
        has_permission = True
    
    logging.debug(f"Checking spank permission for {member.name} in server {server_id}. Permission result: {has_permission}")
    return has_permission

def has_headpat_permission(member: discord.Member) -> bool:
    """Check if member has permission to use headpat command"""
    if not member.guild:
        return False
        
    # Check if the member has headpat permissions in their server
    server_id = str(member.guild.id)
    member_role_ids = [str(role.id) for role in member.roles]
    
    # Required headpat permission role ID
    headpat_role_id = "1350547213717209160"
    has_permission = headpat_role_id in member_role_ids
    
    # Allow bot owner
    if member.id == 859413883420016640:
        has_permission = True
    
    logging.debug(f"Checking headpat permission for {member.name} in server {server_id}. Permission result: {has_permission}")
    return has_permission

def parse_member_mention(message: discord.Message) -> Optional[discord.Member]:
    """Parse member mention from message"""
    if not message.mentions:
        return None
    return message.mentions[0]

def format_value_message(member: discord.Member, value: int) -> str:
    """Format value message"""
    return f"{member.display_name}'s value is: ¥{value} million 💴"

def format_activity_message(member: discord.Member, activity: dict) -> str:
    """Format activity message"""
    return (f"Activity for {member.display_name}:\n"
            f"Messages: {activity['messages']}\n"
            f"Reactions: {activity['reactions']}")

def format_ranking_message(rank: int, total_members: int, value: int, use_emoji: bool = False) -> str:
    """Format ranking message
    
    Args:
        rank: The member's rank
        total_members: Total number of members
        value: The member's value
        use_emoji: Whether to use medal emojis
    """
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    medal = medals.get(rank, "") if use_emoji else ""
    
    if rank == 0 or total_members == 0:
        return "Ranking information not available right now."
    
    percentile = 100 - (rank / total_members * 100) if total_members > 0 else 0
    percentile_text = f"Top {percentile:.1f}%" if percentile > 0 else ""
    
    return (f"{medal}Current Value: ¥{value} million 💴\n"
            f"Rank: #{rank} out of {total_members} members\n"
            f"{percentile_text}")

def get_random_spank_response(spanker: Optional[discord.Member], spankee: discord.Member) -> str:
    """Get a random spank response
    
    Args:
        spanker: The member giving the spank (None if Mommy is spanking)
        spankee: The member being spanked
    """
    if spanker is None:
        # Mommy is spanking the user
        response = random.choice(SPANK_RESPONSES).format(member=spankee)
    else:
        # User is spanking another user
        responses = ['Ouch!', 'That looks painful!', 'Wow, that was harsh!', "That's gonna leave a mark!"]
        response = f"💥 **{spanker.display_name}** spanks **{spankee.display_name}**! {random.choice(responses)}"
    
    logging.debug(f"Generated spank response for {spankee.name}: {response}")
    return response

def get_random_headpat_response() -> str:
    """Get a random headpat response for Mommy"""
    response = random.choice(HEADPAT_RESPONSES)
    logging.debug(f"Generated headpat response: {response}")
    return response

def get_spank_warning_response(member: discord.Member) -> str:
    """Get a random spank warning response"""
    response = random.choice(SPANK_WARNING_RESPONSES).format(member=member)
    logging.debug(f"Generated spank warning for {member.name}: {response}")
    return response

def get_headpat_warning_response(member: discord.Member) -> str:
    """Get a random headpat warning response"""
    response = random.choice(HEADPAT_WARNING_RESPONSES).format(member=member)
    logging.debug(f"Generated headpat warning for {member.name}: {response}")
    return response

def get_random_mute_response(member: discord.Member) -> str:
    """Get a random mute response"""
    response = random.choice(MUTE_RESPONSES).format(member=member)
    logging.debug(f"Generated mute response for {member.name}: {response}")
    return response

def get_random_unmute_response(member: discord.Member) -> str:
    """Get a random unmute response"""
    response = random.choice(UNMUTE_RESPONSES).format(member=member)
    logging.debug(f"Generated unmute response for {member.name}: {response}")
    return response

def get_spill_response(message: discord.Message = None, data_manager=None) -> str:
    """Get a response for !spill command - juicy gossip about Novarians adapted to server humor"""
    # Always use player drama (100% chance) if we have message, guild and data_manager
    if message and message.guild and data_manager:
        try:
            # Get all member values for logging
            all_values = data_manager.get_all_member_values()
            if all_values:
                # Log top 5 highest value players for debugging
                sorted_members = sorted(all_values.items(), key=lambda x: x[1], reverse=True)
                top_5 = sorted_members[:5]
                logging.info(f"Top 5 highest value players: {', '.join([f'{member_id}: {value}' for member_id, value in top_5])}")
            
            # Ensure we have at least 2 high-value players for drama
            drama_generator = PlayerDramaGenerator(data_manager)
            logging.info(f"Generating drama for server {message.guild.id} with high-value threshold {drama_generator.high_value_threshold}")
            drama_scenario = drama_generator.generate_drama(message.guild)
            
            # Register the joke message for reaction tracking
            register_joke_message(message, drama_scenario, JokeCategory.SPILL)
            
            logging.info(f"Generated player drama scenario for server {message.guild.id}")
            return drama_scenario
        except Exception as e:
            logging.error(f"Error generating player drama: {e}", exc_info=True)
            # Continue with normal joke generation if drama fails
    
    if message and message.guild:
        server_id = str(message.guild.id)
        all_jokes = []
        for difficulty, jokes in ALL_SPILL_RESPONSES.items():
            all_jokes.extend(jokes)
            
        joke = get_joke_with_difficulty(all_jokes, JokeCategory.SPILL, server_id)
        
        # Register the joke message for reaction tracking
        if message:
            register_joke_message(message, joke, JokeCategory.SPILL)
            
        logging.debug(f"Generated adaptive spill response for server {server_id}")
        return joke
    else:
        # Fallback to random selection if not in a guild
        all_jokes = []
        for difficulty, jokes in ALL_SPILL_RESPONSES.items():
            all_jokes.extend(jokes)
        joke = random.choice(all_jokes)
        logging.debug("Generated random spill response (not in guild)")
        return joke

def get_shopping_response(message: discord.Message = None, data_manager=None) -> str:
    """Get a response for !shopping command - Mommy's luxury purchases adapted to server humor"""
    if message and message.guild:
        server_id = str(message.guild.id)
        all_jokes = []
        for difficulty, jokes in ALL_SHOPPING_RESPONSES.items():
            all_jokes.extend(jokes)
            
        joke = get_joke_with_difficulty(all_jokes, JokeCategory.SHOPPING, server_id)
        
        # Register the joke message for reaction tracking
        if message:
            register_joke_message(message, joke, JokeCategory.SHOPPING)
            
        logging.debug(f"Generated adaptive shopping response for server {server_id}")
        return joke
    else:
        # Fallback to random selection if not in a guild
        all_jokes = []
        for difficulty, jokes in ALL_SHOPPING_RESPONSES.items():
            all_jokes.extend(jokes)
        joke = random.choice(all_jokes)
        logging.debug("Generated random shopping response (not in guild)")
        return joke

def get_tipjar_response(message: discord.Message = None, data_manager=None) -> str:
    """Get a response for !tipjar command - Mommy's special fund adapted to server humor"""
    if message and message.guild:
        server_id = str(message.guild.id)
        all_jokes = []
        for difficulty, jokes in ALL_TIPJAR_RESPONSES.items():
            all_jokes.extend(jokes)
            
        joke = get_joke_with_difficulty(all_jokes, JokeCategory.TIPJAR, server_id)
        
        # Register the joke message for reaction tracking
        if message:
            register_joke_message(message, joke, JokeCategory.TIPJAR)
            
        logging.debug(f"Generated adaptive tipjar response for server {server_id}")
        return joke
    else:
        # Fallback to random selection if not in a guild
        all_jokes = []
        for difficulty, jokes in ALL_TIPJAR_RESPONSES.items():
            all_jokes.extend(jokes)
        joke = random.choice(all_jokes)
        logging.debug("Generated random tipjar response (not in guild)")
        return joke

def get_confess_response(message: discord.Message = None, data_manager=None) -> str:
    """Get a response for !confess command - Mommy's behind-the-scenes activities adapted to server humor"""
    if message and message.guild:
        server_id = str(message.guild.id)
        all_jokes = []
        for difficulty, jokes in ALL_CONFESS_RESPONSES.items():
            all_jokes.extend(jokes)
            
        joke = get_joke_with_difficulty(all_jokes, JokeCategory.CONFESS, server_id)
        
        # Register the joke message for reaction tracking
        if message:
            register_joke_message(message, joke, JokeCategory.CONFESS)
            
        logging.debug(f"Generated adaptive confess response for server {server_id}")
        return joke
    else:
        # Fallback to random selection if not in a guild
        all_jokes = []
        for difficulty, jokes in ALL_CONFESS_RESPONSES.items():
            all_jokes.extend(jokes)
        joke = random.choice(all_jokes)
        logging.debug("Generated random confess response (not in guild)")
        return joke