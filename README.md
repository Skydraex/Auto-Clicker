# Auto-Clicker

A simple cross-platform auto-clicker with a clean dark GUI. You can:

- **Choose a global hotkey** to toggle clicking on and off. It uses a
  system-wide keyboard hook, so it fires **even when the window is in the
  background or a game is focused** — ideal for AFK games.
- **Set the click speed** in clicks per second (CPS).
- **Pick the mouse button** to click (left / right / middle).

The Windows build also **auto-updates**: on launch it checks the latest
GitHub release and, if the published binary has changed, downloads it and
relaunches automatically.

## Requirements

- Python 3.8+
- [`pynput`](https://pypi.org/project/pynput/)

Tkinter is used for the GUI and ships with most Python installations. On some
Linux distros you may need to install it separately (e.g. `sudo apt install
python3-tk`).

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python auto_clicker.py
```

## Usage

1. Set **Clicks per second** to your desired speed.
2. Choose the **Mouse button**.
3. Click **Set hotkey**, then press the key combination you want (e.g. `F6`, or
   `Ctrl+Shift+C`). The default is `F6`.
4. Position your cursor where you want to click and press the hotkey (or click
   **Start**) to toggle clicking on/off.

## Releasing

Versions are driven by the [`VERSION`](VERSION) file (e.g. `1.1.0`) — the
single source of truth. To cut a new release:

1. Bump the number in `VERSION` (and commit it).
2. Push to `master`.

CI builds the Windows `.exe`, tags it `vX.Y.Z`, and publishes it as the
**latest release**. The number in `VERSION` is also embedded in the binary.
(You can also push a `vX.Y.Z` git tag, or run the workflow manually with a tag
override.)

## Notes

- **Linux**: `pynput` requires an X server. Under Wayland, global hotkey and
  input support can be limited.
- **macOS**: You must grant the terminal/Python **Accessibility** permission
  (System Settings → Privacy & Security → Accessibility) for input control and
  global hotkeys to work.
- Use responsibly. Many games and online services prohibit automated input.
