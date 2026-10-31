"""UI 表格等界面元素的预设配置（列名/宽度等），与逻辑代码分离。"""

from __future__ import annotations

# 主窗口初始大小：(宽, 高)
WINDOW_SIZE = (1200, 640)

# 设计令牌：浅色主题（设计文档：.trae/documents/git-repo-checker/design/ui-style-design.md）
PALETTE: dict[str, str] = {
    "bg": "#f3f4f6",            # 窗口 / 工具栏 / 底栏背景
    "surface": "#ffffff",       # 表格、组列表、弹窗背景
    "stripe": "#f9fafb",        # 表格斑马纹（偶数行）
    "border": "#e5e7eb",        # 分隔线、按钮描边
    "text": "#1f2937",          # 主文本
    "muted": "#6b7280",         # 次要文本、提示、计数
    "accent": "#2563eb",        # 主按钮、选中项
    "accent_hover": "#1d4ed8",  # 主按钮悬停
    "accent_bg": "#dbeafe",     # 选中背景、过滤按钮开启态
    "problem_bg": "#fffbeb",    # 待处理行浅橙底
    "error_bg": "#fef2f2",      # 错误行浅红底
    "problem_text": "#b45309",  # 底栏「M 个需要处理」计数
}

# 字体候选：apply_theme 时取第一个系统可用的
FONT_CANDIDATES = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI")
FONT_SIZE = 9  # pt

# 主表格列：(column id, 表头文字, 宽度)
MAIN_TREE_COLUMNS: tuple[tuple[str, str, int], ...] = (
    ("check", "✓", 36),
    ("group", "组", 100),
    ("repo", "仓库", 420),
    ("branch", "分支", 120),
    ("state", "状态", 150),
    ("detail", "详情", 230),
)

# 设置弹窗：终端偏好可选值
TERMINAL_CHOICES = ("auto", "wt", "gitbash")

# 「关于」信息（版本号与 pyproject.toml 保持一致）
APP_NAME = "Git 仓库状态看板"
APP_NAME_EN = "Git Repo Checker"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "扫描多个工作目录，汇总展示其下所有 git 仓库的未提交 / 未推送 / 未同步状态。"
ABOUT_URL = "https://github.com/beehive-insight/awesome-beehive-insight-tools"
