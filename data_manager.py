"""Unified Data Manager (singleton + helpers)
- Keeps your original DataManager class intact
- Exposes module-level functions used across the bot:
  get_member_value, set_member_value, get_member_ranking, get_all_member_values, ensure_member, etc.
- ALWAYS writes/reads the SAME member_data.json so all commands are consistent.
- Auto-commits to GitHub after every save so values survive Railway restarts.
"""

from __future__ import annotations
import json
import os
import shutil
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


# ---------- auto-commit helper ----------
def _git_commit_push(filename: str) -> None:
    """Auto-commit member_data.json to GitHub after every save."""
    try:
        os.system("git config user.name 'Novera-Bot'")
        os.system("git config user.email 'bot@novera.com'")
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run(["git", "commit", "-m", "auto-save values"], check=True)
        subprocess.run(["git", "push"], check=True)
        logger.info("Pushed member_data.json to GitHub")
    except Exception as e:
        logger.error(f"Git push failed: {e}")


# ---------- DataManager class ----------
class DataManager:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self._backup_data()
        self.data = self._load_data()

    # ---------- internal helpers ----------
    def _backup_data(self) -> None:
        if os.path.exists(self.filename):
            backup_name = f"{self.filename}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            try:
                shutil.copy2(self.filename, backup_name)
                logger.info(f"Created backup of data file: {backup_name}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")

    def _load_data(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "members" not in data:
                    data["members"] = {}
                if "activity" not in data:
                    data["activity"] = {}
                return data
            return {"members": {}, "activity": {}}
        except Exception as e:
            logger.exception(f"Error loading data file: {e}")
            # try to restore from newest backup
            try:
                backups = [
                    f for f in os.listdir(".")
                    if f.startswith(f"{self.filename}.") and f.endswith(".bak")
                ]
                if backups:
                    most_recent = max(backups)
                    shutil.copy2(most_recent, self.filename)
                    with open(self.filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "members" not in data:
                        data["members"] = {}
                    if "activity" not in data:
                        data["activity"] = {}
                    logger.info(f"Restored data from backup: {most_recent}")
                    return data
            except Exception as e2:
                logger.error(f"Failed to restore from backup: {e2}")
            # fall back to empty structure
            return {"members": {}, "activity": {}}

    def _save_data(self) -> None:
        try:
            self._backup_data()
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            logger.info(f"Saved data file with {len(self.data['members'])} members")
            _git_commit_push(self.filename)  # auto-push to GitHub
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    # ---------- public helpers ----------
    def ensure_member(self, member_id: str) -> None:
        if member_id not in self.data["members"]:
            self.data["members"][member_id] = {"value": 0}
            self._save_data()

    def get_member_value(self, member_id: str) -> int:
        self.data = self._load_data()  # always fresh
        try:
            return int(self.data["members"].get(member_id, {}).get("value", 0))
        except Exception:
            return 0

    def set_member_value(self, member_id: str, value: int) -> None:
        try:
            if member_id not in self.data["members"]:
                self.data["members"][member_id] = {}
            self.data["members"][member_id]["value"] = max(0, int(value))
            self._save_data()
        except Exception as e:
            logger.error(f"Error setting member value: {e}")

    def get_all_member_values(self) -> Dict[str, int]:
        try:
            return {mid: int(self.get_member_value(mid)) for mid in self.data["members"]}
        except Exception:
            return {}

    def get_member_ranking(self, member_id: str) -> Tuple[int, int, int]:
        try:
            items = [(mid, self.get_member_value(mid)) for mid in self.data["members"]]
            items.sort(key=lambda x: x[1], reverse=True)
            total = len(items)
            member_value = self.get_member_value(member_id)
            for idx, (mid, _) in enumerate(items, start=1):
                if mid == member_id:
                    return idx, total, member_value
            return total + 1, total, member_value
        except Exception as e:
            logger.error(f"Error computing ranking: {e}")
            return 0, 0, 0


# ---------- singleton ----------
_DEFAULT_FILE = os.environ.get("NOVERA_DATA_FILE", "member_data.json")
_DM: DataManager = DataManager(_DEFAULT_FILE)

# ---------- module-level helpers ----------
def ensure_member(member_id: str) -> None:
    _DM.ensure_member(member_id)

def get_member_value(member_id: str) -> int:
    return _DM.get_member_value(member_id)

def set_member_value(member_id: str, value: int) -> None:
    _DM.set_member_value(member_id, value)

def get_all_member_values() -> Dict[str, int]:
    return _DM.get_all_member_values()

def get_member_ranking(member_id: str):
    return _DM.get_member_ranking(member_id)

def get_data_filename() -> str:
    return _DEFAULT_FILE
