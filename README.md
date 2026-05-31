# Auto-Clicker

A simple cross-platform auto-clicker with a GUI. You can:

- **Choose a global hotkey** to toggle clicking on and off (works even when the
  window is not focused).
- **Set the click speed** in clicks per second (CPS).
- **Pick the mouse button** to click (left / right / middle).

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

## Notes

- **Linux**: `pynput` requires an X server. Under Wayland, global hotkey and
  input support can be limited.
- **macOS**: You must grant the terminal/Python **Accessibility** permission
  (System Settings → Privacy & Security → Accessibility) for input control and
  global hotkeys to work.
- Use responsibly. Many games and online services prohibit automated input.
