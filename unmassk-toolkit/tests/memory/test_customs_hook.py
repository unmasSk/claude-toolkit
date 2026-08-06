"""Contrato ROJO de `hooks/customs.py` -- la aduana -- PIEZAS.md Sec.11
(las tres primeras filas de "Sus tests", obligatorias) y Sec.6.3/7.4/7.5.

`hooks/customs.py` NO EXISTE TODAVIA. Modo test-first, pase de CONTRATO
(antes de Ultron): estos tests son la ACEPTACION -- lo que define
"hecho" para este hook -- no el barrido exhaustivo de ramas (ese llega
en el pase de endurecimiento, tras la implementacion real).

De donde sale cada cosa que este fichero da por cierta, para que Ultron
no tenga que adivinar:

- PIEZAS.md Sec.11, tabla de "Sus tests" (las tres filas obligatorias
  de este encargo): apagada no bloquea nada; encendida bloquea con el
  texto exacto del rechazo; wip y ⏩ pasan sin ni una pregunta.
- PIEZAS.md Sec.6.3 (`config.py`, ya en produccion): `Config.
  customs_enabled: bool = False` -- la aduana NACE APAGADA. Sin
  `config.json`, `config.load()` devuelve `Config()` con ese default.
- PIEZAS.md Sec.7.4 (`rejection.py`, ya en produccion): `build()`,
  `render_terminal()`, `render_hook_block()` -- "mismo objeto, dos
  renderizados", los dos comparten el mismo cuerpo privado `_render()`.
- PIEZAS.md Sec.7.5 (`validator.py`, ya en produccion): `Context(zones,
  existing_in_zone, known_ids, config)`, `validate_note(note, ctx) ->
  tuple[Rejection, ...]` (vacio = valida), `is_wip(subject) -> bool`
  (arranca por el emoji `🚧`, "opera sobre el titular de un commit que
  nunca llega a ser Note" -- literal de su propio docstring).
- `format.py` (ya en produccion): `parse_message(text) -> Note | None`
  -- devuelve `None` ante cualquier texto que no case, nunca lanza.
  `parse_subject`/`_SUBJECT_RE` exigen que el titular EMPIECE por
  `[ID][zona1][zona2]` -- un titular que empieza por `🚧` (wip) nunca
  puede casar esa forma: los dos formatos (nota vs. wip) son
  estructuralmente excluyentes, verificado leyendo el regex real. Por
  eso ningun test de este fichero intenta construir un commit que sea
  "wip Y ademas nota invalida parseable" -- esa combinacion no existe
  en el vocabulario del sistema, y fabricarla seria probar un caso que
  el propio formato ya hace imposible.
- spec-sistema-memoria-v2.md P5: "el canal de rechazo esta medido como
  fiable (`decision:block` llega al modelo)". `hooks/pre-merge-gate.py`
  (v1, YA EN PRODUCCION, leido antes de escribir este contrato) es la
  UNICA pieza real de este repositorio que implementa ese canal:
  `json.dump({"decision": "block"/"approve", "reason": "..."}, sys.
  stdout)`, proceso que SIEMPRE termina con `returncode == 0` -- la
  decision vive en el JSON, nunca en el codigo de salida.
  `test_pre_merge_gate.py::_run_hook` (v1, YA EN PRODUCCION) es la
  convencion de invocacion ya medida: JSON de `{"tool_name": "Bash",
  "tool_input": {"command": ...}}` por stdin, proceso aparte, `cwd` =
  el repo.

ASUNCIONES DE FIRMA, DISCLOSED (ningun documento fija esto -- se anota
en vez de inventarse en silencio, regla de PIEZAS.md Sec.0.2):

1. **Canal de salida de `customs.py`.** Ningun documento dice si la
   aduana usa el mismo canal `decision`/`reason` que `pre-merge-gate.py`
   o el canal mas viejo de `pre-validate-commit-trailers.py` (codigo de
   salida 2 + texto por stderr). Este contrato asume el primero porque
   es el UNICO que la propia especificacion cita por nombre como
   "medido como fiable" (P5) -- el segundo no tiene esa garantia escrita
   en ningun sitio. Si Ultron implementa el otro canal, estos tests
   fallan de forma clara (JSON invalido / `decision` ausente) y hay que
   volver aqui, no adivinar en el hook.
2. **Como extrae `customs.py` el mensaje del commit.** El payload trae
   `tool_input.command` como una CADENA de shell completa (p.ej. `git
   commit --allow-empty -m '<mensaje>'`), no un mensaje ya separado.
   Este contrato asume que la aduana tokeniza esa cadena con `shlex.
   split()` (la misma tecnica que ya usa `pre-validate-commit-trailers.
   py::_is_direct_git_commit`, YA EN PRODUCCION) y toma el valor que
   sigue a `-m` como el texto completo del mensaje -- por eso cada
   comando de este fichero envuelve el mensaje entre comillas simples,
   la forma mas simple que sobrevive un `shlex.split()` con saltos de
   linea dentro. Ningun test de aqui depende de un mecanismo de
   extraccion MAS complejo (heredoc, `-F fichero`, etc.).
3. **Que pasa con un commit que NO es una nota de memoria en absoluto**
   (p.ej. un commit de codigo normal, `git commit -m "fix: bug"`,
   customs_enabled=True). Ningun documento dice si la aduana lo deja
   pasar (porque `format.parse_message` devuelve `None` y no hay nada
   que validar) o lo rechaza como "no se que tipo es esto" (porque
   TAMPOCO empieza por `🚧`/`⏩` y tampoco tiene forma de nota). **Hueco
   real, NO cerrado por este contrato** -- no hay ningun test para ese
   caso en este fichero. Puede ser deliberado (el arbol de tipos de
   TEXTOS Sec.1.4 esta pensado para *notas*, no para *cualquier*
   commit); se anota aqui para que el propietario lo cierre, no se
   rellena con criterio propio.

Los rechazos ESPERADOS de cada test de bloqueo no se escriben a mano:
se derivan llamando a las piezas reales por separado (`format.
parse_message` sobre el MISMO texto que viaja en el comando,
`validator.validate_note`, `rejection.render_hook_block`) -- nunca una
cadena literal copiada del hook. Es la comparacion productor<->consumidor
que exige unmassk-standards Sec.34: lo que la aduana escupe se compara
contra lo que la MISMA `rejection.py`/`validator.py` produce invocada
por separado, nunca contra si misma.

El hook se prueba EJECUTANDOSE como proceso real contra un repositorio
git temporal (`tmp_repo`) con JSON real por stdin -- nunca importando
sus funciones [encargo explicito, mismo patron que los scripts de
`bin/memory/`].

Con el hook inexistente, TODOS estos tests fallan hoy por la MISMA causa
real: `python3 <ruta inexistente>` devuelve el `returncode` que Python
le da a "no se pudo abrir el fichero" (stderr tipo `can't open file
'...': [Errno 2] No such file or directory`), nunca JSON valido por
stdout -- ni `rc == 0` ni `parsed is not None` pueden pasar por
accidente contra ese fallo.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_memory_script,
    seed_config_json,
    seed_note_via_script,
    seed_zones_json,
)

_TESTS_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_TESTS_MEMORY_DIR))
HOOKS_DIR = os.path.join(_TOOLKIT_ROOT, "hooks")
HOOK_PATH = os.path.join(HOOKS_DIR, "customs.py")


# ── Invocacion del hook -- ver "ASUNCIONES DE FIRMA" punto 1 arriba ────────


def run_customs_hook(cwd, command, *, payload_cwd=None, env=None):
    """Invoca `hooks/customs.py` como proceso aparte con un payload de
    Bash tool_input real por stdin. Misma convencion medida que
    `test_pre_merge_gate.py::_run_hook` (v1, ya en produccion).

    `payload_cwd`, si no es `None`, se anade como `hook_input["cwd"]` en
    el JSON del payload -- DISTINTO del `cwd` real del subproceso
    (parametro `cwd`, que sigue fijando el directorio de trabajo real
    del proceso, igual que antes). Sirve para probar la precedencia
    entre el `cwd` que manda el payload y `os.getcwd()` heredado del
    proceso [contrato del `cd` inicial, 2026-08-06] -- ningun test
    anterior a ese contrato lo usa, asi que no cambia su comportamiento.

    `env`, si no es `None`, se ANADE al entorno heredado del subproceso
    (nunca lo sustituye entero) -- mismo contrato aditivo que
    `run_memory_script`/`run_hook_with_payload` de conftest.py. Sirve
    para el test de expansion de `~` (fuerza un `HOME` de prueba).

    Devuelve `(rc, parsed_json_or_None, stdout, stderr)`.
    """
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if payload_cwd is not None:
        payload["cwd"] = payload_cwd
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        env=full_env,
    )
    rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    try:
        parsed = json.loads(stdout) if stdout.strip() else None
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _commit_command(message):
    """`git commit --allow-empty -m '<message>'` -- ver punto 2 de
    "ASUNCIONES DE FIRMA". Ningun mensaje de este fichero contiene una
    comilla simple, asi que el envoltorio nunca necesita escapado.
    """
    assert "'" not in message, "el mensaje de prueba no puede llevar comilla simple (ver helper)"
    return f"git commit --allow-empty -m '{message}'"


# ── Piezas reales de produccion, cargadas una vez por modulo de test ───────


@pytest.fixture
def format_mod():
    return import_lib_memory_module("format")


@pytest.fixture
def validator_mod():
    return import_lib_memory_module("validator")


@pytest.fixture
def rejection_mod():
    return import_lib_memory_module("rejection")


@pytest.fixture
def zones_mod():
    return import_lib_memory_module("zones")


@pytest.fixture
def config_mod():
    return import_lib_memory_module("config")


def _expected_block_text(format_mod, validator_mod, rejection_mod, zones_mod, config_mod, repo, message):
    """Deriva el texto de bloqueo ESPERADO llamando a las piezas reales
    por separado, sobre el MISMO texto que viaja en el comando de
    prueba -- nunca una cadena escrita a mano. Ver docstring del modulo,
    parrafo sobre unmassk-standards Sec.34.

    Falla el propio test (con un mensaje claro) si el mensaje de prueba
    no produce EXACTAMENTE un rechazo -- un fixture con mas o menos de
    un rechazo no es un caso de prueba util para "el texto exacto".
    """
    note = format_mod.parse_message(message)
    assert note is not None, (
        f"fixture de prueba invalido: format.parse_message() no reconocio "
        f"el mensaje construido para este test: {message!r}"
    )
    pm = pm_path(repo)
    zones = zones_mod.load(pm / "zones.json")
    config = config_mod.load(pm / "config.json")
    ctx = validator_mod.Context(
        zones=zones,
        existing_in_zone=(),
        known_ids=frozenset(),
        config=config,
    )
    rejections = validator_mod.validate_note(note, ctx)
    assert len(rejections) == 1, (
        f"fixture de prueba invalido: se esperaba exactamente 1 rechazo y "
        f"llegaron {len(rejections)}: {rejections!r} -- ajusta el mensaje "
        f"de prueba para que dispare una sola regla"
    )
    return rejection_mod.render_hook_block(rejections[0])


# ═══════════════════════════════════════════════════════════════════════
# Fila 1 de PIEZAS.md Sec.11 -- apagada, la aduana no bloquea nada
# ═══════════════════════════════════════════════════════════════════════


class TestCustomsDisabledNeverBlocks:
    """Fallo real que previene: que el primer dia de instalacion (sin
    `config.json` todavia, o con `customs_enabled` explicito a `false`)
    el sistema viejo (v1) que sigue en uso quede bloqueado por una
    aduana que nace hablando de un formato que el v1 nunca escribio."""

    def test_no_config_file_day_one_install_never_blocks(self, tmp_repo):
        """Sin `config.json` -- el estado real de un proyecto recien
        instalado -- `config.load()` cae al default fail-closed
        (`customs_enabled=False`, PIEZAS.md Sec.6.3). El comando de
        prueba es deliberadamente una nota-de-memoria RECONOCIBLE pero
        invalida por partida doble (tipo inexistente + zona inexistente)
        para probar que la aduana apagada de verdad NO evalua nada, no
        que "por casualidad" no reconocio el commit.
        """
        command = _commit_command(
            "[ZZZ-1][ninguna-zona-existe][tampoco-esta] "
            "▲ deliberately invalid note while customs is off\n"
            "\n"
            "Description: contenido de prueba, no deberia importar."
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"con la aduana apagada (sin config.json) un commit invalido "
            f"tiene que pasar sin evaluarse; llego {parsed!r}"
        )

    def test_explicit_customs_disabled_never_blocks(self, tmp_repo):
        """`config.json` PRESENTE pero con `customs_enabled: false`
        explicito -- distingue "el fichero existe" de "la aduana esta
        encendida": un hook que solo comprueba la EXISTENCIA del
        fichero (en vez de leer el valor real de la bandera) bloquearia
        aqui por error."""
        seed_config_json(tmp_repo, customs_enabled=False)
        command = _commit_command(
            "[ZZZ-1][ninguna-zona-existe][tampoco-esta] "
            "▲ deliberately invalid note while customs is off\n"
            "\n"
            "Description: contenido de prueba, no deberia importar."
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"con customs_enabled=false explicito, un commit invalido "
            f"tiene que pasar sin evaluarse; llego {parsed!r}"
        )

    def test_non_commit_command_never_blocks_even_when_enabled(self, tmp_repo):
        """Un comando de Bash que no es un `git commit` en absoluto (aqui,
        `ls -la`) tiene que pasar siempre, incluso con la aduana
        encendida -- previene un hook que intenta tokenizar/validar
        cualquier cosa que le llegue por `tool_input.command` y revienta
        o bloquea por error de reconocimiento."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "ls -la")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"un comando que no es git commit no puede bloquearse jamas; "
            f"llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Fila 2 de PIEZAS.md Sec.11 -- encendida, bloquea con el texto EXACTO
