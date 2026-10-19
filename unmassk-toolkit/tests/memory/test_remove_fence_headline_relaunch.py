"""RED contract (test-first, Short): the headline-too-long rejection that
`gitmem remove <I-ID> "<reason>" --restriction new --restriction-text
"<more than 80 chars>"` prints must relaunch `gitmem remove`, not
`gitmem note <TIPO>`.

THE BUG (reproduced by running the real CLI): `bin/memory/remove.py`
`_guard_restriction_new()` runs `validator.validate_note()` on the candidate
fence and prints each rejection verbatim with `rejection_.render_terminal()`.
The headline rejection comes from `lib/memory/validator.py`
`validate_headline()`, whose relaunch is the generic
`gitmem note <TIPO> --zones <zona1> <zona2> "<titular de hasta 80 caracteres>"
--description "..."`. Whoever pastes that does NOT close the incident and
writes a loose note with no `Origin:` -- the close and its fence drift apart.

THE CONTRACT (decided by the owner, see the task of 2026-10-19):
- reached through `gitmem remove ... --restriction new`, the Relanza block
  of the headline rejection carries a `gitmem remove` command with the real
  incident id, the real reason, `--restriction new`,
  `--restriction-text "<titular de hasta 80 caracteres>"` and, when it was
  given, `--why "<the real why>"`; and it does NOT carry `gitmem note <TIPO>`;
- the plain `gitmem note` path keeps its `gitmem note` relaunch unchanged;
- nothing is committed or closed when the guard rejects.

TWO THINGS WRITTEN APART, COMPARED: every expected value (incident id,
reason, why, the 80-char placeholder, the `gitmem note` relaunch line) is
typed in this file or comes from the seed, never read from the code under
test; it is compared with what the real CLI prints on stderr. The obeyed
relaunch is then RUN as printed (only the headline placeholder replaced by
this test's own short text) and its effect is read back from git and the
real index readers.

Driven through `bin/gitmem` as a subprocess on a disposable temp git repo
(`tmp_repo`), never this repository. No external attacker in this project:
what is watched is the system leaving an incident and its fence apart.
"""

import os
import shlex

import pytest

from .conftest import (
    SEARCHED_ANSWER,
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_note_via_script,
    seed_zones_json,
)

# The owner's limit (80) and the placeholder wording are typed here on
# purpose, not imported from vocabulary/validator: the expected text must not
# be read from the code under test.
_HEADLINE_PLACEHOLDER = "<titular de hasta 80 caracteres>"
_TOO_LONG = "F" * 96
_REASON = "MARK_REASON fixed by capping the retry loop"
_WHY = "MARK_WHY retries without a cap keep taking the API down"
_SHORT_FENCE = "MARK_FENCE retry loops must always carry a hard cap"
_NOTE_RELAUNCH = (
    'gitmem note <TIPO> --zones <zona1> <zona2> '
    '"<titular de hasta 80 caracteres>" --description "..."'
)


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def query():
    return import_lib_memory_module("query")


def _seed_incident(repo, zone1, zone2):
    seed_zones_json(repo, [zone1, zone2])
    rc, out, err = seed_note_via_script(
        repo, "I", zone1, zone2, "MARK the payments API went down from a retry loop",
        description="MARK_ROOTCAUSE a stray retry loop hammered the payments API",
        work="no",
    )
    assert rc == 0, f"setup invalid: incident not seeded: {out!r} {err!r}"
    incident_id = extract_note_id(out)
    assert incident_id and incident_id.startswith("I-"), f"setup invalid: {out!r}"
    return incident_id


def _remove_args(incident_id, *, why):
    args = [
        "remove", incident_id, _REASON,
        "--restriction", "new",
        "--restriction-text", _TOO_LONG,
    ]
    if why is not None:
        args += ["--why", why]
    return args


def _headline_relaunch_lines(output):
    """The command lines of the Relanza block of the ONE headline rejection.

    A rendered rejection is `⛔ <title>`, body, then `Relanza:` and one
    two-space-indented line per command. Several rejections may print one
    after another; only the block whose title names the headline counts.
    """
    blocks = output.split("⛔ ")[1:]
    headline_blocks = [b for b in blocks if b.startswith("el titular tiene 96 caracteres")]
    assert len(headline_blocks) == 1, (
        f"expected exactly one headline rejection in the output:\n{output}"
    )
    lines = headline_blocks[0].splitlines()
    assert "Relanza:" in lines, f"headline rejection without a Relanza block:\n{output}"
    after = lines[lines.index("Relanza:") + 1:]
    commands = []
    for line in after:
        if not line.startswith("  "):
            break
        commands.append(line.strip())
    assert commands, f"empty Relanza block:\n{output}"
    return commands


def _remove_command_tokens(commands, output):
    removes = [shlex.split(c) for c in commands if c.startswith("gitmem remove ")]
    assert len(removes) == 1, (
        f"the headline rejection of `gitmem remove --restriction new` must "
        f"relaunch exactly one `gitmem remove` command; Relanza had "
        f"{commands!r}\nfull output:\n{output}"
    )
    return removes[0]


def _flag_value(tokens, flag):
    assert tokens.count(flag) == 1, f"{flag} must appear exactly once: {tokens!r}"
    return tokens[tokens.index(flag) + 1]


def _run_rejected_remove(repo, incident_id, *, why):
    head_before = run_git(["rev-parse", "HEAD"], repo)[1]
    rc, out, err = run_gitmem_script(_remove_args(incident_id, why=why), cwd=repo)
    assert rc == 1, f"a 96-char fence must bounce the whole command: {out!r} {err!r}"
    assert "Traceback" not in out + err
    assert run_git(["rev-parse", "HEAD"], repo)[1] == head_before, (
        "the guard rejected, yet something was committed"
    )
    return out + err


