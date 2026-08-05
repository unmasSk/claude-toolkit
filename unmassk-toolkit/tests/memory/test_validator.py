"""Contrato de lib/memory/validator.py -- PIEZAS.md Sec.7.5.

validator.py NO EXISTE TODAVIA. Estos ocho tests deben fallar al
importar, por diseno -- es el ROJO del modo test-first. Uno por fila de
la tabla "Sus tests" de Sec.7.5, ni uno mas. (`model.py` y `config.py`,
de los que salen `Note`/`Zone`/`Config`, ya existen en producción --
trabajo paralelo de otro agente durante esta misma sesión -- pero eso es
irrelevante para el rojo de este fichero: `validator` se pide antes que
`model`/`config` en la firma de cada test, así que el fallo reportado
sigue siendo `FileNotFoundError` sobre `validator.py`, nunca sobre sus
dependencias.)

  1. Un titular de 81 caracteres rebota, y el rechazo dice el tope.
  2. Una M sin respuesta a la pregunta del dolor rebota con la pregunta
     literal dentro.
  3. Un "si" a la pregunta del dolor en una M dice "entonces es una R".
  4. Una nota parecida sin --replaces rebota con las candidatas
     completas dentro.
  5. Un campo que no existe para ese tipo rebota.
  6. Una destilacion sin fuentes rebota.
  7. El wip no recibe ni una sola pregunta.
  8. Mismos datos -> mismo veredicto, siempre.

El fixture `validator` importa por ruta de fichero
(`import_lib_memory_module`, ver conftest.py) para que cada test falle
individualmente con la causa real (`FileNotFoundError`:
lib/memory/validator.py no existe todavia), en vez de un unico error de
coleccion para todo el fichero -- mismo patron que test_emojis.py,
test_config.py, test_zones.py y test_similar.py. En cada test, el
fixture `validator` se pide ANTES que `model`/`config` en la firma, para
que sea ESE fallo (validator.py, la pieza de este contrato) y no el de
sus dependencias (tambien inexistentes) el que se reporte primero --
mismo patron que test_zones.py y test_similar.py.

EL VALIDADOR ES PURO (PIEZAS.md Sec.7.5): "Que Context sea un dato
pasado desde fuera es la decision estructural de esta pieza... Por eso
se puede probar entero sin que exista un solo commit". Ningun test de
este fichero usa `tmp_repo`, `run_git` ni ningun otro helper de git del
conftest -- si algun dia hiciera falta un repositorio para probar una
regla del validador, eso seria la senal de que algo esta mal (el propio
encargo de esta tarea lo dice explicitamente), y el test que lo pidiera
estaria mal disenado, no el validador.

DATOS REALES, NO FABRICADOS, donde ya existen: `vocabulary.py` YA
EXISTE en produccion (Capa 1, Sec.6.1) y expone `HEADLINE_MAX` (=80),
`PAIN_QUESTION` (el texto literal de la pregunta del dolor) y `TYPES`
(la tabla de campos obligatorios/permitidos por tipo). Estos tests los
IMPORTAN de ahi en vez de tecleerlos de nuevo -- son las mismas
constantes que Sec.6.1 fija como "una sola copia en todo el sistema", y
copiarlas a mano en este fichero recrearia exactamente el problema que
esa pieza existe para evitar (dos verdades el primer dia).

ASUNCIONES DE FIRMA, DISCLOSED (PIEZAS.md Sec.7.5 solo fija la firma
completa de `Context` y de `validate_note(note: Note, ctx: Context) ->
tuple[Rejection, ...]`; las diez funciones internas se citan con `(...)`
-- argumentos sin fijar. Mismo patron ya usado en
rejection-contract-notes.md para `build(kind, **parts)`: si Ultron elige
otros nombres o tipos, el test que dependa de esa firma falla con un
`TypeError`/`AttributeError` nombrando exactamente lo que no caso --
rojo hablador, no mudo):

  - `validate_headline(headline: str) -> Rejection | None` -- fila 1
    solo habla de longitud, no hace falta mas que el titular suelto.

  - `validate_pain_question(note: Note, stops: str | None) -> Rejection
    | None` -- filas 2 y 3. "stops" (los valores CLI literales "yes"/
    "no" de TEXTOS.md Sec.1.5: "--stops no" / "--stops yes") NO es un
    campo de `Note` (PIEZAS.md Sec.5.3 fija los trece campos de `Note`
    y "stops" no es uno de ellos -- ni falta que le hace: una vez
    contestada, la respuesta ES el tipo, D/M/R no llevan un campo aparte
    que la repita). Por eso la pregunta solo puede hacerse ANTES de que
    exista una `Note` definitiva, con la respuesta como dato aparte que
    trae quien llama -- exactamente el mismo principio de pureza que
    justifica que `Context` sea externo. Se pasa `note` completa (no
    solo el tipo) porque la fila 3 necesita que el rechazo pueda citar
    zonas/titular reales para el comando de relanzamiento corregido
    (ver mas abajo), igual que `validate_replacement`.

  - `validate_replacement(note: Note, existing_in_zone: tuple[Note,
    ...]) -> Rejection | None` -- fila 4. Recibe las notas YA ACOTADAS a
    la zona (el propio nombre del campo de `Context`, "existing_in_zone",
    ya viene pre-filtrado por quien arma el `Context` -- PIEZAS.md
    Sec.7.5 dice que el validador llama a `similar` "por dentro", nunca
    que filtra el indice el mismo).

  - `validate_fields(note: Note) -> Rejection | None` -- fila 5.
    Autosuficiente: la tabla que necesita (`vocabulary.TYPES`) ya vive
    en el modulo que `validator` importa.

  - `validate_distillation(note: Note, is_distillation: bool) ->
    Rejection | None` -- fila 6. "es una destilacion" NO es un campo de
    `Note` tampoco -- spec-sistema-memoria-v2.md Sec.13 la describe como
    una fase de instalacion unica (quien la ejecuta lo sabe de
    antemano), y el propio spec Sec.6 punto 5 dice "por tipo de nota, no
    por firma del autor", lo que descarta que el origen del dato sea
    "quien commitea". El booleano es la forma minima de trasladar esa
    senal sin inventar un campo nuevo en `model.Note` que Sec.5.3 no
    declara.

  - `is_wip(subject: str) -> bool` -- fila 7. `emojis.py` (ya en
    produccion, Sec.5.2) dice explicitamente que el wip "lo escribe git,
    no gitmem -- no tiene productor en este sistema" y que su marca es
    🚧 delante del titular, sin corchetes (PIEZAS.md Sec.5.2 nota 8:
    "las dos formas sin corchetes -- el ⏩ del cierre y el 🚧 del wip --
    lo llevan delante"). Se prueba el predicado en si mismo, no que
    `validate_note` deje de disparar para un wip: un commit wip no pasa
    por `gitmem note` (no tiene zonas, no tiene tipo, no hay `Note` que
    construir), asi que el punto donde se salta la pregunta es la
    llamada a `is_wip` en `hooks/customs.py` (Capa 6, todavia no
    escrita) ANTES de intentar construir nada -- fuera del alcance de
    este fichero. Lo que si es responsabilidad de `validator.py`, y lo
    que prueba este test, es que el predicado clasifica bien: reconoce
    el wip real y no dispara con un titular normal.

No se toca produccion: si `lib/memory/validator.py` no existe, estos
tests se quedan en rojo tal cual estan -- eso es lo esperado.
"""

