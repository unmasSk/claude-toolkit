"""
Pure classification helpers for hooks/stop-dod-gate.py's exit-2 (pytest
collection error) branch.

Extracted [2026-08-20, size/testability pass, Cerberus/Argus Verify
findings] out of the hook itself so this logic is importable and
unit-testable directly (no need to spawn the hook as a subprocess and
shell out to real pytest just to exercise a classification branch --
Dante uses this module directly to cover "block_present", the one branch
`test_stop_dod_gate.py` documents as having no real pytest repro). Nothing
hook-only (stdin parsing, stdout JSON, session-scoped warn-once state)
lives here -- that stays in the hook.

Git-HEAD tracked state is TRI-STATE, not boolean [2026-08-20, T1 fix]: see
git_helpers.git_tracked_status()'s own docstring for the full incident.
In short, "confirmed not tracked" and "git could not answer" must never
collapse into the same value -- a transient git failure while classifying
a missing module must BLOCK (D2, golden rule: block on any doubt), never
silently fall through to "allow_neverwritten".

D-042 [2026-08-20, Moriarty finding, owner-decided fix]: "first party" can
no longer mean "already exists on disk/git" ONLY. Reproduced 2/2 (real
git + real pytest + the real hook): a brand-new TOP-LEVEL module -- the
single most ordinary test-first shape, `import newfeature` where
`newfeature.py` was never written -- has no parent package to make `seg`
exist, so `seg_exists()` always said False and `classify_missing_module()`
always fell into "block_thirdparty", never reaching "allow_neverwritten".
The guard blocked exactly the legitimate red this feature exists to let
through. Fixed by recognizing first-party by the project's OWN DECLARED
IDENTITY (pyproject.toml [project].name / [tool.poetry].name /
[tool.setuptools] packages, setup.cfg [metadata] name), checked BEFORE
falling back to the existing disk/git layout signal -- see
`_declared_first_party_names()` and `_is_first_party_seg()` below. A
project that declares no identity at all keeps the OLD behavior
(layout-only) -- that residual cost was accepted explicitly by the owner:
a loose new file in an undeclared project still blocks until created.
"""

import configparser
import fnmatch
import os
import re

try:
    import tomllib
except ImportError:  # pragma: no cover -- stdlib since Python 3.11
    tomllib = None

from git_helpers import git_tracked_status

_NO_MODULE_RE = re.compile(r"No module named '([^']+)'")


def extract_missing_modules(output: str) -> list[str]:
    """All distinct "No module named 'X'" matches in `output`, in first-seen
    order."""
    return list(dict.fromkeys(_NO_MODULE_RE.findall(output)))


def seg_exists(cwd: str, seg: str) -> bool:
    """True if `seg` (the first dotted segment of a missing module) is a
    real local package/module: `<cwd>/<seg>/` (dir), `<cwd>/<seg>.py`, or
    `<cwd>/src/<seg>/` (dir) on disk -- OR tracked under those same paths
    in git HEAD. Never raises.

    A git "unknown" (transient failure, not a repo, etc.) folds into False
    here on purpose when disk doesn't already confirm existence: seg is
    then treated as not-a-real-local-package, which sends the caller down
    "block_thirdparty" -- the same block a genuinely-absent third-party
    dependency gets. Never silently treated as "exists" on a git error.
    """
    disk_candidates = [
        os.path.join(cwd, seg),
        os.path.join(cwd, seg + ".py"),
        os.path.join(cwd, "src", seg),
    ]
    for candidate in disk_candidates:
        if os.path.isdir(candidate) or os.path.isfile(candidate):
            return True
    git_relpaths = [seg, seg + ".py", os.path.join("src", seg)]
    return git_tracked_status(cwd, git_relpaths) == "tracked"


def _normalize_declared_name(name: str) -> str:
    """D-042 normalization: '-' -> '_' only. Deliberately does NOT
    lowercase -- the decision names only the dash/underscore
    substitution, and importable top-level module/package names on disk
    are case-sensitive; inventing a lowercase transform here could make a
    declared name falsely match a differently-cased sibling that isn't
    actually the same module."""
    return name.replace("-", "_") if isinstance(name, str) else ""


