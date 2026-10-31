"""开发用热重载启动器（仅依赖标准库）。

监视 src 下所有 .py 文件的修改时间，一旦变化就终止并重启 GUI 进程。
入口：uv run git-repo-checker-dev
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
APP_ENTRY = SRC_DIR / "main.py"
POLL_INTERVAL = 0.5


def _snapshot() -> dict[Path, int]:
    """收集 src 下所有 Python 文件的修改时间（纳秒）。"""
    files: dict[Path, int] = {}
    for path in SRC_DIR.rglob("*.py"):
        try:
            files[path] = path.stat().st_mtime_ns
        except OSError:
            continue
    return files


def _spawn() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(APP_ENTRY)], cwd=str(SRC_DIR.parent))


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main() -> None:
    print(f"热重载已启动，监视：{SRC_DIR}（{POLL_INTERVAL}s 轮询）")
    print("修改任意 .py 文件将自动重启 GUI；关闭窗口即退出。")
    while True:
        baseline = _snapshot()
        proc = _spawn()
        restart = False
        try:
            while True:
                code = proc.poll()
                if code is not None:
                    if code != 0:
                        print(f"应用异常退出（code={code}），等待文件变更后重启…")
                        while _snapshot() == baseline:
                            time.sleep(POLL_INTERVAL)
                        restart = True
                    break
                if _snapshot() != baseline:
                    print("检测到文件变更，重启…")
                    restart = True
                    break
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            _stop(proc)
            return
        _stop(proc)
        if not restart:
            return


if __name__ == "__main__":
    main()
