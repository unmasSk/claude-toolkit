"""#95 part 2c fix pass (D-133 and the relaunch fixes), pinned so each one
turns red if its behaviour is removed.

  1. Version skew (D-133): a note saved by THIS code is read WHOLE by the
     frozen 1.47.0 reader -- the one still installed on any machine that
     has not updated. Two doors: its `format.parse_message` in a process
     of its own (every field compared), and its own `gitmem search --id`
     (the user's door). And the reverse: a note written by the 1.47.0
     writer is read by the new reader with `searched=None`, even when its
     description happens to start with `Searched: `.
     -> TestFrozen147ReaderReadsNewNotes, TestNewReaderReadsFrozen147Notes
  2. The new reader keeps a note (and a session-close NEXT) that carries a
     body field it does not know -- a note from a newer version is never
     dropped. A line that is neither a field nor a continuation still
     rejects. -> TestNewReaderToleratesUnknownFields
  3. A note with no `searched` is written byte for byte as 1.47.0 wrote
     it. -> TestBuildWithoutSearchedUnchanged
  4. `--discard`: every X carries the same `--searched` as its D.
     -> TestDiscardCarriesSearched
  5. Relaunches that, obeyed literally, used to lose data or bounce again:
     near-duplicate rule (keeps --kind/--quote/--searched), missing-quote
     rule (keeps --kind and --replaces), field mismatch (keeps a hole for
     --why / --awaits). Each one is OBEYED here and the result read back.
     -> TestRuleNearDuplicateRelaunch, TestRuleMissingQuoteRelaunch,
        TestFieldMismatchRelaunch
  6. A multi-line `--searched` on a rule is folded in the rule's commit
     body. -> TestRuleSearchedFolded
  7. Hook: a `\\`-continued `gitmem note` gets a one-line relaunch that
     saves when obeyed, and a `--searched` given after a continuation
     counts as answered; the `--amend` bounce suggests `--searched`.
     -> TestCustomsLineContinuation, TestCustomsAmendBounce

The frozen reader lives in the plugin cache of the REAL home
(`~/.claude/plugins/cache/.../1.47.0/lib`), resolved from the user
database because the suite runs under a throwaway HOME. It is only read:
every process run from it gets `-B`/PYTHONDONTWRITEBYTECODE so not even a
`.pyc` lands there. If the folder is missing the test FAILS saying so --
except on a GitHub Actions runner, which can never have it (skip, with the
same message). Every expected value is what this test typed.

Points 1-3 (version skew) are in this file; points 4-7 live in
test_presave_searched_fix_pass_relaunch.py since the 2026-10-19 split
(Yoda's size finding).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    run_git,
    run_gitmem_script,
    seed_zones_json,
)
from .presave_searched_fix_support import (  # noqa: F401  (fixtures)
    _SEARCHED,
    _ZONE1,
    _ZONE2,
    _message_of,
    _read_back,
    _save,
    format_mod,
    query_mod,
)

_SEARCHED_MULTI = "busqué rebase: nada\nWhy: esto no es un campo"
_SEARCHED_MARK = "zqx-searched-only"  # appears nowhere but in --searched

_FROZEN_VERSION = "1.47.0"


# ── the frozen 1.47.0 reader ─────────────────────────────────────────────


def _real_home():
    """The owner's real home, not the throwaway HOME the suite runs under."""
    try:
        import pwd
    except ImportError:  # Windows: no plugin cache there either
        return os.path.expanduser("~")
    return pwd.getpwuid(os.getuid()).pw_dir


def _frozen_root():
    return (Path(_real_home()) / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"
            / "unmassk-toolkit" / _FROZEN_VERSION)


@pytest.fixture
def frozen_root():
    root = _frozen_root()
    if (root / "lib" / "memory" / "format.py").is_file() and (root / "bin" / "gitmem").is_file():
        return root
    message = (
        f"FROZEN {_FROZEN_VERSION} READER NOT FOUND at {root} -- the version-skew "
        f"check (a note saved by this code must be readable by {_FROZEN_VERSION}) "
        "DID NOT RUN. Install that version in the plugin cache to run it."
    )
    if os.environ.get("GITHUB_ACTIONS") == "true":
        pytest.skip(message)
    pytest.fail(message)


