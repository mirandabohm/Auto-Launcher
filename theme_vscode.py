#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VS Code–style ttk theme helpers for Auto-Launcher.

Usage:
    import theme_vscode as theme
    palette = theme.apply_theme(app, ttk_style, dark=True, status_widget=txt_widget)
    theme.set_alt_row_tags(tree, palette)
"""

from __future__ import annotations

from typing import Dict, Optional
import tkinter as tk
from tkinter import ttk

# Palettes roughly inspired by VS Code Dark+ and Light+
PALETTE_DARK: Dict[str, str] = {
    "bg": "#1e1e1e",         # window background
    "panel": "#252526",      # panels/controls
    "border": "#3c3c3c",     # subtle borders
    "fg": "#d4d4d4",         # primary text
    "muted": "#c5c5c5",
    "accent": "#007acc",     # VS Code blue
    "sel_bg": "#094771",
    "sel_fg": "#ffffff",
    "tree_alt_even": "#1e1e1e",
    "tree_alt_odd":  "#1b1b1b",
    "emoji": "🌙",
}

PALETTE_LIGHT: Dict[str, str] = {
    "bg": "#f3f3f3",
    "panel": "#ffffff",
    "border": "#dadada",
    "fg": "#1b1b1b",
    "muted": "#333333",
    "accent": "#007acc",
    "sel_bg": "#cce6ff",
    "sel_fg": "#000000",
    "tree_alt_even": "#ffffff",
    "tree_alt_odd":  "#f7f7f7",
    "emoji": "☀️",
}


def apply_theme(
    app: tk.Tk,
    style: ttk.Style,
    dark: bool,
    status_widget: Optional[tk.Text] = None,
) -> Dict[str, str]:
    """
    Apply a VS Code–like theme to ttk and Text widgets.

    Parameters
    ----------
    app : tk.Tk
        Root window (for background).
    style : ttk.Style
        The ttk Style instance to configure.
    dark : bool
        True for dark, False for light.
    status_widget : tk.Text, optional
        If provided, styled to match the palette.

    Returns
    -------
    Dict[str, str]
        The palette dict used (handy for later calls like set_alt_row_tags).
    """
    p = PALETTE_DARK if dark else PALETTE_LIGHT

    bg       = p["bg"]
    panel    = p["panel"]
    border   = p["border"]
    fg       = p["fg"]
    sel_bg   = p["sel_bg"]
    sel_fg   = p["sel_fg"]
    accent   = p["accent"]

    # App window background
    app.configure(bg=bg)

    # App-wide default font (subtle, optional)
    app.option_add("*Font", "Segoe UI 10")

    # Base style
    style.configure(".", background=bg, foreground=fg, fieldbackground=panel)

    # Labels & frames
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)

    # Buttons: flat
    style.configure(
        "Flat.TButton",
        background=panel,
        foreground=fg,
        borderwidth=0,
        focusthickness=0,
        padding=(10, 6),
    )
    style.map(
        "Flat.TButton",
        background=[("active", "#2a2d2e" if dark else "#eaeaea"),
                    ("pressed", "#2a2d2e" if dark else "#e5e5e5")],
        foreground=[("disabled", "#7a7a7a" if dark else "#9a9a9a")],
    )

    # Combobox
    style.configure(
        "VS.TCombobox",
        fieldbackground=panel,
        background=panel,
        foreground=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        arrowsize=16,
    )
    style.map(
        "VS.TCombobox",
        fieldbackground=[("readonly", panel)],
        foreground=[("disabled", "#7a7a7a" if dark else "#9a9a9a")],
    )

    # Treeview (table)
    style.configure(
        "Treeview",
        background=bg,
        fieldbackground=bg,
        foreground=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
        rowheight=24,
    )
    style.configure(
        "Treeview.Heading",
        background=panel,
        foreground=fg,
        bordercolor=border,
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", sel_bg)],
        foreground=[("selected", sel_fg)],
    )
    style.map("Treeview.Heading", background=[("active", "#2a2d2e" if dark else "#eaeaea")])

    # Progressbar (slim)
    style.configure("Horizontal.TProgressbar", background=accent, troughcolor=panel, thickness=6)

    # Text widget styling
    if status_widget is not None:
        status_widget.configure(
            bg=panel,
            fg=fg,
            insertbackground=fg,
            highlightthickness=1,
            highlightbackground=border,
            relief="flat",
            bd=0,
        )

    return p


def set_alt_row_tags(tree: ttk.Treeview, palette: Dict[str, str]) -> None:
    """
    Configure alternating row backgrounds for a Treeview using the palette.

    Call this once after creating the Treeview, and again if the theme changes.
    """
    tree.tag_configure("even", background=palette["tree_alt_even"])
    tree.tag_configure("odd",  background=palette["tree_alt_odd"])
