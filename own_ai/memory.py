"""Small optional in-process conversation memory; no personal data is persisted to disk."""
from __future__ import annotations
from collections import defaultdict, deque
class ConversationMemory:
    def __init__(self, max_messages: int = 12):
        self._items = defaultdict(lambda: deque(maxlen=max_messages))
    def add(self, conversation_id: str, role: str, content: str) -> None:
        if role in {"user","assistant"} and content:
            self._items[str(conversation_id)].append({"role": role, "content": content[:4000]})
    def get(self, conversation_id: str) -> list[dict]:
        return list(self._items[str(conversation_id)])
    def clear(self, conversation_id: str) -> None:
        self._items.pop(str(conversation_id), None)
