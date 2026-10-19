"""Test double for `gh api graphql` -- Dante, issue #95 phase 1 fix pass.

One faithful answer to the GitHub GraphQL read the boot uses (D-130:
one request that names only the cited issues), shared by the in-process
fakes (`test_health.py`, `test_ci_skip_marker.py`) and by the `gh`
executable stub of `test_boot_deadline_contract.py`, which imports this
file by path. Not a test module: pytest does not collect it.

It answers like GitHub, never like the code under test:
  - only the aliases the query asks for come back (`alias: issue(number: N)`);
  - only the fields each alias selects come back;
  - `comments(last: K)` gives the K most recent, `comments(first: K)` the
    K oldest -- asking for the wrong end returns the wrong comment;
  - a number with no issue comes back as `null` for its alias, with a
    top-level `errors` entry, exit code 1 and gh's own stderr line
    (shape verified against the real gh 2.86 on 2026-10-19 by Ultron:
    `gh: Could not resolve to an Issue with the number of 9999.`);
  - a variable the query declares (`$owner`, `$name`) must be passed with
    `-F`/`-f`, or the request fails like GitHub's "Variable ... was not
    provided".
Anything else (other flags, other root fields) exits 2 "unsupported", so
an implementation that changes the request makes this double extended by
a fresh Dante, never guessed at.

`issues` is `{number: {"createdAt": iso, "updatedAt": iso, "state": str,
"title": str, "comments": [{"createdAt": iso, ...}, ...]}}`, comments
oldest first (GitHub's order). A scalar the query selects that the test
did not configure exits 2 "unsupported", never a made-up value.
"""

import json
import re

_VALUE_FLAGS = {"-F": "typed", "--field": "typed", "-f": "raw", "--raw-field": "raw"}
_ISSUE_SCALARS = {"createdAt", "updatedAt", "state", "title", "number"}
_COMMENT_SCALARS = {"createdAt"}


class _Unsupported(Exception):
    pass


class _GraphQLError(Exception):
    pass


def _tokens(text):
    return re.findall(r"\$?\w+|[{}():!,]|\"[^\"]*\"", text)


def _parse_selection(tokens, i):
    """`{ field [alias:] [(args)] [{...}] ... }` from tokens[i] == '{'.
    Returns (list of (alias, name, args, subselection), next index)."""
    if tokens[i] != "{":
        raise _Unsupported("expected '{'")
    i += 1
    fields = []
    while tokens[i] != "}":
        name = tokens[i]
        alias = name
        i += 1
        if tokens[i] == ":":
            name = tokens[i + 1]
            i += 2
        args = {}
        if tokens[i] == "(":
            i += 1
            while tokens[i] != ")":
                key = tokens[i]
                if tokens[i + 1] != ":":
                    raise _Unsupported("bad argument list")
                args[key] = tokens[i + 2]
                i += 3
                if tokens[i] == ",":
                    i += 1
            i += 1
        sub = None
        if tokens[i] == "{":
            sub, i = _parse_selection(tokens, i)
        fields.append((alias, name, args, sub))
    return fields, i + 1


def _parse_document(query):
    """(declared variable names, root selection)."""
    tokens = _tokens(query)
    declared = set()
    i = 0
    if tokens and tokens[0] == "query":
        i = 1
        if tokens[i] == "(":
            while tokens[i] != ")":
                if tokens[i].startswith("$") and tokens[i + 1] == ":":
                    declared.add(tokens[i][1:])
                i += 1
            i += 1
    root, _ = _parse_selection(tokens, i)
    return declared, root


def _parse_argv(argv):
    """`api graphql` plus `-F/-f key=value` pairs only."""
    if argv[:2] != ["api", "graphql"]:
        raise _Unsupported("not 'gh api graphql'")
    fields = {}
    rest = argv[2:]
    i = 0
    while i < len(rest):
        flag = rest[i]
        if flag not in _VALUE_FLAGS or i + 1 >= len(rest) or "=" not in rest[i + 1]:
            raise _Unsupported(f"flag {flag!r}")
        key, value = rest[i + 1].split("=", 1)
        fields[key] = value
        i += 2
    if "query" not in fields:
        raise _Unsupported("no query field")
    return fields


def requested_issue_numbers(argv):
    """Issue numbers one `gh api graphql` argv asks for, in query order."""
    fields = _parse_argv(argv)
    _declared, root = _parse_document(fields["query"])
    numbers = []
    for _alias, name, _args, sub in root:
        if name != "repository" or sub is None:
            raise _Unsupported(f"root field {name!r}")
        for _a, field, args, _s in sub:
            if field != "issue" or "number" not in args:
                raise _Unsupported(f"repository field {field!r}")
            numbers.append(int(args["number"]))
    return numbers


