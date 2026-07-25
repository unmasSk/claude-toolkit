"""Shared fixtures and helpers for git-memory tests.

Nota sobre importabilidad de bin.release y módulos vecinos:
esto NO lo hace pytest (pytest no añade el rootdir a sys.path por su
cuenta). Cuando test_release.py se invoca como `python3 -m pytest ...`
desde la raíz del repo, es `python -m` quien inserta el cwd en
sys.path[0] -- ese cwd resulta ser la raíz, y como bin/ no tiene
__init__.py, Python lo trata como namespace package, permitiendo
"import bin.release" / "import bin.release_helpers" sin
sys.path.insert explícito. Esto se rompe con cualquier otra forma de
invocar pytest (cwd distinto, entry point `pytest` sin `-m`) -- ver
issue #50. Por eso test_release.py inserta _REPO_ROOT en sys.path de
forma explícita en vez de depender de este efecto colateral.
"""

import json
import os
import subprocess
import sys

import pytest

SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(SOURCE_ROOT, "bin")
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")

# Make lib/ importable for unit tests of shared modules
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
HOOKS_DIR = os.path.join(SOURCE_ROOT, "hooks")

# Hook / script paths (all in plugin source, not project root)
PRECOMPACT_SCRIPT = os.path.join(HOOKS_DIR, "precompact-snapshot.py")
PRE_HOOK = os.path.join(HOOKS_DIR, "pre-validate-commit-trailers.py")

DOCTOR = os.path.join(BIN_DIR, "git-memory-doctor.py")
GC = os.path.join(BIN_DIR, "git-memory-gc.py")
INSTALL = os.path.join(BIN_DIR, "git-memory-install.py")
REPAIR = os.path.join(BIN_DIR, "git-memory-repair.py")
UNINSTALL = os.path.join(BIN_DIR, "git-memory-uninstall.py")
UPGRADE = os.path.join(BIN_DIR, "git-memory-upgrade.py")
BOOTSTRAP = os.path.join(BIN_DIR, "git-memory-bootstrap.py")


# ── Helpers ────────────────────────────────────────────────────────────

# Deterministic git identity fallback (issue #50/#51). On a CI runner with
# no git identity configured anywhere (no ~/.gitconfig, no --system config
# -- e.g. GitHub Actions with `useConfigOnly = true`), every `git commit`
# spawned by these test helpers exits 128 -- and run_cmd/git_cmd return that
# rc to callers that routinely never check it (fixtures like tmp_repo just
# call git_cmd(...) for its side effect). The repo silently ends up with
# zero commits, and any test asserting on commit content fails downstream
# with no clue why. House confirmed root cause and reproduced with:
#   printf '[user]\n\tuseConfigOnly = true\n' > /tmp/fakegitconfig
#   GIT_CONFIG_GLOBAL=/tmp/fakegitconfig GIT_CONFIG_SYSTEM=/dev/null \
#       python3 -m pytest unmassk-toolkit/tests/test_boot_output.py -q
# Fix: inject a deterministic fallback identity into every subprocess
# spawned via run_cmd -- and therefore git_cmd/run_script, and therefore
# every test file that imports them from here -- centralized once, no
# per-test-file patch needed.
#
# Coexistence caveat (verified live, do not re-derive without checking):
# git's GIT_AUTHOR_NAME/EMAIL env vars ALWAYS win over `git config
# user.name/user.email`, regardless of Python-side dict merge order -- so
# injecting them unconditionally would silently override the many existing
# tests that deliberately set their own per-repo identity via
# `git_cmd(["config", "user.email"/"user.name", ...], repo)` (dozens of
# call sites across the suite, e.g. test_boot_output.py's
# _make_repo_no_install). _REPOS_WITH_EXPLICIT_GIT_IDENTITY tracks which
# repo paths have had identity set that way, so the fallback only ever
# applies where nothing else already provided one -- an explicit per-repo
# `git config` call always wins.
_DEFAULT_GIT_IDENTITY_ENV = {
    "GIT_AUTHOR_NAME": "unmassk-toolkit-tests",
    "GIT_AUTHOR_EMAIL": "tests@unmassk-toolkit.invalid",
    "GIT_COMMITTER_NAME": "unmassk-toolkit-tests",
    "GIT_COMMITTER_EMAIL": "tests@unmassk-toolkit.invalid",
}

_REPOS_WITH_EXPLICIT_GIT_IDENTITY = set()

