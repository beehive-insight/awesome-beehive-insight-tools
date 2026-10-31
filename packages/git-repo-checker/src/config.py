"""目录分组的持久化（JSON，存于用户主目录）。"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".git-repo-checker.json"


def _load_config() -> dict:
    """读取整个配置文件；不存在或内容损坏时返回空 dict。"""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config(data: dict) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def load_pref(key: str, default: str = "") -> str:
    prefs = _load_config().get("prefs")
    if not isinstance(prefs, dict):
        return default
    return prefs.get(key, default)


def save_pref(key: str, value: str) -> None:
    data = _load_config()
    prefs = data.get("prefs")
    if not isinstance(prefs, dict):
        prefs = {}
        data["prefs"] = prefs
    prefs[key] = value
    _write_config(data)


def load_starred() -> set[str]:
    """读取星标仓库路径集合（prefs.starred）。"""
    prefs = _load_config().get("prefs")
    starred = prefs.get("starred") if isinstance(prefs, dict) else None
    if not isinstance(starred, list):
        return set()
    return {s for s in starred if isinstance(s, str)}


def save_starred(starred: set[str]) -> None:
    """保存星标仓库路径集合，保留文件中的其他字段。"""
    data = _load_config()
    prefs = data.get("prefs")
    if not isinstance(prefs, dict):
        prefs = {}
        data["prefs"] = prefs
    prefs["starred"] = sorted(starred)
    _write_config(data)


def load_groups() -> dict[str, list[str]]:
    """读取组配置：{组名: [工作目录...]}，自动清理失效目录。"""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        groups = data.get("groups", {})
        # 旧版配置迁移：roots 列表转为默认组
        if not groups and isinstance(data.get("roots"), list):
            groups = {"默认": data["roots"]}
        cleaned = {
            name: list(dict.fromkeys(
                r for r in roots if isinstance(r, str) and os.path.isdir(r)
            ))  # 同组内保留首次出现的顺序并去重
            for name, roots in groups.items()
            if isinstance(name, str) and isinstance(roots, list)
        }
        if cleaned != groups:
            save_groups(cleaned)
        return cleaned
    except (OSError, ValueError, AttributeError):
        return {}


def save_groups(groups: dict[str, list[str]]) -> None:
    """保存组配置，保留文件中的其他字段（如 prefs）。"""
    data = _load_config()
    data["groups"] = groups
    _write_config(data)


def ensure_config_file() -> None:
    """配置文件不存在时创建空结构，便于直接编辑。"""
    if CONFIG_PATH.exists():
        return
    CONFIG_PATH.write_text(
        json.dumps({"groups": {}, "prefs": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def open_config_file() -> None:
    """用系统默认程序打开配置文件（不存在则先创建）。"""
    ensure_config_file()
    os.startfile(str(CONFIG_PATH))  # type: ignore[attr-defined]  # Windows 专用
