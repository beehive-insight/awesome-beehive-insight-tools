"""可复用的 tkinter UI 组件：居中弹窗、单元格悬浮提示。"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk

import presets
import style


class TreeTip:
    """Treeview 单元格悬浮提示：鼠标悬停显示单元格全文（类似 HTML title 属性）。

    只在文本超出列宽被截断时出现。用法：TreeTip(tree, {"col": "…", "…"})
    第二个参数可选，用于把 column id 映射为展示文案（默认直接显示单元格值）。
    """

    def __init__(self, tree: ttk.Treeview) -> None:
        self.tree = tree
        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None
        self._font: tkfont.Font | None = None  # 惰性缓存，避免每次 Motion 都解析样式
        tree.bind("<Motion>", self._on_motion, add=True)
        tree.bind("<Leave>", self._hide, add=True)
        # 滚动时内容移位，提示会错位，直接隐藏
        tree.bind("<MouseWheel>", self._hide, add=True)

    def _tree_font(self) -> tkfont.Font:
        if self._font is None:
            tree_font = self.tree.winfo_toplevel().tk.call(
                "ttk::style", "lookup", "Treeview", "-font"
            ) or "TkDefaultFont"
            self._font = tkfont.Font(font=tree_font)
        return self._font

    def _on_motion(self, event: tk.Event) -> None:
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if self._after_id:
            self.tree.after_cancel(self._after_id)
            self._after_id = None
        if self._tip:
            self._tip.destroy()
            self._tip = None
        if not col or not row or col == "#0":
            return
        col_id = self.tree.column(col, "id")
        value = self.tree.set(row, col_id)
        if not value:
            return
        # 文本没超出列宽就不提示
        needed = self._tree_font().measure(value)
        if needed <= int(self.tree.column(col, "width")) - 8:
            return
        x, y, _, _ = self.tree.bbox(row, col)
        self._after_id = self.tree.after(
            400, lambda: self._show(f"+{self.tree.winfo_rootx() + x}+{self.tree.winfo_rooty() + y - 26}", value)
        )

    def _show(self, where: str, text: str) -> None:
        self._tip = tw = tk.Toplevel(self.tree)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(where)
        label = tk.Label(
            tw,
            text=text,
            background=presets.PALETTE["surface"],
            foreground=presets.PALETTE["text"],
            highlightthickness=1,
            highlightbackground=presets.PALETTE["border"],
            font=self.tree.cget("font") or style.font(),
            justify="left",
        )
        label.pack(ipadx=4, ipady=2)

    def _hide(self, _event: "tk.Event | None" = None) -> None:
        if self._after_id:
            self.tree.after_cancel(self._after_id)
            self._after_id = None
        if self._tip:
            self._tip.destroy()
            self._tip = None


class CenteredDialog(tk.Toplevel):
    """相对父窗口居中的弹窗基类。

    用法：子类在 __init__ 中先 super().__init__(master)，
    再构建内容，最后调用 show() 定位显示（先隐藏避免闪烁）。
    """

    def __init__(self, master: tk.Misc, title: str) -> None:
        super().__init__(master)
        self.configure(background=presets.PALETTE["bg"])
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.withdraw()

    def show(self) -> None:
        """布局完成后定位到主窗口居中并显示。"""
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - self.winfo_width()) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
