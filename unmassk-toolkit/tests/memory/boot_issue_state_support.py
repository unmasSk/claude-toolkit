"""In-process GitHub double and section readers for the #89 boot report
tests (step 4.1). Not a test module: pytest does not collect it.

`patch_gh` intercepts only `gh` invocations of the shared `subprocess.run`
(the `git` calls pass through to the real one) and answers them with
`gh_graphql_fake.answer` -- the same double the boot hook stub uses, so
the answer is shaped like GitHub's, never like the code under test.
"""

import re
import subprocess

from .gh_graphql_fake import answer as gh_graphql_answer

PAST = "2020-01-01T00:00:00Z"
GH_FAILURE = "HTTP 502: Bad Gateway (https://api.github.com/graphql)"


def issue_record(state, title):
    """One GitHub issue as `gh_graphql_fake` expects it, no comments."""
    return {
        "state": state,
        "title": title,
        "createdAt": PAST,
        "updatedAt": PAST,
        "comments": [],
    }


def patch_gh(monkeypatch, issues=None, fail=False):
    """Route every `gh` call to the double. Returns the list of `gh`
    argv lists seen, so a test can count the calls."""
    real_run = subprocess.run
    calls = []

    def _fake_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd and cmd[0] == "gh":
            calls.append(list(cmd))
            if fail:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=1, stdout="", stderr=GH_FAILURE + "\n"
                )
            returncode, stdout, stderr = gh_graphql_answer(cmd[1:], issues or {})
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode, stdout=stdout, stderr=stderr
            )
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    return calls


def counts_section(rendered):
    """Lines from `COUNTS` up to (not including) the open-questions title."""
    lines = rendered.splitlines()
    start = lines.index("COUNTS")
    end = next(
        i for i, line in enumerate(lines) if i > start and line.startswith("❓ OPEN QUESTIONS")
    )
    return lines[start:end]


def lines_naming_issue(section, number):
    """Lines of `section` that name issue `#number` (not `#number5`)."""
    pattern = re.compile(rf"#{number}(?!\d)")
    return [line for line in section if pattern.search(line)]


def issue_numbers_in(section):
    """Every `#N` named in `section`, in order of appearance."""
    return [int(n) for line in section for n in re.findall(r"#(\d+)", line)]


def restrictions_section(rendered):
    """Lines from the RESTRICTIONS title up to the next blank-then-COUNTS."""
    lines = rendered.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("⚠️ RESTRICTIONS"))
    end = lines.index("COUNTS")
    return lines[start:end]