def _resolve_setuptools_find(cwd: str, find_table: object) -> set[str]:
    """Best-effort resolution of a [tool.setuptools.packages.find] table
    into top-level package names: scans each `where` directory (default
    ".") for top-level dirs that have `__init__.py`, then applies
    `include`/`exclude` glob patterns (defaults "*" / none) to the dir
    name. Not a reimplementation of setuptools' own finder -- just enough
    to resolve the identity signal D-042 asks for "si está a mano". Only
    ever ADDS names that a `seg_exists()` layout scan would already catch
    on its own (this source can't name something absent from disk, by
    construction), so a failure or empty result here costs nothing.
    Never raises.
    """
    if not isinstance(find_table, dict):
        return set()
    where = find_table.get("where", ["."])
    if isinstance(where, str):
        where = [where]
    if not isinstance(where, list):
        where = ["."]
    include = find_table.get("include", ["*"])
    if not isinstance(include, list) or not include:
        include = ["*"]
    exclude = find_table.get("exclude", [])
    if not isinstance(exclude, list):
        exclude = []

    found: set[str] = set()
    for base in where:
        if not isinstance(base, str):
            continue
        base_dir = os.path.join(cwd, base)
        try:
            entries = os.listdir(base_dir)
        except OSError:
            continue
        for entry in entries:
            full = os.path.join(base_dir, entry)
            if not os.path.isdir(full) or not os.path.isfile(os.path.join(full, "__init__.py")):
                continue
            if not any(fnmatch.fnmatch(entry, pat) for pat in include if isinstance(pat, str)):
                continue
            if any(fnmatch.fnmatch(entry, pat) for pat in exclude if isinstance(pat, str)):
                continue
            found.add(entry)
    return found


def _names_from_pyproject(cwd: str) -> set[str]:
    """[project].name (PEP 621), [tool.poetry].name (Poetry), and
    [tool.setuptools].packages / packages.find from pyproject.toml.
    Missing tomllib, missing file, or malformed TOML all degrade to an
    empty set -- never raises, never assumes first-party.
    """
    names: set[str] = set()
    if tomllib is None:
        return names

    try:
        with open(os.path.join(cwd, "pyproject.toml"), "rb") as f:
            data = tomllib.load(f)
    except (OSError, ValueError):
        # Non-UTF8 pyproject.toml -> tomllib.load() raises
        # UnicodeDecodeError (confirmed), a ValueError subclass -- already caught.
        return names
    if not isinstance(data, dict):
        return names

    project_tbl = data.get("project")
    if isinstance(project_tbl, dict):
        project_name = project_tbl.get("name")
        if isinstance(project_name, str) and project_name:
            names.add(_normalize_declared_name(project_name))

    tool_tbl = data.get("tool")
    if not isinstance(tool_tbl, dict):
        return names

    poetry_tbl = tool_tbl.get("poetry")
    if isinstance(poetry_tbl, dict):
        poetry_name = poetry_tbl.get("name")
        if isinstance(poetry_name, str) and poetry_name:
            names.add(_normalize_declared_name(poetry_name))

    setuptools_tbl = tool_tbl.get("setuptools")
    if isinstance(setuptools_tbl, dict):
        packages_val = setuptools_tbl.get("packages")
        if isinstance(packages_val, list):
            for pkg in packages_val:
                if isinstance(pkg, str) and pkg:
                    names.add(_normalize_declared_name(pkg.split(".")[0]))
        elif isinstance(packages_val, dict):
            names |= {
                _normalize_declared_name(n)
                for n in _resolve_setuptools_find(cwd, packages_val.get("find"))
            }

    return names


def _names_from_setup_cfg(cwd: str) -> set[str]:
    """setup.cfg [metadata] name. Missing file or malformed cfg degrades
    to an empty set -- never raises, never assumes first-party.

    [2026-08-20, Dante finding]: `configparser.ConfigParser.read(...,
    encoding="utf-8")` raises `UnicodeDecodeError` for a non-UTF8 (e.g.
    binary) setup.cfg -- that is NOT a subclass of either `OSError` or
    `configparser.Error`, so the original `except (OSError,
    configparser.Error)` let it escape uncaught, breaking this function's
    own "never raises" contract (masked today only because
    `classify_missing_module()`'s outer `except Exception` happens to
    catch it too -- a future caller without that umbrella would not be so
    lucky). `UnicodeDecodeError` added explicitly alongside the others so
    the degrade-to-empty-set behavior is uniform across every read
    failure this function can hit, never "is first party" and never
    "allow" on a decode failure.
    """
    names: set[str] = set()
    try:
        parser = configparser.ConfigParser()
        parser.read(os.path.join(cwd, "setup.cfg"), encoding="utf-8")
        if parser.has_option("metadata", "name"):
            cfg_name = parser.get("metadata", "name")
            if cfg_name:
                names.add(_normalize_declared_name(cfg_name))
    except (OSError, configparser.Error, UnicodeDecodeError):
        pass
    return names


