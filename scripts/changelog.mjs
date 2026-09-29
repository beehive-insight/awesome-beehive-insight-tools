#!/usr/bin/env node
/**
 * Update a tool's CHANGELOG.md by promoting a list of release notes into a
 * versioned section at the top of the file.
 *
 * Usage:
 *   node scripts/changelog.mjs <tool-name> <version>
 *     [--note "<release note>"] [--note "<another>"] [...]
 *     [--dry-run]
 *
 * What it does:
 *   1. Reads tools/<tool>/CHANGELOG.md.
 *   2. If a `## [<version>]` block already exists (any date), drops it so
 *      re-running for the same version replaces instead of duplicating.
 *   3. Inserts a fresh block `## [<version>] - YYYY-MM-DD` with the bullets
 *      given via --note, right after the file preamble.
 *   4. If no --note is given, generates a default bullet: "升级 <prev> →
 *      <version>" based on the latest existing version in the file (or
 *      "初始发布 <version>" when the file has no versioned entries yet).
 *   5. Leaves the rest of the file (older versioned entries) untouched.
 *
 * Side effects:
 *   - With --dry-run: prints the new file contents to stdout. File is not
 *     touched, git is not touched.
 *   - Without --dry-run: writes tools/<tool>/CHANGELOG.md. Git is *not*
 *     staged, added, or committed. Use your own `git add` / `git commit`.
 *
 * Zero npm dependencies. Uses Node built-ins only.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..");

function die(msg, code = 1) {
    process.stderr.write(`[FAIL] ${msg}\n`);
    process.exit(code);
}

const CHANGELOG_PREAMBLE = (tool) =>
    `# Changelog\n\n` +
    `All notable changes to \`${tool}\` are documented here. ` +
    `The format follows [Keep-a-Changelog](https://keepachangelog.com/).\n\n`;

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
        die(
            "usage: node scripts/changelog.mjs <tool> <version> " +
            "[--note \"...\"] [--dry-run]",
        );
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

function buildNew(raw, tool, version, notes) {
    const today = new Date().toISOString().slice(0, 10);
    const sectionHeaderRe = /^## \[/m;
    const versionRe = /^## \[(\d+\.\d+\.\d+(?:-[\w.]+)?)\]/;

    // Split the file into a preamble (everything before the first `## [` header)
    // and a list of version sections (each starting with a `## [` header and
    // running until the next `## [` header or end-of-file).
    const firstSectionIdx = raw.search(sectionHeaderRe);
    const preamble = firstSectionIdx < 0 ? raw : raw.slice(0, firstSectionIdx);
    const rest = firstSectionIdx < 0 ? "" : raw.slice(firstSectionIdx);

    // Walk the rest, splitting into [version header line, body...] chunks.
    const lines = rest.split("\n");
    const chunks = [];
    let current = null;
    for (const line of lines) {
        if (sectionHeaderRe.test(line)) {
            if (current) chunks.push(current);
            current = [line];
        } else if (current) {
            current.push(line);
        }
        // Lines before the first `## [` header are part of the preamble and
        // already handled above.
    }
    if (current) chunks.push(current);

    // Drop any section for the target version (match version only, not the
    // date, so re-running on a later day still replaces instead of duplicating).
    const filtered = chunks.filter((c) => {
        const m = c[0].match(versionRe);
        return !m || m[1] !== version;
    });

    // Default note when none provided: "升级 <prev> → <version>", where prev is
    // the latest remaining version section. Falls back to an initial-release
    // note when the changelog has no versioned entries yet.
    if (notes.length === 0) {
        const prev = filtered
            .map((c) => c[0].match(versionRe)?.[1])
            .find(Boolean);
        notes = prev
            ? [`升级 ${prev} → ${version}`]
            : [`初始发布 ${version}`];
    }

    // Build the new section.
    const targetHeader = `## [${version}] - ${today}`;
    const bullets = notes.map((n) => `- ${n}`).join("\n");
    const newSectionLines = [targetHeader, ""];
    if (bullets) {
        for (const b of bullets.split("\n")) newSectionLines.push(b);
        newSectionLines.push("");
    }
    const newSection = newSectionLines.join("\n");

    // Compose: preamble (kept as-is when non-empty) + new section + remaining sections.
    const normalisedPreamble =
        preamble.trim().length > 0 ? preamble : CHANGELOG_PREAMBLE(tool);
    const tail = filtered.map((c) => c.join("\n")).join("\n");
    return normalisedPreamble + "\n" + newSection + "\n" + tail + "\n";
}

function main() {
    const args = parseArgs(process.argv);
    const toolDir = join(REPO_ROOT, "tools", args.tool);
    if (!existsSync(toolDir)) die(`tool directory not found: ${toolDir}`);
    const path = join(toolDir, "CHANGELOG.md");
    if (!existsSync(path)) {
        die(
            `CHANGELOG.md not found at ${relative(REPO_ROOT, path)}.\n` +
            `Create it once (e.g. \`touch tools/${args.tool}/CHANGELOG.md\`) ` +
            `and the script will keep it in shape afterwards.`,
        );
    }

    const raw = readFileSync(path, "utf8");
    const next = buildNew(raw, args.tool, args.version, args.notes);

    if (args.dryRun) {
        process.stderr.write(`\n[dry-run] ${relative(REPO_ROOT, path)} would become:\n\n`);
        process.stdout.write(next);
        return;
    }

    writeFileSync(path, next, "utf8");
    process.stderr.write(`[ok] updated ${relative(REPO_ROOT, path)}\n`);
    process.stderr.write(
        `[next] review the diff: git diff tools/${args.tool}/CHANGELOG.md\n`,
    );
}

main();