#!/usr/bin/env python3
"""
UserPromptSubmit hook -- bootstrap + first-message skill routing.

Fires on every user message. Responsibilities:
1. If git-memory is not configured: tell Claude to install it
2. If configured: remind Claude to boot (if not done) + route to relevant skills

Exit codes:
    0: Always (never blocks user input).
"""

import json
import os
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import is_git_repo, run_git, open_no_follow_symlink, ensure_runtime_dir  # noqa: E402  (import after sys.path mutation)

# Re-exported for backward compatibility only (issue #63, boot
# simplification, point 2): the real implementation and its call site both
# moved to lib/upgrade_check.py, invoked once per SessionStart from
# hooks/session-start-boot.py instead of on every UserPromptSubmit message.
# Neither name is called anywhere below — main() has zero trace of upgrade
# evaluation now. Kept importable here only because
# tests/test_needs_upgrade_semver.py loads THIS hook file directly via
# importlib and calls hook.needs_upgrade()/hook._parse_semver() — the
# underlying logic is unchanged, byte-for-byte, only its home moved.
from upgrade_check import needs_upgrade, _parse_semver  # noqa: F401,E402  (import after sys.path mutation)

# ── Toolkit incident channel — imported defensively ──────────────────────
# UserPromptSubmit is the only hook channel proven to reach the model
# mid-session (measured 1445/1445, vs 0/2506 on Stop), so this is where the
# toolkit's own failures get announced. See lib/incidents.py. A missing or
# broken incidents module must cost nothing: drain becomes a no-op.
try:
    from incidents import drain_incidents as _drain_incidents
except Exception as e:
    print(f"[git-memory] incidents import fail-open: {e!r}", file=sys.stderr)
    _drain_incidents = None  # type: ignore[assignment]

# ── Skill router — imported defensively; any import failure is visible but silent ──
# SKILL_TRIGGER_PHRASES is re-exported (not just match_skills) so tooling that
# introspects this hook module directly can read the live trigger table.
try:
    from skill_router import match_skills as _match_skills, SKILL_TRIGGER_PHRASES
except Exception as e:
    print(f"[git-memory] skill_router import fail-open: {e!r}", file=sys.stderr)
    _match_skills = None  # type: ignore[assignment]
    SKILL_TRIGGER_PHRASES = {}  # type: ignore[assignment]

# Plugin root — derived from this script's location in the cache.
# hooks/user-prompt-memory-check.py → go up one level → plugin root.
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def get_project_root() -> str | None:
    """Get the git repo root, or None."""
    code, toplevel = run_git(["rev-parse", "--show-toplevel"])
    return toplevel if code == 0 else None


def needs_install(root: str) -> bool:
    """Check if git-memory CLAUDE.md managed block is present."""
    claude_md = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return True
    try:
        # barrido finding: never follow a symlink planted at CLAUDE.md —
        # treat it exactly like "no CLAUDE.md present" (needs install).
        with open_no_follow_symlink(claude_md, "r") as f:
            return "BEGIN unmassk-toolkit" not in f.read()
    except OSError:
        return True


# Maximum stdin bytes we will read before parsing JSON.
# Guards against a malformed or adversarial payload loading unbounded RAM.
_STDIN_READ_LIMIT: int = 512_000


def _read_prompt_text() -> str | None:
    """Read stdin and extract the prompt string from the JSON payload.

    Returns the prompt string if stdin is valid JSON with a non-empty string
    'prompt' key, otherwise None. All failures are swallowed — this hook must
    never crash due to stdin content.
    """
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        if not raw or not raw.strip():
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return None
        return prompt
    except Exception:
        return None