def _declared_first_party_names(cwd: str) -> set[str]:
    """Names the HOST project declares as its own top-level packages/
    modules, from its OWN build metadata -- independent of whether
    anything by that name exists on disk yet (D-042: identity, not
    presence, is what makes a module first-party).

    Sources, all best-effort and additive (a hit from any one is enough):
    see `_names_from_pyproject()` and `_names_from_setup_cfg()`. Any parse
    failure in either degrades to an EMPTY contribution from that source
    -- NEVER to "assume first-party". When the union is empty, the
    caller's existing layout signal (`seg_exists()`) is the only thing
    that still applies -- this is an additive signal, never a
    replacement.
    """
    return _names_from_pyproject(cwd) | _names_from_setup_cfg(cwd)


def _is_first_party_seg(cwd: str, seg: str) -> bool:
    """True if `seg` (the first dotted segment of a missing module) must
    be treated as the host project's own code, checked in order with the
    first available signal (D-042):
      1. Declared project identity (pyproject.toml / setup.cfg) -- a
         match here means first-party EVEN IF `seg` doesn't exist
         anywhere yet (the whole point: a brand-new top-level module the
         project is about to write).
      2. Existing layout signal (`seg_exists()`): present on disk or
         tracked in git HEAD -- unchanged, still catches submodules of an
         already-existing local package.
    No declared identity AND no layout match -> NOT first-party, same as
    before D-042 -- a genuinely-missing third-party dependency still
    blocks (`import requests` with nothing installed, nothing declared).
    """
    if seg in _declared_first_party_names(cwd):
        return True
    return seg_exists(cwd, seg)


def module_source_candidates(dotted: str) -> list[str]:
    """Convert a dotted module name ("a.b.c") to the repo-relative paths
    where its concrete source could live: "a/b/c.py", "a/b/c/__init__.py",
    and the same two under "src/"."""
    parts = [p for p in dotted.split(".") if p]
    if not parts:
        return []
    base = os.path.join(*parts)
    candidates = [base + ".py", os.path.join(base, "__init__.py")]
    candidates += [os.path.join("src", c) for c in candidates]
    return candidates


def classify_missing_module(cwd: str, dotted: str) -> str:
    """Classify ONE missing module X. Returns one of:
      "block_thirdparty"   -- seg doesn't exist locally at all.
      "block_present"      -- concrete source exists on disk but still
                               failed to import (defensive branch).
      "block_deleted"      -- concrete source absent on disk, tracked in
                               git HEAD (existed, got deleted).
      "block_git_unknown"  -- concrete source absent on disk, and git
                               could not say whether it's tracked (T1:
                               never treated as safe to allow).
      "allow_neverwritten" -- concrete source absent on disk, CONFIRMED
                               not tracked (local module never written --
                               test-first in flight).
    D2 (golden rule): any internal error while classifying folds into
    "block_thirdparty" -- never silently allow on doubt.
    """
    try:
        seg = dotted.split(".")[0]
        if not seg or not _is_first_party_seg(cwd, seg):
            return "block_thirdparty"

        candidates = module_source_candidates(dotted)
        if not candidates:
            return "block_thirdparty"

        for relpath in candidates:
            if os.path.isfile(os.path.join(cwd, relpath)):
                return "block_present"

        status = git_tracked_status(cwd, candidates)
        if status == "tracked":
            return "block_deleted"
        if status == "unknown":
            return "block_git_unknown"
        return "allow_neverwritten"
    except Exception:
        return "block_thirdparty"


def classify_collection_error(cwd: str, output: str) -> tuple[bool, list[str]]:
    """Classify an exit-2 (collection error) outcome.

    Returns (allow, never_written_modules). allow is True only when at
    least one "No module named" match was found AND every one of them
    classified as "allow_neverwritten". never_written_modules is the
    ordered list of dotted module names in that class (for the
    once-per-module warning) -- empty whenever allow is False.
    """
    modules = extract_missing_modules(output)
    if not modules:
        return False, []
    never_written = []
    for module in modules:
        if classify_missing_module(cwd, module) != "allow_neverwritten":
            return False, []
        never_written.append(module)
    return True, never_written