from datetime import datetime, timezone

import pytest

from .conftest import import_lib_memory_module

# Valores literales del flag CLI, citados de TEXTOS.md Sec.1.5 ("--stops
# no" / "--stops yes") -- no son prosa de rechazo (lo que esta prohibido
# copiar), son los DOS valores posibles de un flag, y estan fijados por
# el propio texto igual que el nombre del flag.
STOPS_YES = "yes"
STOPS_NO = "no"

_BASE_NOTE_FIELDS = dict(
    type="M",
    id="M-100",
    zone1="product",
    zone2="auth",
    headline="MARK_BASE_HEADLINE ordinary memo about the auth module",
    description="MARK_BASE_DESCRIPTION not empty, not special",
    timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
)


@pytest.fixture
def validator():
    return import_lib_memory_module("validator")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


@pytest.fixture
def config():
    return import_lib_memory_module("config")


@pytest.fixture
def make_note(model):
    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


def _flatten(rejection):
    """Junta title+body+relaunch de un `Rejection` en un solo texto buscable.

    Mismo motivo que `_assert_content_present` de test_rejection.py: el
    contrato no fija en cual de los tres campos debe vivir cada dato, asi
    que una busqueda que solo mirase `body` daria un falso rojo si Ultron
    puso el dato en `title` o en `relaunch`.
    """
    body = getattr(rejection, "body", "") or ""
    title = getattr(rejection, "title", "") or ""
    relaunch = getattr(rejection, "relaunch", ()) or ()
    return "\n".join([title, body, *relaunch])


