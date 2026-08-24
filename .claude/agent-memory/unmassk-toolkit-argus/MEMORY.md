# Memory Index — unmassk-toolkit (Argus)

- [patterns.md](patterns.md) — no-external-attacker model is load-bearing here; git_helpers.py is already hardened; git arg convention uses literal `--`; `file_lock()` is the established fix for cross-process races (18 sites) — new modules that skip it are a real regression; `verify_path_within_project` guards containment, not sub-path pinning
