"""Contrato de lib/memory/boot.py -- PIEZAS.md Sec.9.5.

boot.py NO EXISTE TODAVIA. Estos tests deben fallar al resolver la
fixture `boot` (FileNotFoundError via `import_lib_memory_module`, ver
conftest) -- es el ROJO del modo test-first, contrato de aceptacion
(pasada 1, antes de Ultron): las CUATRO filas que Sec.9.5 declara en su
tabla "Sus tests", ni una mas, mas UNA fila adicional pedida por el
encargo (ver "EL CHOQUE CON health.build()" mas abajo). El endurecimiento
exhaustivo (branch/edge-case completo) es la pasada 2, DESPUES de que
Ultron implemente -- no se adelanta aqui.

DE QUE SALIDA SE DERIVA [encargo, PIEZAS.md Sec.9.5]: las dos formas
literales del arranque, TEXTOS.md Sec.3.1 (proyecto con contenido) y
Sec.3.2 (proyecto recien instalado) -- "los dos bloques son la salida,
no un ejemplo" -- y el orden de los cinco bloques que fija spec Sec.8.3:
el (NEXT) con su contexto debajo, TODOS los bloqueantes con a quien
esperan, TODAS las restricciones sin tope, los recuentos, los avisos.

LAS CUATRO FILAS DE Sec.9.5 Y SU TEST:

  1. Memoria vacia -> ceros EXPLICITOS y ruidosos, no secciones ausentes
     -> test_empty_memory_shows_explicit_loud_zeros_not_absent_sections
  2. Tres notas -> tres, y las restricciones (y bloqueantes, mismo
     criterio de spec Sec.8.3: "sin tope ni presupuesto") salen TODAS,
     sin tope -> test_all_restrictions_and_blockers_render_without_any_cap
     (se siembran 12, no 3: el fallo real que esta fila previene es el
     PRESUPUESTO del v1 -- "10 de 287 decisiones visibles" -- y con solo
     tres nunca se distinguiria "sin tope" de "tope de 10" o mayor;
     doce si lo distingue)
  3. Un indice corrupto sale como aviso y el arranque SIGUE
     -> test_a_corrupted_index_is_shown_as_a_warning_and_boot_still_completes
  4. Las horas llevan su etiqueta UTC
     -> test_context_and_generated_timestamps_carry_the_utc_label

EL CHOQUE CON health.build() [encargo explicito de esta tarea]: el
arranque necesita un informe de salud entero (`BootSummary.health:
HealthReport`, ya declarado en model.py), y `health.build()` -- la
funcion que lo compondria -- NO ESTA ESCRITA todavia (Sec.9.4 solo
implementa `coherence`/`coherence_rules`/`duplicates`/
`plans_unreflected`, cada una suelta). `ids.find_duplicates` lleva desde
su propio dia declarando a `health.duplicates` como su llamador real
para la linea "no duplicate IDs (N notas)" del arranque -- sin
`health.build()` componiendo el `HealthReport` que `boot.build()`
consume (Sec.9.5, "Que NO hace": "no calcula salud (llama a health)"),
esa linea no se puede producir. `test_id_duplicate_line_requires_a_real_composed_health_report`
es la fila que lo exige: no llama a `health.build` directamente (no
existe), pero `summary.health` solo puede llevar los numeros REALES
-- derivados aqui de `health.coherence()`/`health.duplicates()`, ya en
produccion -- si `boot.build()` los obtuvo de alguna funcion de
`health.py` que los componga a los cuatro juntos. Esta fila NO
IMPLEMENTA `health.build()` -- eso lo escribe Ultron.

COMO SE SIEMBRA [ALINEADO 2026-08-02, ver el memo de la tarea que corrigio
esto]: este parrafo describia originalmente un bug de produccion --
`notes.write()` escribiendo los ocho indices en la raiz PELADA del repo
en vez de `<root>/.claude/project-memory/` -- que ya esta arreglado. La
correccion vive en `notes.pm_root(root)` [notes.py], que compone
`<root>/.claude/project-memory/` y es la MISMA funcion de la que ahora
depende `notes.write()` por dentro y que `health.coherence()`/
`health.duplicates()`/`_current_index_lines()` usan para leer. `test_report.py`
(via su propia `_pm_root(root)` local) y `test_health.py` (via
`notes.pm_root(root)`, arreglado en la misma sesion) ya siembran y leen
ahi -- los cuatro pasan.

`boot.py` (Sec.9.5) se construye con `context`, `health` y `query`
-- NUNCA con `report`/`zones` -- y las TRES funciones de `health.py` que
importan aqui (`coherence(root)`, `duplicates(root)`,
`plans_unreflected()`) siguen tomando la raiz LITERAL del repo como
parametro `root` (su firma no cambia): son ELLAS, por dentro, las que
componen `notes.pm_root(root)` para leer los indices reales -- nunca el
llamador. Por eso cada test de este fichero sigue pasando la raiz
LITERAL (`root = Path(tmp_repo)`) a `health.coherence(root)`/
`health.duplicates(root)`, sin tocarla -- el cambio de convencion solo
afecta a las llamadas DIRECTAS de este fichero a `indexes.seed()`/
`indexes.remove()`/etc. (los mismos sitios donde `notes.write()` deja los
ficheros de verdad), que ahora tienen que pasar por `notes.pm_root(root)`
tambien, en vez de la raiz pelada.

SEMBRADO REAL, NUNCA FABRICADO [unmassk-standards Sec.34]: cada nota
entra por `notes.write(note, ctx)`/`context.write(ctx_note)` contra un
`tmp_repo` real -- nunca construida a mano. El valor esperado de cada
aserto de round-trip (numeros de `health.coherence()`, timestamp real de
`context.latest()`) sale de llamar a la pieza real que ya esta en
produccion y en verde, nunca de un valor tecleado por este fichero.

QUE NO SE PRUEBA AQUI, Y POR QUE (mismo criterio que test_report.py/
test_health.py, "supuestos declarados"): `open_questions`/`open_issues`/
`open_incidents` (el bloque COUNTS) no tienen fila propia en la tabla
"Sus tests" de Sec.9.5 -- de donde sale cada numero (que cuenta como
"abierta" para una Q, una I, o una issue de GitHub) no esta fijado por
ningun texto citado en el encargo, y "una fila = un test, ni uno mas"
(regla ya aplicada en `test_health.py`) prohibe inventar esa fila aqui.
Fuera de esta pasada, para quien la audite despues.

No se toca produccion en ningun momento de esta tarea: `boot.py` no
existe todavia. No se toca ningun otro fichero de test ni de
`lib/memory/`.
"""

from datetime import datetime, timezone
from pathlib import Path
import contextlib
import os

import pytest

from .conftest import import_lib_memory_module, run_git

_BASE_NOTE_FIELDS = dict(
    type="M",
    id="",
    zone1="product",
    zone2="boot-test",
    description="MARK_BOOT_DESCRIPTION not empty, not special",
    timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
)

# Fila 2: mas que cualquier presupuesto de renderizado plausible (el del
# v1 era 10) -- con doce, "sin tope" y "tope de 10" dan resultados
# distintos y el test los distingue de verdad.
_NO_CAP_COUNT = 12

# Fragmentos literales de TEXTOS.md Sec.3.2 (proyecto recien instalado),
# copiados byte a byte leyendo el fichero (nunca tecleados de memoria) --
# mismo criterio que test_report_render.py aplica a "CERO NOTAS".
_ZERO_BLOCKERS_LITERAL = "⛔ BLOCKERS ......  C E R O"
_ZERO_RESTRICTIONS_LITERAL = "⚠️ RESTRICTIONS ....  C E R O"
_ZERO_EXPLANATION_LINE_1 = "No hay ningún muro puesto. Nada te va a parar"
_ZERO_EXPLANATION_LINE_2 = "porque nadie ha escrito todavía qué rompe qué."
_NO_NEXT_LINE_1 = "[NEXT] ninguno todavía. No hay ningún cierre de sesión escrito."
_NO_NEXT_LINE_2 = "El primero lo escribe close-session al terminar hoy."


@pytest.fixture
def boot():
    return import_lib_memory_module("boot")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def config():
    return import_lib_memory_module("config")


@pytest.fixture
def validator():
    return import_lib_memory_module("validator")


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def notes():
    return import_lib_memory_module("notes")


@pytest.fixture
def health():
    return import_lib_memory_module("health")


