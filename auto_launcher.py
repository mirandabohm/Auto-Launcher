
import os
import sys
import json
import time
import threading
import datetime
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from collections import defaultdict

CONFIG_PATH = "launcher_profiles.json"
LOG_PATH = "auto_launcher_log.txt"

def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        messagebox.showerror("Missing Config", f"Cannot find: {path}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "profiles" not in cfg or not isinstance(cfg["profiles"], dict):
            raise ValueError("Missing 'profiles' dictionary in config.")
        return cfg
    except Exception as e:
        messagebox.showerror("Config Error", str(e))
        sys.exit(1)

def log_line(text):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{ts} - {text}\n")

def launch_item(item):
    itype = item.get("type")
    target = item.get("target")
    label = item.get("label", target)

    try:
        if itype == "url":
            webbrowser.open(target)
            return f"Opened URL: {label}"
        elif itype == "app":
            subprocess.Popen(target)
            return f"Launched App: {label}"
        else:
            return f"Unknown type: {itype}"
    except Exception as e:
        return f"Failed to launch {label}: {e}"

class ScheduleDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Schedule Launch")
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Enter launch time (e.g., 08:30 or 5:45pm):").pack(anchor="w")
        self.var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.var)
        self.entry.pack(fill="x", pady=5)
        self.entry.focus()

        self.err_label = ttk.Label(frame, text="", foreground="red")
        self.err_label.pack(anchor="w")

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=10)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="OK", command=self._ok).pack(side="right", padx=5)

    def _ok(self):
        val = self.var.get().strip()
        if not val:
            self.err_label.config(text="Please enter a time.")
            return
        self.result = val
        self.destroy()

