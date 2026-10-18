---
name: moria-repos-map
description: which on-disk Moria repo holds what (names differ by one letter); where its memory code lives
metadata:
  type: reference
---
Read 2026-10-18 (read-only):
- `~/Workspace/m0ria-v3` (zero) = 3 commits, only MORIA_SPEC.md v2.0 (Arctic-Embed, Qdrant, FalkorDB, never built).
- `~/Workspace/moria-v3` (letter o) = 1,454 commits, real code. Memory: `moria/memory/embeddings.py` (fastembed Qwen3-0.6B uint8, 1024d), `search_index.py`+`search_index_db.py` (sqlite-vec vec0 int8 cosine, brute-force scan), `retrieval.py:retrieve` (FTS5 + vectors, no rerank), injected at end of the letter by `assembler.py`.
- Measurements: `data/embeddings-trial/resultados.md` (114 docs, 20 queries only).
- The "lost two months" story is in `CLAUDE.md` "Lo que pasó" and `docs/plan/auditoria-2026-10-07/audit-prd.md`.
