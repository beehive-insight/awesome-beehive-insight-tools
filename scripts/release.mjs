#!/usr/bin/env node
/**
 * Publish a tool release to GitHub Releases via the gh CLI.
 *
 * Usage:
 *   node scripts/release.mjs <tool-name> <version> [--dry-run]
 *
 * Release notes come from tools/<tool>/CHANGELOG.md: the body of the
 * `## [<version>]` section is used verbatim as the release body. Run
 * scripts/changelog.mjs first to (re)write that section. `--note` may be
 * passed to override the CHANGELOG body for this release only.
 *
 * What it does, in order:
 *   1. Extracts the `## [<version>]` section from CHANGELOG.md (fails if
 *      missing — run scripts/changelog.mjs first).
 *   2. Discovers artifacts under tools/<tool>/dist/.
 *   3. Writes tools/<tool>/dist/SHA256SUMS.
 *   4. gh release create <tool>-v<version> --notes "<notes>"
 *      and uploads every artifact + SHA256SUMS.
 *
 * What it does NOT do:
 *   - Modify CHANGELOG.md. Run scripts/changelog.mjs separately for that.
 *   - Touch git. Run `git add` / `git commit` yourself.
 *
 * Pre-requisites:
 *   - gh CLI installed and authenticated (`gh auth status`).
 *   - tools/<tool>/dist/ contains the build output.
 *   - tools/<tool>/CHANGELOG.md has a `## [<version>]` section.
 *
 * Zero npm dependencies. Uses Node built-ins only.
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync, existsSync, statSync } from "node:fs";
import { join, resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");

function die(msg, code = 1) {
    process.stderr.write(`[FAIL] ${msg}\n`);
    process.exit(code);
}

function run(cmd, args, opts = {}) {
    process.stderr.write(`[run] ${cmd} ${args.join(" ")}\n`);
    return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], ...opts });
}

function tryRun(cmd, args) {
    try {
        return { ok: true, out: run(cmd, args) };
    } catch (e) {
        return { ok: false, out: (e.stdout || "") + (e.stderr || ""), status: e.status };
    }
}

function sha256File(path) {
    const buf = readFileSync(path);
    return createHash("sha256").update(buf).digest("hex");
}

function discoverArtifacts(distDir) {
    if (!existsSync(distDir) || !statSync(distDir).isDirectory()) {
        die(`dist directory not found: ${distDir}`);
    }
    const files = readdirSync(distDir)
        .filter((name) => name !== "SHA256SUMS")
        .map((name) => join(distDir, name))
        .filter((p) => statSync(p).isFile())
        .sort();
    if (files.length === 0) {
        die(`no artifacts found in ${distDir}. Drop the build output there first.`);
    }
    return files;
}

function writeChecksums(artifacts, dest) {
    const lines = artifacts.map((p) => {
        const name = p.split(/[\\/]/).pop();
        return `${sha256File(p)}  ${name}`;
    });
    writeFileSync(dest, lines.join("\n") + "\n", "utf8");
    process.stderr.write(`[ok] wrote ${dest}\n`);
}

function releaseExists(tag) {
    const r = tryRun("gh", ["release", "view", tag, "--json", "tagName"]);
    return r.ok && r.out.trim() && r.out.trim() !== "null";
}

function parseArgs(argv) {
    const args = { tool: null, version: null, notes: [], dryRun: false };
    const positional = [];
    for (let i = 2; i < argv.length; i++) {
        const a = argv[i];
        if (a === "--dry-run") args.dryRun = true;
        else if (a === "--note" || a === "-n") {
            const v = argv[++i];
            if (v === undefined) die("--note requires a value");
            args.notes.push(v);
        } else if (!a.startsWith("--") && !a.startsWith("-")) {
            positional.push(a);
        } else {
            die(`unknown flag: ${a}`);
        }
    }
    if (positional.length < 2) {
        die("usage: node scripts/release.mjs <tool> <version> " + '--note "..." [--note "..."] [--dry-run]');
    }
    [args.tool, args.version] = positional;
    if (!/^[\w.-]+$/.test(args.tool)) {
        die(`tool name must be [a-zA-Z0-9_.-] only (got: ${args.tool})`);
    }
    if (!/^\d+\.\d+\.\d+(-[\w.]+)?$/.test(args.version)) {
        die(`version must look like 1.2.3 or 1.2.3-rc.1 (got: ${args.version})`);
    }
    return args;
}

// Extract the body (bullet lines) of the `## [<version>]` section from a
// CHANGELOG.md. Returns null when the section is absent.
function readChangelogSection(raw, version) {
    const versionRe = /^## \[(\d+\.\d+\.\d+(?:-[\w.]+)?)\]/;
    const lines = raw.split("\n");
    let inTarget = false;
    const body = [];
    for (const line of lines) {
        if (versionRe.test(line)) {
            if (inTarget) break; // next version section starts
            inTarget = versionRe.exec(line)[1] === version;
            continue;
        }
        if (inTarget && /^## /.test(line)) break; // non-version section
        if (inTarget) body.push(line);
    }
    const trimmed = body.join("\n").trim();
    return inTarget && trimmed ? trimmed : null;
}

function main() {
    const args = parseArgs(process.argv);
    const toolDir = join(REPO_ROOT, "tools", args.tool);
    if (!existsSync(toolDir)) die(`tool directory not found: ${toolDir}`);

    const changelogPath = join(toolDir, "CHANGELOG.md");
    if (!existsSync(changelogPath)) {
        die(`CHANGELOG.md not found at ${relative(REPO_ROOT, changelogPath)}. Run \`pnpm changelog\` first.`);
    }
    const section = readChangelogSection(readFileSync(changelogPath, "utf8"), args.version);
    if (!section) {
        die(
            `no \`## [${args.version}]\` section in ${relative(REPO_ROOT, changelogPath)}. ` +
                `Run \`pnpm changelog -- ${args.tool} ${args.version} ...\` first.`,
        );
    }
    const notesBody = args.notes.length > 0 ? args.notes.join("\n") : section;

    const distDir = join(toolDir, "dist");
    const artifacts = discoverArtifacts(distDir);

    if (args.dryRun) {
        process.stderr.write(`\n[plan] tool       : ${args.tool}\n`);
        process.stderr.write(`[plan] dist       : ${relative(REPO_ROOT, distDir)}\n`);
        process.stderr.write(`[plan] files      :\n`);
        for (const p of artifacts) {
            process.stderr.write(`                 - ${relative(REPO_ROOT, p)}\n`);
        }
        process.stderr.write(`                 - ${relative(REPO_ROOT, join(distDir, "SHA256SUMS"))} (generated)\n`);
        process.stderr.write(`[plan] tag        : ${args.tool}-v${args.version}\n`);
        process.stderr.write(`[plan] notes preview${args.notes.length > 0 ? " (--note override)" : " (from CHANGELOG)"}:\n`);
        for (const line of notesBody.split("\n")) process.stderr.write(`    | ${line}\n`);
        return;
    }

    const tag = `${args.tool}-v${args.version}`;
    const title = `${args.tool} v${args.version}`;

    if (releaseExists(tag)) {
        die(`release ${tag} already exists. Bump version or delete the existing release first.`);
    }

    const sumsPath = join(distDir, "SHA256SUMS");
    writeChecksums(artifacts, sumsPath);

    run("gh", ["auth", "status"]);

    const cmdArgs = ["release", "create", tag, "--title", title, "--notes", notesBody];
    for (const a of artifacts) cmdArgs.push(a);
    cmdArgs.push(sumsPath);

    process.stderr.write("\n");
    run("gh", cmdArgs, { stdio: "inherit" });
    process.stderr.write(`\n[ok] published ${tag}\n`);
    process.stderr.write(`[next] make sure the changelog commit is pushed: git push\n`);
}

main();
