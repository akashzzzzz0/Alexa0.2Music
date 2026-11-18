"""Explicit feedback-based preference learning, scoped to runtime memory."""
from __future__ import annotations
class FeedbackLearning:
    def __init__(self):
        self._preferences: dict[str, dict[str, int]] = {}
    def record(self, user_id: str, key: str, positive: bool = True) -> None:
        bucket = self._preferences.setdefault(str(user_id), {})
        bucket[key] = bucket.get(key, 0) + (1 if positive else -1)
    def preferences(self, user_id: str) -> dict[str, int]:
        return dict(self._preferences.get(str(user_id), {}))
