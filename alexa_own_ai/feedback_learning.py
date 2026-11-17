"""Privacy-minimizing explicit feedback aggregation for Alexa Own AI."""
import sqlite3
import datetime as dt

ALLOWED = {
    "too_long", "too_short", "misunderstood", "repetitive",
    "wrong_language", "tone_mismatch", "helpful", "good_answer",
}
MAX_EVENTS_PER_SCOPE = 100


def _connect(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS feedback_events ("
        "scope TEXT NOT NULL, category TEXT NOT NULL, sentiment TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_scope_time "
        "ON feedback_events(scope, created_at)"
    )
    return conn


def record_feedback(db_path, scope, feedback):
    """Store only an allowlisted feedback category; never store message text."""
    scope = str(scope or "").strip()[:256]
    if not scope or not isinstance(feedback, dict):
        return False
    category = str(feedback.get("category", "")).strip().casefold()
    sentiment = str(feedback.get("sentiment", "")).strip().casefold()
    if category not in ALLOWED or sentiment not in ("positive", "negative"):
        return False
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO feedback_events(scope, category, sentiment, created_at) "
            "VALUES(?,?,?,?)",
            (scope, category, sentiment, dt.datetime.now(dt.timezone.utc).isoformat()),
        )
        conn.execute(
            "DELETE FROM feedback_events WHERE scope=? AND rowid NOT IN "
            "(SELECT rowid FROM feedback_events WHERE scope=? "
            "ORDER BY created_at DESC LIMIT ?)",
            (scope, scope, MAX_EVENTS_PER_SCOPE),
        )
    return True


def feedback_guidance(db_path, scope):
    """Return compact guidance only when a repeated explicit signal exists."""
    scope = str(scope or "").strip()[:256]
    if not scope:
        return ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT category, sentiment, COUNT(*) FROM feedback_events "
            "WHERE scope=? GROUP BY category, sentiment",
            (scope,),
        ).fetchall()
    counts = {(category, sentiment): count for category, sentiment, count in rows}
    hints = []
    labels = {
        "too_long": "prefer shorter replies",
        "too_short": "provide more complete detail when useful",
        "misunderstood": "check the user's actual intent and references carefully",
        "repetitive": "avoid repeating wording and stock responses",
        "wrong_language": "match the user's language and script more carefully",
        "tone_mismatch": "match the conversational tone more appropriately",
        "helpful": "retain the response approach that was explicitly marked helpful",
        "good_answer": "retain the response approach that was explicitly marked good",
    }
    for (category, sentiment), count in counts.items():
        if count >= 2:
            if sentiment == "negative":
                hints.append(labels[category])
            elif category in ("helpful", "good_answer"):
                hints.append(labels[category])
    if not hints:
        return ""
    return "Explicit user feedback patterns (not model training): " + "; ".join(sorted(set(hints))) + "."
