"""Contrato de lib/memory/format.py -- PIEZAS.md Sec.6.4.

Ni `lib/memory/format.py` ni `lib/memory/model.py` existen todavia -- estos
cuatro tests deben fallar al importar, por diseno: es el RED del modo
test-first. Uno por fila de la tabla "Sus tests" de Sec.6.4, ni uno mas
(mismo criterio que test_emojis.py y test_vocabulary.py).

format.py es "la pareja productor<->consumidor del sistema" (Sec.6.4,
"Para que"): cada build_* tiene su parse_*, y la ley que este fichero
prueba es que el par cierra -- lo que un build_* escribe, su parse_*
tiene que poder volver a leer, siempre contra un objeto generado por el
propio test, nunca contra una cadena escrita a mano (unmassk-standards
Sec.34, y la propia tabla de Sec.6.4: "se prueba con un objeto generado,
nunca con una cadena escrita a mano").

Dos ausencias de la superficie declarada que este fichero asume y deja
dicho, porque PIEZAS.md no las cierra literalmente (mismo tipo de hueco
que FieldSpec/TypeSpec en vocabulary-contract-notes.md):

1. **`SubjectParts`** (el tipo de retorno de `parse_subject`) no aparece
   en las trece clases de `model.py` (PIEZAS Sec.5.3) ni se describe en
   ningun otro sitio. Por eso `test_emoji_after_brackets_enforced` no
   construye ni inspecciona un `SubjectParts`: solo comprueba la
   posicion del emoji en la cadena que produce `build_subject` y si
   `parse_subject` acepta/rechaza segun esa posicion (`is not None` /
   `is None`), sin asumir nombres de atributo.

2. **`Note.timestamp` no aparece como campo de texto en ninguna de las
   plantillas literales de TEXTOS.md Sec.5** (ni el `Contexto de cierre`
   de Sec.5 tiene un campo de fecha) -- PIEZAS Sec.5.3 dice que es "UTC,
   del autor del commit", es decir que su fuente de verdad es la fecha
   de autor de git, no el cuerpo del commit. `build_message`/
   `build_context_message` no tienen forma de escribir un dato que no
   esta en ninguna plantilla, y `parse_message`/`parse_context_message`
   no tienen forma de recuperarlo de un texto que nunca lo llevo. Por
   eso el helper `_assert_fields_match` deja fuera `timestamp` cuando
   compara una Note/ContextNote -- el resto, incluidos los siete tipos y
   el `⏩`, se compara entero y sin excepciones. Si esta lectura resulta
   equivocada (p.ej. porque Ultron encuentra un campo de fecha que si
   viaja en el texto), avisar: endurecer esta exclusion es una linea, no
   un rediseno del test.

**Por que `_assert_fields_match` compara campo a campo y nunca con `==`
directo sobre el objeto:** el companero en paralelo que escribio
test_zones.py (ver zones-contract-notes.md, memoria de este agente)
encontro que dos instancias de la misma clase de `model.py` cargadas por
rutas de fichero distintas -- el fixture `model` de este test frente a
lo que `format.py` use por dentro para llegar a esas mismas clases --
pueden acabar siendo clases Python DISTINTAS aunque el codigo fuente sea
identico, porque `__eq__` generado por `@dataclass` comprueba
`self.__class__ is other.__class__` primero. Comparar `==` directamente
haria que el round trip fallara incluso con una implementacion correcta.
"""

import dataclasses
from datetime import datetime, timezone

import pytest

from .conftest import import_lib_memory_module

SEVEN_TYPES = ("D", "M", "R", "Q", "X", "I", "B")

# Timestamp fijo y compartido: por el hueco 2 del docstring de arriba, su
# valor exacto no se compara en el round trip de Note/ContextNote -- solo
# hace falta que sea un datetime real para poder construir el objeto.
_FIXED_TIMESTAMP = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def fmt():
    return import_lib_memory_module("format")


@pytest.fixture
def emojis():
    return import_lib_memory_module("emojis")


