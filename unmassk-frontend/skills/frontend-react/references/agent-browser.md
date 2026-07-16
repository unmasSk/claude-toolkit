# AgentBrowser — the frontend's browser tool

Browser automation **built for AI agents**: drives Chrome/Chromium over CDP (no Playwright or Puppeteer underneath), with accessibility-tree snapshots and compact `@eN` refs (~200-400 tokens instead of dumping the whole DOM). Native Rust CLI, and an MCP server (`mcp__agent-browser__*` typed tools). Apache-2.0.

## When to use it (scope)

Use AgentBrowser the moment a task needs you to **observe or drive the rendered UI**: validate how something looks on screen, scrape a page, navigate, fill a form, check a flow, log into a site. Writing components/hooks/JSX/CSS by itself does not — this applies once you must *look at* or *drive* the running UI.

**Single exception: TESTS.** Suites and specs (E2E, component, regression) are written with **Playwright** (runner, assertions, fixtures, CI reporting). AgentBrowser is not a testing framework and does not replace them.

## Activate the MCP (on-demand — Claude drives this)

The agent-browser MCP is **not connected by default**. The first time this
skill needs it, Claude registers it, then tells the user to restart. Claude
runs these steps and guides the user — the user only restarts when told.

1. **Register the server** (once, user scope — available in every project):
   ```
   claude mcp add agent-browser --scope user -- agent-browser mcp
   ```
2. **Restart Claude Code.** MCP servers only start at boot; there is no hot
   activation. After the restart, Claude Code exposes the typed
   `mcp__agent-browser__*` tools (default profile `core`).
3. **API key:** none — agent-browser needs no key.

This is the standard on-demand shape for every MCP in the toolkit: register →
restart → (key if needed). The `agent-browser` CLI remains available for
install, docs, and as a fallback while the MCP is not yet registered.

## Preflight & install (once per machine)

The MCP server needs the `agent-browser` binary at **>= 0.31.2** (the version that ships `agent-browser mcp`). Before first use:

```bash
agent-browser --version                       # must be >= 0.31.2
# if missing or older:
npm i -g agent-browser@latest                 # pinned to >= 0.31.2 (mcp support)
agent-browser install                         # downloads Chrome for Testing (~186 MB), one time
```

**If install fails (no network, locked-down machine), STOP and report — never fake a visual check.** Faking "looks fine" is the exact silent failure this toolkit exists to prevent.

Version note: 0.27.0 and earlier have **no** `mcp` subcommand — do not rely on a stale global install. Verify the version, do not assume it.

## The "how" is always current — read it before running commands

AgentBrowser serves its own usage guide, **version-matched to the installed binary** (never stale):

```bash
agent-browser skills get core          # workflows, patterns, refs/selectors, troubleshooting
agent-browser skills get core --full   # + full command reference and templates
agent-browser skills list              # specialized skills (dogfood = QA/bug hunt, etc.)
```

Exact command/tool syntax lives there. This page pins the **criterion** (when and what for) and the **preflight**; the exact **how** comes from `skills get core`. Do not hardcode command syntax from memory.

## Usage patterns

### Visual validation (capture → Read → judge)

Do not trust "it should look fine". Capture, **read the image back, and judge it**:

1. `agent-browser open <url>`
2. `agent-browser screenshot <scratchpad>/ui-check.png` — save into the **session scratchpad dir**, not the repo.
3. **`Read` the PNG** and evaluate: broken / correct / missing / overlapping / off.
4. `agent-browser close`

The value is that the agent **actually sees** the result. Step 3 is not optional — a screenshot nobody reads proves nothing.

### Inspection and scraping (snapshot + refs)

`agent-browser snapshot` returns the accessibility tree with refs (`[ref=e1]`, `[ref=e2]`…); interact by ref (`click @e2`, `fill @e3 "text"`), extract with `text`/`html`. Snapshot is the low-context way for the agent to understand a page. For exact syntax and the interaction set, read `agent-browser skills get core` — it is version-matched; this file does not restate it.

### Login / session / stateful automation

AgentBrowser supports persistent profiles, credentials, cookies, and session state for authenticated flows and logged-in scraping. Load `agent-browser skills get core` for the exact profile/session flags instead of guessing.

## Verified

`open` / `snapshot` / `screenshot` / `close` and `agent-browser mcp` (`initialize` handshake) confirmed working on Windows x64 with 0.31.2. Interaction flags (click/fill/login) come from `skills get core`, the version-matched source — not asserted here from memory.