def _comments(selected, args, comments):
    if set(args) - {"first", "last"} or len(args) != 1:
        raise _Unsupported(f"comments args {args!r}")
    count = int(next(iter(args.values())))
    chosen = comments[-count:] if "last" in args else comments[:count]
    if count == 0:
        chosen = []
    out = {}
    for alias, name, _a, sub in selected:
        if name == "totalCount":
            out[alias] = len(comments)
        elif name == "nodes" and sub is not None:
            nodes = []
            for comment in chosen:
                node = {}
                for c_alias, c_name, _ca, _cs in sub:
                    if c_name not in _COMMENT_SCALARS:
                        raise _GraphQLError(
                            f"Field '{c_name}' doesn't exist on type 'IssueComment'"
                        )
                    node[c_alias] = comment[c_name]
                nodes.append(node)
            out[alias] = nodes
        else:
            raise _GraphQLError(f"Field '{name}' doesn't exist on type 'IssueCommentConnection'")
    return out


def _issue(selected, record, number):
    out = {}
    for alias, name, args, sub in selected:
        if name in _ISSUE_SCALARS:
            if name != "number" and name not in record:
                raise _Unsupported(
                    f"issue #{number} configured without {name!r}: real GitHub always "
                    "returns it -- configure it in the test"
                )
            out[alias] = number if name == "number" else record[name]
        elif name == "comments" and sub is not None:
            out[alias] = _comments(sub, args, record.get("comments", []))
        else:
            raise _GraphQLError(f"Field '{name}' doesn't exist on type 'Issue'")
    return out


def answer(argv, issues):
    """(returncode, stdout, stderr) of `gh <argv>` against `issues`."""
    try:
        fields = _parse_argv(argv)
        declared, root = _parse_document(fields["query"])
        missing_vars = sorted(v for v in declared if v not in fields)
        if missing_vars:
            message = f"Variable ${missing_vars[0]} of type String! was provided invalid value"
            return 1, json.dumps({"errors": [{"message": message}]}), f"gh: {message}\n"
        data = {}
        errors = []
        for r_alias, name, _args, sub in root:
            if name != "repository" or sub is None:
                raise _Unsupported(f"root field {name!r}")
            repository = {}
            for alias, field, args, selected in sub:
                if field != "issue" or "number" not in args or selected is None:
                    raise _Unsupported(f"repository field {field!r}")
                number = int(args["number"])
                if number not in issues:
                    repository[alias] = None
                    errors.append(
                        {
                            "type": "NOT_FOUND",
                            "path": [r_alias, alias],
                            "message": (
                                "Could not resolve to an Issue with the number "
                                f"of {number}."
                            ),
                        }
                    )
                    continue
                repository[alias] = _issue(selected, issues[number], number)
            data[r_alias] = repository
    except _Unsupported as exc:
        return 2, "", f"fake gh (Dante #95 graphql double): unsupported invocation {argv!r}: {exc}\n"
    except _GraphQLError as exc:
        return 1, json.dumps({"errors": [{"message": str(exc)}]}), f"gh: {exc}\n"
    body = {"data": data}
    if errors:
        body["errors"] = errors
        stderr = "".join(f"gh: {e['message']}\n" for e in errors)
        return 1, json.dumps(body), stderr
    return 0, json.dumps(body), ""


def real_gh_failure_line(cwd):
    """First stderr line of the REAL `gh api graphql`, run in `cwd` with
    the same `{owner}`/`{repo}` placeholders the boot passes. In a fresh
    repo with no GitHub remote it fails locally, before any network:
    logged out -> "To get started with GitHub CLI...", logged in ->
    `error parsing "owner" value: no git remotes found` (both verified
    2026-10-19, gh 2.86). The expected cause therefore comes from gh
    itself, never from the code under test."""
    import subprocess

    proc = subprocess.run(
        [
            "gh", "api", "graphql",
            "-F", "owner={owner}", "-F", "name={repo}",
            "-f", "query=query { viewer { login } }",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode != 0, f"setup invalid: real gh succeeded in {cwd}: {proc.stdout!r}"
    line = proc.stderr.strip().splitlines()[0].strip()
    assert line, "setup invalid: real gh failed with an empty stderr"
    return line
