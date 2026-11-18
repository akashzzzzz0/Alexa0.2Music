"""SQLite-backed bounded conversation memory with safe per-conversation separation."""
from __future__ import annotations
import os, sqlite3, threading, time
class ConversationMemory:
    def __init__(self, max_messages: int = 24, db_path: str | None = None):
        self.max_messages=max(2,int(max_messages))
        self.db_path=db_path or os.getenv("ALEXA_AI_MEMORY_DB","alexa_own_ai_memory.sqlite3")
        self._lock=threading.RLock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id,id)")
    def _connect(self):
        db=sqlite3.connect(self.db_path, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=15000")
        return db
    def add(self, conversation_id: str, role: str, content: str) -> None:
        if role not in {"user","assistant"} or not content: return
        cid=str(conversation_id)[:128]
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",(cid,role,str(content)[:8000],time.time()))
            db.execute("DELETE FROM messages WHERE conversation_id=? AND id NOT IN (SELECT id FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?)",(cid,cid,self.max_messages))
    def get(self, conversation_id: str) -> list[dict]:
        with self._lock, self._connect() as db:
            rows=db.execute("SELECT role,content FROM (SELECT id,role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?) ORDER BY id",(str(conversation_id)[:128],self.max_messages)).fetchall()
        return [{"role":r,"content":c} for r,c in rows]
    def clear(self, conversation_id: str) -> None:
        with self._lock, self._connect() as db: db.execute("DELETE FROM messages WHERE conversation_id=?",(str(conversation_id)[:128],))
