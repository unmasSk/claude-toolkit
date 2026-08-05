"""Contrato de lib/memory/rejection.py -- PIEZAS.md Sec.7.4.

rejection.py existe -- los tres tests de contrato de abajo (uno por fila
de la tabla "Sus tests" de Sec.7.4) ya estan en verde:

  1. Los diez rechazos llevan los tres elementos: que ha pasado, las
     opciones, y el comando exacto de relanzamiento.
  2. El comando de relanzamiento es ejecutable tal cual, sin editar.
  3. Los dos renderizados (`render_terminal`, `render_hook_block`)
     llevan el mismo contenido.

Un CUARTO test, anadido despues como REGRESION (no una fila nueva de la
tabla de contrato -- ver su propio docstring,
`test_build_fails_loud_when_a_part_carries_no_value`), cubre un agujero
real que las tres filas de arriba no cazaban: `build()` comprueba que
`what`/`options`/`command` ESTEN, nunca que TRAIGAN algo -- un part
vacio produce un texto mutilado en silencio en vez de fallar. Ese test
esta en rojo por su causa real; los otros tres siguen en verde.

El fixture `rejection` importa por ruta de fichero
(`import_lib_memory_module`, ver conftest.py) para que cada test falle
individualmente con la causa real (`FileNotFoundError`:
lib/memory/rejection.py no existe todavia), en vez de un unico error de
coleccion para todo el fichero -- mismo patron que test_emojis.py y
test_vocabulary.py.

LOS DIEZ RECHAZOS son las secciones de TEXTOS.md Sec.1 que SI son un
rechazo: 1.1 a 1.7 y 1.9 a 1.11. La 1.8 (key marcadora mal escrita)
queda fuera a proposito -- TEXTOS.md la titula literalmente "no es
rechazo, es aviso al guardar", y PIEZAS.md Sec.7.5 lo confirma: "la key
mal escrita no es un rechazo... si se quiere rechazo de verdad, la
mecanica cambia". Nueve mas uno son diez rechazos de verdad.

ASUNCION DE NOMBRES (disclosed, PIEZAS.md Sec.7.4 no los fija -- a
diferencia de vocabulary.py Sec.6.1, que si fijo `FieldSpec`/`TypeSpec`
literalmente): la firma da `build(kind: str, **parts) -> Rejection` sin
nombrar los kwargs de `**parts`. Se asume que acepta tres: `what` (que
ha pasado, str), `options` (las opciones, tuple de str) y `command`
(el/los comandos de relanzamiento, **tuple** de str y no un str suelto
-- el rechazo 1.10 de TEXTOS Sec.1 muestra DOS comandos de relanzamiento
validos segun la rama de la respuesta -- "no" cierra sin mas, "new"
abre una restriction --, y una tupla de longitud 1 cubre el resto de
los nueve sin caso especial). Si Ultron elige otros nombres, la fila 1
falla con un `TypeError` nombrando el kwarg que falta -- rojo hablador,
no mudo (mismo patron ya usado en vocabulary-contract-notes.md para
`FieldSpec.reader`).

DATOS DE ENTRADA SINTETICOS, no copiados de TEXTOS.md: cada uno de los
diez casos usa contenido MARCADO y unico por caso (nunca el texto
literal de TEXTOS.md) porque el encargo es explicito -- "no copies el
texto esperado de TEXTOS.md a tu test y compares cadenas. Eso prueba
que sabes copiar." Los tres tests prueban PROPIEDADES: que lo que se le
da a `build()` sobrevive intacto en el render (en las dos salidas), no
que el render coincide con una cadena tecleada a mano. Los comandos de
relanzamiento son ademas sintaxis de shell realista y con comillas
internas (simples, dobles, dobles escapadas) -- validado con
`shlex.split()` antes de escribir este fichero -- para que la fila 2
tenga algo de verdad que romper.

No se toca produccion: si `lib/memory/rejection.py` no existe, estos
tests se quedan en rojo tal cual estan -- eso es lo esperado.
"""

import shlex

import pytest

from .conftest import import_lib_memory_module

