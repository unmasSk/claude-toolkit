"""Contrato de aceptacion, en ROJO -- la aduana de issues en el guardado
de notas `Q`/`I` (D-065/D-066, decision cerrada del propietario,
2026-08-26, recuperadas con `gitmem search --id D-065`/`D-066`).

Modo test-first, PASE DE CONTRATO (antes de que Ultron toque
produccion): estos tests fijan lo que define "hecho" para este cambio,
a granularidad de aceptacion -- no el barrido exhaustivo de ramas (ese
llega en el pase de endurecimiento, tras la implementacion real). Ningun
test de aqui toca produccion (`lib/`/`bin/` sin editar, limite explicito
del encargo).

EL CONTRATO, siete puntos del encargo mapeados 1:1 a las clases de este
fichero:

1/2. `gitmem note Q ...` / `gitmem note I ...` SIN `--issue` y SIN
     `--work` -> RECHAZO (exit != 0, nada escrito: ni commit ni indice
     tocado) con un mensaje que trae LA VARA DE MEDIR literal y las TRES
     opciones de relanzamiento literales que D-065/D-066 fijan.
3.   `--work no` -> la nota pasa y se guarda normal, sin issue.
4.   `--issue N` (sin `--work`) -> pasa por el validador YA EXISTENTE
     (`gh issue view`), exactamente como hoy -- CONTROL, ya verde
     (Q/I ya traen `issue` en `vocabulary.TYPES[...].allowed_fields`
     desde D-044/D-045, y ningun gate nuevo bloquea esta ruta).
5.   `--issue none` SIN `--quote` -> RECHAZO pidiendo la frase literal
     del propietario. CON `--quote "<frase>"` -> pasa, y la cita
     sobrevive el viaje de ida y vuelta (commit real + `search.py --id`).
6.   Los otros cinco tipos (D, M, R, X, B) NO pasan esta puerta -- se
     siguen guardando igual que hoy, sin `--work` ni `--issue`.
     CONTROL/regresion.
7.   `--work` en un tipo que no es Q/I -> rechazado como campo no
     aceptado para ese tipo (misma mecanica que `validate_fields()` ya
     usa para `--awaits` fuera de B, `test_note_issue_field.py::
     test_awaits_is_still_rejected_outside_type_b`).

HALLAZGO ESTRUCTURAL, leido en produccion antes de escribir esto, no
arreglado aqui (fuera del limite de esta tarea -- solo tests): `bin/
memory/note.py::_parse_args` declara `--issue` con `type=int` (linea
102). El diseno (punto 5) exige que `--issue none` funcione como
CENTINELA LITERAL de cadena -- el mismo patron que `--replaces` ya
soporta (`--replaces`, sin `type=`, cadena libre, distinguido de un id
real en `_handle_write_or_replace` con `args.replaces != "none"`). Con
`type=int` tal como esta hoy, `--issue none` revienta en el propio
argparse ANTES de llegar a ningun validador ("argument --issue: invalid
int value: 'none'") -- ya sale con `rc != 0` hoy, pero por una razon
distinta a la que el contrato pide (un fallo de tipeo de CLI, no la
comprobacion real de `--quote`). Los tests de la clase 5 fijan el
COMPORTAMIENTO FINAL exigido (mensaje pidiendo la cita, nunca un error
de argparse) -- hoy son rojos por esta razon estructural entre otras;
Ultron necesita abrir `--issue` a aceptar el centinela ademas de un
entero.

`--work` TAMPOCO existe como flag de `_parse_args` hoy -- cualquier uso
de `--work <valor>`, en cualquier tipo, revienta hoy en argparse
("unrecognized arguments: --work ...", en stderr). Eso ya deja `rc !=
0` para las clases 1/2/7 sin que la logica de negocio real exista
todavia -- los tests de este fichero no se conforman con "rc != 0": cada
uno pide ademas el TEXTO real que la aduana debe mostrar una vez
implementada, que hoy NO aparece (ni la vara de medir, ni "work" en la
salida de la validacion de campos por tipo), asi que siguen rojos por
la razon correcta, no por casualidad de un `rc` que ya no era 0 antes.

Tecnica de `gh` FALSO en el `PATH`, identica a
`test_note_issue_field.py` (ver su docstring para el porque completo --
unmassk-standards Sec.34.5, un `gh issue view` real es una consulta de
red no determinista, se sustituye por un binario que solo imita la
FORMA de la herramienta real). Reproducida aqui en vez de compartida via
`conftest.py` -- convencion ya fijada en este directorio (cada fichero
de contrato mantiene su propio helper local; ver
`note-py-script-full-contract-notes.md`, "Fixture gap closed locally,
not in conftest.py").
"""