class TestHeadlineRelaunchFromRemoveRelaunchesRemove:
    """New behaviour -- RED today: the block says `gitmem note <TIPO>`."""

    def test_should_relaunch_gitmem_remove_with_id_reason_and_why_when_why_was_given(
        self, tmp_repo,
    ):
        # Bug caught: the generic validator relaunch (gitmem note <TIPO>) is
        # printed verbatim, so pasting it never closes the incident.
        incident_id = _seed_incident(tmp_repo, "payments", "retries")
        output = _run_rejected_remove(tmp_repo, incident_id, why=_WHY)

        commands = _headline_relaunch_lines(output)
        assert not any("gitmem note <TIPO>" in c for c in commands), (
            f"the remove path must not propose `gitmem note <TIPO>`: {commands!r}"
        )
        tokens = _remove_command_tokens(commands, output)
        assert tokens[:4] == ["gitmem", "remove", incident_id, _REASON], tokens
        assert _flag_value(tokens, "--restriction") == "new"
        assert _flag_value(tokens, "--restriction-text") == _HEADLINE_PLACEHOLDER
        assert _flag_value(tokens, "--why") == _WHY

    def test_should_relaunch_gitmem_remove_with_id_and_reason_when_no_why_was_given(
        self, tmp_repo,
    ):
        # Bug caught: the fix only covers the --why variant of the command.
        incident_id = _seed_incident(tmp_repo, "payments", "retries2")
        output = _run_rejected_remove(tmp_repo, incident_id, why=None)

        commands = _headline_relaunch_lines(output)
        assert not any("gitmem note <TIPO>" in c for c in commands), commands
        tokens = _remove_command_tokens(commands, output)
        assert tokens[:4] == ["gitmem", "remove", incident_id, _REASON], tokens
        assert _flag_value(tokens, "--restriction") == "new"
        assert _flag_value(tokens, "--restriction-text") == _HEADLINE_PLACEHOLDER

    def test_should_close_the_incident_and_birth_its_fence_when_the_relaunch_is_obeyed(
        self, tmp_repo, indexes, query,
    ):
        # Bug caught: a relaunch that looks right but cannot be pasted (wrong
        # flag, lost reason, a placeholder left elsewhere) -- the incident
        # stays open, or closes without its fence.
        zones = ("payments", "retries3")
        incident_id = _seed_incident(tmp_repo, *zones)
        output = _run_rejected_remove(tmp_repo, incident_id, why=_WHY)

        tokens = _remove_command_tokens(_headline_relaunch_lines(output), output)
        filled = list(tokens)
        filled[filled.index("--restriction-text") + 1] = _SHORT_FENCE
        rc, out, err = run_gitmem_script(filled[1:], cwd=tmp_repo)
        assert rc == 0, f"obeying the printed relaunch failed: {out!r} {err!r}"

        pm = pm_path(tmp_repo)
        assert not any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm))
        archived = [a for a in indexes.read_archive(pm) if a.id == incident_id]
        assert len(archived) == 1, archived
        fences = [l for l in indexes.read("RESTRICTIONS.md", pm) if l.headline == _SHORT_FENCE]
        assert len(fences) == 1, fences
        previous = os.getcwd()
        os.chdir(tmp_repo)
        try:
            fence = query.by_id(fences[0].id)
        finally:
            os.chdir(previous)
        assert fence is not None
        assert (fence.type, fence.headline, fence.description, fence.why) == (
            "R", _SHORT_FENCE, _SHORT_FENCE, _WHY
        )
        assert fence.origin == (incident_id,)
        assert (fence.zone1, fence.zone2) == zones


class TestGuards:
    """Green today, on purpose: they must stay green after the fix."""

    def test_should_keep_the_incident_live_and_files_untouched_when_the_guard_rejects(
        self, tmp_repo, indexes,
    ):
        # Bug caught: a fix that rebuilds the rejection after notes.close()
        # already ran, closing the incident before bouncing.
        incident_id = _seed_incident(tmp_repo, "payments", "retries4")
        pm = pm_path(tmp_repo)
        before = {
            name: (pm / name).read_bytes()
            for name in ("INCIDENTS.md", "ARCHIVED.md", "RESTRICTIONS.md")
        }

        output = _run_rejected_remove(tmp_repo, incident_id, why=_WHY)

        assert "archivada" not in output.lower(), output
        assert any(line.id == incident_id for line in indexes.read("INCIDENTS.md", pm))
        for name, content in before.items():
            assert (pm / name).read_bytes() == content, f"{name} changed"

    def test_should_keep_the_gitmem_note_relaunch_when_the_long_headline_comes_from_note(
        self, tmp_repo,
    ):
        # Bug caught: a fix made inside validate_headline() for everyone,
        # turning the plain note relaunch into a remove command.
        seed_zones_json(tmp_repo, ["payments", "retries5"])
        head_before = run_git(["rev-parse", "HEAD"], tmp_repo)[1]

        rc, out, err = seed_note_via_script(
            tmp_repo, "R", "payments", "retries5", _TOO_LONG,
            description="MARK_DESC a fence whose headline is too long", why=_WHY,
            stops="yes",  # answers the pain question so only the headline bounces
        )

        assert rc != 0, f"a 96-char headline must bounce: {out!r} {err!r}"
        # note.py carries the caller's own --searched answer onto every
        # relaunch (D-098); that answer is this test's seed input.
        relaunch = _headline_relaunch_lines(out + err)
        assert [shlex.split(c) for c in relaunch] == [
            shlex.split(_NOTE_RELAUNCH) + ["--searched", SEARCHED_ANSWER]
        ], relaunch
        assert "gitmem remove" not in out + err
        assert run_git(["rev-parse", "HEAD"], tmp_repo)[1] == head_before
