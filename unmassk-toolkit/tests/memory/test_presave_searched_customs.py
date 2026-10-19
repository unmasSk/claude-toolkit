"""#95 part 2c contract (D-098, D-124), points 4 and 5 on the hook side:
customs.py (PreToolUse/Bash) blocks a `gitmem note` / `gitmem rule` call
that lacks `--searched`, with the D-098 question, before the command runs;
and lets everything else through. Split out of
test_presave_searched_contract.py (2026-10-19, Yoda's size finding),
whose docstring carries the sources and the declared assumptions (the
hook is tested with customs explicitly ON).
"""

import shlex

import pytest

from .conftest import seed_config_json
from .presave_searched_contract_support import (
    _D098_QUESTION,
    _RULE_NEW_QUOTE,
    _RULE_NEW_TEXT,
    _RULE_QUOTE,
    _RULE_TEXT,
    _SEARCHED_OTHER,
    _ZONE1,
    _ZONE2,
    _norm,
    _run_customs,
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

