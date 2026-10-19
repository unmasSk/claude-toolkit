"""Git Bash's spelling of a Windows drive path, read as Windows reads it.

On Windows, Git Bash writes `C:\\Users\\x` as `/c/Users/x`; bash and git
accept both. Same rule as hooks/customs.py::_translate_git_bash_drive_path.
"""

import re
import sys

# One letter, then `/` or the end: `/cache/x` is a folder, not drive C.
_GIT_BASH_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)?$")


def native_path(path):
    """`/c/Users/x` -> `C:/Users/x` on Windows; anything else unchanged.
    Off Windows nothing is translated: `/c/...` may be a real directory."""
    if sys.platform != "win32":
        return path
    match = _GIT_BASH_DRIVE_RE.match(path)
    if match is None:
        return path
    return f"{match.group(1).upper()}:{match.group(2) or '/'}"
