"""统一主题配置：字体、调色板、ttk 控件样式（零依赖，clam 基座）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk

import presets

FAMILY: str | None = None  # apply_theme 后为实际使用的字体族


def _pick_family(root: tk.Tk) -> str | None:
    families = set(tkfont.families(root))
    for name in presets.FONT_CANDIDATES:
        if name in families:
            return name
    return None


def font(bold: bool = False, size: int | None = None) -> tuple | str:
    """返回字体元组；未应用主题时回退到 Tk 命名字体。"""
    if FAMILY is None:
        return "TkHeadingFont" if bold else "TkTextFont"
    s = size if size is not None else presets.FONT_SIZE
    return (FAMILY, s, "bold") if bold else (FAMILY, s)


def listbox_kwargs(**overrides) -> dict:
    """tk.Listbox 的统一配色参数。"""
    p = presets.PALETTE
    kwargs: dict = {
        "background": p["surface"],
        "foreground": p["text"],
        "selectbackground": p["accent_bg"],
        "selectforeground": p["accent"],
        "activestyle": "none",
        "highlightthickness": 0,
        "borderwidth": 0,
        "font": font(),
    }
    kwargs.update(overrides)
    return kwargs


def apply_theme(root: tk.Tk) -> None:
    """应用全局主题：字体、按钮、表格、滚动条、下拉框。"""
    global FAMILY
    p = presets.PALETTE
    FAMILY = _pick_family(root)
    if FAMILY:
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
            tkfont.nametofont(name).configure(family=FAMILY, size=presets.FONT_SIZE)

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=p["bg"], foreground=p["text"])
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])

    # 按钮：普通（白底描边，hover 浅灰）/ 主操作（蓝底白字，hover 深蓝）
    style.configure(
        "Tool.TButton",
        background=p["surface"],
        foreground=p["text"],
        bordercolor=p["border"],
        lightcolor=p["surface"],
        darkcolor=p["surface"],
        relief="flat",
        padding=(10, 3),
        focusthickness=0,
    )
    style.map(
        "Tool.TButton",
        background=[("pressed", p["accent_bg"]), ("active", p["stripe"])],
        foreground=[("pressed", p["accent_hover"])],
        bordercolor=[("pressed", p["accent"]), ("active", p["border"])],
        lightcolor=[("pressed", p["accent_bg"]), ("active", p["stripe"])],
        darkcolor=[("pressed", p["accent_bg"]), ("active", p["stripe"])],
    )
    style.configure(
        "Accent.TButton",
        background=p["accent"],
        foreground="#ffffff",
        bordercolor=p["accent"],
        lightcolor=p["accent"],
        darkcolor=p["accent"],
        relief="flat",
        padding=(12, 3),
        focusthickness=0,
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", p["accent_hover"]), ("active", p["accent_hover"])],
        bordercolor=[("pressed", p["accent_hover"]), ("active", p["accent_hover"])],
        lightcolor=[("pressed", p["accent_hover"]), ("active", p["accent_hover"])],
        darkcolor=[("pressed", p["accent_hover"]), ("active", p["accent_hover"])],
    )

    # 表格：白底、28px 行高、表头白底加粗仅下边框
    style.configure(
        "Treeview",
        background=p["surface"],
        foreground=p["text"],
        fieldbackground=p["surface"],
        bordercolor=p["border"],
        lightcolor=p["surface"],
        darkcolor=p["surface"],
        borderwidth=0,
        rowheight=28,
        font=font(),
    )
    style.map(
        "Treeview",
        background=[("selected", p["accent_bg"])],
        foreground=[("selected", p["text"])],
    )
    style.configure(
        "Treeview.Heading",
        background=p["surface"],
        foreground=p["text"],
        relief="flat",
        padding=(4, 6),
        font=font(bold=True),
    )
    style.map("Treeview.Heading", background=[("active", p["surface"])])

    # 滚动条
    style.configure(
        "TScrollbar",
        background=p["border"],
        troughcolor=p["surface"],
        bordercolor=p["surface"],
        lightcolor=p["border"],
        darkcolor=p["border"],
        arrowcolor=p["muted"],
        relief="flat",
    )
    style.map("TScrollbar", background=[("active", p["muted"]), ("pressed", p["muted"])])

    # 下拉框
    style.configure(
        "TCombobox",
        fieldbackground=p["surface"],
        background=p["surface"],
        foreground=p["text"],
        bordercolor=p["border"],
        lightcolor=p["border"],
        darkcolor=p["border"],
        arrowcolor=p["muted"],
    )
    style.map("TCombobox", fieldbackground=[("readonly", p["surface"])])