import os
import sys

import pytest

from .conftest import extract_note_id, path_without_real_gh, run_git, run_memory_script, seed_zones_json

# CI incident 2026-08-22 (conftest.py::path_without_real_gh): en Windows,
# `subprocess.run(["gh", ...])` sin `shell=True` (produccion, no tocada
# aqui) nunca resuelve un fichero sin extension `.exe` -- estructural, no
# arreglable desde el lado del test. Se salta explicito, nunca en
# silencio, solo en los tests que dependen de que el `gh` falso gane la
# resolucion de PATH (la clase 4, la unica de este fichero que invoca
# `gh` de verdad).
_WIN_GH_SKIP_REASON = (
    "tecnica de gh falso en PATH: en Windows, subprocess.run(['gh', ...]) "
    "sin shell=True nunca resuelve un fichero sin extension .exe -- "
    "estructural, no arreglable sin tocar validator_issue.py (fuera de "
    "alcance de Dante)"
)
_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason=_WIN_GH_SKIP_REASON
)

_ZONE1 = "issuegatezone"
_ZONE2 = "issuegatezonetwo"

# La vara de medir literal, y las tres opciones de relanzamiento
# literales -- D-065/D-066, tal como el encargo las fija. Constantes en
# vez de repetidas: si algun test las teclea distinto del resto por un
# typo, el fallo salta en el propio test, no en produccion.
_VARA_DE_MEDIR = (
    "¿cerrar esta nota exige trabajo — código, medir, construir — o "
    "solo una respuesta/decisión?"
)
_RELANZA_WORK_NO = "--work no"
_RELANZA_ISSUE_N = "--issue N"
_RELANZA_ISSUE_NONE_QUOTE = '--issue none --quote "<frase exacta del dueño>"'

# (tipo, titular, descripcion) -- dos asuntos DISTINTOS (ni una
# variacion de la misma frase), mismo criterio que
# `test_note_issue_field.py::_SEVEN_TYPES_WITH_REQUIRED_FLAGS` para que
# ninguno rebote contra el otro por similitud (`similar.find_similar`).
# Q e I no exigen ningun flag adicional aparte de `--description`
# (`vocabulary.TYPES["Q"/"I"].required_fields == {"description"}`).
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

# Los otros cinco tipos, con sus flags obligatorios propios
# (`vocabulary.TYPES[<T>].required_fields`) -- asuntos distintos de los
# de `_QI_CASES` y entre si.
_OTHER_FIVE_TYPES = [
    (
        "D",
        "retire the internal wiki in favor of the new docs site",
        "The internal wiki hasn't been updated in a year and the new docs "
        "site already mirrors every page anyone still reads.",
        ["--why", "one source of truth is cheaper than reconciling two, and "
                  "the new site already has search"],
    ),
    (
        "M",
        "the weekly digest email goes out every Monday at 09:00 local time",
        "Support confirmed the schedule after a customer asked why it never "
        "arrives on holidays.",
        ["--stops", "no"],
    ),
    (
        "R",
        "never write to the shared config file from a background thread",
        "A background thread wrote to the shared config file while the main "
        "thread was mid-read and corrupted it silently last quarter.",
        ["--stops", "yes"],
    ),
    (
        "X",
        "dropped the idea of a browser extension for quick note capture",
        "Evaluated a companion browser extension; the existing CLI already "
        "covers the same capture flow without a second codebase.",
        [],
    ),
    (
        "B",
        "waiting on the analytics vendor to backfill last month's data",
        "The monthly report is stuck until the analytics vendor finishes "
        "backfilling the gap their outage caused.",
        ["--awaits", "analytics vendor support -- backfill last month"],
    ),
]


