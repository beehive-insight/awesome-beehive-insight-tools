"""用 PhotoImage 逐像素绘制星标图标（零依赖，tkinter 原生不支持 SVG）。"""

from __future__ import annotations

import math
import tkinter as tk

STAR_SIZE = 15  # 奇数便于星形左右对称


def _star_points(cx: float, cy: float, r_out: float, r_in: float) -> list[tuple[float, float]]:
    """五角星顶点：从正上方开始，外/内半径交替。"""
    pts: list[tuple[float, float]] = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _in_polygon(x: float, y: float, pts: list[tuple[float, float]]) -> bool:
    """射线法判断点是否在多边形内。"""
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _make_star(fill: str, hollow: bool = False) -> tk.PhotoImage:
    """绘制星形：实心或空心（空心保留 2px 描边）。"""
    size = STAR_SIZE
    img = tk.PhotoImage(width=size, height=size)
    cx = cy = size / 2
    outer = size / 2 - 0.5
    pts = _star_points(cx, cy, outer, outer * 0.45)
    inner = _star_points(cx, cy, outer - 2.2, (outer - 2.2) * 0.45) if hollow else []
    for y in range(size):
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            if _in_polygon(px, py, pts) and not (inner and _in_polygon(px, py, inner)):
                img.put(fill, (x, y))
    return img


def make_icons() -> tuple[tk.PhotoImage, tk.PhotoImage]:
    """返回 (星标图标, 未星标图标)；需在 Tk 根窗口创建后调用。"""
    return _make_star("#f5a623"), _make_star("#cbd5e1", hollow=True)
