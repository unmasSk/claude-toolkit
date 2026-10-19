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

- Fix round (Cerberus, 2026-10-18): every merge/pull in a chained command must be judged (`&&`, newline), `cd`/`pushd`/`git -C` before a merge = unknown target, and unknown target gets the HEAVY message, not the light one. `git merge X || git merge --abort` must not be exempted by the fallback; `feat/main` on main is not a sync (only a real remote prefix is).
- The hook's internal-failure branch cannot be forced from outside: run_git swallows every error and returns (1, ""). Report it UNVERIFIED rather than monkeypatching.

- D-129 round (2026-10-18): -C/cd to the SESSION repo (same toplevel, any spelling, subdir) reads the branch like no path; other repo / second worktree stay unknown. Heavy-gate cases were already green for the wrong reason (unknown), so assert the reason names the target ('staging') to make them red.

- D-129 fix pass: `pushd ../other && popd` never tests popd (pushd outside the session already fails closed); use bare `popd &&`. `cd <session> && git -C ../other` never tests the cd+-C join (cd = cwd); use `cd sub && git -C ..` (approve). Edits with Bash heredocs mentioning merges are blocked by the live hook — use Edit.

- Drill round (2026-10-18): the text backstop must only fire when tokenize() fails (then LIGHT message, assert "argus" absent); shlex punctuation_chars splits `2>&1` into `2`,`>&`,`1`, so a redirect reads as a separator; a bare `-F - <<EOF` body with an apostrophe makes shlex fail (the `$(cat <<'EOF')` inside double quotes does not). Redirect AFTER the merge on HEAD=dev was already green.

- I-007 (2026-10-19, 1.47.0 Windows CI red): any path interpolated into a command string must go through `_sh()` (`Path.as_posix()` + one-shell-word assert) -- the hook tokenizes like bash, which eats unquoted backslashes; block-expecting tests stay green on Windows for the wrong reason, so pair them with `_assert_names_target`. Git Bash `/c/...` gap: simulated on a Mac in `test_merge_gate_git_bash_drive_path.py` by swapping `merge_gate_target.os` for a proxy (name "nt", path=ntpath), `sys.platform="win32"`, a `run_git` double answering `rev-parse --show-toplevel` as git for Windows, and `toplevel.cache_clear()` around it. Never patch `os.name` globally (pathlib/shutil break).

**How to apply:** any later round on this hook — keep the third-branch fixture and the dev->staging switch test.