def _fake_gh_dir(tmp_path, *, exists=(), missing=()):
    """`gh` FALSO, ejecutable, en un directorio propio -- ver docstring
    del modulo. Entiende la UNICA forma real que
    `validator_issue.py::_issue_exists` invoca (`gh issue view <N>
    --json number`).
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
    return {"PATH": fake_gh_dir + os.pathsep + path_without_real_gh()}


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _head_sha(repo):
    rc, out, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, f"git rev-parse HEAD fallo en el test: {err}"
    return out


def _note_args(note_type, headline, description, *extra_flags):
    return [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        *extra_flags,
    ]


class TestNoIssueNoWorkIsRejectedForQAndI:
    """Puntos 1 y 2 del encargo, juntos a proposito -- Q e I comparten la
    MISMA puerta con el MISMO texto (D-065/D-066 no distingue entre los
    dos tipos), asi que separarlos en dos clases no cazaria un fallo
    adicional que el otro no cace ya.

    Hoy: rc == 0 (nada bloquea esto todavia) -- rojo real, no por rc
    solamente sino porque el mensaje exigido (vara de medir + tres
    opciones de relanzamiento) no existe en ninguna salida hoy.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_rejected_with_the_measuring_stick_and_three_relaunch_options(
        self, tmp_repo, note_type, headline, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before_count = _git_commit_count(tmp_repo)
        before_head = _head_sha(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py", _note_args(note_type, headline, description), cwd=tmp_repo
        )

        assert rc != 0, (
            f"tipo {note_type} sin --issue y sin --work tendria que "
            f"rebotar -- salio rc=0, stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err, (
            f"un rechazo real nunca es una traza de pila -- stdout={out!r} "
            f"stderr={err!r}"
        )
        combined = out + err
        assert _VARA_DE_MEDIR in combined, (
            f"el rechazo tiene que traer la vara de medir literal -- "
            f"salida real: {combined!r}"
        )
        assert _RELANZA_WORK_NO in combined, (
            f"el rechazo tiene que ofrecer '{_RELANZA_WORK_NO}' como "
            f"relanzamiento -- salida real: {combined!r}"
        )
        assert _RELANZA_ISSUE_N in combined, (
            f"el rechazo tiene que ofrecer '{_RELANZA_ISSUE_N}' como "
            f"relanzamiento -- salida real: {combined!r}"
        )
        assert _RELANZA_ISSUE_NONE_QUOTE in combined, (
            f"el rechazo tiene que ofrecer {_RELANZA_ISSUE_NONE_QUOTE!r} "
            f"como relanzamiento -- salida real: {combined!r}"
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

        # Nada escrito de verdad tambien en el sentido del contador de
        # ids: una siembra valida INMEDIATAMENTE DESPUES tiene que
        # recibir el primer id del tipo, nunca el segundo -- si el
        # intento rechazado hubiera consumido un id igualmente, esta
        # siembra saldria "<T>-002" en vez de "<T>-001".
        rc_ok, out_ok, err_ok = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, "--work", "no"),
            cwd=tmp_repo,
        )
        assert rc_ok == 0, (
            f"la siembra de control tras el rechazo deberia pasar -- "
            f"stdout={out_ok!r} stderr={err_ok!r}"
        )
        note_id = extract_note_id(out_ok)
        assert note_id == f"{note_type}-001", (
            f"el intento rechazado no puede haber consumido un id -- "
            f"id real de la primera nota valida: {note_id!r}"
        )


