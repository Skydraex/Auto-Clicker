"""
Auto-Clicker
------------
A small GUI auto-clicker that lets you:
  * choose a GLOBAL hotkey to toggle clicking on/off (works even when the
    app is in the background or a game is focused -- ideal for AFK games)
  * set the click speed (clicks per second)
  * choose which mouse button to click (left / right / middle)

Dependencies:
    pip install pynput

Run:
    python auto_clicker.py
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from pynput import mouse, keyboard

import updater


BUTTONS = {
    "Left": mouse.Button.left,
    "Right": mouse.Button.right,
    "Middle": mouse.Button.middle,
}


# --- Theme -----------------------------------------------------------------
# A soft dark palette (Catppuccin-inspired) so it doesn't look like a
# bog-standard Tk window.
class Theme:
    BG = "#1e1e2e"        # window background
    CARD = "#28283c"      # card surface
    FIELD = "#3b3b54"     # input background
    TEXT = "#cdd6f4"      # primary text
    SUBTEXT = "#9399b2"   # muted text
    ACCENT = "#89b4fa"    # accent (blue)
    GREEN = "#a6e3a1"     # running
    GREEN_HOVER = "#94d68f"
    RED = "#f38ba8"       # stop
    RED_HOVER = "#eb7299"
    DARK = "#11111b"      # text on bright buttons
    FONT = "Segoe UI"


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
    """Captures a single global hotkey and fires a callback when pressed.

    Uses pynput's GlobalHotKeys, which installs a system-wide keyboard hook,
    so the hotkey is detected even when this window is unfocused / in the
    background (e.g. while an AFK game is in the foreground).
    """

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
        self.root.configure(bg=Theme.BG)

        self.worker = ClickWorker()
        self.worker.start()

        self.hotkey = HotkeyListener(self._on_hotkey)

        self._capturing = False
        self._capture_listener = None

        self._setup_styles()
        self._build_ui()

        # Register the default hotkey.
        self.hotkey.set_hotkey(self._hotkey_value())

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- styling ----------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=Theme.BG)
        style.configure("Card.TFrame", background=Theme.CARD)
        style.configure(
            "Field.TLabel", background=Theme.CARD, foreground=Theme.TEXT,
            font=(Theme.FONT, 10),
        )

        # Spinbox
        style.configure(
            "Dark.TSpinbox",
            fieldbackground=Theme.FIELD, background=Theme.FIELD,
            foreground=Theme.TEXT, arrowcolor=Theme.TEXT,
            bordercolor=Theme.FIELD, lightcolor=Theme.FIELD,
            darkcolor=Theme.FIELD, insertcolor=Theme.TEXT,
            relief="flat", padding=4,
        )
        style.map(
            "Dark.TSpinbox",
            fieldbackground=[("focus", Theme.FIELD)],
            bordercolor=[("focus", Theme.ACCENT)],
        )

        # Combobox
        style.configure(
            "Dark.TCombobox",
            fieldbackground=Theme.FIELD, background=Theme.FIELD,
            foreground=Theme.TEXT, arrowcolor=Theme.TEXT,
            bordercolor=Theme.FIELD, lightcolor=Theme.FIELD,
            darkcolor=Theme.FIELD, selectbackground=Theme.FIELD,
            selectforeground=Theme.TEXT, relief="flat", padding=4,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", Theme.FIELD)],
            foreground=[("readonly", Theme.TEXT)],
            bordercolor=[("focus", Theme.ACCENT)],
        )
        # Dropdown list colors (Tk option DB, not ttk).
        self.root.option_add("*TCombobox*Listbox.background", Theme.FIELD)
        self.root.option_add("*TCombobox*Listbox.foreground", Theme.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", Theme.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", Theme.DARK)

        # Entry (read-only hotkey display)
        style.configure(
            "Dark.TEntry",
            fieldbackground=Theme.FIELD, foreground=Theme.TEXT,
            bordercolor=Theme.FIELD, lightcolor=Theme.FIELD,
            darkcolor=Theme.FIELD, insertcolor=Theme.TEXT,
            relief="flat", padding=6,
        )
        style.map("Dark.TEntry", fieldbackground=[("readonly", Theme.FIELD)],
                  foreground=[("readonly", Theme.TEXT)])

        # Secondary button ("Set hotkey")
        style.configure(
            "Set.TButton",
            background=Theme.FIELD, foreground=Theme.TEXT,
            font=(Theme.FONT, 9, "bold"), borderwidth=0,
            focuscolor=Theme.CARD, padding=(12, 7), relief="flat",
        )
        style.map(
            "Set.TButton",
            background=[("active", Theme.ACCENT), ("pressed", Theme.ACCENT)],
            foreground=[("active", Theme.DARK), ("pressed", Theme.DARK)],
        )

    # -- UI ---------------------------------------------------------------
    def _build_ui(self):
        outer = ttk.Frame(self.root, style="TFrame", padding=18)
        outer.grid(row=0, column=0, sticky="nsew")

        # Header
        header = ttk.Frame(outer, style="TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        tk.Label(
            header, text="⚡  Auto-Clicker", bg=Theme.BG, fg=Theme.ACCENT,
            font=(Theme.FONT, 19, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header, text="Global hotkey — works while a game is focused",
            bg=Theme.BG, fg=Theme.SUBTEXT, font=(Theme.FONT, 9),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Settings card
        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.grid(row=1, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        def label(text, r):
            ttk.Label(card, text=text, style="Field.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=8
            )

        # Speed
        label("Clicks / second", 0)
        self.cps_var = tk.StringVar(value="10")
        cps_spin = ttk.Spinbox(
            card, from_=0.1, to=1000, increment=1, textvariable=self.cps_var,
            width=10, style="Dark.TSpinbox", command=self._on_cps_change,
        )
        cps_spin.grid(row=0, column=1, columnspan=2, sticky="w", pady=8)
        cps_spin.bind("<KeyRelease>", lambda _e: self._on_cps_change())

        # Mouse button
        label("Mouse button", 1)
        self.button_var = tk.StringVar(value="Left")
        button_combo = ttk.Combobox(
            card, textvariable=self.button_var, values=list(BUTTONS.keys()),
            state="readonly", width=9, style="Dark.TCombobox",
        )
        button_combo.grid(row=1, column=1, columnspan=2, sticky="w", pady=8)
        button_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_button_change())

        # Hotkey
        label("Toggle hotkey", 2)
        self.hotkey_var = tk.StringVar(value="F6")
        self.hotkey_entry = ttk.Entry(
            card, textvariable=self.hotkey_var, width=14, state="readonly",
            style="Dark.TEntry", justify="center",
        )
        self.hotkey_entry.grid(row=2, column=1, sticky="ew", pady=8, padx=(0, 8))
        self.capture_btn = ttk.Button(
            card, text="Set", style="Set.TButton", command=self._begin_capture,
        )
        self.capture_btn.grid(row=2, column=2, sticky="e", pady=8)

        # Status pill
        self.status_lbl = tk.Label(
            outer, text="●  STOPPED", bg=Theme.CARD, fg=Theme.SUBTEXT,
            font=(Theme.FONT, 11, "bold"), padx=14, pady=8,
        )
        self.status_lbl.grid(row=2, column=0, sticky="ew", pady=(14, 10))

        # Big toggle button (classic tk.Button for full color control)
        self.toggle_btn = tk.Button(
            outer, text="▶  Start", command=self._toggle,
            bg=Theme.GREEN, fg=Theme.DARK, activebackground=Theme.GREEN_HOVER,
            activeforeground=Theme.DARK, font=(Theme.FONT, 12, "bold"),
            relief="flat", bd=0, cursor="hand2", pady=11,
        )
        self.toggle_btn.grid(row=3, column=0, sticky="ew")
        self._add_hover(self.toggle_btn)

        # Hint
        tk.Label(
            outer,
            text="Tip: place your cursor, then press the hotkey to toggle.",
            bg=Theme.BG, fg=Theme.SUBTEXT, font=(Theme.FONT, 8),
        ).grid(row=4, column=0, sticky="w", pady=(12, 0))

        # Apply initial settings to the worker.
        self._on_cps_change()
        self._on_button_change()
        self._refresh_status(False)

    def _add_hover(self, btn):
        """Track the button's base color so hover restores it correctly."""
        def on_enter(_e):
            btn["bg"] = btn._hover
        def on_leave(_e):
            btn["bg"] = btn._base
        btn._base = Theme.GREEN
        btn._hover = Theme.GREEN_HOVER
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

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
        self.capture_btn.config(text="Press…")
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
        self.capture_btn.config(text="Set")

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
            self.status_lbl.config(text="●  RUNNING", fg=Theme.GREEN)
            self.toggle_btn.config(
                text="■  Stop", bg=Theme.RED, activebackground=Theme.RED_HOVER,
            )
            self.toggle_btn._base = Theme.RED
            self.toggle_btn._hover = Theme.RED_HOVER
        else:
            self.status_lbl.config(text="●  STOPPED", fg=Theme.SUBTEXT)
            self.toggle_btn.config(
                text="▶  Start", bg=Theme.GREEN, activebackground=Theme.GREEN_HOVER,
            )
            self.toggle_btn._base = Theme.GREEN
            self.toggle_btn._hover = Theme.GREEN_HOVER

    # -- lifecycle --------------------------------------------------------
    def _on_close(self):
        self.worker.shutdown()
        self.hotkey.stop()
        if self._capture_listener is not None:
            self._capture_listener.stop()
        self.root.destroy()