def test_headline_over_max_rebounds_and_names_the_limit(
    validator, vocabulary, model, config
):
    """Fila 1: un titular de 81 caracteres rebota, y el rechazo dice el
    tope.

    Fallo real que previene: titulares que crecen hasta dejar de ser
    legibles de un vistazo en el indice.

    `HEADLINE_MAX` se importa de `vocabulary.py` (ya en produccion, Capa
    1) en vez de teclear "80" a mano -- es la misma constante que el
    rechazo real cita, "una sola copia en todo el sistema" (Sec.6.1).
    Se comprueba tambien el borde exacto (justo en el limite no rebota)
    para que este test no pase con una implementacion que rechace
    SIEMPRE -- un validador que nunca deja pasar nada de-cero seria
    indistinguible de uno que sabe contar caracteres hasta que se prueba
    el borde.
    """
    over_limit = "x" * (vocabulary.HEADLINE_MAX + 1)
    at_limit = "x" * vocabulary.HEADLINE_MAX

    rejection = validator.validate_headline(over_limit)

    assert rejection is not None, (
        f"un titular de {len(over_limit)} caracteres "
        f"(tope {vocabulary.HEADLINE_MAX}) no rebotó"
    )
    assert str(vocabulary.HEADLINE_MAX) in _flatten(rejection), (
        "el rechazo de titular largo no menciona el tope real "
        f"({vocabulary.HEADLINE_MAX}): {_flatten(rejection)!r}"
    )

    assert validator.validate_headline(at_limit) is None, (
        "un titular exactamente en el tope no debería rebotar"
    )


def test_missing_pain_answer_in_memo_rebounds_with_the_literal_question(
    validator, vocabulary, make_note, config
):
    """Fila 2: una M sin respuesta a la pregunta del dolor rebota con la
    pregunta literal dentro.

    Fallo real que previene: que el muro y el hecho se confundan, y una
    restriccion que debia salir en todos los arranques quede enterrada
    como memo.

    `PAIN_QUESTION` se importa de `vocabulary.py` (ya en produccion) --
    "la pregunta literal, UNA sola copia en todo el sistema" (Sec.6.1) --
    en vez de teclearla de nuevo aqui, que recrearia el mismo riesgo de
    dos copias que se separan que esa pieza existe para evitar.
    """
    note = make_note(type="M")

    rejection = validator.validate_pain_question(note, None)

    assert rejection is not None, (
        "una M sin respuesta a la pregunta del dolor no rebotó"
    )
    assert vocabulary.PAIN_QUESTION in _flatten(rejection), (
        "el rechazo no lleva la pregunta del dolor literal dentro: "
        f"{_flatten(rejection)!r}"
    )

    # Contestada con "no" (el hecho, no el muro), la M es válida: si
    # esto rebotase también, el test de arriba no probaría nada -- un
    # validador que rechaza toda M rechazaría igual una M bien formada.
    assert validator.validate_pain_question(note, STOPS_NO) is None


def test_yes_pain_answer_in_memo_says_it_should_be_restriction(
    validator, make_note, config
):
    """Fila 3: un "sí" a la pregunta del dolor en una M dice "entonces
    es una R".

    Fallo real que previene: lo mismo que la fila 2, pero cuando el
    usuario ya contestó bien y solo se equivocó de letra.

    No se compara el rechazo contra un texto tecleado a mano (serviría
    solo para probar que se sabe copiar TEXTOS.md) -- se comprueba la
    propiedad estructural real: el comando de relanzamiento corregido
    apunta a `note R`, no a `note M`. Y para que este test no pase con
    un validador que rechace CUALQUIER "yes" sin mirar el tipo, se
    comprueba el caso simétrico: una R contestada con "yes" es
    consistente y NO rebota.
    """
    import re

    note_m = make_note(type="M")
    note_r = make_note(type="R", id="R-100")

    rejection = validator.validate_pain_question(note_m, STOPS_YES)

    assert rejection is not None, (
        "una M con respuesta 'yes' (es un muro) no rebotó"
    )
    relaunch = getattr(rejection, "relaunch", ()) or ()
    assert relaunch, "el rechazo de tipo equivocado no trae comando de relanzamiento"
    assert any(re.search(r"\bnote\s+R\b", command) for command in relaunch), (
        "el comando de relanzamiento no corrige el tipo a R: "
        f"{relaunch!r}"
    )

    # Caso consistente: una R contestada "yes" no tiene nada que
    # corregir.
    assert validator.validate_pain_question(note_r, STOPS_YES) is None