@pytest.fixture
def context_mod():
    return import_lib_memory_module("context")


@pytest.fixture
def rules():
    return import_lib_memory_module("rules")


@pytest.fixture
def emojis():
    return import_lib_memory_module("emojis")


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


def _index_line_for(indexes_mod, vocabulary_mod, root, note_id):
    """Busca `note_id` en los siete indices VIGENTES (no ARCHIVED.md).
    Devuelve `(nombre_fichero, IndexLine)`, o `(None, None)` -- mismo
    helper que `test_health.py::_index_line_for`, duplicado a proposito
    (mismo criterio que `_cwd`/`_delete_rule_line_by_hand` repetidos en
    cada fichero de este contrato).
    """
    for name in vocabulary_mod.INDEX_FILES:
        if name == "ARCHIVED.md":
            continue
        for line in indexes_mod.read(name, root):
            if line.id == note_id:
                return name, line
    return None, None


def _swap_rule_line_by_hand(rules_mod, emojis_mod, root, real_marker, bogus_text, kind="user"):
    """Retira la unica linea del fichero de reglas que contiene
    `real_marker` (dejando su commit real intacto, mismo mecanismo que
    `_delete_rule_line_by_hand`) y anade EN SU LUGAR una linea bogus con
    el mismo formato exacto que `rules.add()` escribe -- para que el
    NUMERO de lineas del fichero quede igual que antes del cambio, pero
    el CONTENIDO diverja en los dos sentidos: la real desaparece, la
    bogus no tiene commit detras.
    """
    path = rules_mod.rules_file_path(root)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if real_marker not in line]
    assert len(kept) == len(lines) - 1, (
        f"se esperaba borrar exactamente una linea con {real_marker!r} de {path}, "
        f"se borraron {len(lines) - len(kept)}"
    )
    emoji = emojis_mod.CHANNEL_EMOJI["rule"]
    bogus_line = f"[remember][{kind}] {emoji} {bogus_text}\n"
    path.write_text("".join(kept) + bogus_line, encoding="utf-8")


def _zero_commit_repo(tmp_path, name="zero_commit_repo"):
    """Un repo git genuinamente SIN NINGUN commit -- distinto de
    `tmp_repo` (conftest.py), que ya trae un commit 'init' de fabrica.
    `git log` sobre este repo devuelve el mensaje real de rama sin nacer
    ('does not have any commits yet'), no un fallo simulado.
    """
    repo = tmp_path / name
    repo.mkdir()
    rc, _out, err = run_git(["init"], str(repo))
    assert rc == 0, f"git init fallo montando el repo sin commits: {err}"
    return repo


def _delete_rule_line_by_hand(rules_mod, root, marker):
    """Retira del fichero de reglas, a mano (fuera de `rules.add()`), la
    unica linea que contiene `marker` -- deja el commit real de esa regla
    intacto en git. Mismo helper que
    `test_health.py::_delete_rule_line_by_hand` -- duplicado a proposito,
    mismo criterio que `_cwd` repetido en cada fichero de este contrato.
    """
    path = rules_mod.rules_file_path(root)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if marker not in line]
    assert len(kept) == len(lines) - 1, (
        f"se esperaba borrar exactamente una linea con {marker!r} de {path}, "
        f"se borraron {len(lines) - len(kept)}"
    )
    path.write_text("".join(kept), encoding="utf-8")


@pytest.fixture
def make_note(model):
    """Fabrica de `Note`, mismos defaults neutros que test_report.py/
    test_health.py -- cada test override solo lo que le importa."""

    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


@pytest.fixture
def make_context(model, config, validator):
    """Un `Context` real, con las zonas de la nota ya dadas de alta EN
    MEMORIA -- mismo patron que test_report.py::make_context. `boot.py`
    no importa `zones`, asi que ningun test de este fichero toca
    `zones.json` en disco.
    """

    def _make(zone_names=(), existing_in_zone=(), known_ids=frozenset(), cfg=None):
        zones = {
            name: model.Zone(name=name, description=f"MARK zone {name}", aliases=())
            for name in zone_names
        }
        return validator.Context(
            zones=zones,
            existing_in_zone=existing_in_zone,
            known_ids=known_ids,
            config=cfg if cfg is not None else config.Config(),
        )

    return _make


@contextlib.contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo
    restaura siempre -- mismo helper que test_report.py/test_health.py.
    `boot.build()` no declara `root`/`cwd` propio (Sec.9.5, misma
    superficie de `context`/`query`/`health`), asi que TODA llamada a
    `boot.*` de este fichero va envuelta en `_cwd(root)`.
    """
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


# ---------------------------------------------------------------------------
# Fila 1 -- memoria vacia -> ceros explicitos y ruidosos, no secciones ausentes
# ---------------------------------------------------------------------------


def test_empty_memory_shows_explicit_loud_zeros_not_absent_sections(
    boot, model, indexes, notes, tmp_repo
):
    """Fila 1 de Sec.9.5: memoria vacia -> ceros EXPLICITOS y ruidosos, no
    secciones ausentes.

    Fallo real que previene: arrancar creyendo que no hay muros puestos
    cuando lo que paso es que el lector fallo -- el propio texto de
    TEXTOS.md Sec.3.2 lo dice en alto ("No hay ningún muro puesto. Nada
    te va a parar porque nadie ha escrito todavia que rompe que"), y esa
    frase solo tiene sentido si aparece SIEMPRE que de verdad no hay
    nada, nunca por omision de un fallo de lectura.

    Repo recien instalado: los ocho indices existen (via `indexes.seed`,
    idempotente) pero ninguno tiene una linea todavia -- ningun commit de
    nota, ningun cierre de sesion. Estado real de TEXTOS.md Sec.3.2, no
    fabricado: `boot.build()`/`boot.render()` son las UNICAS piezas bajo
    prueba aqui.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    with _cwd(root):
        summary = boot.build()
        rendered = boot.render(summary)

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary, devolvio {type(summary)!r}"
    )
    assert summary.context is None, (
        f"un repo sin ningun cierre de sesion no deberia tener context, salio "
        f"{summary.context!r}"
    )
    assert summary.blockers == (), (
        f"un repo sin notas no deberia tener bloqueantes, salio {summary.blockers!r}"
    )
    assert summary.restrictions == (), (
        f"un repo sin notas no deberia tener restricciones, salio "
        f"{summary.restrictions!r}"
    )

    assert _ZERO_BLOCKERS_LITERAL in rendered, (
        f"el literal exacto de TEXTOS.md Sec.3.2 para bloqueantes en cero no "
        f"aparece -- {_ZERO_BLOCKERS_LITERAL!r} no esta en el render:\n{rendered}"
    )
    assert _ZERO_RESTRICTIONS_LITERAL in rendered, (
        f"el literal exacto de TEXTOS.md Sec.3.2 para restricciones en cero no "
        f"aparece -- {_ZERO_RESTRICTIONS_LITERAL!r} no esta en el render:\n{rendered}"
    )
    assert _ZERO_EXPLANATION_LINE_1 in rendered and _ZERO_EXPLANATION_LINE_2 in rendered, (
        "la explicacion literal de TEXTOS.md Sec.3.2 ('No hay ningún muro "
        "puesto... porque nadie ha escrito todavia que rompe que') no aparece "
        f"completa en el render:\n{rendered}"
    )
    assert _NO_NEXT_LINE_1 in rendered and _NO_NEXT_LINE_2 in rendered, (
        "el bloque NEXT ausente (TEXTOS.md Sec.3.2) tiene que decirlo en alto, "
        f"no omitirse -- literal esperado no encontrado en el render:\n{rendered}"
    )


# ---------------------------------------------------------------------------
# Fila 2 -- tres notas -> tres, y las restricciones salen TODAS, sin tope
# ---------------------------------------------------------------------------