# ═══════════════════════════════════════════════════════════════════════


class TestCustomsEnabledBlocksWithExactRejectionText:
    """Fallo real que previene: un bloqueo que no dice que hacer (o que
    dice algo distinto de lo que `rejection.py`/`validator.py` ya
    redactan) obliga a adivinar y se acaba esquivando -- PIEZAS.md
    Sec.11, fila 2; Sec.7.4, "que la aduana diga una cosa y el generador
    otra"."""

    def test_unrecognized_type_blocks_with_validator_text(
        self, tmp_repo, format_mod, validator_mod, rejection_mod, zones_mod, config_mod,
    ):
        """Tipo `Z` no existe en el vocabulario cerrado -- dispara
        SOLO `validate_type` (zonas validas, sin punteros, sin notas
        parecidas de por medio) -- TEXTOS.md Sec.1.4."""
        seed_config_json(tmp_repo, customs_enabled=True)
        seed_zones_json(tmp_repo, ["product", "testarea"])
        message = (
            "[Z-1][product][testarea] ▲ some clearly unrecognized note type\n"
            "\n"
            "Description: contenido de prueba para el tipo desconocido."
        )
        expected_text = _expected_block_text(
            format_mod, validator_mod, rejection_mod, zones_mod, config_mod, tmp_repo, message,
        )

        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un tipo de nota desconocido tiene que bloquear; llego {parsed!r}"
        )
        assert parsed.get("reason") == expected_text, (
            "el texto de bloqueo de la aduana no coincide con el que "
            "produce rejection.render_hook_block() sobre el MISMO rechazo "
            f"de validator.validate_type():\n--- aduana ---\n"
            f"{parsed.get('reason')!r}\n--- esperado ---\n{expected_text!r}"
        )

    def test_zone_not_found_blocks_with_validator_text(
        self, tmp_repo, format_mod, validator_mod, rejection_mod, zones_mod, config_mod,
    ):
        """Zona `ghostzone` no esta en `zones.json` -- dispara SOLO
        `validate_zones` (tipo M valido, zona2 valida, sin candidatas
        parecidas) -- TEXTOS.md Sec.1.1. Un rechazo DISTINTO al de
        arriba, para probar que la aduana despacha por el validador real
        y no copia a mano un unico caso."""
        seed_config_json(tmp_repo, customs_enabled=True)
        seed_zones_json(tmp_repo, ["product", "testarea"])
        message = (
            "[M-001][ghostzone][testarea] 📌 a memo in a zone that does not exist\n"
            "\n"
            "Description: contenido de prueba para la zona inexistente."
        )
        expected_text = _expected_block_text(
            format_mod, validator_mod, rejection_mod, zones_mod, config_mod, tmp_repo, message,
        )

        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"una zona inexistente tiene que bloquear; llego {parsed!r}"
        )
        assert parsed.get("reason") == expected_text, (
            "el texto de bloqueo de la aduana no coincide con el que "
            "produce rejection.render_hook_block() sobre el MISMO rechazo "
            f"de validator.validate_zones():\n--- aduana ---\n"
            f"{parsed.get('reason')!r}\n--- esperado ---\n{expected_text!r}"
        )

    def test_enabled_valid_note_never_blocks(self, tmp_repo):
        """Encendida, pero la nota es VALIDA (tipo, zonas y campos
        correctos, sin punteros ni parecidas) -- tiene que aprobar.
        Previene el fallo contrario al de esta clase: una aduana
        encendida que bloquea TODO, no solo lo invalido -- rompe la
        garantia de `validator.py` ("como el generador valida en
        proceso con esta misma pieza, la aduana casi nunca dispara")."""
        seed_config_json(tmp_repo, customs_enabled=True)
        seed_zones_json(tmp_repo, ["product", "testarea"])
        message = (
            "[M-001][product][testarea] 📌 stripe webhooks are idempotent by event id\n"
            "\n"
            "Description: nota valida de prueba, no deberia bloquearse jamas."
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"una nota valida con la aduana encendida no puede bloquearse; "
            f"llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Fila 3 de PIEZAS.md Sec.11 -- wip y ⏩ pasan sin ni una pregunta
# ═══════════════════════════════════════════════════════════════════════


class TestWipAndNextBypassEveryQuestion:
    """Fallo real que previene: friccion en el checkpoint (wip) y en el
    cierre de sesion (⏩) -- "los dos peores momentos para preguntar"
    (PIEZAS.md Sec.11, fila 3). Encendida a proposito en los dos tests:
    si pasan con la aduana APAGADA no prueban nada (pasarian de todas
    formas); tienen que pasar CON la aduana encendida y con contenido
    que, si se forzara por el validador, no tendria forma reconocible de
    nota valida."""

    def test_wip_commit_bypasses_validation_entirely(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        # Sin zones.json en absoluto -- si la aduana intentara validar
        # esto como nota, ni siquiera podria resolver zonas.
        command = _commit_command(
            "🚧 wip: mid-refactor snapshot, zones and types not finalized yet"
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"un commit wip (🚧) tiene que pasar sin ninguna pregunta, "
            f"incluso con la aduana encendida; llego {parsed!r}"
        )

    def test_next_context_commit_bypasses_validation_entirely(self, tmp_repo, format_mod):
        """El texto real se construye con `format.build_context_message`
        (produccion), nunca a mano -- unmassk-standards Sec.34, "round
        trip real, sin fabricar el texto esperado". Escribirlo a mano
        aqui ya quedo obsoleto una vez [formato `[NEXT] <emoji> ...` +
        `Context:` en prosa, decision del propietario 2026-08-03,
        COLA.md Sec.5] -- construirlo con la pieza real evita que este
        test vuelva a desincronizarse del formato que produce.
        """
        seed_config_json(tmp_repo, customs_enabled=True)
        model_mod = import_lib_memory_module("model")
        from datetime import datetime, timezone

        note = model_mod.ContextNote(
            headline="implement discussed changes to close-session skill",
            context="some point about what was decided",
            keys=("close-session", "checkpoint"),
            timestamp=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
        )
        command = _commit_command(format_mod.build_context_message(note))
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"el commit de contexto de cierre ([NEXT]) tiene que pasar sin "
            f"ninguna pregunta, incluso con la aduana encendida; llego "
            f"{parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Pase de endurecimiento -- DEUDA.md B19 punto 2 [decision del propietario,
# 2026-08-03]: la aduana se enciende sola en cuanto el proyecto tiene su
# primera nota, sin boton. `_project_has_notes`/`_customs_active`
# (hooks/customs.py) ya estan en produccion sin ni un test -- este bloque
# los cubre, siempre a traves del proceso real (nunca importando esas dos
# funciones), sembrando notas REALES con `note.py`/`remove.py` -- los
# mismos escritores que usaria una persona -- nunca fabricando un indice
# a mano.
# ═══════════════════════════════════════════════════════════════════════


def _invalid_note_command(zone1, zone2):
    """Un commit con forma de nota reconocible pero de un tipo que no
    existe en el vocabulario cerrado -- dispara SIEMPRE un rechazo si la
    aduana esta encendida y evalua de verdad, y aprueba SIEMPRE si la
    aduana esta apagada o no evalua nada. Sirve como sonda binaria para
    todos los tests de este bloque: no importa el texto exacto del
    rechazo, solo si la aduana decidio evaluar o no.
    """
    return _commit_command(
        f"[ZZZ-1][{zone1}][{zone2}] ▲ deliberately invalid note type\n"
        "\n"
        "Description: contenido de prueba, no deberia importar."
    )


class TestCustomsAutoEnablesOnFirstNote:
    """Fallo real que previene: antes de esta decision, un proyecto tenia
    que acordarse de poner `customs_enabled: true` a mano para que la
    aduana empezara a vigilar -- "un interruptor que hay que acordarse de
    pulsar es un vigilante apagado" [DEUDA.md B19 punto 2]. Estos tests
    fijan las cuatro fases del ciclo: sin memoria propia (apagada), con
    la primera nota (encendida sola), con esa nota ya archivada (sigue
    contando), y con la bandera explicita (manda siempre, en los dos
    sentidos)."""

    def test_project_memory_dir_exists_but_no_note_ever_written_stays_off(
        self, tmp_repo,
    ):
        """`.claude/project-memory/` existe (trae `zones.json`, sembrado
        por `seed_zones_json`) pero ningun indice se sembro todavia
        (`indexes.seed()` no corrio -- eso solo pasa dentro de
        `notes.write()`, en el primer alta real). Caso DISTINTO del "sin
        directorio en absoluto" de `TestCustomsDisabledNeverBlocks`:
        aqui prueba que `_project_has_notes` no confunde "el directorio
        existe" con "hay notas" -- las ocho lecturas de indice tienen que
        fallar con `FileNotFoundError` (capturado) y devolver `False`,
        igual que sin directorio.
        """
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        command = _invalid_note_command("infra", "deploy")

        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"sin ninguna nota escrita todavia (aunque el directorio de "
            f"memoria ya exista), la aduana tiene que quedar apagada; "
            f"llego {parsed!r}"
        )

    def test_first_real_note_turns_customs_on_without_touching_config(
        self, tmp_repo,
    ):
        """El corazon de la decision: SIN `config.json` en absoluto, en
        cuanto `note.py` escribe la primera nota de verdad, la aduana
        empieza a bloquear -- nadie toco ningun ajuste."""
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "infra", "deploy", "first real note in the project",
            why="a real reason", description="a real description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        command = _invalid_note_command("infra", "deploy")
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"tras la primera nota real, sin config.json, la aduana tiene "
            f"que estar encendida y bloquear una nota invalida; llego "
            f"{parsed!r}"
        )

    def test_first_real_note_turns_customs_on_but_a_valid_note_still_passes(
        self, tmp_repo,
    ):
        """Misma siembra que el test anterior, pero prueba el sentido
        contrario -- que encenderse sola no es "bloquear todo": una nota
        VALIDA, con la aduana recien auto-encendida, tiene que aprobar.
        Sin este test, un `_customs_active` que devolviera `True` sin
        condicion alguna (en vez de delegar en `validator.validate_note`)
        pasaria igual los tests de bloqueo de arriba."""
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "infra", "deploy", "first real note in the project",
            why="a real reason", description="a real description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        message = (
            "[M-001][infra][deploy] 📌 a second, distinct and valid memo\n"
            "\n"
            "Description: nota valida de prueba, distinta de la sembrada."
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"con la aduana auto-encendida, una nota VALIDA tiene que "
            f"seguir aprobando; llego {parsed!r}"
        )

    def test_closed_note_still_counts_customs_stays_on(self, tmp_repo):
        """La nota sembrada se cierra (`remove.py --restriction no`, la
        misma retirada real que usaria una persona) -- ya no vive en
        ningun indice VIGENTE, solo en `ARCHIVED.md`. Fallo real que
        previene: un proyecto que cerro todas sus notas ("no le queda
        nada pendiente") perderia su memoria si `_project_has_notes` solo
        mirara los indices vigentes -- la propia decision dice
        explicitamente que el archivo tambien cuenta.
        """
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "infra", "deploy", "note that will be closed",
            why="a real reason", description="a real description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc_close, out_close, err_close = run_memory_script(
            "remove.py", [note_id, "closed for test purposes", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, (
            f"cierre de siembra fallo: stdout={out_close!r} stderr={err_close!r}"
        )

        command = _invalid_note_command("infra", "deploy")
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"una nota archivada (cerrada) sigue contando como memoria del "
            f"proyecto -- la aduana tiene que seguir encendida; llego "
            f"{parsed!r}"
        )

    def test_explicit_customs_enabled_false_wins_even_with_notes_present(
        self, tmp_repo,
    ):
        """`config.json` dice `customs_enabled: false` EXPLICITO, pese a
        que el proyecto ya tiene una nota real escrita -- la bandera
        manda siempre sobre la deteccion automatica [DEUDA.md B19 punto
        2: "se conserva solo para APAGARLA a mano"]. Sin este test, un
        `_customs_active` que ignorara la bandera explicita en favor de
        `_project_has_notes` bloquearia aqui por error."""
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        seed_config_json(tmp_repo, customs_enabled=False)
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "D", "infra", "deploy", "first real note in the project",
            why="a real reason", description="a real description",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        command = _invalid_note_command("infra", "deploy")
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"customs_enabled=false explicito tiene que ganar aunque haya "
            f"notas reales escritas; llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Pase de endurecimiento -- DEUDA.md B19 punto 3 [decision del propietario,