# Los diez rechazos: (kind, what, options, command).
#   kind    -- identificador libre (PIEZAS.md Sec.7.4 no fija un enum;
#              spec-sistema-memoria-v2.md Sec.6 lista las nueve
#              validaciones de la aduana en prosa, nunca como claves).
#   what    -- que ha pasado, marcado y unico por caso.
#   options -- tuple de las opciones que TEXTOS.md Sec.1 ofrece en esa
#              seccion (una o mas -- "opciones" no exige plural en
#              cuenta, exige presencia).
#   command -- tuple de 1 o 2 comandos de relanzamiento ejecutables tal
#              cual (con comillas reales, no el placeholder "..." de
#              TEXTOS.md, que no es sintacticamente un comando).
TEN_REJECTIONS = (
    (
        "zone_not_found",  # TEXTOS Sec.1.1
        "MARK_ZONE_NOT_FOUND: la zona 'facturacion' no existe en zones.json",
        (
            "MARK_ZONE_NOT_FOUND_OPT_1: relanza con 'billing' si es esa",
            "MARK_ZONE_NOT_FOUND_OPT_2: relanza con 'invoices' si es esa",
        ),
        (
            'gitmem note D --zones product billing "friction on renewal" '
            "--why 'shortens the support cycle' "
            '--description "customer facing rollout, needs a decision"',
        ),
    ),
    (
        "zone_blacklisted",  # TEXTOS Sec.1.2
        "MARK_ZONE_BLACKLISTED: 'session' no es memoria del proyecto",
        (
            "MARK_ZONE_BLACKLISTED_OPT_1: si es conducta, usa gitmem rule",
            "MARK_ZONE_BLACKLISTED_OPT_2: si es producto, dale su zona real",
        ),
        ('gitmem rule "never commit generated snapshots to the repo"',),
    ),
    (
        "ambiguous_word",  # TEXTOS Sec.1.3
        "MARK_AMBIGUOUS_WORD: 'audit' significa dos cosas distintas",
        (
            "MARK_AMBIGUOUS_WORD_OPT_1: registro (zona2), el modulo que audita",
            "MARK_AMBIGUOUS_WORD_OPT_2: codeaudit (zona1), las auditorias de agentes",
        ),
        (
            'gitmem note M --zones product registro "adds a tamper log" '
            '--description "every write now appends an audit row"',
        ),
    ),
    (
        "no_type_fits",  # TEXTOS Sec.1.4
        "MARK_NO_TYPE_FITS: no se sabe que tipo es esto",
        (
            "MARK_NO_TYPE_FITS_OPT_1: partela en dos notas",
            "MARK_NO_TYPE_FITS_OPT_2: elige un tipo de D/M/R/Q/X/I/B",
        ),
        (
            'gitmem note M --zones deploy logging "log rotation switched to journald" '
            '--description "no more logrotate cron entries"',
        ),
    ),
    (
        "missing_pain_answer",  # TEXTOS Sec.1.5
        "MARK_MISSING_PAIN_ANSWER: falta la respuesta a la pregunta del dolor",
        (
            "MARK_MISSING_PAIN_ANSWER_OPT_1: si, es un muro, entra como R",
            "MARK_MISSING_PAIN_ANSWER_OPT_2: no, es un hecho, entra como M",
        ),
        (
            'gitmem note R --zones database backups '
            '"nightly dump must run before 03:00 UTC" '
            '--why "the vendor\'s window closes at 03:00" '
            '--description "backup job" --stops yes',
        ),
    ),
    (
        "overlaps_existing",  # TEXTOS Sec.1.6
        "MARK_OVERLAPS_EXISTING: esto pisa a algo ya escrito en [product][auth]",
        (
            "MARK_OVERLAPS_EXISTING_OPT_1: la sustituye, --replaces D-030",
            "MARK_OVERLAPS_EXISTING_OPT_2: conviven, --replaces none",
            "MARK_OVERLAPS_EXISTING_OPT_3: es duplicado, no la guardes",
        ),
        (
            'gitmem note D --zones product auth --why "adds device fingerprinting" '
            '--description "extra signal on login" --replaces D-030',
        ),
    ),
    (
        "distillation_without_sources",  # TEXTOS Sec.1.7
        "MARK_DISTILLATION_WITHOUT_SOURCES: una destilacion sin fuentes no es destilacion",
        ("MARK_DISTILLATION_WITHOUT_SOURCES_OPT_1: pon los hashes v1 separados por comas",),
        (
            'gitmem note M --zones testing amianto '
            '"three retries absorb the flaky runner" '
            '--description "ci stabilization" --origin 4f2a1bc,9de77a0,c31b8e5',
        ),
    ),
    (
        "issue_not_found",  # TEXTOS Sec.1.9
        "MARK_ISSUE_NOT_FOUND: la issue #47 no existe en este repo",
        (
            "MARK_ISSUE_NOT_FOUND_OPT_1: gh issue list --limit 20",
            "MARK_ISSUE_NOT_FOUND_OPT_2: gh issue create --title ...",
        ),
        (
            'gitmem note M --zones product auth '
            '"login rollout plan, aka \\"legacy cutover\\"" '
            '--description "phased rollout" --origin D-030 --issue 52',
        ),
    ),
    (
        "incident_close_needs_restriction_answer",  # TEXTOS Sec.1.10
        "MARK_INCIDENT_CLOSE: I-014 no se cierra sin contestar si sale muro",
        (
            "MARK_INCIDENT_CLOSE_OPT_1: no, se cierra sin mas",
            "MARK_INCIDENT_CLOSE_OPT_2: new, nace una restriction en la misma zona",
        ),
        # [corregido 2026-08-04: decia "gitmem close I-014 ..." en las dos
        # lineas de abajo -- `close` se renombro a `remove` el 2026-08-04
        # (DEUDA.md B4) y este fichero nunca lo noto, porque este test NO
        # ejecuta el comando ni lo compara contra los subcomandos reales
        # de `bin/gitmem` -- se lo inventa el, lo mete en `rejection_.build()`
        # y solo comprueba que sale impreso donde toca en el maquetado. Por
        # eso un comando muerto sobrevivio aqui mas de un dia con la suite
        # en verde. Sigue teniendo valor PARA LO SUYO (maquetado del
        # rechazo: que el what/options/command salgan los tres, en los dos
        # renders) -- lo que NO comprueba, y nunca comprobo, es que el
        # comando sea uno real y ejecutable; eso lo hace
        # test_rejection_relaunch_commands.py, que extrae el comando real
        # del AST de validator.py y lo cruza contra el argparse real de
        # remove.py. El texto de abajo ahora coincide con el que
        # `lib/memory/validator.py::validate_incident_close_question`
        # ofrece de verdad.]
        (
            'gitmem remove I-014 "seeds fixed to never read the DB url from env" '
            "--restriction no",
            'gitmem remove I-014 "seeds fixed" --restriction new '
            '--restriction-text "seeds never read the DB url from the environment" '
            '--why "the CI runner had a production DB url in that variable"',
        ),
    ),
    (
        "headline_too_long",  # TEXTOS Sec.1.11
        "MARK_HEADLINE_TOO_LONG: el titular tiene 96 caracteres y el tope son 80",
        (
            "MARK_HEADLINE_TOO_LONG_OPT_1: acortalo, el detalle va a Description",
            "MARK_HEADLINE_TOO_LONG_OPT_2: partelo en dos notas si dice dos cosas",
        ),
        (
            'gitmem note R --zones database backups '
            '"restore script must never target the production database" '
            '--why "readability" --description "..." --stops yes',
        ),
    ),
)