def test_all_restrictions_and_blockers_render_without_any_cap(
    boot, model, indexes, notes, tmp_repo, make_note, make_context
):
    """Fila 2 de Sec.9.5: las restricciones (y los bloqueantes, mismo
    criterio explicito de spec Sec.8.3: "TODOS los B"/"TODAS las R... sin
    tope ni presupuesto") salen TODAS.

    Fallo real que previene: el presupuesto de renderizado del v1
    ocultaba el 94-96% de la memoria (10 de 287 decisiones visibles) y el
    modelo concluia que lo que no salia no existia. Se siembran DOCE de
    cada -- mas que cualquier tope plausible -- para que "sin tope" se
    distinga de verdad de "tope de 10".
    """
    root = Path(tmp_repo)
    zone = "bootnocapzone"
    indexes.seed(notes.pm_root(root))
    ctx = make_context(zone_names=(zone,))

    restriction_ids = []
    with _cwd(root):
        for i in range(_NO_CAP_COUNT):
            note = make_note(
                type="R",
                zone1=zone,
                zone2=zone,
                headline=f"MARK_BOOTNOCAP_R{i:02d} restriction {i} of {_NO_CAP_COUNT}",
                why=f"MARK_BOOTNOCAP_WHY{i:02d} the real reason restriction {i} exists",
            )
            result = notes.write(note, ctx)
            assert result.ok, (
                f"seed de la restriccion {i} fallo: "
                f"{result.git_error or result.rejections}"
            )
            restriction_ids.append(result.note_id)

    blocker_ids = []
    with _cwd(root):
        for i in range(_NO_CAP_COUNT):
            note = make_note(
                type="B",
                zone1=zone,
                zone2=zone,
                headline=f"MARK_BOOTNOCAP_B{i:02d} blocker {i} of {_NO_CAP_COUNT}",
                awaits=f"MARK_BOOTNOCAP_AWAITS{i:02d} whoever owns blocker {i}",
            )
            result = notes.write(note, ctx)
            assert result.ok, (
                f"seed del bloqueante {i} fallo: "
                f"{result.git_error or result.rejections}"
            )
            blocker_ids.append(result.note_id)

    with _cwd(root):
        summary = boot.build()
        rendered = boot.render(summary)

    assert len(summary.restrictions) == _NO_CAP_COUNT, (
        f"se sembraron {_NO_CAP_COUNT} restricciones reales, "
        f"summary.restrictions trae {len(summary.restrictions)} -- un tope "
        f"silencioso las esta recortando: {[n.id for n in summary.restrictions]!r}"
    )
    assert {n.id for n in summary.restrictions} == set(restriction_ids), (
        f"summary.restrictions no trae exactamente las {_NO_CAP_COUNT} "
        f"restricciones sembradas -- sembradas: {restriction_ids!r}, "
        f"presentes: {[n.id for n in summary.restrictions]!r}"
    )
    assert len(summary.blockers) == _NO_CAP_COUNT, (
        f"se sembraron {_NO_CAP_COUNT} bloqueantes reales, summary.blockers "
        f"trae {len(summary.blockers)} -- un tope silencioso los esta "
        f"recortando: {[n.id for n in summary.blockers]!r}"
    )
    assert {n.id for n in summary.blockers} == set(blocker_ids), (
        f"summary.blockers no trae exactamente los {_NO_CAP_COUNT} "
        f"bloqueantes sembrados -- sembrados: {blocker_ids!r}, presentes: "
        f"{[n.id for n in summary.blockers]!r}"
    )

    missing_from_render = [
        note_id for note_id in restriction_ids + blocker_ids if note_id not in rendered
    ]
    assert not missing_from_render, (
        f"boot.render() omite {len(missing_from_render)} de las "
        f"{2 * _NO_CAP_COUNT} notas sembradas -- el texto no puede recortar lo "
        f"que spec Sec.8.3 exige mostrar entero: {missing_from_render!r}"
    )


# ---------------------------------------------------------------------------
# Fila 3 -- un indice corrupto sale como aviso y el arranque SIGUE
# ---------------------------------------------------------------------------


def test_a_corrupted_index_is_shown_as_a_warning_and_boot_still_completes(
    boot, model, indexes, notes, health, tmp_repo, make_note, make_context
):
    """Fila 3 de Sec.9.5: un indice corrupto sale como aviso y el
    arranque SIGUE.

    Fallo real que previene: que un fichero de indice a medias deje la
    sesion entera sin memoria -- peor que el propio fichero roto es que
    el arranque reviente o calle en vez de avisar y continuar.

    Corrupcion REAL, no fabricada: se retira a mano (`indexes.remove`,
    misma tecnica que `test_health.py` fila 1) la linea de indice de una
    nota cuyo commit real sigue en git -- exactamente el hueco que un
    proceso muerto a mitad de una migracion dejaria.
    """
    root = Path(tmp_repo)
    zone = "bootcorruptzone"
    ctx = make_context(zone_names=(zone,))

    note_a = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_BOOTCORRUPT_A memo whose index line is deleted by hand",
    )
    note_b = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_BOOTCORRUPT_B memo that stays synced with its index line",
    )
    with _cwd(root):
        result_a = notes.write(note_a, ctx)
        result_b = notes.write(note_b, ctx)
    assert result_a.ok, f"seed de note_a fallo: {result_a.git_error or result_a.rejections}"
    assert result_b.ok, f"seed de note_b fallo: {result_b.git_error or result_b.rejections}"

    # "A mano": se retira la linea de indice de note_a sin tocar su
    # commit real en git -- `notes.pm_root(root)` es la MISMA ruta que
    # `notes.write()` uso de verdad para escribir MEMOS.md (ver docstring
    # del modulo, "COMO SE SIEMBRA"), no la raiz pelada del repo.
    with _cwd(root):
        indexes.remove(result_a.note_id, "MEMOS.md", notes.pm_root(root))

    with _cwd(root):
        expected_lineas, expected_notas, expected_discrepancias = health.coherence(root)
        summary = boot.build()  # NO debe lanzar pese al indice corrupto
        rendered = boot.render(summary)

    assert expected_discrepancias, (
        "comprobacion previa: la corrupcion a mano deberia producir una "
        f"discrepancia real de health.coherence({root!r}) -- salio vacio, el "
        "escenario de este test no se monto de verdad"
    )
    assert expected_lineas != expected_notas, (
        f"comprobacion previa: tras borrar una linea a mano, lineas "
        f"({expected_lineas}) y notas ({expected_notas}) deberian divergir"
    )

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary pese al indice corrupto -- "
        f"devolvio {type(summary)!r} (¿lanzo una excepcion en su lugar?)"
    )
    assert summary.health.index_lines == expected_lineas, (
        f"summary.health.index_lines ({summary.health.index_lines}) no "
        f"coincide con el numero real de health.coherence() ({expected_lineas})"
    )
    assert summary.health.git_notes == expected_notas, (
        f"summary.health.git_notes ({summary.health.git_notes}) no coincide "
        f"con el numero real de health.coherence() ({expected_notas})"
    )

    avisos_split = rendered.split("CHECKS", 1)
    assert len(avisos_split) == 2, (
        f"el render no trae ninguna seccion CHECKS -- un indice corrupto no "
        f"puede quedar callado:\n{rendered}"
    )
    avisos_block = avisos_split[1]
    assert "⚠️" in avisos_block, (
        f"con una discrepancia real de indice, el bloque CHECKS deberia "
        f"llevar un aviso (⚠️), no solo confirmaciones -- bloque CHECKS:\n"
        f"{avisos_block}"
    )
    numbers_fragment = f"{expected_lineas} lines / {expected_notas} notes"
    assert numbers_fragment in avisos_block, (
        f"el bloque CHECKS deberia mostrar los numeros REALES divergentes "
        f"({numbers_fragment!r}, mismo formato que TEXTOS.md Sec.3.1 usa para "
        f"el caso coherente) en vez de callarlos -- bloque CHECKS:\n{avisos_block}"
    )


# ---------------------------------------------------------------------------
# Fila 4 -- las horas llevan su etiqueta UTC
# ---------------------------------------------------------------------------


