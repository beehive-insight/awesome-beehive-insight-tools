"""在指定目录打开外部终端（wt / Git Bash）。"""

from __future__ import annotations

import shutil
import subprocess


def open_terminal(repo: str, pref: str) -> None:
    """在指定目录打开终端：wt 或 git bash，按偏好与可用性选择。"""
    wt = shutil.which("wt")
    bash = shutil.which("bash")  # Git for Windows 自带
    if pref == "wt" and not wt:
        raise RuntimeError("未找到 Windows Terminal (wt)")
    if pref == "gitbash" and not bash:
        raise RuntimeError("未找到 Git Bash")
    if pref in ("auto", "wt") and wt:
        subprocess.Popen(["wt", "-d", repo], cwd=repo)
    elif bash:
        # git bash: bash.exe --cd <path>，加 -i -l 走登录 shell
        subprocess.Popen([bash, "--cd", repo], cwd=repo)
    else:
        raise RuntimeError("未找到可用的终端（wt / Git Bash）")
