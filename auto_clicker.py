"""
Auto-Clicker
------------
A small GUI auto-clicker that lets you:
  * choose a global hotkey to toggle clicking on/off
  * set the click speed (clicks per second)
  * choose which mouse button to click (left / right / middle)

Dependencies:
    pip install pynput

Run:
    python auto_clicker.py
"""

import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from pynput import mouse, keyboard


BUTTONS = {
    "Left": mouse.Button.left,
    "Right": mouse.Button.right,
    "Middle": mouse.Button.middle,
}


class ClickWorker(threading.Thread):
    """Background thread that performs the clicking while enabled."""

    def __init__(self):
        super().__init__(daemon=True)
        self._controller = mouse.Controller()
        self._enabled = threading.Event()
        self._stop = threading.Event()

        # Shared, runtime-adjustable settings.
        self._lock = threading.Lock()
        self._cps = 10.0
        self._button = mouse.Button.left

    # -- settings ---------------------------------------------------------
    def set_cps(self, cps):
        with self._lock:
            self._cps = max(0.1, float(cps))

    def set_button(self, button):
        with self._lock:
            self._button = button

    # -- control ----------------------------------------------------------
    def enable(self):
        self._enabled.set()

    def disable(self):
        self._enabled.clear()

    def toggle(self):
        if self._enabled.is_set():
            self.disable()
        else:
            self.enable()
        return self._enabled.is_set()

    def is_enabled(self):
        return self._enabled.is_set()

    def shutdown(self):
        self._stop.set()
        self._enabled.set()  # wake the loop so it can notice the stop flag

    # -- main loop --------------------------------------------------------
    def run(self):
        while not self._stop.is_set():
            # Wait (cheaply) until clicking is enabled.
            self._enabled.wait()
            if self._stop.is_set():
                break

            with self._lock:
                cps = self._cps
                button = self._button

            self._controller.click(button)

            # Sleep for the configured interval, but stay responsive to
            # disable/stop requests.
            interval = 1.0 / cps
            slept = 0.0
            step = min(0.02, interval)
            while slept < interval:
                if self._stop.is_set() or not self._enabled.is_set():
                    break
                time.sleep(step)
                slept += step


