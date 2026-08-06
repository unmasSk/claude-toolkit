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

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
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


def run_customs_hook(cwd, command):
    """Invoca `hooks/customs.py` como proceso aparte con un payload de
    Bash tool_input real por stdin. Misma convencion medida que
    `test_pre_merge_gate.py::_run_hook` (v1, ya en produccion).

    Devuelve `(rc, parsed_json_or_None, stdout, stderr)`.
    """
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    result = subprocess.run(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
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
