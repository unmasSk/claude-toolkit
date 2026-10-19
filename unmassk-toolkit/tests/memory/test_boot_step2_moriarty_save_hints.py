"""Fix pass after Moriarty's attack on issue #95 step 2 -- the two
save-command findings, each through the door the owner uses (the
PreToolUse customs hook, the boot report a new project gets). Split out
of test_boot_step2_moriarty_fix_pass.py (2026-10-19, Yoda's size
finding), where the boot-hook findings stay.

  T3  customs asked "did you search?" on `gitmem note --help` and
      `gitmem rule help`, which save nothing.
  T3  the new-project boot report taught a `gitmem note` command without
      the now-mandatory `--searched`: copied literally, it bounces.

Windows: skipped like every fake-`gh` test in this suite (the boot report
tests run the SessionStart hook with the fake `gh`).
"""

import json
import shlex

import pytest

from .boot_hook_gh_stub import gh_stub  # noqa: F401  (a fixture)
from .boot_hook_harness import POSIX_ONLY, _assert_full_briefing, _run_boot_hook
from .conftest import (
    run_git,
    run_gitmem_script,
    run_hook_with_payload,
    seed_config_json,
)

pytestmark = POSIX_ONLY


# ==========================================================================
# T3 -- customs does not ask "did you search?" when nothing is saved
# ==========================================================================


def _run_customs(repo, command):
    rc, out, err = run_hook_with_payload(
        "customs.py",
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": repo},
        cwd=repo,
    )
    assert rc == 0, f"customs.py always exits 0 -- rc={rc} stderr={err!r}"
    return json.loads(out)


def _repo_state(repo):
    head = run_git(["rev-parse", "HEAD"], repo)[1]
    status = run_git(["status", "--porcelain", "--untracked-files=all"], repo)[1]
    return head, status


# Hand-written from Moriarty's report and rule.py's usage message (a
# separate source from customs.py's own word list): commands that only ask
# for help or name a single command word. Each is paired below with what
# the REAL command does, so the test never trusts either side alone.
_NOT_SAVES = [
    "gitmem note --help",
    "gitmem note -h",
    "gitmem rule --help",
    "gitmem rule -h",
    "gitmem rule help",
    "gitmem rule add",
    "gitmem rule show",
    "gitmem rule find",
    "gitmem rule read",
    "gitmem rule verify",
    "gitmem rule rebuild",
]


class TestCustomsDoesNotGateHelp:
    @pytest.mark.parametrize("command", _NOT_SAVES)
    def test_should_approve_when_the_real_command_saves_nothing(self, tmp_repo, command):
        # Bug caught (Moriarty ABUSE): `sub == "note"` counted as a save
        # whatever followed, and `help` was taken as rule text -- the
        # owner gets the D-098 question for looking up the usage.
        seed_config_json(tmp_repo, customs_enabled=True)
        before = _repo_state(tmp_repo)
        run_gitmem_script(shlex.split(command)[1:], cwd=tmp_repo)
        assert _repo_state(tmp_repo) == before, (
            f"setup invalid: {command!r} DID change the repo, it is a save"
        )

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "approve", (
            f"{command!r} saves nothing and must pass -- got {decision!r}"
        )

    def test_should_still_block_a_real_rule_that_starts_with_help(self, tmp_repo):
        # Bug caught: the help exemption matching the first WORD of the
        # rule text, so a real rule beginning with "help" slips through
        # without the search question.
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            'gitmem rule "help newcomers by pointing at the rules file first" '
            '--kind user --quote "que lean las reglas primero"'
        )

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "block", f"got {decision!r}"
        assert "--searched" in decision.get("reason", "")


# ==========================================================================
# T3 -- the save command a new project's boot report teaches really saves
# ==========================================================================

_SEARCHED_ANSWER = 'busqué "first note" en la memoria: no hay nada escrito'
_HEADLINE = "the first memo of a brand new project"


def _printed_command(report, program_words):
    """The first command block of the report that starts with
    `program_words` (e.g. `gitmem note`), with its `\\` continuations
    joined, split as a shell would."""
    lines = report.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(program_words):
            block = [line]
            while block[-1].rstrip().endswith("\\") and i + len(block) < len(lines):
                block.append(lines[i + len(block)])
            text = " ".join(part.rstrip().rstrip("\\") for part in block)
            return shlex.split(text)
    return None