def test_overlapping_note_without_replaces_rebounds_with_full_candidates(
    validator, make_note, config
):
    """Fila 4: una nota parecida sin --replaces rebota con las
    candidatas completas dentro.

    Fallo real que previene: dos decisiones contradictorias vigentes a
    la vez, y nadie sabe cuál manda.

    "Candidatas completas" (PIEZAS.md Sec.7.5, no solo un identificador
    suelto) se comprueba exigiendo que el `why` ENTERO de la nota
    existente sobreviva en el rechazo, no solo su id -- un rechazo que
    solo diera "D-030" obligaría a ir a buscarla por otra puerta,
    exactamente lo que el diseño prohíbe.
    """
    existing_note = make_note(
        type="D",
        id="D-030",
        why="MARK_EXISTING_WHY sesiones no escalan multi-tenant",
        keys=("token", "oauth", "MARK_EXISTING_KEY"),
    )
    candidate = make_note(
        type="D",
        id="D-099",
        why="MARK_EXISTING_WHY sesiones no escalan multi-tenant",
        keys=("token", "oauth", "MARK_EXISTING_KEY"),
        replaces=None,
    )

    rejection = validator.validate_replacement(candidate, (existing_note,))

    assert rejection is not None, (
        "una nota casi idéntica de la misma zona, sin --replaces, no rebotó"
    )
    flattened = _flatten(rejection)
    assert existing_note.id in flattened, (
        f"el rechazo no cita el id de la candidata: {flattened!r}"
    )
    assert existing_note.why in flattened, (
        "el rechazo no lleva el 'why' completo de la candidata dentro "
        f"(candidata recortada, no completa): {flattened!r}"
    )

    # Declarando --replaces sobre esa misma candidata, deja de rebotar.
    replacing = make_note(
        type="D",
        id="D-099",
        why="MARK_EXISTING_WHY sesiones no escalan multi-tenant",
        keys=("token", "oauth", "MARK_EXISTING_KEY"),
        replaces=existing_note.id,
    )
    assert validator.validate_replacement(replacing, (existing_note,)) is None


def test_field_not_allowed_for_type_rebounds(validator, vocabulary, make_note, config):
    """Fila 5: un campo que no existe para ese tipo rebota.

    Fallo real que previene: los campos zombis del v1 -- escritos, nunca
    leídos, invisibles (Sec.6.1: 1.002 `Why:` y 605 `Touched:` sin
    lector real).

    `vocabulary.TYPES["Q"].allowed_fields` (ya en producción) no incluye
    `why` -- se usa esa tabla real, no una inventada aquí, para decidir
    qué tipo/campo combina en un campo prohibido.
    """
    assert "why" not in vocabulary.TYPES["Q"].allowed_fields, (
        "fixture de test roto: se asumía que Q no permite 'why', pero "
        "vocabulary.TYPES dice lo contrario -- revisar el test, no "
        "producción"
    )

    note = make_note(type="Q", id="Q-100", why="MARK_ZOMBIE_FIELD no debería existir")

    rejection = validator.validate_fields(note)

    assert rejection is not None, (
        "una Q con 'why' (campo no permitido para Q) no rebotó"
    )
    assert "why" in _flatten(rejection).lower(), (
        f"el rechazo no nombra el campo sobrante 'why': {_flatten(rejection)!r}"
    )

    # Una Q sin ese campo es válida -- si esto también rebotase, el test
    # de arriba no probaría nada específico de 'why'.
    valid_note = make_note(type="Q", id="Q-101", why=None)
    assert validator.validate_fields(valid_note) is None


def test_distillation_without_sources_rebounds(validator, make_note, config):
    """Fila 6: una destilación sin fuentes rebota.

    Fallo real que previene: un resumen del que no se puede volver al
    original ni comprobar si resume bien.

    Se comprueba también que la regla es CONDICIONAL a que la nota sea
    de verdad una destilación -- una M cualquiera sin `origin` no tiene
    por qué rebotar (spec-sistema-memoria-v2.md Sec.6 punto 5: la regla
    aplica "toda nota de consolidación/destilación", no toda M), y que
    una destilación CON fuentes tampoco rebota.
    """
    distillation_without_sources = make_note(type="M", id="M-200", origin=())
    distillation_with_sources = make_note(
        type="M", id="M-201", origin=("4f2a1bc", "9de77a0")
    )
    ordinary_memo_without_origin = make_note(type="M", id="M-202", origin=())

    rejection = validator.validate_distillation(
        distillation_without_sources, is_distillation=True
    )

    assert rejection is not None, (
        "una nota marcada como destilación sin 'origin' no rebotó"
    )

    assert (
        validator.validate_distillation(
            distillation_with_sources, is_distillation=True
        )
        is None
    ), "una destilación CON fuentes rebotó -- no debería"

    assert (
        validator.validate_distillation(
            ordinary_memo_without_origin, is_distillation=False
        )
        is None
    ), "una M ordinaria sin origin rebotó -- la regla solo aplica a destilaciones"