class LauncherApp(tk.Tk):
    def __init__(self, cfg):
        super().__init__()
        self.title("Auto-Launcher (Full Version)")
        self.geometry("800x500")
        self.cfg = cfg
        self.profiles = list(cfg.get("profiles", {}).keys())
        self.selected_profile = tk.StringVar(value=self.profiles[0] if self.profiles else "")
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(padx=10, pady=10, fill="x")
        ttk.Label(top, text="Profile:").pack(side="left")
        self.combo = ttk.Combobox(top, values=self.profiles, textvariable=self.selected_profile, state="readonly")
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_tree())
        self.combo.pack(side="left", padx=5)

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        ttk.Button(btns, text="Launch Profile", command=self.launch_profile).pack(side="left", padx=4)
        ttk.Button(btns, text="Launch All", command=self.launch_all).pack(side="left", padx=4)
        ttk.Button(btns, text="Launch Selection", command=self.launch_selected_items).pack(side="left", padx=4)
        ttk.Button(btns, text="Schedule", command=self.schedule).pack(side="left", padx=4)
        ttk.Button(btns, text="Usage Summary", command=self.usage_summary).pack(side="left", padx=4)
        ttk.Button(btns, text="Open Log", command=self.open_log).pack(side="left", padx=4)

        columns = ("type", "label", "target")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, anchor="w", width=200 if col != "type" else 80)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_tree()

        self.status = tk.Text(self, height=5, state="disabled")
        self.status.pack(fill="x", padx=10, pady=(0, 10))

    def _build_menu(self):
        menubar = tk.Menu(self)
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        actions = tk.Menu(menubar, tearoff=0)
        view_menu = tk.Menu(menubar, tearoff=0)
        help_menu = tk.Menu(menubar, tearoff=0)

        # --- File Menu ---
        file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        # --- Actions Menu ---
        actions.add_command(label="Launch Profile", accelerator="Ctrl+L", command=self.launch_profile)
        actions.add_command(label="Launch Everything", accelerator="Ctrl+E", command=self.launch_all)
        actions.add_command(label="Launch Selected Items", accelerator="Ctrl+Return", command=self.launch_selected_items)
        actions.add_separator()
        actions.add_command(label="Schedule Selected...", accelerator="Ctrl+S", command=self.schedule)
        actions.add_command(label="Usage Summary", accelerator="Ctrl+U", command=self.usage_summary)
        actions.add_command(label="Open Log", accelerator="Ctrl+O", command=self.open_log)

        menubar.add_cascade(label="Actions", menu=actions)  # ✅ This stays

        # --- View Menu ---
        # view_menu.add_command(label="Toggle Dark Mode", accelerator="Ctrl+D", command=self.toggle_dark_mode)
        menubar.add_cascade(label="View", menu=view_menu)

        # --- Help Menu ---
        help_menu.add_command(label="Keyboard Shortcuts", accelerator="F1", command=self.show_shortcuts)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _bind_shortcuts(self):
        self.bind_all("<Control-l>", lambda e: self.launch_profile())
        self.bind_all("<Control-e>", lambda e: self.launch_all())
        self.bind_all("<Control-Return>", lambda e: self.launch_selected_items())
        self.bind_all("<Control-s>", lambda e: self.schedule())
        self.bind_all("<Control-u>", lambda e: self.usage_summary())
        self.bind_all("<Control-o>", lambda e: self.open_log())
        self.bind_all("<F1>", lambda e: self.show_shortcuts())
        # self.bind_all("<Control-d>", lambda e: self.toggle_dark_mode())  # if dark mode returns

    def show_shortcuts(self):
        shortcuts = [
            "Keyboard Shortcuts",
            "-------------------",
            "Ctrl + L   : Launch Selected profile",
            "Ctrl + E   : Launch Everything",
            "Ctrl + Enter : Launch Selected Items",
            "Ctrl + S   : Schedule Selected...",
            "Ctrl + U   : Usage Summary",
            "Ctrl + O   : Open Log",
            # "Ctrl + D   : Toggle Dark Mode",
            "F1         : Show Keyboard Shortcuts",
        ]
        messagebox.showinfo("Keyboard Shortcuts", "\n".join(shortcuts))

    def refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        name = self.selected_profile.get()
        for item in self.cfg["profiles"].get(name, []):
            self.tree.insert("", "end", values=(item.get("type", ""), item.get("label", ""), item.get("target", "")))

    def append_status(self, text):
        self.status.configure(state="normal")
        self.status.insert("end", text + "\n")
        self.status.configure(state="disabled")
        self.status.see("end")

    def parse_time(self, timestr):
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
            return hh * 3600 + mm * 60
        except:
            return None

    def schedule(self):
        dlg = ScheduleDialog(self)
        self.wait_window(dlg)
        result = dlg.result
        if not result:
            return

        target_secs = self.parse_time(result)
        if target_secs is None:
            messagebox.showerror("Invalid Time", "Could not parse the time. Use HH:MM or HH:MMam/pm.")
            return

        now = datetime.datetime.now()
        now_secs = now.hour * 3600 + now.minute * 60 + now.second
        delay = (target_secs - now_secs) % (24 * 3600)

        profile = self.selected_profile.get()
        self.append_status(f"Scheduled '{profile}' for {int(delay/60)} minutes from now.")

        def launch():
            self.append_status(f"Launching scheduled profile: {profile}")
            self.run_profile(profile)

        threading.Timer(delay, launch).start()

    def run_profile(self, name):
        items = self.cfg.get("profiles", {}).get(name, [])
        for item in items:
            result = launch_item(item)
            self.append_status(result)
            log_line(f"{name} - {result}")
            time.sleep(0.5)

    def launch_profile(self):
        name = self.selected_profile.get()
        if not name:
            messagebox.showwarning("No Profile Selected", "Select a profile.")
            return
        threading.Thread(target=self.run_profile, args=(name,), daemon=True).start()

    def launch_all(self):
        for name in self.profiles:
            threading.Thread(target=self.run_profile, args=(name,), daemon=True).start()

    def launch_selected_items(self):
        selection = self.tree.selection()
        items = []
        for iid in selection:
            values = self.tree.item(iid)["values"]
            items.append({
                "type": values[0],
                "label": values[1],
                "target": values[2]
            })
        def launch():
            for item in items:
                result = launch_item(item)
                self.append_status(result)
                log_line(f"Manual - {result}")
                time.sleep(0.5)
        threading.Thread(target=launch, daemon=True).start()

    def usage_summary(self):
        if not os.path.exists(LOG_PATH):
            messagebox.showinfo("Usage Summary", "No log entries found.")
            return
        counts = defaultdict(int)
        last_used = {}
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if " - " in line:
                    ts, rest = line.strip().split(" - ", 1)
                    prof = rest.split(" - ")[0]
                    counts[prof] += 1
                    last_used[prof] = ts
        lines = [f"{p}: {counts[p]} launches (last: {last_used.get(p, '-')})" for p in sorted(counts)]
        messagebox.showinfo("Usage Summary", "\n".join(lines))

    def open_log(self):
        if os.path.exists(LOG_PATH):
            if sys.platform == "win32":
                os.startfile(LOG_PATH)
            elif sys.platform == "darwin":
                subprocess.call(["open", LOG_PATH])
            else:
                subprocess.call(["xdg-open", LOG_PATH])
        else:
            messagebox.showinfo("Log", "No log file found.")

def main():
    cfg = load_config()
    app = LauncherApp(cfg)
    app.mainloop()

if __name__ == "__main__":
    main()