def _frozen_env():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


_FROZEN_PARSE = r"""
import dataclasses, json, sys
sys.path.insert(0, sys.argv[1])
import format as fmt
note = fmt.parse_message(sys.stdin.read())
if note is None:
    print("null")
else:
    data = dataclasses.asdict(note)
    data.pop("timestamp")
    print(json.dumps(data))
"""

_FROZEN_BUILD = r"""
import json, sys
from datetime import datetime, timezone
sys.path.insert(0, sys.argv[1])
import format as fmt
import model
data = json.loads(sys.stdin.read())
data["timestamp"] = datetime(2026, 10, 19, tzinfo=timezone.utc)
for key in ("keys", "origin"):
    data[key] = tuple(data[key])
sys.stdout.write(fmt.build_message(model.Note(**data)))
"""


def _run_frozen_python(frozen_root, script, stdin_text):
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(frozen_root / "lib" / "memory")],
        input=stdin_text, capture_output=True, text=True, encoding="utf-8", env=_frozen_env(),
    )
    assert result.returncode == 0, f"frozen {_FROZEN_VERSION} process crashed: {result.stderr}"
    return result.stdout


def _frozen_parse(frozen_root, message):
    return json.loads(_run_frozen_python(frozen_root, _FROZEN_PARSE, message))


