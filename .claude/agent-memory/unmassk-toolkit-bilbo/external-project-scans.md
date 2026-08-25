---
name: external-project-scans
description: Bilbo deep scans of codebases outside the toolkit's own skills/plugins — chatroom (in-repo) and omawamapas (external repo). All dated March 2026, none re-verified since — treat as a snapshot, not current state.
metadata:
  type: project
---

None of these map to a `gitmem zones list` zone of `claude-toolkit` itself — `chatroom/` lives inside
this repo but is its own project, and `omawamapas` is a fully separate repo at
`/Users/unmassk/Workspace/omawamapas/`. Both dirs were confirmed to still exist 2026-08-25 (EXECUTED
`ls`), but their internal content was NOT re-read — 5+ months have passed since these scans and none of
the specific claims below (dead exports, orphan files, root-cause diagnoses) were re-verified.

## chatroom (`chatroom/apps/backend/`, `chatroom/apps/frontend/`)

### 2026-03-19 — backend `src/` dependency graph, dead exports, structural anomalies

**Dead exports:** `config.ts:WS_ROOM_TOPIC_PREFIX` (never imported), `stream-parser.ts:StreamEvent`/
`PermissionDenial` types (never imported outside their own file), `logger.ts` default export
`rootLogger` (all consumers use named `createLogger` instead), `utils.ts:formatTimeHHMM` (only in its
own test file).

**Structural anomalies:** (1) `BANNED_TOOLS` defined twice — `config.ts:178` (array, consumed by
agent-invoker) AND `agent-registry.ts:32` (Set, private copy) — two sources of truth for a
security-critical blocklist. (2) `RESERVED_AGENT_NAMES` independently constructed in both `ws.ts:130`
and `auth-tokens.ts:33`, different code paths reaching the same set (divergence risk — same pattern
flagged for `boot_migrations.py`'s duplicate `_migrate_runtime_to_unmassk()`, see
`boot-memory-mechanics.md`). (3) `logger.ts:23` reads `process.env.LOG_LEVEL` directly instead of the
validated `LOG_LEVEL` from `config.ts` — bypasses enum validation, invalid value silently falls back to
pino's default instead of `exit(1)`. (4) `log()` helper (unstructured variadic concat) duplicated in
`ws.ts:4`, `agent-invoker.ts:22`, `mention-parser.ts:5` — inconsistent with the structured
`logger.warn({}, 'msg')` pattern used elsewhere in the same files. (5) Circular dependency
`message-bus.ts` → lazy `import('../index.js')` inside `getApp()` — intentional/documented, needed
because `index.ts` exports the Elysia app singleton.

**Missing source file:** `routes/invite.test.ts` (340 LOC) tests POST /api/rooms/:id/invite but builds
its own inline Elysia app rather than importing `apiRoutes` from `routes/api.ts` — not an orphan (it
does test real behavior) but the name implies a `routes/invite.ts` that doesn't exist.

**Oversized files (>500 LOC):** `services/agent-invoker.ts` (1154 LOC — god module: scheduling, queue,
subprocess spawn, stream parsing, prompt building, session mgmt, cost tracking, @mention chaining,
rate-limit retry, context-overflow respawn; candidate split: agent-scheduler / agent-runner /
prompt-builder). `routes/ws.ts` (542 LOC — rate limiter state machine + connection state + all WS
handlers; rate limiter and connection state extractable).

**Root-level stray files:** `design-mocks/` (20+ HTML mock UIs + a JSON + a design-session .md, no
`docs/`/`design/` subdir), `design-references/` (mockup HTML at root), `generated-images/` (HTML files
despite the name implying images). `PLAN.md`/`PROGRESS.md`/`CHANGELOG.md`/`start.sh`/`start.bat` at
root — acceptable for a project of this shape.

**Committed DB files:** `apps/backend/data/chatroom.db(-shm/-wal)` live SQLite files in the repo.
`chatroom/.gitignore` excludes root `data/` but these are under `apps/backend/data/` — unverified
whether a nested `.gitignore` also covers them. `.env.example` defaults `DB_PATH=data/chatroom.db`,
relative to the backend dir.

No escalation needed at the time — structural/dependency audit only.

### 2026-03-19 — backend production-readiness inventory

**Present:** structured pino logging (no rotation), Elysia `t.Object` validation on all HTTP routes +
Zod (`packages/shared/src/schemas.ts`) on WS protocol, origin-locked CORS, custom in-memory
token-bucket rate limiting (WS 5msg/10s, API 20/min), short-lived one-time WS auth tokens (30min TTL +
GC), prompt-injection sanitization (`sanitizePromptContent()`), `/health` endpoint, `bun:sqlite` WAL
mode singleton, strict TypeScript (+noUncheckedIndexedAccess/noImplicitReturns/noFallthroughCasesInSwitch),
20 `bun:test` files (unit+integration+smoke, real in-memory DB, no SQLite mocking), hot reload, partial
signal handling (`start.sh` traps EXIT, but `index.ts` has no `SIGTERM` handler), 64KB WS payload
ceiling.

