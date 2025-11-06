import asyncio
import random
import discord
import logging
from typing import List, Dict, Optional, Union, Callable, Awaitable, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Animation sets for each command with unique loading messages
COMMAND_ANIMATIONS = {
    # Default/General animations
    "general": [
        ["💖 Mommy is thinking", "💖 Mommy is thinking.", "💖 Mommy is thinking..", "💖 Mommy is thinking...", "💖 Mommy is thinking....", "💖 Mommy is thinking....."],
        ["✨ Processing request", "✨ Processing request.", "✨ Processing request..", "✨ Processing request...", "✨ Processing request....", "✨ Processing request....."],
        ["🌸 Loading", "🌸 Loading.", "🌸 Loading..", "🌸 Loading...", "🌸 Loading....", "🌸 Loading....."],
        ["💅 Preparing response", "💅 Preparing response.", "💅 Preparing response..", "💅 Preparing response...", "💅 Preparing response....", "💅 Preparing response....."]
    ],
    
    # Specific command animations
    "checkvalue": [
        ["💰 Checking your value", "💰 Checking your value.", "💰 Checking your value..", "💰 Checking your value...", "💰 Checking your value....", "💰 Checking your value....."],
        ["💎 Looking up your worth", "💎 Looking up your worth.", "💎 Looking up your worth..", "💎 Looking up your worth...", "💎 Looking up your worth....", "💎 Looking up your worth....."],
        ["💵 Calculating your worth", "💵 Calculating your worth.", "💵 Calculating your worth..", "💵 Calculating your worth...", "💵 Calculating your worth....", "💵 Calculating your worth....."],
        ["🧮 Crunching the numbers", "🧮 Crunching the numbers.", "🧮 Crunching the numbers..", "🧮 Crunching the numbers...", "🧮 Crunching the numbers....", "🧮 Crunching the numbers....."]
    ],
    
    "rankings": [
        ["🏆 Updating rankings", "🏆 Updating rankings.", "🏆 Updating rankings..", "🏆 Updating rankings...", "🏆 Updating rankings....", "🏆 Updating rankings....."],
        ["🔢 Sorting by value", "🔢 Sorting by value.", "🔢 Sorting by value..", "🔢 Sorting by value...", "🔢 Sorting by value....", "🔢 Sorting by value....."],
        ["🌟 Finding the stars", "🌟 Finding the stars.", "🌟 Finding the stars..", "🌟 Finding the stars...", "🌟 Finding the stars....", "🌟 Finding the stars....."],
        ["📊 Generating leaderboard", "📊 Generating leaderboard.", "📊 Generating leaderboard..", "📊 Generating leaderboard...", "📊 Generating leaderboard....", "📊 Generating leaderboard....."]
    ],
    
    "goldrush": [
        ["🏅 Checking Gold Rush balance", "🏅 Checking Gold Rush balance.", "🏅 Checking Gold Rush balance..", "🏅 Checking Gold Rush balance...", "🏅 Checking Gold Rush balance....", "🏅 Checking Gold Rush balance....."],
        ["💰 Counting your Gold Rush coins", "💰 Counting your Gold Rush coins.", "💰 Counting your Gold Rush coins..", "💰 Counting your Gold Rush coins...", "💰 Counting your Gold Rush coins....", "💰 Counting your Gold Rush coins....."],
        ["✨ Examining your Gold Rush fortune", "✨ Examining your Gold Rush fortune.", "✨ Examining your Gold Rush fortune..", "✨ Examining your Gold Rush fortune...", "✨ Examining your Gold Rush fortune....", "✨ Examining your Gold Rush fortune....."],
        ["💎 Calculating your Gold Rush wealth", "💎 Calculating your Gold Rush wealth.", "💎 Calculating your Gold Rush wealth..", "💎 Calculating your Gold Rush wealth...", "💎 Calculating your Gold Rush wealth....", "💎 Calculating your Gold Rush wealth....."]
    ],
    
    "sm": [
        ["✏️ Setting member value", "✏️ Setting member value.", "✏️ Setting member value..", "✏️ Setting member value...", "✏️ Setting member value....", "✏️ Setting member value....."],
        ["💶 Adjusting worth", "💶 Adjusting worth.", "💶 Adjusting worth..", "💶 Adjusting worth...", "💶 Adjusting worth....", "💶 Adjusting worth....."],
        ["📝 Updating records", "📝 Updating records.", "📝 Updating records..", "📝 Updating records...", "📝 Updating records....", "📝 Updating records....."]
    ],
    
    "addvalue": [
        ["➕ Adding value", "➕ Adding value.", "➕ Adding value..", "➕ Adding value...", "➕ Adding value....", "➕ Adding value....."],
        ["📈 Modifying worth", "📈 Modifying worth.", "📈 Modifying worth..", "📈 Modifying worth...", "📈 Modifying worth....", "📈 Modifying worth....."],
        ["🔄 Updating player stats", "🔄 Updating player stats.", "🔄 Updating player stats..", "🔄 Updating player stats...", "🔄 Updating player stats....", "🔄 Updating player stats....."]
    ],
    
    "anteup": [
        ["🎲 Setting up wager", "🎲 Setting up wager.", "🎲 Setting up wager..", "🎲 Setting up wager...", "🎲 Setting up wager....", "🎲 Setting up wager....."],
        ["💸 Creating match", "💸 Creating match.", "💸 Creating match..", "💸 Creating match...", "💸 Creating match....", "💸 Creating match....."],
        ["🏅 Setting up competition", "🏅 Setting up competition.", "🏅 Setting up competition..", "🏅 Setting up competition...", "🏅 Setting up competition....", "🏅 Setting up competition....."]
    ],
    
    "mr": [
        ["📋 Processing match results", "📋 Processing match results.", "📋 Processing match results..", "📋 Processing match results...", "📋 Processing match results....", "📋 Processing match results....."],
        ["🗳️ Validating outcome", "🗳️ Validating outcome.", "🗳️ Validating outcome..", "🗳️ Validating outcome...", "🗳️ Validating outcome....", "🗳️ Validating outcome....."],
        ["🏁 Finalizing match", "🏁 Finalizing match.", "🏁 Finalizing match..", "🏁 Finalizing match...", "🏁 Finalizing match....", "🏁 Finalizing match....."]
    ],
    
    "modhelp": [
        ["👮 Loading mod tools", "👮 Loading mod tools.", "👮 Loading mod tools..", "👮 Loading mod tools...", "👮 Loading mod tools....", "👮 Loading mod tools....."],
        ["🔍 Preparing help topics", "🔍 Preparing help topics.", "🔍 Preparing help topics..", "🔍 Preparing help topics...", "🔍 Preparing help topics....", "🔍 Preparing help topics....."],
        ["⚖️ Getting mod tips ready", "⚖️ Getting mod tips ready.", "⚖️ Getting mod tips ready..", "⚖️ Getting mod tips ready...", "⚖️ Getting mod tips ready....", "⚖️ Getting mod tips ready....."]
    ],
    
    "cleanserver": [
        ["🧹 Cleaning the server", "🧹 Cleaning the server.", "🧹 Cleaning the server..", "🧹 Cleaning the server...", "🧹 Cleaning the server....", "🧹 Cleaning the server....."],
        ["🧼 Scrubbing messages", "🧼 Scrubbing messages.", "🧼 Scrubbing messages..", "🧼 Scrubbing messages...", "🧼 Scrubbing messages....", "🧼 Scrubbing messages....."],
        ["🔎 Finding bad language", "🔎 Finding bad language.", "🔎 Finding bad language..", "🔎 Finding bad language...", "🔎 Finding bad language....", "🔎 Finding bad language....."]
    ],
    
    "untimeout": [
        ["⏱️ Removing timeout", "⏱️ Removing timeout.", "⏱️ Removing timeout..", "⏱️ Removing timeout...", "⏱️ Removing timeout....", "⏱️ Removing timeout....."],
        ["🔓 Freeing member", "🔓 Freeing member.", "🔓 Freeing member..", "🔓 Freeing member...", "🔓 Freeing member....", "🔓 Freeing member....."],
        ["⚡ Removing restrictions", "⚡ Removing restrictions.", "⚡ Removing restrictions..", "⚡ Removing restrictions...", "⚡ Removing restrictions....", "⚡ Removing restrictions....."]
    ],
    
    "spank": [
        ["😈 Preparing to spank", "😈 Preparing to spank.", "😈 Preparing to spank..", "😈 Preparing to spank...", "😈 Preparing to spank....", "😈 Preparing to spank....."],
        ["🔥 Warming up the paddle", "🔥 Warming up the paddle.", "🔥 Warming up the paddle..", "🔥 Warming up the paddle...", "🔥 Warming up the paddle....", "🔥 Warming up the paddle....."],
        ["👋 Getting ready to slap", "👋 Getting ready to slap.", "👋 Getting ready to slap..", "👋 Getting ready to slap...", "👋 Getting ready to slap....", "👋 Getting ready to slap....."]
    ],
    
    "headpat": [
        ["💕 Feeling the pats", "💕 Feeling the pats.", "💕 Feeling the pats..", "💕 Feeling the pats...", "💕 Feeling the pats....", "💕 Feeling the pats....."],
        ["🥰 Enjoying the affection", "🥰 Enjoying the affection.", "🥰 Enjoying the affection..", "🥰 Enjoying the affection...", "🥰 Enjoying the affection....", "🥰 Enjoying the affection....."],
        ["😊 Purring happily", "😊 Purring happily.", "😊 Purring happily..", "😊 Purring happily...", "😊 Purring happily....", "😊 Purring happily....."]
    ],
    
    "spill": [
        ["👀 Gathering the tea", "👀 Gathering the tea.", "👀 Gathering the tea..", "👀 Gathering the tea...", "👀 Gathering the tea....", "👀 Gathering the tea....."],
        ["🗣️ Getting the gossip ready", "🗣️ Getting the gossip ready.", "🗣️ Getting the gossip ready..", "🗣️ Getting the gossip ready...", "🗣️ Getting the gossip ready....", "🗣️ Getting the gossip ready....."],
        ["🤭 Finding the juiciest bits", "🤭 Finding the juiciest bits.", "🤭 Finding the juiciest bits..", "🤭 Finding the juiciest bits...", "🤭 Finding the juiciest bits....", "🤭 Finding the juiciest bits....."]
    ],
    
    "confess": [
        ["💋 Preparing confession", "💋 Preparing confession.", "💋 Preparing confession..", "💋 Preparing confession...", "💋 Preparing confession....", "💋 Preparing confession....."],
        ["🙊 Finding secrets to share", "🙊 Finding secrets to share.", "🙊 Finding secrets to share..", "🙊 Finding secrets to share...", "🙊 Finding secrets to share....", "🙊 Finding secrets to share....."],
        ["💭 Thinking of what to admit", "💭 Thinking of what to admit.", "💭 Thinking of what to admit..", "💭 Thinking of what to admit...", "💭 Thinking of what to admit....", "💭 Thinking of what to admit....."]
    ],
    
    "shopping": [
        ["🛍️ Checking the shelves", "🛍️ Checking the shelves.", "🛍️ Checking the shelves..", "🛍️ Checking the shelves...", "🛍️ Checking the shelves....", "🛍️ Checking the shelves....."],
        ["💄 Browsing luxury goods", "💄 Browsing luxury goods.", "💄 Browsing luxury goods..", "💄 Browsing luxury goods...", "💄 Browsing luxury goods....", "💄 Browsing luxury goods....."],
        ["👜 Finding the designer bags", "👜 Finding the designer bags.", "👜 Finding the designer bags..", "👜 Finding the designer bags...", "👜 Finding the designer bags....", "👜 Finding the designer bags....."]
    ],
    
    "tipjar": [
        ["💰 Counting the tips", "💰 Counting the tips.", "💰 Counting the tips..", "💰 Counting the tips...", "💰 Counting the tips....", "💰 Counting the tips....."],
        ["💵 Checking the fund", "💵 Checking the fund.", "💵 Checking the fund..", "💵 Checking the fund...", "💵 Checking the fund....", "💵 Checking the fund....."],
        ["💸 Opening the tip jar", "💸 Opening the tip jar.", "💸 Opening the tip jar..", "💸 Opening the tip jar...", "💸 Opening the tip jar....", "💸 Opening the tip jar....."]
    ],
    
    "tryoutsresults": [
        ["⚽ Processing tryout results", "⚽ Processing tryout results.", "⚽ Processing tryout results..", "⚽ Processing tryout results...", "⚽ Processing tryout results....", "⚽ Processing tryout results....."],
        ["📋 Evaluating player stats", "📋 Evaluating player stats.", "📋 Evaluating player stats..", "📋 Evaluating player stats...", "📋 Evaluating player stats....", "📋 Evaluating player stats....."],
        ["🏆 Finalizing player rating", "🏆 Finalizing player rating.", "🏆 Finalizing player rating..", "🏆 Finalizing player rating...", "🏆 Finalizing player rating....", "🏆 Finalizing player rating....."]
    ],
    
    "eval": [
        ["📊 Evaluating player", "📊 Evaluating player.", "📊 Evaluating player..", "📊 Evaluating player...", "📊 Evaluating player....", "📊 Evaluating player....."],
        ["🔍 Analyzing performance", "🔍 Analyzing performance.", "🔍 Analyzing performance..", "🔍 Analyzing performance...", "🔍 Analyzing performance....", "🔍 Analyzing performance....."],
        ["📈 Rating abilities", "📈 Rating abilities.", "📈 Rating abilities..", "📈 Rating abilities...", "📈 Rating abilities....", "📈 Rating abilities....."]
    ],
    
    "activity": [
        ["📱 Checking activity", "📱 Checking activity.", "📱 Checking activity..", "📱 Checking activity...", "📱 Checking activity....", "📱 Checking activity....."],
        ["📊 Analyzing participation", "📊 Analyzing participation.", "📊 Analyzing participation..", "📊 Analyzing participation...", "📊 Analyzing participation....", "📊 Analyzing participation....."],
        ["📈 Loading activity stats", "📈 Loading activity stats.", "📈 Loading activity stats..", "📈 Loading activity stats...", "📈 Loading activity stats....", "📈 Loading activity stats....."]
    ]
}