# Verificado antes de escribir este fichero (shlex.split() sobre las
# once cadenas de comando -- diez casos, uno con dos comandos --, cero
# ValueError): las comillas internas (simples, dobles, dobles escapadas
# con \\") son sintaxis de shell valida tal como estan. Este test no
# repite esa verificacion en cada corrida (no es responsabilidad de
# rejection.py que shlex acepte MI fixture) -- la deja escrita aqui como
# nota de disenio; lo que SI prueban los tests de abajo es que build()
# y los dos render_* no tocan un solo caracter de estas cadenas.


@pytest.fixture
def rejection():
    return import_lib_memory_module("rejection")


def _assert_content_present(text, kind, what, options, commands):
    """Verifica que `text` contiene los tres elementos del caso `kind`.

    Helper compartido entre la fila 1 y la fila 3 -- ambas comprueban
    "los tres elementos estan", solo que sobre renders distintos.
    """
    assert what in text, (
        f"[{kind}] falta 'que ha pasado' en el render: no aparece {what!r}"
    )
    for option in options:
        assert option in text, (
            f"[{kind}] falta una opcion en el render: no aparece {option!r}"
        )
    for command in commands:
        assert command in text, (
            f"[{kind}] falta el comando de relanzamiento en el render "
            f"(o llego editado): no aparece {command!r}"
        )


def test_all_ten_rejections_carry_what_options_and_relaunch_command(rejection):
    """Fila 1: los diez rechazos llevan los tres elementos -- que ha
    pasado, las opciones, el comando exacto de relanzamiento.

    Fallo real que previene: un rechazo que solo dice "no valido" obliga
    a adivinar, y lo que se acaba haciendo es esquivarlo en vez de
    contestarlo.
    """
    for kind, what, options, commands in TEN_REJECTIONS:
        r = rejection.build(kind, what=what, options=options, command=commands)
        rendered = rejection.render_terminal(r)
        _assert_content_present(rendered, kind, what, options, commands)


