"""Shared values and helpers of the #95 part 2c `--searched` contract
(D-098, D-124): `test_presave_searched_contract.py` and
`test_presave_searched_customs.py`. Not a test module. Split 2026-10-19
(Yoda's size finding); the contract itself is described in
`test_presave_searched_contract.py`.
"""

import json
import unicodedata

import pytest

from .conftest import pm_path, run_git, run_gitmem_script, run_hook_with_payload

_ZONE1 = "presavezone"
_ZONE2 = "presavezonetwo"

# D-098, the owner's own words (gitmem search --id D-098).
_D098_QUESTION = "¿lo busqué y no está ya escrito ni es sentido común?"

# A realistic answer, shaped like the issue's own example, with the
# characters most likely to be lost on the way to a commit: double quotes,
# a colon, accents.
_SEARCHED = 'busqué "squash" y "rebase": encontré D-057, nada sobre esto'
_SEARCHED_OTHER = 'busqué "seat limit": nada parecido, solo M-004 sobre facturas'

# (type, headline, extra flags) -- every type with the flags it needs to
# save today (vocabulary.TYPES required fields, D-065 issue gate for Q/I),
# each a distinct subject.
_SEVEN_TYPES = [
    ("D", "retire the internal wiki in favor of the docs site",
     ["--why", "one source of truth is cheaper than two",
      "--description", "the wiki has not been updated in a year"]),
    ("M", "the weekly digest email goes out on mondays at nine",
     ["--description", "support confirmed the schedule", "--stops", "no"]),
    ("R", "never write the shared config from a background thread",
     ["--description", "a background write corrupted it mid-read", "--stops", "yes"]),
    ("Q", "does a canceled trial still count toward the seat limit",
     ["--description", "finance flagged a possible double count", "--work", "no"]),
    ("X", "dropped the browser extension for quick capture",
     ["--description", "the cli already covers the same capture flow"]),
    ("I", "the retry queue redelivered one webhook for eleven hours",
     ["--description", "a missing ack let the worker redeliver it", "--work", "no"]),
    ("B", "waiting on the analytics vendor to backfill last month",
     ["--description", "the monthly report is stuck until they finish",
      "--awaits", "analytics vendor support"]),
]
_TYPE_IDS = [t[0] for t in _SEVEN_TYPES]

_RULE_TEXT = "never squash the step commits of a branch before merging it"
_RULE_QUOTE = "no me aplastes los commits, que luego no sé qué pasó"
_RULE_NEW_TEXT = "merge branches with no-ff so every step commit survives"
_RULE_NEW_QUOTE = "con no-ff, que se vea cada paso"


# ── helpers ──────────────────────────────────────────────────────────────


def _norm(text):
    return unicodedata.normalize("NFC", text).casefold()


def _note_args(note_type, headline, extra, *more):
    return ["note", note_type, "--zones", _ZONE1, _ZONE2, headline, *extra, *more]


def _rules_md(repo):
    path = pm_path(repo) / "rules.md"
    return path.read_text(encoding="utf-8") if path.exists() else None


def _snapshot(repo):
    """Everything a save could touch: HEAD, commit count, working tree."""
    rc_h, head, err_h = run_git(["rev-parse", "HEAD"], repo)
    assert rc_h == 0, err_h
    rc_c, count, err_c = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc_c == 0, err_c
    rc_s, status, err_s = run_git(["status", "--porcelain", "--untracked-files=all"], repo)
    assert rc_s == 0, err_s
    return {"head": head, "count": int(count), "status": status, "rules_md": _rules_md(repo)}


def _head_message(repo):
    rc, message, err = run_git(["log", "-1", "--format=%B", "HEAD"], repo)
    assert rc == 0, f"git log failed reading the saved commit: {err}"
    return message


def _assert_searched_bounce(rc, out, err, what):
    combined = out + err
    assert rc != 0, f"{what}: must bounce, came out rc=0 -- stdout={out!r}"
    assert "Traceback" not in combined, f"{what}: a bounce is never a traceback -- {combined!r}"
    assert "usage:" not in combined, (
        f"{what}: the bounce must be the D-098 question, not argparse's own "
        f"usage error -- {combined!r}"
    )
    assert _norm(_D098_QUESTION) in _norm(combined), (
        f"{what}: the bounce must ask the D-098 question {_D098_QUESTION!r} -- "
        f"real output: {combined!r}"
    )
    assert "--searched" in combined, (
        f"{what}: the bounce must name the --searched flag to answer with -- {combined!r}"
    )


def _relaunch_commands(output, subcommand):
    """The `gitmem <subcommand> ...` lines of the rejection's structured
    relaunch -- only lines AFTER the literal "Relanza:" header that
    rejection.py::_render prints (prose above it may mention gitmem too;
    see relaunch-command answer-amnesia notes)."""
    lines = output.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "Relanza:")
    except StopIteration:
        return []
    prefix = f"gitmem {subcommand}"
    return [
        line.strip() for line in lines[start + 1:]
        if line.strip().startswith(prefix + " ") or line.strip() == prefix
    ]


def _fill_searched(tokens, value):
    """Replace the value right after `--searched` -- the only thing the
    user has to fill in a relaunch. Fails loudly if the flag is absent."""
    assert "--searched" in tokens, f"relaunch has no --searched flag: {tokens!r}"
    i = tokens.index("--searched")
    assert i + 1 < len(tokens), f"--searched has no value slot: {tokens!r}"
    filled = list(tokens)
    filled[i + 1] = value
    return filled


def _searched_value(tokens):
    assert "--searched" in tokens, f"relaunch dropped --searched: {tokens!r}"
    i = tokens.index("--searched")
    assert i + 1 < len(tokens), f"--searched has no value: {tokens!r}"
    return tokens[i + 1]


def _save_rule(repo, text, quote, searched, kind="user"):
    rc, out, err = run_gitmem_script(
        ["rule", text, "--kind", kind, "--quote", quote, "--searched", searched], cwd=repo
    )
    assert rc == 0, f"seeding a rule with --searched must save -- stdout={out!r} stderr={err!r}"


def _run_customs(repo, command):
    rc, out, err = run_hook_with_payload(
        "customs.py",
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": repo},
        cwd=repo,
    )
    assert rc == 0, f"customs.py always exits 0, the decision is in the JSON -- rc={rc} stderr={err!r}"
    try:
        decision = json.loads(out)
    except ValueError:
        pytest.fail(f"customs.py stdout is not JSON: {out!r} stderr={err!r}")
    return decision
