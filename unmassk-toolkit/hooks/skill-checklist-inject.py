#!/usr/bin/env python3
"""
PostToolUse hook (matcher: Skill) -- dictate a process skill's checklist.

Why this exists (docs/plan/casillas-por-programa.md, pieza 2): the task
board sat lit for 8 sessions with zero real uses (M-119) because nothing
ever told Claude to fill it in. Waiting for the model to remember to
create its own checkboxes makes the safeguard depend on the exact
obedience it is supposed to guarantee. This hook removes that dependency:
when a process skill with a checklist manifest (unmassk-toolkit/
checklists/<skill>.json) loads, THIS PROGRAM -- not the model -- decides
which boxes must exist and records that decision in a per-session file
(lib/checklist_state.py) that `hooks/checklist-gate.py` later checks
against the real board on Stop.

Contract:
- tool_name != "Skill", or the invoked skill has no checklist manifest:
  SILENCE -- no stdout, exit 0. Most skills (unmassk-core, unmassk-memory,
  unmassk-standards, domain skills, ...) are not process skills and must
  never be nagged about a checklist they don't declare.
- Manifest found: append it to this session's registry (once per skill,
  idempotent -- reloading the same skill twice does not duplicate the
  expectation) and emit `hookSpecificOutput.additionalContext` ordering
  Claude to create those exact boxes on the board, now, verbatim.
- Any error (corrupt manifest, unreadable registry, etc.): warn on
  stderr, still exit 0 -- a broken hook must never block a Skill call
  that already ran.

I/O:
  stdin:  PostToolUse JSON -- tool_name, tool_input.skill, session_id, cwd.
  stdout: {"hookSpecificOutput": {"hookEventName": "PostToolUse",
           "additionalContext": "..."}} when a manifest matched; empty
          otherwise.
  exit:   always 0.
"""

import json
import os
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402
force_utf8_streams()

import checklist_state  # noqa: E402

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB, same ceiling as the other Bash/PostToolUse hooks in this repo.

PLUGIN_ROOT = os.path.dirname(_HOOKS_DIR)
CHECKLISTS_DIR = os.path.join(PLUGIN_ROOT, "checklists")


def _load_manifest(skill_name: str):
    """Return (boxes, error). error is None on a clean miss (no manifest
    for this skill -- the normal, silent case) or on a clean read. It is
    an Exception only when the manifest file EXISTS but could not be
    parsed as the expected shape -- the one case that must warn instead
    of staying silent."""
    # Reject anything that isn't a bare skill name before it ever touches
    # a path -- tool_input.skill is model-controlled text, and the only
    # legitimate values are the literal skill names this repo ships
    # (unmassk-flow, unmassk-audit, ...), never a path fragment.
    if not isinstance(skill_name, str) or not skill_name or "/" in skill_name or "\\" in skill_name:
        return None, None
    # Manifest filenames drop the "unmassk-" prefix (checklists/flow.json,
    # not checklists/unmassk-flow.json) -- the literal names this task
    # assigned. A skill name without that prefix (shouldn't happen for
    # this repo's own skills, but keep it a no-op rather than an error)
    # is used as-is.
    manifest_basename = skill_name[len("unmassk-"):] if skill_name.startswith("unmassk-") else skill_name
    manifest_path = os.path.join(CHECKLISTS_DIR, f"{manifest_basename}.json")
    if not os.path.isfile(manifest_path):
        return None, None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        boxes = data["boxes"]
        if not isinstance(boxes, list) or not all(isinstance(b, str) for b in boxes):
            raise ValueError("checklist manifest 'boxes' must be a list of strings")
        return boxes, None
    except Exception as e:
        return None, e


