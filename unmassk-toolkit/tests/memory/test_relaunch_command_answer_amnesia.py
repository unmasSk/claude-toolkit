"""Contrato ROJO: el ciclo intento -> rechazo -> relanzamiento no converge
cuando dos rechazos se encadenan -- PIEZAS.md Sec.7.4 ("el rechazo... el
comando exacto para relanzar"), spec-sistema-memoria-v2.md Sec.2 (P5:
"responder es relanzar el comando con la respuesta como argumento").

EL FALLO, reproducido aqui con `bin/gitmem` real contra un repo real (no
en teoria): `lib/memory/validator.py::validate_pain_question` (linea
~338, construye su `command` solo con `note.type/zone1/zone2/headline`
mas el `--stops` que SI conoce) y `validate_replacement` (linea ~420,
construye el suyo con `--why`/`--description`/`--replaces` pero SIN
`--stops`) escriben cada uno su `command` por separado, sin mirar lo que
el intento que disparo el rechazo ya traia. Secuencia real:

    1. `gitmem note M --zones Z1 Z2 "..." --description "..."`
       -> rechazo `missing_pain_answer`: falta `--stops`. Ofrece DOS
       relanzamientos, uno de ellos con `--stops yes` (tipo R).
    2. Se relanza con `--stops yes` -> rechazo `overlapping_note` (esta
       nota pisa a otra ya escrita en la zona). Su `command` trae
       `--replaces <id>` -- y ya NO trae `--stops yes`.
    3. Si se relanza tal cual, `--stops` vuelve a faltar -> rebota otra
       vez a `missing_pain_answer`. Y su comando, a su vez, no trae
       `--replaces`. El ciclo no cierra en ningun numero finito de pasos.

POR QUE ESTE TEST SE JUSTIFICA (regla de esta rama, CLAUDE.md: "un test
entra solo si compara dos cosas escritas por separado"): compara, en
cada paso, DOS cosas escritas por separado y en momentos distintos --
los flags que el intento YA relanzado trae (extraidos tokenizando el
propio comando que se acaba de ejecutar) contra el comando NUEVO que el
siguiente rechazo ofrece (extraido de la salida real de `bin/gitmem`,
un proceso real, nunca del codigo fuente ni de una prediccion). Ninguno
de los dos lados se teclea a mano.

Alcance deliberado (granularidad de aceptacion, pase de CONTRATO antes
de que Ultron repare nada -- CLAUDE.md, "Test-first mode"): dos tests,
no el barrido exhaustivo de las nueve funciones de `validator.py`. El
encargo señala expresamente que el mismo patron se repite en
`validator_pointers.py`/`validator_zones.py`; ese barrido es material
para el pase de ENDURECIMIENTO, tras la implementacion, no para este.

No hay atacante externo en el modelo de amenaza de esta rama -- el
unico riesgo real que este fichero prueba es que el sistema se rompe a
si mismo empujando a "no guardes la nota", que es justo lo que la
aduana existe para impedir [CLAUDE.md, "Que security y tests son para
en ESTE proyecto"].

Nada de esto se arregla aqui -- Ultron corrige `validator.py` despues.
"""

import re
import shlex

import pytest

from .conftest import (
    extract_note_id,
    pm_path,
    run_gitmem_script,
    seed_note_via_script,
    seed_zones_json,
)

ZONE1 = "api"
ZONE2 = "billing"
# Sin puntuacion ni comillas -- tokeniza limpio con shlex y no colisiona
# con el propio marcador de hueco `"..."` que los rechazos usan para
# `--description`.
HEADLINE = "los comandos de relanzamiento no deben perder respuestas ya dadas"
# Placeholder literal que el propio sistema ya usa en sus comandos de
# relanzamiento (p.ej. `--description "..."`). `\w+` (la regex de
# tokenizacion de `similar.py::_tokens`) no matchea puntos -- por eso
# aportar CERO palabras al vocabulario de Jaccard es intencionado: dos
# notas con el MISMO titular y `description="..."` en las dos quedan
# con solapamiento 1.0, garantizado, sin depender del texto que cada
# paso del relanzamiento use para `--description`.
DESCRIPTION_PLACEHOLDER = "..."

MAX_STEPS = 6

_ANSWER_FLAGS = ("--stops", "--replaces", "--origin", "--awaits")


