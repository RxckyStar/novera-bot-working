import sqlite3
import os
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._initialize_db()

    def _initialize_db(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS members (
                    user_id TEXT PRIMARY KEY,
                    value INTEGER
                )
            '''')
            self.conn.commit()
            logger.info("Database and table created successfully.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def ensure_member(self, member_id: str):
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO members (user_id, value)
                VALUES (?, 0)
            ''', (member_id,))
            self.conn.commit()
            logger.info(f"Member {member_id} ensured.")
        except Exception as e:
            logger.error(f"Error ensuring member {member_id}: {e}")

    def get_member_value(self, member_id: str) -> int:
        try:
            self.cursor.execute('''
                SELECT value FROM members
                WHERE user_id = ?
            ''', (member_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting member value for {member_id}: {e}")
            return 0

    def set_member_value(self, member_id: str, value: int):
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO members (user_id, value)
                VALUES (?, ?)
            ''', (member_id, value))
            self.conn.commit()
            logger.info(f"Set value for member {member_id} to {value}.")
        except Exception as e:
            logger.error(f"Error setting member value for {member_id}: {e}")

    def get_all_member_values(self) -> Dict[str, int]:
        try:
            self.cursor.execute('''
                SELECT user_id, value FROM members
            ''')
            return {row[0]: row[1] for row in self.cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error getting all member values: {e}")
            return {}

    def get_member_ranking(self, member_id: str) -> Tuple[int, int, int]:
        try:
            self.cursor.execute('''
                SELECT user_id, value FROM members
                ORDER BY value DESC
            ''')
            items = self.cursor.fetchall()
            total = len(items)
            member_value = self.get_member_value(member_id)
            for idx, (mid, _) in enumerate(items, start=1):
                if mid == member_id:
                    return idx, total, member_value
            return total + 1, total, member_value
        except Exception as e:
            logger.error(f"Error computing ranking for {member_id}: {e}")
            return 0, 0, 0

    def __del__(self):
        self.conn.close()

# Get the SQLite database path from the environment variable
DATABASE_PATH = os.getenv('SQLITE3.RAILWAY_VOLUME_MOUNT_PATH')
if not DATABASE_PATH:
    logger.error("SQLITE3.RAILWAY_VOLUME_MOUNT_PATH environment variable is not set.")
else:
    logger.info(f"Using database path: {DATABASE_PATH}")

# Initialize the DataManager with the database path
_DM = DataManager(f"{DATABASE_PATH}/database.db")

# Module-level helpers
def ensure_member(member_id: str) -> None:
    _DM.ensure_member(member_id)

def get_member_value(member_id: str) -> int:
    return _DM.get_member_value(member_id)

def set_member_value(member_id: str, value: int) -> None:
    _DM.set_member_value(member_id, value)

def get_all_member_values() -> Dict[str, int]:
    return _DM.get_all_member_values()

def get_member_ranking(member_id: str) -> Tuple[int, int, int]:
    return _DM.get_member_ranking(member_id)

def get_data_filename() -> str:
    return f"{DATABASE_PATH}/database.db"