def main() -> None:
    """Print hook output for Claude to process."""
    # ── Toolkit incidents — printed before any early exit
    # (not-a-git-repo, needs_install) so a toolkit failure is announced in
    # EVERY project, whatever state that project is in. At most 3 detailed
    # per message; the rest are stated in one line and detailed next time.
    # drain_incidents() is fail-open by contract and returns [] on any
    # error, so nothing below this point can be affected by it.
    # The try wraps the CALL as well: a version-skewed or half-written
    # incidents.py in the plugin cache can import cleanly and still raise
    # when called, and this hook must not die for it (verified: an
    # unwrapped call turned exit 0 into exit 1 and swallowed the banner).
    try:
        if _drain_incidents is not None:
            for line in _drain_incidents(os.getcwd()):
                print(line)
    except BaseException:
        pass

    # ── Read prompt from stdin (fail-open: any error → None) ─────────────
    prompt_text = _read_prompt_text()

    if not is_git_repo():
        sys.exit(0)

    root = get_project_root()
    if not root:
        sys.exit(0)

    # Case 1: git-memory not installed yet — tell Claude to install
    if needs_install(root):
        print(
            "[git-memory-bootstrap] Git-memory plugin is active but NOT configured. "
            "BEFORE doing anything else:\n"
            f'1. Run: python3 "{PLUGIN_ROOT}/bin/git-memory-install.py" --auto\n'
            '2. Use the Skill tool with skill="unmassk-core" (TOOL CALL, not bash)\n'
            "3. Show the user a boot summary from the SessionStart output above.\n"
            "DO NOT greet the user first. Install and boot FIRST.\n"
            "DO NOT SKIP ANY STEP."
        )
        sys.exit(0)

    # Case 1.5 (needs_upgrade auto-upgrade) removed (issue #63, boot
    # simplification, point 2): this per-message evaluation + subprocess
    # trigger moved to hooks/session-start-boot.py, which now calls
    # lib/upgrade_check.py's trigger_auto_upgrade_if_needed() once per
    # SessionStart instead. This hook no longer evaluates or triggers an
    # upgrade at all.

    # Case 2: Installed — check if session already booted
    lines = []
    booted_flag = os.path.join(root, ".claude", ".unmassk", ".session-booted")
    session_booted = os.path.isfile(booted_flag)

    if not session_booted:
        # First message — force skill loading
        lines.append(
            f"[git-memory-boot] Plugin root: {PLUGIN_ROOT}\n"
            "MANDATORY — Do these steps NOW before responding to the user:\n"
            '  Step 1: Use the Skill tool with skill="unmassk-core" (TOOL CALL, not bash)\n'
            "  Step 2: Show the user a boot summary from the SessionStart output above\n"
            "DO NOT SKIP ANY STEP. DO NOT GREET THE USER BEFORE COMPLETING ALL STEPS."
        )
        # Create the flag so subsequent messages don't repeat this
        try:
            # SEC-HIGH-004: .claude may be a symlink to an external
            # directory — ensure_runtime_dir() verifies the resolved path
            # stays inside root before creating anything (was a bare
            # os.makedirs() that silently followed the symlink).
            ensure_runtime_dir(root)
            # SEC-HIGH-NEW-10: never follow a (dangling) symlink planted at
            # the booted-flag path — fail-open like every other fallback in
            # this file: don't create the flag, don't break the hook.
            # reject_hardlinks=True (issue #53, decision 51a3c44): the
            # .session-booted flag is toolkit-generated-only, never a
            # legitimate user file, so a hard link here can only be an
            # attack.
            open_no_follow_symlink(booted_flag, "w", reject_hardlinks=True).close()
        except OSError:
            pass
    # else: already booted — no per-message line needed (root is boot-only
    # info now, per issue #69; SessionStart boot still shows it).

    # ── Per-message protocol-skill router — runs on EVERY message, not
    # gated by session_booted, so it coexists with the first-message
    # forcing block above. Purely informational nudge; never blocks.
    if prompt_text and _match_skills is not None:
        try:
            matched_skills = _match_skills(prompt_text)
            if matched_skills:
                lines.append(f"[skill-router] Possibly relevant skill(s): {', '.join(matched_skills)}")
        except Exception as e:
            print(f"[git-memory] skill_router fail-open: {e!r}", file=sys.stderr)
            # fail-open: router failure must never affect the hook output

    # A watchdog that only speaks when it has something to flag is
    # indistinguishable from a watchdog that isn't running at all (P6:
    # this hook already ran silently for days once with nobody noticing —
    # see agent memory). Owner decision 2026-08-04 revokes the prior
    # "stay silent" call: this hook must always print, even when there is
    # nothing to report, so its own execution is provable every message.
    if not lines:
        lines.append("[memory-check] No skill match this turn — nothing to report.")

    print("\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    main()