def test_relaunch_command_survives_render_byte_for_byte(rejection):
    """Fila 2: el comando de relanzamiento es ejecutable tal cual, sin
    editar.

    Fallo real que previene: copiar, pegar, y que falle otra vez por una
    comilla -- si el render tocase un solo caracter de un comando ya
    valido (comillas simples/dobles/escapadas incluidas), la subcadena
    exacta dejaria de aparecer en el texto y este assert lo cazaria.
    """
    for kind, what, options, commands in TEN_REJECTIONS:
        for command in commands:
            # Las cadenas de entrada ya se validaron con shlex.split()
            # al escribir este fichero (ver comentario junto a
            # TEN_REJECTIONS) -- lo que prueba este test es que
            # SOBREVIVEN intactas al pasar por build()+render(), no que
            # sean shell valido (eso ya se sabe).
            assert shlex.split(command), (
                f"[{kind}] el comando de entrada no es sintaxis de shell "
                f"valida -- fixture del test roto, no produccion: {command!r}"
            )

        r = rejection.build(kind, what=what, options=options, command=commands)
        rendered_terminal = rejection.render_terminal(r)
        rendered_hook_block = rejection.render_hook_block(r)

        for command in commands:
            assert command in rendered_terminal, (
                f"[{kind}] el comando llego editado al render de terminal: "
                f"no aparece {command!r} tal cual"
            )
            assert command in rendered_hook_block, (
                f"[{kind}] el comando llego editado al bloqueo del hook: "
                f"no aparece {command!r} tal cual"
            )


def test_terminal_and_hook_block_renders_carry_the_same_content(rejection):
    """Fila 3: los dos renderizados llevan el mismo contenido.

    Fallo real que previene: que la aduana diga una cosa y el generador
    otra -- mismo objeto, dos renderizados (uno para terminal, uno para
    el bloqueo del hook); si fueran dos textos, se separarian.
    """
    for kind, what, options, commands in TEN_REJECTIONS:
        r = rejection.build(kind, what=what, options=options, command=commands)
        rendered_terminal = rejection.render_terminal(r)
        rendered_hook_block = rejection.render_hook_block(r)

        _assert_content_present(rendered_terminal, kind, what, options, commands)
        _assert_content_present(rendered_hook_block, kind, what, options, commands)


@pytest.mark.parametrize("empty_field", ["what", "options", "command"])
def test_build_fails_loud_when_a_part_carries_no_value(rejection, empty_field):
    """Regresion (confirmada 2026-08-02, no una de las tres filas de
    arriba): `build()` solo comprueba que las tres claves ESTEN
    (`_EXPECTED_PARTS - set(parts)`, linea 68), nunca que TRAIGAN algo.

    Confirmado ejecutandolo antes de escribir este test:
    `build("k", what="ALGO PASO", options=("opcion A",), command=())`
    no lanza nada, y `render_terminal()` devuelve el texto SIN la
    seccion "Relanza:" -- desaparece entera y en silencio (`_render()`,
    linea 90, hace `if r.relaunch:` y si viene vacio no pinta nada). Lo
    mismo con `options=()` (se esfuma el bloque de opciones, `r.body`
    queda como cadena vacia) y con `what=""` (el titular sale en
    blanco, `⛔ ` sin nada detras).

    PIEZAS.md Sec.7.4 declara que los diez rechazos comparten "la misma
    anatomia -- que ha pasado, las opciones, y el comando exacto para
    relanzar" y que "un rechazo que solo dice 'no valido' obliga a
    adivinar" -- la fila 1 de la tabla de tests ya lo exige, pero lo
    comprueba sobre rechazos bien construidos (`TEN_REJECTIONS` arriba),
    asi que este agujero se le escapa. La especificacion Sec.2
    (principio P5) va mas lejos: "responder a la aduana ES relanzar el
    comando" -- un rechazo sin comando de relanzamiento deja al usuario
    bloqueado sin salida.

    Fallo real que previene: construir un rechazo al que le falte
    cualquiera de los tres elementos debe fallar EN ALTO -- mismo
    patron que `build()` ya usa para una key ausente o desconocida
    (`TypeError`, lineas 64-72) --, no producir un texto mutilado que el
    usuario lee como si estuviera completo.
    """
    parts = {
        "what": "MARK_REGRESSION_WHAT: algo paso de verdad en este caso",
        "options": ("MARK_REGRESSION_OPT: una opcion real",),
        "command": ("MARK_REGRESSION_CMD: gitmem note D --zones product x",),
    }
    parts[empty_field] = "" if empty_field == "what" else ()

    with pytest.raises((TypeError, ValueError)):
        rejection.build("regression_empty_part", **parts)