def _run_update_flow(url):
    """Show a tiny themed window while the update downloads, then relaunch."""
    splash = tk.Tk()
    splash.title("Updating Auto-Clicker")
    splash.resizable(False, False)
    splash.configure(bg=Theme.BG)

    frm = tk.Frame(splash, bg=Theme.BG, padx=26, pady=22)
    frm.pack()
    tk.Label(
        frm, text="⚡  Auto-Clicker", bg=Theme.BG, fg=Theme.ACCENT,
        font=(Theme.FONT, 15, "bold"),
    ).pack(anchor="w")
    msg = tk.StringVar(value="Checking for the latest version…")
    tk.Label(
        frm, textvariable=msg, bg=Theme.BG, fg=Theme.SUBTEXT,
        font=(Theme.FONT, 10),
    ).pack(anchor="w", pady=(8, 0))

    bar = ttk.Progressbar(frm, mode="indeterminate", length=240)
    bar.pack(pady=(14, 2), fill="x")
    bar.start(12)

    def worker():
        try:
            updater.apply_update(url, lambda m: msg.set(m))
            msg.set("Restarting…")
        except Exception:
            msg.set("Update failed — starting current version.")
            splash.after(1200, lambda: splash.quit())
            return
        # Updated successfully: exit so the helper can swap in the new exe.
        splash.after(700, lambda: os._exit(0))

    threading.Thread(target=worker, daemon=True).start()
    splash.mainloop()
    try:
        splash.destroy()
    except Exception:
        pass


def main():
    # Force-update to the latest published build before launching (frozen exe
    # only; silently skipped when running from source or offline).
    update_url = updater.check_for_update()
    if update_url:
        _run_update_flow(update_url)

    root = tk.Tk()
    # Give the window a sensible minimum width so the layout breathes.
    root.minsize(340, 0)
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
