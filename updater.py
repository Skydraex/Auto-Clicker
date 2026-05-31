"""
Self-updater for the Auto-Clicker Windows executable.

On launch the frozen .exe asks GitHub for the latest release, compares its own
SHA-256 against the published asset's digest, and -- if they differ -- downloads
the new binary and relaunches via a tiny helper batch script. Using the content
digest means *any* change we publish forces an update, without having to bump a
version number by hand.

When running from source (python auto_clicker.py) there is no .exe to replace,
so updating is skipped. All network/OS errors are swallowed so a missing
connection never blocks the app -- important for AFK use.
"""

import hashlib
import json
import os
import subprocess
import sys
import urllib.request


OWNER = "Skydraex"
REPO = "Auto-Clicker"
ASSET_NAME = "AutoClicker.exe"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"


def _read_version():
    """Read the bundled VERSION file (single source of truth), with fallback."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(base, "VERSION"), "r") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


# Embedded build version (fallback comparison if the asset has no digest).
APP_VERSION = _read_version()

_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "AutoClicker-Updater",
}


def _fetch_latest():
    req = urllib.request.Request(API_URL, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=6) as resp:
        return json.load(resp)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_asset(release):
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            return asset
    return None


def check_for_update():
    """Return a download URL if a newer build is published, else None.

    Returns None (rather than raising) on any error, when running from source,
    or when already up to date.
    """
    if not getattr(sys, "frozen", False):
        return None  # running from source -- nothing to self-update

    try:
        release = _fetch_latest()
    except Exception:
        return None  # offline / API error -> never block startup

    asset = _find_asset(release)
    if not asset:
        return None
    url = asset.get("browser_download_url")
    if not url:
        return None

    # Preferred: compare the published binary's content hash to our own.
    digest = asset.get("digest", "") or ""
    if digest.startswith("sha256:"):
        try:
            local = _sha256(sys.executable)
        except Exception:
            local = None
        if local is not None:
            remote = digest.split(":", 1)[1].lower()
            return url if local.lower() != remote else None

    # Fallback: compare the release tag to our embedded version.
    tag = (release.get("tag_name") or "").lstrip("vV")
    if tag and tag != APP_VERSION:
        return url
    return None


def apply_update(url, on_status=None):
    """Download the new exe and relaunch it via a helper batch script (Windows).

    The current process must exit shortly after this returns so the batch can
    replace the (now-unlocked) executable and start the new one.
    """
    def status(msg):
        if on_status:
            on_status(msg)

    target = sys.executable
    new_path = target + ".new"

    status("Downloading update…")
    req = urllib.request.Request(url, headers={"User-Agent": "AutoClicker-Updater"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(new_path, "wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)

    status("Installing…")
    pid = os.getpid()
    bat = target + ".update.bat"

    # Wait for this process to exit, swap the exe, relaunch, then self-delete.
    script = (
        "@echo off\r\n"
        ":waitloop\r\n"
        f'tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "  ping -n 2 127.0.0.1 >NUL\r\n"
        "  goto waitloop\r\n"
        ")\r\n"
        f'move /Y "{new_path}" "{target}" >NUL\r\n'
        f'start "" "{target}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w") as f:
        f.write(script)

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "DETACHED_PROCESS", 0
    )
    subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)
