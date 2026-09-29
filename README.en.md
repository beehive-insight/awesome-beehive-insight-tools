# awesome-beehive-insight-tools

The artifact / distribution repository for open-source tools maintained by the beehive-insight organization. This repo does **not** host source code. Each tool lives in a sub-folder, and the repo's only responsibilities are:

- Providing a tool index (with version info)
- Hosting release assets via GitHub Releases (see "How to Publish a New Version" below)

## Tools

Each tool is a sub-folder `tools/<tool-name>/` with a `manifest.json` describing its metadata, version, assets, and doc paths.

| Tool | Version | Platform | Docs |
| --- | --- | --- | --- |
| [file2markdown](./tools/file2markdown) | 0.3.0 | windows-x64 | [English](./tools/file2markdown/README.en.md) · [中文](./tools/file2markdown/README.md) |

## Directory Layout

```
tools/<tool-name>/
├── manifest.json      # tool metadata: version, platforms, assets, doc paths (required)
├── README.md          # Chinese docs (optional)
├── README.en.md       # English docs (optional)
├── images/            # doc illustrations (tracked in git)
└── assets/            # release artifacts + SHA256SUMS (gitignored; uploaded manually before release)
```

## How to Add a New Tool

1. Create `tools/<name>/` and add `manifest.json` (see [file2markdown's manifest.json](./tools/file2markdown/manifest.json) for a template)
2. Write `README.md` / `README.en.md` and add a row to the root `README.md` "Tools" table
3. No change needed in `.github/workflows/release.yml` — it already accepts any tool name

## How to Publish a New Version

1. Bump `version` in `tools/<name>/manifest.json`
2. Put the new artifacts under `tools/<name>/assets/` and generate `SHA256SUMS`:
   ```bash
   sha256sum file2markdown.exe > tools/file2markdown/assets/SHA256SUMS
   ```
3. On GitHub → Actions → **release** → Run workflow
   - `tool`: tool name (e.g. `file2markdown`)
   - `version`: version number (e.g. `0.3.1`)
   - `notes`: release notes
4. CI creates the tag `<tool>-v<version>` and uploads everything under `assets/`

## License

MIT — see [LICENSE](./LICENSE).
