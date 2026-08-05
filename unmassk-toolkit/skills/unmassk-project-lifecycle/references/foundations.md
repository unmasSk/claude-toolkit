# Enterprise Foundations Catalog

> Reference for START **phase D**. The full menu of engineering foundations offered before a line of business code is written.

## Rules for this catalog

- **Listed by NAME, never by tool.** "Validation", "structured logging", "migrations" — never Zod / pino / Alembic. The concrete tool is a choice the implementer makes at build time, with whatever is current for the chosen stack. The foundation is stable; tools age.
- **Opt-out, not opt-in.** Every applicable foundation is *offered*; the user declines what they don't want. Nothing critical is silently omitted because someone forgot to mention it.
- **Mandatory vs Conditional.** Each foundation is either Mandatory (any serious project) or Conditional (only when its condition holds). Present all of them; skip a Conditional only when its condition is clearly absent (e.g. no money moves → no money foundation).
- **No ellipses, no "etc."** This list is closed. If a foundation is missing, it is added by name — never left to the AI's imagination at build time.

## How to run this in phase D

Do NOT read all ~60 foundations out one by one — that gets abandoned by block 3. Present them in bulk, filtered by the project:

1. **Know the project shape** from phases A–D: public web? money moving? multiple locales? multiple services? database? regulated data? containers?
2. **Auto-accept the Mandatory set** in one move — list them and ask a single "anything here you want to drop?". These are the non-negotiables of any serious project.
3. **Prune the Conditionals by shape.** Drop the ones whose condition is clearly absent (no money → no money foundation; no public web → no cookies / SEO / security headers) — don't even show those.
4. **Ask one-by-one only the genuinely doubtful** Conditionals — the ones where the condition might or might not hold.
5. **Save every foundation accepted AND every one declined** — a "no" is a decision with a reason, and unsaved it comes back as a proposal in three months.
6. The implementer picks the concrete tool per stack at build time (phase E) — never here.

## Toolkit coverage map (which skill already delivers each block)

The catalog is tool-agnostic, but the toolkit already ships the implementation for most of it. When a foundation is accepted, reach for its skill in phase E instead of hand-rolling it:

| Block | Toolkit skill(s) that already cover it |
|---|---|
| 1 — Core cross-cutting | `unmassk-standards` (discipline); i18n → `compliance-i18n` |
| 2 — Code quality | `unmassk-standards` (limits + principles), `typescript-strict`, `frontend-react` |
| 3 — Testing | `unmassk-standards` §34/§34.5, agent `dante` |
| 4 — API & contracts | mostly a gap — document inline |
| 5 — Data & persistence | `db-postgres`, `db-mysql`, `db-mongodb`, `db-redis`, `db-migrations`, `db-schema-design` |
| 6 — Security | `compliance-owasp-privacy`; secrets/CI scanning → `ops-cicd`, `ops-containers` |
| 7 — Observability | `ops-observability`, `ops-error-tracking` |
| 8 — CI/CD & DevOps | `ops-cicd`, `ops-containers`, `ops-iac`, `ops-deploy`, `ops-scripting` |
| 9 — Compliance & legal | `compliance-gdpr`, `compliance-lopdgdd`, `compliance-cookies`, `compliance-nis2`, `compliance-ens`, `compliance-soc2-iso`; SEO → `unmassk-seo`; a11y → `unmassk-design` |
| 10 — Performance | caching → `db-redis`; assets/CWV → `unmassk-seo` |
| 11 — Documentation & process | `unmassk-memory`, agent `alexandria` |
| 12 — Engineering principles | `unmassk-standards` |

A block with no skill (block 4, and any gap noted during design) is documented inline in phase E with a direct implementation, not a pointer to a skill that doesn't exist.

---

## Block 1 — Core cross-cutting

| Foundation | What it buys | When |
|---|---|---|
| Input/output validation | Every value crossing a boundary is checked for shape and type before use | Mandatory |
| Validated env configuration | Env vars read once into a typed, validated object; fails loudly at boot; never read ad-hoc | Mandatory |
| Secrets management | Secrets out of code and repo; rotatable; access auditable | Mandatory (never commit secrets) / Conditional (dedicated vault, by project size) |
| Structured logging with correlation/request ID | JSON logs carrying one ID across a whole request, correlatable across services | Mandatory |
| Centralized error handling + typed domain errors | One place translates errors; a hierarchy of business errors, not loose strings | Mandatory |
| Date/time discipline | Stored in UTC, converted to zone only at presentation, through one single utility | Mandatory |
| Money/decimals | Monetary amounts represented without floating-point error | Conditional — only if money moves |
| Internationalization (i18n/l10n) | Text, formats and layout adapt to language/region | Conditional — only if more than one locale/region |

## Block 2 — Code quality

