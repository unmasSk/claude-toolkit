"""Contrato en ROJO -- Moriarty T2, punto 3 (2026-08-26): `--issue none`
se cuela en silencio, resuelto a "sin issue", en los cinco tipos que
NUNCA pasan por la aduana de issues (D-065/D-066 es exclusiva de Q/I).

EL FALLO, confirmado leyendo el codigo real y reproducido en vivo antes
de escribir esto:

1. `bin/memory/note.py::_issue_arg` (linea ~101) acepta el centinela
   literal `"none"` para CUALQUIER tipo desde que Ultron abrio `--issue`
   a aceptarlo (el hueco estructural que
   `note-issue-gate-work-quote-contract-notes.md` Ronda 1 dejo escrito
   para el CLI, ya cerrado). Antes de eso, `--issue none` reventaba en
   `argparse` para los siete tipos por igual -- ahora parsea limpio para
   los siete, D/M/R/X/B incluidos.

2. `validator_issue.py::validate_issue_gate` (linea ~268) SOLO mira el
   centinela `"none"` DENTRO de la rama `note.type in ("Q", "I")`:

       if note.type not in ("Q", "I"):
           if work is not None:
               return _reject_work_not_allowed(note)
           return None          # <-- issue=="none" nunca se mira aqui

   Para D/M/R/X/B con `--issue none` y sin `--work`, esta funcion
   devuelve `None` (nada que rechazar) SIN comprobar el valor de `issue`
   en absoluto.

3. `bin/memory/note.py::_build_candidate` (linea ~260) resuelve
   `issue = args.issue if isinstance(args.issue, int) else None` --
   el centinela `"none"` (una `str`, no un `int`) se convierte en
   `candidate.issue = None`, INDISTINGUIBLE de "nunca se dio `--issue`".

4. `validator_issue.py::validate_issue(candidate, candidate.issue)`
   (linea ~142) devuelve `None` de inmediato cuando `issue is None` --
   "no hay nada que comprobar", sin llamar a `gh` ni rechazar nada.

Resultado: `gitmem note D --issue none ...` (o M/R/X/B) se guarda
IGUAL que si `--issue` nunca se hubiera dado -- el `"none"` explicito
que el usuario tecleo desaparece en silencio, sin que el sistema deje
ningun rastro de que alguien pidio "sin issue, a proposito" en vez de
"no lo pense". Reproducido en vivo antes de escribir esto: `note.py D
--why "..." --issue none` (sin `--work`, que ni siquiera existe fuera de
Q/I) sale con `rc == 0` y guarda `D-001` hoy.

Contrato exigido: `--issue none` en D/M/R/X/B tiene que RECHAZARSE --
esos cinco tipos no tienen la mecanica de "el dueño dijo que no, con
cita" que D-065/D-066 reservo para Q/I; el centinela `"none"` no tiene
ningun significado valido fuera de esa mecanica, y aceptarlo en silencio
resuelto a "ausente" pierde la intencion real de quien lo tecleo.

Cada test compara dos cosas escritas por separado: el estado REAL del
repositorio (recuento de commits + HEAD, via `git` real) antes y despues
del intento rechazado -- nunca una suposicion sobre "seguro que no se
escribio nada".

LIMITE explicito de esta tarea: solo test, en `tests/memory/`. No se
toca `lib/`, `bin/` ni `hooks/` -- el rojo es correcto al entregar. No
se inventa el texto exacto del rechazo (Ultron todavia no lo escribio):
se fijan propiedades verificables (rc != 0, nada escrito, la palabra
"issue" presente en la salida) en vez de una prosa adivinada -- mismo
criterio que `customs-py-full-contract-notes.md` Ronda 2 usa para un
rechazo sin redaccion todavia decidida.
"""

import os
import sys

import pytest

from .conftest import path_without_real_gh, run_git, run_memory_script, seed_zones_json

_ZONE1 = "issuenoneothertypeszone"
_ZONE2 = "issuenoneothertypeszonetwo"

# CI incident 2026-08-22 (conftest.py::path_without_real_gh, reproducido
# tambien por `test_note_issue_gate.py`): en Windows,
# `subprocess.run(["gh", ...])` sin `shell=True` nunca resuelve un
# fichero sin extension `.exe` -- estructural, no arreglable desde el
# lado del test. Se salta explicito, solo en el control que necesita que
# el `gh` falso gane la resolucion de PATH.
_WIN_GH_SKIP_REASON = (
    "tecnica de gh falso en PATH: en Windows, subprocess.run(['gh', ...]) "
    "sin shell=True nunca resuelve un fichero sin extension .exe -- "
    "estructural, no arreglable sin tocar validator_issue.py (fuera de "
    "alcance de Dante)"
)
_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason=_WIN_GH_SKIP_REASON
)


