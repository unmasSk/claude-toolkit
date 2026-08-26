"""Contrato en ROJO -- Moriarty, punto 4 (2026-08-26, gravedad baja):
`--issue N` y `--work no` juntos en una `Q`/`I` se aceptan en silencio
siendo contradictorios entre si.

EL FALLO, confirmado leyendo el codigo real y reproducido en vivo antes
de escribir esto: `validator_issue.py::validate_issue_gate`
(linea ~243-280) hace tres comprobaciones INDEPENDIENTES entre si (dice
su propio docstring, "Orden de las tres comprobaciones, todas
independientes"):

    if issue is None and work is None:
        return _reject_missing_measuring_stick_answer(note)   # D-065

    quote_has_content = note.quote is not None and note.quote.strip()
    if issue == "none" and not quote_has_content:
        return _reject_issue_none_missing_quote(note)          # D-066

Ninguna de las dos mira la COMBINACION -- `issue` es un `int` real (no
`None`, no el centinela `"none"`) Y `work == "no"` A LA VEZ pasa las dos
comprobaciones sin disparar ninguna: la primera exige `issue is None and
work is None` (falso, `issue` no es `None`), la segunda exige
`issue == "none"` (falso, es un `int`). El resultado es una `Note` que
dice DOS cosas incompatibles al mismo tiempo -- "esto necesita trabajo,
aqui esta la issue" (`--issue N`) y "esto NO necesita trabajo" (`--work
no`) -- guardada sin que nadie la contradiga.

Reproducido en vivo antes de escribir esto (con un `gh` falso que
confirma que la issue existe, para aislar esta comprobacion de
`validate_issue`/`gh issue view`, que es un asunto DISTINTO -- ver
`test_note_issue_gate.py::TestIssueNAlonePassesThroughTheExistingValidator`):
`note.py Q --issue 4242 --work no ...` guarda `Q-001` con `rc == 0` hoy.

Contrato exigido: la combinacion `--issue N` + `--work no` en una Q/I
tiene que rechazarse con un mensaje que nombre la contradiccion -- las
dos respuestas a la vara de medir ("hace falta trabajo" / "no hace
falta trabajo") no pueden convivir en la misma nota.

Cada test compara dos cosas escritas por separado: el estado REAL del
repositorio (recuento de commits + HEAD) antes y despues del intento
rechazado -- nunca una suposicion sobre "seguro que no se escribio
nada".

Tecnica de `gh` FALSO en el `PATH`, identica a
`test_note_issue_gate.py`/`test_note_issue_none_regression_other_types.py`
(ver sus docstrings para el porque completo -- unmassk-standards
Sec.34.5). Reproducida aqui como helper local, misma convencion ya
fijada en este directorio.

LIMITE explicito de esta tarea: solo test, en `tests/memory/`. No se
toca `lib/`, `bin/` ni `hooks/` -- el rojo es correcto al entregar. No
se inventa el texto exacto del rechazo (Ultron todavia no lo escribio):
se fijan propiedades verificables (rc != 0, nada escrito, las palabras
"issue" y "work" presentes en la salida) en vez de una prosa adivinada.
"""

import os
import sys

import pytest

from .conftest import path_without_real_gh, run_git, run_memory_script, seed_zones_json

_ZONE1 = "issueworkcontradictionzone"
_ZONE2 = "issueworkcontradictionzonetwo"

# Mismo motivo/tecnica que los otros dos ficheros hermanos de esta
# misma tanda -- ver sus docstrings.
_WIN_GH_SKIP_REASON = (
    "tecnica de gh falso en PATH: en Windows, subprocess.run(['gh', ...]) "
    "sin shell=True nunca resuelve un fichero sin extension .exe -- "
    "estructural, no arreglable sin tocar validator_issue.py (fuera de "
    "alcance de Dante)"
)
_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason=_WIN_GH_SKIP_REASON
)

# Dos asuntos distintos, uno por tipo gateado -- mismo criterio
# anti-colision (`similar.find_similar`) que el resto de esta serie.
_QI_CASES = [
    (
        "Q",
        "does a canceled trial still count toward the seat limit for billing",
        "Finance flagged that a canceled trial account might still be "
        "counted toward the seat total until the next reconciliation run.",
    ),
    (
        "I",
        "the retry queue kept redelivering the same webhook for eleven hours",
        "A missing acknowledgment step let the retry worker redeliver the "
        "same webhook payload every five minutes until someone noticed the "
        "duplicate charges.",
    ),
]