def _fill(tokens, zones):
    """Fill the placeholders the way a person would, nothing more:
    `<TIPO>` -> M, `<zonaN>` -> the zones that exist, `<yes|no>` -> no,
    `"..."` -> real text, the Spanish example headline -> an English one,
    any other `<...>` (the searched answer) -> a real answer."""
    filled = []
    for token in tokens:
        if token == "<TIPO>":
            filled.append("M")
        elif token.startswith("<zona"):
            filled.append(zones[int(token.strip("<>zona")) - 1])
        elif token == "<nombre>":
            filled.append(zones.pop(0))
        elif token == "<yes|no>":
            filled.append("no")
        elif token == "...":
            filled.append("written while following the boot report literally")
        elif token == "titular en inglés":
            filled.append(_HEADLINE)
        elif "<" in token and ">" in token:
            filled.append(_SEARCHED_ANSWER)
        else:
            filled.append(token)
    return filled


def _obey(repo, tokens):
    assert tokens[0] == "gitmem", tokens
    return run_gitmem_script(tokens[1:], cwd=repo)


def _assert_note_saved(repo, before_head, out, err):
    head = run_git(["rev-parse", "HEAD"], repo)[1]
    assert head != before_head, (
        "the command the boot report teaches saved nothing -- copied "
        f"literally it bounces:\nstdout={out}\nstderr={err}"
    )
    message = run_git(["log", "-1", "--format=%B"], repo)[1]
    assert _HEADLINE in message and _SEARCHED_ANSWER in message, message


class TestBootReportTeachesASaveThatWorks:
    def test_should_save_the_first_note_when_the_setup_missing_hint_is_obeyed(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Moriarty DECEPTION): the "memory not set up" footer
        # taught `gitmem note ... --stops <yes|no>` with no --searched;
        # --searched became mandatory in 2c, so the first save a new
        # project is told to make bounces with "falta --searched".
        run = _run_boot_hook(tmp_repo, tmp_path / "boot", gh_stub, kill_after=60)
        _assert_full_briefing(run)
        report = run.report()
        zone_cmd = _printed_command(report, "gitmem zones add")
        note_cmd = _printed_command(report, "gitmem note")
        assert zone_cmd and note_cmd, (
            "setup invalid: the new project's report does not show the "
            "setup-missing footer\n" + report
        )
        zone_names = ["billing", "support"]
        for name in zone_names:
            rc, out, err = _obey(tmp_repo, _fill(zone_cmd, [name]))
            assert rc == 0, f"zones add as taught failed: {out}{err}"
        before = run_git(["rev-parse", "HEAD"], tmp_repo)[1]

        rc, out, err = _obey(tmp_repo, _fill(note_cmd, list(zone_names)))

        _assert_note_saved(tmp_repo, before, out, err)

    def test_should_save_the_first_note_when_the_zero_notes_hint_is_obeyed(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Moriarty DECEPTION): same gap in the other footer,
        # "zero is not silence: the first note is saved like this".
        first = _run_boot_hook(tmp_repo, tmp_path / "install", gh_stub, kill_after=60)
        _assert_full_briefing(first)
        zone_names = ["billing", "support"]
        for name in zone_names:
            rc, out, err = run_gitmem_script(
                ["zones", "add", name, "--description", f"{name} work"], cwd=tmp_repo
            )
            assert rc == 0, f"setup: zones add failed: {out}{err}"
        run = _run_boot_hook(tmp_repo, tmp_path / "boot", gh_stub, kill_after=60)
        _assert_full_briefing(run)
        report = run.report()
        assert _printed_command(report, "gitmem zones add") is None, (
            "setup invalid: the report still shows the setup-missing footer\n" + report
        )
        note_cmd = _printed_command(report, "gitmem note")
        assert note_cmd, "setup invalid: no first-note footer\n" + report
        before = run_git(["rev-parse", "HEAD"], tmp_repo)[1]

        rc, out, err = _obey(tmp_repo, _fill(note_cmd, list(zone_names)))

        _assert_note_saved(tmp_repo, before, out, err)