def _note(model, **overrides):
    """Factoria de Note con valores por defecto neutros -- cada test override
    solo los campos que le importan."""
    fields = dict(
        type="D",
        id="D-030",
        zone1="product",
        zone2="auth",
        headline="login with JWT + Google OAuth",
        description="placeholder description",
        timestamp=_FIXED_TIMESTAMP,
        why=None,
        keys=(),
        origin=(),
        replaces=None,
        awaits=None,
        issue=None,
    )
    fields.update(overrides)
    return model.Note(**fields)


def _sample_notes(model):
    """Una Note por cada uno de los siete tipos, mas una segunda M (el acta
    de plan, TEXTOS Sec.5 "Acta de plan"), para que Origin/Issue -- los dos
    campos que solo aparece en esa variante -- tambien pasen por el round
    trip. Contenido de headline/why/keys/origin/replaces/awaits/issue
    tomado de los ejemplos literales de TEXTOS.md Sec.5 (D-030, M-044,
    R-029, Q-007, X-012, I-014, B-003, M-063); las descripciones son un
    resumen corto, no la cita completa -- el round trip prueba la
    fidelidad del formato, no que el test copie el parrafo entero.
    """
    return [
        (
            "D",
            _note(
                model,
                type="D",
                id="D-030",
                zone1="product",
                zone2="auth",
                headline="login with JWT + Google OAuth",
                description="Brainstorm de login; se opto por JWT + OAuth de Google por el multi-tenant.",
                why="sesiones no escalan multi-tenant; Google evita gestionar passwords propios",
                keys=("token", "oauth", "sso", "signin", "credentials"),
            ),
        ),
        (
            "M",
            _note(
                model,
                type="M",
                id="M-044",
                zone1="api",
                zone2="billing",
                headline="webhooks arrive out of order; dedup by event id",
                description="Stripe reintenta hasta tres dias y no garantiza el orden; dedup por event id.",
                keys=("webhook", "idempotency", "ordering", "duplicate", "retry"),
                replaces="M-019",
            ),
        ),
        (
            "R",
            _note(
                model,
                type="R",
                id="R-029",
                zone1="testing",
                zone2="billing",
                headline="no Stripe test hits the live key, ever",
                description="Los tests solo pueden ver la clave sk_test_; la clave viva no esta en ningun .env.",
                why="en mayo un test de suscripciones cobro 340 euros reales a catorce clientes",
                keys=("security", "sandbox", "apikey", "charge", "live"),
                origin=("I-011",),
            ),
        ),
        (
            "Q",
            _note(
                model,
                type="Q",
                id="Q-007",
                zone1="product",
                zone2="auth",
                headline="do we support >1 Google Workspace per tenant?",
                description="Un cliente tiene dos dominios de Workspace y quiere un solo espacio en la app.",
                why="el modelo de datos de invitaciones cambia entero segun la respuesta",
                keys=("workspace", "tenant", "invite", "domain", "multi"),
            ),
        ),
        (
            "X",
            _note(
                model,
                type="X",
                id="X-012",
                zone1="product",
                zone2="auth",
                headline="server-side sessions",
                description="Alternativa perdedora de D-030; descartada por el coste de infraestructura.",
                why="no escalan multi-tenant sin un almacen compartido que aun no tenemos",
                keys=("session", "cookie", "redis", "sticky"),
                origin=("D-030",),
            ),
        ),
        (
            "I",
            _note(
                model,
                type="I",
                id="I-014",
                zone1="testing",
                zone2="auth",
                headline="seeds wiped the production users table",
                description="El script de seeds hacia TRUNCATE contra produccion en CI. Fix en #58.",
                why="se perdieron 1200 sesiones y 40 minutos de altas",
                keys=("seeds", "database", "truncate", "env", "ci"),
            ),
        ),
        (
            "B",
            _note(
                model,
                type="B",
                id="B-003",
                zone1="product",
                zone2="auth",
                headline="google workspace admin consent still pending",
                description="El alta masiva necesita que un admin de Workspace apruebe el scope readonly.",
                awaits="el cliente -- Marta, IT de Omawa",
                keys=("consent", "admin", "workspace", "oauth", "scope"),
            ),
        ),
        (
            "M-acta",
            _note(
                model,
                type="M",
                id="M-063",
                zone1="product",
                zone2="auth",
                headline="login rollout plan",
                description="Plan de ejecucion de D-030 en docs/plan-login.md; issue #52 aloja el checklist.",
                keys=("rollout", "milestone", "checklist"),
                origin=("D-030",),
                issue=52,
            ),
        ),
    ]


