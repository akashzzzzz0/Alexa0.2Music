"""Explicit feedback preferences persisted in SQLite; this is not model-weight training."""
from __future__ import annotations
import os, sqlite3, threading, time
class FeedbackLearning:
    def __init__(self, db_path: str | None = None):
        self.db_path=db_path or os.getenv("ALEXA_AI_LEARNING_DB","alexa_own_ai_learning.sqlite3")
        self._lock=threading.RLock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS feedback (user_id TEXT NOT NULL, preference TEXT NOT NULL, score INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY(user_id,preference))")
    def _connect(self):
        db=sqlite3.connect(self.db_path,timeout=15); db.execute("PRAGMA busy_timeout=15000"); return db
    def record(self,user_id: str,key: str,positive: bool=True) -> None:
        uid=str(user_id)[:128]; pref=str(key).strip()[:80]
        if not uid or not pref: return
        with self._lock,self._connect() as db:
            db.execute("INSERT INTO feedback(user_id,preference,score,updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id,preference) DO UPDATE SET score=MAX(-20,MIN(20,score+excluded.score)),updated_at=excluded.updated_at",(uid,pref,1 if positive else -1,time.time()))
    def preferences(self,user_id: str) -> dict[str,int]:
        with self._lock,self._connect() as db:
            rows=db.execute("SELECT preference,score FROM feedback WHERE user_id=?",(str(user_id)[:128],)).fetchall()
        return dict(rows)
