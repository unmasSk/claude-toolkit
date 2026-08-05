"""
Encoding contract (issue #52, T1) — acceptance-granularity, test-first pass.

House (round 2, CI run 28897259775) root-caused the Windows CI failures to
W1: no entry point under unmassk-toolkit/bin/*.py or hooks/*.py forces UTF-8
on stdout/stderr. Under a Windows console using a legacy codepage (e.g.
cp1252, the default for many non-English Windows locales), any print() of
an emoji/arrow (→ ↑ 🧭📌 ...) raises UnicodeEncodeError and the process
exits 1. This is reproducible on ANY OS (macOS/Linux/Windows) via
PYTHONIOENCODING=cp1252 — no real Windows box needed, confirmed here on
macOS.

These are ACCEPTANCE tests at BEHAVIOR granularity — the four scenarios
House named — NOT the exhaustive branch/error-path suite. That hardening
pass belongs after Ultron implements the real fix (force UTF-8 on
stdout/stderr at every entry point). Build mode: test-first contract pass —
no production code is touched by this file.

Manual RED verification BEFORE writing these as pytest tests (reproduced
live against production code as it stands today):
  a. hooks/user-prompt-memory-check.py, installed+booted repo, valid stdin
     JSON, PYTHONIOENCODING=cp1252 → UnicodeEncodeError on the arrow (→) in
     the memory-check reminder line, RC=1.
  b. bin/git-memory-install.py --auto, PYTHONIOENCODING=cp1252 → crashes on
     the "─" * 40 divider before Phase 3 even runs; RC=1; NEITHER CLAUDE.md
     NOR .claude/.unmassk/manifest.json get created.
  c. bin/git-memory-commit.py memo <scope> <msg>, PYTHONIOENCODING=cp1252 →
     the `git commit` itself SUCCEEDS (the commit lands in git log), then
     _print_commit_result()'s pretty confirmation line (contains the memo
     emoji 📌) crashes with UnicodeEncodeError — RC=1 despite the commit
     having actually happened. This is the most dangerous of the three:
     silent success reported as failure.
  d. hooks/session-start-boot.py, PYTHONIOENCODING=cp1252 → the CHILD does
     NOT crash (RC=0 if you only watch its exit code) — the only "special"
     character on the normal-path stdout banner is an em-dash (—, U+2014),
     which happens to already be encodable in cp1252 (byte 0x97), so
     print() in the child never raises. BUT this is still RED end-to-end,
     for a subtler reason (W2's exact shape): the child writes that em-dash
     as ONE cp1252 byte (0x97), and any PARENT that decodes the child's
     captured stdout as UTF-8 (conftest.py's run_cmd, fixed for W2 in this
     same pass) hits `UnicodeDecodeError: 'utf-8' codec can't decode byte
     0x97 in position ... invalid start byte` INSIDE run_script() itself —
     confirmed live with a plain subprocess.run(..., encoding="utf-8")
     script reproducing byte-for-byte what conftest.py's run_cmd does. A
     naive manual check that only pipes the child's raw bytes to a terminal
     (no decode step) misses this — the terminal doesn't need to decode
     anything to display mojibake, but a UTF-8-decoding parent does, and
     that parent-side decode is exactly what breaks. So (d) joins a/b/c in
     the RED/xfail set, not a separate GREEN guard as initially assumed.

Closed (2026-07-07): Ultron implemented the UTF-8 guard (lib/encoding_guard.py
+ 23 entry points, commit 38f5728). All four scenarios confirmed green —
xfail(strict=False) markers removed, these are now plain regression tests
protecting the fix.

[corregido 2026-08-05: scenarios (c) bin/git-memory-commit.py and
(d) hooks/session-start-boot.py were retired along with those two files
(deleted outright with the rest of the v1 memory system). Their test
classes (TestGitMemoryCommitCp1252, TestSessionStartBootCp1252) are gone —
see the retirement note where they used to live, below. Scenarios (a) and
(b) are unaffected and still green.]
"""

import os

from conftest import HOOKS_DIR, INSTALL, git_cmd, run_script

# ── Paths ────────────────────────────────────────────────────────────────

USER_PROMPT_HOOK = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")

# The exact env that reproduces the bug on ANY platform — a legacy Windows
# codepage where most emoji/arrows have no mapping. Passed as the `env=`
# kwarg to run_script/run_cmd, which conftest.py's run_cmd merges with the
# HIGHEST precedence (after os.environ), so only the single subprocess call
# under test runs under cp1252 — repo setup (git init/config/commit, the
# INSTALL call used to build an installed+booted fixture) still runs under
# the real host encoding.
CP1252_ENV = {"PYTHONIOENCODING": "cp1252"}