def _assert_fields_match(parsed, expected, exclude=()):
    """Compara campo a campo, nunca con `==` directo sobre el objeto.

    Dos dataclasses cargadas por rutas de fichero distintas (la del
    fixture `model` del test vs. la que use `format.py` por dentro para
    referirse a las mismas clases de model.py) pueden acabar siendo
    clases Python DISTINTAS aunque el codigo fuente sea identico --
    `__eq__` generado por `@dataclass` comprueba `self.__class__ is
    other.__class__` primero y devuelve `False` pase lo que pase con los
    campos. Regla establecida por el companero en paralelo que escribio
    test_zones.py (mismo hallazgo con `model.Zone`, ver
    zones-contract-notes.md en la memoria de este agente) -- se aplica
    aqui igual porque format.py depende de las mismas clases de model.py.

    `exclude` deja fuera `timestamp` en las comparaciones de
    Note/ContextNote -- ver hueco 2 del docstring del modulo.
    """
    assert parsed is not None
    for field in dataclasses.fields(expected):
        if field.name in exclude:
            continue
        parsed_value = getattr(parsed, field.name)
        expected_value = getattr(expected, field.name)
        assert parsed_value == expected_value, (
            f"campo {field.name!r} no sobrevivio al round trip: "
            f"{parsed_value!r} != {expected_value!r}"
        )


def test_round_trip_seven_types_and_context(model, fmt):
    """Fila 1: construir -> serializar -> volver a parsear -> objeto
    identico al de partida, para los siete tipos y para el `[NEXT]` de
    contexto. Nunca contra una cadena escrita a mano.

    Fallo real que previene: que el sistema escriba algo que el mismo no
    sabe volver a leer -- memoria escrita e invisible, sin un solo error
    por pantalla.
    """
    for label, note in _sample_notes(model):
        built = fmt.build_message(note)
        parsed = fmt.parse_message(built)
        _assert_fields_match(parsed, note, exclude={"timestamp"})
        assert note.type in SEVEN_TYPES, f"tipo fuera del vocabulario para {label}"

    ctx = model.ContextNote(
        headline="implement discussed changes to close-session skill",
        context=(
            "Revisado el diseno del checkpoint: muere el automatico, lo hace "
            "close-session. Punto de inflexion: fuera comodines -- toda nota "
            "lleva dos zonas reales. Decidido de palabra: los planes viven en "
            "docs/ como plan-*.md. Quedo en el aire el alcance de "
            "facturacion; hablar antes de empezar."
        ),
        keys=("close-session", "checkpoint", "plan"),
        timestamp=_FIXED_TIMESTAMP,
    )
    built_ctx = fmt.build_context_message(ctx)
    parsed_ctx = fmt.parse_context_message(built_ctx)
    _assert_fields_match(parsed_ctx, ctx, exclude={"timestamp"})


