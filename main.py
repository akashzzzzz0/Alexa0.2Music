"""Alexa MusicPlayer upstream launcher.

Downloads the complete AGPL-licensed MusicPlayer source into /tmp at startup,
then launches it. This keeps the repository's existing main branch untouched.
"""
import io
import os
import runpy
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

UPSTREAM_ZIP = "https://codeload.github.com/AsmSafone/MusicPlayer/zip/refs/heads/master"
RUNTIME = Path("/tmp/alexa-musicplayer-upstream")


def prepare_environment():
    # Preserve the credentials already configured for Alexa0.2Music hosting.
    if not os.environ.get("SESSION", "").strip():
        os.environ["SESSION"] = os.environ.get("SESSION_STRING", "").strip()
    if not os.environ.get("SUDOERS", "").strip() and os.environ.get("OWNER_ID", "").strip():
        os.environ["SUDOERS"] = os.environ["OWNER_ID"].strip()
    if not os.environ.get("PREFIX", "").strip():
        os.environ["PREFIX"] = "/ !"


def install_upstream_source():
    request = urllib.request.Request(
        UPSTREAM_ZIP,
        headers={"User-Agent": "AlexaMusicPlayerLauncher/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        archive_bytes = response.read()

    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        root = RUNTIME.resolve()
        for member in archive.infolist():
            target = (RUNTIME / member.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError("Unsafe path found in upstream source archive")
        archive.extractall(RUNTIME)

    candidates = list(RUNTIME.glob("MusicPlayer-*"))
    if not candidates or not (candidates[0] / "main.py").is_file():
        raise RuntimeError("MusicPlayer source archive did not contain main.py")
    return candidates[0]


if __name__ == "__main__":
    prepare_environment()
    source = install_upstream_source()
    os.chdir(source)
    sys.path.insert(0, str(source))
    print("Starting upstream MusicPlayer with Alexa hosting credentials...")
    runpy.run_path(str(source / "main.py"), run_name="__main__")
