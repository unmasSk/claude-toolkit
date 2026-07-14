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
"""

import os

from conftest import BIN_DIR, HOOKS_DIR, INSTALL, git_cmd, run_script

# ── Paths ────────────────────────────────────────────────────────────────

USER_PROMPT_HOOK = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")
BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")
COMMIT_SCRIPT = os.path.join(BIN_DIR, "git-memory-commit.py")

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
        assert "git-memory-recall.py" in out, (
            f"hook output must still contain the recall-pointer reminder "
            f"(now folded into the unconditional _BANNER, issue #69).\n"
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


# ── (c) bin/git-memory-commit.py ────────────────────────────────────────────


class TestGitMemoryCommitCp1252:
    """W1: _print_commit_result()'s pretty confirmation line embeds the
    type's emoji (📌 for memo) and crashes with UnicodeEncodeError AFTER the
    real `git commit` has already succeeded — the most dangerous shape of
    this bug, since it reports failure (RC=1) for a commit that actually
    landed, which could cause a caller to retry and double-commit, or a
    human to believe their memo was lost.
    """

    def test_simple_memo_commit_exits_zero(self, tmp_path):
        repo = _make_repo(tmp_path)

        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            extra_args=["memo", "general", "cp1252 encoding contract memo"],
            env=CP1252_ENV,
        )

        assert rc == 0, (
            f"git-memory-commit.py must exit 0 under cp1252 stdout.\n"
            f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
        )


# ── (d) hooks/session-start-boot.py ────────────────────────────────────────


class TestSessionStartBootCp1252:
    """RED, but not via a child crash like a/b/c — see module docstring
    scenario (d) for the full explanation. The child's only "special"
    stdout character on the normal path (em-dash, U+2014) IS representable
    in cp1252 (byte 0x97), so the child itself exits 0. What fails is the
    PARENT's decode: conftest.py's run_script()/run_cmd() decode captured
    stdout as UTF-8 (the W2 fix, correct for a FUTURE properly-UTF8 child),
    and byte 0x97 is not valid UTF-8 — raises UnicodeDecodeError INSIDE
    run_script() itself, before this test body ever gets a clean
    (rc, out, err) tuple to assert on. xfail still catches this correctly
    (pytest's xfail wraps the whole test body, not just assert statements).
    """

    def test_boot_exits_zero_and_writes_boot_log(self, tmp_path):
        repo = _make_repo(tmp_path, "boot_repo")
        rc, _, err = run_script(INSTALL, repo, ["--auto"])
        assert rc == 0, f"fixture setup: install --auto failed: {err}"
        # A couple of real memory commits so boot has real content to
        # render into the (file-only) heavy sections — not required for
        # this guard's assertions, but keeps the scenario representative
        # rather than a degenerate empty-history repo.
        git_cmd(["commit", "--allow-empty", "-m",
                 "🧭 decision(auth): use JWT\n\nDecision: JWT over sessions\nWhy: stateless API"], repo)
        git_cmd(["commit", "--allow-empty", "-m",
                 "📌 memo(api): preference - async/await\n\nMemo: preference - async/await everywhere"], repo)

        rc, out, err = run_script(BOOT_HOOK, repo, env=CP1252_ENV)

        assert rc == 0, (
            f"session-start-boot.py must exit 0 under cp1252 stdout.\n"
            f"--- stdout ---\n{out}\n--- stderr ---\n{err}"
        )
        boot_log_path = os.path.join(repo, ".claude", ".unmassk", "boot-log-latest.txt")
        assert os.path.isfile(boot_log_path), (
            f"boot-log-latest.txt must be written.\n--- stdout ---\n{out}"
        )
        with open(boot_log_path, encoding="utf-8") as f:
            content = f.read()
        assert content.strip(), "boot-log-latest.txt must not be empty"