# Animation frame intervals in seconds
DEFAULT_ANIMATION_INTERVAL = 1.25  # Slowed down from 0.75 to make animations more visible

# Optional: Keep for backward compatibility with existing code
ANIMATION_SETS = COMMAND_ANIMATIONS
COMMAND_CATEGORIES = {cmd: "general" for cmd in COMMAND_ANIMATIONS.keys()}

class LoadingAnimator:
    """Class to manage loading animations for Discord bot commands"""
    
    def __init__(self, ctx: discord.ext.commands.Context, emoji: str = None, text: str = None):
        """Initialize the animator with a command context and optional custom animation"""
        self.ctx = ctx
        self.message = None
        self.running = False
        self.task = None
        self.frame_count = 0
        self.min_frames = 4  # Ensure at least 4 animation frames are shown
        
        # Determine command name and get appropriate animation
        self.command_name = ctx.command.name if ctx.command else "unknown"
        
        # If custom emoji and text are provided, create a custom animation
        if emoji and text:
            self.animation = [f"{emoji} {text}", 
                             f"{emoji} {text}.", 
                             f"{emoji} {text}..", 
                             f"{emoji} {text}...", 
                             f"{emoji} {text}....", 
                             f"{emoji} {text}....."]
        else:
            # Use the default animations
            self.animation = self._get_random_animation()
        
        logger.info(f"Created loading animation for command '{self.command_name}'")
    
    def _get_random_animation(self) -> List[str]:
        """Get a random animation sequence specifically for this command"""
        # First try to get command-specific animations
        if self.command_name in COMMAND_ANIMATIONS:
            # Use animations specifically for this command
            return random.choice(COMMAND_ANIMATIONS[self.command_name])
        
        # Fallback to general animations if no specific ones exist
        return random.choice(COMMAND_ANIMATIONS["general"])
    
    async def start(self) -> discord.Message:
        """Start the loading animation"""
        if self.running:
            logger.warning(f"Animation for command '{self.command_name}' already running")
            return self.message
        
        self.running = True
        
        # Send initial message
        try:
            self.message = await self.ctx.send(self.animation[0])
            
            # Start animation task
            self.task = asyncio.create_task(self._animate())
            logger.info(f"Started animation for '{self.command_name}'")
            
            return self.message
        except Exception as e:
            logger.error(f"Error starting animation: {e}")
            self.running = False
            return None
    
    async def _animate(self) -> None:
        """Animate the loading message with frame updates"""
        frame_index = 0
        
        try:
            while self.running:
                # Cycle through animation frames
                frame_index = (frame_index + 1) % len(self.animation)
                self.frame_count += 1
                
                # Update the message
                await self.message.edit(content=self.animation[frame_index])
                logger.debug(f"Updated animation frame {self.frame_count} for {self.command_name}")
                
                # Wait before next frame
                await asyncio.sleep(DEFAULT_ANIMATION_INTERVAL)
        except asyncio.CancelledError:
            logger.info(f"Animation for '{self.command_name}' was cancelled")
        except Exception as e:
            logger.error(f"Error in animation loop: {e}")
            self.running = False
    
    async def stop(self, final_content: Optional[str] = None, final_embed: Optional[discord.Embed] = None) -> None:
        """Stop the animation and optionally update with final content or embed"""
        if not self.running:
            logger.warning(f"Attempted to stop non-running animation for '{self.command_name}'")
            return
        
        # Check if we need to wait for minimum frames
        if self.frame_count < self.min_frames:
            frames_remaining = self.min_frames - self.frame_count
            logger.info(f"Delaying stop to show at least {self.min_frames} frames (currently at {self.frame_count})")
            await asyncio.sleep(frames_remaining * DEFAULT_ANIMATION_INTERVAL)
        
        self.running = False
        
        if self.task and not self.task.done():
            self.task.cancel()
        
        try:
            if self.message:
                if final_content is not None and final_embed is not None:
                    await self.message.edit(content=final_content, embed=final_embed)
                elif final_content is not None:
                    await self.message.edit(content=final_content)
                elif final_embed is not None:
                    await self.message.edit(content=None, embed=final_embed)
                
                logger.info(f"Stopped animation for '{self.command_name}' after {self.frame_count} frames")
        except Exception as e:
            logger.error(f"Error stopping animation: {e}")

