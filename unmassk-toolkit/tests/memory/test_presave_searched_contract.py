"""RED contract -- issue #95, part 2c: search before saving (D-098, D-124).

Test-first, contract pass, written before any production change. Sources,
read before writing a line (never recalled):

  - D-098 (archived by mistake, restated by D-124), `gitmem search --id
    D-098`: "Solo al guardar (lo pide customs.py antes de gitmem
    note/rule): ¿lo busqué y no está ya escrito ni es sentido común? La
    búsqueda la hace Claude; el comando exige un campo con lo buscado y
    lo encontrado."
  - D-124: "Only when saving: did I search, and is it not already written
    or common sense?"
  - Issue #95, checklist comment: "El comando de guardar pide un campo
    obligatorio con lo buscado y lo encontrado (p. ej. «busqué "squash":
    encontré D-057»); sin él, rechaza el guardado, igual que ya hace
    `--quote` con las reglas." and "La pregunta 3 la pide el vigilante
    que ya salta antes de cada commit (`customs.py`, PreToolUse sobre
    Bash), justo antes de un `gitmem note` o `gitmem rule`."
  - X-105 (discarded): "que un hook o el comando busque solo por
    palabras" -- so neither the command nor the hook may check WHAT was
    searched; any non-empty text is the answer.
  - Plan docs/plan/feat-95-rules-at-boot.md, part 2c.

THE CONTRACT, as the coordinator fixed it, mapped to the classes below:

  1. `gitmem note` (all seven types) and `gitmem rule` (add and
     `--replaces`) WITHOUT `--searched`, or with it empty/blank -> save
     NOTHING (no commit, HEAD unmoved, working tree untouched, no id
     consumed) and bounce with the D-098 question and the exact relaunch.
     -> TestNoteWithoutSearchedBounces, TestRuleWithoutSearchedBounces
  2. The relaunch is EXACT: the command just typed, with every value
     already given kept verbatim, plus `--searched`. Executing it as
     offered (only the `--searched` placeholder filled in) saves, and the
     saved commit carries the values the user gave -- not "..." stand-ins.
     -> TestRelaunchIsExact
  3. WITH `--searched "<searched>: <found>"` -> saved, and the text is in
     the saved commit, read back from git (`git log`), never from the
     input; the note is still readable by the system's own reader
     (`gitmem search --id`). -> TestSearchedSurvivesTheRoundTrip
  4. customs.py (PreToolUse/Bash) blocks a `gitmem note` / `gitmem rule`
     call that lacks `--searched`, with the same question, before the
     command runs. -> TestCustomsBlocksBeforeTheCommandRuns
  5. Nothing else changes: `gitmem rule` bare read, `gitmem rule list`,
     `gitmem rule --retract`, other gitmem commands, and Bash commands
     that merely MENTION `gitmem note`. -> TestNothingElseChanges,
     TestCustomsLetsEverythingElseThrough
  6. Regression for a known incident class (relaunch-command answer
     amnesia, see test_relaunch_command_answer_amnesia.py): once
     `--searched` is given, the relaunch offered by ANOTHER rejection
     (pain question, issue gate) must carry it, or obeying the relaunch
     bounces again and the answer is lost. -> TestOtherRelaunchesCarrySearched

What the expected values are compared against (written separately from the
code under test): the D-098 question is the owner's own sentence from D-098;
every saved value is what THIS test typed, read back from git.

Why `gitmem` and not `note.py`: the contract names `gitmem note` / `gitmem
rule` -- the door the user (Claude) actually uses. The facade dispatches
byte-for-byte to the scripts (bin/gitmem docstring).

DECLARED ASSUMPTIONS (a gap is not filled silently):
  - The question is the D-098 literal, in Spanish like every other
    rejection of this system. Compared casefolded and NFC-normalised, so
    "¿Lo busqué..." and "¿lo busqué..." are the same question.
  - The hook is tested with customs explicitly ON (`customs_enabled:
    true`). Whether the hook also asks on a project whose customs is off
    is not in the contract and is not pinned here.
  - A bounce must not be argparse's own error (`usage:`): an argparse
    `required=True` would print usage instead of the question, and would
    also break test_rejection_relaunch_commands.py's parser crosscheck
    for every existing relaunch that has no `--searched`.
"""

import json
import shlex
import unicodedata

import pytest

from .conftest import (
    extract_note_id,
    pm_path,
    run_git,
    run_gitmem_script,
    run_hook_with_payload,
    seed_config_json,
    seed_zones_json,
)

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


