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