def test_round_trip_index_line_and_three_archive_forms(model, fmt):
    """Fila 2: ida y vuelta de la linea de indice y de las tres formas de
    linea de archivo (`replaced by` / `closed:` / `promoted to`).

    Fallo real que previene: un `→ promoted to X-030` que el parser no
    reconoce y desaparece del informe sin avisar.
    """
    note = _note(
        model,
        type="D",
        id="D-036",
        zone1="product",
        zone2="auth",
        headline="session lifetime is 7 days",
        description="Decision original sobre la duracion de sesion, luego sustituida por D-041.",
    )

    index_line_text = fmt.build_index_line(note)
    parsed_index_line = fmt.parse_index_line(index_line_text)
    expected_index_line = model.IndexLine(
        id=note.id, zone1=note.zone1, zone2=note.zone2, headline=note.headline
    )
    _assert_fields_match(parsed_index_line, expected_index_line)

    # Los tres destinos literales de TEXTOS Sec.4: "replaced by <ID>" ·
    # "closed: <motivo>" · "promoted to <ID>".
    archive_cases = (
        ("replaced", "D-041"),
        ("closed", "arreglado en #58 y con muro puesto (R-018)"),
        ("promoted", "X-030"),
    )
    for destination, detail in archive_cases:
        archive_line_text = fmt.build_archive_line(note, destination, detail)
        parsed_archive_line = fmt.parse_archive_line(archive_line_text)
        expected_archive_line = model.ArchiveLine(
            date=note.timestamp.date(),
            type=note.type,
            id=note.id,
            zone1=note.zone1,
            zone2=note.zone2,
            headline=note.headline,
            destination=destination,
            destination_detail=detail,
        )
        _assert_fields_match(parsed_archive_line, expected_archive_line)


def test_corrupt_line_returns_none_without_raising(fmt):
    """Fila 3: una linea corrupta devuelve `None` y no lanza -- en los
    cinco parsers de la superficie, no solo uno.

    Fallo real que previene: un fichero editado a mano tumba el arranque
    en vez de reportar una incoherencia.
    """
    garbage_by_parser = {
        "parse_subject": "this is not a valid subject line at all",
        "parse_message": "random text\n\nno structure here, just prose",
        "parse_index_line": "not an index line, just some words",
        "parse_archive_line": "2026-13-99 not a real archive line shape",
        "parse_context_message": "random text without the arrow marker",
    }
    for parser_name, garbage in garbage_by_parser.items():
        parser = getattr(fmt, parser_name)
        result = parser(garbage)
        assert result is None, f"{parser_name} deberia devolver None ante una linea corrupta"


def test_emoji_after_brackets_enforced(model, fmt, emojis):
    """Fila 4: el emoji va DESPUES de los corchetes (TEXTOS Sec.6, punto 8:
    correccion expresa del propietario, 2026-08-02), y el parser lo exige
    ahi.

    Fallo real que previene: dos formatos conviviendo, que es como se
    pierde la mitad de la historia.
    """
    note = _note(
        model,
        type="D",
        id="D-030",
        zone1="product",
        zone2="auth",
        headline="login with JWT + Google OAuth",
    )
    subject = fmt.build_subject(note)
    type_emoji = emojis.TYPE_EMOJI[note.type]

    # El emoji aparece DESPUES del ultimo corchete de cierre, nunca antes.
    assert subject.index(type_emoji) > subject.rindex("]")

    # El formato bien construido se parsea sin problema.
    assert fmt.parse_subject(subject) is not None

    # El formato viejo -- emoji ANTES de los corchetes -- lo rechaza.
    old_format_subject = (
        f"{type_emoji} [{note.id}][{note.zone1}][{note.zone2}] {note.headline}"
    )
    assert fmt.parse_subject(old_format_subject) is None


# ---------------------------------------------------------------------------
# Regresion permanente de cinco fallos de ida y vuelta, encontrados y
# arreglados el 2026-08-02 (verificados EJECUTANDO, no leyendo). Cada uno
# nombra en su docstring que hacia el sistema ANTES del arreglo, no una
# regla de diseno -- para que quien lo lea dentro de un ano entienda por
# que existe y no lo borre por parecer redundante.
#
# Confirmado en vivo, antes de escribir estos cuatro tests, que cada uno
# se pone rojo sin su arreglo concreto: copia de model.py/format.py a un
# directorio temporal del scratchpad de sesion, deshecho ahi solo el
# mecanismo puntual de cada bug (nunca lib/memory/ real), y una version
# minima -- sin pytest, aserciones planas -- de cada round trip contra esa
# copia rota. Los cuatro devolvieron exactamente el sintoma descrito
# (None / division incorrecta) contra la copia rota, y el resultado
# correcto contra el codigo real. La propiedad que prueban los cuatro es
# siempre la misma: lo que entra vuelve identico, contenga lo que
# contenga.
# ---------------------------------------------------------------------------