# ── 1. without --searched: nothing saved, the D-098 question ─────────────


class TestNoteWithoutSearchedBounces:
    """Bug caught: a note saved without anyone having searched first --
    the 2026-10-18 failure (a rule already written, a reading mistake
    saved as a memo) that D-098 exists to stop."""

    @pytest.mark.parametrize("note_type,headline,extra", _SEVEN_TYPES, ids=_TYPE_IDS)
    def test_should_save_nothing_and_ask_d098_when_searched_is_missing(
        self, tmp_repo, note_type, headline, extra
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(_note_args(note_type, headline, extra), cwd=tmp_repo)

        _assert_searched_bounce(rc, out, err, f"gitmem note {note_type} without --searched")
        assert _snapshot(tmp_repo) == before, "a bounced note must leave git and the tree untouched"

    @pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "blank"])
    def test_should_save_nothing_when_searched_is_empty_or_blank(self, tmp_repo, blank):
        note_type, headline, extra = _SEVEN_TYPES[0]
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(
            _note_args(note_type, headline, extra, "--searched", blank), cwd=tmp_repo
        )

        _assert_searched_bounce(rc, out, err, f"gitmem note with --searched {blank!r}")
        assert _snapshot(tmp_repo) == before

    def test_should_not_consume_an_id_when_it_bounces(self, tmp_repo):
        """Bug caught: the bounce runs after the id counter moved, so the
        first real D comes out D-002 and D-001 never exists."""
        note_type, headline, extra = _SEVEN_TYPES[0]
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])

        rc_bounce, _, _ = run_gitmem_script(_note_args(note_type, headline, extra), cwd=tmp_repo)
        assert rc_bounce != 0
        rc, out, err = run_gitmem_script(
            _note_args(note_type, headline, extra, "--searched", _SEARCHED), cwd=tmp_repo
        )

        assert rc == 0, f"the answered save must pass -- stdout={out!r} stderr={err!r}"
        assert extract_note_id(out) == "D-001"

    def test_should_bounce_a_replacing_note_without_searched_too(self, tmp_repo):
        """Bug caught: the check placed only on the plain-write branch, so
        `--replaces <ID>` (notes.replace) saves with nobody having searched."""
        note_type, headline, extra = _SEVEN_TYPES[0]
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc_seed, out_seed, err_seed = run_gitmem_script(
            _note_args(note_type, headline, extra, "--searched", _SEARCHED), cwd=tmp_repo
        )
        assert rc_seed == 0, f"seed must save -- stdout={out_seed!r} stderr={err_seed!r}"
        old_id = extract_note_id(out_seed)
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(
            _note_args("D", "retire the wiki and redirect every old link",
                       ["--why", "old links still get traffic",
                        "--description", "redirects keep bookmarks alive"],
                       "--replaces", old_id),
            cwd=tmp_repo,
        )

        _assert_searched_bounce(rc, out, err, "gitmem note --replaces without --searched")
        assert _snapshot(tmp_repo) == before


class TestRuleWithoutSearchedBounces:
    """Bug caught: a rule saved without searching -- the emoji rule saved
    twice on 2026-10-18, the very case D-098 names."""

    def test_should_save_nothing_and_ask_d098_when_adding_without_searched(self, tmp_repo):
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(
            ["rule", _RULE_TEXT, "--kind", "user", "--quote", _RULE_QUOTE], cwd=tmp_repo
        )

        _assert_searched_bounce(rc, out, err, "gitmem rule without --searched")
        assert _snapshot(tmp_repo) == before, "rules.md must not be created nor committed"

    @pytest.mark.parametrize("blank", ["", "   "], ids=["empty", "blank"])
    def test_should_save_nothing_when_searched_is_empty_or_blank(self, tmp_repo, blank):
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(
            ["rule", _RULE_TEXT, "--kind", "user", "--quote", _RULE_QUOTE, "--searched", blank],
            cwd=tmp_repo,
        )

        _assert_searched_bounce(rc, out, err, f"gitmem rule with --searched {blank!r}")
        assert _snapshot(tmp_repo) == before

    def test_should_keep_the_old_rule_when_replacing_without_searched(self, tmp_repo):
        _save_rule(tmp_repo, _RULE_TEXT, _RULE_QUOTE, _SEARCHED)
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(
            ["rule", _RULE_NEW_TEXT, "--replaces", _RULE_TEXT, "--kind", "user",
             "--quote", _RULE_NEW_QUOTE],
            cwd=tmp_repo,
        )

        _assert_searched_bounce(rc, out, err, "gitmem rule --replaces without --searched")
        assert _snapshot(tmp_repo) == before, "the old rule must stay exactly as it was"