class HotkeyListener:
    """Captures a single global hotkey and fires a callback when pressed."""

    def __init__(self, on_trigger):
        self._on_trigger = on_trigger
        self._listener = None
        self._hotkey_str = "<f6>"

    def set_hotkey(self, hotkey_str):
        """hotkey_str uses pynput GlobalHotKeys syntax, e.g. '<f6>' or '<ctrl>+<shift>+c'."""
        self._hotkey_str = hotkey_str
        self.restart()

    def start(self):
        try:
            self._listener = keyboard.GlobalHotKeys(
                {self._hotkey_str: self._on_trigger}
            )
            self._listener.start()
            return True
        except Exception as exc:  # invalid hotkey string
            messagebox.showerror("Invalid hotkey", f"Could not register hotkey:\n{exc}")
            self._listener = None
            return False

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def restart(self):
        self.stop()
        return self.start()


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto-Clicker")
        self.root.resizable(False, False)

        self.worker = ClickWorker()
        self.worker.start()

        self.hotkey = HotkeyListener(self._on_hotkey)

        self._capturing = False
        self._capture_listener = None

        self._build_ui()

        # Register the default hotkey.
        self.hotkey.set_hotkey(self._hotkey_value())

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI ---------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        # Speed
        ttk.Label(frm, text="Clicks per second:").grid(row=0, column=0, sticky="w", **pad)
        self.cps_var = tk.StringVar(value="10")
        cps_spin = ttk.Spinbox(
            frm,
            from_=0.1,
            to=1000,
            increment=1,
            textvariable=self.cps_var,
            width=10,
            command=self._on_cps_change,
        )
        cps_spin.grid(row=0, column=1, sticky="w", **pad)
        cps_spin.bind("<KeyRelease>", lambda _e: self._on_cps_change())

        # Mouse button
        ttk.Label(frm, text="Mouse button:").grid(row=1, column=0, sticky="w", **pad)
        self.button_var = tk.StringVar(value="Left")
        button_combo = ttk.Combobox(
            frm,
            textvariable=self.button_var,
            values=list(BUTTONS.keys()),
            state="readonly",
            width=8,
        )
        button_combo.grid(row=1, column=1, sticky="w", **pad)
        button_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_button_change())

        # Hotkey
        ttk.Label(frm, text="Toggle hotkey:").grid(row=2, column=0, sticky="w", **pad)
        self.hotkey_var = tk.StringVar(value="F6")
        self.hotkey_entry = ttk.Entry(frm, textvariable=self.hotkey_var, width=18, state="readonly")
        self.hotkey_entry.grid(row=2, column=1, sticky="w", **pad)
        self.capture_btn = ttk.Button(frm, text="Set hotkey", command=self._begin_capture)
        self.capture_btn.grid(row=2, column=2, sticky="w", **pad)

        # Status / toggle
        self.status_var = tk.StringVar(value="Status: STOPPED")
        status_lbl = ttk.Label(frm, textvariable=self.status_var, font=("TkDefaultFont", 10, "bold"))
        status_lbl.grid(row=3, column=0, columnspan=3, sticky="w", **pad)

        self.toggle_btn = ttk.Button(frm, text="Start (or press hotkey)", command=self._toggle)
        self.toggle_btn.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)

        hint = ttk.Label(
            frm,
            text="Tip: position your cursor, then press the hotkey to start/stop.",
            foreground="#666",
        )
        hint.grid(row=5, column=0, columnspan=3, sticky="w", **pad)

        # Apply initial settings to the worker.
        self._on_cps_change()
        self._on_button_change()

    # -- settings handlers ------------------------------------------------
    def _on_cps_change(self):
        try:
            cps = float(self.cps_var.get())
            if cps <= 0:
                raise ValueError
            self.worker.set_cps(cps)
        except (ValueError, TypeError):
            pass  # ignore transient/invalid entry while typing

    def _on_button_change(self):
        self.worker.set_button(BUTTONS[self.button_var.get()])

    # -- hotkey capture ---------------------------------------------------
    def _hotkey_value(self):
        """Translate the friendly label into a pynput GlobalHotKeys string."""
        return self._friendly_to_pynput(self.hotkey_var.get())

    def _begin_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self.capture_btn.config(text="Press keys...")
        # Temporarily stop the active hotkey so it doesn't fire while capturing.
        self.hotkey.stop()

        self._pressed = set()
        self._capture_listener = keyboard.Listener(
            on_press=self._capture_on_press,
            on_release=self._capture_on_release,
        )
        self._capture_listener.start()

    def _capture_on_press(self, key):
        self._pressed.add(key)

    def _capture_on_release(self, _key):
        # On first release, finalize the combination that was held.
        combo = self._build_combo(self._pressed)
        self.root.after(0, lambda: self._finish_capture(combo))
        return False  # stop the capture listener

    def _finish_capture(self, combo):
        if self._capture_listener is not None:
            self._capture_listener = None
        self._capturing = False
        self.capture_btn.config(text="Set hotkey")

        if combo:
            friendly, pynput_str = combo
            self.hotkey_var.set(friendly)

        # Re-register the (possibly new) hotkey.
        self.hotkey.set_hotkey(self._hotkey_value())

    def _build_combo(self, keys):
        """Convert a set of pressed pynput keys into (friendly, pynput) strings."""
        mods = []
        main = None
        order = {"ctrl": 0, "alt": 1, "shift": 2, "cmd": 3}

        for key in keys:
            name = self._key_name(key)
            if name is None:
                continue
            base = name.lstrip("<").rstrip(">")
            if base in ("ctrl", "ctrl_l", "ctrl_r"):
                mods.append("ctrl")
            elif base in ("alt", "alt_l", "alt_r", "alt_gr"):
                mods.append("alt")
            elif base in ("shift", "shift_l", "shift_r"):
                mods.append("shift")
            elif base in ("cmd", "cmd_l", "cmd_r"):
                mods.append("cmd")
            else:
                main = name

        if main is None:
            return None

        mods = sorted(set(mods), key=lambda m: order.get(m, 9))

        friendly_parts = [m.capitalize() for m in mods] + [self._friendly_main(main)]
        pynput_parts = [f"<{m}>" for m in mods] + [main]

        return "+".join(friendly_parts), "+".join(pynput_parts)

    @staticmethod
    def _key_name(key):
        """Return a normalized name for a pynput key, or None."""
        if isinstance(key, keyboard.Key):
            return f"<{key.name}>"
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.lower()
            if key.vk is not None:
                return f"<{key.vk}>"
        return None

    @staticmethod
    def _friendly_main(main):
        m = main.lstrip("<").rstrip(">")
        return m.upper() if len(m) == 1 else m.capitalize()

    @staticmethod
    def _friendly_to_pynput(friendly):
        """Convert a friendly label like 'Ctrl+Shift+C' to '<ctrl>+<shift>+c'."""
        parts = [p.strip() for p in friendly.split("+") if p.strip()]
        out = []
        special = {
            "ctrl", "alt", "shift", "cmd",
            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
            "f10", "f11", "f12", "esc", "space", "tab", "enter",
            "delete", "home", "end", "insert", "page_up", "page_down",
            "up", "down", "left", "right", "caps_lock",
        }
        for p in parts:
            low = p.lower()
            if low in special:
                out.append(f"<{low}>")
            elif len(p) == 1:
                out.append(p.lower())
            else:
                out.append(f"<{low}>")
        return "+".join(out) if out else "<f6>"

    # -- toggle / status --------------------------------------------------
    def _on_hotkey(self):
        # Called from the listener thread; marshal to the UI thread.
        self.root.after(0, self._toggle)

    def _toggle(self):
        enabled = self.worker.toggle()
        self._refresh_status(enabled)

    def _refresh_status(self, enabled):
        if enabled:
            self.status_var.set("Status: RUNNING")
            self.toggle_btn.config(text="Stop (or press hotkey)")
        else:
            self.status_var.set("Status: STOPPED")
            self.toggle_btn.config(text="Start (or press hotkey)")

    # -- lifecycle --------------------------------------------------------
    def _on_close(self):
        self.worker.shutdown()
        self.hotkey.stop()
        if self._capture_listener is not None:
            self._capture_listener.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
