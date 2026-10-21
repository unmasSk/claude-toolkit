"""What the boot needs from the remote: fetch (never pull), the branch with the latest commit, and divergence.

A network failure never stops the boot, but it is reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import re
import sys

import boot_common
import gitcmd
import timefmt  # re-exported for boot.py, and used below

# Network call: more time than a local read, but bounded.
FETCH_TIMEOUT = 10

# Non-interactive git: no terminal prompt, no password dialog (askpass must be a bare
# PATH name outside Windows), batch-mode ssh, and every credential helper disabled.
_ASKPASS_FAILFAST = "cmd /c exit 1" if sys.platform == "win32" else "false"

_HARDENED_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": _ASKPASS_FAILFAST,
    "SSH_ASKPASS": _ASKPASS_FAILFAST,
    "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "credential.helper",
    "GIT_CONFIG_VALUE_0": "",
}

# Unit separator: a process argument cannot hold a NUL byte.
_FIELD_SEP = "\x1f"
# Epoch seconds: Python 3.10 `fromisoformat` cannot read iso8601-strict's `Z` suffix.
_REF_FORMAT = _FIELD_SEP.join(
    (
        "%(committerdate:unix)",
        "%(refname:short)",
        "%(objectname:short)",
        "%(symref)",
        "%(contents:subject)",
    )
)

# Refs requested before filtering: the first ones may be skipped.
_REF_CANDIDATES = 20


@dataclass(frozen=True)
class Activity:
    """The branch, commit and time of the most recent work, on any branch."""

    branch: str
    sha: str
    when: datetime
    subject: str


@dataclass(frozen=True)
class RemoteState:
    """What the boot shows in its header."""

    fetched: bool
    fetch_error: str | None
    current_branch: str | None
    latest: Activity | None
    ahead: int | None
    behind: int | None
    # The upstream branch was deleted on the remote.
    upstream_gone: bool = False
    # The remote shares no commit with this repository.
    unrelated_remote: bool = False

    @property
    def elsewhere(self) -> bool:
        """True if the most recent work is on a branch other than the current one."""
        if self.latest is None or self.current_branch is None:
            return False
        return _bare(self.latest.branch) != self.current_branch


def _bare(ref: str) -> str:
    """Strip an `origin/` or `upstream/` prefix from a ref name."""
    if "/" not in ref:
        return ref
    head, tail = ref.split("/", 1)
    return tail if head in ("origin", "upstream") else ref


def fetch_all(root: Path) -> tuple[bool, str | None]:
    """`git fetch --all --prune` within the boot's time budget. Return (ok, reason if not)."""
    budget = boot_common.network_budget(FETCH_TIMEOUT)
    if budget <= 0:
        return False, "no se trajo el remoto: no quedaba tiempo dentro del tope del arranque"
    result = gitcmd.run(
        ["fetch", "--all", "--prune", "--quiet"],
        cwd=root,
        timeout=round(max(budget, 0.1), 1),
        env=_HARDENED_ENV,
    )
    if result.returncode == 0:
        return True, None
    reason = (result.stderr or "").strip().split("\n")[-1]
    return False, reason or "git no dijo por que"


def latest_activity(root: Path, local_only: bool = False) -> Activity | None:
    """The branch with the most recent commit, local and remote refs included."""
    result = gitcmd.run(
        [
            "for-each-ref",
            "--sort=-committerdate",
            f"--count={_REF_CANDIDATES}",
            f"--format={_REF_FORMAT}",
            "refs/heads",
            *(() if local_only else ("refs/remotes",)),
        ],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    if result.returncode != 0:
        return None

    for line in (result.stdout or "").split("\n"):
        if line.count(_FIELD_SEP) != 4:
            continue
        when, branch, sha, symref, subject = line.split(_FIELD_SEP)

        # Skip symbolic refs such as `origin/HEAD`: they are not branches.
        if symref:
            continue

        # An unreadable date raises: None would read as "no activity".
        moment = timefmt.from_git_seconds(when)
        return Activity(branch=branch, sha=sha, when=moment, subject=subject)
    return None


_TRACK_RE = re.compile(r"ahead (\d+)|behind (\d+)")
_GONE = "gone"


def divergence(root: Path, branch: str | None) -> tuple[int | None, int | None]:
    """Commits ahead and behind the upstream, read from `%(upstream:track)`.

    `(None, None)` when there is no upstream or it is gone.
    """
    if not branch:
        return None, None
    result = gitcmd.run(
        [
            "for-each-ref",
            "--format=%(upstream:track)",
            f"refs/heads/{branch}",
        ],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    track = (result.stdout or "").strip()
    if result.returncode != 0 or not track:
        return None, None
    # "[gone]": the upstream was deleted; zero counts would read as "up to date".
    if _GONE in track:
        return None, None
    ahead = behind = 0
    for match in _TRACK_RE.finditer(track):
        if match.group(1):
            ahead = int(match.group(1))
        if match.group(2):
            behind = int(match.group(2))
    return ahead, behind


def shares_history(root: Path, branch: str | None) -> bool:
    """True if any remote ref shares a commit with HEAD, or there are no remote refs.

    False means the remote points at another project.
    """
    candidates = gitcmd.run(
        [
            "for-each-ref",
            f"--count={_REF_CANDIDATES}",
            "--format=%(refname:short)%(symref)",
            "refs/remotes",
        ],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    references = [
        line.strip()
        for line in (candidates.stdout or "").split("\n")
        # Skip symbolic refs (`origin/HEAD`): they are not branches.
        if line.strip() and "refs/remotes/" not in line
    ]
    if candidates.returncode != 0 or not references:
        return True

    for reference in references:
        # `--` separates options from refs.
        shared = gitcmd.run(
            ["merge-base", "--", "HEAD", reference],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
        if shared.returncode == 0:
            return True
    return False


def state(root: Path, current_branch: str | None) -> RemoteState:
    """Fetch and answer all three questions at once."""
    fetched, error = fetch_all(root)
    related = shares_history(root, current_branch)
    # With an unrelated remote the ahead/behind counts are meaningless.
    ahead, behind = divergence(root, current_branch) if related else (None, None)
    gone = related and _upstream_gone(root, current_branch)
    return RemoteState(
        fetched=fetched,
        fetch_error=error,
        current_branch=current_branch,
        # With an unrelated remote only local branches count.
        latest=latest_activity(root, local_only=not related),
        ahead=ahead,
        behind=behind,
        unrelated_remote=not related,
        upstream_gone=bool(gone),
    )


def _upstream_gone(root: Path, branch: str | None) -> bool:
    if not branch:
        return False
    result = gitcmd.run(
        ["for-each-ref", "--format=%(upstream:track)", f"refs/heads/{branch}"],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    return _GONE in (result.stdout or "")
