#!/usr/bin/env python3
"""
SessionStart hook for unmassk-toolkit crew.
Ensures all 5 managed blocks exist in CLAUDE.md.
"""
import subprocess
import sys
from pathlib import Path

# Make lib/ importable when running from the plugin cache
import os
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402
force_utf8_streams()

from managed_blocks import upsert_managed_blocks  # noqa: E402
from git_helpers import claude_md_lock_path, file_lock, open_no_follow_symlink, run_git  # noqa: E402

# The except below reports EVERY OSError as "CLAUDE.md is a symlink" — a
# read-only mount or a failed lock acquisition gets the same wrong,
# unactionable line, and the managed blocks silently never get written.
# The real exception now goes to the incident channel; the printed line is
# left exactly as it was so no existing behavior changes.
try:
    from incidents import report_incident  # noqa: E402
except Exception:  # fail-open: no incident channel is not a reason to fail the boot
    report_incident = None  # type: ignore[assignment]


def find_git_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def _read_claude_md(claude_md):
    """Read CLAUDE.md if it exists.

    Returns (content, exists). (None, None) signals "refuse to follow a
    symlink / undecodable content" -- caller must treat that as a skip, not
    a normal empty-file read.
    """
    if not claude_md.exists():
        return "", False
    try:
        # barrido finding: never follow a symlink planted at CLAUDE.md —
        # same bug class as BUG K (install.py/uninstall.py), a separate
        # call site found via the barrido sweep. open_no_follow_symlink()
        # takes a path-like object fine (os.open() accepts Path via
        # os.fspath()), so we read/write via the file handle instead of
        # pathlib.Path's read_text()/write_text().
        with open_no_follow_symlink(claude_md, "r", encoding="utf-8") as f:
            return f.read(), True
    except (OSError, UnicodeDecodeError):
        return None, None


def _print_plugin_sync_check(git_root: Path) -> None:
    """PLUGIN: repo-vs-installed-cache drift (P7, session-start-boot.py's
    old job, lib/cache_sync_check.py::count_repo_cache_drift()).

    Claude Code runs the plugin from the installed cache, never from this
    working tree -- an edit here changes nothing at runtime until the
    plugin is reinstalled. Always prints one line: a real drift count, an
    explicit zero, or an explicit "not verifiable" -- never silence, so a
    stale cache can't go unnoticed the way it did for 3 days before this
    check existed. Any failure (import or comparison) degrades the same
    way as the rest of this hook: a printed line, never a raised exception.
    """
    try:
        from cache_sync_check import count_repo_cache_drift
        summary = count_repo_cache_drift(str(git_root))
    except Exception as e:
        print(f"[crew] PLUGIN: no verificable ({type(e).__name__})")
        return
    if summary is None:
        print("[crew] PLUGIN: no verificable (sin repo fuente junto a la cache)")
        return
    count, _descriptions = summary
    if count == 0:
        print("[crew] PLUGIN: sincronizado (0 ficheros)")
    else:
        print(
            f"[crew] PLUGIN: {count} ficheros desincronizados (repo vs cache) "
            "-> publica version y ejecuta 'claude plugin update'"
        )


