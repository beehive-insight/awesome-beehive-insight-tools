# git-repo-checker

扫描多个工作目录，汇总展示其下所有 git 仓库的未提交 / 未推送 / 未同步状态（tkinter GUI）。

## 功能

- 以「组」为单位管理工作目录：左侧组列表（含"全部"），每组可包含多个工作目录；组与目录管理在顶部「组」菜单
- 切换组只按已加载数据过滤显示，不重新扫描；打开或点「刷新」时扫描全部组并缓存，选"全部"时汇总所有组的结果
- 终端偏好等在「设置」菜单弹窗中配置
- 「设置」弹窗内可用「打开配置文件」按钮以系统默认程序打开 `~/.git-repo-checker.json`（不存在时自动创建），可直接查看 / 手动编辑；保存后点「重新加载」立即生效（重读组与偏好并重新扫描）
- 「关于」菜单弹出关于窗口，展示工具名称、版本与简介；点击项目主页链接用默认浏览器打开 `https://github.com/beehive-insight/awesome-beehive-insight-tools`
- 启动与手动「刷新」分两步：先立即展示本地状态（状态列显示「检查远端…」），再后台 `git fetch` 并自动更新；fetch 失败时显示「正常（远端未刷新）」，详情列给出原因
- 状态汇总：未提交（区分暂存/未暂存/未跟踪）、未推送（ahead）、未同步（behind）、无远端、分支无上游
- 结果按问题严重度排序，状态行用浅色底区分：待处理（浅橙）/ 错误（浅红）/ 正常（斑马纹交替）；蓝色强调主操作与选中态
- 组配置持久化到 `~/.git-repo-checker.json`（旧版 roots 配置自动迁移为"默认"组）
- 星标仓库：点击表格「★」列切换 ★ / ☆，星标路径持久化到配置文件的 `prefs.starred`；星标仓库在当前组内稳定排序置顶，工具栏「★ 只看星标」可过滤显示（可与「只看待处理」叠加）
- 表格首列为复选框，勾选多个仓库后可「推送勾选」批量 `git push`（仅推送已提交内容；工作区未提交的改动不会被推送，无远端/无上游会失败并在结果中提示）
- 双击表格行可在对应仓库目录打开终端（Windows Terminal 或 Git Bash，终端类型在「设置」中选择）

## 使用

```bash
uv sync
uv run git-repo-checker
```

## 开发（热重载）

```bash
uv run git-repo-checker-dev
```

启动后监视 `src/` 下所有 `.py` 文件，保存修改会自动终止并重启 GUI（进程级重启，窗口状态不保留）；关闭窗口即退出。轮询间隔 0.5s，不引入额外依赖。

## 打包（Windows exe）

```bash
build.bat
```

或直接执行：

```bash
uv sync
uv run pyinstaller --noconfirm --clean git-repo-checker.spec
```

产物为 `dist/git-repo-checker.exe`：单文件、无控制台窗口，当前约 12 MB。

- PyInstaller 属于 dev 依赖（`[dependency-groups] dev`），运行时依赖仍只有标准库
- `git-repo-checker.spec` 以 `src/main.py` 为入口、`src` 为模块搜索路径，并排除开发用的 `dev`
- exe 运行时依然读取/写入 `~/.git-repo-checker.json`，与开发模式共用同一份配置
- 所有 git 子进程使用 `CREATE_NO_WINDOW`，windowed 模式下启动/刷新不会弹出控制台或 Windows Terminal 窗口
- 目标机器需自备 `git`；双击打开终端需要 Windows Terminal 或 Git Bash

## 依赖

仅依赖 Python 标准库（tkinter）与本机 `git` 命令行。
