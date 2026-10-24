"""Compatibility entry point for hosts that default to running main.py.

The application lives in the bot package. Keep the actual startup logic in
bot/__main__.py and delegate here so both `python main.py` and
`python -m bot` work.
"""
import asyncio

from bot.__main__ import main


if __name__ == "__main__":
    asyncio.run(main())