class TestWorkNoSavesNormallyWithoutIssue:
    """Punto 3 del encargo: `--work no` deja pasar la nota, guardada
    igual que cualquier otra, sin numero de issue.

    Hoy: rojo -- `--work` no existe como flag de `_parse_args`,
    `note.py` revienta con "unrecognized arguments: --work no" (rc != 0,
    pero por argparse, no por un guardado real).
    """

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_work_no_saves_the_note_with_no_issue_number(
        self, tmp_repo, note_type, headline, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before_count = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, "--work", "no"),
            cwd=tmp_repo,
        )

        assert rc == 0, (
            f"tipo {note_type} con --work no tendria que guardarse sin "
            f"rebotar -- stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)
        assert note_id.startswith(f"{note_type}-"), (
            f"el id real {note_id!r} no empieza por el prefijo de su "
            f"propio tipo"
        )

        after_count = _git_commit_count(tmp_repo)
        assert after_count == before_count + 1, (
            f"--work no tiene que guardar en UN solo commit nuevo -- "
            f"antes={before_count} despues={after_count}"
        )

        rc_log, commit_message, err_log = run_git(
            ["log", "-1", "--pretty=%B", "HEAD"], tmp_repo
        )
        assert rc_log == 0, f"git log fallo leyendo el commit real: {err_log}"
        assert "Issue:" not in commit_message, (
            f"--work no no puede dejar un trailer de issue en el commit "
            f"real -- mensaje real:\n{commit_message!r}"
        )

        rc_search, search_out, search_err = run_memory_script(
            "search.py", ["--id", note_id], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py --id {note_id} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert "Issue:" not in search_out, (
            f"{note_id} no puede enseñar un numero de issue que nunca "
            f"se le dio -- salida real:\n{search_out!r}"
        )


@_skip_on_windows
class TestIssueNAlonePassesThroughTheExistingValidator:
    """Punto 4 del encargo: `--issue N` sin `--work` sigue pasando por
    `validate_issue()` (la comprobacion real contra `gh issue view`),
    exactamente igual que hoy.

    Nota de honestidad (test-first, se declara para no fingir un rojo
    que no hay): esto YA es verde hoy -- `vocabulary.TYPES["Q"/"I"]`
    trae `issue` en `allowed_fields` desde D-044/D-045, y ningun gate
    nuevo bloquea esta ruta todavia (no hay comprobacion de "--issue o
    --work" cuando `--issue` SI viene). Se fija aqui como GUARDA de
    no-regresion: la puerta nueva de las clases 1/2 no puede tragarse
    esta ruta cuando `--issue` llega poblado.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_issue_that_exists_saves_and_carries_the_real_trailer(
        self, tmp_repo, tmp_path, note_type, headline, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 4242
        fake_gh_dir = _fake_gh_dir(tmp_path, exists=(issue_number,))
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, "--issue", str(issue_number)),
            cwd=tmp_repo,
            env=env,
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} (issue real, "
            f"segun el gh falso) tendria que guardarse sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_log, commit_message, err_log = run_git(
            ["log", "-1", "--pretty=%B", "HEAD"], tmp_repo
        )
        assert rc_log == 0, f"git log fallo leyendo el commit real: {err_log}"
        assert f"Issue: #{issue_number}" in commit_message, (
            f"el commit real de {note_id} no lleva el trailer "
            f"'Issue: #{issue_number}' -- mensaje real:\n{commit_message!r}"
        )

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_issue_that_does_not_exist_is_still_rejected(
        self, tmp_repo, tmp_path, note_type, headline, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        bogus_issue = 999999999
        fake_gh_dir = _fake_gh_dir(tmp_path, missing=(bogus_issue,))
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, "--issue", str(bogus_issue)),
            cwd=tmp_repo,
            env=env,
        )
        assert rc != 0, (
            f"tipo {note_type} con --issue {bogus_issue} (el gh falso "
            f"confirma que NO existe) tendria que rebotar -- salio rc=0, "
            f"stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err
        assert str(bogus_issue) in out and "no existe" in out, (
            f"el rechazo deberia nombrar la issue y decir que no existe "
            f"-- salida real: {out!r}"
        )


class TestIssueNoneRequiresTheOwnersLiteralQuote:
    """Punto 5 del encargo: `--issue none` es la salida de "el propietario
    dijo que no" (D-066) -- distinta de `--work no` ("no hacia falta
    trabajo"). Exige SIEMPRE la frase literal via `--quote` -- a
    diferencia de `gitmem rule`, aqui NO existe un `--quote none` de
    escape: el no siempre es del propietario y siempre lleva cita
    (D-066, textual: "el no siempre es del dueño y siempre lleva cita").

    Hoy: rojo -- `--issue` es `type=int` en `_parse_args` (ver docstring
    del modulo, hallazgo estructural), asi que `--issue none` revienta
    en argparse antes de llegar a ningun validador. `--quote` tampoco
    existe como flag de `note.py` hoy. Las dos cosas dan `rc != 0` ya
    hoy, pero por una razon distinta a la exigida (ni "cita" aparece en
    ningun sitio de la salida hoy, ni el saludo positivo con --quote
    real puede siquiera intentarse).
    """

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_issue_none_without_quote_is_rejected_asking_for_the_literal_phrase(
        self, tmp_repo, note_type, headline, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before_count = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, "--issue", "none"),
            cwd=tmp_repo,
        )

        assert rc != 0, (
            f"tipo {note_type} con --issue none sin --quote tendria que "
            f"rebotar -- salio rc=0, stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err, (
            f"un rechazo real nunca es una traza de pila -- stdout={out!r} "
            f"stderr={err!r}"
        )
        combined = out + err
        assert "cita" in combined.lower(), (
            f"el rechazo tiene que pedir la frase literal del propietario "
            f"(misma palabra 'cita' que ya usa la mecanica de --quote de "
            f"gitmem rule) -- salida real: {combined!r}"
        )

        after_count = _git_commit_count(tmp_repo)
        assert after_count == before_count, (
            f"un rechazo no puede crear un commit -- antes={before_count} "
            f"despues={after_count}"
        )

    @pytest.mark.parametrize(
        "note_type,headline,description", _QI_CASES, ids=[c[0] for c in _QI_CASES]
    )
    def test_issue_none_with_quote_saves_and_the_quote_survives_the_round_trip(
        self, tmp_repo, note_type, headline, description
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        # Frase distintiva, sin palabras que colisionen con el resto del
        # texto de la nota -- para que el hallazgo del round-trip solo
        # pueda venir de la cita, nunca de una coincidencia con el
        # titular o la descripcion (mismo criterio que
        # test_note_script_promotes.py usa para elegir sus titulares).
        literal_quote = (
            "no hace falta abrir una incidencia para esto, ya lo sabemos "
            "de memoria del trimestre pasado"
        )

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(
                note_type, headline, description,
                "--issue", "none", "--quote", literal_quote,
            ),
            cwd=tmp_repo,
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue none --quote \"{literal_quote}\" "
            f"tendria que guardarse sin rebotar -- stdout={out!r} "
            f"stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_log, commit_message, err_log = run_git(
            ["log", "-1", "--pretty=%B", "HEAD"], tmp_repo
        )
        assert rc_log == 0, f"git log fallo leyendo el commit real: {err_log}"
        assert literal_quote in commit_message, (
            f"la cita real con la que se guardo {note_id} no sobrevivio "
            f"al commit real -- mensaje real:\n{commit_message!r}"
        )

        rc_search, search_out, search_err = run_memory_script(
            "search.py", ["--id", note_id], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py --id {note_id} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert literal_quote in search_out, (
            f"la cita con la que se guardo {note_id} ({literal_quote!r}) "
            f"no sobrevivio la ida y vuelta por 'search.py --id' -- "
            f"salida real:\n{search_out!r}"
        )


class TestOtherFiveTypesDoNotPassThroughThisGate:
    """Punto 6 del encargo: D, M, R, X, B siguen guardandose exactamente
    igual que hoy, sin `--work` ni `--issue` -- la puerta nueva es
    exclusiva de Q/I. CONTROL/regresion: ya verde hoy (nada las toca
    todavia), tiene que seguir verde despues de que Ultron implemente
    la puerta -- si un futuro cambio generalizara el gate por accidente
    a los siete tipos, este test lo cazaria.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags",
        _OTHER_FIVE_TYPES,
        ids=[case[0] for case in _OTHER_FIVE_TYPES],
    )
    def test_type_saves_without_work_or_issue_like_today(
        self, tmp_repo, note_type, headline, description, extra_flags
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(note_type, headline, description, *extra_flags),
            cwd=tmp_repo,
        )

        assert rc == 0, (
            f"tipo {note_type} sin --work ni --issue tendria que "
            f"guardarse igual que hoy -- stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err
        note_id = extract_note_id(out)
        assert note_id.startswith(f"{note_type}-"), (
            f"el id real {note_id!r} no empieza por el prefijo de su "
            f"propio tipo"
        )


class TestWorkFieldIsRejectedOutsideQAndI:
    """Punto 7 del encargo: `--work` en un tipo que no es Q/I rebota como
    campo no aceptado para ese tipo -- misma mecanica que
    `validate_fields()` ya usa hoy para `--awaits` fuera de B
    (`test_note_issue_field.py::
    TestOpeningIssueDidNotLoosenOtherTypeGatedFields::
    test_awaits_is_still_rejected_outside_type_b`).

    Hoy: rojo -- `--work` no existe como flag de `_parse_args` en
    absoluto (ver docstring del modulo), asi que revienta en argparse
    ("unrecognized arguments: --work no", en stderr) antes de llegar a
    `validate_fields()`. `rc != 0` ya sale hoy por esa razon estructural,
    pero el mensaje exigido (la palabra "work" en la salida REAL de la
    validacion de campos, como ya pasa con "awaits") no aparece -- rojo
    por la razon correcta, no por casualidad de un rc que ya no era 0.
    """

    def test_work_no_is_rejected_for_type_d(self, tmp_repo):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        before_count = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            _note_args(
                "D",
                "switch the changelog generator from a script to a github action",
                "The changelog script only runs on one machine; a github "
                "action would make it reproducible for anyone with push access.",
                "--why", "a github action removes the single point of failure "
                         "and runs the same way for everyone",
                "--work", "no",
            ),
            cwd=tmp_repo,
        )

        assert rc != 0, (
            "un D con --work no deberia seguir rebotando -- work solo "
            f"existe para Q/I, esto no cambia con la apertura de la "
            f"aduana de issues. salio rc=0: stdout={out!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err
        assert "work" in out, (
            f"el rechazo deberia nombrar el campo que sobra (work) -- "
            f"salida real: {out!r}"
        )

        after_count = _git_commit_count(tmp_repo)
        assert after_count == before_count, (
            f"un rechazo no puede crear un commit -- antes={before_count} "
            f"despues={after_count}"
        )
