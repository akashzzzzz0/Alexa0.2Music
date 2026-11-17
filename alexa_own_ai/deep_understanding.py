"""Lightweight, privacy-safe conversation analysis for Alexa Own AI.

This layer does not guess hidden emotions or replace the language model. It
extracts cautious conversational cues from the current turn and recent turns
so the model can resolve references and choose a more useful reply.
"""
import re

_EMOJI_GROUPS = (
    (("😂", "🤣", "😆", "😹"), "amused_or_laughing"),
    (("❤️", "❤", "💕", "💖", "🥰"), "warm_or_appreciative"),
    (("🙏", "🤲"), "thanks_or_prayer_possible"),
    (("🙄", "😒", "💀"), "sarcasm_or_disbelief_possible"),
    (("😢", "😭", "🥺", "😔"), "sad_or_touched_possible"),
    (("😡", "🤬", "😤"), "frustrated_possible"),
    (("👍", "👌", "✅"), "acknowledgement_or_approval"),
    (("🤔", "❓", "⁉️"), "thinking_or_questioning"),
)

def _last(history, role):
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get("role") == role:
            value = item.get("content")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""

def _emoji_cues(message):
    cues = []
    for symbols, label in _EMOJI_GROUPS:
        if any(symbol in message for symbol in symbols):
            cues.append(label)
    return cues

def analyze(message, history):
    """Return a compact structured cue summary; never infer certainty."""
    raw = str(message or "").strip()
    text = raw.casefold()
    words = re.findall(r"[a-zA-Z0-9']+", text)
    previous_assistant = _last(history, "assistant")
    previous_user = _last(history, "user")
    previous_assistant_asked = bool(
        previous_assistant and re.search(r"[?؟]\\s*$", previous_assistant)
    )

    correction = bool(re.search(
        r"\\b(no|nahi|nahin|nhi|galat|wrong|mera matlab|matlab ye|i meant|"
        r"that's not|that is not|you misunderstood|samjho)\\b", text
    ))
    question = "?" in raw or "؟" in raw or bool(re.search(
        r"\\b(what|why|when|where|who|which|how|kya|kyun|kaise|kaisa|kab|kahan|"
        r"kon|kaun|matlab|mtlb)\\b", text
    ))
    request = bool(re.search(
        r"\\b(please|plz|can you|could you|help me|batao|btao|samjhao|karo|"
        r"kar do|likh do|explain|tell me|show me)\\b", text
    ))
    greeting = bool(re.fullmatch(
        r"[\\W_]*(hi|hello|hey|salam|assalam o alaikum|suno|oye)[\\W_]*", text
    ))
    gratitude = bool(re.search(r"\\b(thanks|thank you|shukriya|meharbani)\\b", text))
    apology = bool(re.search(r"\\b(sorry|maaf|my bad|meri galti)\\b", text))
    frustration = bool(re.search(
        r"\\b(annoyed|angry|frustrated|bakwas|kya yaar|samajh nahi|"
        r"nahi samajhte|not listening|useless|wtf)\\b", text
    ))
    playful = bool(re.search(r"\\b(lol|lmao|haha|hehe|mazak|mazaak)\\b", text))
    emotional = bool(re.search(
        r"\\b(sad|udaas|pareshan|worried|tension|happy|khush|excited|"
        r"hurt|dukhi|pareshani)\\b", text
    ))
    short = len(words) <= 4
    followup = short and bool(previous_assistant)
    refers_back = bool(re.search(
        r"\\b(it|that|this|same|ye|woh|us|iska|uska|kyun|kaise|matlab|mtlb|"
        r"phir|aur|haan|han|acha|achha|ok|okay)\\b", text
    ))
    emoji_cues = _emoji_cues(raw)

    if correction:
        act = "correction_or_disagreement"
    elif greeting:
        act = "greeting"
    elif gratitude:
        act = "gratitude"
    elif apology:
        act = "apology"
    elif question:
        act = "question"
    elif request:
        act = "request"
    elif emotional:
        act = "emotional_share"
    elif playful:
        act = "playful_message"
    elif short and previous_assistant_asked:
        act = "answer_to_previous_question"
    elif followup and refers_back:
        act = "contextual_followup"
    else:
        act = "statement_or_open_chat"

    tones = []
    if frustration:
        tones.append("possibly_frustrated")
    if playful or any(x == "amused_or_laughing" for x in emoji_cues):
        tones.append("possibly_playful")
    if emotional:
        tones.append("emotion_word_present")
    if not tones and not emoji_cues:
        tones.append("neutral_or_unclear")

    strategies = {
        "correction_or_disagreement": "acknowledge_correction_first_then_fix_the_misunderstanding",
        "question": "answer_the_specific_question_first_then_add_only_useful_context",
        "request": "identify_the_requested_outcome_and_complete_it_directly",
        "answer_to_previous_question": "connect_this_short_answer_to_the_previous_assistant_question",
        "contextual_followup": "resolve_references_from_recent_turns_before_answering",
        "emotional_share": "acknowledge_the_emotion_without_assuming_unstated_causes",
        "gratitude": "respond_warmly_without_reopening_a_finished_topic",
        "apology": "accept_or_reassure_briefly_without_overdoing_it",
        "playful_message": "match_the_light_tone_only_if_context_supports_it",
        "greeting": "greet_naturally_and_invite_the_actual_topic",
        "statement_or_open_chat": "respond_to_the_meaningful_point_and_add_one_relevant_next_step",
    }
    lines = [
        "Conversation analysis (heuristic cues, not certainties):",
        "message_act=" + act,
        "tone_cues=" + ",".join(tones),
        "emoji_cues=" + (",".join(emoji_cues) if emoji_cues else "none_detected"),
        "short_message=" + ("yes" if short else "no"),
        "likely_contextual_reference=" + ("yes" if refers_back else "no"),
        "previous_assistant_asked_question=" + ("yes" if previous_assistant_asked else "no"),
        "reply_strategy=" + strategies[act],
        "Use the full conversation to verify these cues. If a cue conflicts with the actual words or context, trust the conversation. Never state this analysis to the user.",
    ]
    return "\\n".join(lines)
