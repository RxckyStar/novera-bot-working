import sqlite3
import os
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, db_path: str) -> None:
        os.makedirs(db_path, exist_ok=True)          # ensure folder exists
        self.db_file = os.path.join(db_path, "bot.db")
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL") # safer concurrent access
        self._init_table()

    def _init_table(self) -> None:
        with self.conn:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS members (user_id TEXT PRIMARY KEY, value INTEGER)"
            )

    # ---------- CRUD ----------
    def ensure_member(self, user_id: str) -> None:
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO members(user_id,value) VALUES (?,0)", (user_id,))

    def get_member_value(self, user_id: str) -> int:
        cur = self.conn.execute("SELECT value FROM members WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else 0

    def set_member_value(self, user_id: str, value: int) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO members(user_id,value) VALUES (?,?)", (user_id, value))

    def get_all_member_values(self) -> Dict[str, int]:
        cur = self.conn.execute("SELECT user_id, value FROM members")
        return {uid: val for uid, val in cur.fetchall()}

    def get_member_ranking(self, user_id: str) -> Tuple[int, int, int]:
        cur = self.conn.execute("SELECT user_id, value FROM members ORDER BY value DESC")
        rows = cur.fetchall()
        total = len(rows)
        user_val = self.get_member_value(user_id)
        for rank, (uid, _) in enumerate(rows, 1):
            if uid == user_id:
                return rank, total, user_val
        return total + 1, total, user_val

# ---------- singleton ----------
_MOUNT_PATH = os.getenv("SQLITE3_RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("SQLITE3.RAILWAY_VOLUME_MOUNT_PATH")
if not _MOUNT_PATH:
    raise RuntimeError("SQLite volume mount path not found in env vars")

_DM = DataManager(_MOUNT_PATH)

# ---------- public API ----------
def ensure_member(uid: str) -> None:
    _DM.ensure_member(uid)

def get_member_value(uid: str) -> int:
    return _DM.get_member_value(uid)

def set_member_value(uid: str, value: int) -> None:
    _DM.set_member_value(uid, value)

def get_all_member_values() -> Dict[str, int]:
    return _DM.get_all_member_values()

def get_member_ranking(uid: str) -> Tuple[int, int, int]:
    return _DM.get_member_ranking(uid)

def get_data_filename() -> str:
    return _DM.db_file
