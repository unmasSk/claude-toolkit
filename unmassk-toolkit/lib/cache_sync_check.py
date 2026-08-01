"""
Repo-vs-cache sync check for bin/git-memory-doctor.py.

Claude Code executes the plugin from ~/.claude/plugins/cache/..., never from
the working tree. An edit made in the repo therefore changes nothing at
runtime until the plugin is reinstalled -- and every other doctor check looks
only at the cache, so the report stays fully green while the edit sits
unexecuted. This module is the one check that looks at both sides at once.

Two design constraints, both deliberate:

- **Developer-only.** It applies exactly when the current project IS the
  toolkit repo (a `unmassk-toolkit/` directory in the working tree). Any
  other project has no toolkit source to compare against, so the check does
  not apply and says nothing at all -- see `check_repo_cache_sync`'s None
  return.
- **Fail-open.** If the cache cannot be located, or a directory cannot be
  read, it reports "nothing to say" instead of inventing an alarm. A stale
  cache is a developer inconvenience, never a correctness threat to the
  memory itself.

Comparison is by file content digest (reusing lib/boot_health.py's
`_md5_file`, the same primitive `check_skill_drift()` already uses for
SKILL.md files), never a line-by-line diff: the answer needed is "same or
not", and nothing more.
"""

import os
import sys

# Loading this module standalone (importlib spec_from_file_location, without
# lib/ on sys.path) would break the sibling `boot_health` import below. Same
# self-insertion guard already used by lib/boot_migrations.py and
# bin/release_helpers.py; a no-op under normal execution, where the caller
# has already put lib/ on the path.
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from boot_health import CACHE_BASE_DIR, _latest_version_dir, _md5_file


# Directory name of this plugin, both inside the repo working tree and under
# CACHE_BASE_DIR.
PLUGIN_DIR_NAME = "unmassk-toolkit"

# The executable surface: everything Claude Code actually runs. Skills are
# deliberately absent -- lib/boot_health.py's check_skill_drift() already
# covers those at boot, and duplicating it here would produce two warnings
# for one fact.
COMPARED_SUBDIRS = ("hooks", "lib", "bin")

# Never a source file, always regenerated locally, and guaranteed to differ
# between two copies of the same tree.
_IGNORED_ENTRIES = {"__pycache__"}

# How many differing filenames to name before falling back to a bare count.
_MAX_NAMED_FILES = 3


def _dir_fingerprint(path: str) -> dict[str, str] | None:
    """Map filename -> content digest for the regular files directly in `path`.

    Not recursive: hooks/, lib/ and bin/ are flat directories, and the only
    nested entry any of them has is __pycache__, which is excluded.

    Returns:
        The digest map, or None if the directory does not exist or cannot be
        listed (fail-open -- the caller treats that as "cannot compare").
    """
    try:
        entries = os.listdir(path)
    except OSError:
        return None
    fingerprint: dict[str, str] = {}
    for name in entries:
        if name.startswith(".") or name in _IGNORED_ENTRIES:
            continue
        full = os.path.join(path, name)
        if not os.path.isfile(full):
            continue
        try:
            fingerprint[name] = _md5_file(full)
        except OSError:
            # One unreadable file must not void the whole comparison; leaving
            # it out only ever makes the check quieter, never louder.
            continue
    return fingerprint


def _describe(subdir: str, differing: list[str]) -> str:
    """Render one subdirectory's drift as a short, bounded phrase."""
    shown = sorted(differing)[:_MAX_NAMED_FILES]
    rest = len(differing) - len(shown)
    suffix = f", +{rest} more" if rest > 0 else ""
    return f"{subdir}/: {', '.join(shown)}{suffix}"


def _compute_drift(project_root: str) -> tuple[int, list[str]] | None:
    """Shared core for check_repo_cache_sync() / count_repo_cache_drift().

    Returns:
        None if the check does not apply (this project is not the toolkit
        repo, or the cache could not be located). Otherwise (total differing
        file count, human-readable drift descriptions) -- count is 0 and
        descriptions is [] when both sides are identical.
    """
    repo_plugin = os.path.join(project_root, PLUGIN_DIR_NAME)
    if not os.path.isdir(repo_plugin):
        return None

    cache_plugin = _latest_version_dir(os.path.join(CACHE_BASE_DIR, PLUGIN_DIR_NAME))
    if not cache_plugin or not os.path.isdir(cache_plugin):
        return None
    if os.path.realpath(cache_plugin) == os.path.realpath(repo_plugin):
        # Running against the source tree itself -- nothing to compare.
        return None

    total = 0
    drifted: list[str] = []
    for subdir in COMPARED_SUBDIRS:
        repo_fp = _dir_fingerprint(os.path.join(repo_plugin, subdir))
        if repo_fp is None:
            continue  # No source side to compare against — fail open.
        cache_fp = _dir_fingerprint(os.path.join(cache_plugin, subdir))
        if cache_fp is None:
            # Whole subdir missing from the cache -- every repo file in it
            # is unaccounted for, not just the ones that happen to differ.
            total += len(repo_fp)
            drifted.append(f"{subdir}/: absent from the cache")
            continue
        differing = [
            name for name in set(repo_fp) | set(cache_fp)
            if repo_fp.get(name) != cache_fp.get(name)
        ]
        if differing:
            total += len(differing)
            drifted.append(_describe(subdir, differing))

    return total, drifted


def check_repo_cache_sync(project_root: str) -> list[str] | None:
    """Compare the toolkit working tree against the installed plugin cache.

    Args:
        project_root: Git root of the current project.

    Returns:
        None if the check does not apply (this project is not the toolkit
        repo, or the cache could not be located) -- the caller must stay
        silent in that case. An empty list if both sides are identical. A
        list of human-readable drift descriptions otherwise.
    """
    result = _compute_drift(project_root)
    return None if result is None else result[1]


def count_repo_cache_drift(project_root: str) -> tuple[int, list[str]] | None:
    """Same comparison as check_repo_cache_sync(), plus the raw file count.

    A subdirectory bundles its named files behind "+N more" past
    _MAX_NAMED_FILES, so the description list alone cannot answer "how many
    files, exactly" -- this is for callers (the boot banner's PLUGIN: line)
    that need that number instead of, or in addition to, the descriptions.

    Returns:
        None if the check does not apply (same fail-open cases as
        check_repo_cache_sync() -- the caller must render this as "not
        verifiable", never as "in sync"). Otherwise (total differing file
        count, drift descriptions); count 0 means genuinely in sync.
    """
    return _compute_drift(project_root)
