"""Contrato de aceptacion, en ROJO -- apertura de `--issue` a los siete
tipos de nota (D-044/D-045, memoria del proyecto).

Modo test-first, PASE DE CONTRATO (antes de que Ultron toque
produccion): estos tests fijan lo que define "hecho" para este cambio,
a granularidad de aceptacion -- no el barrido exhaustivo de ramas (ese
llega en el pase de endurecimiento, tras la implementacion real).

QUE CAMBIA (leido en produccion antes de escribir esto, nunca supuesto):

- `lib/memory/vocabulary.py::TYPES` -- de los siete `_TypeSpec`, solo
  `"M"` trae `"issue"` en su `allowed_fields`. Los otros seis (D, R, Q,
  X, I, B) NO lo traen -- `validator.validate_fields()` los rechaza hoy
  con "Estos campos no existen para el tipo <T>: issue" en cuanto
  `note.issue is not None`.
- `bin/memory/note.py::main()` llama a `validator.validate_issue()` (la
  comprobacion real contra `gh issue view`, en `validator_issue.py`)
  ANTES de `validate_pain_question`... no, al reves: primero
  `validate_pain_question`, LUEGO `validate_issue`, y solo despues
  `notes.write()/replace()` (que es quien dispara `validate_fields()`).
  Ese orden importa para este fichero: `validate_issue()` NO mira el
  tipo de la nota en absoluto (`validator_issue.py::validate_issue`, sin
  ninguna rama por `note.type`) -- ya rechaza una issue inexistente para
  CUALQUIER tipo, hoy, sin tocar nada. Lo que bloquea a los seis tipos
  no-M es exclusivamente `vocabulary.py`, mas abajo en la tuberia.
- `lib/memory/format.py::_body_field_line()` (la que arma el cuerpo del
  commit) tampoco mira el tipo para el campo `Issue` -- `if label ==
  "Issue": return f"Issue: #{note.issue}" if note.issue is not None else
  None`, sin condicion de tipo. El trailer de commit para un tipo no-M
  YA saldria bien si la nota llegara a guardarse.
- `lib/memory/report_render_note.py::_note_fields()`, linea 96, SI trae
  su propia condicion de tipo, aparte de la de vocabulary.py: `if
  note.type == "M" and note.issue is not None:` -- este es un SEGUNDO
  cierre, en un modulo distinto, que haria falta abrir ademas del de
  `vocabulary.py` para que `gitmem search --id` enseñe el numero de una
  nota no-M. Hallazgo para Ultron, no arreglado aqui.

Consecuencia para este fichero: abrir SOLO `vocabulary.py` (el cambio
minimo que D-044/D-045 piden) deja en verde los tests de aceptacion de
issue-existe-y-se-guarda y el trailer de commit (ninguno de los dos
pasa hoy por `report_render_note.py`), pero el test de ida y vuelta via
`gitmem search --id` (item 3 del encargo) exige TAMBIEN el segundo
arreglo -- por eso vive aparte, en su propia clase, y no se da por
hecho que "arreglar vocabulary.py" es suficiente para el contrato
entero.

QUE SIGUE SIN CAMBIAR (rechazado hoy, tiene que seguir rechazado
despues -- item 5 del encargo): `--awaits` solo lo admite B
(`vocabulary.TYPES["B"].allowed_fields`); `--stops` solo tiene efecto en
M/R (`validator.validate_pain_question`, `if note.type not in ("M",
"R"): return None`). Ninguno de los dos cambia con esta tarea.

COMO SE EVITA LA RED DE VERDAD PARA `gh issue view` [regla de esta
rama, unmassk-standards Sec.34.5: "mock solo cuando la dependencia no
puede correr aqui" -- una consulta de red no determinista es
exactamente ese caso]: `note.py` se prueba como PROCESO SEPARADO
(`run_memory_script`, conftest.py) -- un `monkeypatch.setattr(subprocess,
"run", ...)` en el proceso de test (la tecnica que SI usa
`test_health.py::_patch_gh` para `health.py`, que corre EN proceso) no
alcanza al hijo. El equivalente para un binario externo invocado por un
proceso hijo es un `gh` FALSO en el `PATH` que se le pasa a ese hijo
(`run_memory_script(..., env=...)`, ya soporta `env` sin sustituir el
heredado) -- `_fake_gh_dir()` mas abajo escribe un script de Python
ejecutable que entiende exactamente la forma que `validator_issue.py`
invoca (`gh issue view <N> --json number`) y responde con la MISMA
forma real que gh: returncode 0 para una issue que "existe", o
returncode !=0 con el marcador textual exacto que
`validator_issue.py::_ISSUE_NOT_FOUND_MARKER` ya declara y tiene
verificado en vivo contra gh real ("Could not resolve to an issue or
pull request..."). El falso `gh` no replica la LOGICA de
`validator_issue.py` (no decide nada por su cuenta) -- solo imita la
FORMA de la herramienta externa real, mismo criterio que ya usa
`test_health.py::_patch_gh` con `CompletedProcess` fingidos.

Ningun test de aqui toca produccion. Si algo de esto no encajara con lo
que Ultron acaba implementando, es un hallazgo, no un arreglo silencioso
aqui.
"""