**Absent:** Swagger/OpenAPI docs, global Elysia `onError` handler (unhandled exceptions surface as
Elysia's default 500), Helmet/security headers, CSRF protection on `/api/auth/token`, log rotation,
ORM/query builder (raw `bun:sqlite`), migration tooling (schema init via `CREATE TABLE IF NOT EXISTS`,
no versioning/rollback), Prometheus/OTel metrics, Sentry/error tracking, env-var validation library,
Docker/containerization, coverage tooling, ESLint/Biome/Prettier config, graceful shutdown, connection
pooling (N/A by design — single-connection `bun:sqlite`, WAL enables concurrent reads).

No escalation — inventory scan only.

### 2026-03-21 — frontend WS reconnect-storm diagnosis (2 competing theories, both partly wrong)

Traced `vite.config.ts` → `ws-store.ts` → `useWebSocket` → all status subscribers for a
crash-on-backend-stop report. 3 status subscribers total (`MessageInput.tsx:17`, `StatusBar.tsx:6`,
`useWebSocket.ts:24`); `App.tsx:12` discards the hook's return value entirely (`useWebSocket(ROOM_ID)`,
no destructure — re-renders but has no status-derived JSX). `ParticipantItem.tsx` subscribes only to
the stable `send` function ref, no re-render on status change. Per reconnect cycle: 2 `set()` calls ×
10 attempts × 3 subscribers = 60 renders total — trivial.

**Theory 1 (partly right, overblown):** the debounce fix (`CONNECT_DEBOUNCE_MS=2000`) was an unstaged
change in `ws-store.ts`, not yet in the committed code (`bc7ff45`, no debounce). React Fast Refresh
does NOT unmount/remount for module edits (only on component-identity change) — the real HMR risk was
module reinitialization resetting `socket=null` + guards mid-session, abandoning the live WebSocket
with no cleanup (a resource leak, not a connection storm). Reconnect-timer callbacks bypass the
debounce by design (`reconnectAttempts > 0`).

**Theory 2 (partly right):** Vite proxy has no `proxyTimeout` (confirmed) — but locally, backend death
sends a TCP RST → immediate 502, so the 75s SYN-retransmit path only matters if packets are silently
dropped (firewall), not the local-dev case. `AbortController` is passed to fetch (`ws-store.ts:198`)
but only cancels on `disconnect()`, not on timeout. No circuit breaker: `reconnectAttempts` caps at 10
but never distinguishes WHY the server is dead.

**Actual root cause (missed by both):** backend dies → WS close → `connect()` → fetch
`/api/auth/token` → no-timeout Vite proxy → instant 502 locally → reconnect timer. The 10-attempt
exponential backoff (1→2→4→8→16→30×5s, ~181s total) is correct, not a storm. **Unaddressed gap:** the
token fetch has an `AbortController` from `disconnect()` but no `AbortSignal.timeout()` — if a fetch is
mid-flight and `disconnect()` never fires (server just blips instead of dying), it hangs until OS TCP
timeout in non-ECONNREFUSED scenarios.

No escalation — structural trace only.

## omawamapas (`/Users/unmassk/Workspace/omawamapas/`) — geospatial SPA, asbestos inventory management

### 2026-03-15 — technology stack scan

Backend: Node 22+/Express 5/TS ESM/Knex+pg. Frontend: React 19/Vite/TS/Radix UI/Mapbox GL
JS/Turf.js/Axios/react-router-dom 7. DB: PostgreSQL 17+PostGIS 3.3/3.4 via Supabase (eu-west-1 pooler).
Cache: Upstash Redis (ioredis, TLS). Auth: mock headers in dev, JWT in prod. API docs:
swagger-jsdoc+swagger-ui-express. Testing: Vitest+Supertest+Testing Library. Monitoring: Sentry (node
9.x+profiling). Rate limiting: express-rate-limit+Helmet+compression+opossum circuit breaker. Hosting
target: Supabase+Upstash+AWS EC2/RDS/ElastiCache for staging/prod.

**Toolkit skill matches at the time:** db-postgres/db-redis/db-migrations direct matches;
db-schema-design and compliance-owasp relevant; compliance-gdpr potentially relevant; ops-observability
only a partial match (Sentry present but that skill was infra-level Prometheus/Grafana, not app-level —
**note: `unmassk-ops` gained `ops-error-tracking` since, see `toolkit-audits.md`, not re-checked
against this project**); ops-iac relevant for the planned AWS staging architecture. **Confirmed gaps at
the time:** no app-level error-tracking skill, no Mapbox/geospatial frontend skill, no Supabase-specifics
skill, no Knex/query-builder skill, no React19/Vite dev skill.

No orphans/dead code investigated — inventory scan only.

### 2026-03-15 — `db/` deep trace: PostgreSQL schema + Knex + connection pool

Schema (`schema.sql`, source of truth): 4 tables (`municipio`, `usuario`, `inventario_amianto`,
`asignacion_tecnico_municipio`), PostGIS geometry columns on 2 of them, an MVT tile function
(`public.inventario_amianto_mvt`).