def test_context_and_generated_timestamps_carry_the_utc_label(
    boot, model, indexes, notes, context_mod, tmp_repo
):
    """Fila 4 de Sec.9.5: las horas llevan su etiqueta UTC.

    Fallo real que previene: dos maquinas leyendo la misma hora como dos
    horas distintas -- sin la etiqueta, una hora local y una UTC son
    indistinguibles a simple vista.

    Round-trip real [unmassk-standards Sec.34]: el (NEXT) de TEXTOS.md
    Sec.3.1 muestra "Context (cerrado <fecha> UTC):" con la fecha REAL
    del cierre -- se escribe un cierre de verdad con `context.write()`,
    se relee su timestamp real con `context.latest()` (la unica fuente
    de verdad, ya en produccion), y se comprueba que ESE valor -- nunca
    uno tecleado aqui -- aparece marcado UTC en el texto que produce
    `boot.render()`. El banner del encabezado (`generated_at`, la hora en
    que se LEYO el arranque) se comprueba contra el propio valor que
    `boot.build()` devolvio, por el mismo motivo: no se fabrica.
    """
    root = Path(tmp_repo)
    indexes.seed(notes.pm_root(root))

    ctx_note = model.ContextNote(
        headline="MARK_BOOTUTC_NEXT implement the change discussed for the UTC label",
        context="MARK_BOOTUTC point one, kept short on purpose",
        keys=("bootutc",),
        # marcador de posicion: el commit real de git es la fuente de
        # verdad, no este campo -- mismo patron que context.py documenta
        # para `ContextNote.timestamp`.
        timestamp=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    with _cwd(root):
        write_result = context_mod.write(ctx_note)
    assert write_result.ok, f"seed del cierre de sesion fallo: {write_result.git_error}"

    with _cwd(root):
        real_context = context_mod.latest()
    assert real_context is not None, (
        "context.latest() devolvio None justo despues de escribir un cierre real"
    )

    with _cwd(root):
        summary = boot.build()
        rendered = boot.render(summary)

    assert summary.context is not None, (
        "summary.context es None pese a que context.write() dejo un cierre real"
    )
    assert summary.context.timestamp == real_context.timestamp, (
        f"summary.context.timestamp ({summary.context.timestamp!r}) no coincide "
        f"con el timestamp real de context.latest() ({real_context.timestamp!r}) "
        "-- boot.build() no esta leyendo el cierre real"
    )

    # `context.latest()` devuelve el timestamp con el offset LOCAL del
    # autor de git (p.ej. +02:00), nunca normalizado -- verificado en
    # vivo antes de escribir este test. La propia fila exige la
    # ETIQUETA UTC, que solo tiene sentido si el valor mostrado esta
    # normalizado a UTC de verdad (si no, un commit hecho a la 01:00
    # +02:00 -- las 23:00 UTC del dia anterior -- se etiquetaria "UTC"
    # con la fecha LOCAL, la misma mentira que esta fila existe para
    # impedir). Por eso el dia esperado se deriva aqui con
    # `.astimezone(timezone.utc)`, nunca del offset crudo.
    context_day = real_context.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d")
    context_lines = [line for line in rendered.splitlines() if "Context (cerrado" in line]
    assert context_lines, (
        f"ninguna linea del render trae 'Context (cerrado' (TEXTOS.md Sec.3.1) "
        f"pese a que hay un context real:\n{rendered}"
    )
    assert any(context_day in line and "UTC" in line for line in context_lines), (
        f"la linea de Context deberia llevar la fecha real ({context_day!r}) "
        f"junto a la etiqueta UTC en la misma linea, sin ella una hora local y "
        f"una UTC son indistinguibles -- lineas de Context encontradas: "
        f"{context_lines!r}"
    )

    # Mismo motivo que context_day arriba: si `generated_at` llegara con
    # offset local en vez de UTC, comparar contra el crudo ocultaria
    # justo el fallo que esta fila prueba.
    generated_day = summary.generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    banner_lines = rendered.splitlines()[:5]
    assert any(generated_day in line and "UTC" in line for line in banner_lines), (
        f"el encabezado del arranque (primeras lineas del render) deberia "
        f"llevar generated_at ({generated_day!r}) marcado UTC -- primeras "
        f"lineas: {banner_lines!r}"
    )


# ---------------------------------------------------------------------------
# El vigilante mudo -- hallazgo de Cerberus (2026-08-02): `health.coherence_rules()`
# funciona, esta en produccion y tiene sus 5 tests en verde
# (`test_health.py`), pero no llega a ninguna parte: `model.HealthReport`
# no tiene sitio para sus dos numeros, `health.build()` la excluye a
# proposito por eso, y `boot.py` nunca la pinta en el bloque CHECKS. Mismo
# patron que ya costo caro en la capa 1 (seis hooks en version vieja, tests
# en verde, nadie avisado).
#
# Tres filas -- las tres viven aqui porque las tres son sobre boot.py (la
# cuarta fila del encargo, sobre HealthReport, vive en
# `test_health.py::test_health_report_carries_the_real_rule_coherence_numbers`).
# Ninguna toca produccion. Las tres empiezan comprobando directamente
# `summary.health.rule_commits`/`rule_lines` -- eso es lo que hace que el
# rojo sea por su causa REAL (los campos no existen todavia, `AttributeError`),
# no solo un texto ausente en el render.
#
# DECISION DE TEXTO [no fijada en TEXTOS.md Sec.3.1 -- esa fila no existe
# ahi todavia; se decide aqui, con el mismo patron literal que ya usa el
# arranque para las otras dos confirmaciones]: una tercera linea en CHECKS,
# junto a "no duplicate IDs" e "indices coherentes con git" --
#
#     Y  rules match git (N lineas / M commits)
#     O  rules do not match git (N lineas / M commits)
#
# mismo formato que la linea de indices (`{lineas} lineas / {notas} notas`),
# cambiando "indices"->"reglas" y "notas"->"commits". Los tests de aqui
# comprueban el contenido (la palabra "reglas", el simbolo correcto, los
# numeros reales) sin fijar el texto letra por letra -- si Ultron elige otra
# redaccion, solo esas comprobaciones puntuales cambian, no el test entero
# [mismo criterio que el supuesto 4 de test_health.py].
# ---------------------------------------------------------------------------


def test_avisos_block_paints_rule_coherence_alongside_the_other_two_checks(
    boot, model, indexes, notes, health, rules, tmp_repo
):
    """Fila 2 del encargo: el arranque pinta los numeros de reglas en su
    bloque CHECKS, JUNTO a los otros dos chequeos que ya salen ahi ('IDs
    sin duplicados' / 'indices coherentes con git').

    Estado simple y sano: una sola regla real, coherente. El fallo real
    que esta fila previene es de CABLEADO, no de calculo -- coherence_rules()
    ya funciona; lo que falta es que boot.build()/boot.render() la lean y
    la pinten junto a las otras dos.
    """
    root = Path(tmp_repo)
    marker = "MARK_BOOTRULES_ROW2 unica regla real, coherente, para probar el cableado"

    with _cwd(root):
        indexes.seed(notes.pm_root(root))  # boot.build() cruza coherence()/duplicates() tambien
        result = rules.add(marker, "user")
        assert result.ok, f"add() fallo inesperadamente: {result.git_error}"
        expected_commits, expected_lineas, _ = health.coherence_rules(root)
        summary = boot.build()
        rendered = boot.render(summary)

    assert summary.health.rule_commits == expected_commits, (
        f"summary.health.rule_commits no coincide con el commits real de "
        f"coherence_rules() ({expected_commits!r}) -- sin este campo el "
        "arranque no tiene de donde pintar la linea de reglas"
    )
    assert summary.health.rule_lines == expected_lineas, (
        f"summary.health.rule_lines no coincide con el lineas real de "
        f"coherence_rules() ({expected_lineas!r})"
    )

    avisos_split = rendered.split("CHECKS", 1)
    assert len(avisos_split) == 2, f"el render no trae ninguna seccion CHECKS:\n{rendered}"
    avisos_block = avisos_split[1]

    assert "no duplicate IDs" in avisos_block, (
        f"el chequeo de IDs, que ya sale hoy en CHECKS, deberia seguir ahi "
        f"junto al nuevo de reglas:\n{avisos_block}"
    )
    assert (
        "indexes match git" in avisos_block
        or "indexes do not match git" in avisos_block
    ), (
        f"el chequeo de indices, que ya sale hoy en CHECKS, deberia seguir "
        f"ahi junto al nuevo de reglas:\n{avisos_block}"
    )
    assert "rules" in avisos_block, (
        f"ninguna linea de CHECKS menciona las reglas -- coherence_rules() "
        f"existe y esta en verde (test_health.py), pero boot.render() no la "
        f"pinta junto a los otros dos chequeos:\n{avisos_block}"
    )
    assert str(expected_lineas) in avisos_block and str(expected_commits) in avisos_block, (
        f"los numeros reales de coherence_rules() (lineas={expected_lineas}, "
        f"commits={expected_commits}) no aparecen en el bloque CHECKS:\n{avisos_block}"
    )


def test_avisos_block_shows_the_real_rule_count_when_everything_is_fine(
    boot, model, indexes, notes, health, rules, tmp_repo
):
    """Fila 3 del encargo: los numeros de reglas salen TAMBIEN cuando todo
    esta bien, con su numero real -- no solo al fallar. Es la leccion ya
    escrita en la ficha de `coherence()`/`coherence_rules()`: un chequeo
    que solo habla cuando falla es indistinguible de uno que no se ejecuta.

    Se siembran TRES reglas coherentes (no una) para que el numero
    comprobado no coincida por casualidad con un 0 o un 1 por defecto --
    mismo criterio que
    `test_health.py::test_coherence_rules_fully_coherent_multiple_rules_reports_the_real_numbers_not_silence`.
    """
    root = Path(tmp_repo)
    markers = (
        ("MARK_BOOTRULES_ROW3_A primera de tres reglas reales", "user"),
        ("MARK_BOOTRULES_ROW3_B segunda de tres reglas reales", "claude"),
        ("MARK_BOOTRULES_ROW3_C tercera de tres reglas reales", "user"),
    )

    with _cwd(root):
        indexes.seed(notes.pm_root(root))  # boot.build() cruza coherence()/duplicates() tambien
        for text, kind in markers:
            result = rules.add(text, kind)
            assert result.ok, f"add({text!r}, {kind!r}) fallo: {result.git_error}"
        expected_commits, expected_lineas, expected_discrepancias = health.coherence_rules(root)
        summary = boot.build()
        rendered = boot.render(summary)

    assert expected_discrepancias == (), (
        "comprobacion previa: con las tres reglas sincronizadas no deberia "
        f"haber ninguna discrepancia, salieron: {expected_discrepancias!r}"
    )
    assert expected_commits == 3 and expected_lineas == 3, (
        f"comprobacion previa: deberian salir los tres commits/lineas "
        f"reales, salio commits={expected_commits}, lineas={expected_lineas}"
    )

    assert summary.health.rule_commits == 3, (
        f"summary.health.rule_commits deberia ser 3 (las tres reglas reales "
        f"sembradas) -- un chequeo mudo devolveria 0 o un numero por "
        "defecto, nunca el real"
    )
    assert summary.health.rule_lines == 3, (
        "summary.health.rule_lines deberia ser 3, mismo criterio que "
        "rule_commits arriba"
    )

    avisos_block = rendered.split("CHECKS", 1)[1]
    assert "✓" in avisos_block, (
        f"con las reglas coherentes deberia aparecer al menos una "
        f"confirmacion junto a las que ya salen hoy en CHECKS:\n{avisos_block}"
    )
    assert "rules" in avisos_block and "3" in avisos_block, (
        f"la linea de reglas deberia mostrar el numero real (3), no callar "
        f"solo porque todo esta bien:\n{avisos_block}"
    )


def test_a_rule_line_deleted_by_hand_is_shown_as_a_warning_at_boot_end_to_end(
    boot, model, indexes, notes, health, rules, tmp_repo
):
    """Fila 4 del encargo, la que de verdad importa: con una regla perdida
    de VERDAD -- se le borra la linea del fichero dejando el commit -- el
    arranque LO DICE. Fallo real reproducido de punta a punta: el mismo
    hueco que un proceso muerto entre las dos escrituras de `rules.add()`
    dejaria, exactamente lo que `coherence_rules()` se escribio para cazar
    [hallazgo de Cerberus, 2026-08-02].
    """
    root = Path(tmp_repo)
    marker = "MARK_BOOTRULES_ROW4 regla cuya linea se borra a mano tras commitear"

    with _cwd(root):
        indexes.seed(notes.pm_root(root))  # boot.build() cruza coherence()/duplicates() tambien
        result = rules.add(marker, "user")
        assert result.ok, f"add() fallo inesperadamente: {result.git_error}"

    _delete_rule_line_by_hand(rules, root, marker)

    with _cwd(root):
        expected_commits, expected_lineas, expected_discrepancias = health.coherence_rules(root)
        summary = boot.build()  # NO debe lanzar pese a la regla perdida
        rendered = boot.render(summary)

    assert expected_discrepancias, (
        "comprobacion previa: borrar la linea a mano deberia producir una "
        f"discrepancia real de health.coherence_rules({root!r}) -- salio "
        "vacio, el escenario de este test no se monto de verdad"
    )
    assert expected_commits != expected_lineas, (
        f"comprobacion previa: tras borrar la linea a mano, commits "
        f"({expected_commits}) y lineas ({expected_lineas}) deberian divergir"
    )

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary pese a la regla perdida "
        f"-- devolvio {type(summary)!r} (¿lanzo una excepcion en su lugar?)"
    )
    assert summary.health.rule_commits == expected_commits, (
        f"summary.health.rule_commits no coincide con el commits real de "
        f"coherence_rules() ({expected_commits!r})"
    )
    assert summary.health.rule_lines == expected_lineas, (
        f"summary.health.rule_lines no coincide con el lineas real de "
        f"coherence_rules() ({expected_lineas!r})"
    )

    avisos_block = rendered.split("CHECKS", 1)[1]
    assert "⚠️" in avisos_block, (
        f"con una regla perdida de verdad, el bloque CHECKS deberia llevar "
        f"un aviso, no solo confirmaciones:\n{avisos_block}"
    )
    assert "rules" in avisos_block, (
        f"ninguna linea de CHECKS menciona las reglas tras perder una de "
        f"verdad:\n{avisos_block}"
    )
    assert str(expected_lineas) in avisos_block and str(expected_commits) in avisos_block, (
        f"los numeros reales divergentes de coherence_rules() (lineas="
        f"{expected_lineas}, commits={expected_commits}) no aparecen en "
        f"CHECKS:\n{avisos_block}"
    )


