"""
Round-trip FIDELITY test for `Memo: deadend/<subsystem>` — the dead-end
research residue design.

Design decision this test locks in (Cerberus finding this session, "cero
test cubre la forma real"): dead-end investigation residue is stored as
`memo(deadend/<subsystem>)` in exactly ONE physical line of the `Memo:`
trailer, never in the commit body, because:

  - lib/recall.py::_format_block() only ever emits `entry["text"]`, which
    is `trailers[kind]` — the raw TRAILER VALUE. The commit body is never
    read by the recall path at all.
  - lib/parsing.py::parse_trailers() (bottom-up, validation-time) and
    lib/parsing.py::scan_trailers_memory() (full-body, recall-time) both
    stop treating a line as a trailer the moment it isn't one — prose in
    the body never becomes part of a trailer's value.

The whole design depends on that ONE `Memo:` line surviving byte-for-byte
from the commit that writes it to the string recall() hands back to Bilbo.
No existing test exercised the REAL shape of a deadend value (`; `-joined
clauses, backtick-quoted symbols, an `@<sha>` anchor) through both
parse_trailers() and recall() — this closes that gap.

Threat model (per this project's CLAUDE.md / unmassk-standards §34): this
is producer -> consumer data-integrity, not an external attacker. Producer
= a real `Memo:` trailer written by a commit. Consumers = parse_trailers()
(validation-time read) and recall() (Bilbo-facing read). Nothing here
simulates malicious input.
"""

import os
import sys

from conftest import SOURCE_ROOT, git_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from parsing import parse_trailers
from recall import recall


# The exact realistic deadend value under test: ONE physical line (no
# embedded "\n" anywhere in this literal — adjacent string-literal
# concatenation below does not insert one), "; "-joined ruled-out clauses,
# backtick-quoted symbols, and an "@<sha>" anchor at the end. This is the
# literal shape decided for the dead-end memory feature.
_DEADEND_VALUE = (
    "deadend - asked: donde se valida la firma | "
    "ruled out: NOT `validarActa()` (solo estado); "
    "NOT `authMiddleware` (no toca acta) | @fdfab09"
)

# Nonce marking prose that lives ONLY in the commit body, above the
# trailer block — never a trailer line itself. Used to prove the negative:
# this text must never reach recall()'s output, only the Memo: line does.
_BODY_ONLY_NONCE = "xyzbodyonlyneversurvives"


def _make_repo(tmp_path):
    """Minimal git repo, no toolkit install required (matches test_recall.py)."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, body):
    git_cmd(["commit", "--allow-empty", "-m", subject + "\n\n" + body], repo)


class TestDeadendMemoRoundTripFidelity:
    """One test, one behavior: a `Memo: deadend/...` line survives
    parse_trailers() and recall() completely intact, while body prose in
    the SAME commit never leaks into either."""

    def test_deadend_memo_line_survives_parse_and_recall_intact(self, tmp_path):
        repo = _make_repo(tmp_path)

        subject = "📌 memo(deadend/auth): investigacion de firma agotada"
        # Realistic shape: explanatory prose ABOVE the trailer block (what a
        # human might assume "also" gets remembered), a blank line, then the
        # single Memo: trailer line — the ONLY thing the design relies on.
        body = (
            f"{_BODY_ONLY_NONCE} intentamos varias rutas para dar con el "
            "punto de validacion de la firma antes de anotar el trailer.\n"
            "\n"
            f"Memo: {_DEADEND_VALUE}"
        )
        _commit(repo, subject, body)

        # ── (1) parse_trailers() extracts the COMPLETE, intact value ──────
        # Exercises the real bottom-up trailer scan (validation-time path)
        # against the exact message git would see: subject + blank + body.
        full_message = subject + "\n\n" + body
        parsed = parse_trailers(full_message)
        assert parsed.get("Memo") == _DEADEND_VALUE, (
            "parse_trailers() must return the Memo value byte-for-byte "
            "intact -- not truncated at the first ';', '-', '|', or "
            f"backtick. got: {parsed.get('Memo')!r}"
        )

        # ── (2) recall() returns that SAME line intact, unabbreviated ─────
        # Query mixes scope routing (deadend/auth) with terms drawn from the
        # trailer's own text -- what Bilbo would realistically search with.
        result = recall(
            "firma validarActa authMiddleware",
            scope="deadend/auth",
            _repo_dir=repo,
        )
        assert _DEADEND_VALUE in result, (
            "recall() must hand back the deadend Memo value fully intact -- "
            "what was written to the trailer is what must come back through "
            f"recall(). got:\n{result!r}"
        )

        # ── (3) Negative control: body-only prose never reaches recall() ──
        assert _BODY_ONLY_NONCE not in result, (
            "Prose placed only in the commit BODY (above the trailer, never "
            "itself a trailer line) must not survive to recall() -- this is "
            "exactly the failure mode the deadend design avoids by relying "
            f"on a single trailer line instead of the commit body. got:\n{result!r}"
        )