def _build_context_message(skill_name: str, boxes: list[str], enforced: bool) -> str:
    numbered = "\n".join(f"{i}. {box}" for i, box in enumerate(boxes, start=1))
    header = (
        f'[checklist] Skill "{skill_name}" declares {len(boxes)} checklist box(es) '
        "for this session's task board. Create these tasks on the board NOW, "
        "verbatim, one per box -- do not paraphrase, merge, or skip any of them:\n"
        f"{numbered}\n"
    )
    if enforced:
        return header + (
            "The Stop hook (checklist-gate.py) will block closing this session if any "
            "of these is missing from the board or left pending/in_progress."
        )
    # Moriarty, 2026-08-24: promising enforcement when the registry write
    # itself failed is a false guarantee -- reproduced with a chmod 555
    # registry dir, this hook kept promising "the Stop hook will block"
    # forever while the Stop hook could never see anything to enforce.
    return header + (
        "NOTE: this session's checklist registry could not be saved, so the "
        "Stop hook will NOT be able to enforce these boxes this session -- "
        "create them anyway, but closing will not be blocked if you don't."
    )


def _record_skill_load(
    project_root: str, session_id: str, skill_name: str, boxes: list[str]
) -> tuple[bool, list[str]]:
    """Append this skill's boxes to the session registry, once (idempotent
    across repeated loads of the same skill in one session). The whole
    load-mutate-save cycle runs inside checklist_state.locked() -- without
    it, two concurrent Skill loads race on the same file and one silently
    loses its entry (Cerberus/Argus, 2026-08-24: reproduced with flow+audit
    loading at the same time, only one survived).

    Returns (enforced, effective_boxes). `enforced` is True only when
    these boxes are durably known to be in the registry (either just
    saved successfully, or already there from an earlier successful load
    THIS session) -- callers use it to decide whether they may promise
    enforcement (Moriarty finding 3). `effective_boxes` is what the
    registry actually holds for this skill -- if it was already declared
    earlier this session, that is the OLD list from that earlier load,
    NOT a fresh re-read of `boxes` (Moriarty finding 4: if the manifest
    file changes on disk between two loads of the same skill in one
    session, the registry still enforces the FIRST version -- the
    message must name what will actually be enforced)."""
    with checklist_state.locked(project_root, session_id):
        registry, corrupt = checklist_state.load_registry(project_root, session_id)
        if corrupt:
            sys.stderr.write(
                "skill-checklist-inject: session-checklists registry was unreadable, "
                "starting a fresh one for this session\n"
            )

        for entry in registry["skills"]:
            if entry.get("skill") == skill_name:
                return True, entry.get("boxes", boxes)

        registry["skills"].append({"skill": skill_name, "boxes": boxes})
        if not checklist_state.save_registry(project_root, session_id, registry):
            sys.stderr.write(
                "skill-checklist-inject: could not persist the checklist registry "
                "(fail-open -- the board order below is still given this turn, "
                "unenforced)\n"
            )
            return False, boxes
        return True, boxes


def _emit_checklist_order(skill_name: str, boxes: list[str], enforced: bool) -> None:
    message = _build_context_message(skill_name, boxes, enforced)
    json.dump(
        {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}},
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.flush()


def main() -> None:
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        sys.stderr.write(f"skill-checklist-inject: unreadable stdin, skipping ({e!r})\n")
        sys.exit(0)

    try:
        if hook_input.get("tool_name") != "Skill":
            sys.exit(0)  # silence: not a Skill invocation

        tool_input = hook_input.get("tool_input") or {}
        skill_name = tool_input.get("skill")

        boxes, error = _load_manifest(skill_name)
        if error is not None:
            sys.stderr.write(
                f"skill-checklist-inject: manifest for '{skill_name}' is broken, "
                f"skipping this session's checklist for it ({error!r})\n"
            )
            sys.exit(0)
        if boxes is None:
            sys.exit(0)  # silence: no manifest for this skill

        session_id = hook_input.get("session_id")
        project_root = hook_input.get("cwd") or os.getcwd()

        enforced, effective_boxes = _record_skill_load(project_root, session_id, skill_name, boxes)
        _emit_checklist_order(skill_name, effective_boxes, enforced)

    except Exception as e:
        sys.stderr.write(f"skill-checklist-inject: unexpected error, fail-open ({e!r})\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