# ---------------------------------------------------------------------------
# El choque con health.build() -- ver docstring del modulo, "EL CHOQUE CON
# health.build()". No es una de las cuatro filas de la tabla; la exige el
# encargo explicitamente porque, sin ella, el arranque no puede existir.
# ---------------------------------------------------------------------------


def test_id_duplicate_line_requires_a_real_composed_health_report(
    boot, model, indexes, notes, health, tmp_repo, make_note, make_context
):
    """El arranque necesita un `HealthReport` entero (Sec.9.5, "Que NO
    hace": "no calcula salud (llama a health)") y `health.build()` -- la
    unica funcion de Sec.9.4 que lo compondria -- no existe todavia. Sin
    ella, `boot.build()` no tiene de donde sacar `summary.health`, y la
    linea "no duplicate IDs (N notas)" de TEXTOS.md Sec.3.1 no se puede
    producir. Esta fila no implementa `health.build()` -- lo hace Ultron.

    Round-trip real: los numeros esperados salen de llamar aqui mismo a
    `health.coherence()`/`health.duplicates()` (Sec.9.4, ya en
    produccion), nunca tecleados.
    """
    root = Path(tmp_repo)
    zone = "boothealthzone"
    ctx = make_context(zone_names=(zone,))

    note_a = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_BOOTHEALTH_A first real memo for the health.build() gap",
    )
    note_b = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_BOOTHEALTH_B second real memo for the health.build() gap",
    )
    with _cwd(root):
        result_a = notes.write(note_a, ctx)
        result_b = notes.write(note_b, ctx)
    assert result_a.ok, f"seed de note_a fallo: {result_a.git_error or result_a.rejections}"
    assert result_b.ok, f"seed de note_b fallo: {result_b.git_error or result_b.rejections}"

    with _cwd(root):
        expected_lineas, expected_notas, expected_discrepancias = health.coherence(root)
        expected_duplicates = health.duplicates(root)
        summary = boot.build()
        rendered = boot.render(summary)

    assert expected_discrepancias == (), (
        "comprobacion previa: con dos notas sincronizadas no deberia haber "
        f"ninguna discrepancia, salieron: {expected_discrepancias!r}"
    )
    assert expected_duplicates == (), (
        f"comprobacion previa: dos notas con id autoasignado no deberian "
        f"colisionar, salieron: {expected_duplicates!r}"
    )

    assert isinstance(summary.health, model.HealthReport), (
        f"summary.health no es un HealthReport real, es {type(summary.health)!r} "
        "-- health.build() (Sec.9.4) no existe todavia: sin ella boot.build() no "
        "puede componer el informe de salud que el arranque necesita"
    )
    assert summary.health.duplicate_ids == expected_duplicates, (
        f"summary.health.duplicate_ids ({summary.health.duplicate_ids!r}) no "
        f"coincide con el resultado real de health.duplicates() "
        f"({expected_duplicates!r})"
    )
    assert summary.health.index_lines == expected_lineas, (
        f"summary.health.index_lines ({summary.health.index_lines}) no "
        f"coincide con el numero real de health.coherence() ({expected_lineas})"
    )
    assert summary.health.git_notes == expected_notas, (
        f"summary.health.git_notes ({summary.health.git_notes}) no coincide "
        f"con el numero real de health.coherence() ({expected_notas})"
    )

    expected_line = f"no duplicate IDs ({expected_notas} notes)"
    assert expected_line in rendered, (
        f"el render no trae la linea real {expected_line!r} (TEXTOS.md "
        f"Sec.3.1) -- sin health.build() componiendo summary.health con los "
        f"numeros reales, esta linea no se puede producir:\n{rendered}"
    )


