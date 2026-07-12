"""
Shared fallback for open_no_follow_symlink() (Cerberus T3-1).

lib/boot_memory.py and hooks/session-start-boot.py each need
git_helpers.open_no_follow_symlink() but must still import cleanly when
git_helpers is replaced by a minimal test stub that predates this helper
(tests/test_migrate_statusline.py does exactly this). Before this module
existed, both call sites carried a byte-identical local reimplementation
of the same O_NOFOLLOW logic as a fallback — two copies that could drift
apart silently. This module is the single shared implementation; both
call sites import defensively:

    try:
        from git_helpers import open_no_follow_symlink
    except ImportError:
        from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink

This module is never itself stubbed by any test (only "git_helpers",
"parsing", and "version" are), so the fallback import above always
resolves to this real implementation even during a stub window.

Must be kept behaviorally identical to git_helpers.open_no_follow_symlink().
"""

import errno
import os
import sys


def open_no_follow_symlink_fallback(
    path: str,
    mode: str = "w",
    encoding: str = "utf-8",
    reject_hardlinks: bool = False,
    errors: str = "strict",
):
    """Fallback reimplementation — see git_helpers.open_no_follow_symlink() for the
    full rationale (SEC-CRIT-001 write guard, SEC-MED-NEW-02 read guard) and
    the full Windows hybrid-guard (option C, decision 75fdb2f) writeup,
    including the F4 (0o600 is POSIX-only), F5 (O_CREAT TOCTOU residual,
    accepted deliberately), F6 (hard-link bypass, issue #53, decision
    51a3c44 — closed via the opt-in `reject_hardlinks` parameter below; a
    hard link shares device+inode with its target, so it is undetected by
    both os.path.islink() on Windows and O_NOFOLLOW on POSIX), and the
    `errors` parameter (issue #54, T3 — default "strict" preserves prior
    behavior for every existing call site; a write-mode caller whose text
    can contain a lone surrogate must pass a non-strict value so a bare
    UnicodeEncodeError never escapes in violation of the "only OSError
    escapes" contract) notes. Must be kept behaviorally identical to
    git_helpers.open_no_follow_symlink() on both branches, including the
    reject_hardlinks and errors behavior."""
    if sys.platform == "win32":
        return _open_no_follow_symlink_windows(path, mode, encoding, reject_hardlinks, errors)

    defer_truncate = False
    if mode == "r":
        flags = os.O_RDONLY | os.O_NOFOLLOW
        fd = os.open(path, flags)
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        if mode == "a":
            flags |= os.O_APPEND
        elif reject_hardlinks:
            # Defer O_TRUNC: truncating a shared inode before the
            # st_nlink check below would destroy the sibling hard link's
            # content even when the check is about to reject the open
            # outright.
            defer_truncate = True
        else:
            flags |= os.O_TRUNC
        fd = os.open(path, flags, 0o600)

    if reject_hardlinks:
        try:
            if os.fstat(fd).st_nlink > 1:
                raise OSError(
                    errno.EMLINK,
                    "Refusing to open a hard-linked file (st_nlink > 1); "
                    "reject_hardlinks=True forbids opening a multi-link path",
                    path,
                )
            if defer_truncate:
                os.ftruncate(fd, 0)
        except BaseException:
            os.close(fd)
            raise

    return os.fdopen(fd, mode, encoding=encoding, errors=errors)


def _open_no_follow_symlink_windows(
    path: str, mode: str, encoding: str, reject_hardlinks: bool = False,
    errors: str = "strict",
):
    """Windows half of the option-C hybrid guard — must be kept
    behaviorally identical to
    git_helpers._open_no_follow_symlink_windows(). See that function's
    module for the full rationale, including the `errors` parameter
    (issue #54, T3)."""
    if os.path.islink(path):
        # ELOOP is reused here (not the literal syscall errno) so that both
        # Windows rejection paths — direct symlink here, and the divergent-
        # identity race below — share one errno with each other and POSIX.
        raise OSError(errno.ELOOP, "Refusing to open a symlink", path)

    # Pre-open identity, only meaningful if the path already exists —
    # a brand-new path (O_CREAT case) has nothing to compare against
    # (F5 residual, accepted deliberately).
    prior_identity = None
    if os.path.exists(path):
        prior_identity = os.lstat(path)

    if mode == "r":
        fd = os.open(path, os.O_RDONLY)
    else:
        # O_TRUNC is deliberately withheld here: truncating at open() time
        # would destroy the target's contents even if the identity check
        # below goes on to reject the open as a symlink race. For mode
        # "w" the truncate is deferred until after that check passes,
        # via the ftruncate() call further down.
        flags = os.O_WRONLY | os.O_CREAT
        flags |= os.O_APPEND if mode == "a" else 0
        fd = os.open(path, flags, 0o600)

    try:
        if prior_identity is not None:
            post_identity = os.fstat(fd)
            if (post_identity.st_dev, post_identity.st_ino) != (
                prior_identity.st_dev, prior_identity.st_ino,
            ):
                # ELOOP reused again here, matching the direct-symlink
                # rejection above — see the comment on that raise.
                raise OSError(
                    errno.ELOOP,
                    "Refusing to open: file identity changed between the "
                    "pre-open check and the open() call (possible symlink race)",
                    path,
                )
        if reject_hardlinks:
            # Checked on the already-open fd (never os.stat(path)) to keep
            # the same TOCTOU discipline as the identity check above.
            if os.fstat(fd).st_nlink > 1:
                raise OSError(
                    errno.EMLINK,
                    "Refusing to open a hard-linked file (st_nlink > 1); "
                    "reject_hardlinks=True forbids opening a multi-link path",
                    path,
                )
        if mode == "w":
            os.ftruncate(fd, 0)
    except BaseException:
        os.close(fd)
        raise

    return os.fdopen(fd, mode, encoding=encoding, errors=errors)
