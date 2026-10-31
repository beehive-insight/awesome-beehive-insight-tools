"""git 命令封装与仓库状态解析。"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field, replace


@dataclass
class RepoStatus:
    """单个 git 仓库的状态汇总。"""

    path: str
    branch: str = ""
    dirty: bool = False  # 有未提交变更（含未跟踪文件）
    ahead: int = 0  # 本地领先远端（未 push）
    behind: int = 0  # 本地落后远端（未 pull）
    has_remote: bool = True  # 是否配置了远端
    has_upstream: bool = True  # 当前分支是否有上游
    error: str | None = None  # status 解析失败时的提示
    fetch_error: str | None = None  # 本次 fetch 失败原因；为空表示远端状态可信
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0

    @property
    def problems(self) -> list[str]:
        """该仓库存在的所有问题，用于展示。"""
        if self.error:
            return [self.error]
        problems: list[str] = []
        if self.dirty:
            problems.append(f"未提交 {self.staged + self.unstaged + self.untracked}")
        if not self.has_remote:
            problems.append("无远端")
        elif not self.has_upstream:
            problems.append("分支无上游")
        else:
            if self.ahead:
                problems.append(f"未推送 {self.ahead}")
            if self.behind:
                problems.append(f"未同步 {self.behind}")
        return problems

    @property
    def is_clean(self) -> bool:
        return not self.error and not self.problems

    @property
    def sort_key(self) -> int:
        if self.error:
            return 0
        if self.dirty or not self.has_remote or not self.has_upstream:
            return 1
        if self.ahead or self.behind:
            return 2
        return 3


# 禁止 git 等待终端输入凭据：GUI 无法交互，卡住不如尽快失败并提示
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

# windowed exe 没有控制台；若默认终端是 Windows Terminal，每次启动 git 都会弹出一个
# wt 窗口。CREATE_NO_WINDOW 让 git 完全在后台运行（非 Windows 平台为 0）。
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _run_git(repo: str, *args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=_GIT_ENV,
        creationflags=_CREATE_NO_WINDOW,
    )


def push(repo: str) -> tuple[bool, str]:
    """推送当前分支到上游，返回 (是否成功, 提示信息)。"""
    try:
        r = _run_git(repo, "push", timeout=60)
    except subprocess.TimeoutExpired:
        return False, "push 超时"
    if r.returncode == 0:
        return True, "推送成功"
    msg = (r.stderr or r.stdout or "未知错误").strip().splitlines()
    return False, "推送失败：" + (msg[-1] if msg else "未知错误")


def push_many(repos: list[str]) -> list[tuple[str, bool, str]]:
    """依次推送多个仓库，返回 [(仓库, 是否成功, 提示)]。"""
    return [(repo, *push(repo)) for repo in repos]


def format_push_report(results: list[tuple[str, bool, str]]) -> tuple[int, str]:
    """汇总推送结果：返回 (成功数, 报告文本)。"""
    ok = sum(1 for _, success, _ in results if success)
    report = "\n".join(f"{'✔' if s else '✘'} {repo}: {msg}" for repo, s, msg in results)
    return ok, report


def is_git_repo(path: str) -> bool:
    """判断目录是否是 git 仓库（工作区或 .git 均可）。"""
    try:
        r = _run_git(path, "rev-parse", "--is-inside-work-tree")
        return r.returncode == 0 and r.stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired):
        return False


def fetch(repo: str) -> str | None:
    """后台刷新远端状态；返回失败原因，成功返回 None。

    只取当前分支上游所在的远端（不带 --all，避免 fork 类仓库把多个
    远端全部拉一遍）、不取 tag、不递归子模块，并缩短超时，避免死远端
    长时间占用并发槽位。同时关闭 fetch 触发的自动 gc，防止大仓库在
    刷新过程中被一次后台清理拖慢。
    """
    try:
        r = _run_git(
            repo,
            "-c",
            "gc.auto=0",
            "fetch",
            "--quiet",
            "--no-tags",
            "--no-recurse-submodules",
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return "fetch 超时"
    if r.returncode == 0:
        return None
    msg = (r.stderr or r.stdout or "未知错误").strip().splitlines()
    return msg[-1] if msg else "未知错误"


def _apply_branch_lines(status: RepoStatus, lines: list[str]) -> None:
    """从 porcelain v2 的 # 头信息里解析分支 / 上游 / 领先落后数。"""
    upstream_seen = False
    for line in lines:
        if line.startswith("# branch.head "):
            status.branch = line.split(" ", 2)[2]
        elif line.startswith("# branch.upstream "):
            upstream_seen = True
        elif line.startswith("# branch.ab "):
            # 格式: # branch.ab +1 -2
            parts = line.split(" ")
            status.ahead = int(parts[2])
            status.behind = int(parts[3])
    status.has_upstream = upstream_seen
    if not upstream_seen:
        status.ahead = status.behind = 0


def get_status(repo: str, has_remote: bool | None = None) -> RepoStatus:
    """只读取本地状态（不访问远端），一次 status 调用解析出全部信息。

    has_remote: 已知该仓库是否配置远端时直接传入（阶段二复用阶段一结果），
    省去重复的 git remote 子进程；None 表示需要现场查询。
    """
    status = RepoStatus(path=repo)
    try:
        r = _run_git(repo, "status", "--porcelain=v2", "--branch")
    except subprocess.TimeoutExpired:
        status.error = "git status 超时"
        return status
    if r.returncode != 0:
        status.error = "非 git 仓库或无法读取"
        return status

    if has_remote is None:
        remote_proc = _run_git(repo, "remote")
        has_remote = bool(remote_proc.stdout.strip())
    status.has_remote = has_remote

    _apply_branch_lines(status, r.stdout.splitlines())
    for line in r.stdout.splitlines():
        if line.startswith("1 ") or line.startswith("2 "):
            fields = line.split(" ")
            # v2: 1 <xy> ... ; xy 如 "M.", ".M", "A." 等
            xy = fields[1]
            if xy[0] not in (".", "?"):
                status.staged += 1
            if xy[1] != ".":
                status.unstaged += 1
        elif line.startswith("? "):
            status.untracked += 1
        elif line.startswith("u "):
            status.staged += 1  # 合并冲突状态也视为待处理
    status.dirty = bool(status.staged or status.unstaged or status.untracked)
    return status


def refresh_remote(repo: str, base: RepoStatus) -> RepoStatus:
    """fetch 之后只刷新与远端相关的字段，复用阶段一的本地变更统计。

    - 远端变化只会影响 ahead / behind / 上游，工作区的 staged / unstaged /
      untracked 数量不受影响，因此这里给 status 加 --untracked-files=no，
      避免对工作区（尤其是大仓库或未跟踪文件很多时）做第二次全量扫描。
    - 返回新的 RepoStatus，不修改入参（同一仓库可能被多个组引用）。
    """
    status = replace(base, fetch_error=fetch(repo))
    try:
        r = _run_git(
            repo, "status", "--porcelain=v2", "--branch", "--untracked-files=no"
        )
    except subprocess.TimeoutExpired:
        return status
    if r.returncode != 0:
        status.error = "非 git 仓库或无法读取"
        return status
    _apply_branch_lines(status, r.stdout.splitlines())
    return status