import os

import pytest

from .conftest import (
    extract_note_id,
    run_git,
    run_memory_script,
    seed_zones_json,
)

_ZONE1 = "issuefieldzone"
_ZONE2 = "issuefieldzonetwo"

# (tipo, titular, descripcion, flags extra obligatorios para ESE tipo
# segun vocabulary.TYPES.required_fields -- D exige --why; M y R exigen
# --stops (no/yes respectivamente); B exige --awaits). Siete asuntos
# DISTINTOS, no variaciones de la misma frase -- mismo criterio que
# test_note_script.py::TestCreatesAllSevenNoteTypesForReal, para que
# ninguno rebote contra otro por similitud (`similar.find_similar`,
# `vocabulary.SIMILARITY_THRESHOLD`).
_SEVEN_TYPES_WITH_REQUIRED_FLAGS = [
    (
        "D",
        "retire the legacy CSV export in favor of the new bulk API",
        "The CSV export hasn't been touched in two years and the new bulk "
        "API already covers every field it exposed.",
        ["--why", "one export path is cheaper to maintain than two, and the "
                  "API path already has tests"],
    ),
    (
        "M",
        "the nightly backup job runs at 03:00 UTC",
        "Ops confirmed the cron schedule after last month's overlap with "
        "the deploy window.",
        ["--stops", "no"],
    ),
    (
        "R",
        "never call the billing webhook from inside a database transaction",
        "A webhook call inside an open transaction held a row lock for the "
        "full HTTP round trip and stalled every other writer last quarter.",
        ["--stops", "yes"],
    ),
    (
        "Q",
        "should a soft-deleted user still count toward the seat limit",
        "Sales keeps asking whether an offboarded-but-not-purged user frees "
        "up a licensed seat immediately or at the next billing cycle.",
        [],
    ),
    (
        "X",
        "dropped the idea of a client-side rate limiter",
        "Evaluated throttling requests in the browser before they reach the "
        "API; server-side limiting already covers the real risk.",
        [],
    ),
    (
        "I",
        "the search index went stale for six hours after a silent reindex failure",
        "The nightly reindex job exited early on a schema mismatch but the "
        "cron wrapper swallowed the non-zero exit code.",
        [],
    ),
    (
        "B",
        "waiting on the payments vendor to raise our sandbox rate limit",
        "Load testing checkout is stuck at fifty requests per minute until "
        "the vendor bumps the sandbox quota.",
        ["--awaits", "payments vendor support -- sandbox rate limit increase"],
    ),
]


def _fake_gh_dir(tmp_path, *, exists=(), missing=()):
    """Escribe un `gh` FALSO, ejecutable, en un directorio propio -- ver
    docstring del modulo para el porque (un proceso hijo no se puede
    parchear con `monkeypatch`). Entiende la UNICA forma real que
    `validator_issue.py::_issue_exists` invoca (`gh issue view <N>
    --json number`): `exists` devuelve returncode 0 (contenido de
    stdout irrelevante -- `_issue_exists` solo mira `returncode == 0`
    para el caso positivo); `missing` devuelve returncode 1 con el
    marcador textual REAL en stderr, verificado en vivo contra `gh`
    (`validator_issue.py::_ISSUE_NOT_FOUND_MARKER`). Cualquier otra
    invocacion sale con returncode 97 y un stderr que la nombra --
    ruidosa, no un cero inventado, si algun test la disparase sin
    querer.
    """
    gh_dir = tmp_path / "fake-gh-bin"
    gh_dir.mkdir(exist_ok=True)
    gh_path = gh_dir / "gh"
    exists_tuple = tuple(str(n) for n in exists)
    missing_tuple = tuple(str(n) for n in missing)
    script = f'''#!/usr/bin/env python3
import sys

EXISTS = {exists_tuple!r}
MISSING = {missing_tuple!r}

args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view":
    num = args[2]
    if num in EXISTS:
        sys.stdout.write('{{"number": ' + num + '}}')
        sys.exit(0)
    if num in MISSING:
        sys.stderr.write(
            "GraphQL: Could not resolve to an issue or pull request with "
            "the number of " + num + ". (repository.issue)"
        )
        sys.exit(1)

sys.stderr.write("fake gh (dante test double): unexpected invocation " + repr(args))
sys.exit(97)
'''
    gh_path.write_text(script, encoding="utf-8")
    gh_path.chmod(0o755)
    return str(gh_dir)