def test_regression_headline_with_embedded_newline_round_trips_whole_note(model, fmt):
    """REGRESION (arreglado 2026-08-02): un titular con un salto de linea
    propio se escribia sin problema pero, al releerlo, `parse_message`
    devolvia `None` -- la nota entera desaparecia, sin un solo error en
    pantalla. El arreglo (folding del titular en
    `build_subject`/`parse_subject`, mas el bucle de continuacion en
    `parse_message`) hace que un titular con `\\n` sobreviva el round
    trip igual que uno de una sola linea.

    Confirmado en vivo contra una copia con el folding deshecho (scratchpad
    de esta sesion, `mutcheck/bug1_headline_newline/`): `parse_message`
    devolvia `None` con ese arreglo desecho; con el codigo real, no.
    """
    note = _note(
        model,
        headline="rename colors.py\nto emojis.py per new naming convention",
    )
    built = fmt.build_message(note)
    parsed = fmt.parse_message(built)
    assert parsed is not None, "la nota desaparecio: parse_message devolvio None"
    _assert_fields_match(parsed, note, exclude={"timestamp"})


def test_regression_context_with_embedded_newline_round_trips_whole_context(model, fmt):
    """REGRESION (arreglado 2026-08-02, adaptada 2026-08-03 al contexto en
    prosa): un contexto de cierre con un salto de linea propio no se
    releia como continuacion del mismo campo -- se perdia el cierre de
    sesion COMPLETO (`parse_context_message` devolvia `None` ante
    cualquier linea que no empezara literalmente por el campo conocido).
    El folding de `Context:` en `build_context_message` (misma mecanica
    que `Why:`/`Description:` de una nota), mas el manejo de continuacion
    en `parse_context_message`, hace que un contexto con `\\n` sobreviva
    sin tumbar el resto del cierre.

    Adaptada al formato nuevo [decision del propietario, 2026-08-03,
    COLA.md Sec.5]: el contexto ya no es una lista de puntos con `- `,
    es una unica cadena en prosa (`ContextNote.context`) que puede traer
    saltos de linea propios.
    """
    ctx = model.ContextNote(
        headline="close session",
        context=(
            "first paragraph line, single line\n"
            "second paragraph line, with an embedded newline of its own\n"
            "third paragraph line, single line"
        ),
        keys=("a", "b"),
        timestamp=_FIXED_TIMESTAMP,
    )
    built = fmt.build_context_message(ctx)
    parsed = fmt.parse_context_message(built)
    assert parsed is not None, "el cierre de sesion entero desaparecio"
    _assert_fields_match(parsed, ctx, exclude={"timestamp"})


def test_regression_headline_containing_arrow_separator_round_trips_archive_line(model, fmt):
    """REGRESION (arreglado 2026-08-02): un titular que contuviera
    literalmente el separador `  ->  ` (simbolo de uso habitual en la
    prosa de este proyecto, p.ej. "rename colors.py  ->  emojis.py")
    hacia que `parse_archive_line` casara con la PRIMERA aparicion del
    separador en vez de con la real -- la linea del archivo se
    descartaba al releer (`parse_archive_line` devolvia `None`). El
    arreglo exige que lo que sigue al separador empiece por uno de los
    tres destinos literales del vocabulario cerrado (`replaced by ` /
    `closed: ` / `promoted to `), asi que una aparicion del separador
    DENTRO del propio titular ya no se confunde con la real.

    Confirmado en vivo contra una copia con esa exigencia deshecha
    (scratchpad de esta sesion, `mutcheck/bug3_headline_arrow/`, regex
    con headline no goloso en vez de exigir el vocabulario): la linea se
    descartaba con ese arreglo desecho; con el codigo real, no.
    """
    note = _note(
        model,
        id="D-036",
        headline="rename colors.py  →  emojis.py per new naming convention",
    )
    built = fmt.build_archive_line(note, "closed", "superseded by the rename")
    parsed = fmt.parse_archive_line(built)
    assert parsed is not None, "la linea de archivo desaparecio"
    expected = model.ArchiveLine(
        date=note.timestamp.date(),
        type=note.type,
        id=note.id,
        zone1=note.zone1,
        zone2=note.zone2,
        headline=note.headline,
        destination="closed",
        destination_detail="superseded by the rename",
    )
    _assert_fields_match(parsed, expected)