def _fake_gh_dir(tmp_path, issue_number):
    """`gh` FALSO, ejecutable, que siempre confirma que `issue_number`
    existe -- mismo mecanismo (y misma forma real invocada:
    `gh issue view <N> --json number`) que `test_note_issue_gate.py::
    _fake_gh_dir`, reproducido aqui como helper LOCAL por la convencion
    ya fijada en este directorio (cada fichero de contrato mantiene su
    propio helper, ver `note-py-script-full-contract-notes.md`).
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

# (tipo, titular, descripcion, flags extra obligatorios del tipo) -- un
# asunto DISTINTO por tipo, mismo criterio que
# `note-issue-gate-work-quote-contract-notes.md` ya documenta para evitar
# que un tipo rebote contra otro por parecido (`similar.find_similar`).
_OTHER_FIVE_TYPES = [
    (
        "D",
        "retire the nightly backup script in favor of the managed snapshot",
        "The nightly backup script has needed manual babysitting twice "
        "this quarter; the managed snapshot service already covers the "
        "same retention window.",
        ["--why", "one less script paging someone at 3am for a free "
                  "managed alternative that already exists"],
    ),
    (
        "M",
        "the release train cuts every other Tuesday at 14:00 UTC",
        "Support kept asking why a hotfix missed the train after the "
        "schedule moved off a plain weekly cadence last spring.",
        ["--stops", "no"],
    ),
    (
        "R",
        "never read the session token from the request body in a GET handler",
        "A GET handler read the token from the body instead of the header "
        "last year and logging middleware persisted it in plaintext.",
        ["--stops", "yes"],
    ),
    (
        "X",
        "dropped the idea of a standalone mobile app for status checks",
        "Evaluated a companion mobile app; the existing responsive web "
        "dashboard already covers the same status-check flow.",
        [],
    ),
    (
        "B",
        "waiting on the payments vendor to confirm the new webhook schema",
        "The reconciliation job is stuck until the payments vendor "
        "confirms the new webhook payload shape they announced.",
        ["--awaits", "payments vendor -- confirm new webhook schema"],
    ),
]


def _note_args(note_type, headline, description, extra_flags):
    return [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        *extra_flags,
        "--issue", "none",
    ]


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _head_sha(repo):
    rc, out, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, f"git rev-parse HEAD fallo en el test: {err}"
    return out


class TestIssueNoneIsRejectedOutsideQAndI:
    """Los cinco tipos sin mecanica de "el dueño dijo que no" -- D-065/
    D-066 es exclusiva de Q/I; el centinela `"none"` no tiene sentido
    fuera de ahi y hoy se cuela resuelto a `None` en silencio."""

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags",
        _OTHER_FIVE_TYPES,
        ids=[case[0] for case in _OTHER_FIVE_TYPES],
    )
    def test_issue_none_is_rejected_and_nothing_is_written(
        self, tmp_repo, note_type, headline, description, extra_flags,
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before_count = _git_commit_count(tmp_repo)
        before_head = _head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, extra_flags),
            cwd=tmp_repo,
        )

        assert rc != 0, (
            f"tipo {note_type} con --issue none (sin mecanica de "
            f"D-065/D-066, exclusiva de Q/I) tendria que rebotar -- salio "
            f"rc=0, stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err, (
            f"un rechazo real nunca es una traza de pila -- stdout={out!r} "
            f"stderr={err!r}"
        )
        combined = out + err
        assert "issue" in combined.lower(), (
            f"el rechazo tiene que nombrar el campo issue -- salida real: "
            f"{combined!r}"
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
class TestIssueNIsStillAcceptedOutsideQAndI:
    """Control de no-sobrecorreccion, GREEN hoy y debe seguir GREEN: un
    numero REAL de issue en D/M/R/X/B sigue funcionando -- el contrato
    exigido es "`--issue none` rebota", nunca "`--issue` deja de
    funcionar del todo fuera de Q/I" (D-044/D-045 ya lo dejo disponible
    en los siete tipos)."""

    def test_issue_number_still_saves_for_type_d(self, tmp_repo, tmp_path):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 5555
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = run_memory_script(
            "note.py",
            [
                "D", "--zones", _ZONE1, _ZONE2,
                "retire the nightly backup script in favor of managed snapshots",
                "--description", "control case: a real issue number must "
                                  "still work outside Q/I",
                "--why", "confirms the fix does not overtighten --issue "
                         "itself, only the none sentinel",
                "--issue", str(issue_number),
            ],
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, (
            f"un numero real de issue en D tiene que seguir guardandose "
            f"sin rebotar -- stdout={out!r} stderr={err!r}"
        )