def _fake_gh_dir(tmp_path, issue_number):
    """`gh` FALSO que siempre confirma que `issue_number` existe --
    aisla esta comprobacion (la contradiccion `--issue`+`--work`) de
    `validate_issue()`/`gh issue view`, un asunto distinto. Mismo
    mecanismo que los ficheros hermanos, reproducido como helper local.
    """
    gh_dir = tmp_path / "fake-gh-bin"
    gh_dir.mkdir(exist_ok=True)
    gh_path = gh_dir / "gh"
    script = f'''#!/usr/bin/env python3
import sys

args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view" and args[2] == "{issue_number}":
    sys.stdout.write('{{"number": {issue_number}}}')
    sys.exit(0)
sys.stderr.write("fake gh (dante test double): unexpected invocation " + repr(args))
sys.exit(97)
'''
    gh_path.write_text(script, encoding="utf-8")
    gh_path.chmod(0o755)
    return str(gh_dir)


def _env_with_fake_gh(fake_gh_dir):
    return {"PATH": fake_gh_dir + os.pathsep + path_without_real_gh()}


def _note_args(note_type, headline, description, issue_number):
    return [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        "--issue", str(issue_number),
        "--work", "no",
    ]


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _head_sha(repo):
    rc, out, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, f"git rev-parse HEAD fallo en el test: {err}"
    return out


@_skip_on_windows
class TestIssueNumberAndWorkNoTogetherAreRejected:
    """`--issue N` ("hace falta trabajo, aqui esta la issue") y
    `--work no` ("no hace falta trabajo") en la MISMA nota se
    contradicen -- hoy ninguna de las tres comprobaciones de
    `validate_issue_gate` mira esta combinacion, y la nota se guarda con
    las dos respuestas a la vez."""

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_contradiction_is_rejected_and_nothing_is_written(
        self, tmp_repo, tmp_path, note_type, headline, description,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)
        before_count = _git_commit_count(tmp_repo)
        before_head = _head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, issue_number),
            cwd=tmp_repo,
            env=env,
        )

        assert rc != 0, (
            f"tipo {note_type} con --issue {issue_number} --work no a la "
            f"vez (contradictorio: una cosa dice que hace falta trabajo, "
            f"la otra que no) tendria que rebotar -- salio rc=0, "
            f"stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err, (
            f"un rechazo real nunca es una traza de pila -- stdout={out!r} "
            f"stderr={err!r}"
        )
        combined = out + err
        assert "issue" in combined.lower() and "work" in combined.lower(), (
            f"el rechazo tiene que nombrar los dos campos en contradiccion "
            f"(issue y work) -- salida real: {combined!r}"
        )

        after_count = _git_commit_count(tmp_repo)
        after_head = _head_sha(tmp_repo)
        assert after_count == before_count, (
            f"un rechazo no puede crear un commit -- antes={before_count} "
            f"despues={after_count}"
        )
        assert after_head == before_head, (
            f"un rechazo no puede mover HEAD -- antes={before_head} "
            f"despues={after_head}"
        )


@_skip_on_windows
class TestIssueNumberAloneStillWorksWithoutWork:
    """Control de no-sobrecorreccion, GREEN hoy y debe seguir GREEN:
    `--issue N` SIN `--work` sigue guardandose normal -- el contrato
    exigido es "la COMBINACION de los dos rebota", nunca "`--issue` deja
    de aceptarse solo" (ya cubierto ademas por
    `test_note_issue_gate.py::TestIssueNAlonePassesThroughTheExistingValidator`,
    repetido aqui solo como guarda local de este fichero)."""

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_issue_alone_still_saves(
        self, tmp_repo, tmp_path, note_type, headline, description,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 4243
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = run_memory_script(
            "note.py",
            [
                note_type, "--zones", _ZONE1, _ZONE2, headline,
                "--description", description,
                "--issue", str(issue_number),
            ],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} SOLO (sin "
            f"--work) tiene que seguir guardandose sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )


class TestWorkNoAloneStillWorksWithoutIssue:
    """Control de no-sobrecorreccion, GREEN hoy y debe seguir GREEN:
    `--work no` SIN `--issue` sigue guardandose normal -- el contrato
    exigido es "la COMBINACION rebota", nunca "`--work no` deja de
    aceptarse solo"."""

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_work_no_alone_still_saves(
        self, tmp_repo, note_type, headline, description,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])

        rc, out, err = run_memory_script(
            "note.py",
            [
                note_type, "--zones", _ZONE1, _ZONE2, headline,
                "--description", description,
                "--work", "no",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, (
            f"tipo {note_type} con --work no SOLO (sin --issue) tiene que "
            f"seguir guardandose sin rebotar -- stdout={out!r} "
            f"stderr={err!r}"
        )
