import discord
import asyncio
import logging
from datetime import datetime
import re
from typing import List, Tuple
import os
from data_manager import DataManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='value_restore.log'
)
logger = logging.getLogger(__name__)

# Initialize Discord client with necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

# Initialize data manager
data_manager = DataManager("member_data.json")

async def extract_value_command(message: discord.Message) -> Tuple[str, str, int]:
    """Extract command type, member ID, and value from a message"""
    content = message.content.lower()

    # Extract command type (setvalue or addvalue)
    if content.startswith('!setvalue'):
        command_type = 'setvalue'
    elif content.startswith('!addvalue'):
        command_type = 'addvalue'
    else:
        return None

    # Extract member ID from mention
    member_matches = re.findall(r'<@!?(\d+)>', content)
    if not member_matches:
        return None
    member_id = member_matches[0]

    # Extract value
    if command_type == 'setvalue':
        value_matches = re.findall(r'\d+', content)
        if not value_matches:
            return None
        value = int(value_matches[-1])
    else:  # addvalue
        value_matches = re.findall(r'[+-]?\d+', content)
        if not value_matches:
            return None
        value = int(value_matches[-1])

    return (command_type, member_id, value)

async def process_value_channel(channel_id: int) -> None:
    """Process the value channel and execute all value commands"""
    channel = client.get_channel(channel_id)
    if not channel:
        logger.error(f"Could not find channel with ID {channel_id}")
        return

    logger.info("Starting to process value channel history...")
    processed_count = 0

    async for message in channel.history(limit=None, oldest_first=True):
        try:
            if message.content.startswith(('!setvalue', '!addvalue')):
                result = await extract_value_command(message)
                if result:
                    command_type, member_id, value = result
                    current_value = data_manager.get_member_value(member_id)

                    if command_type == 'setvalue':
                        data_manager.set_member_value(member_id, value)
                        logger.info(f"Restored setvalue command: Member {member_id} value set to {value}m")
                    else:  # addvalue
                        new_value = current_value + value
                        if new_value >= 0:  # Ensure value doesn't go negative
                            data_manager.set_member_value(member_id, new_value)
                            logger.info(f"Restored addvalue command: Member {member_id} value adjusted by {value}m to {new_value}m")

                    processed_count += 1
                    if processed_count % 10 == 0:  # Log progress every 10 commands
                        logger.info(f"Processed {processed_count} commands so far...")

        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            continue

    logger.info(f"Finished processing value channel. Restored {processed_count} value commands.")

@client.event
async def on_ready():
    """Process value channel when bot is ready"""
    try:
        logger.info(f"Bot {client.user} is connected to Discord!")

        # Get the value channel ID from environment
        VALUE_CHANNEL_ID = int(os.getenv('VALUE_CHANNEL_ID'))

        # Process the channel and restore values
        await process_value_channel(VALUE_CHANNEL_ID)
        logger.info("Value restoration complete!")

        # Close the client after processing
        await client.close()

    except Exception as e:
        logger.error(f"Error in value restoration: {e}")
        await client.close()

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("Discord token not found in environment variables")

    try:
        client.run(TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")