# ---------------------------------------------------------------------------
# Regresiones de Argus (2026-08-02) sobre cuatro fallos YA ARREGLADOS y sin
# ninguna red que los proteja -- Ultron los dejo senalados como hueco al
# cerrarlos. Los cuatro se demostraron ejecutando (guiones `argus_*.py`),
# nunca supuestos por lectura de codigo. Ninguno toca produccion: los
# cuatro pasan hoy contra el codigo real, sin tocarlo.
# ---------------------------------------------------------------------------


def test_a_repo_where_indexes_seed_never_ran_boots_without_crashing(boot, model, tmp_repo):
    """Bug 1 -- el arranque reventaba en un proyecto recien instalado.

    Distinto de `test_empty_memory_shows_explicit_loud_zeros_not_absent_sections`
    (fila 1 de Sec.9.5, que llama a `indexes.seed()` antes de arrancar):
    aqui NO se llama a `indexes.seed()` ni a `notes.write()` -- el estado
    real del PRIMER `boot.build()` de cualquier proyecto (TEXTOS.md
    Sec.3.2), antes de que exista siquiera `.claude/project-memory/`.

    Fallo real, demostrado ejecutando (`argus_fresh_project_crash.py`)
    antes de que `indexes.archived_ids()` descontara un `ARCHIVED.md`
    ausente: `boot.build()` reventaba con `FileNotFoundError` en vez de
    devolver la pantalla de proyecto nuevo -- lo primero que veias al
    abrir sesion en un proyecto nuevo era un error de Python.
    """
    root = Path(tmp_repo)
    pm_root = root / ".claude" / "project-memory"
    assert not pm_root.exists(), (
        f"comprobacion previa: {pm_root} ya existe -- el escenario no es "
        "genuinamente fresco, este test no prueba lo que dice probar"
    )

    with _cwd(root):
        summary = boot.build()  # NO debe lanzar
        rendered = boot.render(summary)

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary, devolvio {type(summary)!r} "
        "-- ¿lanzo una excepcion en su lugar?"
    )
    assert summary.restrictions == (), (
        f"un proyecto sin project-memory/ no deberia tener restricciones, "
        f"salio {summary.restrictions!r}"
    )
    assert summary.blockers == (), (
        f"un proyecto sin project-memory/ no deberia tener bloqueantes, "
        f"salio {summary.blockers!r}"
    )
    assert summary.health.index_lines == 0 and summary.health.git_notes == 0, (
        "los ocho indices no existen todavia -- deberian contar como cero, "
        f"no reventar: index_lines={summary.health.index_lines!r}, "
        f"git_notes={summary.health.git_notes!r}"
    )

    assert _ZERO_BLOCKERS_LITERAL in rendered, (
        f"el literal exacto de TEXTOS.md Sec.3.2 para bloqueantes en cero no "
        f"aparece:\n{rendered}"
    )
    assert _ZERO_RESTRICTIONS_LITERAL in rendered, (
        f"el literal exacto de TEXTOS.md Sec.3.2 para restricciones en cero "
        f"no aparece:\n{rendered}"
    )


def test_boot_survives_a_real_gh_failure_and_shows_it_as_a_warning_line(
    boot, model, notes, tmp_repo
):
    """Bug 2 -- un fallo de red tumbaba el arranque entero.

    Fallo real que previene: la excepcion de `plans_unreflected()` (una
    nota/commit de trabajo cita una issue, `gh` falla al consultarla) se
    llevaba por delante TODO el arranque -- el Next, los bloqueantes, las
    restricciones, todo. Lo que mas importa: nunca se inventa un cero en
    su lugar -- decir "todo correcto" porque no se pudo mirar es la
    mentira exacta que este sistema existe para impedir.

    Sin mock: `tmp_repo` es un repo git real recien creado sin remoto de
    GitHub -- `gh issue view` contra el falla YA, de verdad (mismo hecho
    verificado en vivo que `test_health.py::
    test_gh_failure_raises_instead_of_reporting_all_clear`).
    """
    root = Path(tmp_repo)
    issue_number = 999999999
    file_path = root / "work_1.txt"
    file_path.write_text("MARK_BOOTGH work committed while gh is unreachable", encoding="utf-8")

    with _cwd(root):
        write_result = notes.write_work(
            "trabajo citando una issue que gh no puede resolver",
            [file_path],
            issue_number,
        )
    assert write_result.ok, f"seed del commit de trabajo fallo: {write_result.git_error}"

    with _cwd(root):
        summary = boot.build()  # NO debe lanzar pese al fallo real de gh
        rendered = boot.render(summary)

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary pese al fallo real de gh -- "
        f"devolvio {type(summary)!r} (¿lanzo una excepcion en su lugar?)"
    )
    assert summary.health.plans_unreflected == (), (
        "con gh fallando no hay forma de saber que esta sin reflejar -- "
        f"deberia quedar vacio, no un cero inventado: {summary.health.plans_unreflected!r}"
    )
    assert summary.health.plans_unreflected_error is not None, (
        "el motivo real del fallo de gh deberia quedar en "
        "plans_unreflected_error -- salio None, indistinguible de 'no habia "
        "nada que consultar'"
    )
    assert str(issue_number) in summary.health.plans_unreflected_error, (
        f"el motivo real deberia nombrar la issue #{issue_number} -- salio "
        f"{summary.health.plans_unreflected_error!r}"
    )

    avisos_split = rendered.split("CHECKS", 1)
    assert len(avisos_split) == 2, f"el render no trae ninguna seccion CHECKS:\n{rendered}"
    avisos_block = avisos_split[1]
    assert "no se pudo comprobar" in avisos_block, (
        f"el fallo de gh deberia salir como una linea de aviso explicita, "
        f"nunca en silencio:\n{avisos_block}"
    )
    assert str(issue_number) in avisos_block, (
        f"la linea de aviso deberia nombrar la issue real #{issue_number}:\n"
        f"{avisos_block}"
    )
    # El resto del informe de salud sigue siendo real -- el fallo de gh no
    # tumba los otros dos chequeos.
    assert "no duplicate IDs" in avisos_block or "duplicate IDs" in avisos_block, (
        f"el chequeo de IDs deberia seguir corriendo pese al fallo de gh:\n"
        f"{avisos_block}"
    )


