"""Session boot report: branch, NEXT, blockers, restrictions, COUNTS and CHECKS.

Only composes and renders: reads through `query` and `health`, writes nothing.
"""

import textwrap
from datetime import datetime, timezone

import context
import emojis
import health
import indexes
import notes
import notes_duplicate
import query
import remote
import repo_guard
import timefmt
import validator
from model import BootSummary, ContextNote

_BOX_WIDTH = 72  # same width as report_render._BOX_WIDTH

_ZERO_BLOCKERS = "⛔ BLOCKERS ......  C E R O"
_ZERO_RESTRICTIONS = (
    "⚠️ RESTRICTIONS ....  C E R O",
    "                      No hay ningún muro puesto. Nada te va a parar",
    "                      porque nadie ha escrito todavía qué rompe qué.",
)
_NEXT_LABEL = "[NEXT] "
_NEXT_INDENT = " " * len(_NEXT_LABEL)
_NO_NEXT = (
    f"{_NEXT_LABEL}ninguno todavía. No hay ningún cierre de sesión escrito.",
    f"{_NEXT_INDENT}El primero lo escribe close-session al terminar hoy.",
)
_FIRST_NOTE_HINT = (
    "Cero no es silencio: es que todavía no se ha escrito nada. La primera",
    "nota se guarda así:",
    "",
    '  gitmem note <TIPO> --zones <zona1> <zona2> "titular en inglés" \\',
    '    --description "..." --stops <yes|no> \\',
    f"    --searched '{validator.SEARCHED_PLACEHOLDER}'",
)
_MAP_IS_SET = (
    "El mapa está puesto. Dime por dónde: el Next, una pregunta, una issue,",
    "o lo que traigas.",
)
# Footer when memory setup is incomplete: zones must exist before the first note.
_SETUP_MISSING_HINT = (
    "La memoria de este proyecto todavía no está montada del todo -- antes",
    "de guardar una nota hace falta dar de alta al menos una zona:",
    "",
    '  gitmem zones add <nombre> --description "..."',
    "",
    "Con al menos una zona dada de alta, la primera nota se guarda así:",
    "",
    '  gitmem note <TIPO> --zones <zona1> <zona2> "titular en inglés" \\',
    '    --description "..." --stops <yes|no> \\',
    f"    --searched '{validator.SEARCHED_PLACEHOLDER}'",
)


def build() -> BootSummary:
    """Build the project's BootSummary from one full read of the note history.

    A note is live if its id is not archived, or if its (id, headline) is still in a
    live index. open_issues counts distinct issues with live non-X notes not closed on GitHub.
    """
    root = notes.repo_root()
    # Fetch first, so the summary is not this copy's stale state; a repo with no commit has no branch.
    try:
        branch = repo_guard.current_branch(root)
    except RuntimeError:
        branch = None
    remote_state = remote.state(root, branch)
    archived_ids = indexes.archived_ids(notes.pm_root(root))
    live_keys = frozenset((line.id, line.headline) for line in health.current_index_lines(root))
    live_notes = tuple(
        note for note in query.by_zone(None, None)
        if note.id not in archived_ids or (note.id, note.headline) in live_keys
    )

    restrictions = tuple(
        sorted((n for n in live_notes if n.type == "R"), key=lambda n: n.id)
    )
    blockers = tuple(
        sorted((n for n in live_notes if n.type == "B"), key=lambda n: n.id)
    )
    questions = tuple(sorted((n for n in live_notes if n.type == "Q"), key=lambda n: n.id))
    incidents = tuple(sorted((n for n in live_notes if n.type == "I"), key=lambda n: n.id))
    open_questions = len(questions)
    open_incidents = len(incidents)
    health_report = health.build()
    closed = {n for n, state, _title in health_report.issue_states if state == "CLOSED"}
    issues = tuple(
        sorted(
            (
                n for n in live_notes
                if n.issue is not None and n.type != "X" and n.issue not in closed
            ),
            key=lambda n: (n.issue, n.id),
        )
    )
    open_issues = len({n.issue for n in issues})

    return BootSummary(
        project=root.name,
        generated_at=datetime.now(timezone.utc),
        remote=remote_state,
        # An unrelated remote cannot provide the Next.
        context=context.latest(all_refs=not remote_state.unrelated_remote),
        blockers=blockers,
        restrictions=restrictions,
        open_questions=open_questions,
        open_issues=open_issues,
        open_incidents=open_incidents,
        questions=questions,
        incidents=incidents,
        health=health_report,
        issues=issues,
    )


def _box_border(left_corner: str, right_corner: str) -> str:
    return f"{left_corner}{'═' * (_BOX_WIDTH - 2)}{right_corner}"


def _box_content_line(left: str, right: str) -> str:
    inner = _BOX_WIDTH - 2
    gap = inner - len(left) - len(right)
    if gap < 1:
        gap = 1
    return f"║{left}{' ' * gap}{right}║"


# Wrap width: the box minus the Next indent.
_PROSE_WIDTH = _BOX_WIDTH - len(_NEXT_INDENT) - 2