def _print_upgrade_check(git_root: Path) -> None:
    """UPGRADE: auto-upgrade the installed manifest when it's behind (P2,
    session-start-boot.py's old job, lib/upgrade_check.py).

    needs_upgrade() is checked first (read-only) purely so this can always
    print a line -- trigger_auto_upgrade_if_needed() itself is silent on
    the "nothing to do" case and only ever speaks (to stderr) on failure.
    Both calls already fail-open internally; wrapped again here so an
    import failure alone can't skip the printed line either.
    """
    # El manifest AUSENTE se dice aparte, y no es un detalle
    # [2026-08-05, medido en un proyecto nuevo sin instalar nunca]: hasta
    # esta linea, `needs_upgrade()` devolvia False tanto para "estas al
    # dia" como para "no hay manifest del que estar al dia" -- su
    # fail-safe documentado, para no entrar en bucle de instalacion. El
    # efecto era que el arranque de un proyecto SIN INSTALAR imprimia
    # "manifest al dia", que es literalmente lo contrario de lo que pasa,
    # y encima en el primer mensaje que ve el usuario. Un proyecto puede
    # quedarse asi para siempre: nada dispara el instalador solo.
    try:
        from upgrade_check import needs_upgrade, trigger_auto_upgrade_if_needed
        manifest = git_root / ".claude" / ".unmassk" / "manifest.json"
        installed = manifest.is_file()
        pending = needs_upgrade(str(git_root))
    except Exception as e:
        print(f"[crew] UPGRADE: no verificable ({type(e).__name__})")
        return
    if not installed:
        print(
            "[crew] UPGRADE: este proyecto NO tiene el toolkit instalado "
            "(falta .claude/.unmassk/manifest.json)"
        )
        return
    if not pending:
        print("[crew] UPGRADE: manifest al dia, no hace falta actualizar")
        return
    try:
        trigger_auto_upgrade_if_needed(str(git_root))
    except Exception as e:
        print(f"[crew] UPGRADE: fallo al disparar la actualizacion ({type(e).__name__})")
        return
    print("[crew] UPGRADE: disparada (el manifest instalado iba por detras)")


def _print_repo_status_check(git_root: Path) -> None:
    """REPO: working-tree status (P3, session-start-boot.py's old job).

    No equivalent survives in the new hook set (docs/memoria-v2 owns only
    memory concerns), so this reimplements the one-line summary directly
    on top of `git status --porcelain`, bounded to a 5s timeout so a stuck
    git process can never hang the session start.
    """
    try:
        code, output = run_git(["status", "--porcelain"], cwd=str(git_root), timeout=5)
    except Exception as e:
        print(f"[crew] REPO: estado no verificable ({type(e).__name__})")
        return
    if code != 0:
        print("[crew] REPO: estado no verificable (git status fallo)")
        return
    changed = output.strip().splitlines()
    if not changed:
        print("[crew] REPO: working tree limpio, sin cambios sin guardar")
    else:
        print(f"[crew] REPO: {len(changed)} ficheros con cambios sin guardar")


def main():
    git_root = find_git_root()
    if not git_root:
        print("[crew] Not a git repo, skipping CLAUDE.md check")
        return

    # Issue: session-start-boot.py's SessionStart hook was unplugged when
    # the memory v2 hooks replaced it, silently taking 3 non-memory checks
    # with it. Their home is this hook (the toolkit's own SessionStart
    # entry point), never lib/memory/ -- that tree has a declared,
    # zero-toolkit-imports boundary (docs/memoria-v2/PIEZAS.md #13). Each
    # is self-contained and always prints, success or failure -- see each
    # function's own docstring.
    #
    # They run AFTER the managed-block cycle, and the `finally` is what
    # keeps them unconditional across its several early returns. Running
    # them first was tried and is WRONG, caught in the act by
    # test_issue63_t1_end_marker_and_magic_string.py: _print_upgrade_check()
    # calls trigger_auto_upgrade_if_needed(), which runs the real installer,
    # which itself rewrites CLAUDE.md's managed blocks. A block whose END
    # marker had been deleted was therefore already repaired by the time
    # the cycle below read the file, so the hook printed "All managed
    # blocks up to date" over damage it never saw. That is precisely the
    # failure this project declares as its only threat -- a green light
    # covering a repair nobody reported.
    try:
        _managed_blocks_cycle(git_root)
    finally:
        _print_plugin_sync_check(git_root)
        _print_upgrade_check(git_root)
        _print_repo_status_check(git_root)