def _make_repo(tmp_path, name="repo"):
    """Bare git repo, real identity, one commit. No install."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _make_installed_booted_repo(tmp_path, name="repo"):
    """Repo with git-memory installed AND the first-boot flag already set.

    Needed for scenario (a): user-prompt-memory-check.py only reaches the
    arrow-containing "[memory-check]" reminder line (append at the tail of
    main()) once needs_install()/needs_upgrade() are both False — a bare
    repo short-circuits at needs_install() and never reaches that code path.
    Setup runs under the normal host encoding (no cp1252) — only the
    INVOCATION UNDER TEST gets the cp1252 env, via the env= kwarg passed by
    the caller.
    """
    repo = _make_repo(tmp_path, name)
    rc, _, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"fixture setup: install --auto failed: {err}"
    booted_flag = os.path.join(repo, ".claude", ".unmassk", ".session-booted")
    os.makedirs(os.path.dirname(booted_flag), exist_ok=True)
    open(booted_flag, "w", encoding="utf-8").close()
    return repo


# ── (a) hooks/user-prompt-memory-check.py ──────────────────────────────────


class TestUserPromptMemoryCheckCp1252:
    """W1: main()'s final print("\\n".join(lines)) always includes the
    "[memory-check] ... → do nothing. Silence beats noise." reminder line,
    which contains a raw U+2192 (→) not encodable in cp1252 — crashes with
    UnicodeEncodeError, RC=1, on every single invocation of this hook in an
    installed+booted repo (i.e. every real user message after the first).
    """

    def test_valid_stdin_json_exits_zero_with_useful_output(self, tmp_path):
        repo = _make_installed_booted_repo(tmp_path)

        rc, out, err = run_script(
            USER_PROMPT_HOOK, repo,
            input_text='{"prompt": "hola, sigamos con el trabajo de hoy"}',
            env=CP1252_ENV,
        )

        assert rc == 0, (
            f"hook must exit 0 under cp1252 stdout (never blocks user input).\n"
            f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
        )
        # 2026-08-04: the old assertion here checked for the literal string
        # "git-memory-recall.py" — a v1-system script deleted at the start
        # of this branch (feat/memoria-v2), so the string can never appear
        # again. Do NOT restore it — it wasn't lost by accident, it's stale.
        # Replaced with a structural check of the SAME real invariant this
        # test class exists to protect (encoding, not content): the owner
        # decided 2026-08-04 that this hook must always print something,
        # even "nothing to report", so a silent hook is provably not a
        # working one (see hook's own comment, main(), just above the
        # fallback line). Tied to the bracket-label convention every line
        # in this hook follows ([git-memory-boot], [git-memory],
        # [skill-router], [memory-check], ...) rather than to literal
        # banner wording, so a future rewrite of the banner text doesn't
        # flip this test red for no reason.
        stripped = out.strip()
        assert stripped, (
            f"hook must still emit non-empty output when run under cp1252 "
            f"stdout encoding — a crash or a swallowed exception could "
            f"silently produce empty output even with rc == 0.\n"
            f"--- stdout ---\n{out}"
        )
        assert stripped.startswith("["), (
            f"hook output must follow the bracket-label convention "
            f"(e.g. '[memory-check] ...') even under cp1252 — structural "
            f"check, not literal banner text.\n"
            f"--- stdout ---\n{out}"
        )


# ── (b) bin/git-memory-install.py --auto ───────────────────────────────────


class TestGitMemoryInstallAutoCp1252:
    """W1: main()'s plan-summary divider (print("\\u2500" * 40), a literal
    box-drawing "─" repeated) is not encodable in cp1252 and crashes before
    Phase 3 (apply) ever runs — RC=1, and NEITHER CLAUDE.md nor
    .claude/.unmassk/manifest.json get created. A user on a non-English
    Windows locale cannot install git-memory at all.
    """

    def test_install_auto_exits_zero_and_creates_claude_md_and_manifest(self, tmp_path):
        repo = _make_repo(tmp_path)

        rc, out, err = run_script(INSTALL, repo, ["--auto"], env=CP1252_ENV)

        assert rc == 0, (
            f"install --auto must exit 0 under cp1252 stdout.\n"
            f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
        )
        claude_md = os.path.join(repo, "CLAUDE.md")
        manifest = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        assert os.path.isfile(claude_md), "CLAUDE.md must be created"
        assert os.path.isfile(manifest), ".claude/.unmassk/manifest.json must be created"


# RETIRADO (memoria v2, 2026-08-05): TestGitMemoryCommitCp1252 (escenario c,
# bin/git-memory-commit.py) y TestSessionStartBootCp1252 (escenario d,
# hooks/session-start-boot.py) probaban al 100% dos ficheros ya borrados del
# sistema v1 (confirmado: ambos ficheros no existen en disco). Las otras dos
# clases de este fichero (TestUserPromptMemoryCheckCp1252,
# TestGitMemoryInstallAutoCp1252) siguen probando hooks/user-prompt-memory-
# check.py y bin/git-memory-install.py, ambos vivos — 2/2 verde, confirmado
# ejecutando el fichero. No hay objetivo vivo equivalente al que redirigir
# los dos casos retirados (git-memory-commit.py y session-start-boot.py no
# tienen sucesor 1:1 en v2 con el mismo defecto de encoding conocido).