| Foundation | What it buys | Default (tunable in project profile) | When |
|---|---|---|---|
| Strict typing | The compiler/analyzer rejects implicit or unsafe types | — | Mandatory |
| Linter | Static analysis catches errors and anti-patterns before running | — | Mandatory |
| Formatter | Deterministic automatic formatting; zero format diffs | — | Mandatory |
| Lines per file | Cap on source file size | ≤ 300 | Mandatory |
| Lines per function | Cap on function size | ≤ 50 | Mandatory |
| Parameters per function | Object of options beyond the cap | ≤ 4 | Mandatory |
| Cyclomatic complexity | Independent execution paths per function | ≤ 10 | Mandatory |
| Nesting depth | Nested block levels (early returns beyond) | ≤ 3 | Mandatory |
| Lines per component | Cap on a UI component | = file cap unless overridden | Conditional — frontend |
| Line length | Characters per line | 100 | Mandatory |
| Naming convention | Casing/pattern per symbol kind | per stack | Mandatory |
| Pre-commit hooks | Lint/format run automatically before each commit | — | Mandatory |
| Code documentation | Docstrings on non-obvious exported symbols; never restate the signature | — | Mandatory (public library API) / Conditional (internal) |
| Dead-code detection | Tooling that finds exports/functions with no consumers | — | Mandatory |
| Logging levels/discipline | A taxonomy for when to use DEBUG/INFO/WARN/ERROR | — | Mandatory |

## Block 3 — Testing

| Foundation | What it buys | Default | When |
|---|---|---|---|
| Unit tests | Verify a unit of logic in isolation | — | Mandatory |
| Integration tests | Verify real components collaborate correctly | — | Mandatory |
| End-to-end tests | Verify the full flow from the public entry point | — | Conditional — if there's a UI or a critical multi-service flow |
| Contract tests | Producer and consumer of an API honor the same contract without co-deploying | — | Conditional — if two or more services talk over an API |
| Coverage threshold | CI gate that blocks merge below a number | ~90% functions / ~80% error paths | Mandatory |
| Real-dependency tests (no infra mocks) | The feature's core seam runs at least once against a real, disposable dependency | — | Mandatory |
| Factories / fixtures | Reusable test-data builders instead of hardcoded objects | — | Mandatory |
| Production guard | A technical guard (not a convention) that aborts the suite if it points at production | — | Mandatory |

## Block 4 — API & contracts

| Foundation | What it buys | When |
|---|---|---|
| Schema-generated API docs | The API spec is derived mechanically from the same object that validates the request — never hand-written in parallel | Conditional — if there is an API |
| API versioning | An explicit strategy for breaking changes without breaking existing consumers | Conditional — if the API has external consumers |
| Shared front↔back contracts | Backend validation types and frontend typing come from one source, not two hand-kept copies | Conditional — full-stack / monorepo |

## Block 5 — Data & persistence

| Foundation | What it buys | When |
|---|---|---|
| Versioned immutable migrations | Each schema change is a numbered file never edited after applying; the history is the source of truth | Conditional — if there is a database |
| Transactions & consistency | Multi-step operations are atomic; isolation and conflict handled explicitly | Conditional — if there is a database |
| Connection pooling | Reused connection pool instead of one per request | Conditional — if there is a database |
| Backups & point-in-time recovery | Backup + restore-to-an-instant, with recovery tested, not assumed | Conditional — if there is a database with real data |
| System-only seeds | Seeds populate only structural data (roles, config, catalogs) — never demo data mixed with the boot mechanism | Conditional — if there is a database |

## Block 6 — Security

| Foundation | What it buys | When |
|---|---|---|
| Authentication | Verify user identity | Conditional — if there are stateful users |
| Server-side authorization / RBAC | Access by role/permission revalidated on every server request | Conditional — if more than one role |
| Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options) | HTTP headers mitigating XSS, clickjacking, sniffing | Conditional — any public web app |
| Rate limiting / anti-abuse | Limit request frequency per IP/user/endpoint | Conditional — public and auth endpoints |
| Boundary sanitization | Validate/sanitize all external input at the edge | Conditional — any public API |
| Secrets out of repo + scanner | Never commit secrets; scan repo/history for them | Mandatory |
| Dependency audit | Scan dependencies for known vulnerabilities + automated updates | Mandatory |
| Signed + idempotent webhooks | Verify third-party payload signatures + deduplicate by event ID | Conditional — if the project receives webhooks |
| CORS | Cross-origin policy between browser and API | Conditional — if front and back are on different origins |
| OWASP defense (injection, XSS, CSRF, SSRF) | Prevention of the four most common vulnerability classes | Conditional — any public web app |
| Encryption in transit (TLS) | Encrypt HTTP traffic with TLS 1.2+/1.3 | Mandatory (public) |
| Encryption at rest | Encrypt stored data | Conditional — PII/health/financial; recommended always |

