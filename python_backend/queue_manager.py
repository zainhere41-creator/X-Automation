import sqlite3
import logging
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class QueueManager:
    """Manage SQLite task database and queue operations."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                timeout=10.0,
                check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _init_database(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Check if tasks table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Migrate: add missing columns
            cursor.execute("PRAGMA table_info(tasks)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            migrations = [
                ("sheet_index", "INTEGER NOT NULL DEFAULT 0"),
                ("sheet_name", "TEXT NOT NULL DEFAULT ''"),
                ("community", "TEXT DEFAULT ''"),
            ]
            for col_name, col_def in migrations:
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Migration: added column {col_name}")
            
            conn.commit()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                sheet_index INTEGER NOT NULL DEFAULT 0,
                sheet_name TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                community TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                posted_at TEXT,
                error TEXT,
                CHECK (status IN ('pending', 'done', 'failed')),
                CHECK (profile_id > 0)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_profile_status ON tasks(profile_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_sheet ON tasks(sheet_index, status)")
        
        conn.commit()
        logger.info(f"Database initialized at {self.db_path}")
    
    def load_posts(self, sheets: list[dict], profiles: list[int]) -> int:
        """Load posts from sheets into queue with round-robin profile assignment."""
        if not sheets:
            logger.warning("No sheets to load")
            return 0
        
        if not profiles:
            raise ValueError("No profiles available")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM tasks")
        
        created_at = datetime.now().isoformat()
        total = 0
        
        for sheet in sheets:
            sheet_index = sheet["index"]
            sheet_name = sheet["sheet_name"]
            
            for i, post in enumerate(sheet["posts"]):
                profile_id = profiles[i % len(profiles)]
                cursor.execute("""
                    INSERT INTO tasks (profile_id, sheet_index, sheet_name, title, url, community, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (profile_id, sheet_index, sheet_name, post["title"], post["url"], post.get("community", ""), created_at))
                total += 1
        
        conn.commit()
        logger.info(f"Loaded {total} posts from {len(sheets)} sheets across {len(profiles)} profiles")
        return total
    
    def append_posts(self, sheets: list[dict], profiles: list[int]) -> int:
        """Append posts from new XLSX to existing queue. Continues sheet_index from last."""
        if not sheets:
            logger.warning("No sheets to append")
            return 0
        
        if not profiles:
            raise ValueError("No profiles available")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Find max existing sheet_index
        cursor.execute("SELECT COALESCE(MAX(sheet_index), -1) FROM tasks")
        max_sheet = cursor.fetchone()[0]
        next_sheet_index = max_sheet + 1
        
        created_at = datetime.now().isoformat()
        total = 0
        
        for sheet in sheets:
            sheet_name = sheet["sheet_name"]
            
            for i, post in enumerate(sheet["posts"]):
                profile_id = profiles[i % len(profiles)]
                cursor.execute("""
                    INSERT INTO tasks (profile_id, sheet_index, sheet_name, title, url, community, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (profile_id, next_sheet_index, sheet_name, post["title"], post["url"], post.get("community", ""), created_at))
                total += 1
            
            next_sheet_index += 1
        
        conn.commit()
        logger.info(f"Appended {total} posts from {len(sheets)} sheets (starting at sheet_index {max_sheet + 1})")
        return total
    
    def get_next_pending(self, profile_id: int) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, profile_id, sheet_index, sheet_name, title, url, community, status, created_at
            FROM tasks
            WHERE profile_id = ? AND status = 'pending'
            ORDER BY sheet_index ASC, id ASC
            LIMIT 1
        """, (profile_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_next_sheet_index(self) -> Optional[int]:
        """Get the next sheet_index that has pending tasks."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MIN(sheet_index) as next_sheet
            FROM tasks WHERE status = 'pending'
        """)
        
        row = cursor.fetchone()
        if row and row["next_sheet"] is not None:
            return row["next_sheet"]
        return None
    
    def get_tasks_for_sheets(self, sheet_indices: list[int]) -> list[dict]:
        """Get all pending tasks for given sheet indices."""
        if not sheet_indices:
            return []
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        placeholders = ",".join("?" * len(sheet_indices))
        cursor.execute(f"""
            SELECT id, profile_id, sheet_index, sheet_name, title, url, community, status, created_at
            FROM tasks
            WHERE sheet_index IN ({placeholders}) AND status = 'pending'
            ORDER BY sheet_index ASC, id ASC
        """, sheet_indices)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def sheet_exists(self, sheet_index: int) -> bool:
        """Check if a sheet_index exists in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE sheet_index = ?", (sheet_index,))
        row = cursor.fetchone()
        return row["cnt"] > 0
    
    def mark_done(self, task_id: int) -> None:
        posted_at = datetime.now().isoformat()
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("UPDATE tasks SET status = 'done', posted_at = ? WHERE id = ?", (posted_at, task_id))
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.error(f"Database operation failed for task {task_id}: {e}")
                time.sleep(0.5)
                try:
                    conn.rollback()
                    cursor.execute("UPDATE tasks SET status = 'done', posted_at = ? WHERE id = ?", (posted_at, task_id))
                    conn.commit()
                except Exception as retry_error:
                    logger.error(f"Database retry failed for task {task_id}: {retry_error}")
                    raise
    
    def mark_failed(self, task_id: int, error: str) -> None:
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                cursor.execute("UPDATE tasks SET status = 'failed', error = ? WHERE id = ?", (error, task_id))
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.error(f"Database operation failed for task {task_id}: {e}")
                time.sleep(0.5)
                try:
                    conn.rollback()
                    cursor.execute("UPDATE tasks SET status = 'failed', error = ? WHERE id = ?", (error, task_id))
                    conn.commit()
                except Exception as retry_error:
                    logger.error(f"Database retry failed for task {task_id}: {retry_error}")
                    raise
    
    def get_stats(self) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM tasks
        """)
        
        row = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(DISTINCT sheet_index) as total_sheets FROM tasks")
        sheet_row = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(DISTINCT sheet_index) as completed_sheets FROM tasks WHERE sheet_index NOT IN (SELECT DISTINCT sheet_index FROM tasks WHERE status = 'pending')")
        completed_row = cursor.fetchone()
        
        cursor.execute("SELECT sheet_name FROM tasks WHERE status = 'pending' ORDER BY sheet_index ASC LIMIT 1")
        current_row = cursor.fetchone()
        
        return {
            "total": row["total"] or 0,
            "done": row["done"] or 0,
            "pending": row["pending"] or 0,
            "failed": row["failed"] or 0,
            "total_sheets": sheet_row["total_sheets"] or 0,
            "completed_sheets": completed_row["completed_sheets"] or 0,
            "current_sheet": current_row["sheet_name"] if current_row else "",
            "sheets_remaining": (sheet_row["total_sheets"] or 0) - (completed_row["completed_sheets"] or 0)
        }
    
    def get_sheet_preview(self, limit: int = 0) -> list[dict]:
        """Get preview of sheets with post counts. limit=0 means all."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if limit and limit > 0:
            cursor.execute("""
                SELECT sheet_index, sheet_name, 
                       COUNT(*) as post_count,
                       SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM tasks
                GROUP BY sheet_index, sheet_name
                ORDER BY sheet_index ASC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT sheet_index, sheet_name, 
                       COUNT(*) as post_count,
                       SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM tasks
                GROUP BY sheet_index, sheet_name
                ORDER BY sheet_index ASC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def reset(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        conn.commit()
        logger.info("Queue reset - all tasks cleared")
    
    def get_tasks(self, limit: int = 0) -> list[dict]:
        """Get tasks. limit=0 means all."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if limit and limit > 0:
            cursor.execute("""
                SELECT id, profile_id, sheet_index, sheet_name, title, url, community, status, created_at, posted_at
                FROM tasks
                ORDER BY id ASC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT id, profile_id, sheet_index, sheet_name, title, url, community, status, created_at, posted_at
                FROM tasks
                ORDER BY id ASC
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_campaign_details(self, profile_id: int) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                MAX(CASE WHEN status = 'done' THEN posted_at ELSE NULL END) as last_post
            FROM tasks WHERE profile_id = ?
        """, (profile_id,))
        
        stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT id, title, url, sheet_name, status, posted_at
            FROM tasks WHERE profile_id = ? AND status IN ('done', 'failed')
            ORDER BY id DESC
        """, (profile_id,))
        
        tasks = [dict(row) for row in cursor.fetchall()]
        
        return {
            "pending": stats["pending"] or 0,
            "done": stats["done"] or 0,
            "failed": stats["failed"] or 0,
            "last_post": stats["last_post"],
            "tasks": tasks
        }
    
    def get_all_campaigns_details(self) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT profile_id FROM tasks")
        profile_ids = [row["profile_id"] for row in cursor.fetchall()]
        
        campaigns = {}
        for profile_id in profile_ids:
            campaigns[str(profile_id)] = self.get_campaign_details(profile_id)
        
        return {"campaigns": campaigns}
    
    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