# Issue #61 (reabierto) — House root cause, reproducido byte-a-byte:
# los fixtures que montan cientos de commits (test_consolidation_trigger.py,
# test_recall.py horizonte-510, test_drift.py 200 commits) disparan
# `git gc --auto` desde dentro de `git commit`/`git fetch` en masa. En
# Ubuntu CI, gc.autoDetach desacopla ese gc por fork() y corre en carrera
# con el object-DB bajo ext4 + I/O paralelo del runner — perdiendo
# ocasionalmente un objeto commit PADRE todavía alcanzable. El daño queda
# en disco: un `git log --all --grep=...` posterior (recall/consolidación)
# tropieza con el padre ausente y muere rc=128 ("Could not read <sha>" /
# "Failed to traverse parents of commit <sha>"), lo que los reintentos del
# wrapper no pueden recuperar porque leen el mismo repo ya roto. No
# reproduce en Windows (no puede fork gc) ni en macOS local (no repackea a
# mitad del loop) — solo Ubuntu-CI. commit-graph fue descartado como causa.
#
# Fix: desactivar TODO mantenimiento implícito del object-store en cada
# subprocess git de la suite, inyectado UNA sola vez aquí (mismo patrón de
# capa-de-menor-precedencia que _DEFAULT_GIT_IDENTITY_ENV arriba) via
# GIT_CONFIG_COUNT/GIT_CONFIG_KEY_n/GIT_CONFIG_VALUE_n — esto vale como
# "config de máxima prioridad" para git (por encima de cualquier
# git config local/global/system) sin tener que parchear cada `git init`
# individual de cada fixture. gc.auto=0 mata el trigger tanto de `git
# commit` como de `git fetch`; gc.autoDetach=false y maintenance.auto=false
# son defensa en profundidad (si algo SÍ dispara un gc, que corra en
# foreground y no via cron/maintenance, nunca en background por fork).
_GC_DISABLE_ENV = {
    "GIT_CONFIG_COUNT": "3",
    "GIT_CONFIG_KEY_0": "gc.auto",
    "GIT_CONFIG_VALUE_0": "0",
    "GIT_CONFIG_KEY_1": "gc.autoDetach",
    "GIT_CONFIG_VALUE_1": "false",
    "GIT_CONFIG_KEY_2": "maintenance.auto",
    "GIT_CONFIG_VALUE_2": "false",
}


def _sets_git_identity(args):
    """True if args is a `git config user.name|user.email <value>` call --
    the exact shape every existing test helper already uses to set
    per-repo identity on purpose (git_cmd always prepends "git", so args[0]
    is reliably "git" by the time run_cmd sees it for any git_cmd caller)."""
    return (
        len(args) >= 4
        and args[0] == "git"
        and args[1] == "config"
        and args[2] in ("user.name", "user.email")
    )


def run_cmd(args, cwd, timeout=30, env=None, input_text=None):
    """Run a command and return (returncode, stdout, stderr)."""
    repo_key = os.path.realpath(cwd)
    if _sets_git_identity(args):
        _REPOS_WITH_EXPLICIT_GIT_IDENTITY.add(repo_key)
        identity_defaults = {}
    elif repo_key in _REPOS_WITH_EXPLICIT_GIT_IDENTITY:
        identity_defaults = {}
    else:
        identity_defaults = _DEFAULT_GIT_IDENTITY_ENV
    merged = {**identity_defaults, **_GC_DISABLE_ENV, **os.environ, **(env or {})}
    # W2 (issue #52, House round 2): text=True without an explicit encoding=
    # makes subprocess.run decode the child's stdout/stderr bytes using
    # locale.getpreferredencoding(False) -- on Windows that's the console's
    # ANSI codepage (e.g. cp1252), not UTF-8. Once Ultron's #52 fix forces
    # every entry point to emit UTF-8 on stdout/stderr (W1), the PARENT side
    # here still needs to decode those UTF-8 bytes as UTF-8 explicitly, or
    # any non-cp1252 byte sequence (emoji, arrows) raises UnicodeDecodeError
    # in the test process itself -- confirmed as the root cause of 16
    # decode failures on the Windows CI run. Pin it explicitly so this
    # helper's behavior doesn't depend on the host's locale.
    # errors="replace" (test-only regression from commit 72805bc's encoding
    # sweep, House root cause): the CHILD (git, or any bin/hooks script run
    # via run_script()) still emits bytes in the OS locale codepage when
    # PYTHONUTF8 isn't set (e.g. a Windows CI runner), not guaranteed UTF-8.
    # A strict utf-8 decode dies inside subprocess's _readerthread on the
    # first non-ASCII byte, leaving stdout/stderr as None -- surfacing as a
    # TypeError wherever a caller concatenates them. errors="replace" keeps
    # the decode alive (U+FFFD substitution) so every caller of
    # run_cmd/git_cmd/run_script always gets a real string.
    result = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=cwd, timeout=timeout, env=merged, input=input_text,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_cmd(args, cwd, env=None):
    """Run a git command. args can be a list or a space-separated string."""
    if isinstance(args, str):
        args = args.split()
    return run_cmd(["git"] + args, cwd, env=env)


