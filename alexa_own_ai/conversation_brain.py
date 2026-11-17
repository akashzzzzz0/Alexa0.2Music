"""Conversation-focused response layer for Alexa Own AI.

This is a deterministic, low-memory dialogue layer. It improves common
conversation and follow-up handling without pretending to be a trained LLM.
"""
import re

EN = {
    "greet_back": "Hey! I'm here. What's going on?",
    "how_back": "I'm doing well, thanks for asking. How has your day been?",
    "day_back": "My day is going well, thanks for asking. How has yours been?",
    "thanks_back": "You're welcome. What else is on your mind?",
    "apology_back": "No worries. It's okay—what would you like to talk about?",
    "what_doing": "I'm here chatting with you. What are you up to?",
    "meaning": "I meant you can talk naturally. I’ll follow along—what were you saying?",
    "repeat": "Sure. Which part would you like me to explain again?",
    "agree": "Got it. Tell me a little more.",
    "disagree": "Okay, I may have misunderstood. What did you mean instead?",
    "ask_opinion": "I can help think it through. What matters most to you in this situation?",
    "ask_feelings": "I don't have feelings like a person, but I'm here to listen and respond thoughtfully.",
    "ask_memory": "I can use the conversation context available to me. Remind me of the detail if it was from much earlier.",
    "ask_identity": "I'm Alexa. I'm here for conversation, questions, and helping you think things through.",
    "ask_clarify": "I may have missed the point. Are you talking about what we just discussed?",
    "encourage": "I'm listening. What happened next?",
    "sad": "I'm sorry things are feeling difficult. Want to tell me what happened?",
    "happy": "That's good to hear! What happened?",
    "bored": "We can just chat. What's one thing you've been thinking about lately?",
    "default_follow": "Okay, I'm following. Go on.",
}
UR = {
    "greet_back": "Haan, yahin hoon. Kya chal raha hai?",
    "how_back": "Main theek hoon, poochne ka shukriya. Tumhara din kaisa ja raha hai?",
    "day_back": "Mera din acha ja raha hai 😊 Tumhara din kaisa raha?",
    "thanks_back": "Koi baat nahi. Aur batao, kya chal raha hai?",
    "apology_back": "Koi baat nahi, sab theek hai. Ab kis bare mein baat karein?",
    "what_doing": "Bas yahin tumse chat kar rahi hoon. Tum kya kar rahe ho?",
    "meaning": "Mera matlab tha ke tum normally baat karo. Main samajhne ki koshish karungi—batao kya keh rahe the?",
    "repeat": "Zaroor. Kaunsi baat dobara samjhaun?",
    "agree": "Achha, samajh gayi. Phir batao?",
    "disagree": "Theek hai, shayad main galat samjhi. Tumhara matlab kya tha?",
    "ask_opinion": "Main tumhare saath soch sakti hoon. Is baat mein tumhare liye sabse zaroori kya hai?",
    "ask_feelings": "Mere paas insano jaisi feelings nahi hoti, lekin main tumhari baat dhyan se samajhne ki koshish karungi.",
    "ask_memory": "Jo conversation context mere paas available hai, main usay use kar sakti hoon. Agar purani baat thi to ek hint de do.",
    "ask_identity": "Main Alexa hoon. Tumse chat karne, sawalon ke jawab dene aur ideas samajhne ke liye yahan hoon.",
    "ask_clarify": "Shayad main tumhari baat miss kar gayi. Kya tum pichhli baat ke bare mein keh rahe ho?",
    "encourage": "Main sun rahi hoon. Phir kya hua?",
    "sad": "Ye sun kar afsos hua. Agar batana chaho to kya hua?",
    "happy": "Wah, ye achhi baat hai! Kya hua?",
    "bored": "Chalo normal baat karte hain. Aaj kal tumhare zehan mein kya chal raha hai?",
    "default_follow": "Achha, main samajh rahi hoon. Aage batao.",
}

def _history_text(history):
    items = [x for x in history if isinstance(x, dict)]
    last_user = next((str(x.get("content", "")) for x in reversed(items) if x.get("role") == "user"), "")
    last_assistant = next((str(x.get("content", "")) for x in reversed(items) if x.get("role") == "assistant"), "")
    return last_user, last_assistant

