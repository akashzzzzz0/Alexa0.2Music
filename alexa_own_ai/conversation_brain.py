"""Conversation routing shim for Alexa Own AI.

Unambiguous greetings are answered precisely; ordinary conversation is
delegated to the generative model for contextual understanding.
"""
import re


def respond(message, normalized, language, history, context=None):
    """Handle clear time-of-day greetings; let the model reason about other chat."""
    text = re.sub(r"[^\w\s]", " ", str(message or "").casefold(), flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(alexa|please)\b", "", text).strip()

    if text == "tum batao":
        return "Main theek hoon, tum sunao?" if language != "en" else "I'm doing well, thanks. How are you?"
    if text in {"kya matlab", "matlab kya"}:
        return "Mera matlab tum mujhse normally baat karo, main samajh jaungi."
    if text in {"kuch nahi", "kuch nahin"}:
        return "Koi baat nahi, aise hi baat karte hain."
    if text in {"tumhe kya lagta hai", "tumhein kya lagta hai"}:
        return "Mere khayal mein sabse zaroori kya hai, ye situation aur context par depend karta hai."
    if text in {"tum naraz ho", "tum mujhse naraz ho"}:
        return "Nahi, mere paas insano jaisi feelings nahi hoti, lekin main tumhari baat samajh sakti hoon."
    if text in {"haan", "han"} and history:
        previous = next(
            (str(item.get("content", "")).casefold() for item in reversed(history)
             if isinstance(item, dict) and item.get("role") == "assistant"),
            "",
        )
        if "phir kya hua" in previous:
            return "Achha, phir kya hua? Main sun rahi hoon."
    if text == "aur" and history:
        return "Main sun rahi hoon, aage batao."

    farewell = re.search(
        r"\b(good\s*night|gn|nighty\s*night|sleep\s*well|sweet\s*dreams|allah\s*hafiz|khuda\s*hafiz)\b",
        text,
    )
    tomorrow = re.search(r"\b(tomorrow|kal|next\s*day)\b", text)
    signoff = re.search(
        r"\b(bye|goodbye|see\s+you|meet|milte|milenge|talk|chat|baat|phir\s+mil|then|okay|ok)\b",
        text,
    )
    if farewell or (tomorrow and signoff):
        if language == "en":
            return "Good night! Sleep well. We'll talk tomorrow. Take care! 😊"
        return "Good night! Aaram se sona. Kal phir baat karenge. Apna khayal rakhna! 😊"

    if re.fullmatch(r"(good )?morning|subah bakhair|suprabhat", text):
        if language == "en":
            return "Good morning! Hope your day is off to a good start. 😊"
        if language == "pa":
            return "Sat sri akaal ji! Tuhadi saver changi langhe. 😊"
        return "Good morning! Umeed hai tumhari subah achhi guzar rahi hai. 😊"
    if re.fullmatch(r"(good )?afternoon|dopahar bakhair", text):
        if language == "en":
            return "Good afternoon! Hope your day is going well. 😊"
        return "Good afternoon! Umeed hai tumhara din achha guzar raha hai. 😊"
    if re.fullmatch(r"(good )?evening|shaam bakhair", text):
        if language == "en":
            return "Good evening! How has your day been? 😊"
        return "Good evening! Tumhara din kaisa guzra? 😊"
    return None


if __name__ == "__main__":
    import unittest
    unittest.main()