def assert_repo_integrity(repo, context=""):
    """Fail loud, with a clear message, if `repo`'s object database is
    corrupt (a missing/unreachable-but-referenced object).

    Issue #61 (reabierto) — probe requested by House alongside the
    gc.auto=0 fix above. `_GC_DISABLE_ENV` should prevent the root-caused
    `git gc --auto` fork race from ever corrupting a fixture repo again,
    but IF it reappears (a different gc trigger, a git version without
    full GIT_CONFIG_COUNT honoring, etc.), the previous failure mode was a
    silent, opaque one: `git log --grep=...` swallows the `Could not read
    <sha>` / `Failed to traverse parents` error via each caller's own
    fail-safe design (`_scan_commits()` -> `[]`,
    `commits_since_last_consolidation()` -> 0/sentinel), so the eventual
    test failure looked like "CONSOLIDATE: ausente" / "entry not found" —
    a scan-logic bug, not a fixture-integrity bug. Call this right after
    building a massive-commit-loop fixture (and BEFORE the test's main
    assertion) so a reappearing corruption fails as an explicit, readable
    fixture error instead of that opaque downstream symptom.

    `context` is prepended to the failure message (e.g. the test's own
    name / which fixture stage) to make it obvious which build step this
    check followed.
    """
    rc, out, err = git_cmd(["fsck", "--connectivity-only"], repo)
    assert rc == 0, (
        f"fixture corrupto (objeto ausente) — git fsck --connectivity-only "
        f"exited {rc} (expected 0){': ' + context if context else ''}.\n"
        f"--- stdout ---\n{out}\n"
        f"--- stderr ---\n{err}"
    )


def write_file(repo, path, content):
    """Write a file inside a repo directory."""
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def run_script(script_path, cwd, extra_args=None, timeout=30, env=None, input_text=None):
    """Run a Python script. Returns (returncode, stdout, stderr)."""
    args = [sys.executable, script_path] + (extra_args or [])
    return run_cmd(args, cwd, timeout=timeout, env=env, input_text=input_text)


def run_doctor_json(cwd):
    """Run doctor --json and return (parsed_dict, returncode).

    Issue #52 (House): stderr used to be silently discarded here. If
    doctor.py crashes before it can print valid JSON (e.g. an
    encoding-related UnicodeEncodeError), every caller previously only saw
    {"status": "error", "checks": []} with zero trace of why. The "_debug"
    key below carries rc/stdout/stderr for exactly that case -- it doesn't
    change the shape any existing caller already relies on (nothing reads
    "_debug" today), so a test that wants a better failure message can
    assert on result.get("_debug") without every other caller needing to
    change.
    """
    rc, out, err = run_script(DOCTOR, cwd, ["--json"])
    try:
        return json.loads(out), rc
    except json.JSONDecodeError:
        return {
            "status": "error", "checks": [],
            "_debug": f"doctor.py --json rc={rc} stdout={out!r} stderr={err!r}",
        }, rc