def test_wip_marked_subject_is_recognized_and_skips_all_questions(validator, config):
    """Fila 7: el wip no recibe ni una sola pregunta.

    Fallo real que previene: fricción en el checkpoint silencioso, que
    es lo que hace que se deje de usar (spec-sistema-memoria-v2.md
    Sec.15: "el wip está exento de toda pregunta de la aduana... el
    escape no produce notas malas, produce CERO notas").

    El commit wip no pasa por `gitmem note` -- no tiene zonas, no tiene
    tipo, no hay `Note` que construir -- así que lo único que
    `validator.py` puede exponer (y lo único que se prueba aquí) es el
    predicado que lo reconoce, marcado con 🚧 delante del titular sin
    corchetes (emojis.py, ya en producción, Sec.5.2 nota 8). El punto
    donde ese predicado hace que ninguna pregunta se dispare vive en
    `hooks/customs.py` (Capa 6, todavía no construida) -- fuera del
    alcance de este contrato.
    """
    wip_subject = "🚧 quick checkpoint before switching tasks"
    normal_subject = "[D-030][product][auth] 🧭 login with JWT + Google OAuth"
    unmarked_subject = "just a plain line without any marker at all"

    assert validator.is_wip(wip_subject) is True
    assert validator.is_wip(normal_subject) is False
    assert validator.is_wip(unmarked_subject) is False