async def with_loading_animation(
    ctx: discord.ext.commands.Context,
    coro: Callable[..., Awaitable],
    *args,
    **kwargs
) -> Tuple[bool, Optional[Exception], any]:
    """
    Decorator-like function to run a coroutine with a loading animation
    
    Args:
        ctx: The command context
        coro: The coroutine to run
        *args, **kwargs: Arguments to pass to the coroutine
        
    Returns:
        Tuple of (success, exception, result)
    """
    animator = LoadingAnimator(ctx)
    await animator.start()
    
    try:
        result = await coro(*args, **kwargs)
        # If result is an embed, update with it
        if isinstance(result, discord.Embed):
            await animator.stop(final_embed=result)
        # If result is a string, update with it
        elif isinstance(result, str):
            await animator.stop(final_content=result)
        # If result is a tuple of (content, embed), update with both
        elif isinstance(result, tuple) and len(result) == 2:
            content, embed = result
            if isinstance(content, str) and isinstance(embed, discord.Embed):
                await animator.stop(final_content=content, final_embed=embed)
            else:
                await animator.stop()
        else:
            await animator.stop()
        
        return True, None, result
    except Exception as e:
        logger.error(f"Error in coroutine executed with loading animation: {e}")
        await animator.stop(final_content=f"❌ An error occurred: {str(e)}")
        return False, e, None