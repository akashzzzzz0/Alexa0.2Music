"""Conversation routing shim for Alexa Own AI.

Ordinary conversation is deliberately delegated to the generative model so
meaning, emotion, references, and tone are interpreted from the full context.
"""

def respond(message, normalized, language, history, context=None):
    """Never answer ordinary chat with canned text; let the model use context."""
    return None


if __name__ == "__main__":
    import unittest
    unittest.main()
