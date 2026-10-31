"""组配置的目录操作（纯逻辑，无 UI 依赖）。

工具栏快捷操作与「管理目录」弹窗共用：
两个入口只负责各自的选择方式（勾选反查 / 列表直选），
拿到 (组, 目录) 后统一调用这里的数据变更函数。
"""

from __future__ import annotations

import os

Groups = dict[str, list[str]]


def is_under(repo: str, root: str) -> bool:
    """判断仓库路径是否等于或位于工作目录之下（Windows 下忽略大小写）。"""
    repo_n = os.path.normcase(os.path.normpath(repo))
    root_n = os.path.normcase(os.path.normpath(root))
    return repo_n == root_n or repo_n.startswith(root_n + os.sep)


def find_root(repo: str, roots: list[str]) -> str | None:
    """反查仓库所属的工作目录，取最长前缀匹配。"""
    match: str | None = None
    for root in roots:
        if is_under(repo, root) and (match is None or len(root) > len(match)):
            match = root
    return match


def checked_roots(
    groups: Groups, checked: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """把勾选的 (组, 仓库) 反查为 (组, 工作目录)，同一目录只保留一次。"""
    picked: list[tuple[str, str]] = []
    for group, repo in checked:
        match = find_root(repo, groups.get(group, []))
        if match is not None and (group, match) not in picked:
            picked.append((group, match))
    return picked


def add_root(groups: Groups, group: str, path: str) -> bool:
    """向组添加目录（去重）。返回是否发生变更。"""
    roots = groups.get(group)
    if roots is None or path in roots:
        return False
    roots.append(path)
    return True


def remove_roots(groups: Groups, picks: list[tuple[str, str]]) -> None:
    """按 (组, 目录) 批量移除。"""
    for group, root in picks:
        if group in groups:
            groups[group] = [r for r in groups[group] if r != root]


def move_roots(groups: Groups, picks: list[tuple[str, str]], dst: str) -> None:
    """把 (组, 目录) 批量移动到目标组；目标组已有同路径时只移除不重复添加。"""
    for group, root in picks:
        if group in groups:
            groups[group] = [r for r in groups[group] if r != root]
        if root not in groups.setdefault(dst, []):
            groups[dst].append(root)