def test_avisos_names_the_specific_note_when_an_archived_lines_separator_becomes_unparseable(
    boot, model, indexes, notes, tmp_repo, make_note, make_context
):
    """Bug 3 -- un muro retirado podia resucitar sin ninguna marca.

    Fallo real que previene: `indexes.read_archive()` descarta en
    silencio cualquier linea que no reconoce (mismo contrato que
    `read()`) -- una edicion a mano de `ARCHIVED.md` (un separador
    distinto, por ejemplo) hace que esa nota deje de contar como
    archivada y reaparezca como restriccion viva, SIN marca. El arreglo
    no es impedir la reaparicion (el dato de la linea rota se sigue
    tirando, por diseno) sino que `health.coherence()`/`boot.build()`
    SIGUEN viendo esa nota en git y ausente de los indices vigentes, asi
    que la discrepancia sale nombrando la nota concreta en CHECKS --
    "el dato existia y se tiraba", ahora se avisa en vez de callarse.

    Archivado real (`indexes.remove()` + `indexes.archive()`, mismo
    patron que `test_health.py::
    test_coherence_does_not_false_alarm_on_a_legitimately_archived_note`),
    corrupcion real (se reescribe el separador literal de
    `format_lines.build_archive_line` a mano, exactamente como dejaria
    una edicion manual del fichero).
    """
    from datetime import date

    root = Path(tmp_repo)
    zone = "bootphantomzone"
    ctx = make_context(zone_names=(zone,))

    restriction = make_note(
        type="R",
        zone1=zone,
        zone2=zone,
        headline="MARK_BOOTPHANTOM never deploy on friday afternoon, it breaks prod",
        why="MARK_BOOTPHANTOM_WHY last time it cost a weekend",
    )
    with _cwd(root):
        write_result = notes.write(restriction, ctx)
    assert write_result.ok, (
        f"seed de la restriccion fallo: {write_result.git_error or write_result.rejections}"
    )
    note_id = write_result.note_id

    with _cwd(root):
        indexes.remove(note_id, "RESTRICTIONS.md", notes.pm_root(root))
        indexes.archive(
            model.ArchiveLine(
                date=date(2026, 8, 2),
                type="R",
                id=note_id,
                zone1=zone,
                zone2=zone,
                headline=restriction.headline,
                destination="closed",
                destination_detail="MARK_BOOTPHANTOM_DETAIL deploy process changed, no longer applies",
            ),
            notes.pm_root(root),
        )

    with _cwd(root):
        summary_archived = boot.build()
    assert note_id not in [n.id for n in summary_archived.restrictions], (
        "comprobacion previa: recien archivada de verdad, la restriccion no "
        f"deberia salir todavia -- {note_id!r} aparece en "
        f"{[n.id for n in summary_archived.restrictions]!r}"
    )

    archive_path = notes.pm_root(root) / "ARCHIVED.md"
    content = archive_path.read_text(encoding="utf-8")
    assert "  →  " in content, (
        "comprobacion previa: el separador literal de build_archive_line no "
        f"aparece en ARCHIVED.md, no se puede montar la corrupcion:\n{content!r}"
    )
    corrupted = content.replace("  →  ", "  ->  ")
    archive_path.write_text(corrupted, encoding="utf-8")

    with _cwd(root):
        summary = boot.build()  # NO debe lanzar pese a la linea corrupta
        rendered = boot.render(summary)

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary pese a la linea de archivo "
        f"corrupta -- devolvio {type(summary)!r}"
    )
    assert any(note_id in d for d in summary.health.index_discrepancies), (
        f"con la linea de {note_id!r} en ARCHIVED.md vuelta ilegible, "
        "health debe nombrar esa nota concreta como discrepancia -- salieron: "
        f"{summary.health.index_discrepancies!r}"
    )

    avisos_split = rendered.split("CHECKS", 1)
    assert len(avisos_split) == 2, f"el render no trae ninguna seccion CHECKS:\n{rendered}"
    avisos_block = avisos_split[1]
    assert "⚠️" in avisos_block, (
        f"con una discrepancia real, CHECKS deberia llevar un aviso, no solo "
        f"confirmaciones:\n{avisos_block}"
    )
    assert note_id in avisos_block, (
        f"CHECKS deberia nombrar la nota concreta ({note_id!r}), no solo "
        f"decir 'algo diverge':\n{avisos_block}"
    )


def test_recuentos_label_says_planes_con_acta_not_issues_abiertas(
    boot, model, indexes, notes, tmp_repo, make_note, make_context
):
    """Bug 4 -- el recuento de planes mentia bajo la etiqueta "issues
    abiertas".

    Fallo real que previene: el numero nunca pregunta a GitHub, solo
    cuenta actas de plan LOCALES sin archivar -- con la etiqueta vieja
    podia decir "0" con una issue real todavia abierta (acta archivada
    por limpieza rutinaria) o "1" con la issue ya cerrada hace meses
    (acta nunca archivada). El arreglo es el ROTULO, no el calculo:
    `_recuentos_block()` pinta "plans with a record ....." en vez de "issues
    abiertas", que es lo que el numero mide de verdad.

    Round-trip real [unmassk-standards Sec.34]: se escribe un acta real
    con `issue=47`, se archiva de verdad (`indexes.remove()` +
    `indexes.archive()`), y se comprueba que el numero baja a 0 aunque
    GitHub nunca se toco -- exactamente el hallazgo de
    `argus_open_issues_lie.py`.
    """
    from datetime import date

    root = Path(tmp_repo)
    zone = "bootissueszone"
    ctx = make_context(zone_names=(zone,))

    acta = make_note(
        type="M",
        zone1=zone,
        zone2=zone,
        headline="MARK_BOOTISSUES acta de plan for issue 47 tracking",
        issue=47,
    )
    with _cwd(root):
        write_result = notes.write(acta, ctx)
    assert write_result.ok, (
        f"seed del acta fallo: {write_result.git_error or write_result.rejections}"
    )
    note_id = write_result.note_id

    with _cwd(root):
        summary_before = boot.build()
        rendered_before = boot.render(summary_before)

    assert summary_before.open_issues == 1, (
        f"comprobacion previa: un acta vigente con issue deberia contar como "
        f"1, salio {summary_before.open_issues!r}"
    )
    assert "issues abiertas" not in rendered_before, (
        "la etiqueta vieja mentia -- este numero nunca pregunta a GitHub, "
        f"solo cuenta actas locales sin archivar:\n{rendered_before}"
    )
    assert "plans with a record" in rendered_before, (
        f"la etiqueta real ('plans with a record', que es lo que el numero mide "
        f"de verdad) no aparece:\n{rendered_before}"
    )

    with _cwd(root):
        indexes.remove(note_id, "MEMOS.md", notes.pm_root(root))
        indexes.archive(
            model.ArchiveLine(
                date=date(2026, 8, 2),
                type="M",
                id=note_id,
                zone1=zone,
                zone2=zone,
                headline=acta.headline,
                destination="closed",
                destination_detail="MARK_BOOTISSUES_DETAIL acta superseded, routine cleanup",
            ),
            notes.pm_root(root),
        )
        summary_after = boot.build()
        rendered_after = boot.render(summary_after)

    assert summary_after.open_issues == 0, (
        "el acta se archivo por limpieza rutinaria, sin tocar GitHub -- el "
        f"numero LOCAL deberia bajar a 0, salio {summary_after.open_issues!r} "
        "(si no baja, el calculo dejo de ser el que argus_open_issues_lie.py "
        "demostro)"
    )
    assert "issues abiertas" not in rendered_after, (
        f"la etiqueta vieja no deberia aparecer tampoco tras archivar:\n"
        f"{rendered_after}"
    )
    assert "plans with a record" in rendered_after, (
        f"la etiqueta real deberia seguir ahi con su numero real (0):\n"
        f"{rendered_after}"
    )


# ---------------------------------------------------------------------------
# Ronda 2 (Moriarty) -- tres arreglos mas, ya hechos, sin ninguna red que
# los proteja. Los tres se demostraron ejecutando (docstrings de
# boot.py/health.py/context.py, "hallazgo N de Moriarty, ronda 2"). Ninguno
# toca produccion: los tres pasan hoy contra el codigo real, sin tocarlo.
# ---------------------------------------------------------------------------