def _env_with_fake_gh(fake_gh_dir):
    return {"PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", "")}


def _seed_with_issue(repo, note_type, headline, description, issue, extra_flags, env):
    args = [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        "--issue", str(issue),
        *extra_flags,
    ]
    return run_memory_script("note.py", args, cwd=repo, env=env)


class TestSevenTypesAcceptIssueAndCarryItToARealCommitTrailer:
    """Items 1 y 4 del encargo, juntos a proposito: los dos transicionan
    de rojo a verde con el MISMO arreglo real (`vocabulary.py`,
    `allowed_fields` de los seis tipos que hoy no traen `"issue"`) --
    `format.py::_body_field_line()` ya escribe el trailer `Issue: #N`
    sin mirar el tipo (verificado leyendo el fichero, ver docstring del
    modulo), asi que separar esto en dos tests no cazaria un fallo
    adicional que el otro no cace ya.

    Hoy: rojo para D, R, Q, X, I, B (rc==1, rechazo real de
    `validator.validate_fields`: "Estos campos no existen para el tipo
    <T>: issue"); verde de partida para M (ya lo admite) -- se deja
    dentro de la tabla como guarda de no-regresion, no como caso nuevo.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags",
        _SEVEN_TYPES_WITH_REQUIRED_FLAGS,
        ids=[case[0] for case in _SEVEN_TYPES_WITH_REQUIRED_FLAGS],
    )
    def test_type_accepts_issue_and_commit_carries_the_real_trailer(
        self, tmp_repo, tmp_path, note_type, headline, description, extra_flags
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, exists=(issue_number,))
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo, note_type, headline, description, issue_number, extra_flags, env
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} (issue real, segun "
            f"el gh falso) tendria que guardarse sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)
        assert note_id.startswith(f"{note_type}-"), (
            f"el id real {note_id!r} no empieza por el prefijo de su propio tipo"
        )

        rc_log, commit_message, err_log = run_git(
            ["log", "-1", "--pretty=%B", "HEAD"], tmp_repo
        )
        assert rc_log == 0, f"git log fallo leyendo el commit real: {err_log}"
        assert f"Issue: #{issue_number}" in commit_message, (
            f"el commit real de {note_id} no lleva el trailer 'Issue: "
            f"#{issue_number}' -- mensaje real:\n{commit_message!r}"
        )


class TestIssueNotFoundRejectionAppliesToAllSevenTypes:
    """Item 2 del encargo: `validate_issue()` (la comprobacion real
    contra `gh issue view`) rechaza una issue que no existe -- para
    CUALQUIER tipo, no solo M.

    Nota de honestidad (test-first, se declara para no fingir un rojo
    que no hay): `validator_issue.py::validate_issue()` NO tiene ninguna
    rama por `note.type` -- se llama en `note.py::main()` ANTES de
    `notes.write()/replace()`, que es donde vive el gate de
    `vocabulary.py` que SI distingue por tipo. Este rechazo concreto ya
    funciona igual para los siete tipos HOY, sin tocar produccion --
    este test fija esa garantia como regresion (no se rompe al abrir
    `--issue` en `vocabulary.py`), no como capacidad nueva. Se mantiene
    en el contrato porque el encargo lo pide explicitamente ("ese
    rechazo tiene que seguir funcionando... no solo para M") y porque un
    arreglo futuro de `vocabulary.py` que reordenara las comprobaciones
    (issue-existe despues del gate de campos, por ejemplo) SI podria
    romperlo -- vale como red de seguridad aunque no sea rojo hoy.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags",
        _SEVEN_TYPES_WITH_REQUIRED_FLAGS,
        ids=[case[0] for case in _SEVEN_TYPES_WITH_REQUIRED_FLAGS],
    )
    def test_type_is_rejected_when_the_issue_does_not_exist(
        self, tmp_repo, tmp_path, note_type, headline, description, extra_flags
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        bogus_issue = 999999999
        fake_gh_dir = _fake_gh_dir(tmp_path, missing=(bogus_issue,))
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo, note_type, headline, description, bogus_issue, extra_flags, env
        )
        assert rc != 0, (
            f"tipo {note_type} con --issue {bogus_issue} (el gh falso confirma "
            f"que NO existe) tendria que rebotar -- salio rc=0, "
            f"stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err, (
            f"un rechazo real nunca es una traza de pila -- stdout={out!r} "
            f"stderr={err!r}"
        )
        assert str(bogus_issue) in out, (
            f"el rechazo deberia nombrar la issue #{bogus_issue} -- "
            f"salida real: {out!r}"
        )
        assert "no existe" in out, (
            f"el rechazo deberia decir que la issue no existe (mismo texto "
            f"real que validator_issue.py::validate_issue) -- salida: {out!r}"
        )


