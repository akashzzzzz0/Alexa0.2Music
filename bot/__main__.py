"""Keep the previous `python -m bot` host command working."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent.parent / "main.py"), run_name="__main__")