def neutralize_needs_upgrade_check1(repo):
    """Normalize CLAUDE.md's managed blocks to their real canonical render so
    lib/upgrade_check.py::needs_upgrade()'s Check 1
    (managed_blocks.any_block_outdated(content)) is definitively False,
    isolating whatever the caller actually wants to exercise (Check 2
    semver, or — see BUG M / SEC-T1-002 — the manifest-read symlink guards).

    Decision 1d623da / Moriarty T1-B (issue #63): Check 1 used to require
    the literal string "Context Checkpoint Commits" inside the block — a
    string that never existed in real production content (only test
    fixtures faked it), so this helper used to hand-inject it. Check 1 now
    reuses managed_blocks.any_block_outdated(), the same real canonical-body
    comparison the P1 v2 crew content gate trusts. Hand-injecting that
    unrelated literal today would make the block's body diverge FROM
    canonical and trip Check 1 the opposite way (True instead of False) —
    confirmed live: a fresh --auto install is already canonical
    (any_block_outdated() == False out of the box), and appending the old
    literal broke that. Per unmassk-standards §34 (no fabricated ground
    truth in producer/consumer checks), the neutralized state must be
    derived from the SAME render production code trusts, not a second
    hand-typed string: this runs the real managed_blocks.upsert_managed_blocks()
    over CLAUDE.md's current content, which rewrites every block to its
    byte-for-byte canonical body. Idempotent — a no-op on an already
    canonical (e.g. freshly installed) repo; fixes a tampered/legacy block
    on any other repo state.

    No-op (returns silently) if CLAUDE.md is missing entirely — callers
    that rely on this should have already installed.
    """
    claude_md_path = os.path.join(repo, "CLAUDE.md")
    if not os.path.isfile(claude_md_path):
        return
    with open(claude_md_path, encoding="utf-8") as f:
        content = f.read()

    import managed_blocks  # LIB_DIR already on sys.path (see top of file)

    new_content, _log = managed_blocks.upsert_managed_blocks(content)

    with open(claude_md_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def check_hook_msg(subject, cwd, trailers=None, as_claude=False):
    """Send a commit message to the pre-hook and return the exit code."""
    command = 'git commit -m "' + subject + '"'
    if trailers:
        command = command + ' -m "' + trailers + '"'
    payload = {"tool_input": {"command": command}}
    env = {}
    if as_claude:
        env["CLAUDE_CODE"] = "1"
    rc, _, _ = run_script(PRE_HOOK, cwd, env=env, input_text=json.dumps(payload))
    return rc


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repo with an initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


@pytest.fixture
def real_symlink_capable(tmp_path):
    """Skip the test using this fixture if the CURRENT environment cannot
    create real filesystem symlinks.

    Confirmed live on Windows dev boxes without Developer Mode /
    SeCreateSymbolicLinkPrivilege:
        os.symlink(...) -> OSError: [WinError 1314] El cliente no dispone
        de un privilegio requerido.

    The POSIX/anti-symlink guards under test rely on real filesystem
    symlink semantics (O_NOFOLLOW, os.path.islink(), directory-symlink
    traversal) that cannot be meaningfully mocked — mocking os.path.islink()
    would only prove the mock works, not that the guard itself still
    functions. A real symlink is the only honest way to test it, so when one
    cannot be created here, this reports an explicit skip rather than faking
    the result.

    Shared by test_crossplatform_symlink_guard.py and
    test_boot_freshness_hardening.py — single source of truth, auto-discovered
    via conftest.py (no import needed).
    """
    probe_target = tmp_path / "_symlink_probe_target.txt"
    probe_link = tmp_path / "_symlink_probe_link.txt"
    probe_target.write_text("probe", encoding='utf-8')
    try:
        os.symlink(str(probe_target), str(probe_link))
    except OSError as e:
        pytest.skip(f"cannot create real symlinks in this environment: {e}")
    else:
        os.remove(str(probe_link))


@pytest.fixture
def real_hardlink_capable(tmp_path):
    """Skip the test using this fixture if the CURRENT environment cannot
    create real filesystem hard links.

    Unlike os.symlink() (which needs Developer Mode /
    SeCreateSymbolicLinkPrivilege on Windows), os.link() works on
    NTFS/ext4/APFS without any special privilege on every OS this project
    targets -- confirmed live on this Windows dev box (2026-07-09, issue
    #53). Still guarded explicitly rather than assumed universally
    available, because some CI/container filesystems (network mounts,
    certain overlay/tmpfs configurations) reject hard-link creation across
    mount boundaries or entirely. st_nlink > 1 is the ONLY signal a
    reject_hardlinks=True guard can act on, so a test that cannot create a
    real multi-link file cannot meaningfully exercise that guard -- skip
    explicitly rather than faking the result.

    Shared by any test file exercising reject_hardlinks (issue #53,
    design decision 51a3c44) -- single source of truth, auto-discovered
    via conftest.py (no import needed), same pattern as
    real_symlink_capable above.
    """
    probe_target = tmp_path / "_hardlink_probe_target.txt"
    probe_link = tmp_path / "_hardlink_probe_link.txt"
    probe_target.write_text("probe", encoding='utf-8')
    try:
        os.link(str(probe_target), str(probe_link))
    except OSError as e:
        pytest.skip(f"cannot create real hard links in this environment: {e}")
    else:
        os.remove(str(probe_link))


@pytest.fixture
def installed_repo(tmp_path):
    """Create a temporary git repo with git-memory installed."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])
    return repo
