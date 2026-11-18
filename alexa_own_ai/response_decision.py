"""Conservative reply/reaction/silence recommendations for chat integrations."""
import re

ALLOWED_REACTIONS = {"👍", "❤️", "😂", "😮", "😢", "🔥", "🎉"}


def decide(message, context=None):
    """Recommend an action; the calling Telegram integration performs it."""
    context = context if isinstance(context, dict) else {}
    is_group = context.get("is_group") is True
    addressed = any(
        context.get(key) is True for key in (
            "addressed", "mentioned", "replied_to", "bot_name_mentioned",
            "username_mentioned", "reply_to_bot", "replied_to_bot",
        )
    )
    allow_reactions = context.get("allow_reactions") is True
    text = str(message or "").strip()
    if not is_group:
        return {"action": "reply", "reason": "private_chat", "reaction": None}

    if addressed:
        return {"action": "reply", "reason": "bot_was_addressed", "reaction": None}

    if not allow_reactions:
        return {"action": "silence", "reason": "unaddressed_group_message", "reaction": None}

    # Only recommend a reaction for clearly notable content, not routine greetings.
    cues = (
        (r"(😂|🤣|😆|\b(lol|lmao|haha|hehe|mazak|mazaak)\b)", "😂"),
        (r"(❤️|💕|💖|🥰)", "❤️"),
        (r"(🎉|🥳|\b(congratulations|mubarak|congrats)\b)", "🎉"),
        (r"(😢|😭|🥺|\b(sorry to hear|afsoos|udaas|sad)\b)", "😢"),
        (r"(🔥|\b(amazing|zabardast|excellent)\b)", "🔥"),
    )
    for pattern, reaction in cues:
        if re.search(pattern, text, flags=re.IGNORECASE):
            if reaction in ALLOWED_REACTIONS:
                return {"action": "react", "reason": "notable_message", "reaction": reaction}
    return {"action": "silence", "reason": "ordinary_unaddressed_group_message", "reaction": None}
