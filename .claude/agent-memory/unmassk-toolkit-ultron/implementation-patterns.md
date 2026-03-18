---
name: elysia-ws-upgrade-context
description: Elysia .ws() upgrade hook receives an Elysia Context, not a Request object
type: project
---

Elysia's `.ws()` upgrade hook parameter is an **Elysia Context**, not a Web API `Request`.

- `context.headers` is a plain `Record<string, string>` — use bracket access: `context.headers['origin'] ?? ''`
- Do NOT call `.get()` on headers — that is a `Headers` API method absent on Elysia's plain object
- To reject an upgrade, use `context.set.status = 403; return 'Forbidden'` — do NOT return `new Response(...)` from the Elysia hook
- To accept and annotate the connection, return `{ data: { ...extraFields } }`

**Why:** House diagnosed a T1 bug (2026-03-17) where `request.headers.get('origin')` threw a TypeError on every WS upgrade, causing HTTP 500.

**How to apply:** Any time the `.ws({ upgrade })` hook is written or modified in this codebase.
