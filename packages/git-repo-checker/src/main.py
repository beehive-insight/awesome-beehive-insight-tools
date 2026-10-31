"""git-repo-checker GUI 入口（tkinter）。

以「组」为单位管理工作目录：左侧为组列表（含"全部"），每组可包含多个工作目录，
表格按组展示各 git 仓库的未提交 / 未推送 / 未同步状态。
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox, ttk

import config
import style
from dialogs import (
    AboutDialog,
    ManageGroupsDialog,
    ManageRootsDialog,
    MoveTargetDialog,
    SettingsDialog,
)
from git_status import RepoStatus, format_push_report, push_many, refresh_remote
from icons import make_icons
from presets import MAIN_TREE_COLUMNS, PALETTE, WINDOW_SIZE
from scanner import check_groups
from terminal import open_terminal
from ui_widgets import TreeTip

ALL_GROUPS = "全部"
# 远端 fetch 以网络等待为主，并发高于本地 status 阶段（8）以缩短总耗时；
# 取 16 兼顾死远端占位与 Windows 上 git 进程的 CPU 开销。
_FETCH_WORKERS = 16


def _is_under(repo: str, root: str) -> bool:
    """判断仓库路径是否等于或位于工作目录之下（Windows 下忽略大小写）。"""
    repo_n = os.path.normcase(os.path.normpath(repo))
    root_n = os.path.normcase(os.path.normpath(root))
    return repo_n == root_n or repo_n.startswith(root_n + os.sep)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        style.apply_theme(self)
        self.configure(background=PALETTE["bg"])
        self.title("Git 仓库状态看板")
        self.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}")
        self._scanning = False
        self._remote_pending = False
        # 扫描期间收到的新刷新请求（fetch=True 优先），扫描结束后自动补扫
        self._rescan_after: bool | None = None
        self._group_items: list[str] = []  # 组列表每行对应的组名
        # 星标图标（PhotoImage 需挂引用防止被 GC）
        self._icon_starred, self._icon_unstarred = make_icons()

        # ── 菜单栏 ──────────────────────────────
        menubar = tk.Menu(self)
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="🗂 编辑组", command=self.manage_groups)
        edit_menu.add_command(label="📁 管理目录", command=self.manage_roots)
        menubar.add_cascade(label="✏️ 编辑", menu=edit_menu)
        menubar.add_command(label="⚙️ 设置", command=self.open_settings)
        menubar.add_command(label="ℹ️ 关于", command=self.show_about)
        self.config(menu=menubar)

        # ── 顶部：操作按钮 ──────────────────────────────
        top = ttk.Frame(self, padding=(8, 8, 8, 4))
        top.pack(fill="x")

        # 左：目录快捷操作（作用于左侧选中的组）
        ttk.Button(
            top, text="➕ 添加目录", style="Tool.TButton", command=self.add_root
        ).pack(side="left")
        ttk.Button(
            top, text="🗑 移除", style="Tool.TButton", command=self.remove_roots
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            top, text="🔁 移动到其他组", style="Tool.TButton", command=self.move_roots
        ).pack(side="left", padx=(8, 0))

        self.only_problem = tk.BooleanVar(value=False)
        self.only_starred = tk.BooleanVar(value=False)
        self.refresh_btn = ttk.Button(
            top, text="⟳ 刷新", style="Accent.TButton", command=self.refresh
        )
        self.refresh_btn.pack(side="right")
        self.filter_btn = ttk.Button(
            top, text="🔍 只看待处理", style="Tool.TButton", command=self._toggle_filter
        )
        self.filter_btn.pack(side="right", padx=(0, 12))
        self.star_filter_btn = ttk.Button(
            top, text="★ 只看星标", style="Tool.TButton", command=self._toggle_star_filter
        )
        self.star_filter_btn.pack(side="right", padx=(0, 12))
        ttk.Button(
            top, text="☑ 全选", style="Tool.TButton", command=self._select_all
        ).pack(side="right", padx=(0, 12))
        ttk.Button(
            top, text="⬆ 推送勾选", style="Tool.TButton", command=self.push_selected
        ).pack(side="right", padx=(0, 8))

        # ── 主体：左组列表 + 右表格 ──────────────────────────────
        body = ttk.Frame(self, padding=(8, 4, 8, 4))
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, background=PALETTE["surface"])
        sidebar.pack(side="left", fill="y")
        tk.Label(
            sidebar,
            text="分组",
            background=PALETTE["surface"],
            foreground=PALETTE["muted"],
            font=style.font(bold=True),
            anchor="w",
        ).pack(fill="x", padx=(8, 0), pady=(6, 2))
        self.group_list = tk.Listbox(
            sidebar, width=20, selectmode="single", exportselection=False,
            **style.listbox_kwargs(),
        )
        self.group_list.pack(fill="y", padx=4, pady=(0, 4))
        self.group_list.bind("<<ListboxSelect>>", lambda _e: self._on_group_select())

        columns = ("check", "group", "repo", "branch", "state", "detail")
        tree_frame = ttk.Frame(body)
        tree_frame.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="tree headings", selectmode="browse"
        )
        self.tree.heading("#0", text="★")
        self.tree.column("#0", width=36, minwidth=36, stretch=False)
        for col, text, width in MAIN_TREE_COLUMNS:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")

        tree_xscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        tree_yscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        # 水平滚动逐像素重绘全部可见行，很卡；改为按 64px 步长滚动
        self._hscroll_pending = 0

        def _on_hscroll(event: tk.Event) -> str:
            if abs(event.delta) >= 120:  # 常规滚轮
                units = 64 * (1 if event.delta < 0 else -1)
            else:  # 触控板：累积小幅 delta，凑满一步再滚
                self._hscroll_pending += event.delta
                if abs(self._hscroll_pending) < 120:
                    return "break"
                units = 64 * (1 if self._hscroll_pending < 0 else -1)
                self._hscroll_pending = 0
            self.tree.xview_scroll(units, "units")
            return "break"

        self.tree.bind("<Shift-MouseWheel>", _on_hscroll)
        self.tree.configure(
            xscrollcommand=tree_xscroll.set, yscrollcommand=tree_yscroll.set
        )
        tree_yscroll.pack(side="right", fill="y")
        tree_xscroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        # 状态行底色：先配置 stripe（低优先级），后配置的 tint 覆盖之
        self.tree.tag_configure("stripe", background=PALETTE["stripe"])
        self.tree.tag_configure("problem", background=PALETTE["problem_bg"])
        self.tree.tag_configure("error", background=PALETTE["error_bg"])
        TreeTip(self.tree)  # 单元格截断时悬浮显示全文

        self.empty_label = tk.Label(
            tree_frame,
            text="",
            background=PALETTE["surface"],
            foreground=PALETTE["muted"],
            font=style.font(),
        )

        # 扫描/检查远端时覆盖在表格中央的加载动画
        self.loading_bar = ttk.Progressbar(
            tree_frame, mode="indeterminate", length=220, maximum=100
        )
        self.loading_label = tk.Label(
            tree_frame,
            text="",
            background=PALETTE["surface"],
            foreground=PALETTE["muted"],
            font=style.font(),
        )

        # ── 底部：提示 + 摘要 ──────────────────────────────
        self.term_var = tk.StringVar(value=config.load_pref("terminal", "auto"))
        bottom = ttk.Frame(self, padding=(12, 2))
        bottom.pack(fill="x")
        tk.Label(
            bottom,
            text="双击行可打开该仓库的终端 · 详见菜单",
            background=PALETTE["bg"],
            foreground=PALETTE["muted"],
            font=style.font(),
        ).pack(side="left")

        self._summary_main = tk.StringVar()
        self._summary_count = tk.StringVar()
        self._summary_tail = tk.StringVar()
        # pack(side="right") 先右后左：tail 最右、count 居中、main 最左
        tk.Label(
            bottom,
            textvariable=self._summary_tail,
            background=PALETTE["bg"],
            foreground=PALETTE["text"],
            font=style.font(),
        ).pack(side="right")
        tk.Label(
            bottom,
            textvariable=self._summary_count,
            background=PALETTE["bg"],
            foreground=PALETTE["problem_text"],
            font=style.font(bold=True),
        ).pack(side="right")
        self.summary_label = tk.Label(
            bottom,
            textvariable=self._summary_main,
            background=PALETTE["bg"],
            foreground=PALETTE["text"],
            font=style.font(),
        )
        self.summary_label.pack(side="right")

        self.groups: dict[str, list[str]] = config.load_groups()
        self._starred: set[str] = config.load_starred()
        self._last_results: list[tuple[str, RepoStatus]] = []
        self._render_groups()
        self.refresh()  # 启动时自动加载，并 fetch 以获取真实远端状态

    # ── 组/目录管理 ──────────────────────────────
    def _render_groups(self, counts: dict[str, int] | None = None) -> None:
        counts = counts or {}
        selected = self._selected_group()
        names = [ALL_GROUPS, *self.groups]
        self._group_items = names
        self.group_list.delete(0, "end")
        for name in names:
            n = counts.get(name)
            self.group_list.insert("end", f"{name} ({n})" if n is not None else name)
        # 保留当前选择；组被删掉时回落到「全部」
        if selected in names:
            self.group_list.selection_set(names.index(selected))
        else:
            self.group_list.selection_set(0)

    def _selected_group(self) -> str | None:
        sel = self.group_list.curselection()
        if not sel:
            return None
        return self._group_items[sel[0]]

    def _on_group_select(self) -> None:
        """切换组：直接用缓存结果按组过滤渲染，不重新扫描。"""
        if not self._last_results:
            return
        self._render(
            self._last_results,
            remote_pending=self._remote_pending,
            finalize=False,
        )

    def _save(self) -> None:
        config.save_groups(self.groups)

    def manage_groups(self) -> None:
        """编辑组弹窗：添加 / 重命名 / 删除。"""
        def on_changed() -> None:
            self._save()
            self._render_groups()
            self.refresh(fetch=False)
        ManageGroupsDialog(self, self.groups, on_changed).show()

    def manage_roots(self) -> None:
        """管理目录弹窗：添加 / 移除 / 移动。"""
        def on_saved() -> None:
            self._save()
            self.refresh(fetch=False)
        ManageRootsDialog(self, self.groups, on_saved).show()

    # ── 工具栏：目录快捷操作 ──────────────────────────────
    def _active_group(self) -> str | None:
        """当前侧栏选中的具体组；选了「全部」或未选中时提示并返回 None。"""
        group = self._selected_group()
        if not group or group == ALL_GROUPS:
            messagebox.showinfo("提示", "请先在左侧选择一个具体的组", parent=self)
            return None
        return group

    def _checked_roots(self) -> list[tuple[str, str]]:
        """把勾选的仓库反查为其所属组的工作目录，同一目录只保留一次。"""
        picked: list[tuple[str, str]] = []
        for iid in self.tree.get_children():
            values = self.tree.item(iid, "values")
            if values[0] != "☑":
                continue
            group, repo = values[1], values[2]
            match: str | None = None
            for root in self.groups.get(group, []):
                if _is_under(repo, root) and (match is None or len(root) > len(match)):
                    match = root
            if match is not None and (group, match) not in picked:
                picked.append((group, match))
        return picked

    def add_root(self) -> None:
        """向当前选中的组添加一个工作目录。"""
        if self._scanning:
            return
        group = self._active_group()
        if not group:
            return
        path = filedialog.askdirectory(title=f"向组「{group}」添加工作目录", parent=self)
        if not path:
            return
        roots = self.groups[group]
        if path not in roots:
            roots.append(path)
            self._save()
            self.refresh(fetch=False)

    def remove_roots(self) -> None:
        """移除勾选仓库所在的工作目录。"""
        if self._scanning:
            return
        picked = self._checked_roots()
        if not picked:
            messagebox.showinfo(
                "提示", "请先在表格中勾选要移除的仓库", parent=self
            )
            return
        listing = "\n".join(f"· [{group}] {root}" for group, root in picked)
        if not messagebox.askyesno(
            "移除目录",
            f"将从组中移除以下 {len(picked)} 个工作目录：\n\n{listing}\n\n"
            "这些目录下的其他仓库也会一起从看板消失，确定继续？",
            parent=self,
        ):
            return
        for group, root in picked:
            self.groups[group] = [r for r in self.groups[group] if r != root]
        self._save()
        self.refresh(fetch=False)

    def move_roots(self) -> None:
        """把勾选仓库所在的工作目录移动到其他组。"""
        if self._scanning:
            return
        picked = self._checked_roots()
        if not picked:
            messagebox.showinfo(
                "提示", "请先在表格中勾选要移动的仓库", parent=self
            )
            return
        sources = {group for group, _ in picked}
        dsts = [name for name in self.groups if name not in sources]
        if not dsts:
            messagebox.showinfo(
                "提示", "没有其他组可移动，请先在「编辑 → 编辑组」创建", parent=self
            )
            return
        dlg = MoveTargetDialog(self, dsts, len(picked))
        dlg.show()
        dst = dlg.result
        if dst not in dsts:
            return
        for group, root in picked:
            self.groups[group] = [r for r in self.groups[group] if r != root]
            if root not in self.groups[dst]:
                self.groups[dst].append(root)
        self._save()
        self.refresh(fetch=False)

    # ── 打开终端 ──────────────────────────────
    def open_settings(self) -> None:
        SettingsDialog(self, self.term_var, on_reload=self.reload_config).show()

    def reload_config(self) -> None:
        """重新读取磁盘上的配置（组 / 目录 / 偏好）并刷新界面。"""
        self.groups = config.load_groups()
        self._starred = config.load_starred()
        self.term_var.set(config.load_pref("terminal", "auto"))
        self._render_groups()
        self.refresh(fetch=False)

    def show_about(self) -> None:
        """弹出「关于」窗口：名称、版本、简介与项目主页。"""
        AboutDialog(self).show()

    def _on_double_click(self, event: tk.Event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        repo = self.tree.item(item_id, "values")[2]  # values: (check, group, repo, ...)
        try:
            open_terminal(repo, self.term_var.get())
        except (RuntimeError, OSError) as e:
            messagebox.showerror("打开终端失败", str(e), parent=self)

    # ── 勾选、星标与推送 ──────────────────────────────
    def _on_click(self, event: tk.Event) -> None:
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        if self.tree.identify_region(event.x, event.y) == "tree":
            # 首列（星标图标列）：切换 ★ / ☆ 并持久化
            repo = self.tree.item(item_id, "values")[2]  # values: (check, group, repo, ...)
            if repo in self._starred:
                self._starred.discard(repo)
            else:
                self._starred.add(repo)
            config.save_starred(self._starred)
            self.tree.item(
                item_id,
                image=self._icon_starred if repo in self._starred else self._icon_unstarred,
            )
            return
        if self.tree.identify_column(event.x) == "#1":
            # 勾选列：切换 ☐ / ☑
            values = self.tree.item(item_id, "values")
            checked = values[0] == "☑"
            self.tree.item(item_id, values=("☑" if not checked else "☐", *values[1:]))

    def _selected_repos(self) -> list[str]:
        return [
            self.tree.item(iid, "values")[2]
            for iid in self.tree.get_children()
            if self.tree.item(iid, "values")[0] == "☑"
        ]  # values: (check, group, repo, ...)

    def push_selected(self) -> None:
        if self._scanning:
            return
        repos = self._selected_repos()
        if not repos:
            messagebox.showinfo("提示", "请先在表格左侧勾选要推送的仓库", parent=self)
            return
        if not messagebox.askyesno(
            "推送", f"确定推送 {len(repos)} 个勾选的仓库？", parent=self
        ):
            return
        self._scanning = True
        self.refresh_btn.config(state="disabled")
        self._set_summary("推送中…")

        def worker() -> None:
            results = push_many(repos)
            self.after(0, lambda: self._push_done(results))

        threading.Thread(target=worker, daemon=True).start()

    def _push_done(self, results: list[tuple[str, bool, str]]) -> None:
        self._scanning = False
        self.refresh_btn.config(state="normal")
        ok, report = format_push_report(results)
        self._set_summary(f"推送完成：{ok}/{len(results)} 成功")
        messagebox.showinfo("推送结果", report, parent=self)
        # 推送期间若有被拦下的刷新请求，此处一并补扫（fetch=True 优先）
        pending, self._rescan_after = self._rescan_after, None
        self.refresh(fetch=pending or False)

    # ── 刷新 ──────────────────────────────
    def refresh(self, fetch: bool = True) -> None:
        if self._scanning:
            # 扫描中不丢弃请求：记下待补扫（fetch=True 优先），结束后自动执行
            self._rescan_after = fetch or self._rescan_after
            return
        # 始终扫描全部组：切换组时直接从缓存过滤，无需重新扫描
        targets: list[tuple[str, list[str]]] = list(self.groups.items())
        if not any(roots for _, roots in targets):
            self._set_summary("还没有配置任何工作目录")
            self.tree.delete(*self.tree.get_children())
            self._show_empty("还没有配置任何工作目录")
            return

        self._scanning = True
        self.refresh_btn.config(state="disabled")
        self._set_summary("扫描中…")
        self._show_loading("正在扫描工作目录…")
        self.tree.delete(*self.tree.get_children())

        def worker() -> None:
            # 第一阶段：只取本地状态，先让表格尽快出结果
            # （同一仓库被多个组引用时只扫描一次）
            results = check_groups(targets)
            if not results:
                self.after(0, lambda: self._render(results))
                return
            self.after(0, lambda: self._render(results, remote_pending=fetch))
            if not fetch:
                return

            # 第二阶段：后台 fetch + 只刷新分支/远端字段；同一路径只检查一次
            base_by_path = {s.path: s for _, s in results if not s.error}
            # 无远端或当前分支无上游的仓库 fetch 没有意义，直接跳过以省下
            # 每个仓库一次网络子进程（这也是最耗时的一类子进程）
            paths = sorted(
                p for p, s in base_by_path.items() if s.has_remote and s.has_upstream
            )
            if not paths:
                self.after(0, lambda: self._render(results))
                return
            total = len(paths)
            self.after(0, lambda: self.summary_label.config(foreground=PALETTE["accent"]))
            fetched: dict[str, RepoStatus] = {}
            # fetch 是网络等待为主，并发可以比本地 status 阶段放大一倍以上
            with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
                futures = enumerate(
                    zip(
                        paths,
                        pool.map(
                            lambda p: refresh_remote(p, base_by_path[p]),
                            paths,
                        ),
                    ),
                    start=1,
                )
                for done, (path, status) in futures:
                    fetched[path] = status
                    self.after(
                        0,
                        lambda d=done, t=total: (
                            self._set_summary(f"检查远端状态… {d}/{t}"),
                            self._show_loading_progress(d, t),
                        ),
                    )
            final = [(group, fetched.get(s.path, s)) for group, s in results]
            final.sort(key=lambda item: (item[1].sort_key, item[0], item[1].path.lower()))
            self.after(0, lambda: self._render(final))

        threading.Thread(target=worker, daemon=True).start()

    def _render(
        self,
        results: list[tuple[str, RepoStatus]],
        remote_pending: bool = False,
        finalize: bool = True,
    ) -> None:
        self._remote_pending = remote_pending
        if finalize and not remote_pending:
            self._scanning = False
            self.refresh_btn.config(state="normal")
            # 扫描彻底结束才隐藏加载动画；切组（finalize=False）不隐藏，
            # 否则远端检查阶段切一次组进度反馈就消失了
            self._hide_loading()
            # 扫描期间若有新的刷新请求（如中途改了组/目录），结束后自动补扫
            if self._rescan_after is not None:
                pending, self._rescan_after = self._rescan_after, None
                self.after_idle(lambda: self.refresh(fetch=pending))
        elif finalize and remote_pending:
            # 阶段一出结果，表格已可读；动画降级为底部细进度条，不再遮挡行数据
            self._dock_loading()
        self._last_results = results
        counts = {ALL_GROUPS: len(results)}
        for group, _s in results:
            counts[group] = counts.get(group, 0) + 1
        self._render_groups(counts)
        self.summary_label.config(
            foreground=PALETTE["accent"] if remote_pending else PALETTE["text"]
        )
        selected = self._selected_group()
        visible = [
            (group, status)
            for group, status in results
            if selected is None or selected == ALL_GROUPS or group == selected
        ]
        # 星标仓库排在同组结果的前面（稳定排序，不打乱原有顺序）
        visible.sort(key=lambda item: 0 if item[1].path in self._starred else 1)
        self.tree.delete(*self.tree.get_children())
        problem = 0
        shown = 0
        for group, s in visible:
            if s.error:
                state, tag = "错误", "error"
            elif s.is_clean:
                if remote_pending:
                    state, tag = "检查远端…", "clean"
                else:
                    # fetch 失败时不敢断言「正常」，明确提示远端状态未刷新
                    state = "正常（远端未刷新）" if s.fetch_error else "正常"
                    tag = "clean"
            else:
                state, tag = "待处理", "problem"
                problem += 1
            starred = s.path in self._starred
            if self.only_starred.get() and not starred:
                continue
            if self.only_problem.get() and tag == "clean":
                continue
            detail = "；".join(s.problems) or "—"
            if s.fetch_error and not s.error:
                warning = f"远端未刷新：{s.fetch_error}"
                detail = warning if detail == "—" else f"{detail}；{warning}"
            if tag == "clean":
                tags = ("stripe",) if shown % 2 else ()
            else:
                tags = (tag,)
            shown += 1
            self.tree.insert(
                "",
                "end",
                image=self._icon_starred if starred else self._icon_unstarred,
                values=("☐", group, s.path, s.branch, state, detail),
                tags=tags,
            )
        if remote_pending:
            self._set_summary(f"共 {len(visible)} 个仓库，正在检查远端状态…")
        else:
            self._set_summary(f"共 {len(visible)} 个仓库", problem=problem)

        # 空状态提示
        if remote_pending:
            self._hide_empty()
        elif not results:
            self._show_empty("没有发现 git 仓库")
        elif not self.tree.get_children():
            if self.only_starred.get():
                self._show_empty("没有星标的仓库")
            elif self.only_problem.get():
                self._show_empty("没有待处理的仓库")
            else:
                self._show_empty("该组下没有仓库")
        else:
            self._hide_empty()

    def _set_summary(self, text: str, problem: int | None = None) -> None:
        """更新底栏摘要；problem 非 None 时以橙色加粗计数展示。"""
        self._summary_main.set(text)
        self._summary_count.set("" if problem is None else str(problem))
        self._summary_tail.set("" if problem is None else " 个需要处理")

    def _show_empty(self, text: str) -> None:
        self.empty_label.config(text=text)
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def _hide_empty(self) -> None:
        self.empty_label.place_forget()

    # ── 加载动画 ──────────────────────────────
    def _show_loading(self, text: str) -> None:
        """扫描中：表格中央显示滚动条动画 + 文案（marquee 模式）。"""
        self._hide_empty()
        self.loading_label.config(text=text)
        self.loading_bar.config(mode="indeterminate")
        self.loading_bar.place(
            relx=0.5, rely=0.47, anchor="center", x=0, y=0
        )
        self.loading_label.place(relx=0.5, rely=0.57, anchor="center")
        self.loading_bar.start(20)

    def _show_loading_progress(self, done: int, total: int) -> None:
        """检查远端阶段：切换为确定进度（d/t）。"""
        self.loading_bar.stop()
        self.loading_bar.config(mode="determinate", maximum=total, value=done)
        self.loading_label.config(text=f"正在检查远端状态… {done}/{total}")

    def _dock_loading(self) -> None:
        """阶段一出数据后：动画停靠到表格底部一条细进度，不遮挡行数据。"""
        self.loading_bar.stop()
        self.loading_bar.config(mode="determinate")
        self.loading_bar.place_forget()
        self.loading_label.place_forget()
        self.loading_bar.place(
            relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=4, bordermode="outside"
        )

    def _hide_loading(self) -> None:
        self.loading_bar.stop()
        self.loading_bar.place_forget()
        self.loading_label.place_forget()

    def _toggle_filter(self) -> None:
        self.only_problem.set(not self.only_problem.get())
        # 处于开启状态时用「按下」样式示意
        self.filter_btn.state(["pressed"] if self.only_problem.get() else ["!pressed"])
        self._render(
            self._last_results,
            remote_pending=self._remote_pending,
            finalize=False,
        )

    def _toggle_star_filter(self) -> None:
        self.only_starred.set(not self.only_starred.get())
        self.star_filter_btn.state(["pressed"] if self.only_starred.get() else ["!pressed"])
        self._render(
            self._last_results,
            remote_pending=self._remote_pending,
            finalize=False,
        )

    def _select_all(self) -> None:
        items = self.tree.get_children()
        all_checked = all(
            self.tree.item(iid, "values")[0] == "☑" for iid in items
        )
        # 全部已勾选时再点为取消全选
        for iid in items:
            values = self.tree.item(iid, "values")
            self.tree.item(iid, values=("☐" if all_checked else "☑", *values[1:]))


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
