"""递归扫描工作目录，发现 git 仓库并汇总状态。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from git_status import RepoStatus, get_status, is_git_repo


def find_repos(root: str) -> list[str]:
    """递归查找 root 下所有 git 仓库（含 root 自身）。

    遇到 .git 目录即停止下钻；跳过常见虚拟环境/依赖目录。
    """
    skip_names = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox"}
    repos: list[str] = []
    if is_git_repo(root):
        repos.append(root)
        return repos

    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_names]
        for d in list(dirnames):
            child = os.path.join(dirpath, d)
            if os.path.exists(os.path.join(child, ".git")):
                repos.append(child)
                dirnames.remove(d)  # 不再下钻子仓库内部
    return sorted(repos)


def check_groups(
    targets: list[tuple[str, list[str]]], max_workers: int = 8
) -> list[tuple[str, RepoStatus]]:
    """扫描所有组的工作目录，并行获取本地状态，按问题严重度排序。

    同一仓库被多个组（或多个工作目录）引用时只执行一次 git 子进程，
    结果对象在多个组间共享（展示与远端刷新均按只读使用）。

    并发刻意压到 8：每个任务是一个 git 子进程，开太满会抢占 GUI
    主线程的时间片，表现为界面卡顿（扫描慢 1s 左右，可接受）。
    """
    pairs: list[tuple[str, str]] = []
    for group, roots in targets:
        for root in roots:
            if not os.path.isdir(root):
                continue
            for repo in find_repos(root):
                pairs.append((group, repo))
    unique = sorted({repo for _, repo in pairs})

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        statuses = dict(zip(unique, pool.map(get_status, unique)))

    results = [(group, statuses[repo]) for group, repo in pairs]
    results.sort(key=lambda item: (item[1].sort_key, item[0], item[1].path.lower()))
    return results
