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

    # Resolve short confirmations against Alexa's immediately preceding question.
    if text in {"yes", "yeah", "yep", "haan", "han", "ji", "okay", "ok", "achha", "acha"} and history:
        previous_assistant = next(
            (str(item.get("content", "")).casefold() for item in reversed(history)
             if isinstance(item, dict) and item.get("role") == "assistant"),
            "",
        )
        if "what can i help" in previous_assistant or "how can i help" in previous_assistant:
            return "Sure—what would you like help with?" if language == "en" else "Haan, bolo—kis cheez mein help chahiye?"

    # Answer a clear, everyday relationship-advice request instead of returning
    # a generic clarification. Alexa must not claim it can arrange a partner.
    relationship_request = re.search(
        r"\b(?:girlfriend|boyfriend|gf|bf|girl friend|boy friend)\b.{0,40}\b(?:chahiye|chaiye|want|need|dila do|dilao|milwa do|milao)\b|"
        r"\b(?:chahiye|chaiye|want|need)\b.{0,30}\b(?:girlfriend|boyfriend|gf|bf|girl friend|boy friend)\b",
        text,
    )
    if relationship_request:
        if language == "en":
            return "I can't arrange someone for you, but I can help you think of a respectful way to get to know someone. 😊"
        return "Haha, samajh gayi 😄 Main kisi ko arrange nahi kar sakti, lekin kisi se respectfully baat shuru karne ki achhi advice de sakti hoon."

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
