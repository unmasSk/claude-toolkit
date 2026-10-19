"""The fake `gh` of the issue #95 boot-deadline tests (I-005, D-130), and
the seeding of commits that cite issues. Not a test module (no `test_`
prefix): imported by the `test_boot_deadline_*` files and
`test_boot_step2_moriarty_*` files.

THE `gh` STUB. A real executable named `gh`, first on the hook's PATH; any
directory holding a real `gh` is removed from that PATH
(`path_without_real_gh`), so no test ever reaches GitHub. It logs every
invocation and answers like the real tool for:
  - `gh api graphql -F/-f key=value ... -f query=...` -- the one request
    the check makes since the fix pass (Cerberus F1): one alias per cited
    issue. Answered by `gh_graphql_fake.py` (same double as the
    in-process tests): only the aliases asked come back, `comments(last:
    K)` vs `first: K` honoured, a missing issue comes back `null` with
    exit 1 and gh's own stderr line.
  - `gh issue view N --json <fields>` (the old per-issue call), kept so a
    regression to N+1 calls fails on TIME, not on an unsupported command.
Anything else (`issue list`, `--jq`, `--search`...) exits 2 with
"unsupported invocation" -- if the implementation needs another command,
the stub is extended by a fresh Dante, never guessed at here.
Every issue's `updatedAt` is a year in the future on purpose: "last
activity" is the last comment, or the creation date when there is none
(health_plans.py docstring). An implementation that reads `updatedAt`
instead would hide every unreflected commit, and the correctness test
goes red.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from .conftest import path_without_real_gh, run_git

_PAST_CREATED = "2020-01-01T00:00:00Z"
_PAST_COMMENT = "2021-06-01T00:00:00Z"


def _future_iso():
    return (datetime.now(timezone.utc) + timedelta(days=365)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# --------------------------------------------------------------------------
# The gh stub
# --------------------------------------------------------------------------

_GH_STUB_SOURCE = r'''#!/usr/bin/env python3
"""Fake gh -- Dante, issue #95 test double. Mimics the real tool's
answers for `api graphql` and `issue view`; never contacts GitHub."""
import json
import os
import sys
import time

cfg_path = os.environ["GH_STUB_CONFIG"]
with open(cfg_path, encoding="utf-8") as fh:
    cfg = json.load(fh)
args = sys.argv[1:]
with open(cfg["log"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")

time.sleep(cfg["latency"])
mode = cfg["mode"]
if mode == "hang":
    time.sleep(cfg["hang_seconds"])
elif mode == "fail":
    sys.stderr.write("HTTP 502: Bad Gateway (https://api.github.com/graphql)\n")
    sys.exit(1)
elif mode == "garbage":
    sys.stdout.write("<html><body>rate limited</body></html>\n")
    sys.exit(0)
elif mode == "wrong_shape":
    sys.stdout.write('{"data": null}\n')
    sys.exit(0)

issues = {int(k): v for k, v in cfg["issues"].items()}
KNOWN_FIELDS = {"number", "state", "title", "createdAt", "updatedAt", "comments"}


def unsupported():
    sys.stderr.write(
        "fake gh (Dante #95 test double): unsupported invocation " + repr(args) + "\n"
    )
    sys.exit(2)


def parse_flags(rest, value_flags):
    out = {}
    i = 0
    while i < len(rest):
        token = rest[i]
        if "=" in token and token.startswith("--"):
            name, value = token.split("=", 1)
            i += 1
        else:
            name = token
            if i + 1 >= len(rest):
                unsupported()
            value = rest[i + 1]
            i += 2
        if name not in value_flags:
            unsupported()
        out[value_flags[name]] = value
    return out


def project(number, fields):
    unknown = [f for f in fields if f not in KNOWN_FIELDS]
    if unknown:
        sys.stderr.write("Unknown JSON field: " + repr(unknown[0]) + "\n")
        sys.exit(1)
    record = dict(issues[number])
    record["number"] = number
    return {f: record[f] for f in fields}


if args[:2] == ["issue", "view"] and len(args) >= 3:
    number_text = args[2].lstrip("#")
    if not number_text.isdigit():
        unsupported()
    flags = parse_flags(args[3:], {"--json": "json", "--repo": "repo", "-R": "repo"})
    if "json" not in flags:
        unsupported()
    number = int(number_text)
    if number not in issues:
        sys.stderr.write(
            "GraphQL: Could not resolve to an issue or pull request with the "
            "number of " + str(number) + ". (repository.issue)\n"
        )
        sys.exit(1)
    sys.stdout.write(json.dumps(project(number, flags["json"].split(","))))
    sys.exit(0)

if args[:2] == ["api", "graphql"]:
    sys.path.insert(0, cfg["helper_dir"])
    import gh_graphql_fake

    rc, out, err = gh_graphql_fake.answer(args, issues)
    sys.stdout.write(out)
    sys.stderr.write(err)
    sys.exit(rc)

unsupported()
'''


class GhStub:
    """A `gh` executable on disk plus its configuration and call log."""

    def __init__(self, tmp_path):
        self.dir = tmp_path / "fake-gh-bin"
        self.dir.mkdir()
        exe = self.dir / "gh"
        exe.write_text(_GH_STUB_SOURCE, encoding="utf-8")
        exe.chmod(0o755)
        self.config_path = tmp_path / "gh-stub-config.json"
        self.log_path = tmp_path / "gh-stub-calls.log"
        self.configure()

    def configure(self, *, issues=None, mode="ok", latency=0.0, hang_seconds=0.0):
        self.config_path.write_text(
            json.dumps(
                {
                    "log": str(self.log_path),
                    "helper_dir": str(Path(__file__).parent),
                    "mode": mode,
                    "latency": latency,
                    "hang_seconds": hang_seconds,
                    "issues": {str(k): v for k, v in (issues or {}).items()},
                }
            ),
            encoding="utf-8",
        )

    def env(self):
        return {
            "PATH": str(self.dir) + os.pathsep + path_without_real_gh(),
            "GH_STUB_CONFIG": str(self.config_path),
        }

    def calls(self):
        if not self.log_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


@pytest.fixture
def gh_stub(tmp_path):
    return GhStub(tmp_path)


def _issue(*, state="OPEN", created=_PAST_CREATED, comment_dates=(), title="fake issue title"):
    return {
        "state": state,
        "title": title,
        "createdAt": created,
        "updatedAt": _future_iso(),
        "comments": [
            {"createdAt": d, "body": "progress note", "author": {"login": "bex"}}
            for d in comment_dates
        ],
    }


def _all_unreflected(numbers):
    """Every issue created in the past with no comment: every commit that
    cites it counts as unreflected."""
    return {n: _issue() for n in numbers}


# --------------------------------------------------------------------------
# Seeding the disposable repo
# --------------------------------------------------------------------------


def _cite(repo, issue_number, times=1):
    for i in range(times):
        rc, _out, err = run_git(
            [
                "commit",
                "--allow-empty",
                "-m",
                f"work on #{issue_number} ({i})\n\nIssue: #{issue_number}",
            ],
            repo,
        )
        assert rc == 0, f"seeding commit failed: {err}"


def _seed_citations(repo, citations):
    """`citations`: {issue_number: number of commits citing it}."""
    for number, times in citations.items():
        _cite(repo, number, times)

