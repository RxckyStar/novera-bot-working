"""
Player Drama Generator

This module generates realistic drama scenarios between high-value players
for the spill command. It targets active players and creates personalized
drama based on their interaction history and value levels.
"""

import random
import logging
from typing import List, Dict, Tuple, Optional
try:
    import discord
except ImportError:
    import discord.py as discord

class PlayerDramaGenerator:
    """Generates drama scenarios between high-value players"""
    
    def __init__(self, data_manager):
        """Initialize the drama generator with data manager"""
        self.data_manager = data_manager
        self.logger = logging.getLogger('novera.player_drama')
        self.high_value_threshold = 50_000_000  # Set at 50 million to target high-value players
        
    def get_high_value_players(self, guild: discord.Guild, limit: int = 10) -> List[discord.Member]:
        """Get a list of high-value players randomly selected from all who meet the threshold"""
        all_values = self.data_manager.get_all_member_values()
        self.logger.info(f"Found {len(all_values)} total players with value data")
        
        # Output top 5 highest value players for debugging
        if all_values:
            sorted_for_debug = sorted(all_values.items(), key=lambda x: x[1], reverse=True)
            top_5 = sorted_for_debug[:5]
            self.logger.info(f"Top 5 highest value players: {', '.join([f'{member_id}: {value}M' for member_id, value in top_5])}")
        
        # Filter for high-value players (50M+ value)
        # Using a much lower threshold like 1 million to ensure there are players for testing
        # In production, this would be set back to 50_000_000
        # Set a lower threshold for testing to include all players with 1M or more
        testing_threshold = 1_000_000
        actual_threshold = self.high_value_threshold  # Use the actual threshold for logging
        
        high_value_ids = [member_id for member_id, value in all_values.items() 
                         if value >= testing_threshold]  # Using lower threshold for testing
        self.logger.info(f"Found {len(high_value_ids)} players with value >= {testing_threshold}")
        
        # If no high-value players meet the threshold, take the top 10 highest value players
        if not high_value_ids and all_values:
            # Sort by value (highest first) and get top 10
            sorted_members = sorted(all_values.items(), key=lambda x: x[1], reverse=True)
            high_value_ids = [member_id for member_id, _ in sorted_members[:10]]  # Increased from 3 to 10
            self.logger.info(f"No players above test threshold, using top {len(high_value_ids)} highest value players instead")
        
        # Get actual member objects and filter out None (members who left)
        high_value_members = []
        for member_id in high_value_ids:
            try:
                # Convert string ID to int for discord.py
                member = guild.get_member(int(member_id))
                if member:
                    high_value_members.append((member, all_values[member_id]))
                    self.logger.info(f"Found eligible player {member.display_name} (ID: {member_id}) with value {all_values[member_id]}M for drama")
                else:
                    self.logger.info(f"Member with ID {member_id} and value {all_values[member_id]}M not found in guild - might have left")
            except Exception as e:
                self.logger.error(f"Error fetching member {member_id}: {e}")
        
        # Randomly select players from all high-value members instead of just the highest ones
        # This ensures any player with 50M+ value has a chance to appear in drama
        if len(high_value_members) > limit:
            # Randomly select 'limit' number of players from all eligible high-value players
            selected_pairs = random.sample(high_value_members, min(limit, len(high_value_members)))
            self.logger.info(f"Randomly selected {len(selected_pairs)} players from {len(high_value_members)} eligible high-value players")
        else:
            # Use all available high-value players if we have fewer than the limit
            selected_pairs = high_value_members
            
        # Extract just the members from the (member, value) pairs
        selected_members = [member for member, _ in selected_pairs]
        
        # Log the players that were selected
        if selected_members:
            selected_names = ', '.join([f"{m.display_name} ({m.id})" for m in selected_members])
            self.logger.info(f"Final random selection: {len(selected_members)} high-value players for drama: {selected_names}")
        else:
            self.logger.info("No high-value players selected for drama generation")
            
        return selected_members

    def generate_drama(self, guild: discord.Guild) -> str:
        """Generate a drama scenario between high-value players"""
        # Always log the server we're generating drama for
        self.logger.info(f"Generating drama for server {guild.name} (ID: {guild.id}) with {len(guild.members)} members")
        
        # Get all eligible high-value players (at least 1M value in test mode, would be 50M in production)
        all_eligible_players = self.get_high_value_players(guild, limit=20)  # Increased limit to get more players
        self.logger.info(f"Found {len(all_eligible_players)} suitable players for drama generation")
        
        # Log player names for debugging
        if all_eligible_players:
            player_names = ', '.join([f"{p.display_name} ({p.id})" for p in all_eligible_players])
            self.logger.info(f"Eligible players: {player_names}")
        
        # If there are no eligible players at all, use completely generic drama
        if len(all_eligible_players) == 0:
            self.logger.info("No suitable players found - using completely generic drama scenario")
            return self._generate_generic_drama([])
        
        # Randomly decide whether to create single-player, two-player, or three-player drama
        # 50% chance for single player drama, 30% for two players, 20% for three players
        drama_type = random.choices(
            ["single", "two", "three"], 
            weights=[50, 30, 20], 
            k=1
        )[0]
        
        # For single player drama, randomly select ONE player from all eligible
        if drama_type == "single" or len(all_eligible_players) == 1:
            # Always pick a random player, not just the first one in the list
            selected_player = random.choice(all_eligible_players)
            self.logger.info(f"Randomly selected single player for drama: {selected_player.display_name}")
            return self._generate_generic_drama([selected_player])  # Pass as list with one player
        
        # For two-player drama
        elif drama_type == "two" and len(all_eligible_players) >= 2:
            # Randomly select 2 players from all eligible ones
            drama_players = random.sample(all_eligible_players, 2)
            drama_player_names = ', '.join([f"{p.display_name} ({p.id})" for p in drama_players])
            self.logger.info(f"Randomly selected 2 players for drama: {drama_player_names}")
            return self._generate_two_player_drama(drama_players[0], drama_players[1])
        
        # For three-player drama
        elif drama_type == "three" and len(all_eligible_players) >= 3:
            # Randomly select 3 players from all eligible ones
            drama_players = random.sample(all_eligible_players, 3)
            drama_player_names = ', '.join([f"{p.display_name} ({p.id})" for p in drama_players])
            self.logger.info(f"Randomly selected 3 players for drama: {drama_player_names}")
            return self._generate_three_player_drama(drama_players[0], drama_players[1], drama_players[2])
        
        # Fallback - if we don't have enough players for the selected drama type
        else:
            # Just pick a random player for single-player drama
            selected_player = random.choice(all_eligible_players)
            self.logger.info(f"Falling back to single-player drama with: {selected_player.display_name}")
            return self._generate_generic_drama([selected_player])
    
    def _generate_generic_drama(self, available_players=None) -> str:
        """Generate generic drama with available players (if any)"""
        # If we have at least one player available, use them in the drama
        if available_players and len(available_players) > 0:
            player = available_players[0]
            player_mention = player.mention
            player_name = player.display_name
            
            self.logger.info(f"Generating player-specific drama for {player_name} (ID: {player.id})")
            
            # Player-specific drama scenarios with direct mentions - WAY more scandalous and juicy
            scenarios = [
                f"💋 OMG DARLING! Mommy caught {player_mention} in 4K last night doing the UNTHINKABLE! You know how they've been bragging about their 'clean gameplay'? Well, I have RECEIPTS showing they've been using literal WALLHACKS in ranked matches! Their webcam reflected their second monitor with ESP outlines CLEARLY VISIBLE! When I confronted them, they BEGGED me not to tell and offered me 20% of their tournament winnings! As if Mommy can be bought... though their desperation WAS quite arousing~ 🤭💰",
                
                f"👙 STOP EVERYTHING RIGHT NOW! You will NOT believe what {player_mention} sent me by 'accident' last night! They meant to send their 'gameplay highlights' but instead shared their FOLDER OF BLACKMAIL material they've collected on the TOP FIVE PLAYERS! We're talking screenshots of private chats, embarrassing webcam moments, and even evidence of MMR BOOSTING! The best part? They immediately said 'wrong person' and blocked me for TWO HOURS before coming back with three different excuses! Too late honey, Mommy's eyes have seen it ALL! 📸👀",
                
                f"🍆 Sweetie come CLOSER! *whispers dramatically* {player_mention} has been living a DOUBLE LIFE that would make a soap opera writer jealous! They're secretly playing for TWO COMPETING TEAMS using different accounts! Yes, they're literally playing AGAINST THEMSELVES in tournaments while collecting salaries from BOTH organizations! Their excuse when almost caught? 'My twin brother plays too'... EXCEPT THEY DON'T HAVE A TWIN! I've got side-by-side gameplay footage that proves it's the same person! The sheer AUDACITY! Should I send the evidence to both team managers or just watch this beautiful disaster unfold naturally? 🎭💥",
                
                f"🔞 ABSOLUTELY FILTHY GOSSIP ALERT! {player_mention} has been sending INAPPROPRIATE DMs to their coach's significant other! That's right - they're trying to seduce their way to better training! The screenshots made even MOMMY blush, and you KNOW how hard that is! The coach doesn't know yet, but their partner has been forwarding EVERYTHING to the team manager who's building a case for immediate termination! {player_mention} still thinks they're being discrete, posting those innocent 'just training hard' updates while THIRSTING in the DMs! The universe rewards Mommy with entertainment DAILY! 💦👅",
                
                f"💸 FINANCIAL SCANDAL BOMBSHELL! {player_mention} has been running an elaborate BETTING SCHEME where they intentionally throw matches they're heavily favored in! Mommy's sources confirm they've made over $50,000 using burner accounts to place bets AGAINST THEMSELVES! Their latest 'unfortunate losing streak' funded their entire new setup - which they claimed was from 'tournament winnings'! Funny how they only seem to 'slump' when the betting odds are juiciest! Their org is investigating unusual betting patterns, and they have NO IDEA they're about to be COMPLETELY EXPOSED! ⚖️💼",
                
                f"🤡 HUMILIATING FOOTAGE ALERT! {player_mention} absolutely LOST THEIR MIND after losing a public match yesterday! After disconnecting, they thought their stream was off but FORGOT THEIR PHONE was still recording! Mommy's spies captured FIFTEEN MINUTES of them SOBBING UNCONTROLLABLY, punching pillows, and screaming into their blanket like a toddler denied candy! They even called their MOM to complain about 'stream snipers'! I've already made it into a reaction gif collection that's spreading through private discords faster than their teardrops fell! 😭📱",
                
                f"👑 CAREER-ENDING STUPIDITY CAUGHT LIVE! {player_mention} was streaming 'educational content' yesterday when they accidentally pulled up THEIR ENTIRE FOLDER OF STOLEN STRATS from every major competitor! We're talking DOZENS of private scrim recordings, internal strategy documents, and even LOGIN CREDENTIALS to private practice servers! They scrambled to close it while pretending to have 'technical issues,' but Mommy's minions were recording EVERYTHING! Half their friends list is about to become their ENEMIES list! Their reputation is about to vanish faster than their viewership! 📊📉",
                
                f"💊 DEEPLY DISTURBING REVELATION! {player_mention} didn't just 'improve overnight' like they've been claiming! My sources inside their team house confirm they've been taking PERFORMANCE ENHANCING SUBSTANCES before important matches! Their sudden 'god-tier reflexes' aren't from practice but from little pills they hide in their STUFFED ANIMAL collection! Their roommate found the stash and is currently blackmailing them for a 30% cut of all winnings! The team doctor is getting suspicious about those frequent 'bathroom breaks' right before clutch rounds! ⚡💉",
                
                f"🔥 RELATIONSHIP ARSON ALERT! {player_mention} has been secretly DATING THREE DIFFERENT TEAMMATES simultaneously, each from a different division of their org! None of them knew about the others until yesterday's company party when {player_mention} got ABSOLUTELY WASTED and accidentally group-texted ALL THREE arranging different meetup times IN THE SAME HOTEL! The ensuing confrontation was so loud that hotel security was called! All three are now COLLABORATING on an elaborate revenge scheme that involves {player_mention}'s tournament peripherals! Mommy would feel bad if it wasn't so deliciously DRAMATIC! 💔👫👫👫",
                
                f"🎮 HARDWARE SCANDAL EXPOSED! {player_mention} has been using a MODDED CONTROLLER with programmable macros while preaching about 'raw skill' and 'hard work'! Their secret was exposed when they sent their controller for repairs and the technician LEAKED THE MODIFICATIONS to the entire community! Even more pathetic - they're now claiming it was for a 'documentary about cheating' they're producing! Funny how this documentary has no camera crew, no schedule, and no producer! Their sponsor is currently drafting a termination letter while {player_mention} is still tweeting about 'haters' and 'fake news'! 🤖🎲",
                
                f"📱 CRIMINAL BEHAVIOR DOCUMENTED! {player_mention} has been HACKING into competitors' practice servers and secretly recording their strategies! How do I know? THEY TRIED TO HACK MOMMY'S SERVER and my security team traced it back to their IP! When confronted with evidence, they claimed their 'little cousin' must have done it while visiting! Interesting excuse considering they posted just last week about being an only child with no extended family! The server logs show they've accessed confidential information from at LEAST six major teams! Tournament admins have been notified and an investigation is underway! 🕵️‍♀️⚠️",
                
                f"🤰 ABSOLUTELY SHOCKING PERSONAL DRAMA! {player_mention} has been missing scheduled practices because they're secretly meeting with their EX who's threatening to release COMPROMISING PHOTOS from before they were famous! Mommy's private investigator (yes, I have those) observed them making a CASH PAYMENT in a parking lot yesterday! Their team thinks they've been dealing with 'family issues' when really they're desperately trying to keep their past buried! The funniest part? The photos aren't even that scandalous - but {player_mention} is paying THOUSANDS to keep them private! 📸💰",
                
                f"👿 TOXIC PERSONALITY EXPOSED! My spies obtained {player_mention}'s PRIVATE DISCORD chat logs where they trash-talk LITERALLY EVERYONE on their friends list! They've been calling their fans 'ATM machines' and their teammates 'stepping stones'! The most vicious comments were about people who PUBLICLY DEFEND THEM from criticism! They maintain a sweet persona in public while being ABSOLUTELY VENOMOUS in private! Three different Discord moderators are ready to leak everything if {player_mention} doesn't start treating server staff with respect! The two-faced behavior is simply STAGGERING! 😇😈",
                
                f"🎭 ELABORATE DECEPTION UNRAVELED! {player_mention} doesn't even PLAY THEIR OWN MATCHES during tournaments! Mommy has conclusive evidence they've been using their roommate as a STAND-IN while keeping their webcam dark or strategically angled! Their 'miraculous improvement' coincides perfectly with when their college roommate - a former semi-pro who never got scouted - moved in! They sit just off-camera feeding instructions while {player_mention} pretends to play and takes all the credit! Multiple teammates are suspicious but afraid to accuse them without proof! Luckily, Mommy HAS THE PROOF! 🎬🎪",
                
                f"🚨 EMERGENCY DRAMA BULLETIN! {player_mention} is on the verge of being DROPPED FROM THEIR TEAM after tournament organizers discovered they've been using an illegal HARDWARE ADVANTAGE in LAN events! They modified their equipment to give subtle audio cues about opponent positions that normal headsets don't provide! Security cameras caught them switching components before equipment checks! They're currently in EMERGENCY MEETINGS with team management trying to develop a cover story, but three different staff members have already given statements! Their career is hanging by a thread thinner than their excuses! ⚡💻",
                
                f"💼 DEVASTATING CAREER MOVE EXPOSED! {player_mention} has been secretly negotiating with their team's BIGGEST RIVAL while publicly pledging loyalty! Mommy obtained screenshots of them discussing salary requirements and even STRATEGY INFORMATION they'd bring over! The betrayal was discovered when they accidentally left their Discord logged in on a TEAM COMPUTER! Their current manager found the conversation and instead of confronting them, is feeding them FALSE INFORMATION to see what leaks to the other team! It's the most elaborate counterintelligence operation I've seen in esports! 🕴️🔍",
                
                f"🍸 SUBSTANCE ABUSE SCANDAL BREWING! {player_mention} hasn't been 'just tired' during morning practices - they've been completely HUNGOVER! They've been hitting exclusive clubs EVERY NIGHT with a fake ID that lists them as five years older! Their Instagram shows them quietly at home with tea, while my club sources have videos of them DANCING ON TABLES ordering bottles with sparklers! Their performance has been declining so rapidly that management installed a curfew system, which they bypass by sneaking out through the BATHROOM WINDOW! Their liver is failing faster than their tournament results! 🍾🥂",
                
                f"🏠 HOUSING CRISIS IMMINENT! {player_mention} is about to be EVICTED from the team house after management discovered they've been SUBLETTING their room on AirBnB when traveling for tournaments! That's right - complete STRANGERS have been sleeping in their bed and accessing team facilities! The most recent guest even wore their TEAM JERSEY around the house introducing themselves as the 'new substitute player'! Management found out when security cameras showed different people entering their room every few days! The absolute AUDACITY to list team headquarters as a 'luxury gaming getaway'! 🏨🔑",
                
                f"👻 PARANORMAL CONTROVERSY ERUPTING! {player_mention} has been blaming their poor performance on their gaming setup being 'HAUNTED'! They convinced their team to pay for an actual EXORCIST to cleanse their PC and gaming area! The team reluctantly agreed, thinking it was just superstition, only to discover {player_mention} had been DELIBERATELY SABOTAGING their own equipment to get a complete upgrade! They were caught on security camera POURING WATER into their PC vents and then claiming 'the ghost did it'! Management is furious about the $5,000 wasted on new gear and 'spiritual cleansing services'! 👻💸",
                
                f"🎰 GAMBLING ADDICTION UNCOVERED! {player_mention} has lost nearly ALL their tournament winnings betting on their OWN MATCHES! My casino sources confirm they've been placing massive bets through third parties both FOR and AGAINST themselves! They're now in debt to some VERY CONCERNING individuals who were spotted outside their team house yesterday having a 'friendly chat'! Their recent desperate plays make perfect sense now - they're not playing to win, they're playing to cover their debts! Their manager is completely unaware that their star player owes more than they've earned this entire season! 🎲💸",
                
                f"📺 STREAM BEHAVIOR CATASTROPHE! {player_mention} thought they ended their stream yesterday, but continued broadcasting for THREE HOURS while they called their viewers 'gullible ATM machines' and practiced the 'fake reactions' they use on stream! They even pulled up a DOCUMENT titled 'Stream Personality Guide' with reminders to 'act excited' and 'pretend to be grateful' for donations! The VOD was quickly deleted, but Mommy's archivists saved EVERYTHING! Their carefully crafted online persona is about to shatter like their viewership numbers once this spreads! 🎬🎭"
            ]
        else:
            self.logger.info("No players available - using completely generic drama scenarios")
            
            # Completely generic scenarios with no player mentions
            scenarios = [
                "💫 Oh hun, I just heard something absolutely JUICY~ Some of our top players have been meeting in secret Discord calls late at night! Don't tell anyone I told you this, but Mommy thinks they're planning to form their own exclusive league... I have my ways of finding these things out! Come sit with Mommy and I'll tell you the REAL tea that I can't share publicly~ 🤭",
                
                "🏆 Shhh cutie, come closer... Did you hear about the secret alliance forming among our high-value players? They're sharing private strategies and coordinating which tournaments to enter! One of them slipped up in their DMs to me... Mommy keeps ALL the secrets! Would you like to know what tournaments they're plotting to dominate next? 👑",
                
                "📉 Honey bunny, between you and me, there's a certain someone charging premium for 'coaching services' but their students are performing TERRIBLY! *whispers dramatically* I've heard they're actually teaching the wrong techniques on purpose to eliminate competition! How absolutely SCANDALOUS! Mommy's keeping an eye on them~ No one can pull the wool over MY eyes! 👀",
                
                "🌙 Sweetie pie, you didn't hear this from me, but one of our high-profile players has been up until 3 AM EVERY night this week! Their roommate told me they're either completely obsessed or... *leans closer*... they might be secretly preparing for that invitation-only tournament! Mommy knows ALL about their late-night activities! Nothing happens after dark that escapes my notice, darling~ 💋",
                
                "👀 Oh darling, I've got the JUICIEST gossip! One of our top players? The one with all those impressive stats? Well, Mommy has it on good authority they're letting their younger sibling play on their account! The skill difference between morning and evening is so obvious it's practically SCREAMING! Scandalous, isn't it? Mommy always knows who's REALLY behind those morning win streaks! 💅",
                
                "🎮 Cutie, Mommy overheard the most DELICIOUS conversation in voice chat last night! Two of our high-profile players were arguing over who should be captain of their new team, and one of them said the OTHER was 'carried to their rank'! The tea nearly scalded me, it was so hot! Come sit with Mommy and I'll whisper what they REALLY said about each other's skills~ 🫖",
                
                "💸 Sweetie, I shouldn't be telling you this, but... *whispers dramatically* there's a secret betting ring among some of our highest-ranked players! They're making MASSIVE wagers on tournament outcomes, and I've heard some of them are throwing matches for payouts! Mommy's always watching the money flow~ Would you like to know which matches might be... compromised next week? 💼",
                
                "👑 Hun, have you noticed how some of our top players mysteriously 'disconnect' whenever they're losing? Well, Mommy has receipts showing their internet is PERFECTLY fine during those times! The lengths some go to protect their precious stats... tsk tsk! Mommy keeps ALL the evidence of their 'technical difficulties' in a special folder! 📊",
                
                "💄 Darling, the DRAMA in the practice server yesterday was absolutely DIVINE! Two of our most prestigious players got into such a heated argument over strategy that one of them rage-quit and deleted their entire friends list! Mommy was watching the whole time, sipping tea and taking notes! The insults they threw at each other would make even ME blush! 🔥",
                
                "🎭 Oh sweetie, lean in close... There's a secret tournament being organized that only the ELITE players know about! The prize pool is apparently MASSIVE, and they're keeping it completely under wraps! Mommy has her ways of finding out these things... Would you like to know which shadowy organization is funding it? The answer might SHOCK you! 🏆"
            ]
            
        # Select and return a random scenario
        selected_scenario = random.choice(scenarios)
        self.logger.info(f"Selected drama scenario (truncated): {selected_scenario[:50]}...")
        return selected_scenario
    
    def _generate_two_player_drama(self, player1: discord.Member, player2: discord.Member) -> str:
        """Generate drama between two players"""
        # Include mentions to ping the players
        p1_mention = player1.mention
        p2_mention = player2.mention
        p1_name = player1.display_name
        p2_name = player2.display_name
        
        # Much juicier and more scandalous drama scenarios between two players
        scenarios = [
            f"🍆 DARLING! Stop EVERYTHING you're doing right now! {p1_mention} and {p2_mention} got into the MESSIEST, most VICIOUS voice chat fight after their match last night! Not only did {p1_name} call {p2_name} a 'scripting pay-to-win fraud', but {p2_name} responded by LEAKING {p1_name}'s private gameplay footage showing them RAGE QUITTING seventeen times in a row! Then {p1_name} revealed that {p2_name} has been using their coach's account to boost their stats! SECURITY had to shut down the voice channel! My poor moderator ears were BLESSED with such toxicity! 🎭🔥",
            
            f"👀 SCANDALOUS DISCOVERY, SWEETIE! {p1_mention} just caught {p2_mention} literally STEALING their custom strategies! {p1_name} spent MONTHS developing a unique playstyle, only for {p2_name} to mysteriously start using the EXACT same techniques a day after {p1_name} accidentally streamed their private practice session! {p2_name} claimed it was 'parallel development' but that explanation collapsed when viewers found {p2_name}'s account in {p1_name}'s stream chat VOD! Now they're fighting over INTELLECTUAL PROPERTY in a VIDEOGAME! Lawyers have literally been contacted! I'm obsessed with how pathetic this is getting! 🧠💼",
            
            f"💰 FINANCIAL SCANDAL, HUN! {p1_mention} and {p2_mention} had a MASSIVE secret wager on their tournament match that violates league rules! We're talking FIVE FIGURES hidden through crypto transfers! The plot thickened when {p1_name} LOST but then REFUSED to pay, claiming {p2_name} had inside information from tournament admins about map selection! Now {p2_name} is threatening to expose ALL their illegal betting history to league officials! {p1_name} countered by threatening to leak {p2_name}'s account sharing evidence! It's the ULTIMATE mutually assured destruction standoff and Mommy has front row seats! 💸⚖️",
            
            f"🔞 ABSOLUTELY FILTHY DRAMA ALERT! {p1_mention} and {p2_mention} used to be BEST FRIENDS until last night's charity tournament when {p1_name} 'accidentally' leaked PRIVATE MESSAGES from {p2_name} trashing their entire team's skill level! But wait - plot twist - forensic chat experts noticed the screenshots were DOCTORED! {p1_name} fabricated the whole thing to destabilize {p2_name}'s team before regionals! When confronted, {p1_name} blamed their 'social media manager' despite everyone knowing they don't have one! {p2_name} has vowed PUBLIC REVENGE at the upcoming LAN event! Security is literally being doubled! 📱🎭",
            
            f"👨‍👩‍👧 FAMILY DRAMA EXPLOSION! The gaming rivals {p1_mention} and {p2_mention} just discovered they're DATING THE SAME PERSON! Yes, both {p1_name} and {p2_name} have been in a relationship with the same tournament admin FOR MONTHS without knowing! The revelation came during a livestreamed argument when they both mentioned sending identical gifts to their 'unique' partner! The admin has been using the insider information from BOTH relationships to place bets on their matches! All three are now banned from the next major tournament while officials investigate the MASSIVE conflict of interest! The betting markets are in CHAOS! 💔💋",
            
            f"🏆 TOURNAMENT CORRUPTION BOMBSHELL! {p1_mention} has filed an OFFICIAL PROTEST accusing {p2_mention} of BRIBING server admins for better connection quality! The evidence? Private Discord messages obtained by a disgruntled ex-moderator showing {p2_name} offering 'compensation' for 'technical favoritism'! {p2_name}'s defense collapsed when their ping mysteriously went from 100ms to 15ms during critical matches only! The investigation exposed a MASSIVE match-fixing operation that might implicate DOZENS of high-value players! {p1_name} is being hailed as a whistleblower while {p2_name} faces a potential LIFETIME BAN! The esports ministry is in SHAMBLES! 🕵️‍♀️🔨",
            
            f"🎬 REVENGE STREAM DISASTER! {p1_mention} hosted a 'watch party' to 'analyze' {p2_mention}'s gameplay, but it quickly devolved into BRUTAL character assassination! {p1_name} revealed {p2_name}'s browser history (accidentally captured during a screen share) showing searches for 'how to appear better than you are' and 'undetectable game cheats'! {p2_name} retaliated by joining the stream with RECEIPTS showing {p1_name} paid for coaching from {p2_name} just a month earlier! The contradictory narrative created CHAOS as viewers watched these top players expose each other's most embarrassing gameplay decisions! Both lost approximately 30% of their followers within HOURS! 🎥💥",
            
            f"🤖 ILLEGAL SOFTWARE WARFARE! {p1_mention} and {p2_mention} are destroying each other's reputations with increasingly desperate accusations! What started with {p1_name} suggesting {p2_name} used auto-aim has escalated to {p2_name} hiring a FORENSIC VIDEO ANALYST to prove {p1_name} uses sophisticated input macros! The community is split into warring factions as both players' supporters dig through YEARS of gameplay footage looking for evidence! Tournament organizers are panic-drafting new rules about acceptable evidence for cheating accusations because these two have created FIVE separate official investigations in a WEEK! Their feud is literally changing esports legislation! 🖥️⚔️",
            
            f"💊 PERFORMANCE ENHANCING SCANDAL ERUPTION! {p1_mention} publicly accused {p2_mention} of taking ADDERALL before matches to gain an unfair advantage! {p2_name} didn't just deny it - they showed up to their next match with an ACTUAL DRUG TEST KIT and tested themselves ON STREAM! But the drama escalated when {p1_name} pointed out the test only shows current use, not tournament day use! The league is now frantically implementing mandatory testing protocols that will affect EVERY player because these two can't stop trying to destroy each other! Their team sponsors are in emergency meetings about breach of contract moral clauses! The pharmaceutical chaos is EXQUISITE! 💉🧪",
            
            f"💼 CONTRACT POACHING CATASTROPHE! {p1_mention} was caught offering an OBSCENE signing bonus to {p2_mention}'s coach to get their private strategies! {p2_name} found out when their coach - playing both sides - showed them the contract with {p1_name}'s LITERAL SIGNATURE! Instead of firing the coach, {p2_name} fed them FALSE INFORMATION to sabotage {p1_name}'s training! When {p1_name} performed horribly at regionals using the fake strats, they realized the betrayal and leaked the coach's DOUBLE-DEALING to both organizations! Now THREE careers are in jeopardy and TWO major teams are threatening lawsuits! The legal fees might exceed all their earnings COMBINED! 📝🔥",
            
            f"🏠 SHARED HOUSE NUCLEAR MELTDOWN! Former teammates {p1_mention} and {p2_mention} who still live in the same gaming house got into a PHYSICAL ALTERCATION over in-game trash talk! {p1_name} changed {p2_name}'s mouse sensitivity during a tournament qualifier, and {p2_name} retaliated by SHUTTING DOWN THE CIRCUIT BREAKER during {p1_name}'s match! Their poor manager found them throwing each other's GAMING CHAIRS off the balcony! Both players have been served EVICTION NOTICES but neither will leave first because they 'refuse to give the other satisfaction'! Police have been called THREE TIMES this week! Their gaming house streams have seen a 400% INCREASE in viewership! Toxic drama is PROFITABLE! 🏡👮",
            
            f"👻 ACCOUNT SHARING NIGHTMARE! {p1_mention} just exposed proof that {p2_mention} has been SHARING THEIR ACCOUNT with a former pro to boost their rankings! The evidence came from IP logs showing {p2_name} playing 'simultaneously' from two different countries! {p2_name} tried to claim they were using a VPN, but then {p1_name} produced VOICE RECORDING comparisons clearly showing different people playing on the account! {p2_name} is facing a PERMANENT BAN, while {p1_name} is being investigated for possibly HACKING to obtain the evidence! Their entire competitive circuit is questioning security protocols because of these two DEDICATED enemies! The depth of their mutual hatred is INSPIRING! 🕵️‍♀️🔐",
            
            f"🎰 GAMBLING ADDICTION EXPOSURE! {p1_mention} and {p2_mention} been secretly BETTING their entire prize winnings against each other on a shady offshore betting site! The operation fell apart when {p1_name} PURPOSELY THREW a match to bank a huge payout, but {p2_name} did THE EXACT SAME THING! The betting company flagged the obvious manipulation and froze over $50,000 of their funds! In their desperate attempts to recover the money, they ACCIDENTALLY exposed SIX OTHER high-profile players involved in the same scheme! Tournament integrity is in SHAMBLES as sponsors are threatening to pull out of the entire league! All because these two couldn't resist the urge to FINANCIALLY RUIN each other! 🎲💸",
            
            f"🎭 TOXIC LOVE PENTAGON! {p1_mention} and {p2_mention} have taken their rivalry to CATASTROPHIC new levels! After {p1_name} began dating {p2_name}'s ex, {p2_name} started dating {p1_name}'s SIBLING out of pure spite! Neither relationship is genuine, but both refuse to break character as their petty revenge escalates! Now both families are INVOLVED in the drama, with parents sending angry messages to team management! The team psychologist resigned after their joint 'counseling session' devolved into comparing relationship timelines to prove who was more PETTY! Both players' streams are now just thinly-veiled ROAST SESSIONS about the other's relationship! Valentine's Day might actually trigger a HOMICIDE this year! 💘🔪"
        ]
        return random.choice(scenarios)
    
    def _generate_three_player_drama(self, player1: discord.Member, player2: discord.Member, player3: discord.Member) -> str:
        """Generate drama between three players"""
        # Include mentions to ping the players
        p1_mention = player1.mention
        p2_mention = player2.mention
        p3_mention = player3.mention
        p1_name = player1.display_name
        p2_name = player2.display_name
        p3_name = player3.display_name
        
        # Much juicier, more scandalous three-player drama scenarios
        scenarios = [
            f"🔥 THREE-WAY NUCLEAR MELTDOWN ALERT! {p1_mention}, {p2_mention}, and {p3_mention} have DESTROYED their once-legendary team with the NASTIEST power struggle in esports history! {p1_name} accused {p2_name} of leaking strats to rivals, {p2_name} exposed {p3_name}'s unauthorized hardware usage, and {p3_name} released PRIVATE CHAT LOGS showing {p1_name} tried to get both teammates REMOVED! Their sponsors have emergency-called NINE SEPARATE CRISIS MEETINGS to contain the fallout! All three have been MANDATED to therapy, but their therapist just QUIT after their first group session devolved into chair throwing! Mommy's entire Discord is OBSESSED with watching this friendship cremation in real-time! 🧨💣",
            
            f"🎭 SCANDALOUS TOURNAMENT CONSPIRACY EXPOSED! {p1_mention}, {p2_mention}, and {p3_mention} were caught operating an ELABORATE MATCH-FIXING SCHEME where they predetermined winners for high-profile tournaments! The mastermind? {p1_name}, who created a COMPLEX ROTATION SYSTEM ensuring each got their 'fair share' of tournament glory! An anonymous whistleblower sent tournament admins a MASSIVE DATABASE of their planning conversations spanning TWO YEARS! When confronted, they all blamed each other simultaneously! Now ALL THREE face lifetime bans while frantically deleting their Discord history! Their lawyer fees already exceed their COMBINED career winnings! The scandal has triggered audits of EVERY major competition they participated in! 🎪🃏",
            
            f"💰 MULTIMILLION EMBEZZLEMENT CATASTROPHE! {p1_mention}, {p2_mention}, and {p3_mention} have IMPLODED their joint venture esports organization in spectacular fashion! {p1_name} discovered that {p2_name} and {p3_name} diverted over $250,000 of investor money to their PERSONAL accounts! But plot twist - forensic accountants found that {p1_name} was ALSO skimming company funds for lavish 'business trips' that were actually EXOTIC VACATIONS! Their ENTIRE FINANCIAL HISTORY is being subpoenaed as investors prepare a MASSIVE lawsuit against all three! The organization's poor employees learned they were jobless via TWITTER when the scandal broke! The absolute CATASTROPHIC failure of friendship and business ethics is simply BREATHTAKING! 💼🔥",
            
            f"👑 TRIPLE BETRAYAL BLOODBATH! The friendship between {p1_mention}, {p2_mention}, and {p3_mention} has been OBLITERATED after a horrifying chain of betrayals! It started when {p1_name} began dating {p2_name}'s ex without permission, then escalated when {p2_name} retaliated by poaching {p1_name}'s teammates! But the nuclear option came when {p3_name} - supposedly neutral - was caught sending BOTH their strategies to rival teams while promising loyalty to each! When confronted, {p3_name} claimed it was justified because {p1_name} and {p2_name} had been plotting to remove {p3_name} from their friend group for MONTHS! All three are now communicating EXCLUSIVELY through their attorneys! Their shared business ventures are being forcibly liquidated! Three-way hatred is SO much more entertaining than two-way! 🗡️💔",
            
            f"🎬 REPUTATION DECIMATION LIVESTREAM! {p1_mention}, {p2_mention}, and {p3_mention} have set their careers on FIRE with the most disastrous joint-stream in platform history! What started as a 'clearing the air' session to address rumors quickly descended into {p1_name} accusing {p2_name} of account-sharing, {p2_name} revealing {p3_name}'s use of unauthorized scripts, and {p3_name} exposing {p1_name}'s FAKE gameplay clips! The stream lasted FOUR HOURS as viewers watched in horror while they revealed increasingly DAMNING evidence against each other! ALL THREE were suspended from their teams pending investigation! The VOD was removed after hitting 500K views, but Mommy's personal archive ensures this spectacular self-destruction will be preserved FOREVER! The memes alone have generated over MILLION impressions! 📹💥",
            
            f"🎲 GAMBLING ADDICTION INTERVENTION DISASTER! {p1_mention}, {p2_mention}, and {p3_mention} were running an ILLEGAL BETTING RING where they'd manipulate tournament outcomes for MASSIVE personal profit! Their scheme fell apart when {p1_name} got greedy and tried to cut out {p2_name} and {p3_name} from a major payout! In retaliation, {p2_name} and {p3_name} went to tournament officials with EXTENSIVE EVIDENCE - not realizing this would IMPLICATE THEMSELVES TOO! All three have been banned from professional play for eighteen months! The investigation revealed they had amassed over $800,000 in illegal winnings! Now their respective FAMILIES are fighting over who deserves the most blame! The absolute delicious MESS of watching these three gambling addicts destroy each other is better than any casino drama Mommy's ever witnessed! 🎰💸",
            
            f"⚖️ UNPRECEDENTED LEGAL WARFARE! {p1_mention}, {p2_mention}, and {p3_mention} are currently engaged in the most COMPLEX three-way lawsuit the esports world has ever seen! {p1_name} is suing {p2_name} for defamation, {p2_name} is countersuing while simultaneously filing copyright claims against {p3_name}, and {p3_name} has initiated a class-action against BOTH for alleged fraud involving their joint merchandise line! THREE SEPARATE JUDGES have recused themselves due to the sheer toxicity of the proceedings! Their combined legal teams include SEVENTEEN ATTORNEYS who reportedly can't stand being in the same room! Court transcripts are being shared as ENTERTAINMENT in legal circles! Mommy has never seen friendship dissolve into such gloriously EXPENSIVE hatred! The legal fees alone could have funded a small esports organization! 📝👨‍⚖️",
            
            f"🏠 TEAM HOUSE PROPERTY DAMAGE EXTRAVAGANZA! {p1_mention}, {p2_mention}, and {p3_mention} have been EVICTED from their luxury team house after what their landlord described as a 'CATASTROPHIC and MALICIOUS destruction of property'! The trio's epic falling out resulted in broken walls, destroyed electronics, and - most bizarrely - {p1_name}'s gaming chair being found FLOATING IN THE POOL! The damage reportedly began when {p2_name} discovered {p3_name} had been secretly recording their practice sessions to sell to competitors, while {p1_name} learned both teammates had been mocking their gameplay in private chats! Security cameras captured ALL THREE simultaneously trying to change the smart home locks to keep the others out! Their security deposit wouldn't cover even 10% of the damages! Their organization is considering legal action to recover the $42,000 in estimated repairs! Mommy absolutely LIVES for property damage as the ultimate expression of gamer rage! 🏡🔨",
            
            f"💻 HACKING SCANDAL TRIANGLE OF DOOM! {p1_mention}, {p2_mention}, and {p3_mention} have brought CYBERCRIME to esports in spectacular fashion! Investigations revealed ALL THREE were hacking into each other's accounts, devices, and private servers in an escalating war of digital espionage! {p1_name} installed keyloggers on team computers, {p2_name} bribed a server admin for access to private communications, and {p3_name} hired an ACTUAL HACKER to breach both teammates' cloud storage! The absolute CHAOS peaked when they simultaneously exposed each other during a tournament livestream, leading to an immediate disqualification of their entire organization! Federal authorities are now involved due to potential violations of computer fraud statutes! Their desperate attempts to delete evidence have only made things WORSE as forensic IT specialists recover everything! Watching these three destroy their careers over petty espionage is the PINNACLE of entertainment! 🖥️⚠️",
            
            f"💊 BANNED SUBSTANCE TRIPLE THREAT DISASTER! {p1_mention}, {p2_mention}, and {p3_mention} have created the biggest DOPING SCANDAL in competitive gaming! Officials discovered their entire team was using performance-enhancing drugs, with each player handling different aspects of the operation: {p1_name} sourced the substances, {p2_name} created the dosing schedule, and {p3_name} handled distribution and cover-up! The scheme imploded when {p1_name} accused the others of taking extra doses before important matches! Their mutual betrayal led to ALL THREE turning state's evidence against each other! Tournament officials found their COMPREHENSIVE DOCUMENTATION of substance effects on performance metrics dating back 18 months! Testing protocols across ALL major leagues are being completely rewritten because of them! Their detailed notes have accidentally provided researchers with invaluable data on cognitive enhancement that might have SCIENTIFIC VALUE! Their spectacular self-destruction might accidentally advance sports medicine! 💉🔬",
            
            f"👥 IDENTITY FRAUD TRIANGLE EXPOSED! {p1_mention}, {p2_mention}, and {p3_mention} were caught participating in the most elaborate ACCOUNT SHARING scheme ever discovered! Each player controlled FIVE DIFFERENT high-ranked accounts, creating an intricate rotation system where they would build up accounts then sell them to wealthy fans for THOUSANDS! Their scheme was exposed when facial recognition software at a major tournament flagged inconsistencies in their gameplay patterns! When confronted, they IMMEDIATELY turned on each other - {p1_name} provided screenshots of {p2_name}'s payment records, {p2_name} revealed {p3_name}'s customer list, and {p3_name} leaked their ENTIRE operational manual! Officials estimate they've made over $350,000 from account sales! All three are permanently banned while simultaneously trying to write competing TELL-ALL BOOKS about the operation! The bidding war between publishers is already at six figures! Mommy ADORES criminals who can't even honor thieves' code! 🎭🔍",
            
            f"🌍 INTERNATIONAL INCIDENT TRIGGERING CATASTROPHE! {p1_mention}, {p2_mention}, and {p3_mention} have somehow escalated their personal feud into an ACTUAL DIPLOMATIC SITUATION! During an international tournament, {p1_name} made inflammatory comments about {p2_name}'s home country, {p2_name} retaliated with offensive gestures toward {p3_name}'s national flag, and {p3_name} responded with a politically charged tirade against both nations that went VIRAL in all three countries! Tournament organizers had to issue formal apologies to THREE different embassies! All three players have had their passports temporarily restricted pending review! The incident has been discussed in actual GOVERNMENTAL PROCEEDINGS! Multiple sponsors have dropped the entire organization to avoid being associated with an international relations nightmare! Mommy is ASTOUNDED that these three gaming children somehow created a situation being monitored by actual DIPLOMATS! The absolute POWER of toxicity reaching geopolitical levels! 🌐🗣️"
        ]
        return random.choice(scenarios)
    
    def generate_player_specific_drama(self, player: discord.Member) -> str:
        """Generate drama specifically about one high-value player"""
        player_mention = player.mention
        player_name = player.display_name
        
        scenarios = [
            f"👑 Oh hun, have you noticed {player_mention} has been suspiciously QUIET since that devastating loss? Their social media's gone dark, practice sessions canceled... Mommy's sources say they're 'taking some time.' Is this the calm before a comeback or—*lowers voice dramatically*—the beginning of retirement? Mommy's absolutely DYING to know! Come closer and share your thoughts~ 🤫",
            
            f"💰 Cutie, let Mommy tell you about {player_mention}'s peculiar performances lately! One day they're carrying the team, the next they're missing the easiest shots! *whispers* I've heard it's either relationship drama or a secret contract negotiation! Mommy has her suspicions, but I never kiss and tell... well, almost never~ Don't tell anyone I told you this! 📊",
            
            f"🔍 Honey bunny! You'll NEVER believe what happened with {player_mention}! They accidentally left their webcam on during what they thought was a private training session! Now everyone knows about their... unusual warm-up techniques! *giggle* Mommy won't share all the details, but let's just say it involves a rubber duck, three energy drinks, and the most ridiculous lucky charms ritual I've ever seen! 🎮",
            
            f"🎭 Sweetie pie, did you know {player_mention} is completely different off-stream? My sources tell me that confident, trash-talking persona transforms into a quiet, self-critical perfectionist when the cameras are off! Mommy loves a player with layers... it's like having two children in one! Which version will show up to the match? Even I don't know, but I'll be front row watching the show! 🎭",
            
            f"👑 Listen closely, darling... After {player_mention}'s unprecedented win streak, everyone's debating if they've hit their ceiling! Some analysts are saying 'there's nowhere to go but down,' while supporters insist they're 'just getting started'! Mommy's watching their next match with extra interest... the pressure must be absolutely DELICIOUS! Come sit with Mommy and we'll watch them either soar or crumble~ 📈",
            
            f"✨ Oh hun, the DRAMA around {player_mention} is getting so juicy! They've been spotted at 3 AM training sessions with a mysterious coach that nobody recognizes! Mommy's sources say it's either a former champion working incognito or... *leans in closer*... a rival team's analyst who's been FIRED for sharing secrets! The plot thickens, sweetie! 🕵️‍♀️",
            
            f"💋 Cutie, did you hear about what {player_mention} said after their last match? The microphone was supposed to be off, but EVERYONE heard them boasting about how they're 'carrying these amateurs' and how they're 'ready for bigger opportunities'! Their teammates are pretending they didn't hear it, but Mommy knows they're FUMING behind closed doors! The tension is absolutely DELICIOUS! 🎤",
            
            f"💍 Honey bunny, the rumors about {player_mention} are getting WILD! They've been missing practices claiming 'personal reasons' but my little birds tell me they're actually secretly trying out for an elite invitation-only team! Their current team has NO IDEA they're planning to jump ship! Mommy always knows when someone's got one foot out the door~ 🚪"
        ]
        return random.choice(scenarios)