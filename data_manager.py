"""File operations and data management for the Discord bot"""
import json
import os
from typing import Dict, Any, List, Tuple
import logging
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, filename: str):
        self.filename = filename
        self._backup_data()  # Create backup before any operations
        self.data = self._load_data()

    def _backup_data(self) -> None:
        """Create a backup of the data file if it exists"""
        if os.path.exists(self.filename):
            backup_name = f"{self.filename}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            try:
                shutil.copy2(self.filename, backup_name)
                logger.info(f"Created backup of data file: {backup_name}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")

    def _load_data(self) -> Dict[str, Any]:
        """Load data from JSON file or create new if doesn't exist"""
        try:
            if os.path.exists(self.filename):
                logger.info(f"Loading data from {self.filename}")
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    # Ensure required structures exist
                    if "members" not in data:
                        logger.warning("No 'members' key found in file, creating it")
                        data["members"] = {}
                    if "activity" not in data:
                        logger.warning("No 'activity' key found in file, creating it")
                        data["activity"] = {}
                    logger.info(f"Loaded data file with {len(data['members'])} members and {len(data['activity'])} activity records")
                    logger.debug(f"Loaded data structure: {data}")
                    return data

            # If file doesn't exist, create new data structure
            logger.warning("Data file not found, creating new empty structure")
            return {"members": {}, "activity": {}}

        except Exception as e:
            logger.exception(f"Error loading data file: {e}")
            # Try to restore from backup
            self._restore_from_backup()
            # If restore fails, return empty structure
            logger.warning("Creating new empty data structure after error")
            return {"members": {}, "activity": {}}

    def _restore_from_backup(self) -> None:
        """Attempt to restore data from most recent backup"""
        try:
            # Find most recent backup
            backups = [f for f in os.listdir('.') if f.startswith(f"{self.filename}.") and f.endswith('.bak')]
            if backups:
                most_recent = max(backups)
                shutil.copy2(most_recent, self.filename)
                logger.info(f"Restored data from backup: {most_recent}")
            else:
                logger.warning("No backup files found for restoration")
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")

    def _save_data(self) -> None:
        """Save data to JSON file with backup"""
        try:
            # Create backup before saving
            self._backup_data()

            # Save merged data
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=4)
            logger.info(f"Saved data file with {len(self.data['members'])} members")
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def get_member_value(self, member_id: str) -> int:
        """Get member's value, returns 0 if not set"""
        try:
            value = self.data["members"].get(member_id, {}).get("value", 0)
            logger.debug(f"Retrieved value {value} for member {member_id}")
            return value
        except Exception as e:
            logger.error(f"Error getting member value: {e}")
            return 0

    def set_member_value(self, member_id: str, value: int) -> None:
        """Set member's value"""
        try:
            old_value = self.get_member_value(member_id)
            new_value = max(value, 0)  # Ensure value doesn't go below 0

            # Initialize member dictionary if it doesn't exist
            if member_id not in self.data["members"]:
                self.data["members"][member_id] = {}

            self.data["members"][member_id]["value"] = new_value
            self._save_data()
            logger.info(f"Updated value for member {member_id}: {old_value}m -> {new_value}m")
        except Exception as e:
            logger.error(f"Error setting member value: {e}")

    def get_member_data(self, member_id: str, key: str, default: Any = None) -> Any:
        """Get member's data for a specific key"""
        try:
            if member_id in self.data["members"]:
                return self.data["members"][member_id].get(key, default)
            return default
        except Exception as e:
            logger.error(f"Error getting member data for {member_id}.{key}: {e}")
            return default

    def set_member_data(self, member_id: str, key: str, value: Any) -> None:
        """Set member's data for a specific key"""
        try:
            if member_id not in self.data["members"]:
                self.data["members"][member_id] = {}
            self.data["members"][member_id][key] = value
            self._save_data()
            logger.info(f"Updated {key} for member {member_id}: {value}")
        except Exception as e:
            logger.error(f"Error setting member data for {member_id}.{key}: {e}")

    def update_activity(self, member_id: str, activity_type: str, count: int = 1) -> None:
        """Update member's activity"""
        if member_id not in self.data["activity"]:
            self.data["activity"][member_id] = {"messages": 0, "reactions": 0}

        self.data["activity"][member_id][activity_type] += count
        self._save_data()

    def get_activity(self, member_id: str) -> Dict[str, int]:
        """Get member's activity"""
        return self.data["activity"].get(member_id, {"messages": 0, "reactions": 0})
        
    def get_member_gold(self, member_id: str) -> int:
        """Get member's gold balance"""
        try:
            return self.get_member_data(member_id, "gold", 0)
        except Exception as e:
            logger.error(f"Error getting gold for member {member_id}: {e}")
            return 0
            
    def add_member_gold(self, member_id: str, amount: int) -> int:
        """Add gold to member's balance and return new total"""
        try:
            current_gold = self.get_member_gold(member_id)
            new_gold = current_gold + amount
            self.set_member_data(member_id, "gold", new_gold)
            logger.info(f"Updated gold for member {member_id}: {current_gold} -> {new_gold} ({'+' if amount >= 0 else ''}{amount})")
            return new_gold
        except Exception as e:
            logger.error(f"Error adding gold for member {member_id}: {e}")
            return self.get_member_gold(member_id)
            
    def get_member_ranking(self, member_id: str) -> Tuple[int, int, int]:
        """Get member's ranking"""
        try:
            # Get all members and their values
            member_values = [(mid, self.get_member_value(mid)) for mid in self.data["members"]]
            # Sort by value in descending order
            sorted_members = sorted(member_values, key=lambda x: x[1], reverse=True)

            # Find member's rank
            member_value = self.get_member_value(member_id)
            for rank, (mid, _) in enumerate(sorted_members, 1):
                if mid == member_id:
                    return rank, len(sorted_members), member_value

            # If member not found
            return len(sorted_members) + 1, len(sorted_members), member_value
        except Exception as e:
            logger.error(f"Error getting member ranking: {e}")
            return 0, 0, 0

    def get_all_member_values(self) -> Dict[str, int]:
        """Get all member values as a dictionary of member_id: value pairs"""
        try:
            logger.info("Attempting to retrieve all member values")
            logger.debug(f"Current data structure: {self.data}")

            if "members" not in self.data:
                logger.warning("No 'members' key found in data structure")
                return {}

            values = {
                member_id: self.get_member_value(member_id)
                for member_id in self.data["members"]
            }
            logger.info(f"Retrieved {len(values)} member values")
            logger.debug(f"Member values: {values}")
            return values
        except Exception as e:
            logger.exception(f"Error getting all member values: {e}")
            return {}

    def get_value_growth_3days(self) -> Dict[str, int]:
        """Get member value growth over the last 3 days"""
        # Placeholder implementation - could be enhanced with actual growth tracking
        try:
            values = self.get_all_member_values()
            # For now, return current values as growth (simulated)
            return values
        except Exception as e:
            logger.error(f"Error getting value growth: {e}")
            return {}
            
    def reset_member_gold(self, member_id: str) -> None:
        """Reset gold for a specific member to 0"""
        try:
            current_gold = self.get_member_gold(member_id)
            self.set_member_data(member_id, "gold", 0)
            logger.info(f"Reset gold for member {member_id} from {current_gold} to 0")
        except Exception as e:
            logger.error(f"Error resetting gold for member {member_id}: {e}")
            
    def reset_all_gold(self) -> int:
        """Reset gold for all members to 0 and return the count of members affected"""
        try:
            count = 0
            # Iterate through all members and reset their gold
            for member_id in self.data["members"]:
                if "gold" in self.data["members"][member_id] and self.data["members"][member_id]["gold"] != 0:
                    self.data["members"][member_id]["gold"] = 0
                    count += 1
            
            # Save the changes
            self._save_data()
            logger.info(f"Reset gold for {count} members to 0")
            return count
        except Exception as e:
            logger.error(f"Error resetting all member gold: {e}")
            return 0
            
    def get_all_member_gold(self) -> Dict[str, int]:
        """Get all members' gold amounts"""
        try:
            result = {}
            logger.info("Attempting to retrieve all member gold amounts")
            
            # Iterate over all members in the data
            for member_id, member_data in self.data["members"].items():
                # Get the gold value with default 0 if not set
                gold = member_data.get("gold", 0)
                # Add to results dictionary
                result[member_id] = gold
                
            logger.info(f"Retrieved {len(result)} member gold amounts")
            return result
        except Exception as e:
            logger.error(f"Error getting all member gold: {e}")
            return {}