def _run_frozen_gitmem(frozen_root, args, cwd):
    result = subprocess.run(
        [sys.executable, "-B", str(frozen_root / "bin" / "gitmem"), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_frozen_env(),
    )
    return result.returncode, result.stdout, result.stderr

# ── 1. version skew: 1.47.0 reads what this code writes ──────────────────


# (id, gitmem note args after the zones, the fields this test typed)
_NEW_NOTES = [
    ("D-why-keys",
     ["D", "retire the internal wiki", "--why", "one source of truth",
      "--description", "nobody updates it", "--keys", "intranet", "confluence"],
     {"type": "D", "headline": "retire the internal wiki", "why": "one source of truth",
      "description": "nobody updates it", "keys": ["intranet", "confluence"], "quote": None,
      "awaits": None, "issue": None}),
    ("M-multiline",
     ["M", "the deploy window closes at six", "--description", "ops said so\nsecond line",
      "--stops", "no"],
     {"type": "M", "headline": "the deploy window closes at six", "why": None,
      "description": "ops said so\nsecond line", "keys": [], "quote": None,
      "awaits": None, "issue": None}),
    ("Q-quote",
     ["Q", "do canceled trials count toward seats", "--description", "finance is unsure",
      "--issue", "none", "--quote", "no abras issue para esto"],
     {"type": "Q", "headline": "do canceled trials count toward seats", "why": None,
      "description": "finance is unsure", "keys": [], "quote": "no abras issue para esto",
      "awaits": None, "issue": None}),
    ("B-awaits",
     ["B", "waiting on the vendor backfill", "--description", "report stuck",
      "--awaits", "vendor support"],
     {"type": "B", "headline": "waiting on the vendor backfill", "why": None,
      "description": "report stuck", "keys": [], "quote": None,
      "awaits": "vendor support", "issue": None}),
]

_SEARCHED_VALUES = [
    ("one-line", _SEARCHED + " " + _SEARCHED_MARK),
    ("multi-line-field-lookalike", _SEARCHED_MULTI + "\n" + _SEARCHED_MARK),
    ("starts-like-description", "Description: " + _SEARCHED_MARK),
]


def _new_note(repo, spec, searched):
    note_type, headline, *rest = spec
    return _save(repo, ["note", note_type, "--zones", _ZONE1, _ZONE2, headline, *rest,
                        "--searched", searched])


class TestFrozen147ReaderReadsNewNotes:
    """Bug caught: `searched` written as a field 1.47.0 does not know (its
    reader drops the whole note -> a machine still on 1.47.0 silently
    loses every note saved by an updated one), or written where 1.47.0
    takes it for the description (corrupted note)."""

    @pytest.mark.parametrize("searched", [v for _, v in _SEARCHED_VALUES],
                             ids=[i for i, _ in _SEARCHED_VALUES])
    @pytest.mark.parametrize("spec,typed", [(s, t) for _, s, t in _NEW_NOTES],
                             ids=[i for i, _, _ in _NEW_NOTES])
    def test_should_parse_every_field_with_the_frozen_parser(
        self, tmp_repo, frozen_root, query_mod, spec, typed, searched
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        note_id = _new_note(tmp_repo, spec, searched)

        frozen = _frozen_parse(frozen_root, _message_of(tmp_repo))

        assert frozen is not None, (
            f"{_FROZEN_VERSION} DROPS the note saved by this code: {_message_of(tmp_repo)!r}"
        )
        expected = {**typed, "id": note_id, "zone1": _ZONE1, "zone2": _ZONE2,
                    "origin": [], "replaces": None}
        assert frozen == expected
        # And the new reader still gets the search back, untouched.
        new = _read_back(tmp_repo, query_mod, note_id)
        assert new.searched == searched
        assert new.description == typed["description"]

    def test_should_show_the_note_through_the_frozen_gitmem_search(
        self, tmp_repo, frozen_root
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        note_id = _save(tmp_repo, [
            "note", "D", "--zones", _ZONE1, _ZONE2, "retire the internal wiki",
            "--why", "one source of truth", "--description", "nobody updates it",
            "--searched", _SEARCHED_MULTI + "\n" + _SEARCHED_MARK,
        ])

        rc, out, err = _run_frozen_gitmem(frozen_root, ["search", "--id", note_id], tmp_repo)

        assert rc == 0, f"{_FROZEN_VERSION} gitmem search --id failed: {out!r} {err!r}"
        assert note_id in out
        assert "retire the internal wiki" in out
        assert "nobody updates it" in out
        assert "one source of truth" in out
        assert _SEARCHED_MARK not in out, (
            f"{_FROZEN_VERSION} shows the search text as part of the note: {out!r}"
        )


class TestNewReaderReadsFrozen147Notes:
    """Bug caught: the new reader taking an old note's only
    `Description: Searched: ...` for the search (description lost), or
    dropping notes written before this version."""

    @pytest.mark.parametrize("description", [
        "plain old description",
        "Searched: this is the real description of an old note",
    ], ids=["plain", "description-starts-with-searched"])
    def test_should_read_a_note_written_by_the_frozen_writer(
        self, tmp_repo, frozen_root, query_mod, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = _run_frozen_gitmem(frozen_root, [
            "note", "M", "--zones", _ZONE1, _ZONE2, "the digest goes out on mondays",
            "--description", description, "--stops", "no",
        ], tmp_repo)
        assert rc == 0, f"{_FROZEN_VERSION} writer failed: {out!r} {err!r}"

        note = _read_back(tmp_repo, query_mod, extract_note_id(out))

        assert note.description == description
        assert note.searched is None
        assert note.headline == "the digest goes out on mondays"


# ── 2. the new reader tolerates a field it does not know ─────────────────


def _amend_head_message(repo, tmp_path, message):
    msg_file = tmp_path / "amended-message.txt"
    msg_file.write_text(message, encoding="utf-8")
    rc, _out, err = run_git(["commit", "--amend", "--allow-empty", "-F", str(msg_file)], repo)
    assert rc == 0, err


def _insert_after(message, anchor_prefix, extra_lines):
    lines = message.split("\n")
    index = next(i for i, line in enumerate(lines) if line.startswith(anchor_prefix))
    return "\n".join(lines[:index + 1] + extra_lines + lines[index + 1:])


class TestNewReaderToleratesUnknownFields:
    """Bug caught: `_parse_fields` returning None on any label it does not
    know -- the next version adds a field and this one silently loses
    every note (or the NEXT) that carries it."""

    def test_should_keep_a_note_carrying_an_unknown_field(
        self, tmp_repo, tmp_path, query_mod
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        note_id = _save(tmp_repo, [
            "note", "D", "--zones", _ZONE1, _ZONE2, "retire the internal wiki",
            "--why", "one source of truth", "--description", "nobody updates it",
            "--keys", "intranet", "--searched", _SEARCHED,
        ])
        future = _insert_after(_message_of(tmp_repo), "Why:",
                               ["Future-Field: from a newer version", " and its continuation"])
        _amend_head_message(tmp_repo, tmp_path, future)

        note = _read_back(tmp_repo, query_mod, note_id)

        assert note.why == "one source of truth"
        assert note.description == "nobody updates it"
        assert note.keys == ("intranet",)
        assert note.searched == _SEARCHED

    def test_should_show_it_through_gitmem_search(self, tmp_repo, tmp_path):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        note_id = _save(tmp_repo, [
            "note", "M", "--zones", _ZONE1, _ZONE2, "the deploy window closes at six",
            "--description", "ops confirmed it", "--stops", "no", "--searched", _SEARCHED,
        ])
        future = _message_of(tmp_repo) + "\nFuture-Field: from a newer version"
        _amend_head_message(tmp_repo, tmp_path, future)

        rc, out, err = run_gitmem_script(["search", "--id", note_id], cwd=tmp_repo)

        assert rc == 0, f"{out!r} {err!r}"
        assert "ops confirmed it" in out

    def test_should_still_reject_a_line_that_is_neither_field_nor_continuation(
        self, tmp_repo, tmp_path, format_mod
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        _save(tmp_repo, [
            "note", "M", "--zones", _ZONE1, _ZONE2, "the deploy window closes at six",
            "--description", "ops confirmed it", "--stops", "no", "--searched", _SEARCHED,
        ])
        broken = _message_of(tmp_repo) + "\nthis line is no field at all"

        assert format_mod.parse_message(broken) is None

    def test_should_keep_a_next_carrying_an_unknown_field(self, format_mod):
        model = import_lib_memory_module("model")
        from datetime import datetime, timezone
        ctx = model.ContextNote(
            headline="pick up the release tomorrow", context="tests green\nrelease pending",
            keys=("release",), timestamp=datetime(2026, 10, 19, tzinfo=timezone.utc),
        )
        message = format_mod.build_context_message(ctx)
        future = _insert_after(message, "Keys:", ["Future-Field: newer", " continuation"])

        parsed = format_mod.parse_context_message(future)

        assert parsed is not None, f"a NEXT with an unknown field was dropped: {future!r}"
        assert parsed.context == "tests green\nrelease pending"
        assert parsed.keys == ("release",)
        assert parsed.headline == "pick up the release tomorrow"


# ── 3. no searched -> the 1.47.0 bytes ───────────────────────────────────


class TestBuildWithoutSearchedUnchanged:
    """Bug caught: the writer changing the message of a note with no
    search (an empty `Description: Searched:` line, a reordered field)."""

    def test_should_write_the_same_bytes_as_the_frozen_writer(self, frozen_root, format_mod):
        model = import_lib_memory_module("model")
        fields = {
            "type": "D", "id": "D-007", "zone1": _ZONE1, "zone2": _ZONE2,
            "headline": "retire the internal wiki", "description": "nobody updates it\nat all",
            "why": "one source of truth", "keys": ["wiki", "docs"], "origin": ["M-002"],
            "replaces": None, "awaits": None, "issue": 95, "quote": None,
        }
        from datetime import datetime, timezone
        note = model.Note(**{**fields, "keys": tuple(fields["keys"]),
                             "origin": tuple(fields["origin"]),
                             "timestamp": datetime(2026, 10, 19, tzinfo=timezone.utc)})

        frozen_bytes = _run_frozen_python(frozen_root, _FROZEN_BUILD, json.dumps(fields))

        assert format_mod.build_message(note) == frozen_bytes

