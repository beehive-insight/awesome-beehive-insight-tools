# awesome-beehive-insight-tools

beehive-insight 组织下的开源工具**分发仓库**。本仓库不托管源码，每个工具一个子目录，仅承担以下职责：

- 工具索引（导航 + 版本信息）
- 各工具的发布产物上传（通过 GitHub Releases，详见下方"如何发布新版本"）

## 工具列表

每个工具是一个独立的子目录 `tools/<tool-name>/`。

| 工具                                   | 版本  | 平台        | 文档                                                                                    |
| -------------------------------------- | ----- | ----------- | --------------------------------------------------------------------------------------- |
| [file2markdown](./tools/file2markdown) | 0.3.0 | windows-x64 | [中文](./tools/file2markdown/README.md) · [English](./tools/file2markdown/README.en.md) |

## 如何新增一个工具

1. 在 `tools/<name>/` 下创建子目录
2. 编写 `README.md` / `README.en.md`（可选），并在此 README 的"工具列表"里补一行
3. 产物（zip / exe 等）放到 `tools/<name>/dist/`（被 `.gitignore` 忽略，不进 git）

## 如何发布新版本

两个脚本各管一摊，互不耦合：

```bash
# 1. 在 tools/<name>/CHANGELOG.md 顶部插入新版本条目（不 commit / 不 push）
pnpm changelog -- <name> <version> --note "新增xxx" --note "修复yyy"
# --dry-run 只预览不写盘

# 2. review CHANGELOG.md，commit + push
git add tools/<name>/CHANGELOG.md
git commit -m "docs(<name>): changelog for v<version>"
git push

# 3. 发 GitHub Release（release notes 由 --note 传入，与 CHANGELOG 无关）
pnpm release -- <name> <version> --note "新增xxx" --note "修复yyy"
# --dry-run 只展示计划不真发
```

前置条件：

- Node >= 18
- `gh` CLI 已安装并登录（[安装](https://cli.github.com/)）
- `tools/<name>/dist/` 里已放好待发布的产物

## 许可证

MIT — see [LICENSE](./LICENSE).