# 2026-08-03, que revoca la lectura anterior tomada por un agente sin
# revision]: solo se rechaza el `git rebase` que EMPIEZA uno.
# `--continue`/`--skip`/`--abort` pasan los tres -- bloquear a mitad de un
# rebase ya en marcha deja el repositorio a medias, que es peor que el
# dano que se queria evitar. Ninguno de los cuatro caminos tenia test
# todavia -- de hecho, ningun camino de `merge`/`rebase`/`cherry-pick`/
# `--amend` los tenia; este bloque cubre unicamente los cuatro que este
# encargo pide.
# ═══════════════════════════════════════════════════════════════════════


class TestRebasePassthroughOnlyForInFlightOperations:
    """Los cuatro caminos, con la aduana encendida a proposito en los
    cuatro: si alguno pasara solo porque la aduana estuviera apagada, no
    probaria la excepcion real -- probaria que apagada todo pasa, que ya
    cubre `TestCustomsDisabledNeverBlocks`."""

    def test_git_rebase_starting_one_blocks(self, tmp_repo):
        """`git rebase main` -- el que EMPIEZA un rebase -- tiene que
        bloquear: reescribe historia en lote, viola P1."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "git rebase main")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un `git rebase main` que EMPIEZA un rebase tiene que "
            f"bloquear; llego {parsed!r}"
        )

    def test_git_rebase_continue_passes(self, tmp_repo):
        """`git rebase --continue` -- ya se esta DENTRO de un rebase
        (empezado en la terminal, o tras resolver un conflicto) --
        bloquearlo dejaria al usuario atascado sin salida hacia
        delante."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "git rebase --continue")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git rebase --continue` tiene que pasar siempre, incluso "
            f"con la aduana encendida; llego {parsed!r}"
        )

    def test_git_rebase_skip_passes(self, tmp_repo):
        """`git rebase --skip` -- mismo motivo que `--continue`: saltar
        un commit conflictivo de un rebase ya en marcha, no empezar uno
        nuevo."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "git rebase --skip")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git rebase --skip` tiene que pasar siempre, incluso con la "
            f"aduana encendida; llego {parsed!r}"
        )

    def test_git_rebase_abort_passes(self, tmp_repo):
        """`git rebase --abort` -- ya pasaba antes de esta decision;
        sigue pasando ahora, sin cambio de comportamiento, solo cubierto
        por primera vez."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "git rebase --abort")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git rebase --abort` tiene que pasar siempre, incluso con la "
            f"aduana encendida; llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Reapuntado (memoria v2, 2026-08-05) -- esta cobertura vivia en
# tests/test_pre_validate_commit_trailers_git_log.py::TestGitLogRegexHasNoFalsePositives,
# contra el hook v1 `pre-validate-commit-trailers.py` (borrado junto con
# el resto del sistema de memoria v1). El BUG C que protegia (un regex
# `\bgit\b.*\blog\b` que bloqueaba CUALQUIER comando que mencionara "git"
# y "log" como palabras sueltas en cualquier parte -- `cat git.log`,
# `echo 'git log info'`, `git log-remote origin`) ya se pago cuatro veces
# en una manana de esta obra -- la regla que sobrevive no es "sobre
# git log" en concreto, es "la deteccion de que un comando crea un commit
# tiene que mirar la POSICION del token, nunca el texto suelto". El
# sustituto real es `hooks/customs.py::_find_commit_creating_statement()`
# -- tokeniza con `shlex.split()`, localiza el token "git" real (regex
# anclado `(?:^|/)git(?:\.exe)?$`, nunca una subcadena) y solo mira el
# token INMEDIATO siguiente (tras saltar flags) contra el vocabulario
# cerrado `{"commit","merge","rebase","cherry-pick"}` -- estructuralmente
# distinto del regex suelto que causaba BUG C, pero la garantia que un
# usuario necesita ("un comando que solo MENCIONA una palabra no se
# bloquea") es la misma, así que el equivalente de cada caso del bug
# original se fija aqui, contra la pieza real que reemplaza esa
# deteccion.
# ═══════════════════════════════════════════════════════════════════════


