---
name: pre-merge-gate-target-branch-contract-notes
description: pre-merge-gate.py D-119/D-120 target-branch contract — HEAD-vs-switched-target trap and wrong-reason greens
metadata:
  type: project
---

D-119/D-120 (#101, 2026-10-18): merge/pull INTO dev = no gate; target above dev (staging/main/master/production) = heavy gate (Cerberus+Argus on whole diff, Alexandria CHANGELOG+version, Bex's yes, suite left to CI).

- The TARGET is the branch receiving the merge: HEAD, or the branch a leading `git switch/checkout X &&` moves to. A hook reading only HEAD gets it wrong both ways.
- Pre-existing hole (EXECUTED 2026-10-18): on `dev`, `git switch staging && git merge dev` was APPROVED — the same-branch exemption compares the merge arg `dev` with HEAD `dev`. Always test "HEAD is dev but the command lands elsewhere".
- Wrong-reason green trap: starting on feat/x and pulling `origin feat/x` after `git switch dev` passes via same-branch sync. Start switch-first tests on a third branch.
- The live hook blocks any Bash text containing "git merge" — even a heredoc writing a memory note. Write such files with the Write tool.
- Open owner question at contract time: same-branch sync on main (`git pull origin main` on main) is approved today but D-120 literally says target main = block.

**How to apply:** any later round on this hook — keep the third-branch fixture and the dev->staging switch test.