**Critical anomalies confirmed at the time:**
1. **5 phantom tables** queried by code but absent from `schema.sql` — `usuarios` (plural; real table
   is `usuario`, singular) in `permissions.access.service.ts`/`permissions.lookup.service.ts`;
   `layer_permissions`, `spatial_layers`, `supervisor_municipio`, `operador_municipio` across
   permissions/search modules. These modules will throw Postgres `42P01 UNDEFINED_TABLE` at runtime.
2. Duplicate btree index on `asignacion_tecnico_municipio(usuario_id)` —
   `idx_asignacion_tecnico_municipio_usuario` (line 539) and `..._usuario_id` (line 546).
3. **Knex is vestigial** — installed with a CLI alias but the single migration file
   (`20250507162238_initial_schema_setup.ts`) has empty `up()`/`down()`. The real schema was deployed
   via `pg_dump`'d `schema.sql`; the MVT function via a separate `create-mvt-function.ts`.
4. `asignacion_tecnico_municipio` INSERT in `permissions.assign.service.ts` references a
   `fecha_asignacion` column that does not exist in `schema.sql` — will fail at runtime.

**Connection pool (`pg` direct driver, not Knex):** max connections env `DB_MAX_CONNECTIONS` (default
20), idle timeout 30000ms (hardcoded), connection timeout env `DB_CONNECTION_TIMEOUT_MS` (default
5000ms), statement timeout 30000ms (hardcoded), query timeout env `DB_QUERY_TIMEOUT_MS` (default
35000ms), idle-in-transaction 60000ms (hardcoded), keepalive 10000ms delay, SSL strict in prod
(provider-detected), 60s telemetry log + saturation/queue-depth alerts. `database.ts` is the facade,
`query-executor.ts` wraps all SQL — most modules import via the `database.js` re-export, geo/most
permissions modules import `query-executor.js` directly.

**Escalation at the time:** Cerberus/Argus should review the permissions module for the schema-drift
runtime failures (#1 and #4 above). **Not re-verified 2026-08-25 — if this project is touched again,
re-check whether the phantom tables were ever created or the code fixed, do not assume either.**

### 2026-03-15 — `frontend/src/` deep trace: React 19 + Mapbox GL JS

**Component hierarchy:** `main.tsx` → `AuthProvider` → `BrowserRouter` → `App` → `MainLayout` →
`HomePage` → `MapContainer`, which orchestrates `MapInitializer`/`MapFeatureHandler`/`MapHoverHandler`/
`MapCenterer`/`MapRestrictionHandler`/`MapDiagnostics`/overlay+spinner/`InfoPanel`. `InfoPanel` →
`FloatingControls` + (`AmiantoVisorPanel` or `AmiantoGestorPanel` by edit mode) → tab panels.

**State:** no global-state library — `AuthContext` is the sole global container; all map state is
local `useState` in `MapContainer`; services are `api.ts` (Axios) + `municipioService` +
`authService`, mock auth via localStorage + `X-Mock-*` headers hardcoded to `userId=2, role='Tecnico'`.

**Mapbox integration:** worker loaded via Vite `?url` import in `useMapUtils`; only the `'fill'`
polygon layer is actually used in production — `addPointLayer`/`addLineLayer`/`addClusterLayer` are
defined but never consumed; tile source is a `pg_tileserv` MVT endpoint matching the backend function.

**Confirmed orphans/dead code (18 items):** a second, unconsumed `components/map/MapContainer.tsx`
(re-exported from its own index only); the entire `visor-tabs/` directory (4 files, ~1,129 LOC) —
superseded by `tabs/` (which `AmiantoVisorPanel` actually imports) but never deleted, same 4 component
names in both, a refactor remnant; `AmiantoVisorPanel.optimized.tsx` (never imported);
`hooks/useMapFilters.ts`, `utils/clusterLayers.ts`, `utils/mapHelpers.ts`, `utils/renderCounter.ts`,
`utils/performance-observer.ts`, `src/mapbox-shim/index.ts`, `src/mapbox-gl-worker-setup.ts` (worker
setup is actually done inline via the `?url` import instead) — all confirmed zero consumers;
`useMapLayers` exports 5 functions, only 2 consumed; `useMapUtils.isPointInCurrentView` never consumed;
`services/api.ts:clearMockAuthHeaders` referenced only in a log-comment string, never called;
`components/panels/KeyValuePair.tsx`, `panels/amianto/StatusCard.tsx`, `BaseInfoList.tsx`,
`InventarioTable.tsx`, `QuickCreateForm.tsx` — all exported, none imported anywhere.

**Auth is entirely mock-only, and cannot truly log out:** `logout()` calls `setMockAuthHeaders(2,
'Tecnico')` — it RE-SETS the mock user rather than clearing it. `LoginPage.tsx` renders a form with no
`onSubmit` handler.

**Double hover handling confirmed:** `useMapEvents` (in `MapContainer` body) AND `MapHoverHandler`
(rendered component) both independently attach hover Popups to the `'inventario-polygons'` layer.

**Dev tooling shipped in the production tree:** `PerformanceProfiler` wraps render in every major
component; `PerfTest` (Shift+T) and `PerformanceMonitor` (Shift+P) debug tools mount on every `App`
render, not gated out of production builds.
