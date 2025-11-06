"""Central state manager for the Discord bot"""
from typing import Dict, Optional, List
import discord

class StateManager:
    def __init__(self):
        self.active_matches: Dict[int, 'MatchState'] = {}
        self.active_tryouts: Dict[int, Dict] = {}
        
    def get_active_match(self, user_id: int) -> Optional['MatchState']:
        """Get active match for a user (either as creator or participant)"""
        # Direct match check
        if user_id in self.active_matches:
            return self.active_matches[user_id]
            
        # Check if user is participant in any match
        for match in self.active_matches.values():
            if match.status == "in_progress":
                if user_id == match.creator.id or any(p.id == user_id for p in match.opponents):
                    return match
        return None
        
    def get_active_tryout(self, user_id: int) -> Optional[Dict]:
        """Get active tryout for a user"""
        return self.active_tryouts.get(user_id)
        
    def start_match(self, creator: discord.Member) -> 'MatchState':
        """Start a new match"""
        from bot import MatchState  # Import here to avoid circular imports
        match_state = MatchState(creator)
        self.active_matches[creator.id] = match_state
        return match_state
        
    def start_tryout(self, evaluator_id: int, member: discord.Member) -> Dict:
        """Start a new tryout"""
        tryout_state = {"member": member, "evaluation": None}
        self.active_tryouts[evaluator_id] = tryout_state
        return tryout_state
        
    def end_match(self, match_state: 'MatchState') -> None:
        """End a match and clean up its state"""
        if match_state.creator.id in self.active_matches:
            del self.active_matches[match_state.creator.id]
            
    def end_tryout(self, evaluator_id: int) -> None:
        """End a tryout and clean up its state"""
        if evaluator_id in self.active_tryouts:
            del self.active_tryouts[evaluator_id]

# Global instance
state_manager = StateManager()