def _extract_relaunch_commands(stdout):
    """Los comandos del campo `Rejection.relaunch` -- SOLO las lineas
    que van despues de la cabecera literal `"Relanza:"` que
    `rejection.render_terminal` imprime (`lib/memory/rejection.py::
    _render`, "lines.append('Relanza:')" seguido de una linea por
    comando de `r.relaunch`, cada una precedida de dos espacios).

    Deliberadamente NO cualquier linea que empiece por `"gitmem "` en
    todo `stdout`: el cuerpo de `options` de `overlapping_note`
    (`validator.py`, rechazo `overlapping_note`) menciona ADEMAS, como
    prosa explicativa de la tercera salida ("es duplicado"), un
    `gitmem remove <id> ...` que NO es el campo `command` estructurado
    de ESE rechazo -- confirmado en vivo: sin este filtro,
    `_extract_relaunch_commands` devolvia dos comandos para un rechazo
    cuyo contrato (`rejection.build`, PIEZAS.md Sec.7.4) dice que
    `command` es "uno o dos comandos", nunca tres ni una mezcla con
    prosa. El campo real de relanzamiento -- lo unico que P5 (spec
    Sec.2, "responder es relanzar el comando") describe -- es
    exactamente lo que vive bajo `"Relanza:"`.
    """
    if "Relanza:" not in stdout:
        return []
    after = stdout.split("Relanza:", 1)[1]
    return [
        line.strip()
        for line in after.splitlines()
        if line.strip().startswith("gitmem ")
    ]


def _tokens(command):
    """Tokeniza un comando `gitmem ...` real, sin el token `gitmem`
    inicial -- lo que `run_gitmem_script` espera como `args`.
    """
    return shlex.split(command)[1:]


def _flag_value(tokens, flag):
    """El valor inmediatamente despues de `flag` en `tokens`, o `None`
    si el flag no aparece -- nunca fabricado, solo leido.
    """
    if flag not in tokens:
        return None
    idx = tokens.index(flag)
    if idx + 1 >= len(tokens):
        return None
    return tokens[idx + 1]


def _answers_in(tokens):
    """Las respuestas (`--stops`/`--replaces`/`--origin`/`--awaits`) que
    `tokens` YA trae, como `{flag: valor}` -- solo las que estan
    presentes de verdad, nunca completadas con un valor por defecto.
    """
    return {
        flag: value
        for flag in _ANSWER_FLAGS
        if (value := _flag_value(tokens, flag)) is not None
    }


def _pick_relaunch(commands):
    """Cuando un rechazo ofrece mas de un comando (solo pasa con
    `missing_pain_answer`, TEXTOS.md Sec.1.5 -- una alternativa M con
    `--stops no`, otra R con `--stops yes`), esta es la UNICA decision
    que el test toma por el usuario simulado: elegir la rama `--stops
    yes` (tipo R) si esta -- R admite `--why` en su vocabulario
    [vocabulary.py TYPES["R"].allowed_fields], evitando que el `--why
    "..."` que `validate_replacement` añade sin condicion de tipo
    dispare ADEMAS un `field_not_allowed` ajeno al fallo que este
    fichero reproduce (M no admite `--why`). No es una eleccion
    arbitraria disfrazada: el resto del ciclo (una vez fijado el tipo)
    solo ofrece SIEMPRE un unico comando por rechazo.
    """
    if len(commands) == 1:
        return commands[0]
    for command in commands:
        tokens = _tokens(command)
        if _flag_value(tokens, "--stops") == "yes":
            return command
    return commands[0]


