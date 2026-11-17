"""Lightweight, privacy-safe conversation analysis for Alexa Own AI.

This layer extracts cautious multilingual cues from the complete current turn
and recent turns. It guides the language model; it never replaces it or claims
to know hidden emotions with certainty.
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

_CORRECTION = (
    r"\b(no|nahi|nahin|nhi|galat|wrong|mera matlab|mera kehna|"
    r"matlab ye|matlab yeh|maine kaha|i meant|i mean|that's not|"
    r"that is not|not what i meant|you misunderstood|samjho)\b"
)
_QUESTION = (
    r"\b(what|why|when|where|who|which|how|kya|kyun|kiun|kaise|kaisa|"
    r"kab|kahan|kidhar|kon|kaun|matlab|mtlb|kis tarah|kitna|kitni)\b"
)
_REQUEST = (
    r"\b(please|plz|can you|could you|would you|help me|batao|btao|"
    r"samjhao|samjha do|samjha|karo|kro|kar do|kardo|kr do|"
    r"bana do|bna do|fix karo|fix kro|theek karo|thik karo|"
    r"likh do|likh do|explain|tell me|show me|chahiye|zaroorat hai)\b"
)
_REFERENCE = (
    r"\b(it|that|this|same|ye|yeh|wo|woh|wahi|wohi|us|usne|iska|"
    r"uska|unki|unhon|phir|fir|kyun|kiun|kaise|matlab|mtlb|"
    r"aur|or|haan|han|acha|achha|iske|uske)\b"
)

def _last(history, role):
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get("role") == role:
            value = item.get("content")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _emoji_cues(message):
    return [
        label for symbols, label in _EMOJI_GROUPS
        if any(symbol in message for symbol in symbols)
    ]


def _script_hint(message):
    if any("\u0600" <= char <= "\u06ff" for char in message):
        return "urdu_or_arabic_script"
    if any("\u0900" <= char <= "\u097f" for char in message):
        return "devanagari_script"
    return "latin_or_mixed_script"


def analyze(message, history):
    """Return compact, uncertainty-aware cues for whole-message interpretation."""
    raw = str(message or "").strip()
    text = raw.casefold()
    # Unicode-aware tokenization keeps Urdu/Devanagari words in the length
    # estimate instead of treating a full-script message as an empty string.
    words = re.findall(r"[a-z0-9']+|[\u0600-\u06ff]+|[\u0900-\u097f]+", text, flags=re.UNICODE)
    previous_assistant = _last(history, "assistant")
    previous_user = _last(history, "user")
    previous_assistant_asked = bool(
        previous_assistant and re.search(r"[?؟]\s*$", previous_assistant)
    )

    correction = bool(re.search(_CORRECTION, text))
    owner_assertion = bool(re.search(
        r"\b(?:tera|tumhara|tumhari|aapka|apki)\s+owner\s+(?:to\s+)?"
        r"(?:mai|main|me)\s+(?:hi\s+)?(?:hu|hun|hoon|hon|na|naa)\b|"
        r"\b(?:mai|main|me)\s+(?:hi\s+)?(?:tera|tumhara|tumhari|"
        r"aapka|apki)\s+owner\s+(?:hu|hun|hoon|hon)\b|"
        r"\bowner\s+(?:to\s+)?(?:mai|main|me)\s+(?:hi\s+)?"
        r"(?:hu|hun|hoon|hon|na|naa)\b",
        text,
    ))
    correction = correction or owner_assertion
    ranking_question = bool(re.search(
        r"\\b(?:no\\.?\\s*1|number\\s*1|#\\s*1|top\\s*1|rank\\s*1)\\b.{0,32}\\b(?:kon|kaun|who|hai|is)\\b|"
        r"\\b(?:who|kon|kaun)\\b.{0,32}\\b(?:no\\.?\\s*1|number\\s*1|#\\s*1|top\\s*1|rank\\s*1)\\b",
        text,
    ))
    question = "?" in raw or "؟" in raw or bool(re.search(_QUESTION, text))
    request = bool(re.search(_REQUEST, text))
    greeting = bool(re.fullmatch(
        r"[\W_]*(hi|hello|hey|salam|assalam o alaikum|suno|oye)[\W_]*", text
    ))
    gratitude = bool(re.search(r"\b(thanks|thank you|shukriya|meharbani|dhanvaad)\b", text))
    apology = bool(re.search(r"\b(sorry|maaf|my bad|meri galti|meri ghalti)\b", text))
    frustration = bool(re.search(
        r"\b(annoyed|angry|frustrated|bakwas|kya yaar|samajh nahi|"
        r"samajh nhi|nahi samajhte|not listening|not understanding|"
        r"useless|wtf|pareshan kar diya)\b", text
    ))
    playful = bool(re.search(
        r"\b(lol|lmao|haha|hehe|mazak|mazaak|majak|mazaq)\b", text
    ))
    emotional = bool(re.search(
        r"\b(sad|udaas|pareshan|worried|tension|happy|khush|excited|"
        r"hurt|dukhi|pareshani|ghussa|gussa|naraz|naraaz)\b", text
    ))
    negation = bool(re.search(
        r"\b(no|not|never|don't|doesn't|didn't|nahi|nahin|nhi|mat|"
        r"bilkul nahi|aisa nahi|aise nahi)\b", text
    ))
    short = len(words) <= 4
    refers_back = bool(re.search(_REFERENCE, text))
    followup = bool(previous_assistant and (short or refers_back))
    emoji_cues = _emoji_cues(raw)

    # A short answer to Alexa's last question is more useful as a continuation
    # than as a fresh, isolated question/request classification.
    if owner_assertion:
        act = "owner_relationship_assertion"
    elif correction:
        act = "correction_or_disagreement"
    elif greeting:
        act = "greeting"
    elif gratitude:
        act = "gratitude"
    elif apology:
        act = "apology"
    elif ranking_question:
        act = "ranking_or_comparison_question"
    elif short and previous_assistant_asked and not question and not request:
        act = "answer_to_previous_question"
    elif request:
        act = "request"
    elif question:
        act = "question"
    elif emotional:
        act = "emotional_share"
    elif playful:
        act = "playful_message"
    elif followup and refers_back:
        act = "contextual_followup"
    else:
        act = "statement_or_open_chat"

    tones = []
    if frustration:
        tones.append("possibly_frustrated")
    if playful or "amused_or_laughing" in emoji_cues:
        tones.append("possibly_playful")
    if emotional:
        tones.append("emotion_word_present")
    if negation:
        tones.append("negation_present_check_what_it_modifies")
    if not tones and not emoji_cues:
        tones.append("neutral_or_unclear")

    strategies = {
        "owner_relationship_assertion": "accept_the_explicit_owner_statement_as_conversation_context_and_acknowledge_it_without_claiming_it_authenticates_privileged_permissions",
        "correction_or_disagreement": "acknowledge_correction_first_then_replace_the_wrong_interpretation",
        "question": "answer_the_actual_question_first_and_cover_each_requested_part",
        "ranking_or_comparison_question": "use_explicit_ranking_evidence_from_recent_turns_or_caller_context;_if_missing_ask_what_ranking_the_user_means_and_never_guess_or_claim_to_be_number_one",
        "request": "identify_the_requested_outcome_and_do_it_without_answering_only_a_surface_keyword",
        "answer_to_previous_question": "connect_this_answer_to_the_assistant_question_and_continue_that_thread",
        "contextual_followup": "resolve_pronouns_and_omitted_subjects_from_the_closest_relevant_turns",
        "emotional_share": "acknowledge_the_expressed_feeling_without_inventing_its_cause",
        "gratitude": "respond_warmly_without_reopening_a_finished_topic",
        "apology": "accept_or_reassure_briefly_without_overdoing_it",
        "playful_message": "match_the_light_tone_only_if_the_words_and_context_support_it",
        "greeting": "greet_naturally_and_invite_the_actual_topic",
        "statement_or_open_chat": "respond_to_the_main_point_and_preserve_any_explicit_constraints",
    }

    lines = [
        "Whole-message conversation analysis (heuristic cues, not certainties):",
        "message_act=" + act,
        "script_hint=" + _script_hint(raw),
        "word_count=" + str(len(words)),
        "short_message=" + ("yes" if short else "no"),
        "contains_negation=" + ("yes" if negation else "no"),
        "contains_possible_correction=" + ("yes" if correction else "no"),
        "explicit_owner_relationship_statement=" + ("yes" if owner_assertion else "no"),
        "contains_request=" + ("yes" if request else "no"),
        "contains_question=" + ("yes" if question else "no"),
        "asks_about_number_one_or_ranking=" + ("yes" if ranking_question else "no"),
        "tone_cues=" + (",".join(tones) if tones else "none_detected"),
        "emoji_cues=" + (",".join(emoji_cues) if emoji_cues else "none_detected"),
        "likely_contextual_reference=" + ("yes" if refers_back else "no"),
        "previous_assistant_asked_question=" + ("yes" if previous_assistant_asked else "no"),
        "previous_user_turn_available=" + ("yes" if previous_user else "no"),
        "reply_strategy=" + strategies[act],
        "Interpret every clause in the complete message, including conditions, negation, and constraints. "
        "Do not let one detected keyword override the sentence meaning. Use the recent conversation "
        "to resolve omitted subjects and references; if evidence conflicts, trust the actual words. "
        "These cues are hints only: never state them to the user or present uncertain tone as fact.",
    ]
    return "\n".join(lines)
