
import os
import sys
import json
import time
import threading
import datetime
import subprocess
import tkinter as tk
import webbrowser

from tkinter import ttk, messagebox, simpledialog
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
        self.profiles = sorted(cfg.get("profiles", {}).keys())
        self.selected_profile = tk.StringVar(value=self.profiles[0] if self.profiles else "")
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(padx=10, pady=10, fill="x")
        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Label(top, text="Profile:").pack(side="left")
        self.combo = ttk.Combobox(top, values=self.profiles, textvariable=self.selected_profile, state="readonly")
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_tree())
        self.combo.pack(side="left", padx=5)

        btns = ttk.Frame(self)
        btns.pack(pady=5)
        ttk.Button(btns, text="Launch Profile", command=self.launch_profile).pack(side="left", padx=4)
        ttk.Button(btns, text="Launch All", command=self.launch_all).pack(side="left", padx=4)
        ttk.Button(btns, text="Launch Selection", command=self.launch_selected_items).pack(side="left", padx=4)
        ttk.Button(btns, text="Schedule Profile", command=self.schedule).pack(side="left", padx=4)
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
        actions.add_command(label="Manage Profiles...", accelerator="Ctrl+M", command=self.open_profile_editor)
        menubar.add_cascade(label="Actions", menu=actions)

        # --- View Menu ---
        view_menu.add_command(label="Usage Summary", accelerator="Ctrl+U", command=self.usage_summary)
        view_menu.add_command(label="Open Log", accelerator="Ctrl+O", command=self.open_log)
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
        self.bind_all("<Control-m>", lambda e: self.open_profile_editor())

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
            "Ctrl + M   : Manage Profiles",
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
        self.progress["value"] = 0
        self.progress["maximum"] = len(items)
        
        for item in items:
            result = launch_item(item)
            self.append_status(result)
            log_line(f"{name} - {result}")
            self.progress["value"] += 1
            self.progress.update_idletasks()
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

    def open_profile_editor(self):
        ProfileEditor(self)

    def update_profile_list(self):
        self.combo["values"] = sorted(self.cfg.get("profiles", {}).keys())

    def save_config(self, cfg=None):
        if cfg is None:
            cfg = self.cfg
        with open("launcher_profiles.json", "w") as f:
            json.dump(cfg, f, indent=4)

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

