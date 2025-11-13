import sqlite3
import os
import pathlib
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# ---------- CONFIG ----------
_MOUNT = os.getenv("SQLITE3_RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("SQLITE3.RAILWAY_VOLUME_MOUNT_PATH")
if _MOUNT:
    os.makedirs(_MOUNT, exist_ok=True)
    _DB_FILE = pathlib.Path(_MOUNT) / "bot.db"
    logger.info("Persistent SQLite at %s", _DB_FILE)
else:
    _DB_FILE = ":memory:"
    logger.warning("SQLite mount missing – using in-memory DB (data will NOT persist)")
# ---------------------------


class DataManager:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(_DB_FILE, timeout=5, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_table()

    def _init_table(self) -> None:
        with self.conn:
            self.conn.execute("CREATE TABLE IF NOT EXISTS members (user_id TEXT PRIMARY KEY, value INTEGER)")

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
        # flush to disk **immediately**
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

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
_DM = DataManager()

# public API
ensure_member   = _DM.ensure_member
get_member_value = _DM.get_member_value
set_member_value = _DM.set_member_value
get_all_member_values = _DM.get_all_member_values
get_member_ranking    = _DM.get_member_ranking

# drop-in object for legacy bot.py
data_manager = _DM