def _remote_block(state) -> list[str]:
    """Render the BRANCH block: where the last work was left and where you are."""
    if state is None:
        return []

    lines = ["🌿 BRANCH"]

    if not state.fetched:
        lines.append("   ⚠️  fetch failed — everything below may be stale")
        if state.fetch_error:
            lines.append(f"      {state.fetch_error}")

    if state.latest is not None:
        where = remote._bare(state.latest.branch)
        lines.append(
            f"   Last worked on: {where} · {timefmt.ago(state.latest.when)}"
        )
    if state.current_branch:
        lines.append(f"   You are on: {state.current_branch}")

    if state.elsewhere:
        lines.append("")
        lines.append(
            "   ⚠️  the last work is NOT on your branch — it was left somewhere"
        )
        lines.append("      else, probably on another machine.")

    if state.unrelated_remote:
        lines.append("")
        lines.append(
            "   ⚠️  origin shares NO history with this repository — it points"
        )
        lines.append(
            "      at another project. Ahead/behind counts are meaningless"
        )
        lines.append("      here and are not shown. Do not pull.")

    if state.upstream_gone:
        lines.append(
            "   ⚠️  its remote branch no longer exists — merged and deleted"
        )

    if state.behind:
        lines.append(
            f"   ⚠️  behind origin by {state.behind} commit(s), already fetched"
        )
    if state.ahead:
        lines.append(f"   ⚠️  {state.ahead} commit(s) not pushed")

    return lines


def _looks_like_a_commit_line(line: str) -> bool:
    """True for a commit-list line under the context: starts with `[`, `- ` or `* `."""
    stripped = line.lstrip()
    return stripped.startswith(("[", "- ", "* "))


def _next_block(ctx: ContextNote | None) -> list[str]:
    if ctx is None:
        return list(_NO_NEXT)
    lines = [
        f"{_NEXT_LABEL}{emojis.CHANNEL_EMOJI['next']} {ctx.headline}",
        f"{_NEXT_INDENT}Context (cerrado {timefmt.utc_label(ctx.timestamp)}):",
    ]
    # Prose is wrapped to the box; commit-list lines are kept unwrapped.
    for paragraph in ctx.context.split("\n"):
        if not paragraph.strip():
            lines.append("")
        elif _looks_like_a_commit_line(paragraph):
            lines.append(f"{_NEXT_INDENT}{paragraph.rstrip()}")
        else:
            lines.extend(
                f"{_NEXT_INDENT}{chunk}"
                for chunk in textwrap.wrap(paragraph, width=_PROSE_WIDTH)
            )
    return lines


def _blockers_section(blockers) -> list[str]:
    """Render the BLOCKERS block, each with what it awaits."""
    if not blockers:
        return [_ZERO_BLOCKERS]
    lines = [f"⛔ BLOCKERS ({len(blockers)})", ""]
    for note in blockers:
        lines.append(f"   {note.id}  [{note.zone1}][{note.zone2}]   {note.headline}")
        if note.awaits:
            lines.append(f"          awaits: {note.awaits}")
    return lines


def _restrictions_block(restrictions) -> list[str]:
    if not restrictions:
        return list(_ZERO_RESTRICTIONS)
    # Headline only; the full why is one search away.
    lines = [
        f"⚠️ RESTRICTIONS ({len(restrictions)})",
        "   the full why of each: gitmem search --id R-NNN",
        "",
    ]
    for note in restrictions:
        lines.append(f"   {note.id}  [{note.zone1}][{note.zone2}]     {note.headline}")
    return lines


def _recuentos_block(summary: BootSummary) -> list[str]:
    # One line per issue with its GitHub title, else its first note's headline.
    report = summary.health
    lines = ["COUNTS"]
    if summary.issues and report.plans_unreflected_error is not None:
        lines.append(
            "   ⚠️  GitHub could not be asked: open/closed below is NOT checked"
        )
    listed_numbers = {note.issue for note in summary.issues}
    unchecked = [n for n in report.issues_unanswered if n in listed_numbers]
    if unchecked:
        lines.append(
            f"   ⚠️  GitHub did not return {_issue_refs(unchecked)}: "
            "its open/closed below is NOT checked"
        )
    lines.append(f"   open issues with live work .  {summary.open_issues}")
    titles = {n: title for n, _state, title in report.issue_states}
    listed = set()
    for note in summary.issues:
        if note.issue not in listed:
            listed.add(note.issue)
            lines.append(f"      - #{note.issue}: {titles.get(note.issue) or note.headline}")
    # Open questions and incidents are listed by name, not as a count.
    lines.extend(_named_block("❓ OPEN QUESTIONS", summary.questions))
    lines.extend(_named_block("🔥 OPEN INCIDENTS", summary.incidents))
    return lines


def _issue_refs(numbers) -> str:
    return ", ".join(f"#{n}" for n in numbers)


