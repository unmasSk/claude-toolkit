# Yoda Memory — unmassk-toolkit

## Topic files
- [judgment-patterns.md](./judgment-patterns.md) — patrones de juicio aprendidos
- [conventions.md](./conventions.md) — convenciones del proyecto

## Session log
- 2026-06-09: Primera evaluación. Script de release (release.py + release_helpers.py + bump-version.py). Veredicto: READY. Ver judgment-patterns.md.
- 2026-07-05: Juicio final del pipeline de hardening del boot hook (14 rondas Cerberus/Argus, sin Moriarty separado). Reproduje en vivo 2 ataques críticos (symlink en settings.json, inyección de registro vía bytes de control en git log) y un mutation test. Veredicto: APPROVED WITH CONDITIONS. Ver judgment-patterns.md y conventions.md.
