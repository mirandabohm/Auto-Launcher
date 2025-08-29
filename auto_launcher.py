#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto-Launcher (Demo-Safe)

A config-driven launcher for opening bundles of URLs and apps, with a
VS Code–style theme, selective launching, scheduling, usage summary,
and duplicate-launch protection.

Packaged with PyInstaller, it runs as a single .exe (no Python needed).
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Any, Dict, List, Optional, Sequence

# 3rd-party
import psutil  # pip install psutil

# Tkinter
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# Theme module (must sit next to this file)
import theme_vscode as theme



# ---------------------------------------------------------------------------
# Paths & constants (EXE-friendly)
# ---------------------------------------------------------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
IS_FROZEN = getattr(sys, "frozen", False)
BASE_DIR = os.path.dirname(sys.executable) if IS_FROZEN else APP_DIR

CONFIG_PATH = os.path.join(BASE_DIR, "launcher_profiles.json")
LOG_PATH    = os.path.join(BASE_DIR, "auto_launcher_log.txt")

ICON_DARK_ICO  = os.path.join(BASE_DIR, "icon_dark.ico")
ICON_LIGHT_ICO = os.path.join(BASE_DIR, "icon_light.ico")
ICON_DARK_PNG  = os.path.join(BASE_DIR, "icon_dark.png")
ICON_LIGHT_PNG = os.path.join(BASE_DIR, "icon_light.png")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Load JSON config or show an error and exit."""
    if not os.path.exists(path):
        messagebox.showerror("Config Missing", f"Missing configuration file:\n{path}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as exc:
        messagebox.showerror("Config Error", f"Failed to parse JSON:\n{exc}")
        sys.exit(1)

    if "profiles" not in cfg or not isinstance(cfg["profiles"], dict):
        messagebox.showerror("Config Error", "Config must contain a 'profiles' object.")
        sys.exit(1)
    return cfg


def log_line(text: str, log_path: str = LOG_PATH) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{ts} - {text}\n")


def is_running(exe_name_lower: str) -> bool:
    """Return True if a process with this .exe name is running."""
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            nm = proc.info.get("name")
            if nm and nm.lower() == exe_name_lower:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def launch_item(item: Dict[str, Any], avoid_duplicates: bool = True) -> str:
    """Launch a single config item (URL or app/script)."""
    itype = item.get("type")
    label = item.get("label", itype)
    target = item.get("target")

    if itype == "url":
        webbrowser.open(str(target))
        return f"Opened URL: {label}"

    if itype == "app":
        exe_name = os.path.basename(str(target)).lower()
        if avoid_duplicates and exe_name.endswith(".exe") and is_running(exe_name):
            return f"Already running: {label}"
        try:
            subprocess.Popen([str(target)], shell=False)
            return f"Launched app: {label}"
        except FileNotFoundError:
            return f"Not found: {label} ({target})"

    return f"Unknown item type: {itype}"


def open_path_cross_platform(path: str) -> None:
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)

# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class ScheduleDialog(tk.Toplevel):
    """Small modal to collect a schedule time like '08:55' or '6:05pm'."""
    def __init__(self, parent: tk.Tk, title: str = "Schedule Launch"):
        super().__init__(parent)
        self.result: Optional[str] = None
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)

        # Center over parent
        self.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        w, h = 320, 140
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Launch time (e.g., 08:55, 8:55am, 6:05pm):").pack(anchor="w")
        # default = next whole minute
        now = datetime.datetime.now() + datetime.timedelta(minutes=1)
        default = now.strftime("%H:%M")
        self.var = tk.StringVar(value=default)
        self.entry = ttk.Entry(frm, textvariable=self.var, width=18)
        self.entry.pack(anchor="w", pady=(6, 4))
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()

        self.err = ttk.Label(frm, text="", foreground="#cc5757")
        self.err.pack(anchor="w", pady=(2, 6))

        btns = ttk.Frame(frm)
        btns.pack(anchor="e", fill="x")
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="Schedule", style="Flat.TButton", command=self._ok).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

        # Make truly modal/topmost
        self.grab_set()
        self.attributes("-topmost", True)
        self.after(50, lambda: self.attributes("-topmost", False))  # keep above initially
        self.wait_visibility()
        self.wait_window(self)

    def _ok(self) -> None:
        val = (self.var.get() or "").strip()
        if not val:
            self.err.config(text="Please enter a time.")
            return
        self.result = val
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class LauncherUI(tk.Tk):
    """Tk GUI for launching configured tool profiles with a VS Code–style theme."""

    def __init__(self, cfg: Dict[str, Any]) -> None:
        super().__init__()
        self.title("Auto-Launcher (Demo-Safe)")
        self.geometry("900x560")
        self.minsize(820, 520)

        # Config & behavior flags
        self.cfg: Dict[str, Any] = cfg
        self.profiles: List[str] = list(self.cfg.get("profiles", {}).keys())
        self.selected: tk.StringVar = tk.StringVar(
            value=self.profiles[0] if self.profiles else ""
        )

        launch_cfg = self.cfg.get("launch", {}) or {}
        self.stagger: float = float(int(launch_cfg.get("stagger_ms", 250)) / 1000.0)
        self.avoid_dupes: bool = bool(launch_cfg.get("avoid_duplicates", True))

        # Theme state
        self.dark_mode = tk.BooleanVar(value=True)
        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except Exception:
            pass
        self._icon_img: Optional[tk.PhotoImage] = None  # keep PNG ref if used
        self._palette: Dict[str, str] = {}

        # Build UI
        self._build_menu()
        self._build_widgets()
        self._bind_shortcuts()

        # Apply theme (separate module)
        self._apply_theme_wrapper(self.dark_mode.get())

        self._append_status("Ready.")
        self._refresh_preview()

    # ---------------------- Menu / Shortcuts ---------------------- #

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        # File
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open Log\t Ctrl + O", command=self.open_log)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=False)
        view_menu.add_checkbutton(
            label="Dark Mode\t Ctrl + D",
            variable=self.dark_mode,
            command=lambda: self._apply_theme_wrapper(self.dark_mode.get()),
        )
        menubar.add_cascade(label="View", menu=view_menu)

        # Actions
        act_menu = tk.Menu(menubar, tearoff=False)
        act_menu.add_command(label="Launch Selected\t Ctrl + L", command=self.launch_selected)
        act_menu.add_command(label="Launch Everything\t Ctrl + E", command=self.launch_all)
        act_menu.add_command(label="Launch Selected Items\t Ctrl + Enter", command=self.launch_chosen)
        act_menu.add_separator()
        act_menu.add_command(label="Schedule Selected…\t Ctrl + S", command=self.schedule_selected)
        act_menu.add_command(label="Usage Summary\t Ctrl + U", command=self.usage_summary)
        menubar.add_cascade(label="Actions", menu=act_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Keyboard Shortcuts…", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-l>", lambda e: self.launch_selected())
        self.bind_all("<Control-e>", lambda e: self.launch_all())
        self.bind_all("<Control-s>", lambda e: self.schedule_selected())
        self.bind_all("<Control-u>", lambda e: self.usage_summary())
        self.bind_all("<Control-o>", lambda e: self.open_log())
        self.bind_all("<Control-Return>", lambda e: self.launch_chosen())
        self.bind_all("<Control-d>", lambda e: self._toggle_dark_mode())

    def _toggle_dark_mode(self) -> None:
        self.dark_mode.set(not self.dark_mode.get())
        self._apply_theme_wrapper(self.dark_mode.get())

    def show_shortcuts(self) -> None:
        lines = [
            "Keyboard Shortcuts",
            "-------------------",
            "Ctrl + L   : Launch Selected profile",
            "Ctrl + E   : Launch Everything",
            "Ctrl + Enter : Launch Selected Items",
            "Ctrl + S   : Schedule Selected…",
            "Ctrl + U   : Usage Summary",
            "Ctrl + O   : Open Log",
            "Ctrl + D   : Toggle Dark Mode",
        ]
        messagebox.showinfo("Keyboard Shortcuts", "\n".join(lines))

    # ---------------------- Theme wrapper ---------------------- #

    def _apply_theme_wrapper(self, dark: bool) -> None:
        """Apply VS Code–style theme and update icon/title + labels."""
        # Apply external style and remember palette
        self._palette = theme.apply_theme(self, self._style, dark, status_widget=getattr(self, "status", None))
        # Configure alt-row tags on the table (if created)
        if hasattr(self, "tree"):
            theme.set_alt_row_tags(self.tree, self._palette)
        # Update title/icon and header label
        emoji = self._palette.get("emoji", "🌙" if dark else "☀️")
        self._update_icon_and_title(dark, emoji)
        if hasattr(self, "brand_label"):
            self.brand_label.configure(text=f"{emoji}  Auto-Launcher")

    def _update_icon_and_title(self, dark: bool, emoji: str) -> None:
        base = "Auto-Launcher (Demo-Safe)"
        mode = "Dark" if dark else "Light"
        self.title(f"{base} — {emoji} {mode} Mode")

        try:
            ico = ICON_DARK_ICO if dark else ICON_LIGHT_ICO
            if os.path.exists(ico) and hasattr(self, "iconbitmap"):
                self.iconbitmap(ico)  # type: ignore[arg-type]
                return
            png = ICON_DARK_PNG if dark else ICON_LIGHT_PNG
            if os.path.exists(png):
                img = tk.PhotoImage(file=png)
                self.iconphoto(True, img)
                self._icon_img = img  # keep reference
        except Exception:
            pass

    # ---------------------- Layout & Widgets ---------------------- #

    def _build_widgets(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(10, 6))
        self.brand_label = ttk.Label(header, text="🌙  Auto-Launcher", font=("Segoe UI Semibold", 18))
        self.brand_label.pack(side="left", padx=12)

        top = ttk.Frame(self)
        top.pack(fill="x", padx=12)
        ttk.Label(top, text="Profile:").grid(row=0, column=0, padx=(0, 8), pady=6, sticky="e")
        self.combo = ttk.Combobox(
            top, values=self.profiles, textvariable=self.selected,
            state="readonly", width=40, style="VS.TCombobox"
        )
        self.combo.grid(row=0, column=1, padx=(0, 8), pady=6, sticky="w")
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())

        # Buttons row (single line, short labels)
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=(2, 8))
        ttk.Button(btns, text="Launch Selected",      style="Flat.TButton", command=self.launch_selected).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Launch Everything",    style="Flat.TButton", command=self.launch_all).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Launch Selected Items",style="Flat.TButton", command=self.launch_chosen).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Schedule",             style="Flat.TButton", command=self.schedule_selected).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Usage Summary",        style="Flat.TButton", command=self.usage_summary).pack(side="left", padx=4, pady=2)
        ttk.Button(btns, text="Open Log",             style="Flat.TButton", command=self.open_log).pack(side="left", padx=4, pady=2)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Left: preview table
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)
        cols = ("type", "label", "target")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("type", text="Type")
        self.tree.heading("label", text="Label")
        self.tree.heading("target", text="Target")
        self.tree.column("type", width=80, anchor="w")
        self.tree.column("label", width=250, anchor="w")
        self.tree.column("target", width=420, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")

        # Right: status + progress
        right = ttk.Frame(main)
        right.pack(side="right", fill="y")
        self.progress = ttk.Progressbar(right, mode="determinate", length=240)
        self.progress.pack(pady=(4, 6))
        self.status = tk.Text(right, height=24, width=38, state="disabled")
        self.status.pack(fill="y")

    # ---------------------- Status helper ---------------------- #

    def _append_status(self, text: str) -> None:
        self.status.configure(state="normal")
        self.status.insert("end", text + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    # ---------------------- Preview ---------------------- #

    def _refresh_preview(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        # ensure alt-row tags reflect current theme
        theme.set_alt_row_tags(self.tree, self._palette or theme.PALETTE_DARK)

        self._current_preview: List[Dict[str, Any]] = []
        self._tree_id_to_index: Dict[str, int] = {}

        name = self.selected.get()
        items = self.cfg.get("profiles", {}).get(name, [])
        for idx, it in enumerate(items):
            itype = (it.get("type") or "").upper()
            label = it.get("label") or ""
            target = it.get("target") or ""
            tag = "odd" if idx % 2 else "even"
            iid = self.tree.insert("", "end", values=(itype, label, target), tags=(tag,))
            self._current_preview.append(dict(it))
            self._tree_id_to_index[iid] = idx

    # ---------------------- Launch logic ---------------------- #

    def _threaded_launch(self, profile_names: Sequence[str]) -> None:
        try:
            total = sum(len(self.cfg["profiles"].get(n, [])) for n in profile_names) or 1
            self.progress["value"] = 0
            self.progress["maximum"] = total

            for name in profile_names:
                items = self.cfg["profiles"].get(name, [])
                self._append_status(f"Launching: {name}")
                log_line(f"Launching profile: {name}")
                for item in items:
                    msg = launch_item(item, avoid_duplicates=self.avoid_dupes)
                    self._append_status(f"  - {msg}")
                    self.progress["value"] += 1
                    self.update_idletasks()
                    time.sleep(self.stagger)
            self._append_status("Done.")
        except Exception as exc:
            messagebox.showerror("Launch Error", str(exc))

    def _threaded_launch_items(self, items: List[Dict[str, Any]], logical_name: str = "Selected Items") -> None:
        try:
            total = len(items) or 1
            self.progress["value"] = 0
            self.progress["maximum"] = total
            self._append_status(f"Launching: {logical_name}")
            log_line(f"Launching profile: {logical_name}")
            for item in items:
                msg = launch_item(item, avoid_duplicates=self.avoid_dupes)
                self._append_status(f"  - {msg}")
                self.progress["value"] += 1
                self.update_idletasks()
                time.sleep(self.stagger)
            self._append_status("Done.")
        except Exception as exc:
            messagebox.showerror("Launch Error", str(exc))

    def launch_selected(self) -> None:
        name = self.selected.get()
        if not name:
            messagebox.showwarning("No Profile Selected", "Please select a profile.")
            return
        threading.Thread(target=self._threaded_launch, args=([name],), daemon=True).start()

    def launch_all(self) -> None:
        if not self.profiles:
            messagebox.showinfo("No Profiles", "No profiles are configured.")
            return
        threading.Thread(target=self._threaded_launch, args=(self.profiles,), daemon=True).start()

    def launch_chosen(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select one or more rows to launch.")
            return
        items: List[Dict[str, Any]] = []
        for iid in selection:
            idx = self._tree_id_to_index.get(iid)
            if idx is not None and 0 <= idx < len(self._current_preview):
                items.append(self._current_preview[idx])
        threading.Thread(target=self._threaded_launch_items, args=(items, "Selected Items"), daemon=True).start()

    # ---------------------- Log, schedule, analytics ---------------------- #

    def open_log(self) -> None:
        if os.path.exists(LOG_PATH):
            open_path_cross_platform(LOG_PATH)
        else:
            messagebox.showinfo("Log", "No log entries yet.")

    def _parse_time_to_seconds(self, timestr: str) -> Optional[int]:
        try:
            s = timestr.strip().lower().replace(" ", "")
            ampm = None
            if s.endswith(("am", "pm")):
                ampm, s = s[-2:], s[:-2]
            hh_str, mm_str = s.split(":")
            hh, mm = int(hh_str), int(mm_str)
            if ampm == "pm" and hh != 12:
                hh += 12
            if ampm == "am" and hh == 12:
                hh = 0
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return None
            return hh * 3600 + mm * 60
        except Exception:
            return None

    def schedule_selected(self) -> None:
        name = self.selected.get()
        if not name:
            messagebox.showwarning("No Profile Selected", "Please select a profile.")
            return

        dlg = ScheduleDialog(self)
        timestr = dlg.result
        if not timestr:
            return  # user cancelled

        target = self._parse_time_to_seconds(timestr)
        if target is None:
            messagebox.showerror("Invalid Time", "Enter a valid time like 08:55 or 6:05pm.")
            return

        now = datetime.datetime.now()
        now_secs = now.hour * 3600 + now.minute * 60 + now.second
        delay = (target - now_secs) % (24 * 3600)  # wrap to next day if needed
        when_str = (now + datetime.timedelta(seconds=delay)).strftime("%Y-%m-%d %H:%M")

        self._append_status(f"Scheduled '{name}' for {when_str} (in {int(delay/60)} min).")
        log_line(f"Scheduled '{name}' for {when_str}")

        # Fire using a Timer (cleaner than a manual sleep thread)
        def _fire():
            # Run the normal threaded launcher (already updates progress/status)
            try:
                self._append_status(f"Launching (scheduled): {name}")
                self._threaded_launch([name])
            except Exception as exc:
                messagebox.showerror("Schedule Error", str(exc))

        t = threading.Timer(delay, _fire)
        t.daemon = True
        t.start()

    def usage_summary(self) -> None:
        if not os.path.exists(LOG_PATH):
            messagebox.showinfo("Usage Summary", "No log entries yet.")
            return

        from collections import defaultdict
        by_profile: Dict[str, int] = defaultdict(int)
        last_used: Dict[str, str] = {}

        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "Launching profile:" in line and " - " in line:
                    try:
                        ts, rest = line.split(" - ", 1)
                        prof = rest.split("Launching profile:", 1)[1].strip()
                        by_profile[prof] += 1
                        last_used[prof] = ts
                    except Exception:
                        continue

        if not by_profile:
            messagebox.showinfo("Usage Summary", "No profile launches recorded yet.")
            return

        total_launches = sum(by_profile.values())
        most_used = max(by_profile.items(), key=lambda kv: kv[1])[0]
        lines = [
            "Usage Summary",
            "--------------",
            f"Total launches: {total_launches}",
            f"Most used: {most_used}",
            "",
            "By profile:",
        ]
        for prof in sorted(by_profile.keys()):
            count = by_profile[prof]
            last = last_used.get(prof, "—")
            lines.append(f"  - {prof}: {count} (last: {last})")
        messagebox.showinfo("Usage Summary", "\n".join(lines))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = load_config(CONFIG_PATH)
    app = LauncherUI(cfg)
    app.mainloop()


if __name__ == "__main__":
    main()