def _managed_blocks_cycle(git_root: Path) -> None:
    # Issue #63 (boot simplification, P1 v2 -- decision 2d56444): the gate
    # verifies CONTENT, never manifest.json's "version" field. That field is
    # only a proxy for "an install ran", not "CLAUDE.md's managed blocks are
    # correct right now" -- Moriarty broke the version-only gate with 3 live
    # T1 PoCs (producer stamps version even when the CLAUDE.md write failed;
    # a poisoned block sits untouched next to a version-matching manifest;
    # CLAUDE.md deleted while a matching manifest survives is never
    # recreated). CLAUDE.md is therefore ALWAYS read (existence check comes
    # first, below) and always diffed against the canonical blocks via
    # upsert_managed_blocks(); reading+diffing is cheap and always happens.
    # The only thing ever skipped is the WRITE, and only when the diff is
    # empty (new_content == content) -- Bex's "write the minimum" goal,
    # preserved without trusting any external proxy for content state.
    claude_md = git_root / "CLAUDE.md"

    # T1-1 (Cerberus/Moriarty regression): a cheap, LOCK-FREE check first.
    # file_lock() below creates/opens a file under .claude/.unmassk/, which
    # can fail on a read-only mount -- a repo whose managed blocks are
    # already canonical must stay a pure no-op READ and never attempt that
    # acquisition just to discover there was nothing to write. Only
    # escalate to the locked read-modify-write cycle when this cheap check
    # finds an actual write is needed.
    content, claude_md_exists = _read_claude_md(claude_md)
    if content is None:
        print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping")
        return

    new_content, log = upsert_managed_blocks(content)
    if claude_md_exists and new_content == content:
        print("[crew] All managed blocks up to date")
        return

    # A write looks needed -- acquire the lock (issue: lost-update race,
    # memo eae0880) and RE-CHECK under it: another writer may have already
    # applied this exact update between the cheap check above and getting
    # the lock here. The lock must span the ENTIRE read -> upsert -> write
    # cycle, not just the write, so a concurrent writer always sees this
    # cycle's committed result before starting its own. claude_md_lock_path()
    # (Cerberus anti-pollution finding): all 3 CLAUDE.md writers in this
    # codebase must pass the exact same lock path so they genuinely
    # serialize against each other, and it lives under .claude/.unmassk/
    # (already gitignored) instead of next to CLAUDE.md itself. A failure
    # here (lock acquisition OR the write itself -- e.g. a read-only
    # directory) degrades the same way an unwriteable CLAUDE.md always has:
    # warn and return, never crash the boot.
    try:
        lock_path = claude_md_lock_path(str(git_root))
        with file_lock(str(claude_md), lock_path=lock_path):
            content, claude_md_exists = _read_claude_md(claude_md)
            if content is None:
                print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping")
                return

            new_content, log = upsert_managed_blocks(content)

            # atomic=True (docs/plan/fix-atomic-claude-md-write.md, T1): writes
            # to a temp file in the same directory + os.replace(), so a crash/
            # kill mid-write can never leave CLAUDE.md empty or partial — see
            # git_helpers._AtomicWriteNoFollowSymlink's docstring.
            if not claude_md_exists:
                with open_no_follow_symlink(claude_md, "w", encoding="utf-8", atomic=True) as f:
                    f.write(new_content)
                print("[crew] Created CLAUDE.md with all managed blocks")
                return

            if new_content != content:
                with open_no_follow_symlink(claude_md, "w", encoding="utf-8", atomic=True) as f:
                    f.write(new_content)
                for line in log:
                    print(f"[crew] {line}")
            else:
                print("[crew] All managed blocks up to date")
    except OSError as exc:
        # Wrapped as well as inside report_incident(): a version-skewed
        # incidents.py can import cleanly and still raise when called, and
        # the boot is not allowed to die for it.
        try:
            if report_incident is not None:
                report_incident("claude-md-write",
                                "los bloques gestionados de CLAUDE.md NO se escribieron",
                                exc=exc)
        except BaseException:
            pass
        print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping write")


if __name__ == "__main__":
    main()
