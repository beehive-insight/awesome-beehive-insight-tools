"""弹窗组件：编辑组、管理目录、设置。"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

import config
import style
from presets import (
    ABOUT_URL,
    APP_DESCRIPTION,
    APP_NAME,
    APP_NAME_EN,
    APP_VERSION,
    PALETTE,
    TERMINAL_CHOICES,
)
from ui_widgets import CenteredDialog

ALL_GROUPS = "全部"


class ManageGroupsDialog(CenteredDialog):
    """编辑组弹窗：左侧组列表 + 添加/重命名/删除。"""

    def __init__(self, master: tk.Misc, groups: dict[str, list[str]], on_changed) -> None:
        super().__init__(master, "编辑组")
        self.groups = groups
        self.on_changed = on_changed

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill="x")
        ttk.Button(btns, text="➕ 添加", style="Tool.TButton", command=self._add).pack(side="left")
        ttk.Button(
            btns, text="📝 重命名", style="Tool.TButton", command=self._rename
        ).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="🗑 删除", style="Tool.TButton", command=self._delete).pack(
            side="left", padx=(6, 0)
        )

        self.listbox = tk.Listbox(
            frame, width=28, height=10, exportselection=False, **style.listbox_kwargs()
        )
        self.listbox.pack(fill="both", expand=True, pady=(8, 0))
        self._reload()

        ttk.Button(frame, text="关闭", style="Tool.TButton", command=self.destroy).pack(
            anchor="e", pady=(10, 0)
        )
        ttk.Label(
            frame, text="删除组会同时移除其目录配置", foreground=PALETTE["muted"]
        ).pack(anchor="w", pady=(6, 0))

    def _reload(self, select: str | None = None) -> None:
        self.listbox.delete(0, "end")
        for name in self.groups:
            self.listbox.insert("end", name)
        if select and select in self.groups:
            self.listbox.selection_set(self.listbox.get(0, "end").index(select))

    def _picked(self) -> str | None:
        sel = self.listbox.curselection()
        return self.listbox.get(sel[0]) if sel else None

    def _add(self) -> None:
        name = simpledialog.askstring("添加组", "组名：", parent=self)
        if not name or name == ALL_GROUPS or name in self.groups:
            return
        self.groups[name] = []
        self.on_changed()
        self._reload(select=name)

    def _rename(self) -> None:
        group = self._picked()
        if not group:
            messagebox.showinfo("提示", "请先在列表中选择一个组", parent=self)
            return
        name = simpledialog.askstring(
            "重命名组", f"「{group}」的新组名：", initialvalue=group, parent=self
        )
        if not name or name == ALL_GROUPS or name in self.groups:
            return
        self.groups[name] = self.groups.pop(group)
        self.on_changed()
        self._reload(select=name)

    def _delete(self) -> None:
        group = self._picked()
        if not group:
            messagebox.showinfo("提示", "请先在列表中选择一个组", parent=self)
            return
        if messagebox.askyesno("删除组", f"确定删除组「{group}」及其目录配置？", parent=self):
            del self.groups[group]
            self.on_changed()
            self._reload()


class ManageRootsDialog(CenteredDialog):
    """管理目录弹窗：左选组，右侧对选中组的目录做添加/移除/移动。"""

    def __init__(self, master: tk.Misc, groups: dict[str, list[str]], on_saved) -> None:
        super().__init__(master, "管理目录")
        self.groups = groups
        self.on_saved = on_saved

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        # 顶部：操作按钮（横贯整行）
        btns = ttk.Frame(frame)
        btns.pack(fill="x")
        ttk.Button(
            btns, text="➕ 添加目录", style="Tool.TButton", command=self._add
        ).pack(side="left")
        ttk.Button(btns, text="🗑 移除", style="Tool.TButton", command=self._remove).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(
            btns, text="🔁 移动到其他组", style="Tool.TButton", command=self._move
        ).pack(side="left", padx=(6, 0))

        # 主体：左组列表，右目录列表
        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True, pady=(10, 0))

        # 左：组列表
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="ns")
        ttk.Label(left, text="组：").pack(anchor="w")
        self.group_box = tk.Listbox(
            left, width=22, height=10, exportselection=False, **style.listbox_kwargs()
        )
        self.group_box.pack(fill="y")
        self.group_box.bind("<<ListboxSelect>>", lambda _e: self._load_roots())
        for name in groups:
            self.group_box.insert("end", name)
        self.group_box.selection_set(0)

        # 右：目录列表
        right = ttk.Frame(body)
        right.grid(row=0, column=1, padx=(12, 0), sticky="nsew")
        body.columnconfigure(1, weight=1)
        ttk.Label(right, text="目录：").pack(anchor="w")

        self.root_box = tk.Listbox(
            right,
            width=46,
            height=8,
            selectmode="extended",
            exportselection=False,
            **style.listbox_kwargs(),
        )
        self.root_box.pack(fill="both", expand=True, pady=(6, 0))
        ttk.Label(
            right, text="Ctrl+点击 / Shift+点击 可多选", foreground=PALETTE["muted"]
        ).pack(anchor="w", pady=(2, 0))

        self.note_var = tk.StringVar()
        ttk.Label(right, textvariable=self.note_var, foreground="#15803d").pack(
            anchor="w", pady=(6, 0)
        )
        ttk.Button(right, text="关闭", style="Tool.TButton", command=self.destroy).pack(
            anchor="e", pady=(10, 0)
        )

        self._load_roots()

    # ── 内部工具 ──────────────────────────────
    def _group(self) -> str | None:
        sel = self.group_box.curselection()
        return self.group_box.get(sel[0]) if sel else None

    def _picked_roots(self) -> list[str]:
        return [self.root_box.get(i) for i in self.root_box.curselection()]

    def _load_roots(self) -> None:
        group = self._group()
        self.note_var.set("")
        self.root_box.delete(0, "end")
        self.root_box.selection_clear(0, "end")  # 切组后清掉旧选中，避免误操作
        for root in self.groups.get(group, []):
            self.root_box.insert("end", root)

    # ── 操作 ──────────────────────────────
    def _add(self) -> None:
        group = self._group()
        if not group:
            return
        path = filedialog.askdirectory(title=f"向组「{group}」添加工作目录", parent=self)
        if not path:
            return
        roots = self.groups[group]
        if path not in roots:
            roots.append(path)
            self.on_saved()
            self._load_roots()
            self.root_box.selection_set("end")

    def _remove(self) -> None:
        group = self._group()
        picked = self._picked_roots()
        if not group or not picked:
            messagebox.showinfo("提示", "请先在右侧选择要移除的目录（可多选）", parent=self)
            return
        if messagebox.askyesno(
            "移除目录", f"确定从组「{group}」移除 {len(picked)} 个目录？", parent=self
        ):
            roots = self.groups[group]
            for root in picked:
                roots.remove(root)
            self.on_saved()
            self._load_roots()

    def _move(self) -> None:
        group = self._group()
        picked = self._picked_roots()
        if not group or not picked:
            messagebox.showinfo("提示", "请先在右侧选择要移动的目录（可多选）", parent=self)
            return
        dsts = [name for name in self.groups if name != group]
        if not dsts:
            messagebox.showinfo("提示", "没有其他组可移动，请先创建", parent=self)
            return
        dlg = MoveTargetDialog(self, dsts, len(picked))
        dlg.show()
        dst = dlg.result
        if dst not in dsts:
            return
        roots = self.groups[group]
        for root in picked:
            roots.remove(root)
            if root not in self.groups[dst]:
                self.groups[dst].append(root)
        self.on_saved()
        self._load_roots()
        self.note_var.set(f"已移动 {len(picked)} 个目录到组「{dst}」")


class MoveTargetDialog(CenteredDialog):
    """选择目标组：列出其他组，双击 / 回车 / 「移动」按钮确认。"""

    def __init__(self, master: tk.Misc, groups: list[str], count: int) -> None:
        super().__init__(master, "移动到其他组")
        self.result: str | None = None

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"将选中的 {count} 个目录移动到：").pack(anchor="w")

        self.box = tk.Listbox(
            frame,
            width=32,
            height=min(len(groups), 10),
            exportselection=False,
            **style.listbox_kwargs(),
        )
        self.box.pack(fill="both", expand=True, pady=(8, 0))
        for name in groups:
            self.box.insert("end", name)
        self.box.selection_set(0)
        self.box.bind("<Double-1>", lambda _e: self._on_ok())
        self.box.bind("<Return>", lambda _e: self._on_ok())
        self.box.focus_set()

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="确定", style="Accent.TButton", command=self._on_ok).pack(
            side="right"
        )
        ttk.Button(btns, text="取消", style="Tool.TButton", command=self.destroy).pack(
            side="right", padx=(0, 8)
        )

    def show(self) -> None:
        super().show()
        self.wait_window()

    def _on_ok(self) -> None:
        sel = self.box.curselection()
        if not sel:
            return
        self.result = self.box.get(sel[0])
        self.destroy()


class SettingsDialog(CenteredDialog):
    """设置弹窗：双击打开的终端类型、打开配置文件。"""

    def __init__(self, master: tk.Misc, term_var: tk.StringVar, on_reload=None) -> None:
        super().__init__(master, "设置")
        self.term_var = term_var
        self.on_reload = on_reload
        # 独立副本：取消时不会改动主窗口当前值
        self.local_var = tk.StringVar(value=term_var.get())

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="双击表格行打开的终端：").grid(row=0, column=0, sticky="w")
        box = ttk.Combobox(
            frame,
            textvariable=self.local_var,
            state="readonly",
            width=16,
            values=TERMINAL_CHOICES,
        )
        box.grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            frame,
            text="auto：优先 Windows Terminal，未安装则用 Git Bash",
            foreground=PALETTE["muted"],
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 16))

        ttk.Separator(frame, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky="ew"
        )

        cfg = ttk.Frame(frame)
        cfg.grid(row=3, column=0, columnspan=2, sticky="w", pady=(16, 0))
        ttk.Button(
            cfg, text="📝 打开配置文件", style="Tool.TButton", command=self._open_config
        ).pack(side="left")
        ttk.Button(
            cfg, text="🔄 重新加载", style="Tool.TButton", command=self._reload
        ).pack(side="left", padx=(6, 0))
        self.note_var = tk.StringVar()
        ttk.Label(
            frame,
            textvariable=self.note_var,
            foreground="#15803d",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(
            frame,
            text="直接编辑磁盘上的配置（组与目录），保存后点「重新加载」生效",
            foreground=PALETTE["muted"],
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 16))

        btns = ttk.Frame(frame)
        btns.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="确定", style="Accent.TButton", command=self._on_ok).pack(
            side="left"
        )
        ttk.Button(btns, text="取消", style="Tool.TButton", command=self.destroy).pack(
            side="left", padx=(8, 0)
        )

    def _open_config(self) -> None:
        """用系统默认编辑器打开配置文件，便于手动编辑。"""
        try:
            config.open_config_file()
        except OSError as e:
            messagebox.showerror("打开配置文件失败", str(e), parent=self)

    def _reload(self) -> None:
        """重读磁盘配置并刷新主窗口；同步弹窗内的终端选项。"""
        if self.on_reload is None:
            return
        self.on_reload()
        # 主窗口已按新配置更新 term_var，弹窗副本跟随
        self.local_var.set(self.term_var.get())
        self.note_var.set("配置已重新加载")

    def _on_ok(self) -> None:
        value = self.local_var.get()
        self.term_var.set(value)
        config.save_pref("terminal", value)
        self.destroy()


class AboutDialog(CenteredDialog):
    """关于弹窗：工具名称、版本、简介与项目主页链接。"""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, "关于")

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame, text=APP_NAME, font=style.font(bold=True, size=15), anchor="w"
        ).pack(fill="x")
        ttk.Label(
            frame,
            text=f"{APP_NAME_EN} · v{APP_VERSION}",
            foreground=PALETTE["muted"],
            anchor="w",
        ).pack(fill="x", pady=(2, 14))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(0, 14))

        ttk.Label(
            frame,
            text=APP_DESCRIPTION,
            justify="left",
            wraplength=420,
            anchor="w",
        ).pack(fill="x")

        ttk.Label(
            frame, text="项目主页", foreground=PALETTE["muted"], anchor="w"
        ).pack(fill="x", pady=(14, 2))
        link = tk.Label(
            frame,
            text=ABOUT_URL,
            background=PALETTE["bg"],
            foreground=PALETTE["accent"],
            font=style.font(),
            cursor="hand2",
            anchor="w",
        )
        link.pack(fill="x")
        link.bind("<Button-1>", lambda _e: self._open_link())

        ttk.Button(frame, text="关闭", style="Tool.TButton", command=self.destroy).pack(
            anchor="e", pady=(18, 0)
        )

    def _open_link(self) -> None:
        if not webbrowser.open(ABOUT_URL):
            messagebox.showerror("打开链接失败", ABOUT_URL, parent=self)
