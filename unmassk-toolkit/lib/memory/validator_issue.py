"""Issue checks of the note validator: the issue exists on GitHub (via `gh`), and the Q/I issue gate.

Re-exported by validator.py; `gh` is the only external call, never git.
"""

import re
import shlex
import subprocess
from pathlib import Path

from model import Note, Rejection
import rejection as rejection_
from validator_pointers import carry_accepted_flags, description_flag

# Seconds for `gh issue view`; same value as health._GH_TIMEOUT.
_GH_TIMEOUT = 10

# gh's stderr when the number is no issue/PR; any other gh failure means "could not check".
_ISSUE_NOT_FOUND_MARKER = "Could not resolve to an issue or pull request"


def issue_exists(issue: int) -> bool:
    """True if `gh` confirms the issue exists, False if it confirms it does not.

    Any other outcome (gh missing, no network, timeout) raises RuntimeError. Also used by bin/memory/work.py.
    """
    try:
        # Explicit utf-8: the console codec (cp1252 on Windows) can leave stdout/stderr as None.
        proc = subprocess.run(
            ["gh", "issue", "view", str(issue), "--json", "number"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"gh issue view #{issue} no termino dentro de {_GH_TIMEOUT}s"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"no se pudo ejecutar 'gh' para comprobar la issue #{issue} "
            f"(no esta instalado, o no es ejecutable): {exc}"
        ) from exc

    if proc.returncode == 0:
        return True
    stderr = proc.stderr or ""
    if _ISSUE_NOT_FOUND_MARKER in stderr:
        return False
    raise RuntimeError(
        f"gh issue view #{issue} fallo: {stderr.strip() or (proc.stdout or '').strip()}"
    )


def validate_issue(note: Note, issue: int | None) -> Rejection | None:
    """Reject a note whose `--issue` number does not exist on GitHub; None issue calls no `gh`."""
    if issue is None:
        return None
    if issue_exists(issue):
        return None

    what = f"ACTA RECHAZADA — la issue #{issue} no existe en este repo"
    options = (
        "Esta es la única vez que se comprueba. Si el número está mal, el enlace",
        "decisión → plan queda roto para siempre y nadie lo va a notar.",
        "",
        "  gh issue list --limit 20          ver las abiertas",
        '  gh issue create --title "..."     crearla ahora',
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --issue <numero real>',
    )
    return rejection_.build(
        kind="issue_not_found", what=what, options=options, command=command
    )


# The issue-gate question, verbatim; the only copy.
_MEASURING_STICK = (
    "¿cerrar esta nota exige trabajo — código, medir, construir — o "
    "solo una respuesta/decisión?"
)

_HOLE_RE = re.compile(r"<[^<>]*>")


def _quote_given(note: Note) -> bool:
    """A real owner quote: not blank and not a relaunch's `<...>` hole pasted unfilled."""
    text = (note.quote or "").strip()
    return bool(text) and not _HOLE_RE.fullmatch(text)


def _quote_flag(note: Note) -> str:
    """` --quote` with the owner's words already given, else the hole to fill."""
    if _quote_given(note):
        return f" --quote {shlex.quote(note.quote)}"
    return ' --quote "<frase exacta del dueño>"'


def _reject_work_not_allowed(note: Note) -> Rejection:
    """Reject `--work` outside Q/I, worded like validator.validate_fields()'s field rejection."""
    what = f"el campo no encaja con el tipo {note.type}"
    options = (f"Estos campos no existen para el tipo {note.type}: work",)
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)}',
    )
    return rejection_.build(
        kind="field_not_allowed", what=what, options=options, command=command
    )


def _reject_missing_measuring_stick_answer(note: Note) -> Rejection:
    """Reject a Q/I note with neither `--issue` nor `--work`; offers the three relaunch commands."""
    what = f"{note.headline!r} no se guarda sin contestar la vara de medir"
    options = (
        _MEASURING_STICK,
        "",
        "  no, solo hace falta una respuesta/decision  ->  --work no",
        "  si, hace falta trabajo y ya hay una issue     ->  --issue N",
        "  si, hace falta trabajo y el dueño dice que no ->  --issue none --quote",
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --work no',
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --issue N',
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --issue none'
        f'{_quote_flag(note)}',
    )
    return rejection_.build(
        kind="missing_issue_gate_answer", what=what, options=options, command=command
    )


def _reject_issue_none_not_allowed(note: Note) -> Rejection:
    """Reject the `--issue none` sentinel outside Q/I; a real issue number stays valid."""
    what = f"--issue none no tiene sentido para el tipo {note.type}"
    options = (
        "El centinela 'none' es exclusivo de la aduana de issues (Q/I) -- fuera",
        "de ahi no existe la mecanica del \"no\" del dueño con cita.",
        "",
        "  un numero real de issue sigue funcionando  ->  --issue N",
        "  sin issue, simplemente omite la bandera     ->  (sin --issue)",
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)}',
    )
    return rejection_.build(
        kind="issue_none_not_allowed", what=what, options=options, command=command
    )


def _reject_issue_and_work_contradiction(note: Note) -> Rejection:
    """Reject `--issue N` together with `--work no` on Q/I: the two answers exclude each other."""
    what = f"{note.headline!r} contesta la vara de medir con issue y work a la vez"
    options = (
        "issue y work no pueden convivir: --issue N dice que hace falta trabajo,",
        "--work no dice que no hace falta -- son respuestas excluyentes.",
        "",
        "  hace falta trabajo, ya hay issue  ->  --issue N (sin --work)",
        "  no hace falta trabajo             ->  --work no (sin --issue)",
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --issue N',
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --work no',
    )
    return rejection_.build(
        kind="issue_work_contradiction", what=what, options=options, command=command
    )


def _reject_issue_none_missing_quote(note: Note) -> Rejection:
    """Reject `--issue none` without the owner's quote; there is no `--quote none` escape here."""
    what = f"{note.headline!r} necesita la cita literal del dueño"
    options = (
        "El no a abrir una issue es una decision del dueño, nunca un default",
        "silencioso -- trae sus palabras exactas con --quote.",
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{description_flag(note)}{carry_accepted_flags(note)} --issue none'
        f'{_quote_flag(note)}',
    )
    return rejection_.build(
        kind="issue_none_missing_quote", what=what, options=options, command=command
    )


def validate_issue_gate(note: Note, issue, work: str | None) -> Rejection | None:
    """Issue gate: only Q/I notes answer whether closing them needs work.

    `issue` is the raw `--issue` value (None, the literal "none", or an int), so an absent
    flag and an explicit "none" stay distinct. `work` is the raw `--work` value.
    """
    if note.type not in ("Q", "I"):
        if work is not None:
            return _reject_work_not_allowed(note)
        if issue == "none":
            return _reject_issue_none_not_allowed(note)
        return None

    if isinstance(issue, int) and work == "no":
        return _reject_issue_and_work_contradiction(note)

    if issue is None and work is None:
        return _reject_missing_measuring_stick_answer(note)

    if issue == "none" and not _quote_given(note):
        return _reject_issue_none_missing_quote(note)

    return None
