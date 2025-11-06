from datetime import datetime, timedelta
from typing import Dict
import logging
from data_manager import DataManager
from config import INACTIVITY_THRESHOLD_DAYS, VALUE_REDUCTION_AMOUNT, MINIMUM_VALUE

class ActivityTracker:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    async def track_message(self, member_id: str) -> None:
        """Track a message from a member"""
        try:
            self.data_manager.update_activity(member_id, "messages")
        except Exception as e:
            logging.error(f"Error tracking message for member {member_id}: {e}")

    async def track_reaction(self, member_id: str) -> None:
        """Track a reaction from a member"""
        try:
            self.data_manager.update_activity(member_id, "reactions")
        except Exception as e:
            logging.error(f"Error tracking reaction for member {member_id}: {e}")

    async def check_inactivity(self) -> Dict[str, dict]:
        """Check for inactive members and return their status"""
        inactive_members = {}
        try:
            for member_id in self.data_manager.data["members"]:
                activity = self.data_manager.get_activity(member_id)
                current_value = self.data_manager.get_member_value(member_id)

                if activity["messages"] == 0 and activity["reactions"] == 0:
                    potential_new_value = max(current_value - VALUE_REDUCTION_AMOUNT, MINIMUM_VALUE)
                    inactive_members[member_id] = {
                        "current_value": current_value,
                        "potential_new_value": potential_new_value,
                        "activity": activity
                    }

            return inactive_members
        except Exception as e:
            logging.error(f"Error checking inactivity: {e}")
            return {}