class TestIssueSurvivesTheRoundTripThroughSearchById:
    """Item 3 del encargo (unmassk-standards Sec.34 -- ida y vuelta
    real): se guarda una nota REAL de un tipo no-M con `--issue N`, y se
    lee de vuelta con `search.py --id <ID>` (el mismo binario que
    `gitmem search --id` despacha, ver conftest.py -- ningun literal
    esperado se teclea a mano: `issue_number` es la ENTRADA que este
    mismo test le paso al escritor, y la asercion comprueba que ESA
    MISMA cadena sobrevive el viaje completo, no un valor inventado
    aparte).

    Este es el UNICO test de este fichero que exige el SEGUNDO arreglo
    (`report_render_note.py:96`, `if note.type == "M" and note.issue is
    not None:` -- ver docstring del modulo): abrir solo
    `vocabulary.py` deja pasar el alta (clase de arriba) pero
    `search.py --id` seguiria sin enseñar el numero para un tipo no-M,
    porque ese segundo cierre es independiente del primero.
    """

    def test_a_question_notes_issue_number_appears_in_search_by_id_output(
        self, tmp_repo, tmp_path
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, exists=(issue_number,))
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo,
            "Q",
            "does a paused subscription still block a duplicate signup",
            "Support found a user who paused instead of cancelling and then "
            "hit the duplicate-account guard on a fresh signup.",
            issue_number,
            [],
            env,
        )
        assert rc == 0, (
            f"la siembra (tipo Q, --issue {issue_number}) tendria que "
            f"guardarse sin rebotar -- stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", ["--id", note_id], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py --id {note_id} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert f"Issue: #{issue_number}" in search_out, (
            f"el numero de issue con el que se guardo {note_id} "
            f"({issue_number}) no sobrevivio la ida y vuelta por "
            f"'search.py --id' -- salida real:\n{search_out!r}"
        )


class TestOpeningIssueDidNotLoosenOtherTypeGatedFields:
    """Item 5 del encargo: abrir `issue` en los siete tipos no puede
    abrir la mano con otros campos que siguen siendo de un tipo
    concreto. Los dos ya pasan hoy (no dependen de `--issue` en
    absoluto) -- se fijan aqui como guarda explicita de que seguir
    pasando despues del cambio, tal como pide el encargo ("un test que
    fije que los demas campos siguen rechazandose donde no tocan").
    """

    def test_awaits_is_still_rejected_outside_type_b(self, tmp_repo):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", _ZONE1, _ZONE2,
                "switch the on-call rotation tool from PagerDuty to Opsgenie",
                "--why", "the team already standardized on the rest of the "
                         "Atlassian suite and licensing is bundled",
                "--description", "PagerDuty's contract is up for renewal; "
                                  "Opsgenie is already paid for via the "
                                  "Atlassian bundle.",
                "--awaits", "legal -- contract sign-off",
            ],
            cwd=tmp_repo,
        )
        assert rc != 0, (
            "un D con --awaits deberia seguir rebotando -- awaits solo "
            f"existe para B, esto no cambia con la apertura de issue. "
            f"salio rc=0: stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err
        assert "awaits" in out, (
            f"el rechazo deberia nombrar el campo que sobra (awaits) -- "
            f"salida real: {out!r}"
        )

    def test_stops_still_has_no_effect_outside_m_and_r(self, tmp_repo):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        headline = "dropped the idea of auto-archiving stale draft notes"
        rc, out, err = run_memory_script(
            "note.py",
            [
                "X",
                "--zones", _ZONE1, _ZONE2,
                headline,
                "--description", "Considered auto-archiving Q/D drafts after "
                                  "ninety days of no activity; too easy to "
                                  "silently lose an open question.",
                "--stops", "yes",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, (
            f"--stops no deberia significar nada para X (solo M/R lo leen) "
            f"-- tendria que guardarse igual que sin el flag, salio "
            f"rc={rc}: stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)
        assert note_id.startswith("X-"), (
            f"--stops yes no puede haber forzado el tipo a R -- id real "
            f"{note_id!r}"
        )