def _named_block(title: str, notes_seen) -> list[str]:
    if not notes_seen:
        return ["", f"{title} ....  C E R O"]
    lines = ["", f"{title} ({len(notes_seen)})", ""]
    for note in notes_seen:
        lines.append(f"   {note.id}  [{note.zone1}][{note.zone2}]   {note.headline}")
        if note.description:
            first = note.description.split("\n")[0]
            lines.extend(
                f"          {chunk}" for chunk in textwrap.wrap(first, width=_PROSE_WIDTH)
            )
    return lines


def _avisos_block(summary: BootSummary) -> list[str]:
    """Render the CHECKS block.

    Each coherence check always prints its ✓ or ⚠️ line, decided by its discrepancy list
    (or its error when it could not run). The legacy-memory and setup warnings print only when they fire.
    """
    report = summary.health
    lines = ["CHECKS"]

    if report.legacy_commits_suspected is not None:
        lines.append(
            f"   ⚠️  {report.legacy_commits_suspected} commits en el historial, "
            f"0 notas reconocidas -- puede ser memoria del sistema anterior "
            "sin destilar"
        )

    if report.memory_setup_missing:
        lines.append("   ⚠️  la memoria de este proyecto no está montada:")
        for text in report.memory_setup_missing:
            lines.append(f"      - {text}")

    if report.install_uncommitted:
        lines.append(
            "   ⚠️  la instalación dejó sus cambios sin commit (rama protegida):"
            " commitéalos desde una rama de trabajo"
        )
        for path in report.install_uncommitted:
            lines.append(f"      - {path}")

    if report.plans_unreflected_error is not None:
        lines.append(
            "   ⚠️  no se pudo comprobar si hay planes sin reflejar: "
            f"{report.plans_unreflected_error}"
        )
    else:
        if report.issues_unanswered:
            lines.append(
                f"   ⚠️  GitHub no devolvio {_issue_refs(report.issues_unanswered)} "
                "(citadas en commits): sus planes no se comprobaron"
            )
        for issue_number, unreflected in report.plans_unreflected:
            plural = "" if unreflected == 1 else "s"
            lines.append(
                f"   ⚠️  plan #{issue_number}: {unreflected} commit{plural} sin "
                "reflejar en la issue"
            )

    if report.duplicate_ids:
        lines.append(
            f"   ⚠️  duplicate IDs: {', '.join(report.duplicate_ids)} -- "
            f"fix each with `{notes_duplicate.remove_relaunch('<id>')('<sha>')}`"
        )
        for sha, note in report.duplicate_notes:
            short = sha[:notes_duplicate.SHORT_SHA]
            lines.append(f"      - {note.id} {short} [{note.zone1}] [{note.zone2}] {note.headline}")
    else:
        lines.append(f"   ✓  no duplicate IDs ({report.git_notes} notes)")

    if report.archived_notes:
        numbers = (
            f"{report.index_lines} live + {report.archived_notes} archived / "
            f"{report.git_notes} notes"
        )
    else:
        numbers = f"{report.index_lines} lines / {report.git_notes} notes"
    if not report.index_discrepancies:
        lines.append(f"   ✓  indexes match git ({numbers})")
    else:
        lines.append(f"   ⚠️  indexes do not match git ({numbers})")
    for text in report.index_discrepancies:
        lines.append(f"      - {text}")

    if report.rule_discrepancies_error is not None:
        lines.append(
            "   ⚠️  no se pudo comprobar si las reglas coinciden con git: "
            f"{report.rule_discrepancies_error}"
        )
    else:
        rule_numbers = f"{report.rule_file_lines} lines / {report.rule_head_lines} committed"
        if not report.rule_discrepancies:
            lines.append(f"   ✓  rules match git ({rule_numbers})")
        else:
            lines.append(f"   ⚠️  rules do not match git ({rule_numbers})")
        for text in report.rule_discrepancies:
            lines.append(f"      - {text}")

    return lines


def render(summary: BootSummary) -> str:
    """Render the full boot text; blockers and restrictions are never truncated."""
    lines: list[str] = []
    lines.append(_box_border("╔", "╗"))
    lines.append(
        _box_content_line(
            f"  MEMORY · {summary.project}", f"{timefmt.utc_label(summary.generated_at)} "
        )
    )
    lines.append(_box_border("╚", "╝"))
    lines.append("")

    remote_block = _remote_block(summary.remote)
    if remote_block:
        lines.extend(remote_block)
        lines.append("")

    lines.extend(_next_block(summary.context))
    lines.append("")
    lines.extend(_blockers_section(summary.blockers))
    lines.append("")
    lines.extend(_restrictions_block(summary.restrictions))
    lines.append("")
    lines.extend(_recuentos_block(summary))
    lines.append("")
    lines.extend(_avisos_block(summary))
    lines.append("")

    if summary.health.memory_setup_missing:
        lines.extend(_SETUP_MISSING_HINT)
    elif summary.health.git_notes == 0:
        lines.extend(_FIRST_NOTE_HINT)
    else:
        lines.extend(_MAP_IS_SET)

    return "\n".join(lines)
