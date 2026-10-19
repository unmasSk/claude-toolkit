"""Fix pass after Moriarty's attack on issue #95 step 2 (DECEPTION T3):
the first-message reminder still told Claude to "show the user a boot
summary from the SessionStart output above". Since D-007 the briefing is
NOT in the hook output -- only its path is, on the `[memory]` lines -- and
step 2a rewrote the CLAUDE.md managed block to say exactly that. The
reminder's own comment says it "changes with" the block; it did not.

Two separately written texts are compared here: what the reminder prints
on the session's first message (run as Claude Code runs it, from
hooks.json) and the managed block every project's CLAUDE.md carries
(lib/managed_blocks.py). They must name the same place for the briefing.
"""

import os
import sys

from conftest import SOURCE_ROOT
from test_d124_per_message_checklist import NEUTRAL, POSIX_SHELL_ONLY, _make_installed_repo, _run

# _run goes through d124's shell=True harness; its skip is not inherited by import.
pytestmark = POSIX_SHELL_ONLY

sys.path.insert(0, os.path.join(SOURCE_ROOT, "lib"))
import managed_blocks  # noqa: E402


def _toolkit_block():
    bodies = [b["body"] for b in managed_blocks.BLOCKS if "unmassk-toolkit Active" in b["body"]]
    assert len(bodies) == 1, "setup invalid: no single unmassk-toolkit managed block"
    return bodies[0]


def _flat(text):
    """Lower case, every run of whitespace one space: both texts wrap
    their lines at different points."""
    return " ".join(text.lower().split())


def _first_message_reminder(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    repo = _make_installed_repo(tmp_path, booted=False)
    rc, out, err = _run(repo, str(home), NEUTRAL)
    assert rc == 0, err
    assert 'skill="unmassk-memory"' in out, (
        "setup invalid: no first-message block printed\n" + out
    )
    return out


class TestFirstMessageReminderPointsToTheReport:
    def test_should_not_send_claude_to_the_sessionstart_output_for_the_summary(self, tmp_path):
        # Bug caught: Claude looks for a summary in the hook output, finds
        # only two pointer lines, and either invents a menu or reports a
        # boot failure that did not happen.
        out = _first_message_reminder(tmp_path)

        assert "SessionStart output above" not in out, out

    def test_should_name_the_same_place_for_the_briefing_as_the_managed_block(self, tmp_path):
        # Bug caught: the two texts Claude reads at the start of a session
        # disagree on where the briefing lives -- or one forgets what to
        # do when no report arrived (the boot failed and must be said).
        block = _flat(_toolkit_block())
        anchors = ("[memory]", "boot report", "boot failed")
        assert all(a in block for a in anchors), (
            "setup invalid: the managed block no longer says this -- update "
            "the anchors to what it says now\n" + block
        )

        out = _flat(_first_message_reminder(tmp_path))

        missing = [a for a in anchors if a not in out]
        assert missing == [], (
            f"the first-message reminder lacks {missing}, which the managed "
            "block says about the briefing\n" + out
        )