class ProfileEditor(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Manage Profiles")
        self.geometry("500x400")
        self.parent = parent
        self.cfg = parent.cfg
        self.profiles = parent.cfg.get("profiles", {})
        self.selected_profile = tk.StringVar()
        self._drag_start_index = None

        # UI Elements
        top = ttk.Frame(self)
        top.pack(fill="x", pady=5)
        
        ttk.Label(top, text="Select Profile:").pack(side="left", padx=5)
        self.profile_combo = ttk.Combobox(top, textvariable=self.selected_profile, values=sorted(self.profiles.keys()), state="readonly")
        self.profile_combo.pack(side="left", fill="x", expand=True, padx=5)

        # Top row: profile-level buttons
        row1 = ttk.Frame(self)
        row1.pack(fill="x", padx=10, pady=3)

        ttk.Button(row1, text="New Profile", command=self.create_profile).pack(side="left", padx=5)
        ttk.Button(row1, text="Rename Profile", command=self.rename_profile).pack(side="left", padx=5)
        ttk.Button(row1, text="Delete Profile", command=self.delete_profile).pack(side="left", padx=5)

        self.profile_combo.bind("<<ComboboxSelected>>", self.load_profile_items)

        self.items_list = tk.Listbox(self)
        self.items_list.pack(fill="both", expand=True, padx=10, pady=5)
        self.items_list.bind("<Button-1>", self.on_drag_start)
        self.items_list.bind("<B1-Motion>", self.on_drag_motion)
        self.items_list.bind("<ButtonRelease-1>", self.on_drag_drop)

        # Bottom row: item-level buttons
        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(row2, text="Add Item", command=self.add_item).pack(side="left", padx=5)
        ttk.Button(row2, text="Remove Selected", command=self.remove_item).pack(side="left", padx=5)
        ttk.Button(row2, text="Save Profile", command=self.save_profile).pack(side="right", padx=5)

        # Auto-select the profile from the main UI if it's still valid
        initial_profile = parent.selected_profile.get()
        sorted_profiles = sorted(self.profiles.keys())
        self.profile_combo["values"] = sorted_profiles

        if initial_profile in self.profiles:
            self.selected_profile.set(initial_profile)
        else:
            self.selected_profile.set(sorted_profiles[0] if sorted_profiles else "")

        self.refresh_profile_list()
        self.load_profile_items()
        self.items_list.yview_moveto(0)


    def on_drag_start(self, event):
        self._drag_start_index = self.items_list.nearest(event.y)

    def on_drag_motion(self, event):
        curr_index = self.items_list.nearest(event.y)
        if self._drag_start_index is None or curr_index == self._drag_start_index:
            return

        # Swap items
        items = list(self.items_list.get(0, "end"))
        items[self._drag_start_index], items[curr_index] = items[curr_index], items[self._drag_start_index]

        # Update list
        self.items_list.delete(0, "end")
        for item in items:
            self.items_list.insert("end", item)

        # Update drag index to current
        self._drag_start_index = curr_index

    def on_drag_drop(self, event):
        self._drag_start_index = None

    def load_profile_items(self, event=None):
        self.items_list.delete(0, "end")
        name = self.selected_profile.get()
        items = self.profiles.get(name, [])
        for item in items:
            self.items_list.insert("end", f"{item['type']} | {item['label']} | {item['target']}")

    def refresh_profile_list(self):
        self.profile_combo["values"] = sorted(self.profiles.keys())
        self.profile_combo.set(self.selected_profile.get())
        
    def add_item(self):
        dlg = simpledialog.askstring("Add Item", "Enter type,label,target (comma separated):", parent=self)
        if dlg:
            try:
                type_, label, target = [s.strip() for s in dlg.split(",")]
                item_str = f"{type_} | {label} | {target}"
                self.items_list.insert("end", item_str)
            except ValueError:
                messagebox.showerror("Invalid Format", "Please enter: type,label,target", parent=self)

    def remove_item(self):
        selection = self.items_list.curselection()
        if selection:
            self.items_list.delete(selection[0])

    def create_profile(self):
        name = simpledialog.askstring("New Profile", "Enter new profile name:", parent=self)
        if not name:
            return
        if name in self.profiles:
            messagebox.showerror("Duplicate Name", f"A profile named '{name}' already exists.", parent=self)
            return

        self.profiles[name] = []
        self.selected_profile.set(name)
        self.refresh_profile_list()
        self.load_profile_items()
        
        self.cfg["profiles"] = self.profiles
        self.parent.save_config(self.cfg)
        self.parent.update_profile_list()

        self.parent.selected_profile.set(name)
        self.parent.combo.set(name)
        self.parent.refresh_tree()

    def rename_profile(self):
        old_name = self.selected_profile.get()
        if not old_name:
            return

        new_name = simpledialog.askstring("Rename Profile", "Enter new profile name:", initialvalue=old_name, parent=self)
        if not new_name or new_name == old_name:
            return
        if new_name in self.profiles:
            messagebox.showerror("Duplicate Name", f"A profile named '{new_name}' already exists.", parent=self)
            return

        # Perform rename
        self.profiles[new_name] = self.profiles.pop(old_name)
        self.selected_profile.set(new_name)
        self.refresh_profile_list()
        self.load_profile_items()

        self.cfg["profiles"] = self.profiles
        self.parent.save_config(self.cfg)

        # Update the main LauncherApp
        self.parent.update_profile_list()
        self.parent.selected_profile.set(new_name)

        # Refresh tree view to reflect the renamed profile's items
        self.parent.refresh_tree()

    def save_profile(self):
        name = self.selected_profile.get()
        items = []

        for line in self.items_list.get(0, "end"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                item = {
                    "type": parts[0],
                    "label": parts[1],
                    "target": parts[2],
                }
                items.append(item)

        self.profiles[name] = items
        self.cfg["profiles"] = self.profiles
        self.parent.save_config(self.cfg)

        # Update the parent (LauncherApp) profile list and tree
        if hasattr(self.parent, "update_profile_list"):
            self.parent.update_profile_list()

        if hasattr(self.parent, "refresh_tree"):
            self.parent.refresh_tree()

        messagebox.showinfo("Success", f"Profile '{name}' updated.", parent=self)
        self.destroy()

    def delete_profile(self):
        name = self.selected_profile.get()
        if not name:
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Delete profile '{name}'?", parent=self)
        if not confirm:
            return

        del self.profiles[name]

        # If the deleted profile was the selected one in the main UI, switch it
        if self.parent.selected_profile.get() == name:
            remaining_profiles = sorted(self.profiles.keys())
            new_selection = remaining_profiles[0] if remaining_profiles else ""
            self.parent.selected_profile.set(new_selection)
            self.parent.refresh_tree()

        self.selected_profile.set("")
        self.refresh_profile_list()
        self.items_list.delete(0, "end")
        self.cfg["profiles"] = self.profiles
        self.parent.save_config(self.cfg)
        self.parent.update_profile_list()

def main():
    cfg = load_config()
    app = LauncherApp(cfg)
    app.mainloop()

if __name__ == "__main__":
    main()