def test_avisos_shows_warning_not_checkmark_when_index_counts_match_but_content_differs(
    boot, model, indexes, notes, health, tmp_repo, make_note, make_context, vocabulary
):
    """Hallazgo 1 de Moriarty, ronda 2 -- "el visto bueno que mentia": el
    ✓/⚠️ de indices comparaba solo `lineas == notas` (dos numeros que
    pueden coincidir aunque el CONTENIDO diverja) en vez de si hay
    discrepancias reales -- salia '✓  indices coherentes con git (2
    lineas / 2 notas)' y, justo debajo, el detalle de por que no lo eran.

    Se monta el caso que lo demuestra: se retira a mano la linea real de
    note_a (commiteada) Y se inserta a mano una linea bogus que nunca se
    commiteo -- el CONTEO de lineas de indice vuelve a igualar al de
    notas en git (2 == 2, "una linea por otra"), pero el contenido
    diverge en los dos sentidos.
    """
    root = Path(tmp_repo)
    zone = "bootlyingcheck"
    ctx = make_context(zone_names=(zone,))

    note_a = make_note(
        type="M", zone1=zone, zone2=zone,
        headline="MARK_LYING_A note whose index line gets swapped for a bogus one",
    )
    note_b = make_note(
        type="M", zone1=zone, zone2=zone,
        headline="MARK_LYING_B note that stays synced throughout",
    )
    with _cwd(root):
        result_a = notes.write(note_a, ctx)
        result_b = notes.write(note_b, ctx)
    assert result_a.ok, f"seed de note_a fallo: {result_a.git_error or result_a.rejections}"
    assert result_b.ok, f"seed de note_b fallo: {result_b.git_error or result_b.rejections}"

    with _cwd(root):
        index_name, _line = _index_line_for(indexes, vocabulary, notes.pm_root(root), result_a.note_id)
    assert index_name is not None, f"{result_a.note_id!r} no aparece en ningun indice tras sembrarla"

    bogus_id = "M-999999"
    bogus_line = model.IndexLine(
        id=bogus_id, zone1=zone, zone2=zone,
        headline="MARK_LYING_BOGUS line inserted by hand, never committed to git",
    )
    with _cwd(root):
        indexes.remove(result_a.note_id, index_name, notes.pm_root(root))
        indexes.insert(bogus_line, index_name, notes.pm_root(root))

    with _cwd(root):
        expected_lineas, expected_notas, expected_discrepancias = health.coherence(root)
        summary = boot.build()
        rendered = boot.render(summary)

    assert expected_lineas == expected_notas, (
        "comprobacion previa: tras cambiar una linea por otra, los NUMEROS "
        f"deberian volver a cuadrar (lineas={expected_lineas}, "
        f"notas={expected_notas}) -- si no cuadran, este test no monta el "
        "escenario que el hallazgo describe"
    )
    assert expected_discrepancias, (
        "comprobacion previa: pese a que los numeros cuadran, el CONTENIDO "
        "diverge -- deberia haber discrepancias reales, salio vacio"
    )
    assert any(result_a.note_id in d for d in expected_discrepancias), (
        f"ninguna discrepancia nombra a {result_a.note_id!r} (deberia faltar "
        f"en el indice): {expected_discrepancias!r}"
    )
    assert any(bogus_id in d for d in expected_discrepancias), (
        f"ninguna discrepancia nombra a {bogus_id!r} (no deberia existir en "
        f"git): {expected_discrepancias!r}"
    )

    avisos_block = rendered.split("CHECKS", 1)[1]
    assert "indexes do not match git" in avisos_block, (
        f"con los numeros cuadrando pero el contenido divergiendo, CHECKS "
        f"deberia decir 'indices no coherentes con git', no callarlo:\n"
        f"{avisos_block}"
    )
    assert "indexes match git" not in avisos_block, (
        f"el visto bueno afirmativo ('indices coherentes con git', sin 'no') "
        f"no deberia aparecer -- los numeros cuadran mintiendo, el contenido "
        f"no:\n{avisos_block}"
    )


def test_avisos_shows_warning_not_checkmark_for_rules_when_counts_match_but_content_differs(
    boot, model, indexes, notes, health, rules, emojis, tmp_repo
):
    """Mismo hallazgo 1 de Moriarty, ronda 2, aplicado a las reglas: se
    sustituye a mano la linea de fichero de una regla real por una linea
    bogus (mismo formato exacto, nunca commiteada) -- el numero de
    lineas del fichero vuelve a igualar al de commits reales (2 == 2),
    pero el contenido diverge en los dos sentidos.

    Ademas comprueba que la discrepancia se NOMBRA en CHECKS -- antes del
    "Revision ronda 2, punto 1" (docstring de health.py), el tercer valor
    de `coherence_rules()` se calculaba y se tiraba: `build()` nunca lo
    guardaba en `HealthReport`, asi que aunque el chequeo detectara la
    divergencia por dentro, nada de eso llegaba a pintarse.
    """
    root = Path(tmp_repo)
    marker_a = "MARK_LYING_RULE_A regla real cuya linea de fichero se sustituye"
    marker_b = "MARK_LYING_RULE_B regla real que se queda igual"
    bogus_text = "MARK_LYING_RULE_BOGUS linea de fichero anadida a mano, sin commit real"

    with _cwd(root):
        indexes.seed(notes.pm_root(root))  # boot.build() cruza coherence()/duplicates() tambien
        result_a = rules.add(marker_a, "user")
        result_b = rules.add(marker_b, "user")
    assert result_a.ok, f"add(marker_a) fallo: {result_a.git_error}"
    assert result_b.ok, f"add(marker_b) fallo: {result_b.git_error}"

    _swap_rule_line_by_hand(rules, emojis, root, marker_a, bogus_text)

    with _cwd(root):
        expected_commits, expected_lineas, expected_discrepancias = health.coherence_rules(root)
        summary = boot.build()
        rendered = boot.render(summary)

    assert expected_commits == expected_lineas, (
        "comprobacion previa: tras cambiar una linea por otra, los NUMEROS "
        f"deberian volver a cuadrar (commits={expected_commits}, "
        f"lineas={expected_lineas}) -- si no cuadran, este test no monta el "
        "escenario que el hallazgo describe"
    )
    assert expected_discrepancias, (
        "comprobacion previa: pese a que los numeros cuadran, el CONTENIDO "
        "diverge -- deberia haber discrepancias reales, salio vacio"
    )
    assert any(marker_a in d for d in expected_discrepancias), (
        f"ninguna discrepancia nombra la regla real sustituida: "
        f"{expected_discrepancias!r}"
    )
    assert any(bogus_text in d for d in expected_discrepancias), (
        f"ninguna discrepancia nombra la linea bogus sin commit: "
        f"{expected_discrepancias!r}"
    )

    avisos_block = rendered.split("CHECKS", 1)[1]
    assert "rules do not match git" in avisos_block, (
        f"con los numeros cuadrando pero el contenido divergiendo, CHECKS "
        f"deberia decir 'rules do not match git', no callarlo:\n"
        f"{avisos_block}"
    )
    assert "rules match git" not in avisos_block, (
        f"el visto bueno afirmativo ('rules match git', sin 'no') "
        f"no deberia aparecer -- los numeros cuadran mintiendo, el contenido "
        f"no:\n{avisos_block}"
    )
    assert marker_a in avisos_block or bogus_text in avisos_block, (
        "la discrepancia de reglas deberia NOMBRARSE en CHECKS, no solo "
        f"cambiar el simbolo -- antes se calculaba y se tiraba (build() no "
        f"guardaba el tercer valor de coherence_rules()):\n{avisos_block}"
    )


def test_boot_build_on_a_repo_with_zero_commits_does_not_crash(boot, model, tmp_path):
    """Hallazgo 2 de Moriarty, ronda 2 -- un repo recien creado, sin un
    solo commit todavia, reventaba `boot.build()`: `git log` sobre una
    rama sin nacer devuelve `returncode=128` con el mensaje real "does
    not have any commits yet", y antes de la consolidacion del
    2026-08-02 eso se trataba como el mismo fallo transitorio que un
    `index.lock` en curso -- se reintentaba y, al agotar los intentos, se
    lanzaba: el arranque entero moria en el primerisimo `git log` de
    cualquier proyecto sin un solo commit.

    Genuinamente distinto de `test_a_repo_where_indexes_seed_never_ran_
    boots_without_crashing` (Bug 1 de Argus): aquel usa `tmp_repo`, que
    YA trae un commit 'init' -- prueba "no hay .claude/project-memory/
    todavia", no "no hay ni un commit". Aqui se usa
    `_zero_commit_repo()`, sin ningun commit en absoluto.
    """
    root = _zero_commit_repo(tmp_path)

    with _cwd(root):
        summary = boot.build()  # NO debe lanzar
        rendered = boot.render(summary)

    assert isinstance(summary, model.BootSummary), (
        f"boot.build() no devolvio un BootSummary en un repo sin commits -- "
        f"devolvio {type(summary)!r} (¿lanzo una excepcion en su lugar?)"
    )
    assert summary.context is None, (
        f"un repo sin ningun commit no deberia tener context, salio "
        f"{summary.context!r}"
    )
    assert summary.restrictions == () and summary.blockers == (), (
        "un repo sin ningun commit no deberia tener restricciones ni "
        f"bloqueantes, salio restrictions={summary.restrictions!r} "
        f"blockers={summary.blockers!r}"
    )
    assert _ZERO_BLOCKERS_LITERAL in rendered, (
        f"el literal exacto de TEXTOS.md Sec.3.2 para bloqueantes en cero no "
        f"aparece:\n{rendered}"
    )
    assert _ZERO_RESTRICTIONS_LITERAL in rendered, (
        f"el literal exacto de TEXTOS.md Sec.3.2 para restricciones en cero "
        f"no aparece:\n{rendered}"
    )