# ── 2. the relaunch is exact ─────────────────────────────────────────────


class TestRelaunchIsExact:
    """Bug caught: a relaunch that drops or blanks what was already given
    (`--description "..."`, a lost `--stops`/`--work`/`--kind`/`--quote`).
    Obeyed literally, it either bounces again or saves "..." in place of
    the real text -- memory content lost by the system itself."""

    @pytest.mark.parametrize(
        "note_type,headline,extra,given_texts",
        [
            (*_SEVEN_TYPES[0], ("one source of truth is cheaper than two",
                                "the wiki has not been updated in a year")),
            (*_SEVEN_TYPES[2], ("a background write corrupted it mid-read",)),
            (*_SEVEN_TYPES[3], ("finance flagged a possible double count",)),
        ],
        ids=["D-why-description", "R-stops", "Q-work"],
    )
    def test_should_save_with_every_given_value_when_the_note_relaunch_is_obeyed(
        self, tmp_repo, note_type, headline, extra, given_texts
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = run_gitmem_script(_note_args(note_type, headline, extra), cwd=tmp_repo)
        assert rc != 0, f"must bounce first -- stdout={out!r}"
        relaunches = _relaunch_commands(out + err, "note")
        assert len(relaunches) == 1, f"one exact relaunch expected, got {relaunches!r} in {out + err!r}"

        tokens = _fill_searched(shlex.split(relaunches[0]), _SEARCHED)
        rc2, out2, err2 = run_gitmem_script(tokens[1:], cwd=tmp_repo)

        assert rc2 == 0, (
            f"the relaunch, obeyed as offered, must save -- ran {tokens!r} -> "
            f"stdout={out2!r} stderr={err2!r}"
        )
        message = _head_message(tmp_repo)
        assert headline in message
        missing = [text for text in given_texts if text not in message]
        assert missing == [], (
            f"the relaunch lost text the user gave: {missing!r} -- saved commit:\n{message}"
        )
        assert _SEARCHED in message

    def test_should_keep_text_kind_and_quote_when_the_rule_relaunch_is_obeyed(self, tmp_repo):
        """`--kind claude` on purpose: a relaunch that drops --kind falls
        back to the `user` default and swaps the rule's owner silently."""
        rc, out, err = run_gitmem_script(
            ["rule", _RULE_TEXT, "--kind", "claude", "--quote", _RULE_QUOTE], cwd=tmp_repo
        )
        assert rc != 0, f"must bounce first -- stdout={out!r}"
        relaunches = _relaunch_commands(out + err, "rule")
        assert len(relaunches) == 1, f"one exact relaunch expected, got {relaunches!r} in {out + err!r}"

        tokens = _fill_searched(shlex.split(relaunches[0]), _SEARCHED)
        rc2, out2, err2 = run_gitmem_script(tokens[1:], cwd=tmp_repo)

        assert rc2 == 0, f"ran {tokens!r} -> stdout={out2!r} stderr={err2!r}"
        rules = _rules_md(tmp_repo)
        assert rules is not None, "rules.md must exist after the relaunch saved"
        assert f"[claude] 🧠 {_RULE_TEXT} — «{_RULE_QUOTE}»" in rules, (
            f"text, owner and quote must survive the relaunch -- rules.md:\n{rules}"
        )

    def test_should_keep_the_replaced_text_when_the_rule_replace_relaunch_is_obeyed(self, tmp_repo):
        _save_rule(tmp_repo, _RULE_TEXT, _RULE_QUOTE, _SEARCHED)
        rc, out, err = run_gitmem_script(
            ["rule", _RULE_NEW_TEXT, "--replaces", _RULE_TEXT, "--kind", "user",
             "--quote", _RULE_NEW_QUOTE],
            cwd=tmp_repo,
        )
        assert rc != 0, f"must bounce first -- stdout={out!r}"
        relaunches = _relaunch_commands(out + err, "rule")
        assert len(relaunches) == 1, f"one exact relaunch expected, got {relaunches!r} in {out + err!r}"

        tokens = _fill_searched(shlex.split(relaunches[0]), _SEARCHED_OTHER)
        rc2, out2, err2 = run_gitmem_script(tokens[1:], cwd=tmp_repo)

        assert rc2 == 0, f"ran {tokens!r} -> stdout={out2!r} stderr={err2!r}"
        rules = _rules_md(tmp_repo)
        assert f"[user] 🧠 {_RULE_NEW_TEXT} — «{_RULE_NEW_QUOTE}»" in rules
        assert _RULE_TEXT not in rules, f"the old rule must be gone -- rules.md:\n{rules}"


# ── 3. with --searched: saved, and the text survives the round trip ──────


class TestSearchedSurvivesTheRoundTrip:
    """Bug caught: `--searched` accepted and thrown away (validated but
    never written), or written in a shape the system's own reader can no
    longer parse -- the note silently vanishes from search."""

    @pytest.mark.parametrize("note_type,headline,extra", _SEVEN_TYPES, ids=_TYPE_IDS)
    def test_should_store_searched_in_the_note_commit_and_keep_it_readable(
        self, tmp_repo, note_type, headline, extra
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before = _snapshot(tmp_repo)

        rc, out, err = run_gitmem_script(
            _note_args(note_type, headline, extra, "--searched", _SEARCHED), cwd=tmp_repo
        )

        assert rc == 0, f"with --searched the note must save -- stdout={out!r} stderr={err!r}"
        note_id = extract_note_id(out)
        assert _snapshot(tmp_repo)["count"] == before["count"] + 1, "exactly one new commit"
        message = _head_message(tmp_repo)
        assert _SEARCHED in message, (
            f"the --searched text must be in the saved commit, verbatim -- commit:\n{message}"
        )

        rc_s, out_s, err_s = run_gitmem_script(["search", "--id", note_id], cwd=tmp_repo)
        assert rc_s == 0, f"the saved note must stay readable -- stdout={out_s!r} stderr={err_s!r}"
        assert headline in out_s, f"search --id {note_id} lost the note -- {out_s!r}"

    def test_should_store_searched_in_the_rule_commit(self, tmp_repo):
        rc, out, err = run_gitmem_script(
            ["rule", _RULE_TEXT, "--kind", "user", "--quote", _RULE_QUOTE,
             "--searched", _SEARCHED],
            cwd=tmp_repo,
        )

        assert rc == 0, f"with --searched the rule must save -- stdout={out!r} stderr={err!r}"
        assert _SEARCHED in _head_message(tmp_repo)
        rc_r, out_r, err_r = run_gitmem_script(["rule"], cwd=tmp_repo)
        assert rc_r == 0, err_r
        assert _RULE_TEXT in out_r, f"the saved rule must read back -- {out_r!r}"

    def test_should_store_searched_in_the_rule_replace_commit(self, tmp_repo):
        _save_rule(tmp_repo, _RULE_TEXT, _RULE_QUOTE, _SEARCHED)

        rc, out, err = run_gitmem_script(
            ["rule", _RULE_NEW_TEXT, "--replaces", _RULE_TEXT, "--kind", "user",
             "--quote", _RULE_NEW_QUOTE, "--searched", _SEARCHED_OTHER],
            cwd=tmp_repo,
        )

        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert _SEARCHED_OTHER in _head_message(tmp_repo), (
            "the replace commit must carry ITS OWN --searched, not the old rule's"
        )


# ── 4. customs.py asks before the command runs ───────────────────────────


class TestCustomsBlocksBeforeTheCommandRuns:
    """Bug caught: the hook still only watching `git commit`, so the
    question is never asked at the moment it matters."""

    @pytest.mark.parametrize(
        "command",
        [
            f'gitmem note D --zones {_ZONE1} {_ZONE2} "retire the wiki" '
            f'--why "one source" --description "stale"',
            f'gitmem rule "{_RULE_TEXT}" --kind user --quote "{_RULE_QUOTE}"',
            f'gitmem rule "{_RULE_NEW_TEXT}" --replaces "{_RULE_TEXT}" --kind user '
            f'--quote "{_RULE_NEW_QUOTE}"',
        ],
        ids=["note", "rule-add", "rule-replaces"],
    )
    def test_should_block_with_d098_when_searched_is_missing(self, tmp_repo, command):
        seed_config_json(tmp_repo, customs_enabled=True)

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "block", f"must block {command!r} -- got {decision!r}"
        reason = decision.get("reason", "")
        assert _norm(_D098_QUESTION) in _norm(reason), f"block must ask D-098 -- {reason!r}"
        assert "--searched" in reason

    def test_should_block_when_the_save_comes_after_a_cd(self, tmp_repo):
        """The everyday shape: `cd <repo> && gitmem note ...`."""
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            f'cd {shlex.quote(tmp_repo)} && gitmem note X --zones {_ZONE1} {_ZONE2} '
            f'"dropped the extension" --description "cli covers it"'
        )

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "block", f"got {decision!r}"
        assert _norm(_D098_QUESTION) in _norm(decision.get("reason", ""))


# ── 5. nothing else changes ──────────────────────────────────────────────


class TestCustomsLetsEverythingElseThrough:
    """Bug caught: an over-broad match that blocks reads, retractions, or
    any command that only mentions `gitmem note` -- friction on every
    search and grep of the day."""

    @pytest.mark.parametrize(
        "command",
        [
            f'gitmem note D --zones {_ZONE1} {_ZONE2} "retire the wiki" '
            f'--why "one source" --description "stale" --searched "{_SEARCHED_OTHER}"',
            f'gitmem note D --zones {_ZONE1} {_ZONE2} "retire the wiki" '
            f'--why "one source" --description "stale" --searched="wiki: nada"',
            f'gitmem rule "{_RULE_TEXT}" --kind user --quote "{_RULE_QUOTE}" '
            f'--searched "{_SEARCHED_OTHER}"',
            "gitmem rule",
            f'gitmem rule --retract "{_RULE_TEXT}" --kind user',
            "gitmem search --id D-098",
            'grep -rn "gitmem note" unmassk-toolkit/skills',
        ],
        ids=["note-answered", "note-answered-equals-form", "rule-answered", "rule-read",
             "rule-retract", "search", "grep-mention"],
    )
    def test_should_approve(self, tmp_repo, command):
        seed_config_json(tmp_repo, customs_enabled=True)

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "approve", f"{command!r} must pass -- got {decision!r}"


class TestNothingElseChanges:
    """Bug caught: the check placed before the read/retract branches of
    rule.py -- reading the rules (`/remember`) or retracting one starts
    demanding a search."""

    def test_should_read_rules_without_searched(self, tmp_repo):
        rc, out, err = run_gitmem_script(["rule"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "--searched" not in out + err

    def test_should_treat_rule_list_as_a_read_without_searched(self, tmp_repo):
        rc, out, err = run_gitmem_script(["rule", "list"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "--searched" not in out + err

    def test_should_retract_a_rule_without_searched(self, tmp_repo):
        _save_rule(tmp_repo, _RULE_TEXT, _RULE_QUOTE, _SEARCHED)

        rc, out, err = run_gitmem_script(
            ["rule", "--retract", _RULE_TEXT, "--kind", "user"], cwd=tmp_repo
        )

        assert rc == 0, f"--retract needs no --searched -- stdout={out!r} stderr={err!r}"
        assert _RULE_TEXT not in (_rules_md(tmp_repo) or "")


# ── 6. regression: other relaunches carry the given --searched ───────────


class TestOtherRelaunchesCarrySearched:
    """Known incident class (test_relaunch_command_answer_amnesia.py): a
    relaunch built from scratch drops an answer already given. Here: the
    pain question / issue gate fire AFTER `--searched` was answered; if
    their relaunch drops it, obeying it bounces again on D-098 and the
    search the user wrote is gone."""

    @pytest.mark.parametrize(
        "note_type,headline,extra,expected_relaunches",
        [
            ("M", "the deploy window closes at six on fridays",
             ["--description", "ops confirmed the freeze"], 2),
            ("Q", "should canceled trials count toward seats",
             ["--description", "finance is unsure"], 3),
        ],
        ids=["pain-question", "issue-gate"],
    )
    def test_should_carry_searched_verbatim_in_every_offered_relaunch(
        self, tmp_repo, note_type, headline, extra, expected_relaunches
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])

        rc, out, err = run_gitmem_script(
            _note_args(note_type, headline, extra, "--searched", _SEARCHED), cwd=tmp_repo
        )

        assert rc != 0, f"must bounce on the other question -- stdout={out!r}"
        relaunches = _relaunch_commands(out + err, "note")
        assert len(relaunches) == expected_relaunches, f"got {relaunches!r} in {out + err!r}"
        for relaunch in relaunches:
            assert _searched_value(shlex.split(relaunch)) == _SEARCHED, (
                f"relaunch dropped or altered the given --searched: {relaunch!r}"
            )
