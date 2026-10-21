"""Find plans whose `Issue: #N` commits are newer than the issue's last GitHub activity.

Commits are read with `query.run_git_log()`; issues come from one `gh api graphql`
call. A failed `gh` raises `RuntimeError`, never an invented result; `gh` is not
called when no commit cites an issue. `health.py` re-exports `plans_unreflected`.
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import boot_common
import query
import timefmt

_FIELD_SEP = "\x1f"
_ISSUE_TRAILER_RE = re.compile(r"^Issue: #(\d+)$", re.MULTILINE)
_GH_DEADLINE_ENV = "UNMASSK_GH_DEADLINE_SECONDS"
# Own deadline; at boot `boot_common.network_budget` cuts it down.
_GH_DEADLINE_DEFAULT = 15.0
# One alias per cited issue; `gh` fills `{owner}`/`{repo}` from the current repository.
_GH_QUERY = (
    "query($owner: String!, $name: String!) {"
    " repository(owner: $owner, name: $name) {%s} }"
)
_GH_ISSUE_FIELD = (
    "i%d: issue(number: %d) { state title createdAt comments(last: 1) { nodes { createdAt } } }"
)


def _issue_commit_dates() -> dict[int, tuple[datetime, ...]]:
    """Author dates of the commits carrying an `Issue: #N` trailer, grouped by issue number.

    Raises `RuntimeError` if `git log` fails; a branch with no commits gives `{}`.
    """
    raw_stdout = query.run_git_log(f"--pretty=format:%at{_FIELD_SEP}%B")

    by_issue: dict[int, list[datetime]] = {}
    for record in raw_stdout.split("\0"):
        if not record:
            continue
        author_date, _sep, body = record.partition(_FIELD_SEP)
        commit_date = timefmt.from_git_seconds(author_date)
        for match in _ISSUE_TRAILER_RE.finditer(body):
            by_issue.setdefault(int(match.group(1)), []).append(commit_date)

    return {number: tuple(dates) for number, dates in by_issue.items()}


def _gh_deadline() -> float:
    """Total deadline in seconds for the GitHub query, from the env; bad values fall back to the default."""
    return boot_common.env_seconds(_GH_DEADLINE_ENV, _GH_DEADLINE_DEFAULT)


def _gh_graphql(issue_numbers: list[int]) -> tuple[int, str, str]:
    """`(returncode, stdout, stderr)` of one GraphQL query for the cited issues.

    Raises `RuntimeError` if `gh` is missing or times out. A non-zero return code
    is not raised: `gh` exits 1 when an issue is missing but still prints the rest.
    """
    # Own deadline, cut to what is left of the boot's.
    deadline = boot_common.network_budget(_gh_deadline())
    if deadline <= 0:
        raise RuntimeError(
            "gh api graphql no se lanzo: no quedaba tiempo dentro del tope del arranque"
        )
    deadline = round(max(deadline, 0.1), 1)
    fields = " ".join(_GH_ISSUE_FIELD % (n, n) for n in issue_numbers)
    try:
        # Explicit utf-8: the console codec (cp1252 on Windows) can yield stdout=None silently.
        proc = subprocess.run(
            [
                "gh", "api", "graphql",
                "-F", "owner={owner}", "-F", "name={repo}",
                "-f", f"query={_GH_QUERY % fields}",
            ],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=deadline,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh api graphql no termino dentro de {deadline:g}s") from exc
    except OSError as exc:
        raise RuntimeError(
            f"no se pudo ejecutar 'gh' (no esta instalado, o no es ejecutable): {exc}"
        ) from exc
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _last_activity_by_issue(
    issue_numbers: list[int],
) -> tuple[dict[int, datetime], dict[int, tuple[str, str]], tuple[int, ...]]:
    """Per cited issue: last activity date (last comment, else creation) and `(state, title)`,
    plus the cited numbers GitHub did not return.

    Raises `RuntimeError` on a `gh` failure or an unexpected response shape.
    """
    returncode, stdout, stderr = _gh_graphql(issue_numbers)
    try:
        repository = json.loads(stdout)["data"]["repository"]
    except (KeyError, TypeError, ValueError):
        repository = None
    if not isinstance(repository, dict):
        if returncode != 0:
            raise RuntimeError(f"gh api graphql fallo: {stderr.strip() or stdout.strip()}")
        raise RuntimeError(
            f"respuesta de 'gh api graphql' con forma inesperada: {stdout.strip()[:200]}"
        )

    activity: dict[int, datetime] = {}
    states: dict[int, tuple[str, str]] = {}
    try:
        for number in issue_numbers:
            issue = repository.get(f"i{number}")
            if issue is None:
                continue
            dates = [c["createdAt"] for c in issue["comments"]["nodes"]]
            raw = max(dates) if dates else issue["createdAt"]
            activity[number] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            states[number] = (str(issue["state"]), str(issue["title"]))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError(f"respuesta de 'gh api graphql' con forma inesperada: {exc}") from exc

    missing = tuple(n for n in issue_numbers if n not in activity)
    return activity, states, missing


def plans_unreflected() -> tuple[tuple[int, int], ...]:
    """`(issue_number, unreflected_commits)` for each issue with commits newer than its last activity.

    Never yields a `0` entry; returns `()` without calling `gh` when no commit cites an issue.
    """
    return issues_checked()[0]


def issues_checked() -> tuple[
    tuple[tuple[int, int], ...], tuple[tuple[int, str, str], ...], tuple[int, ...]
]:
    """`plans_unreflected()`, each cited issue's `(number, state, title)` and the numbers
    GitHub did not return, from one single query. Raises like `plans_unreflected()`.
    """
    by_issue = _issue_commit_dates()
    if not by_issue:
        return (), (), ()

    issue_numbers = sorted(by_issue)
    last_activity_by_issue, states, missing = _last_activity_by_issue(issue_numbers)
    results = []
    for issue_number in issue_numbers:
        if issue_number in missing:
            continue
        last_activity = last_activity_by_issue[issue_number]
        unreflected = sum(1 for date in by_issue[issue_number] if date > last_activity)
        if unreflected:
            results.append((issue_number, unreflected))
    issue_states = tuple((n, *states[n]) for n in issue_numbers if n in states)
    return tuple(results), issue_states, missing