def _seed_existing_similar_note(repo):
    """Una nota YA escrita en `[ZONE1][ZONE2]` con el MISMO titular y
    `description="..."` -- solapamiento de Jaccard 1.0 garantizado
    contra cualquier candidata que use el mismo titular (ver comentario
    de `DESCRIPTION_PLACEHOLDER` arriba), sin importar que texto real
    lleve `--description` en cada paso del relanzamiento. Tipo `Q`
    (pregunta abierta): el unico tipo cuyo alta no exige contestar
    ninguna pregunta previa (`stops`/`issue`), asi que sembrarla es una
    unica llamada, sin ella misma disparar el ciclo bajo prueba.
    """
    # --work no [2026-08-26, D-065/D-066]: la aduana de issues rebota una
    # Q sin --issue/--work antes de llegar al ciclo de rechazos que este
    # fichero prueba -- esta Q solo es la nota YA existente que dispara
    # el solapamiento, ajena a la aduana bajo prueba.
    rc, stdout, stderr = seed_note_via_script(
        repo, "Q", ZONE1, ZONE2, HEADLINE, description=DESCRIPTION_PLACEHOLDER,
        work="no",
    )
    assert rc == 0, (
        f"fallo al sembrar la nota existente que dispara el solapamiento "
        f"(error de siembra, no el fallo bajo prueba): rc={rc}\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
    return extract_note_id(stdout)


def test_overlap_rejection_command_drops_the_already_answered_stops_flag(tmp_repo):
    """Comparacion minima, aislada, de las DOS cosas del contrato: los
    flags que el segundo intento (el que YA contesto `--stops yes`)
    traia de verdad, contra el comando que el rechazo SIGUIENTE
    (`overlapping_note`) ofrece para el tercero. Fallo esperado HOY:
    `--stops yes` desaparece.
    """
    seed_zones_json(tmp_repo, [ZONE1, ZONE2])
    _seed_existing_similar_note(tmp_repo)

    # Paso 1: intento real, sin `--stops` -- exactamente la reproduccion
    # del encargo.
    rc1, out1, err1 = run_gitmem_script(
        ["note", "M", "--zones", ZONE1, ZONE2, HEADLINE,
         "--description", DESCRIPTION_PLACEHOLDER],
        cwd=tmp_repo,
    )
    assert rc1 != 0, (
        f"sanidad de montaje: el primer intento (sin --stops) tendria que "
        f"rebotar -- salio rc=0:\n{out1}"
    )
    assert "falta una respuesta" in out1, (
        f"sanidad de montaje: se esperaba el rechazo 'missing_pain_answer' "
        f"(TEXTOS.md Sec.1.5); salio otra cosa:\n{out1}"
    )
    commands1 = _extract_relaunch_commands(out1)
    assert commands1, f"el rechazo del paso 1 no ofrecio ningun comando de relanzamiento:\n{out1}"

    relaunch_2 = _pick_relaunch(commands1)
    tokens_2 = _tokens(relaunch_2)
    assert _flag_value(tokens_2, "--stops") == "yes", (
        f"sanidad de montaje: se eligio el relanzamiento equivocado, no "
        f"trae --stops yes: {relaunch_2!r}"
    )

    # Paso 2: se ejecuta LITERALMENTE lo que el paso 1 ofrecio.
    rc2, out2, err2 = run_gitmem_script(tokens_2, cwd=tmp_repo)
    assert rc2 != 0, (
        f"sanidad de montaje: el segundo intento (con --stops yes, pero "
        f"pisando la nota existente) tendria que rebotar -- salio rc=0:\n{out2}"
    )
    assert "pisa a algo que ya esta escrito" in out2, (
        f"sanidad de montaje: se esperaba el rechazo 'overlapping_note' "
        f"(TEXTOS.md Sec.1.6); salio otra cosa (revisa que la siembra de "
        f"la nota parecida disparo el solapamiento):\n{out2}"
    )
    commands2 = _extract_relaunch_commands(out2)
    assert len(commands2) == 1, (
        f"'overlapping_note' siempre ofrece un unico comando "
        f"[validator.py, linea ~420] -- salieron {len(commands2)}: {commands2}"
    )
    overlap_command = commands2[0]
    overlap_tokens = _tokens(overlap_command)

    # LA COMPARACION REAL: el flag que el paso 2 YA contesto (`--stops
    # yes`, extraido de `tokens_2`, lo que de verdad se ejecuto) tiene
    # que seguir presente, con el MISMO valor, en el comando que el
    # rechazo del paso 2 ofrece para el paso 3 (`overlap_tokens`, leido
    # de la salida real del proceso -- nunca del codigo fuente).
    assert _flag_value(overlap_tokens, "--stops") == "yes", (
        f"el comando de relanzamiento que ofrece 'overlapping_note' perdio "
        f"la respuesta ya dada a la pregunta del dolor (--stops yes, dada "
        f"en el paso 2: {relaunch_2!r}) -- ofrece en su lugar: "
        f"{overlap_command!r}. Relanzar esto tal cual vuelve a rebotar por "
        f"falta de --stops, exactamente el ciclo que no converge descrito "
        f"en el encargo."
    )


def test_pain_question_and_overlap_rejection_cycle_converges(tmp_repo):
    """Contrato completo: partiendo de una nota que dispara los DOS
    rechazos encadenados (dolor + solapamiento), ejecutar LITERALMENTE
    cada comando que el sistema ofrece tiene que acabar guardando la
    nota, en un numero finito (`MAX_STEPS`) de pasos -- nunca un
    comando que pierda o cambie una respuesta ya dada.

    En cada paso se comprueba, ANTES de ejecutar el siguiente comando,
    que TODA respuesta ya dada en un paso anterior (`given_answers`,
    acumulado leyendo lo que cada comando ejecutado de verdad traia)
    sigue presente y con el MISMO valor en el comando que el rechazo
    acaba de ofrecer -- la comprobacion general de la que
    `test_overlap_rejection_command_drops_the_already_answered_stops_flag`
    es el caso minimo aislado. Esto cubre a la vez las dos cosas que el
    encargo pide que NO pasen: que se pierda una respuesta ya dada, y
    que se invente una distinta de la que el usuario dio -- las dos
    fallan la MISMA asercion (un valor que ya no coincide), nunca una
    por separado.

    Fallo esperado HOY: la asercion de "respuesta preservada" salta en
    el primer relanzamiento tras el solapamiento (paso 2 -> paso 3),
    con el mismo motivo exacto que el test aislado de arriba -- este
    test ademas prueba, una vez arreglado, que la secuencia real
    converge de verdad (round-trip contra git real: el identificador
    que `note.py` imprime aparece de verdad en un indice real en
    disco), no solo que un flag concreto ya no se pierde.
    """
    seed_zones_json(tmp_repo, [ZONE1, ZONE2])
    _seed_existing_similar_note(tmp_repo)

    given_answers = {}
    current_args = [
        "note", "M", "--zones", ZONE1, ZONE2, HEADLINE,
        "--description", DESCRIPTION_PLACEHOLDER,
    ]
    transcript = []

    for step in range(MAX_STEPS):
        rc, stdout, stderr = run_gitmem_script(current_args, cwd=tmp_repo)
        transcript.append((list(current_args), rc, stdout))

        if rc == 0:
            note_id = extract_note_id(stdout)
            pm = pm_path(tmp_repo)
            index_files = list(pm.glob("*.md"))
            assert index_files, f"'{note_id}' guardada pero no hay ningun indice en {pm}"
            found = any(
                note_id in index_file.read_text(encoding="utf-8")
                for index_file in index_files
            )
            assert found, (
                f"note.py dijo '{note_id} guardada' pero ese identificador "
                f"no aparece en ningun fichero de {pm} -- round-trip real "
                f"contra disco, no una confirmacion de palabra"
            )
            return  # CONVERGIO: contrato cumplido.

        commands = _extract_relaunch_commands(stdout)
        assert commands, (
            f"paso {step}: el rechazo no ofrecio ningun comando de "
            f"relanzamiento (viola P5, spec Sec.2) -- salida:\n{stdout}"
        )
        chosen = _pick_relaunch(commands)
        chosen_tokens = _tokens(chosen)

        for flag, value in given_answers.items():
            got = _flag_value(chosen_tokens, flag)
            assert got == value, (
                f"paso {step}: el comando ofrecido perdio o cambio una "
                f"respuesta ya dada -- {flag} era {value!r} (contestado en "
                f"un paso anterior) y el nuevo comando trae {got!r}. "
                f"Comando ofrecido: {chosen!r}.\n"
                f"Transcripcion hasta aqui: "
                + " -> ".join(f"`gitmem {' '.join(a)}` (rc={r})" for a, r, _ in transcript)
            )

        given_answers.update(_answers_in(chosen_tokens))
        current_args = chosen_tokens

    pytest.fail(
        f"la secuencia intento->rechazo->relanzamiento no convergio en "
        f"{MAX_STEPS} pasos (P5, spec-sistema-memoria-v2.md Sec.2: "
        f"'responder es relanzar el comando con la respuesta como "
        f"argumento' -- un ciclo que no cierra empuja a no guardar la "
        f"nota). Transcripcion completa:\n"
        + "\n".join(
            f"  paso {i}: `gitmem {' '.join(args)}` -> rc={rc}\n{out}"
            for i, (args, rc, out) in enumerate(transcript)
        )
    )
