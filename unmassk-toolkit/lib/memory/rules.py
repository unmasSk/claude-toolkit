"""Rules file (remembers): add, retract and replace a rule line, each as one file write plus one commit.

On a failed commit the file is restored, so rules.md and HEAD never diverge.
"""

import gitcmd
from emojis import CHANNEL_EMOJI
from model import WriteResult
from rules_commit import (
    commit_or_restore,
    lock_resource,
    read_current_rules_content,
    repo_root,
    rules_file_path,
)
from rules_commit import read_all  # noqa: F401 -- re-exported
from rules_similarity import (  # noqa: F401 -- iter_rule_texts/strip_quote_suffix re-exported
    find_rule_line,
    iter_rule_texts,
    remove_rule_line,
    similar_existing,
    strip_quote_suffix,
)
from rules_validate import (
    QUOTE_NOT_GIVEN,
    TEXT_MAX_CHARS,
    reject_invalid_kind,
    reject_invalid_text,
    reject_rule_not_found,
    reject_too_long,
    validate_quote,
)


def _with_searched(subject: str, searched: str | None) -> str:
    """Append a folded `Searched:` body to the commit message; rules.md never gets it."""
    if searched is None:
        return subject
    folded = searched.replace("\n", "\n ")
    return f"{subject}\n\nSearched: {folded}"


def _check_new_rule(text: str, kind: str, quote, replaces: str | None = None):
    """Validate a new rule: `(quote_has_content, None)` if valid, else `(False, WriteResult)`."""
    if "\n" in kind or not kind.strip():
        rejection = reject_invalid_kind(kind)
    elif "\n" in text or not text.strip():
        rejection = reject_invalid_text(text)
    elif len(text) > TEXT_MAX_CHARS:
        rejection = reject_too_long(text)
    else:
        quote_has_content, rejection = validate_quote(quote, text, kind, replaces=replaces)
        if rejection is None:
            return quote_has_content, None
    return False, WriteResult(ok=False, note_id=None, rejections=(rejection,), git_error=None)


def add(text: str, kind: str, quote=QUOTE_NOT_GIVEN, searched: str | None = None) -> WriteResult:
    """Append a rule line and commit it; `ok=True` only when the commit exists.

    `quote`, when passed, must be non-blank or the literal "none"; a real quote is
    appended as ` — «<quote>»`. Invalid input is rejected without touching the file.
    """
    quote_has_content, rejected = _check_new_rule(text, kind, quote)
    if rejected is not None:
        return rejected

    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        emoji = CHANNEL_EMOJI["rule"]
        subject = f"[remember][{kind}] {emoji} {text}"
        if quote_has_content:
            subject += f" — «{quote}»"

        path = rules_file_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_existed_before, previous_content = read_current_rules_content(path)

        # Re-read right before writing to pick up a manual edit made meanwhile.
        file_existed_before, previous_content = read_current_rules_content(path)

        gitcmd.atomic_write(path, previous_content + subject + "\n")

        # file_existed_before: on a failed first rule the file is deleted, not restored.
        message = _with_searched(subject, searched)
        git_error = commit_or_restore(path, previous_content, message, root, file_existed_before)
        if git_error is not None:
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_error)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def retract(text: str, kind: str) -> WriteResult:
    """Remove the `[kind]` line whose text (without quote) equals `text`, and commit it.

    No matching line under that `kind` is a rejection, never a silent no-op.
    """
    if "\n" in kind or not kind.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_kind(kind),), git_error=None
        )
    if "\n" in text or not text.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(reject_invalid_text(text),), git_error=None
        )

    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        path = rules_file_path(root)
        file_existed_before, previous_content = read_current_rules_content(path)
        # Re-read, same reason as in add().
        file_existed_before, previous_content = read_current_rules_content(path)

        matched_line = find_rule_line(previous_content, text, kind)
        if matched_line is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(reject_rule_not_found(text, kind),),
                git_error=None,
            )

        new_content = remove_rule_line(previous_content, matched_line)
        emoji = CHANNEL_EMOJI["rule"]
        message = f"[remember][retract][{kind}] {emoji} {text}"

        gitcmd.atomic_write(path, new_content)

        git_error = commit_or_restore(path, previous_content, message, root, file_existed_before)
        if git_error is not None:
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_error)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def replace(
    old_text: str, new_text: str, kind: str, quote=QUOTE_NOT_GIVEN, searched: str | None = None
) -> WriteResult:
    """Swap the `[kind]` rule `old_text` for `new_text` in one write and one commit.

    Validates like add() and rejects like retract(); a failed commit leaves the old rule intact.
    """
    quote_has_content, rejected = _check_new_rule(new_text, kind, quote, replaces=old_text)
    if rejected is not None:
        return rejected

    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        path = rules_file_path(root)
        file_existed_before, previous_content = read_current_rules_content(path)
        # Re-read, same reason as in add().
        file_existed_before, previous_content = read_current_rules_content(path)

        matched_line = find_rule_line(previous_content, old_text, kind)
        if matched_line is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(reject_rule_not_found(old_text, kind),),
                git_error=None,
            )

        content_without_old = remove_rule_line(previous_content, matched_line)

        emoji = CHANNEL_EMOJI["rule"]
        new_subject = f"[remember][{kind}] {emoji} {new_text}"
        if quote_has_content:
            new_subject += f" — «{quote}»"

        new_content = content_without_old + new_subject + "\n"
        message = _with_searched(f"[remember][replace][{kind}] {emoji} {old_text} -> {new_text}", searched)

        gitcmd.atomic_write(path, new_content)

        git_error = commit_or_restore(path, previous_content, message, root, file_existed_before)
        if git_error is not None:
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_error)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)