def test_regression_key_and_origin_with_embedded_comma_space_do_not_split_into_extra_entries(model, fmt):
    """REGRESION (arreglado 2026-08-02): una key o un origen que trajera
    literalmente `", "` dentro (p.ej. la key "a, b") volvia partido en
    entradas de mas al releer -- `("a, b", "c")` volvia como tres
    elementos en vez de dos. El arreglo (`_encode_list`/`_decode_list`,
    que escapan `\\` y `,` caracter a caracter en vez de un
    `", ".join()`/`.split(", ")` sin escapar) hace que un item con `", "`
    dentro sobreviva entero.

    Confirmado en vivo contra una copia con el escapado deshecho
    (scratchpad de esta sesion, `mutcheck/bug4_list_comma/`, join/split
    sin escapar): `("a, b", "c")` volvia como `("a", "b", "c")` con ese
    arreglo desecho; con el codigo real, vuelve identico.
    """
    note = _note(
        model,
        keys=("a, b", "c"),
        origin=("D-030, D-031", "M-002"),
    )
    built = fmt.build_message(note)
    parsed = fmt.parse_message(built)
    assert parsed is not None
    assert parsed.keys == ("a, b", "c"), f"keys volvio partido: {parsed.keys!r}"
    assert parsed.origin == ("D-030, D-031", "M-002"), f"origin volvio partido: {parsed.origin!r}"
    _assert_fields_match(parsed, note, exclude={"timestamp"})


def test_regression_keys_origin_replaces_with_embedded_newline_round_trip_note(model, fmt):
    """REGRESION (arreglado 2026-08-02, encontrado por Moriarty -- capa 1):
    `Keys`, `Origin` y `Replaces` se escribian en crudo en
    `_body_field_line` (`f"Keys: {_encode_list(note.keys)}"` directo, sin
    pasar por `_fold`) mientras `Why`, `Awaits` y `Description` ya iban
    protegidos con `_fold`. Una key (o un origen, o un `replaces`) con un
    salto de linea propio quedaba como una linea de cuerpo cruda que no
    empezaba por espacio de continuacion ni por ningun campo conocido --
    `_parse_body_fields` la rechazaba y `parse_message` devolvia `None`
    SIN excepcion: la nota entera desaparecia al releerla, no solo el
    campo. El arreglo pliega los tres igual que los demas campos de texto
    libre (`_fold("Keys", ...)` / `_fold("Origin", ...)` /
    `_fold("Replaces", ...)`), asi que un salto de linea interno en
    cualquiera de los tres sobrevive el round trip identico al resto.

    Confirmado en vivo contra una copia con el plegado deshecho para estos
    tres campos (scratchpad de esta sesion,
    `dante_bug_regressions_20260802/format_bug/`, `_body_field_line`
    vuelto a un f-string crudo sin `_fold` para Keys/Origin/Replaces):
    `parse_message` devolvia `None` (nota entera perdida) con ese arreglo
    desecho; con el codigo real, la nota vuelve identica.
    """
    note = _note(
        model,
        keys=("token", "multi-line key\nwith an embedded newline"),
        origin=("D-030", "another origin\nwith its own newline"),
        replaces="M-019\nwith a continuation line of its own",
    )
    built = fmt.build_message(note)
    parsed = fmt.parse_message(built)
    assert parsed is not None, "la nota entera desaparecio: parse_message devolvio None"
    _assert_fields_match(parsed, note, exclude={"timestamp"})
