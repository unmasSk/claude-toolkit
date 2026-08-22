# Todo lo retirado, en orden cronológico. El tipo viaja en la línea; al
# pasado se le pregunta por fecha. Lo escribe el script.

2026-08-06  [M-097][standards][testing] 📌 unmassk-standards gained Producer-Consumer round-trip integrity (§34)  →  closed: reclasificada como decision (era una eleccion entre alternativas, no un hecho estable) -- ver D-004
2026-08-06  [M-100][memory][hooks] 📌 the near-dup write-path gate stays lexical and non-blocking, on purpose  →  closed: reclasificada como decision -- ver la nota nueva
2026-08-06  [M-101][memory][release] 📌 code commits: local WIPs per sub-step, single squash and push at close  →  closed: reclasificada como decision
2026-08-06  [M-102][boot][memory] 📌 boot hook output is always a minimal banner, full content lives only in the file  →  closed: reclasificada como decision
2026-08-06  [M-105][docs][architecture] 📌 important content is documented in three audiences at once  →  closed: reclasificada como decision
2026-08-06  [M-072][release][install] 📌 plugin marketplace distribution replaces manual git-clone install  →  closed: reclasificada como decision
2026-08-06  [M-076][memory][install] 📌 no confirmation before saving memos and decisions  →  closed: reclasificada como decision
2026-08-06  [M-078][skills][architecture] 📌 BM25 skill routing replaced the static CLAUDE.md skill-map  →  closed: reclasificada como decision
2026-08-06  [M-085][release][architecture] 📌 this marketplace repo works directly on main  →  closed: reclasificada como decision
2026-08-06  [M-087][memory][architecture] 📌 the memory system stays a hooks-based plugin, not an MCP  →  closed: reclasificada como decision
2026-08-06  [M-088][memory][hooks] 📌 subagent recall needs a PreToolUse/Task hook rewriting the prompt  →  closed: reclasificada como decision
2026-08-06  [M-089][testing][skills] 📌 two build modes: test-first for clear contracts, linear Flow for the rest  →  closed: reclasificada como decision
2026-08-06  [M-094][docs][architecture] 📌 public repo content: English code and UI, Spanish conversation  →  closed: reclasificada como decision
2026-08-06  [M-096][memory][architecture] 📌 vector search deferred as non-foundational, unlike the git decision graph  →  closed: reclasificada como decision
2026-08-06  [D-017][skills][architecture] 🧭 BM25 skill routing replaced the static CLAUDE.md skill-map  →  closed: el gate BM25 se deprecó de verdad en julio -- ver D-028, que lo sustituye
2026-08-06  [M-090][skills][architecture] 📌 Gitto existed as a dedicated git-ops subagent, later retired  →  closed: fecha y motivo exactos confirmados -- ver la nota nueva
2026-08-06  [Q-001][memory][hooks] ❓ can a hook launch a headless CLI session in the background, unverified  →  closed: hipotesis de una IA externa que el propietario nunca pidio; no se construye nada sobre ella
2026-08-09  [R-002][memory][install] ⚠️ branch claude/silly-cori holds 17 old-memory commits reachable nowhere else  →  closed: la fase 8 destilo el historial de todas las ramas, esos 17 commits ya estan en la memoria; Bex ordena borrar la rama
2026-08-09  [I-001][testing][ci] 🔥 Ubuntu CI flakiness on #61 was reopened, then closed for real  →  closed: cerrado de verdad el 25 de julio: la raiz era una carrera de git gc --auto durante un fork, arreglada con gc.auto=0 en conftest y confirmada con 3 corridas Ubuntu verdes seguidas sin rerun
2026-08-09  [I-002][memory][testing] 🔥 building v2 found three silent-loss bugs -- fixed, now regression tests  →  closed: los tres fallos de perdida silenciosa se arreglaron el 2 de agosto y los tres quedaron fijados como tests de regresion probados en rojo sin su arreglo: candado en los indices, titular con salto de linea, y --cleanup=verbatim
2026-08-09  [M-114][memory][hooks] 📌 zone memory search by filename replaces role-based push injection  →  replaced by M-115
2026-08-09  [B-001][memory][hooks] ⛔ message-level memory injection redesign is paused, awaiting Bex's new approach  →  closed: Bex lo descarta el 2026-08-09: ya no espera planteamiento ninguno, la inyeccion de memoria por mensaje no se reinstaura
2026-08-22  [D-043][memory][architecture] 🧭 the issue field opens to all seven types; asking moves to session close  →  replaced by D-044