class TestCommitDetectionHasNoFalsePositivesOnMereMentions:
    """Comandos que mencionan "git" y una subpalabra del vocabulario
    cerrado (commit/merge/rebase/cherry-pick) sin ser realmente esa
    invocacion -- ninguno puede bloquear, con la aduana encendida a
    proposito en todos (si pasaran con la aduana apagada no probarian
    nada -- eso ya lo cubre TestCustomsDisabledNeverBlocks)."""

    def test_cat_git_commit_log_filename_not_blocked(self, tmp_repo):
        """`cat git-commit.log`: "git" y "commit" aparecen dentro de un
        NOMBRE DE FICHERO, nunca como el programa real seguido de su
        subcomando -- equivalente directo del `cat git.log` del bug
        original."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "cat git-commit.log")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"'cat git-commit.log' no invoca git en absoluto -- no puede "
            f"bloquear; llego {parsed!r}"
        )

    def test_echo_git_commit_message_not_blocked(self, tmp_repo):
        """`echo 'git commit -m test'`: imprime texto, no ejecuta git --
        equivalente directo del `echo 'git log info'` del bug original.
        El texto citado llega como UN solo token de shlex (no se separa
        en "git"/"commit"/...), asi que ademas confirma que el regex
        anclado no casa dentro de un token compuesto."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(
            tmp_repo, "echo 'git commit -m test'")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"'echo git commit -m test' no invoca git -- no puede "
            f"bloquear; llego {parsed!r}"
        )

    def test_git_log_with_commit_as_grep_value_not_blocked(self, tmp_repo):
        """`git log --grep=commit`: "commit" aparece como VALOR de un
        flag de `git log`, un subcomando fuera del vocabulario cerrado --
        nunca como el subcomando real que sigue a "git"."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(
            tmp_repo, "git log --grep=commit")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"'git log --grep=commit' no crea ningun commit -- 'log' no "
            f"esta en el vocabulario cerrado; llego {parsed!r}"
        )

    def test_git_remote_subcommand_not_blocked(self, tmp_repo):
        """`git remote show origin`: subcomando real de git, pero fuera
        del vocabulario cerrado -- equivalente directo del
        `git log-remote origin` del bug original."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(
            tmp_repo, "git remote show origin")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"'git remote show origin' no crea ningun commit -- 'remote' "
            f"no esta en el vocabulario cerrado; llego {parsed!r}"
        )

    def test_anti_vacuity_real_commit_still_evaluated_in_same_conditions(
        self, tmp_repo,
    ):
        """Control anti-vacuidad de toda esta clase: en el MISMO estado
        (aduana encendida, sin notas sembradas), un `git commit` real con
        mensaje no reconocible SI tiene que bloquear -- si esto tambien
        aprobara, los cuatro "approve" de arriba no probarian que la
        deteccion distingue el token real, probarian que nada bloquea
        nunca en este fixture."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(
            tmp_repo, 'git commit -m "not a recognizable note"')

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un 'git commit' real con mensaje no reconocible SI tiene que "
            f"bloquear en el mismo fixture que los casos de arriba -- si "
            f"esto tambien aprobara, ninguno de ellos probaria nada; "
            f"llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Contrato nuevo (2026-08-06, hallazgo reportado -- Bilbo confirmo que
# `config.json`/`zones.json` corrupto dispara el mismo bloqueo generico):
# con `.claude/project-memory/config.json` o `zones.json` ilegible (p.ej.
# marcadores de conflicto de merge sin resolver, ya no es JSON valido),
# `config.load()`/`zones.load()` lanza y el `except Exception` de
# `main()` (hooks/customs.py) bloquea "por seguridad" -- ANTES de llegar
# a la logica de paso libre que ya existe para `git merge --abort` /
# `git rebase --abort`/`--continue`. Consecuencia real medida: un merge
# en conflicto deja al usuario atascado, porque el comando natural para
# salir (`git merge --abort`) tambien matchea el vocabulario cerrado que
# dispara la evaluacion y cae en el mismo bloqueo ciego.
#
# Decision del propietario ("bloquear con salida clara"): un commit
# normal SIGUE bloqueado (no hay bandera fiable que leer de un fichero
# roto) pero el `reason` tiene que decir COMO reparar el fichero, no
# solo nombrarlo; los cuatro comandos de RESCATE
# (`git merge --abort`/`--continue`, `git rebase --abort`/`--continue`)
# tienen que APROBAR siempre, corrupcion o no.
# ═══════════════════════════════════════════════════════════════════════


_RESCUE_COMMANDS = (
    "git merge --abort",
    "git merge --continue",
    "git rebase --abort",
    "git rebase --continue",
)

_GENERIC_NO_ESCAPE_PREFIX = "customs.py: fallo inesperado, bloqueando por seguridad: "

# Vocabulario razonable de verbos de reparacion -- ver ASUNCIONES DE
# FIRMA punto 1 de la clase de abajo: este contrato no fija la redaccion
# final (Ultron no la ha escrito todavia), solo que deje de ser un
# volcado de excepcion y de que, ademas de nombrar el fichero, de una
# instruccion accionable.
_REPAIR_VERB_HINTS = (
    "repara", "arregla", "corrige", "edita", "resuelve", "valida", "revisa",
)


def _write_corrupt_json(repo, filename):
    """Escribe `filename` (`config.json`/`zones.json`) dentro de
    `.claude/project-memory/` con marcadores de conflicto de merge sin
    resolver -- exactamente la forma de corrupcion que motiva este
    contrato: un merge que se dejo a medias deja el fichero con
    `<<<<<<<`/`=======`/`>>>>>>>` dentro, invalido para `json.loads`
    ("Expecting value: line 1 column 1"). No usa `seed_config_json`/
    `seed_zones_json` (esos escriben JSON valido por diseno) -- este
    helper escribe el contenido roto tal cual.
    """
    pm = pm_path(repo)
    pm.mkdir(parents=True, exist_ok=True)
    content = (
        "<<<<<<< HEAD\n"
        '{"left": "value"}\n'
        "=======\n"
        '{"right": "value"}\n'
        ">>>>>>> feature-branch\n"
    )
    (pm / filename).write_text(content, encoding="utf-8")


def _reason_has_escape_hatch(reason, filename):
    """Las dos propiedades minimas que el encargo exige del `reason` de
    un fichero de memoria corrupto (ver ASUNCIONES DE FIRMA punto 1 de
    `TestCorruptMemoryFileBlocksWithEscapeHatch`): (a) ya NO es el
    prefijo generico actual seguido tal cual del texto crudo de la
    excepcion de Python, y (b) nombra el fichero corrupto ADEMAS de
    traer una instruccion accionable -- nombrar el fichero solo no
    basta, el encargo lo dice explicitamente.
    """
    if reason is None:
        return False
    if reason.startswith(_GENERIC_NO_ESCAPE_PREFIX):
        return False
    if filename not in reason:
        return False
    lowered = reason.lower()
    return any(hint in lowered for hint in _REPAIR_VERB_HINTS)


class TestCorruptMemoryFileBlocksWithEscapeHatch:
    """Fallo real que este contrato cierra: con `config.json` o
    `zones.json` corrupto, el `except Exception` generico de `main()`
    bloquea CUALQUIER sentencia detectada como creadora de commit --
    incluidos los cuatro comandos de RESCATE que son la salida natural de
    un merge/rebase en conflicto, y el commit normal que si sigue
    bloqueado no dice como reparar el fichero.

    ASUNCIONES DE FIRMA, DISCLOSED (PIEZAS.md Sec.0.2 -- ningun documento
    fija esto todavia, se anota en vez de inventarse en silencio):

    1. **Que cuenta como "menciona la via de salida".** El encargo dice
       literalmente "el reason... debe MENCIONAR la via de salida (como
       reparar el fichero), no solo nombrar el fichero corrupto". Este
       contrato no fija la redaccion final (Ultron no la ha escrito
       todavia, es el arreglo de este mismo encargo) -- fija DOS
       propiedades minimas verificables sin adivinar la prosa
       (`_reason_has_escape_hatch` arriba): deja de ser el volcado crudo
       de excepcion con el prefijo generico actual, Y nombra el fichero
       corrupto mas una instruccion accionable. Una redaccion que solo
       nombra el fichero sin ninguna instruccion es rechazada a
       proposito por este contrato -- es exactamente el caso que el
       encargo dice que NO basta.
    2. **`git merge --continue` no es sintaxis real de git** (`merge` no
       tiene esa bandera -- existe para `rebase`/`cherry-pick`). Se
       incluye tal cual porque el encargo lo pide explicitamente Y
       porque `_decide_commit_creating` (hooks/customs.py) ya trata
       `merge` como aprobacion incondicional sin mirar sus banderas
       ["ASUNCIONES DE FIRMA" punto 2 del docstring del modulo] -- la
       forma del comando basta para ejercitar el mismo despacho que un
       `git merge --abort` real.
    3. **Solo `config.json` corrupto rompe HOY los cuatro comandos de
       rescate** -- confirmado ejecutando el hook real (proceso aparte,
       mismo mecanismo que `run_customs_hook`) antes de escribir este
       contrato: `config.load()` se llama SIEMPRE, para cualquier
       subcomando, antes de despachar a `_decide_commit_creating`, asi
       que su excepcion se dispara sin condicion. `zones.json` en
       cambio solo se lee dentro de `_decide_note()`, alcanzable
       UNICAMENTE cuando el subcomando es `commit` (nunca
       `merge`/`rebase`) Y el mensaje parsea como nota reconocible --
       los cuatro tests de rescate con `zones.json` corrupto de esta
       clase YA APRUEBAN hoy (no son rojo). Se incluyen de todas formas
       porque el encargo pide cubrir "los dos ficheros" en los "dos
       puntos" y porque fijan el comportamiento correcto como red de
       seguridad si algun dia cambia el orden de lectura de `_decide()`.
       Los cinco tests que SI son rojo hoy: los cuatro de rescate con
       `config.json` corrupto, mas el commit normal con `config.json`
       corrupto. El commit-con-forma-de-nota con `zones.json` corrupto
       tambien es rojo (el `reason` de hoy ni siquiera nombra
       `zones.json` -- ver salida real pegada en el informe).
    """

    def test_normal_commit_blocks_with_escape_hatch_when_config_json_corrupt(
        self, tmp_repo,
    ):
        """Con `config.json` corrupto, cualquier `git commit` normal
        (sin nota reconocible siquiera -- no importa, `config.load()`
        revienta antes de mirar el mensaje) sigue bloqueado, pero el
        `reason` tiene que decir como reparar `config.json`, no solo
        volcar la excepcion cruda de `json`."""
        _write_corrupt_json(tmp_repo, "config.json")
        command = _commit_command("fix: a normal code commit, not a memory note")
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con config.json corrupto, un commit normal tiene que "
            f"seguir bloqueado (no hay bandera fiable que leer del "
            f"fichero roto); llego {parsed!r}"
        )
        reason = parsed.get("reason")
        assert _reason_has_escape_hatch(reason, "config.json"), (
            "el reason del bloqueo con config.json corrupto tiene que "
            "mencionar como repararlo, no solo nombrar el fichero ni "
            f"volcar la excepcion cruda sin mas contexto; llego: {reason!r}"
        )

    def test_normal_commit_blocks_with_escape_hatch_when_zones_json_corrupt(
        self, tmp_repo,
    ):
        """Con `zones.json` corrupto (y `config.json` valido y
        encendido), un commit CON FORMA DE NOTA reconocible -- la unica
        forma de que `_decide_note()` llegue a leer `zones.json` -- sigue
        bloqueado, y el `reason` tiene que decir como reparar
        `zones.json`, no solo volcar la excepcion cruda de `json`."""
        seed_config_json(tmp_repo, customs_enabled=True)
        _write_corrupt_json(tmp_repo, "zones.json")
        message = (
            "[M-001][product][testarea] 📌 a note-shaped message so zones.json gets read\n"
            "\n"
            "Description: contenido de prueba, no deberia importar."
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, _commit_command(message))

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con zones.json corrupto, un commit con forma de nota "
            f"tiene que seguir bloqueado; llego {parsed!r}"
        )
        reason = parsed.get("reason")
        assert _reason_has_escape_hatch(reason, "zones.json"), (
            "el reason del bloqueo con zones.json corrupto tiene que "
            "mencionar como repararlo, no solo nombrar el fichero ni "
            f"volcar la excepcion cruda sin mas contexto; llego: {reason!r}"
        )

    @pytest.mark.parametrize("rescue_command", _RESCUE_COMMANDS)
    def test_rescue_command_passes_when_config_json_corrupt(
        self, tmp_repo, rescue_command,
    ):
        """Los cuatro comandos de rescate tienen que aprobar SIEMPRE,
        incluso con config.json corrupto -- son la unica salida real de
        un merge/rebase en conflicto; bloquearlos deja al usuario
        atascado con el repositorio a medias."""
        _write_corrupt_json(tmp_repo, "config.json")
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, rescue_command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"{rescue_command!r} tiene que aprobar SIEMPRE, incluso con "
            f"config.json corrupto -- es la unica salida real de un "
            f"merge/rebase en conflicto; llego {parsed!r}"
        )

    @pytest.mark.parametrize("rescue_command", _RESCUE_COMMANDS)
    def test_rescue_command_passes_when_zones_json_corrupt(
        self, tmp_repo, rescue_command,
    ):
        """Mismo contrato que el test anterior, con `zones.json`
        corrupto en vez de `config.json` -- ver ASUNCIONES DE FIRMA
        punto 3 de la clase: `zones.json` no se lee en el camino de
        `merge`/`rebase`, asi que estos cuatro YA aprueban hoy; se fijan
        aqui como red de seguridad, no como brecha nueva."""
        seed_config_json(tmp_repo, customs_enabled=True)
        _write_corrupt_json(tmp_repo, "zones.json")
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, rescue_command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"{rescue_command!r} tiene que aprobar SIEMPRE, incluso con "
            f"zones.json corrupto; llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Contrato nuevo (2026-08-06, hallazgo de Moriarty via PoC en vivo): con
# `shlex.split()` fallando (comilla simple sin escapar en una sentencia
# ANTERIOR de la misma cadena bash), `_find_commit_creating_statement()`
# (hooks/customs.py:212-218) cae en su rama `except ValueError` y
# devuelve `(sub, [])` -- SIN los tokens que siguen al subcomando. Con
# `rest_tokens` vacio, `_decide_rescue_passthrough()` nunca puede ver
# `--abort`/`--continue`/`--skip`, asi que el rebase de rescate (la unica
# salida real de un rebase en conflicto) queda bloqueado por el mismo
# motivo que un `git rebase` que EMPIEZA uno -- dejando al usuario
# atascado con el repositorio a medias.
#
# Disparador ordinario, no un ataque: un apostrofo sin escapar dentro del
# MENSAJE de un commit anterior en la misma linea de bash (p.ej.
# `git commit -m 'WIP: don't lose this...' && git rebase --abort`) rompe
# `shlex.split()` para la CADENA ENTERA -- shlex no sabe donde termina la
# comilla abierta, asi que ni siquiera llega a intentar tokenizar la
# segunda sentencia.
#
# Nota de determinismo, verificada en vivo antes de escribir este
# contrato (ejecutando el fallback real cinco veces, procesos distintos):
# `_COMMIT_CREATING_SUBCOMMANDS` es un `set` de cadenas -- con
# `PYTHONHASHSEED` sin fijar (el default de este repo), el ORDEN en que
# el bucle `for sub in _COMMIT_CREATING_SUBCOMMANDS` prueba cada
# subcomando varia entre procesos. Para los tres casos de `rebase`
# (--abort/--continue/--skip) esto NO importa: tanto si el fallback casa
# primero "commit" como "rebase", el resultado de hoy es SIEMPRE bloqueo
# (con `rest_tokens=[]`, ninguno de los dos caminos puede aprobar) --
# rojo deterministico, confirmado en las cinco corridas (4/5 "commit",
# 1/5 "rebase", las dos bloquean). Para `merge --abort` SI importa: de
# las cinco corridas, 4/5 caso "commit" primero (bloquea, INCORRECTO) y
# 1/5 caso "merge" primero (aprueba, porque `merge` aprueba SIEMPRE, con
# o sin tokens -- nunca dependio de `rest_tokens`). Ese test se deja tal
# cual, con el comportamiento de hoy documentado como no-deterministico
# en su propio docstring -- no es un artefacto de test inestable, es el
# propio bug fuente el que no es deterministico.
# ═══════════════════════════════════════════════════════════════════════


class TestRescuePassthroughSurvivesShlexTokenizationFailure:
    """Fallo real que este contrato fija: un apostrofo sin escapar en una
    sentencia ANTERIOR de la misma cadena bash no puede tirar abajo el
    rescate de un rebase/merge en conflicto que va DESPUES en la misma
    cadena."""

    def test_rebase_abort_survives_shlex_failure_from_earlier_apostrophe(
        self, tmp_repo,
    ):
        """El PoC literal de Moriarty. Hoy bloquea SIEMPRE (ver nota de
        determinismo arriba: los dos posibles matches del fallback --
        "commit" o "rebase" -- llevan a bloqueo con `rest_tokens=[]`)."""
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            "git commit -m 'WIP: don't lose this before aborting' "
            "&& git rebase --abort"
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"un `git rebase --abort` que va DESPUES de una sentencia que "
            f"rompe shlex.split() (comilla simple sin escapar en el "
            f"mensaje del commit anterior) tiene que aprobar igual -- es "
            f"la unica salida real de un rebase en conflicto; llego "
            f"{parsed!r}"
        )

    def test_rebase_continue_survives_shlex_failure_from_earlier_apostrophe(
        self, tmp_repo,
    ):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            "git commit -m 'WIP: don't lose this before aborting' "
            "&& git rebase --continue"
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git rebase --continue` tras una sentencia que rompe "
            f"shlex.split() tiene que aprobar igual; llego {parsed!r}"
        )

    def test_rebase_skip_survives_shlex_failure_from_earlier_apostrophe(
        self, tmp_repo,
    ):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            "git commit -m 'WIP: don't lose this before aborting' "
            "&& git rebase --skip"
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git rebase --skip` tras una sentencia que rompe "
            f"shlex.split() tiene que aprobar igual; llego {parsed!r}"
        )

    def test_merge_abort_survives_shlex_failure_from_earlier_apostrophe(
        self, tmp_repo,
    ):
        """A diferencia de los tres de arriba, este caso es
        NO-DETERMINISTICO hoy (ver nota de determinismo arriba): `merge`
        aprueba siempre en `_decide_rescue_passthrough`/
        `_decide_commit_creating` independientemente de `rest_tokens`,
        asi que si el fallback casa "merge" antes que "commit" en el
        orden de iteracion del set (dependiente del hash seed del
        proceso), este test ya pasa hoy por casualidad -- no porque el
        mecanismo preserve los tokens, sino porque `merge` nunca los
        necesito. Se fija de todas formas como contrato: tiene que
        aprobar SIEMPRE, no solo cuando el hash seed favorece a
        "merge" (medido en vivo: 1 de 5 corridas)."""
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            "git commit -m 'WIP: don't lose this before aborting' "
            "&& git merge --abort"
        )
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git merge --abort` tras una sentencia que rompe "
            f"shlex.split() tiene que aprobar igual; llego {parsed!r}"
        )

    def test_anchor_plain_rebase_abort_without_shlex_failure_already_approves(
        self, tmp_repo,
    ):
        """Control balanceado: SIN ningun apostrofo que rompa shlex,
        `git rebase --abort` a secas ya aprueba hoy (cubierto tambien por
        `TestRebasePassthroughOnlyForInFlightOperations::
        test_git_rebase_abort_passes`, replicado aqui como ancla propia
        de esta clase para que quede claro que el fallo es especifico del
        camino `except ValueError`, no del passthrough de rebase en
        general)."""
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "git rebase --abort")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"sin fallo de shlex de por medio, `git rebase --abort` ya "
            f"aprueba hoy -- si esto tambien bloqueara, ninguno de los "
            f"tests de arriba probaria nada especifico del camino "
            f"`except ValueError`; llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Contrato nuevo, TEST-FIRST (encargo del propietario, 2026-08-06):
# `hooks/customs.py::_decide()` decide sobre el proyecto de la SESION
# (`hook_input.get("cwd") or os.getcwd()`, linea ~586), nunca sobre el
# directorio del COMANDO real que se va a ejecutar. Si el usuario corre
# `cd /otro/proyecto && git commit ...`, la aduana evalua contra el
# proyecto equivocado -- puede dejar pasar un commit que debia bloquear,
# o bloquear uno que no le incumbe.
#
# `hooks/customs.py` NO SE TOCA en esta fase: contrato en rojo, Ultron
# implementa despues hasta que estos tests pasen. Diez puntos del
# encargo, cada clase de aqui abajo cubre uno o dos.
#
# Sonda comun a todos estos tests: DOS repositorios git reales (nunca uno
# solo) con ajustes de aduana OPUESTOS -- uno APAGADO, otro ENCENDIDO con
# una nota invalida que dispara bloqueo si de verdad se evalua. Si la
# aduana mira el repositorio equivocado, el resultado observable (approve
# vs block) cambia por casualidad y el test lo detecta -- nunca se
# compara contra una cadena de texto fabricada a mano (unmassk-standards
# Sec.34: la comparacion es entre dos caminos reales, sesion vs cd).
# ═══════════════════════════════════════════════════════════════════════


def _init_repo(path):
    """Crea un repo git real en `path` (mkdir + git init + identidad
    local + commit inicial) -- mismo patron que el fixture `tmp_repo` de
    conftest.py, para los repositorios EXTRA que este contrato necesita
    (el destino de un `cd` tiene que ser un repositorio git de verdad
    para que `gitcmd.repo_root` lo resuelva). Fija la identidad git EN
    EL REPO (`git config user.*`, local, no global) para que el test de
    expansion de `~` -- que fuerza un `HOME` de prueba sin `.gitconfig`
    propio -- no dependa de la identidad global de esta maquina.
    """
    path.mkdir(parents=True, exist_ok=True)
    repo_path = str(path)
    rc_init, _out, err_init = run_git(["init"], repo_path)
    assert rc_init == 0, f"git init fallo en repo auxiliar: {err_init}"
    rc_email, _out, err_email = run_git(
        ["config", "user.email", "dante-test@example.com"], repo_path
    )
    assert rc_email == 0, f"git config user.email fallo en repo auxiliar: {err_email}"
    rc_name, _out, err_name = run_git(
        ["config", "user.name", "Dante Test"], repo_path
    )
    assert rc_name == 0, f"git config user.name fallo en repo auxiliar: {err_name}"
    rc_commit, _out, err_commit = run_git(
        ["commit", "--allow-empty", "-m", "init"], repo_path
    )
    assert rc_commit == 0, (
        f"git commit inicial fallo en repo auxiliar: {err_commit}"
    )
    return repo_path


class TestLeadingCdOverridesSessionCwd:
    """Contrato punto 1: un comando con `cd <ruta> &&` (o `cd <ruta>;`)
    al principio hace que el directorio EFECTIVO sea `<ruta>`, no el cwd
    de la SESION (`os.getcwd()` real del proceso del hook). El
    repositorio de sesion (A) queda con la aduana APAGADA a proposito, el
    repositorio de destino del `cd` (B) queda ENCENDIDA con una nota
    invalida -- si la aduana mira A (comportamiento de hoy), aprueba; si
    mira B (contrato), bloquea."""

    def test_cd_with_double_ampersand_uses_cd_target(self, tmp_path, tmp_repo):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        target_repo = _init_repo(tmp_path / "target-and")
        seed_config_json(target_repo, customs_enabled=True)
        seed_zones_json(target_repo, ["infra", "deploy"])

        command = f"cd {target_repo} && {_invalid_note_command('infra', 'deploy')}"
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con `cd {target_repo} &&` al principio, la aduana tiene que "
            f"evaluar CONTRA el repositorio de destino (encendido), no "
            f"contra el de la sesion (apagado); llego {parsed!r}"
        )

    def test_cd_with_semicolon_uses_cd_target(self, tmp_path, tmp_repo):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        target_repo = _init_repo(tmp_path / "target-semi")
        seed_config_json(target_repo, customs_enabled=True)
        seed_zones_json(target_repo, ["infra", "deploy"])

        command = f"cd {target_repo}; {_invalid_note_command('infra', 'deploy')}"
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con `cd {target_repo};` al principio, la aduana tiene que "
            f"evaluar contra el repositorio de destino, no contra el de "
            f"la sesion; llego {parsed!r}"
        )


class TestNoCdPreservesTodaysBehaviorExactly:
    """Contrato punto 2: SIN ningun `cd` al principio, el comportamiento
    de hoy se conserva byte a byte -- `hook_input['cwd']` si el payload
    lo trae, si no `os.getcwd()` (el cwd real del proceso). Los dos
    primeros tests fijan ese comportamiento como ancla EXPLICITA del
    contrato (ya en verde hoy -- no son el hueco; el hueco es que un `cd`
    los pise sin efecto). El tercero es un anti-falso-positivo: la
    palabra `cd` dentro del propio MENSAJE del commit no puede
    confundirse con una sentencia de shell."""

    def test_no_cd_no_payload_cwd_uses_process_cwd(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        command = _invalid_note_command("infra", "deploy")

        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"sin cd y sin payload_cwd, la aduana tiene que seguir "
            f"evaluando contra el cwd real del proceso; llego {parsed!r}"
        )

    def test_no_cd_with_payload_cwd_uses_payload_cwd_over_process_cwd(
        self, tmp_path, tmp_repo,
    ):
        process_repo = tmp_repo
        seed_config_json(process_repo, customs_enabled=False)

        payload_repo = _init_repo(tmp_path / "payload-cwd-repo")
        seed_config_json(payload_repo, customs_enabled=True)
        seed_zones_json(payload_repo, ["infra", "deploy"])

        command = _invalid_note_command("infra", "deploy")
        rc, parsed, stdout, stderr = run_customs_hook(
            process_repo, command, payload_cwd=payload_repo,
        )

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"sin cd, hook_input['cwd'] tiene que ganar sobre el cwd real "
            f"del proceso -- comportamiento YA vigente hoy, no deberia "
            f"cambiar; llego {parsed!r}"
        )

    def test_literal_cd_word_inside_commit_message_is_not_mistaken_for_shell_cd(
        self, tmp_repo,
    ):
        """Mismo tipo de falso positivo que ya peleo este fichero para
        'git log'/'git commit' como subcadena (ver
        `TestCommitDetectionHasNoFalsePositivesOnMereMentions` mas
        arriba) -- aqui aplicado a 'cd'. Unico repositorio real de este
        test: la sesion. Si un parser ingenuo buscara la subcadena 'cd '
        en cualquier parte del comando (incluido dentro del mensaje
        citado) en vez de detectar la sentencia de shell real, este test
        lo detectaria porque no hay ningun OTRO repositorio al que
        pudiera desviarse."""
        seed_config_json(tmp_repo, customs_enabled=True)
        seed_zones_json(tmp_repo, ["infra", "deploy"])
        message = (
            "[ZZZ-1][infra][deploy] ▲ update the cd-player firmware docs\n"
            "\n"
            "Description: contenido de prueba, no deberia importar."
        )
        rc, parsed, stdout, stderr = run_customs_hook(
            tmp_repo, _commit_command(message),
        )

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"la palabra 'cd' dentro del MENSAJE del commit no puede "
            f"confundirse con una sentencia de shell 'cd' -- la aduana "
            f"tiene que seguir evaluando contra el repositorio de la "
            f"sesion; llego {parsed!r}"
        )


class TestRelativeCdResolvesAgainstCorrectBase:
    """Contrato puntos 3 y 4: una ruta RELATIVA en el `cd` se resuelve a
    absoluta contra el directorio BASE correcto -- `hook_input['cwd']`
    si viene poblado (punto 3), si no el cwd real del proceso (punto 4).
    Sonda: el nombre relativo `proj` existe como subdirectorio -- un
    repositorio git DISTINTO -- tanto bajo la base correcta como bajo la
    base incorrecta, con ajustes de aduana OPUESTOS en cada uno, para que
    resolver contra la base equivocada de una respuesta observable
    DISTINTA, nunca la misma por casualidad."""

    def test_relative_cd_resolves_against_payload_cwd_not_process_cwd(
        self, tmp_path, tmp_repo,
    ):
        # base equivocada: el cwd real del proceso (la 'sesion')
        wrong_base = tmp_repo
        wrong_target = _init_repo(Path(wrong_base) / "proj")
        seed_config_json(wrong_target, customs_enabled=False)

        # base correcta: hook_input['cwd'] del payload
        right_base = _init_repo(tmp_path / "payload-base")
        right_target = _init_repo(Path(right_base) / "proj")
        seed_config_json(right_target, customs_enabled=True)
        seed_zones_json(right_target, ["infra", "deploy"])

        command = f"cd proj && {_invalid_note_command('infra', 'deploy')}"
        rc, parsed, stdout, stderr = run_customs_hook(
            wrong_base, command, payload_cwd=right_base,
        )

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con hook_input['cwd'] poblado, el 'cd proj' relativo tiene "
            f"que resolverse contra ESE valor ({right_base!r}), no contra "
            f"el cwd real del proceso ({wrong_base!r}); llego {parsed!r}"
        )

    def test_relative_cd_resolves_against_process_cwd_when_no_payload_cwd(
        self, tmp_repo,
    ):
        seed_config_json(tmp_repo, customs_enabled=False)
        nested_target = _init_repo(Path(tmp_repo) / "proj")
        seed_config_json(nested_target, customs_enabled=True)
        seed_zones_json(nested_target, ["infra", "deploy"])

        command = f"cd proj && {_invalid_note_command('infra', 'deploy')}"
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"sin hook_input['cwd'], el 'cd proj' relativo tiene que "
            f"resolverse contra el cwd real del proceso ({tmp_repo!r}); "
            f"llego {parsed!r}"
        )


class TestCdPathExpansionAndQuoting:
    """Contrato puntos 5 y 6: `~` se expande al HOME real del proceso, y
    una ruta entre comillas (simples o dobles) con espacios dentro se
    reconoce como una unica ruta, no como varios tokens sueltos."""

    def test_tilde_expands_to_home_directory(self, tmp_path, tmp_repo):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        home_target = _init_repo(fake_home / "homerepo")
        seed_config_json(home_target, customs_enabled=True)
        seed_zones_json(home_target, ["infra", "deploy"])

        command = f"cd ~/homerepo && {_invalid_note_command('infra', 'deploy')}"
        rc, parsed, stdout, stderr = run_customs_hook(
            session_repo, command, env={"HOME": str(fake_home)},
        )

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"'cd ~/homerepo' tiene que expandir '~' al HOME real del "
            f"proceso ({fake_home!r}) y evaluar contra ese repositorio; "
            f"llego {parsed!r}"
        )

    def test_double_quoted_path_with_spaces(self, tmp_path, tmp_repo):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        target_repo = _init_repo(tmp_path / "target with spaces dq")
        seed_config_json(target_repo, customs_enabled=True)
        seed_zones_json(target_repo, ["infra", "deploy"])

        command = (
            f'cd "{target_repo}" && '
            f'{_invalid_note_command("infra", "deploy")}'
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"'cd \"{target_repo}\"' (comillas dobles, espacios dentro) "
            f"tiene que reconocerse como UNA sola ruta; llego {parsed!r}"
        )

    def test_single_quoted_path_with_spaces(self, tmp_path, tmp_repo):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        target_repo = _init_repo(tmp_path / "target with spaces sq")
        seed_config_json(target_repo, customs_enabled=True)
        seed_zones_json(target_repo, ["infra", "deploy"])

        command = f"cd '{target_repo}' && {_invalid_note_command('infra', 'deploy')}"
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"\"cd '{target_repo}'\" (comillas simples, espacios dentro) "
            f"tiene que reconocerse como UNA sola ruta; llego {parsed!r}"
        )


class TestCdToNonexistentPathFallsBackGracefully:
    """Contrato punto 7: un `cd` a una ruta que NO existe no revienta el
    hook -- cae al comportamiento de hoy (evaluar contra el cwd real tal
    cual, sin el `cd`). Ya verde HOY (todavia no hay parseo de `cd`, asi
    que la ruta inexistente ya se ignora por completo) -- se fija aqui
    como red de seguridad para cuando Ultron implemente el parseo: tiene
    que comprobar la existencia del destino ANTES de usarlo, no dejar que
    la resolucion de una ruta inexistente reviente sin capturar y caiga
    en el bloqueo GENERICO de `main()` (el mismo patron de fallo que ya
    corrigio el hallazgo de `config.json` corrupto de este mismo
    fichero, para otro camino de excepcion)."""

    def test_cd_to_nonexistent_path_falls_back_to_session_cwd_behavior(
        self, tmp_repo, format_mod, validator_mod, rejection_mod, zones_mod, config_mod,
    ):
        seed_config_json(tmp_repo, customs_enabled=True)
        seed_zones_json(tmp_repo, ["product", "testarea"])
        message = (
            "[Z-1][product][testarea] ▲ some clearly unrecognized note type\n"
            "\n"
            "Description: contenido de prueba para el tipo desconocido."
        )
        expected_text = _expected_block_text(
            format_mod, validator_mod, rejection_mod, zones_mod, config_mod,
            tmp_repo, message,
        )
        command = (
            "cd /this/path/does/not/exist/xyz-dante-2026 && "
            f"{_commit_command(message)}"
        )

        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un 'cd' a una ruta inexistente no puede tumbar la "
            f"evaluacion -- tiene que caer al comportamiento de hoy "
            f"(evaluar contra el cwd real); llego {parsed!r}"
        )
        assert parsed.get("reason") == expected_text, (
            "con un 'cd' a una ruta inexistente, el texto de bloqueo "
            "tiene que seguir siendo el que produce "
            "rejection.render_hook_block() sobre el repositorio real -- "
            "no el mensaje generico de 'fallo inesperado' que dispararia "
            "si la excepcion de resolver una ruta inexistente escapara "
            f"sin capturar:\n--- aduana ---\n{parsed.get('reason')!r}\n"
            f"--- esperado ---\n{expected_text!r}"
        )


class TestChainedCdLastOneWins:
    """Contrato punto 8: encadenados (`cd /a && cd /b && git ...`) --
    manda el ULTIMO `cd` que se aplica antes de la sentencia que crea el
    commit. Sonda: el primer destino (P) queda APAGADO, el segundo (Q, el
    que manda) queda ENCENDIDO -- si la aduana se quedara con el PRIMER
    `cd` en vez del ultimo, aprobaria en vez de bloquear."""

    def test_chained_cd_uses_last_target(self, tmp_path, tmp_repo):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        first_target = _init_repo(tmp_path / "chain-first")
        seed_config_json(first_target, customs_enabled=False)

        last_target = _init_repo(tmp_path / "chain-last")
        seed_config_json(last_target, customs_enabled=True)
        seed_zones_json(last_target, ["infra", "deploy"])

        command = (
            f"cd {first_target} && cd {last_target} && "
            f"{_invalid_note_command('infra', 'deploy')}"
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con dos 'cd' encadenados, tiene que mandar el ULTIMO "
            f"({last_target!r}), no el primero ({first_target!r}) ni el "
            f"cwd de la sesion; llego {parsed!r}"
        )


class TestCdNotAtBeginningStillApplies:
    """Contrato punto 9: un `cd` que NO esta al principio de la cadena
    (p.ej. `echo x && cd /otro && git ...`) TAMBIEN se aplica -- decision
    de este contrato, ningun documento previo la fija. Motivo, en una
    linea: `&&` en bash es ejecucion SECUENCIAL real -- cuando la
    sentencia de commit se ejecuta, el shell YA esta en el directorio del
    ultimo `cd` anterior, sea o no la primera sentencia de la cadena;
    tratar solo el `cd` inicial como valido imitaria mal al propio bash,
    que es justo lo que este contrato reproduce."""

    def test_cd_after_other_command_in_chain_still_applies(
        self, tmp_path, tmp_repo,
    ):
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        target_repo = _init_repo(tmp_path / "not-first-cd-target")
        seed_config_json(target_repo, customs_enabled=True)
        seed_zones_json(target_repo, ["infra", "deploy"])

        command = (
            f"echo hello && cd {target_repo} && "
            f"{_invalid_note_command('infra', 'deploy')}"
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"un 'cd' que no es la primera sentencia de la cadena tiene "
            f"que aplicarse igual -- asi se comporta bash de verdad; "
            f"llego {parsed!r}"
        )


class TestCdFixDoesNotBreakExistingSafetyNets:
    """Contrato punto 10: nada de lo que ya existe se rompe con el parseo
    nuevo de `cd`. Los rescates (`merge`/`rebase`
    `--abort`/`--continue`/`--skip`) siguen aprobando ANTES de leer
    ningun fichero, y el bloqueo ante fichero corrupto sigue dando su
    instruccion de reparacion -- los dos, incluso cuando el repositorio
    real a mirar llega detras de un `cd`."""

    def test_rescue_command_still_approves_after_cd_to_corrupt_config_repo(
        self, tmp_path, tmp_repo,
    ):
        """`merge --abort` aprueba SIEMPRE, antes de tocar config.json --
        tiene que seguir aprobando aunque el `cd` resuelva a un
        repositorio con config.json corrupto. Ya verde hoy (el rescate ya
        aprueba sin condicion, y hoy el 'cd' se ignora del todo) -- se
        fija como ancla explicita de que el parseo nuevo no invierte el
        orden (rescate siempre antes que lectura de ficheros)."""
        session_repo = tmp_repo
        target_repo = _init_repo(tmp_path / "rescue-corrupt-target")
        _write_corrupt_json(target_repo, "config.json")

        command = f"cd {target_repo} && git merge --abort"
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"'git merge --abort' tiene que aprobar SIEMPRE, incluso tras "
            f"un 'cd' a un repositorio con config.json corrupto; llego "
            f"{parsed!r}"
        )

    def test_corrupt_config_escape_hatch_still_fires_after_cd_resolves_target(
        self, tmp_path, tmp_repo,
    ):
        """Un commit normal (sin nota) sigue bloqueado con la instruccion
        de reparacion cuando config.json esta corrupto -- pero del
        repositorio que resuelve el `cd`, no del de la sesion. Rojo hoy:
        el 'cd' se ignora, la sesion no tiene config.json corrupto (sin
        notas -> aduana apagada), asi que hoy aprueba; el contrato exige
        bloquear con la instruccion de reparacion del config.json del
        repositorio de DESTINO."""
        session_repo = tmp_repo
        target_repo = _init_repo(tmp_path / "escape-hatch-target")
        _write_corrupt_json(target_repo, "config.json")

        command = (
            f"cd {target_repo} && "
            f"{_commit_command('fix: a normal code commit, not a memory note')}"
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"con config.json corrupto en el repositorio de destino del "
            f"'cd', un commit normal tiene que bloquear; llego {parsed!r}"
        )
        reason = parsed.get("reason")
        assert _reason_has_escape_hatch(reason, "config.json"), (
            "el reason tiene que mencionar como reparar config.json del "
            "repositorio de DESTINO del cd, no volcar la excepcion cruda "
            f"ni quedarse callado; llego: {reason!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Contrato nuevo, TEST-FIRST (hallazgo de Cerberus tras la implementacion
# de Ultron -- fase 2 del contrato del `cd`, 2026-08-06, con los 52 tests
# de arriba ya en verde): `_resolve_effective_cwd` (hooks/customs.py)
# aplica CUALQUIER sentencia `cd` de todo el comando, este ANTES o
# DESPUES de la sentencia que crea el commit. Reproducido en vivo por
# Cerberus:
#
#   cmd = "cd unmassk-toolkit && git commit -m x && cd .."
#   _resolve_effective_cwd(cmd, "/Users/unmassk/Workspace/claude-toolkit")
#   # devuelve la base de sesion, no "unmassk-toolkit/" -- que es donde
#   # bash esta DE VERDAD cuando corre "git commit -m x"
#
# Es el idioma del dia a dia: entrar a un subproyecto, commitear, volver.
# La aduana acaba evaluando un directorio que no es ni el de la sesion ni
# el real del commit, y no queda nada en pantalla.
#
# `hooks/customs.py` NO SE TOCA en esta fase -- contrato en rojo, Ultron
# implementa despues. Misma sonda que el resto del fichero: dos
# repositorios git reales con ajustes de aduana OPUESTOS, senal
# observable approve/block, por el camino real (proceso aparte + stdin) --
# nunca una cadena fabricada a mano.
# ═══════════════════════════════════════════════════════════════════════


class TestCdAfterCommitStatementDoesNotOverrideEffectiveCwd:
    """El directorio EFECTIVO para decidir es el que esta vigente EN EL
    MOMENTO del commit -- un `cd` que llega DESPUES de la sentencia que
    crea el commit no puede pisarlo, aunque `_resolve_effective_cwd` hoy
    lo aplique igual que uno anterior."""

    def test_trailing_cd_dot_dot_does_not_undo_the_cd_at_commit_time(
        self, tmp_repo,
    ):
        """Reproduccion literal del hallazgo de Cerberus: `cd <subproj> &&
        git commit ... && cd ..` -- `subproj` es un repositorio ANIDADO
        DENTRO de la sesion (mismo shape que 'unmassk-toolkit/' dentro de
        'claude-toolkit/' en el PoC real), asi que el `cd ..` final
        aterriza EXACTAMENTE en la sesion -- la misma forma exacta del
        bug reportado, no una variante sintetica. Sesion (A) queda
        APAGADA, subproyecto (B) ENCENDIDO con una nota invalida -- si la
        aduana mira A (el bug), aprueba; si mira B (donde bash estaba de
        verdad al commitear), bloquea."""
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        subproject = _init_repo(Path(session_repo) / "subproject")
        seed_config_json(subproject, customs_enabled=True)
        seed_zones_json(subproject, ["infra", "deploy"])

        command = (
            f"cd subproject && {_invalid_note_command('infra', 'deploy')} "
            "&& cd .."
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"'cd subproject && git commit ... && cd ..' tiene que "
            f"evaluar contra 'subproject' (donde bash estaba AL "
            f"COMMITEAR), no contra la sesion a la que el 'cd ..' "
            f"posterior vuelve; llego {parsed!r}"
        )

    def test_trailing_cd_to_another_repo_does_not_override_commit_time_repo(
        self, tmp_path, tmp_repo,
    ):
        """Simetrico -- punto 2 del encargo: `cd <repoA> && git commit ...
        && cd <repoB>`, A y B repositorios DISTINTOS con ajustes
        opuestos. Decide sobre A (donde bash estaba al commitear), nunca
        sobre B (adonde bash se movio DESPUES, ya sin relacion con el
        commit que se acaba de crear)."""
        session_repo = tmp_repo

        repo_a = _init_repo(tmp_path / "repo-a-at-commit-time")
        seed_config_json(repo_a, customs_enabled=True)
        seed_zones_json(repo_a, ["infra", "deploy"])

        repo_b = _init_repo(tmp_path / "repo-b-after-commit")
        seed_config_json(repo_b, customs_enabled=False)

        command = (
            f"cd {repo_a} && {_invalid_note_command('infra', 'deploy')} "
            f"&& cd {repo_b}"
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"'cd {repo_a} && git commit ... && cd {repo_b}' tiene que "
            f"decidir sobre {repo_a!r} (donde bash estaba al commitear), "
            f"nunca sobre {repo_b!r} (adonde se movio DESPUES); llego "
            f"{parsed!r}"
        )

    def test_chained_leading_cds_still_apply_and_are_not_undone_by_trailing_cd(
        self, tmp_path, tmp_repo,
    ):
        """Punto 3 del encargo -- no se rompe lo ya fijado: dos `cd`
        encadenados ANTES del commit siguen mandando el ultimo de ellos
        (`TestChainedCdLastOneWins`, fase 1, sigue verde) -- aqui se
        anade un TERCER `cd` DESPUES del commit para confirmar que ese no
        pisa al que ya gano antes de la sentencia de commit. Primer
        destino (P) apagado, segundo (Q, el que manda antes del commit)
        encendido, tercer destino (R, tras el commit) apagado -- si R
        pisara a Q, aprobaria; si Q sigue mandando, bloquea."""
        session_repo = tmp_repo
        seed_config_json(session_repo, customs_enabled=False)

        first_target = _init_repo(tmp_path / "chain2-first")
        seed_config_json(first_target, customs_enabled=False)

        winning_target = _init_repo(tmp_path / "chain2-winning")
        seed_config_json(winning_target, customs_enabled=True)
        seed_zones_json(winning_target, ["infra", "deploy"])

        after_commit_target = _init_repo(tmp_path / "chain2-after-commit")
        seed_config_json(after_commit_target, customs_enabled=False)

        command = (
            f"cd {first_target} && cd {winning_target} && "
            f"{_invalid_note_command('infra', 'deploy')} && "
            f"cd {after_commit_target}"
        )
        rc, parsed, stdout, stderr = run_customs_hook(session_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"el 'cd' que gana ANTES del commit ({winning_target!r}) "
            f"tiene que seguir mandando aunque llegue otro 'cd' DESPUES "
            f"({after_commit_target!r}); llego {parsed!r}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Contrato nuevo, TEST-FIRST (hallazgo de Cerberus, fase 3, pedido
# expresamente por el propietario -- mas grave que el de las fases
# anteriores: aqui la aduana no decide MAL, no decide EN ABSOLUTO).
# Confirmado en vivo por Cerberus, y reconfirmado aqui antes de escribir
# ningun test (import directo de `customs.py`, nunca adivinado):
#
#   customs._find_commit_creating_statement("echo hi;git commit -m x")
#   # -> None
#
# `_find_commit_creating_statement` usa `shlex.split()` PLANO (sin
# `punctuation_chars`), asi que un separador de sentencia PEGADO sin
# espacio antes de "git" (`;`, `&&`, `||`, `|`) funde el separador y
# "git" en UN SOLO token (p.ej. "hi;git"). `_GIT_PROGRAM_TOKEN_RE` exige
# que el token TERMINE en "git" precedido de "/" o de inicio de cadena --
# "hi;git" no casa nunca. La funcion devuelve `None` para el comando
# ENTERO, y `_decide()` aprueba en la rama `found is None` (linea ~645)
# SIN pasar por el rescate, SIN resolver el directorio y SIN leer
# `config.json`: el commit pasa sin evaluacion alguna.
#
# Verificado en vivo, ANTES de escribir estos tests, que los CUATRO
# separadores producen el mismo `None`:
#
#   'echo hi;git commit -m x'  -> None
#   'echo hi&&git commit -m x' -> None
#   'echo hi||git commit -m x' -> None
#   'echo hi|git commit -m x'  -> None
#
# `hooks/customs.py` NO SE TOCA en esta fase -- contrato en rojo, Ultron
# implementa despues. Misma sonda de siempre: repositorio git real,
# senal observable approve/block, por el camino real (proceso aparte +
# stdin) -- nunca una cadena fabricada a mano.
# ═══════════════════════════════════════════════════════════════════════


class TestPegadoStatementSeparatorsBeforeGitAreRecognized:
    """Contrato puntos 1 y 2: un separador de sentencia PEGADO (sin
    espacio) justo antes de `git` no puede hacer que la sentencia de
    commit se vuelva invisible. Un solo repositorio con la aduana
    ENCENDIDA basta como sonda -- el mecanismo del bug es "no se lee
    NINGUN fichero", asi que no hace falta un segundo repositorio con
    ajuste opuesto para que la senal sea observable: hoy aprueba SIEMPRE
    (sin condicion alguna), el contrato exige bloquear (mensaje sin nota
    reconocible, aduana encendida). Un test por separador, para que se
    lea exactamente cual se rompio si alguno vuelve a fallar."""

    @pytest.mark.parametrize("sep", [";", "&&", "||", "|"], ids=["semicolon", "and-and", "or-or", "pipe"])
    def test_pegado_separator_before_git_still_gets_evaluated(self, tmp_repo, sep):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = f"echo hi{sep}git commit -m x"
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"{command!r} (separador {sep!r} PEGADO, sin espacio, justo "
            f"antes de 'git') tiene que evaluarse igual que si llevara "
            f"espacio -- un commit sin nota reconocible, con la aduana "
            f"encendida, tiene que bloquear, nunca aprobar sin evaluar; "
            f"llego {parsed!r}"
        )


class TestTrailingPegadoSeparatorAfterCommitStatement:
    """Contrato punto 3 -- decision de este contrato, ningun documento
    previo la fija (mismo tipo de decision que el punto 9 de la fase 1):
    un ';' PEGADO DESPUES del valor de `-m` (`git commit -m x;otra_cosa`,
    el caso exacto del hallazgo) no puede cambiar la decision que
    produciria la sentencia AISLADA (`git commit -m x`, sin la cola
    pegada) -- ya sea porque el separador se reconoce de verdad (arreglo
    completo, coherente con como bash interpretaria esto de verdad) o
    porque, como minimo, el contenido sobrante nunca se filtra de forma
    que voltee approve<->block.

    Verificado en vivo ANTES de escribir este test (import directo de
    `customs.py`, `format.py`, `validator.py`): con el tokenizado PLANO
    de hoy, 'x;otra_cosa' se funde en UN solo valor de `-m` -- la cola
    sobrante SI se cuela en el mensaje (y si el mensaje fuera una nota
    real, en el campo `why`/`context`, verificado con `format.
    parse_message`/`parse_context_message`), pero para el ejemplo EXACTO
    del hallazgo (`x` bare, ni wip ni nota ni NEXT reconocible) la
    decision de hoy YA coincide con la de la sentencia limpia -- las dos
    rebotan igual a 'gitmem work', con el MISMO texto (la plantilla de
    ese rebote no interpola ningun campo del mensaje). Por eso este test
    es YA VERDE hoy -- no es el hueco nuevo -- se fija como contrato
    EXPLICITO, con comparacion productor<->consumidor real (unmassk-
    standards Sec.34: las dos decisiones se piden al MISMO hook, nunca se
    fabrica una cadena esperada a mano), para que si algun dia la cola
    sobrante SI llega a alterar el veredicto (p.ej. un validador futuro
    que mire el campo `why`), quede detectado aqui."""

    def test_trailing_pegado_semicolon_matches_isolated_statement_decision(
        self, tmp_repo,
    ):
        seed_config_json(tmp_repo, customs_enabled=True)
        clean_command = "git commit -m x"
        polluted_command = "git commit -m x;otra_cosa"

        rc_clean, parsed_clean, out_clean, err_clean = run_customs_hook(
            tmp_repo, clean_command,
        )
        rc_polluted, parsed_polluted, out_polluted, err_polluted = run_customs_hook(
            tmp_repo, polluted_command,
        )

        assert rc_clean == 0, (
            f"el proceso del hook fallo (comando limpio): rc={rc_clean}, "
            f"stderr={err_clean!r}"
        )
        assert rc_polluted == 0, (
            f"el proceso del hook fallo (comando con cola pegada): "
            f"rc={rc_polluted}, stderr={err_polluted!r}"
        )
        assert parsed_clean is not None, (
            f"stdout no es JSON valido (comando limpio): {out_clean!r}"
        )
        assert parsed_polluted is not None, (
            f"stdout no es JSON valido (comando con cola pegada): "
            f"{out_polluted!r}"
        )
        assert parsed_polluted.get("decision") == parsed_clean.get("decision"), (
            f"{polluted_command!r} tiene que decidir IGUAL que "
            f"{clean_command!r} aislado -- la cola pegada tras el ';' no "
            f"puede cambiar el veredicto; limpio={parsed_clean!r}, "
            f"con cola={parsed_polluted!r}"
        )
        assert parsed_polluted.get("reason") == parsed_clean.get("reason"), (
            f"y el texto (si bloquea) tiene que ser el MISMO, no uno "
            f"contaminado con la cola pegada; "
            f"limpio={parsed_clean.get('reason')!r}, "
            f"con cola={parsed_polluted.get('reason')!r}"
        )


class TestNormalCommandsStillRecognizedAfterSeparatorFix:
    """Contrato punto 4 -- anclas explicitas de que lo normal sigue
    reconociendose: un comando corriente con espacios alrededor del
    subcomando, y uno que invoca git por RUTA ABSOLUTA al binario. Los
    dos ya verdes hoy -- se fijan aqui para que la correccion de los
    separadores pegados (puntos 1 y 2) no los rompa por el camino."""

    def test_normal_spaced_command_still_recognized(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, "git commit -m x")

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"'git commit -m x' (forma normal, con espacios) tiene que "
            f"seguir reconociendose y bloqueando (mensaje sin nota "
            f"reconocible); llego {parsed!r}"
        )

    def test_absolute_path_to_git_binary_still_recognized(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        rc, parsed, stdout, stderr = run_customs_hook(
            tmp_repo, "/usr/bin/git commit -m x",
        )

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"'/usr/bin/git commit -m x' (ruta absoluta al binario) "
            f"tiene que seguir reconociendose y bloqueando; llego "
            f"{parsed!r}"
        )


class TestQuotedSemicolonInsideCommitMessageIsNotASeparator:
    """Contrato punto 5: un ';' DENTRO de un mensaje CITADO (`git commit
    -m "arreglado a;b"`) no puede confundirse con un separador de shell.
    Las comillas ya protegen el ';' hoy -- `shlex` respeta comillas
    independientemente de si detecta separadores pegados, verificado en
    vivo antes de escribir este test -- se fija aqui como ancla explicita
    para que la correccion de los puntos 1 y 2 no la rompa."""

    def test_quoted_semicolon_inside_message_is_preserved_as_literal_text(
        self, tmp_repo,
    ):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = 'git commit -m "arreglado a;b"'
        rc, parsed, stdout, stderr = run_customs_hook(tmp_repo, command)

        assert rc == 0, f"el proceso del hook fallo: rc={rc}, stderr={stderr!r}"
        assert parsed is not None, f"stdout no es JSON valido: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"{command!r} tiene que reconocerse como UNA sola sentencia "
            f"de commit (el ';' esta DENTRO de las comillas, no es un "
            f"separador) y bloquear (mensaje sin nota reconocible); "
            f"llego {parsed!r}"
        )