## Block 7 — Observability

| Foundation | What it buys | When |
|---|---|---|
| Error monitoring | Capture uncaught exceptions in production | Mandatory (production) |
| Tracing (request ID, OpenTelemetry) | Correlate a request across services | Conditional — multi-service; recommended in a large monolith |
| Metrics | Time series for latency, throughput, error rate | Conditional — production multi-service |
| Health checks | Liveness/readiness endpoint | Conditional — if orchestrated; recommended always |
| External uptime monitoring | External probe verifying public availability | Conditional — public SLA; recommended always |
| Alerting | Notification on threshold breach or critical error | Mandatory (production) |
| Business audit log (who did what, before/after) | Immutable record of business actions with diff | Conditional — regulated domains; recommended for admin actions |

## Block 8 — CI/CD & DevOps

| Foundation | What it buys | When |
|---|---|---|
| Blocking CI pipeline | install → lint → typecheck → test → build → dependency audit → secret scan → dead-code, blocks merge on any failure | Mandatory |
| CD (auto staging, manual production) | Automatic deploy to staging, deliberate manual promotion to production | Conditional — if there is more than one environment |
| Containers (multi-stage) | Build/runtime stages separated | Conditional — if the deploy uses containers |
| Orchestration / IaC | Declarative infra and deploy at scale (K8s/Helm/Terraform) | Conditional — by scale/complexity |
| Environment parity (local/staging/prod) | Comparable environments; the cloud jump is a config change, not a code change | Mandatory |
| Lockfiles + pinned versions | Exact versions for reproducible builds | Mandatory |
| Feature flags | Toggle functionality without a deploy | Conditional — offered with justified opt-out; expected with frequent CD |

## Block 9 — Compliance & legal

| Foundation | What it buys | When |
|---|---|---|
| GDPR/LOPDGDD | Consent, retention, right to erasure | Conditional — if there is EU/Spain user data |
| Cookie consent | Consent banner before non-essential cookies | Conditional — non-essential cookies + EU users |
| Accessibility (WCAG) | Interface usable with disabilities | Conditional — any UI (legal in EU public sector) |
| Technical SEO | Crawlability, indexability, metadata, structured data | Conditional — public indexable web surface |
| Licensing | Choose own license; verify dependency license compatibility | Mandatory (choose one) / Conditional (compatibility scan if distributed) |

## Block 10 — Performance

| Foundation | What it buys | When |
|---|---|---|
| Caching strategy | Cache layers (CDN, app, DB) | Conditional — significant traffic; recommended from day one |
| Asset optimization | Compress images, minify, modern formats, lazy loading | Conditional — frontend with heavy assets |
| Performance budgets (Core Web Vitals) | Enforced LCP/INP/CLS/TTFB thresholds | Conditional — public web with SEO/conversion goals |

## Block 11 — Documentation & process

| Foundation | What it buys | When |
|---|---|---|
| README + 3-audience docs | Every capability documented for repo visitors, the team, and the loading AI, in the same change | Mandatory |
| CHANGELOG | Versioned record of notable changes, human-written, not raw commit dumps | Mandatory |
| Branching / repo type | Explicit, persisted decision: trunk (main is the working branch) vs gitflow (main protected, PR) | Mandatory |
| TODO-with-issue | A `TODO` in code is only valid if it references a tracked issue | Mandatory |

## Block 12 — Engineering principles (the discipline that governs how all code is written)

These are not tools; they are the discipline enforced in review and, where possible, by lint. All Mandatory unless noted.

| Principle | In one line |
|---|---|
| YAGNI | Don't build what isn't needed today; no speculative code |
| KISS | The simplest thing that works |
| DRY | Extract after the second duplication; abstraction mandatory at three |
| SOLID — SRP | One module, one reason to change |
| SOLID — OCP | Open to extension, closed to modification |
| SOLID — LSP | A subtype is substitutable for its supertype without breaking the contract |
| SOLID — ISP | Small specific interfaces, not one fat general-purpose one |
| SOLID — DIP | Depend on abstractions, not concrete implementations |
| Separation of concerns | Each module does one thing; layers not mixed |
| Composition over inheritance | Prefer composing objects/functions over deep inheritance |
| Law of Demeter | An object talks only to its direct neighbors, not `a.b.c.d` chains |
| Principle of least astonishment | Behavior matches what the name/signature promises |
| Fail-fast | Validate at the boundary and stop on invalid state instead of propagating it |
| Single source of truth | One authoritative place per datum/config; everything else derives or references it |
| Boy-scout rule | Leave code a little cleaner than you found it |
| Twelve-Factor App | Config in env, stateless processes, logs as streams, dev/prod parity, etc. — Conditional: cloud-native/containers |