def respond(message, normalized, language, history):
    """Return a context-aware reply, or None when this layer has no confident match."""
    t = normalized
    roman = language != "en"
    bank = UR if roman else EN
    last_user, last_assistant = _history_text(history)
    prev = last_assistant.lower()
    words = set(t.split())

    # Preserve the exact real-world conversation that exposed the repeated fallback.
    if re.search(r"\b(sab theek|sab thik|sab thek)\b", t) and re.search(r"\b(kahan thi|kha th+i+|kaha thi|kidhar thi|tum thi|tum ho)\b", t):
        return ("Yes, all good here. I was right here—how are you?" if not roman
                else "Haan, sab theek chal raha hai. Main yahin thi, tum sunao? Kya chal raha hai?")

    # Conversational repair: understand why the user is asking for clarification.
    if re.search(r"\b(kya matlab|matlab kya|what do you mean|meaning kya|kis liye|kyun poocha|why ask)\b", t):
        return bank["meaning"]
    if re.search(r"\b(dobara|phir se|repeat|again|samjhao|samjha do|explain again)\b", t):
        return bank["repeat"]
    if re.search(r"\b(kis|kaun|kon)\b", t) and re.search(r"\b(alfaz|lafz|ilfaz|word|words|tarah)\b", t) and re.search(r"\b(samj|samajh)\w*\b", t):
        if any(k in prev for k in ("rephrase", "doosre", "context", "samajh", "clarify")):
            return ("My mistake—I understood you the first time. I shouldn't have asked you to rephrase." if not roman
                    else "Arey, meri galti! Tumhari pehli baat samajh aa gayi thi—mujhe dobara poochna nahi chahiye tha.")
        return bank["ask_clarify"]

    # Replies that depend on the last assistant turn, not just keywords.
    if re.fullmatch(r"(haan|han|yes|yeah|yep|ok|okay|theek|thik|acha|achha|bilkul|sure|hmm+)[!. ]*", t):
        if any(q in prev for q in ("want to tell", "batao", "kya hua", "what happened", "go on", "aage")):
            return bank["encourage"]
        return bank["agree"]
    if re.fullmatch(r"(nahi|nahin|no|nope|not really)[!. ]*", t):
        if any(q in prev for q in ("do you mean", "kya tum", "would you", "chahte")):
            return bank["disagree"]
        return bank["disagree"]
    if re.fullmatch(r"(aur|phir|then|and then|uske baad|aage|go on|tell me more)[!. ]*", t):
        return bank["encourage"]
    if re.fullmatch(r"(tum batao|aap batao|you tell me|what about you|aur tum|aur aap)[!. ]*", t):
        return bank["how_back"]
    if re.fullmatch(r"(are+ yaar|aray yaar|uff yaar|oh yaar|yaar)[!. ]*", t):
        return ("Oh no—what happened? Did I misunderstand something?" if not roman
                else "Arey, kya hua? Meri kisi baat se confusion hua?")
    if re.fullmatch(r"(kuch nahi|kuch bhi nahi|nothing|not much|bas aise hi|just like that)[!. ]*", t):
        return ("That's okay. We can chat casually. How has your day been?" if not roman
                else "Koi baat nahi. Aise hi baat karte hain. Aaj din kaisa guzra?")

    # Casual questions about Alexa's day (including common Roman Urdu spellings/typos).
    if re.search(r"\b(how('?s| is) your day|how has your day been|how('s| is) your day going)\b", t):
        return bank["day_back"]
    if re.search(r"\b(tumhara|aapka|apka)?\s*din\b", t) and re.search(r"\b(kesa|kaisa|kaise|kese|kesaa)\b", t) and re.search(r"\b(ha|hai|he|raha|rahi|guzar|guzra|guzri|chal)\w*\b", t):
        return bank["day_back"]

    # Reassurance: the user is asking whether Alexa understands them.
    # Match natural Roman Urdu/Hindi variants instead of sending a generic fallback.
    if re.search(r"\b(tum|aap)\b", t) and re.search(r"\b(mujhe|mujy|mujhko|mujh|meri baat|my)\b", t) and re.search(r"\b(samajh|samaj|understand)\w*\b", t):
        if re.search(r"\b(sakti|sakte|sakta|paogi|paoge|can|right|na|hai|ho)\b", t):
            return ("Yes, I can understand you. You can speak naturally—I’m listening." if not roman
                    else "Haan ji, bilkul samajh sakti hoon 😊 Tum apni baat normally batao, main dhyan se sun rahi hoon.")
    if re.search(r"\b(do you understand me|you understand me|can you understand me)\b", t):
        return ("Yes, I can understand you. You can speak naturally—I’m listening." if not roman
                else "Haan ji, bilkul samajh sakti hoon 😊 Tum apni baat normally batao, main dhyan se sun rahi hoon.")

    # Common conversational intents and questions about Alexa.
    if re.search(r"\b(kaisi ho|kaise ho|kese ho|kese ha|kaise ha|kaisa ha|kaisa hai|kesa hai|how are you|how r u|sab theek|sab thik|sab thek)\b", t):
        return bank["how_back"]
    if re.search(r"\b(kya kar rahi|kya kar rahe|what are you doing|what r u doing)\b", t):
        return bank["what_doing"]
    if re.search(r"\b(kaun ho|kon ho|who are you|tumhara naam|your name)\b", t):
        return bank["ask_identity"]
    if re.search(r"\b(yaad hai|yaad hai kya|remember me|do you remember|what did i say)\b", t):
        return bank["ask_memory"]
    if re.search(r"\b(tumhe kaisa lagta|tumhe kya lagta|tumhara kya khayal|what do you think|your opinion|kya sochti)\b", t):
        return bank["ask_opinion"]
    if re.search(r"\b(khush ho|naraz ho|bura laga|feelings|do you feel|are you happy|are you sad)\b", t):
        return bank["ask_feelings"]
    if re.search(r"\b(thank you|thanks|shukriya|bohat shukriya|meharbani)\b", t):
        return bank["thanks_back"]
    if re.search(r"\b(sorry|maaf karna|maaf karo|my bad|meri galti)\b", t):
        return bank["apology_back"]
    if re.search(r"\b(udaas|pareshan|tension|mood off|sad|upset|worried|dukhi)\b", t):
        return bank["sad"]
    if re.search(r"\b(khush|khushi|happy|great news|zabardast|mazay)\b", t):
        return bank["happy"]
    if re.search(r"\b(bore|boring|pak gaya|pak gayi|bored)\b", t):
        return bank["bored"]

    # Short follow-up questions: use the prior assistant prompt as a clue.
    if len(words) <= 4 and re.search(r"\b(kyun|kaise|how|why|kis liye|what|kya)\b", t):
        if any(k in prev for k in ("batao", "tell me", "what happened", "kya hua", "which", "kaunsa")):
            return bank["ask_clarify"]
    if last_user and len(words) <= 3 and re.search(r"\b(acha|achha|theek|hmm|hmmm|right|really|sach)\b", t):
        return bank["default_follow"]

    return None