def test_same_note_and_context_always_produce_the_same_verdict(
    validator, model, config
):
    """Fila 8: mismos datos → mismo veredicto, siempre.

    Fallo real que previene: un validador que depende del entorno -- pasa
    en el generador y falla en el hook, o al revés.

    Construye dos pares `Note`/`Context` INDEPENDIENTES (objetos
    distintos, no la misma referencia reutilizada dos veces) con los
    MISMOS valores de campo, y comprueba que `validate_note` devuelve
    exactamente lo mismo para ambos. Se usa una zona que no existe en
    `ctx.zones` (`zones={}`) para garantizar un veredicto NO vacío --
    comparar dos tuplas vacías no demostraría pureza de verdad, solo que
    "nada pasó nada" dos veces.
    """

    def _build_pair():
        note = model.Note(
            type="M",
            id="M-300",
            zone1="MARK_UNKNOWN_ZONE_1",
            zone2="MARK_UNKNOWN_ZONE_2",
            headline="a perfectly ordinary headline under the limit",
            description="a perfectly ordinary description, not empty",
            timestamp=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        ctx = validator.Context(
            zones={},
            existing_in_zone=(),
            known_ids=frozenset(),
            config=config.Config(),
        )
        return note, ctx

    note_a, ctx_a = _build_pair()
    note_b, ctx_b = _build_pair()

    assert note_a is not note_b, "fixture roto: se reutilizó el mismo objeto Note"
    assert ctx_a is not ctx_b, "fixture roto: se reutilizó el mismo objeto Context"

    result_a = validator.validate_note(note_a, ctx_a)
    result_b = validator.validate_note(note_b, ctx_b)

    assert result_a, (
        "el veredicto de una nota con zona inexistente salió vacío -- "
        "este test necesita un caso NO vacío para probar pureza de verdad"
    )
    assert result_a == result_b, (
        "los mismos datos produjeron veredictos distintos entre dos "
        f"llamadas independientes: {result_a!r} != {result_b!r}"
    )


def test_empty_or_whitespace_why_in_decision_rebounds_same_as_missing(
    validator, vocabulary, make_note, config
):
    """Regresión: un `why` vacío o solo espacios pasa la validación sin rebotar.

    Causa real (confirmada leyendo `validator.py::_present_fields`): `why`
    se comprueba por EXISTENCIA (`if note.why is not None`), no por
    CONTENIDO como `description` (`if note.description`) -- una cadena
    vacía o de solo espacios "existe" para ese chequeo, así que cuenta
    como presente aunque `why` sea obligatorio en D
    [vocabulary.TYPES["D"].required_fields].

    Por qué importa y no es un caso de laboratorio: una decisión sin
    porqué es exactamente el campo zombi que el sistema entero existe
    para impedir -- en el v1 se escribieron 1.002 `Why:` que nadie leyó
    [vocabulary.py, docstring del módulo]. Y aquí es peor: el campo está
    declarado obligatorio, el validador dice que lo exige, y no lo exige.
    """
    assert "why" in vocabulary.TYPES["D"].required_fields, (
        "fixture de test roto: se asumía que 'why' es obligatorio en D, "
        "pero vocabulary.TYPES dice lo contrario -- revisar el test, no "
        "producción"
    )

    note_empty_why = make_note(type="D", id="D-501", why="")
    note_whitespace_why = make_note(type="D", id="D-502", why="   ")

    rejection_empty = validator.validate_fields(note_empty_why)
    rejection_whitespace = validator.validate_fields(note_whitespace_why)

    assert rejection_empty is not None, (
        "una D con why='' (cadena vacía) no rebotó -- 'why' es obligatorio "
        "en D y una cadena vacía no es una respuesta"
    )
    assert "why" in _flatten(rejection_empty).lower(), (
        "el rechazo de why vacío no nombra el campo que falta: "
        f"{_flatten(rejection_empty)!r}"
    )
    assert rejection_whitespace is not None, (
        "una D con why='   ' (solo espacios) no rebotó -- solo espacios no "
        "es una respuesta, igual que una cadena vacía"
    )

    # Sanity: una D con why de verdad no rebota -- si esto también
    # rebotase, los dos asserts de arriba no probarían nada específico de
    # vacío/espacios (un validador que rechaza TODA D probaría lo mismo).
    note_real_why = make_note(
        type="D", id="D-503", why="MARK_REAL_WHY una razón de verdad"
    )
    assert validator.validate_fields(note_real_why) is None, (
        "una D con un why de verdad rebotó -- este test necesita un caso "
        "válido para probar que el rechazo es específico de vacío/espacios"
    )


def test_whitespace_only_description_rebounds_same_as_missing_for_every_type(
    validator, vocabulary, model, config
):
    """Regresión: una `description` de solo espacios pasa en los siete tipos.

    Misma causa raíz que el test de arriba: `_present_fields` mira `if
    note.description`, que es verdadero para cualquier cadena no vacía --
    incluida una hecha solo de espacios (una cadena vacía sí se detecta
    hoy, porque `""` es falsy en Python; `"   "` no lo es). `description`
    es obligatorio en los siete tipos [vocabulary.py, docstring del
    módulo: "description es obligatorio en los siete"], así que el hueco
    aplica a los siete, no solo a uno.

    Se recorren los siete tipos reales de `vocabulary.TYPES` (no una
    lista tecleada a mano) para que si algún día se añade o quita un
    tipo, este test lo siga cubriendo sin tener que tocarlo.
    """
    timestamp = datetime(2026, 8, 2, tzinfo=timezone.utc)

    for letter, spec in vocabulary.TYPES.items():
        assert "description" in spec.required_fields, (
            f"fixture de test roto: se asumía que 'description' es "
            f"obligatorio en {letter}, pero vocabulary.TYPES dice lo "
            "contrario -- revisar el test, no producción"
        )

        fields = dict(
            type=letter,
            id=f"{letter}-600",
            zone1="product",
            zone2="auth",
            headline="a normal headline under the limit",
            description="   ",
            timestamp=timestamp,
        )
        if "why" in spec.required_fields:
            fields["why"] = "MARK_REAL_WHY needed because this type requires it"
        if "awaits" in spec.required_fields:
            fields["awaits"] = "MARK_REAL_AWAITS someone responsible"

        note = model.Note(**fields)

        rejection = validator.validate_fields(note)

        assert rejection is not None, (
            f"una nota de tipo {letter} con description='   ' (solo "
            "espacios) no rebotó -- 'description' es obligatorio en los "
            "siete tipos y solo espacios no es contenido"
        )
        assert "description" in _flatten(rejection).lower(), (
            f"el rechazo de description vacía para {letter} no nombra el "
            f"campo que falta: {_flatten(rejection)!r}"
        )


# ---------------------------------------------------------------------------
# Regresión: `validate_pointers` (lib/memory/validator_pointers.py) distingue
# mayúsculas en `_NOTE_ID_PATTERN` (línea 63: `^[DMRQXIB]-\d+$`, sin
# `re.IGNORECASE`) y no recorta espacios antes de comprobar la forma. Un
# puntero con forma de identificador de nota casi bien escrito ("d-030" en
# vez de "D-030", o "D-030 " con un espacio de más) NO casa el patrón, así
# que cae por la misma rendija reservada a los hashes de commit del sistema
# viejo (p.ej. "4f2a1bc") y se exime de toda comprobación -- pasa en
# silencio, enlazado a nada.
#
# CONDUCTA FIJADA (decisión del orquestador, revocable por el propietario):
# un puntero con forma de identificador se comprueba SIEMPRE, sin importar
# mayúsculas ni espacios sobrantes. Si no está tal cual en `known_ids`, se
# rechaza como `dangling_pointer` -- no se corrige solo, el usuario reescribe
# el identificador. Lo que NO cambia: un hash de commit v1 sigue exento (no
# tiene forma de identificador de nota bajo ningún criterio razonable de
# mayúsculas/espacios).
#
# Cada test compara dos cosas escritas por separado: el puntero que el
# "usuario" tecleó en `origin`/`replaces` (un dato) contra `known_ids` (el
# índice real, otro dato) -- nunca el resultado se mira contra sí mismo.
# ---------------------------------------------------------------------------


def test_origin_pointer_lowercase_of_existing_id_rejects_as_dangling(
    validator, make_note, config
):
    """Un puntero en minúscula de un id real ("d-030" cuando existe "D-030")
    rebota como colgante -- HOY pasa en silencio.

    Fallo real que previene: `gitmem note ... --origin d-030` guarda una
    nota que se cree enlazada a la decisión D-030 y no lo está -- el racimo
    del informe nunca la agrupa, y nadie se entera nunca (memoria escrita
    que se cree conectada y no lo está).
    """
    known_ids = frozenset({"D-030", "I-001"})
    lowercase_note = make_note(type="M", id="M-100", origin=("d-030",))

    rejection = validator.validate_pointers(lowercase_note, known_ids)

    assert rejection is not None, (
        "origin=('d-030',) con known_ids={'D-030', 'I-001'} no rebotó -- "
        "un identificador real mal escrito en mayúscula se coló como si "
        "fuera un hash de commit v1 exento"
    )
    assert "d-030" in _flatten(rejection), (
        "el rechazo no cita el puntero tal como se escribió ('d-030'): "
        f"{_flatten(rejection)!r}"
    )

    # Sanity: el mismo id, bien escrito, no rebota -- si esto también
    # rebotase, el assert de arriba no probaría nada específico de
    # mayúsculas (un validador que rechaza TODO origin probaría lo mismo).
    exact_note = make_note(type="M", id="M-101", origin=("D-030",))
    assert validator.validate_pointers(exact_note, known_ids) is None, (
        "origin=('D-030',) con known_ids={'D-030', 'I-001'} rebotó -- "
        "un puntero exacto a un id real no debería rechazarse nunca"
    )


def test_origin_pointer_with_surrounding_whitespace_of_existing_id_rejects_as_dangling(
    validator, make_note, config
):
    """Un puntero con espacio de más ("D-030 " o " D-030") de un id real
    rebota como colgante -- HOY pasa en silencio.

    Fallo real que previene: el mismo que el de mayúsculas -- un espacio
    perdido al teclear el `--origin` deja la nota enlazada a nada, sin aviso.
    Se comprueban los dos lados (espacio al final y al principio) porque
    ambos son errores de tecleo reales igual de plausibles.
    """
    known_ids = frozenset({"D-030"})
    trailing_space_note = make_note(type="M", id="M-102", origin=("D-030 ",))
    leading_space_note = make_note(type="M", id="M-103", origin=(" D-030",))

    trailing_rejection = validator.validate_pointers(trailing_space_note, known_ids)
    leading_rejection = validator.validate_pointers(leading_space_note, known_ids)

    assert trailing_rejection is not None, (
        "origin=('D-030 ',) (espacio al final) con known_ids={'D-030'} no "
        "rebotó -- el espacio sobrante debería seguir tratándose como el "
        "mismo identificador con forma de nota, y por tanto comprobarse"
    )
    assert leading_rejection is not None, (
        "origin=(' D-030',) (espacio al principio) con known_ids={'D-030'} "
        "no rebotó -- mismo hueco que el espacio al final"
    )

    # Sanity: el mismo id, sin espacios de más, no rebota.
    exact_note = make_note(type="M", id="M-104", origin=("D-030",))
    assert validator.validate_pointers(exact_note, known_ids) is None, (
        "origin=('D-030',) sin espacios rebotó -- un puntero exacto no "
        "debería rechazarse nunca"
    )


def test_restriction_lowercase_incident_pointer_rejects_as_dangling(
    validator, make_note, config
):
    """Una R que cita una incidencia real en minúscula ("i-001" cuando
    existe "I-001") rebota como colgante -- HOY pasa en silencio, y además
    se salta la exigencia real de citar una incidencia de verdad (el
    puntero nunca se comprueba, así que "i-001" cuenta como si apuntara a
    algo, sin apuntar a nada).

    Fallo real que previene: un muro que se cree enlazado a su incidencia de
    origen -- I-001 -- y no lo está, porque el usuario tecleó la letra en
    minúscula.
    """
    known_ids = frozenset({"D-030", "I-001"})
    note_r = make_note(type="R", id="R-100", origin=("i-001",))

    rejection = validator.validate_pointers(note_r, known_ids)

    assert rejection is not None, (
        "una R con origin=('i-001',) y known_ids={'D-030', 'I-001'} no "
        "rebotó -- una incidencia real citada en minúscula se coló sin "
        "comprobarse"
    )
    assert "i-001" in _flatten(rejection), (
        "el rechazo no cita el puntero tal como se escribió ('i-001'): "
        f"{_flatten(rejection)!r}"
    )

    # Sanity: la misma incidencia, bien escrita, no rebota.
    exact_note_r = make_note(type="R", id="R-101", origin=("I-001",))
    assert validator.validate_pointers(exact_note_r, known_ids) is None, (
        "una R con origin=('I-001',) sobre una incidencia real rebotó -- "
        "no debería"
    )


def test_origin_v1_commit_hash_remains_exempt_from_pointer_check(
    validator, make_note, config
):
    """Guarda de no-regresión: un hash de commit del sistema viejo
    ("4f2a1bc") sigue exento de la comprobación de punteros -- es el motivo
    por el que `_NOTE_ID_PATTERN` existe (TEXTOS.md Sec.1.7, una
    destilación cita su origen v1 por hash, no por id de nota).

    Este test debe seguir en verde tanto ANTES como DESPUÉS del arreglo de
    mayúsculas/espacios -- si el arreglo lo rompe, el arreglo está mal: un
    hash de commit nunca es un identificador de nota, con cualquier criterio
    razonable de mayúsculas o espacios.
    """
    known_ids = frozenset({"D-030"})
    note = make_note(type="M", id="M-105", origin=("4f2a1bc",))

    assert validator.validate_pointers(note, known_ids) is None, (
        "origin=('4f2a1bc',) (hash de commit v1) rebotó -- un hash nunca "
        "debe tratarse como identificador de nota"
    )


def test_origin_mixed_hash_and_bad_case_pointer_rejects_only_the_bad_one(
    validator, make_note, config
):
    """Edge case: un `origin` con un hash v1 exento Y un id real mal
    escrito a la vez rechaza SOLO el segundo -- el hash no debe aparecer
    citado como puntero colgante en el mismo rechazo.

    Cubre la combinación real más probable: una destilación que cita su
    fuente v1 por hash y, en el mismo `--origin`, una decisión nueva mal
    tecleada.
    """
    known_ids = frozenset({"D-030"})
    note = make_note(type="M", id="M-106", origin=("4f2a1bc", "d-030"))

    rejection = validator.validate_pointers(note, known_ids)

    assert rejection is not None, (
        "origin=('4f2a1bc', 'd-030') con known_ids={'D-030'} no rebotó -- "
        "'d-030' es un id real mal escrito y debería colgar"
    )
    flattened = _flatten(rejection)
    assert "d-030" in flattened, (
        f"el rechazo no cita el puntero mal escrito 'd-030': {flattened!r}"
    )
    assert "4f2a1bc" not in flattened, (
        "el rechazo cita el hash exento '4f2a1bc' como si colgara -- el "
        f"hash no debe aparecer como puntero colgante: {flattened!r}"
    )


def test_replaces_case_mismatch_of_existing_id_already_rejects(
    validator, make_note, config
):
    """Guarda de no-regresión: `replaces` en minúscula de un id real
    ("d-030" cuando existe "D-030") YA rebota HOY como colgante -- a
    diferencia de `origin`, `replaces` no pasa por `_NOTE_ID_PATTERN`
    (validator_pointers.py líneas 78-83: se compara contra `known_ids`
    entero, sin filtro de forma), así que nunca tuvo el hueco de mayúsculas.

    Este test documenta la conducta ya correcta (confirmada leyendo el
    código, no asumida) para que el arreglo de `origin` no la toque por
    accidente -- debe seguir en verde antes y después del arreglo.
    """
    known_ids = frozenset({"D-030"})
    lowercase_replaces = make_note(type="M", id="M-107", replaces="d-030")

    rejection = validator.validate_pointers(lowercase_replaces, known_ids)

    assert rejection is not None, (
        "replaces='d-030' con known_ids={'D-030'} no rebotó -- ya se "
        "esperaba que rebotase hoy, sin ningún arreglo"
    )
    assert "d-030" in _flatten(rejection), (
        f"el rechazo no cita el puntero tal como se escribió: {_flatten(rejection)!r}"
    )

    # Sanity: el mismo id, bien escrito, no rebota.
    exact_replaces = make_note(type="M", id="M-108", replaces="D-030")
    assert validator.validate_pointers(exact_replaces, known_ids) is None, (
        "replaces='D-030' sobre un id real rebotó -- no debería"
    )

    # Sanity: el centinela 'none' sigue exento, con cualquier known_ids.
    none_sentinel = make_note(type="M", id="M-109", replaces="none")
    assert validator.validate_pointers(none_sentinel, frozenset()) is None, (
        "replaces='none' rebotó -- el centinela de 'convive con todas' "
        "debe seguir exento"
    )
