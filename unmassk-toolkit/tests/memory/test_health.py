"""Contrato de lib/memory/health.py -- PIEZAS.md Sec.9.4.

`health.py` YA EXISTE y esta en produccion (`coherence()` y
`plans_unreflected()` implementadas). Este fichero cubre las SIETE filas
que la tabla "Sus tests" de Sec.9.4 tiene hoy, ni una mas:

  1-3. `coherence()`, test-first (rojo -> verde cuando `notes.py`/
       `query.py` pasaron a produccion): borrar una linea de indice a
       mano se reporta como <<falta en indice>>; anadir una de mas se
       reporta tambien -- las dos direcciones; con todo correcto salen
       los numeros, no el silencio.
  4-7. `plans_unreflected()`, anadidas 2026-08-02 sobre codigo YA
       ESCRITO y sin ningun test -- el patron del punto 11 de DEUDA.md.
       La funcion nacio al reves que el resto de esta rama: no la pidio
       una fila de esta tabla, la pidio `vocabulary.FIELDS["issue"]`
       declarandola como su lector real, y la regla de los tres estados
       (Sec.6.1) puso `test_vocabulary.py` en rojo en cuanto `health.py`
       existio sin ella (ver el docstring del propio modulo,
       `lib/memory/health.py` lineas 21-37, para el detalle completo de
       ese porque). Las filas: un commit de trabajo posterior al ultimo
       movimiento de su issue sale como "sin reflejar" con su recuento;
       uno ANTERIOR no sale; sin ningun commit que cite una issue,
       vacio SIN CONSULTAR NADA FUERA; y si la consulta externa (`gh`)
       falla o no esta disponible, `plans_unreflected()` falla en alto
       -- nunca "todo correcto" por no haber podido mirar.

El fixture `health` se pide PRIMERO en cada firma (mismo patron que
test_query.py/test_notes.py): pytest instancia los fixtures en el orden
en que aparecen, asi que si algun dia `health.py` deja de existir el
fallo se reporta ahi -- nunca por `model`/`config`/`validator`/
`indexes`/`notes`/`vocabulary`, que ya estan en produccion y en verde.

De que salida se deriva [encargo, PIEZAS.md Sec.9.4]: del bloque AVISOS
del arranque, TEXTOS.md Sec.3.1:

    AVISOS
       O  plan #47: 3 commits sin reflejar en la issue
       Y  IDs sin duplicados (68 notas)
       Y  indices coherentes con git (68 lineas / 68 notas)

Los dos marcados en verde (Y) importan tanto como el de aviso (O): un
chequeo que solo habla cuando falla es indistinguible de uno que no se
ejecuta -- y eso ya paso en el v1, seis hooks corriendo version vieja
durante dias sin que nada lo dijera. Por eso la fila 3 no solo comprueba
que no hay discrepancias: comprueba que los NUMEROS reales salen.

**Superficie que cubre este contrato, y la que NO** [PIEZAS.md Sec.9.4,
tabla ampliada 2026-08-02]:

    def coherence(root: Path) -> tuple[int, int, tuple[str, ...]]   # lineas, notas, discrepancias
    def duplicates(root: Path) -> tuple[str, ...]
    def plans_unreflected() -> tuple[tuple[int, int], ...]
    def build() -> HealthReport

La tabla "Sus tests" de Sec.9.4 tiene hoy SIETE filas: las tres
originales de `coherence()` (indice/divergencia) mas cuatro nuevas de
`plans_unreflected()`, anadidas por el orquestador el 2026-08-02 sobre
la funcion ya escrita y sin test [derivadas de spec-sistema-memoria-v2.md
Sec.10.4]. Este fichero cubre las siete, una a una, ni una mas.
`duplicates()`/`build()` SIGUEN sin fila propia en Sec.9.4 y siguen sin
test aqui -- `ids.find_duplicates` (Sec.7.2) ya cubre el mecanismo de
duplicados con su propio contrato, y `build()` (que compondria
`HealthReport`) no tiene forma fijada en ningun sitio sin inventarla.
Regla del encargo, vigente para las dos rondas: "una fila = un test, ni
uno mas".

**Ronda 3 (2026-08-02, endurecimiento de capa 4, paso 5 de PIEZAS.md
Sec.12bis) -- dos anadidos mas, fuera de las siete filas de arriba:**

1. **`coherence_rules(root)`** -- funcion nueva sin ningun test (mismo
   patron del punto 11 de DEUDA.md que ya cerro `plans_unreflected()`
   arriba). Sin fila propia en "Sus tests" -- el encargo la pide
   directamente, con la firma ya fijada en Sec.9.4 y el docstring del
   propio modulo. Cinco tests: los cuatro escenarios que se comprobaron a
   mano al escribirla (repo limpio; una regla dada de alta; una linea
   borrada a mano con el commit intacto; una linea anadida a mano sin
   commit) mas uno que no esta en esa lista -- los numeros salen siempre,
   tambien cuando todo va bien, mismo criterio que la fila 3 de
   `coherence()`.
2. **Regresion de `coherence()`**: ya no grita en falso con una nota
   archivada legitimamente -- ver "Revision 2026-08-02" en el docstring
   del modulo para la demostracion original (`('D-001: existe en git pero
   falta en el indice',)` tras un archivado limpio, sin nada roto). Un
   test que archiva de verdad (`indexes.remove()` + `indexes.archive()`)
   y comprueba que la nota archivada nunca vuelve a aparecer como
   discrepancia.

**Como se prueban las cuatro filas de `plans_unreflected()` sin `gh`
real** [instruccion explicita del encargo -- el corredor de tests no
tiene garantizado ni red ni el binario `gh`]:

- **Filas 4-6** (commit posterior sale, commit anterior no sale, sin
  commits no se consulta nada) necesitan CONTROLAR lo que la consulta
  externa responde -- se finge en el mismo limite que ya establecio
  `test_query.py::test_by_id_retries_after_transient_git_failure_before_giving_up`
  para `git`: `monkeypatch.setattr(subprocess, "run", ...)` sobre el
  modulo `subprocess` COMPARTIDO (health.py y gitcmd.py hacen los dos
  `import subprocess`, nunca `from subprocess import run` -- parchear el
  atributo del modulo real, no una copia, es lo que hace que el parche
  alcance a `health.py` sin que este fichero de test lo importe). El
  helper `_patch_gh` de este fichero deja pasar SIN TOCAR cualquier
  invocacion cuyo primer argumento no sea `"gh"` (los `git add`/`git
  commit`/`git log` reales de `notes.write_work` siguen yendo al
  `subprocess.run` real) y solo responde -- o cuenta -- las que si lo
  son. Nunca se fabrica el commit de trabajo a mano: `notes.write_work`
  (Sec.8.1, ya real) es quien escribe el trailer `Issue: #N` literal,
  con un commit real en el `tmp_repo` de cada test.
- **Fila 7** (la que mas importa: si `gh` falla, `plans_unreflected()`
  falla en alto, nunca "todo correcto") NO finge nada -- deja que
  `health.py` llame al `gh` REAL contra el `tmp_repo` del test. Un repo
  temporal recien creado no tiene remoto de GitHub, y `gh issue view`
  contra un repo sin remoto falla YA, sin red y en milisegundos
  (verificado en vivo antes de escribir el test: `gh issue view 999999`
  en un repo git limpio devuelve `returncode=1`, `stderr='no git
  remotes found\n'`, sin tocar la red). Es un fallo real de la
  herramienta real, no una simulacion -- la fila que pide "falla de
  verdad" es, literalmente, la mas facil de las cuatro.

**Supuestos declarados, sin fuente literal en Sec.9.4 (misma disciplina
que el resto de contratos de esta rama -- format/zones/similar/query):**

1. **`coherence(root)` puede depender del cwd del proceso ademas de
   `root`.** `query.py` (Sec.8.2, ya real) lee "contra el cwd del
   proceso" en sus cuatro funciones publicas, sin `root`/`cwd` propio
   -- si `health.coherence` cruza el indice contra git usando `query.py`
   por dentro, necesitaria el proceso ya posicionado dentro del repo
   aunque tambien reciba `root` explicito para leer los indices. Cada
   test envuelve la llamada en `_cwd(root)` para cubrir las dos
   posibilidades a la vez (mismo criterio que test_query.py, supuesto 1
   de su propio docstring) -- no cuesta nada si `health.py` acaba
   resolviendo la raiz solo con el parametro.
2. **El segundo elemento de la tupla ("notas") cuenta commits de nota
   REALES en git, no lineas de indice que casan.** Es la unica lectura
   que hace tener sentido la propia fila 1 de la tabla ("una nota que
   existe en git y no la encuentra ninguna busqueda" -- si "notas"
   contara solo lo que el indice ya sabe, nunca podria divergir de
   "lineas" en la direccion que esa fila describe). `query.py` ya tiene,
   real y en verde, el mecanismo que hace exactamente esto
   (`_all_notes()`: cada commit se intenta parsear con
   `format.parse_message`, el commit `init` y cualquier commit ajeno se
   descartan en silencio por no parsear como nota) -- se asume que
   `health.coherence` usa ese mismo criterio para contar "notas", sea
   por dentro de `query.py` o replicandolo.
3. **El primer elemento ("lineas") es el total de lineas de nota en los
   SIETE indices vigentes** (no incluye `ARCHIVED.md`, que es un
   historico de notas ya retiradas, no "lo que hay ahora mismo"). Cada
   test deriva su valor esperado llamando a `indexes.counts(root)` (ya
   real, en verde) y sumando sus valores -- nunca lo teclea a mano
   (unmassk-standards Sec.34: no fabricar el resultado esperado de un
   round trip). Como ningun test de este fichero toca `ARCHIVED.md`,
   esta suma es identica incluya o no ese fichero (aporta siempre 0), asi
   que el supuesto no condiciona el resultado de ningun assert.
4. **Cada string de `discrepancias` nombra, en texto, el identificador de
   la nota afectada.** Es la unica lectura consistente con el propio
   "para que" de la pieza ("comprobar que el sistema no se ha roto
   solo") y con el estilo ya usado en el resto del sistema para avisos
   accionables (p.ej. `by_word` -- Sec.8.2, fila 4 -- devuelve las lineas
   concretas que casaron "para que el informe pueda marcar cual fue").
   Si Ultron elige otro formato de texto, solo la comprobacion
   `any(note_id in d for d in discrepancias)` de cada test seria la linea
   a ajustar, no el test entero.
5. **El fixture de base (`_seed_two_synced_notes`) asume que las dos
   notas sembradas caen en el MISMO fichero de indice** -- las dos son
   tipo "M" (memo), y el propio helper comprueba esto explicitamente
   (`assert file_a == file_b`) en vez de asumirlo en silencio, para que
   un cambio futuro en que tipo va a que indice falle con un mensaje
   legible en vez de un assert de conteo confuso mas abajo.
6. **La comparacion de `plans_unreflected()` es "fecha de autor del
   commit" contra "fecha de actividad devuelta por `gh`", ninguna de
   las dos anclada a un valor fijo del calendario.** Las filas 4 y 5
   fingen la respuesta de `gh` con una fecha deliberadamente MUY en el
   pasado (fila 4, para que cualquier commit real de "ahora" quede
   despues) o calculada como "ahora + 365 dias" en el momento del test
   (fila 5, para que quede despues sin importar cuando corra la
   suite) -- nunca una fecha fija cercana al presente, que envejeceria
   mal. Ninguna de las dos es una fecha "inventada" en el sentido de
   Sec.34: son la entrada de un limite que el propio encargo pide
   fingir (la respuesta de `gh`), no el resultado esperado de un round
   trip -- el resultado esperado (cuenta de commits, o vacio) se sigue
   derivando de lo que `notes.write_work` escribio de verdad en git.

**Sembrado real, no fabricado.** `notes.py` (Sec.8.1) ya esta en
produccion y en verde: cada test siembra su base con `notes.write()` (o,
para las filas 4-7, `notes.write_work()`) de verdad, un commit real por
nota o por commit de trabajo, con su linea de indice real (o su trailer
`Issue: #N` real) escrita por la misma transaccion que usara produccion
-- no se fabrica a mano ni el commit ni la linea de indice ni el
trailer. Las divergencias que cada fila 1-2 necesita se crean DESPUES,
con las piezas reales de la capa 2 (`indexes.remove()`/`indexes.insert()`
directamente, sin pasar por `notes.write()`) -- exactamente lo que el
encargo describe como "a mano": el indice cambia sin que el commit de la
nota en git se entere, o al reves.

No se toca produccion en ningun momento de este encargo: `health.py` ya
existia, completo, antes de escribir estos tests, y sigue exactamente
igual despues -- si algo de su comportamiento no hubiera encajado con lo
que la tabla de Sec.9.4 describe, el hallazgo se reporta, no se arregla
aqui. No se toca ningun fichero de un companero.
"""

import contextlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module

_BASE_NOTE_FIELDS = dict(
    type="M",
    zone1="product",
    zone2="notes-test",
)


@pytest.fixture
def health():
    return import_lib_memory_module("health")


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
def vocabulary():
    return import_lib_memory_module("vocabulary")


@pytest.fixture
def make_note(model):
    """Fabrica de `Note`, mismos defaults neutros que test_notes.py --
    cada test override solo lo que le importa. `id`/`description`/
    `timestamp` se fijan aqui porque `validate_note` los exige o los
    ignora por igual en los tres tests de este fichero.
    """

    def _make(**overrides):
        from datetime import datetime, timezone

        fields = dict(_BASE_NOTE_FIELDS)
        fields["id"] = ""
        fields["description"] = "MARK_HEALTH_DESCRIPTION not empty, not special"
        fields["timestamp"] = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


@pytest.fixture
def make_context(model, config, validator):
    """Un `Context` real con las zonas de la nota ya dadas de alta --
    mismo patron que test_notes.py::make_context. `existing_in_zone=()`
    evita cualquier rechazo de parecido entre las dos notas base de este
    contrato.
    """

    def _make(zone_names=("product", "notes-test")):
        zones = {
            name: model.Zone(name=name, description=f"MARK zone {name}", aliases=())
            for name in zone_names
        }
        return validator.Context(
            zones=zones,
            existing_in_zone=(),
            known_ids=frozenset(),
            config=config.Config(),
        )

    return _make


@contextlib.contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo
    restaura siempre -- ver supuesto 1 del docstring del modulo.
    """
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _index_line_for(indexes_mod, vocabulary_mod, root, note_id):
    """Busca `note_id` en los siete indices VIGENTES (no ARCHIVED.md).
    Devuelve `(nombre_fichero, IndexLine)`, o `(None, None)` -- mismo
    helper que test_notes.py::_index_line_for, deliberadamente sin
    asumir que letra de tipo va a que fichero.
    """
    for name in vocabulary_mod.INDEX_FILES:
        if name == "ARCHIVED.md":
            continue
        for line in indexes_mod.read(name, root):
            if line.id == note_id:
                return name, line
    return None, None


def _seed_two_synced_notes(notes_mod, indexes_mod, vocabulary_mod, make_note, make_context, root):
    """Siembra la base COMPARTIDA de los tres tests: dos notas reales,
    cada una con su commit real en git y su linea de indice real,
    escritas por `notes.write()` -- nunca fabricadas a mano. Devuelve
    `(note_id_a, note_id_b, index_name)`.
    """
    indexes_mod.seed(notes_mod.pm_root(root))
    ctx = make_context()
    note_a = make_note(headline="MARK_HEALTH_A first synced note for the health.py contract")
    note_b = make_note(headline="MARK_HEALTH_B second synced note for the health.py contract")

    with _cwd(root):
        result_a = notes_mod.write(note_a, ctx)
        result_b = notes_mod.write(note_b, ctx)

    assert result_a.ok, f"sembrado de la nota A fallo: {result_a.git_error}"
    assert result_b.ok, f"sembrado de la nota B fallo: {result_b.git_error}"

    file_a, _line_a = _index_line_for(indexes_mod, vocabulary_mod, notes_mod.pm_root(root), result_a.note_id)
    file_b, _line_b = _index_line_for(indexes_mod, vocabulary_mod, notes_mod.pm_root(root), result_b.note_id)
    assert file_a is not None, f"{result_a.note_id!r} no aparece en ningun indice tras sembrarla"
    assert file_a == file_b, (
        "el fixture de base de este contrato asume que las dos notas sembradas caen "
        f"en el mismo indice -- salieron en {file_a!r} y {file_b!r} respectivamente "
        "(ver supuesto 5 del docstring del modulo)"
    )

    return result_a.note_id, result_b.note_id, file_a


# ---------------------------------------------------------------------------
# Fila 1
# ---------------------------------------------------------------------------


def test_index_line_deleted_by_hand_is_reported_as_missing_from_index(
    health, model, config, validator, indexes, notes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 1: borrar una linea de un indice a mano se reporta como
    <<falta en indice>>.

    Fallo real que previene: una nota que existe en git y no la
    encuentra ninguna busqueda -- memoria escrita e invisible, porque el
    indice ya no sabe que existe.
    """
    root = Path(tmp_repo)
    note_id_a, note_id_b, index_name = _seed_two_synced_notes(
        notes, indexes, vocabulary, make_note, make_context, root
    )

    # "A mano": se retira la linea de indice de la nota A sin tocar su
    # commit real en git -- el mismo hueco que produciria un fichero de
    # indice editado directamente, o una migracion a medias.
    with _cwd(root):
        indexes.remove(note_id_a, index_name, notes.pm_root(root))

    with _cwd(root):
        lineas, notas, discrepancias = health.coherence(root)

    expected_lineas = sum(indexes.counts(notes.pm_root(root)).values())
    assert lineas == expected_lineas, (
        f"lineas devuelto por coherence() ({lineas}) no coincide con "
        f"sum(indexes.counts(root).values()) ({expected_lineas}) -- el numero no "
        "refleja el indice real"
    )
    assert lineas == 1, (
        f"solo deberia quedar la linea de {note_id_b!r} tras borrar la de "
        f"{note_id_a!r} a mano, salio lineas={lineas}"
    )
    assert notas == 2, (
        "las dos notas siguen siendo commits reales en git -- solo se borro su "
        f"linea de indice, no su commit; salio notas={notas}"
    )
    assert discrepancias, (
        f"coherence() no reporto ninguna discrepancia tras borrar a mano la linea de "
        f"{note_id_a!r} del indice, aunque su commit sigue real en git -- un chequeo "
        "mudo es indistinguible de uno que no se ejecuta"
    )
    assert any(note_id_a in d for d in discrepancias), (
        f"ninguna discrepancia nombra a {note_id_a!r} -- el informe no podria decir "
        f"cual nota falta en el indice: {discrepancias!r}"
    )


# ---------------------------------------------------------------------------
# Fila 2
# ---------------------------------------------------------------------------


def test_extra_index_line_pointing_nowhere_is_also_reported(
    health, model, config, validator, indexes, notes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 2: anadir una linea de mas se reporta tambien -- la
    divergencia se detecta en los dos sentidos.

    Fallo real que previene: una linea que apunta a una nota que no
    existe -- el sentido contrario a la fila 1, y la tabla es explicita
    en que las dos direcciones tienen que detectarse, no solo una.
    """
    root = Path(tmp_repo)
    note_id_a, note_id_b, index_name = _seed_two_synced_notes(
        notes, indexes, vocabulary, make_note, make_context, root
    )

    bogus_id = "M-999999"
    bogus_line = model.IndexLine(
        id=bogus_id,
        zone1="product",
        zone2="notes-test",
        headline="MARK_HEALTH_BOGUS line inserted directly, never committed to git",
    )
    with _cwd(root):
        indexes.insert(bogus_line, index_name, notes.pm_root(root))

    with _cwd(root):
        lineas, notas, discrepancias = health.coherence(root)

    expected_lineas = sum(indexes.counts(notes.pm_root(root)).values())
    assert lineas == expected_lineas, (
        f"lineas devuelto por coherence() ({lineas}) no coincide con "
        f"sum(indexes.counts(root).values()) ({expected_lineas}) -- el numero no "
        "refleja el indice real"
    )
    assert lineas == 3, (
        f"deberian quedar las lineas de {note_id_a!r}/{note_id_b!r} mas la linea de "
        f"mas insertada a mano, salio lineas={lineas}"
    )
    assert notas == 2, (
        f"git solo tiene dos notas reales ({note_id_a!r}, {note_id_b!r}) -- la linea "
        f"de mas nunca se commiteo, salio notas={notas}"
    )
    assert discrepancias, (
        f"coherence() no reporto ninguna discrepancia tras anadir a mano una linea de "
        f"indice que apunta a {bogus_id!r}, que no existe en git -- un chequeo mudo "
        "es indistinguible de uno que no se ejecuta"
    )
    assert any(bogus_id in d for d in discrepancias), (
        f"ninguna discrepancia nombra a {bogus_id!r} -- el informe no podria decir "
        f"cual linea sobra: {discrepancias!r}"
    )


# ---------------------------------------------------------------------------
# Fila 3
# ---------------------------------------------------------------------------


def test_fully_coherent_state_reports_the_real_numbers_not_silence(
    health, model, config, validator, indexes, notes, vocabulary, tmp_repo, make_note, make_context
):
    """Fila 3: con todo correcto, salen los numeros, no el silencio.

    Fallo real que previene: un chequeo mudo, indistinguible de uno que
    no se ejecuta -- el aviso `Y indices coherentes con git (68 lineas /
    68 notas)` solo demuestra que el chequeo corrio si ensena el numero
    real cuando todo va bien, no un `0`/vacio por defecto.
    """
    root = Path(tmp_repo)
    note_id_a, note_id_b, _index_name = _seed_two_synced_notes(
        notes, indexes, vocabulary, make_note, make_context, root
    )

    with _cwd(root):
        lineas, notas, discrepancias = health.coherence(root)

    expected_lineas = sum(indexes.counts(notes.pm_root(root)).values())
    assert lineas == expected_lineas, (
        f"lineas devuelto por coherence() ({lineas}) no coincide con "
        f"sum(indexes.counts(root).values()) ({expected_lineas}) -- el numero no "
        "refleja el indice real"
    )
    assert lineas == 2, (
        f"deberian salir las dos lineas reales de {note_id_a!r}/{note_id_b!r}, "
        f"salio lineas={lineas}"
    )
    assert notas == 2, (
        f"deberian salir las dos notas reales de git, salio notas={notas}"
    )
    assert discrepancias == (), (
        "con el indice y git en verde no deberia haber ninguna discrepancia, "
        f"salieron: {discrepancias!r}"
    )


# ---------------------------------------------------------------------------
# Helpers compartidos por las filas 4-7 (`plans_unreflected`)
# ---------------------------------------------------------------------------


def _write_work_commit(notes_mod, root, filename, content, message, issue):
    """Siembra UN commit de trabajo real via `notes.write_work()` (Sec.8.1,
    ya en produccion) -- nunca fabricado a mano. Escribe `content` en un
    fichero nuevo bajo `root` (necesario: `write_work` exige
    `allow_empty=False`, hace falta un cambio real que commitear) y lo
    commitea con `message`, mas el trailer `Issue: #{issue}` si `issue`
    no es `None` -- el MISMO mecanismo que produce el texto que
    `health._issue_commit_dates()` lee despues con su regex.

    Devuelve el `WriteResult` real; el llamador decide que comprobar.
    """
    file_path = Path(root) / filename
    file_path.write_text(content, encoding="utf-8")
    with _cwd(root):
        result = notes_mod.write_work(message, [file_path], issue)
    assert result.ok, f"commit de trabajo de seed fallo: {result.git_error}"
    return result


def _patch_gh(monkeypatch, response_for_call):
    """Sustituye el `subprocess.run` COMPARTIDO (el mismo objeto de modulo
    que `health.py` y `gitcmd.py` referencian via su propio `import
    subprocess`) por una version que intercepta SOLO las invocaciones a
    `gh` -- `response_for_call(cmd)` decide que `CompletedProcess`
    devolver, o lanza si el propio test quiere que una llamada
    inesperada falle ruidosamente. Cualquier otra invocacion (los `git
    add`/`git commit`/`git log` reales que `notes.write_work` y
    `health.plans_unreflected` siguen necesitando) pasa intacta al
    `subprocess.run` real -- nunca se finge git, solo `gh`.

    Devuelve la lista de invocaciones a `gh` observadas (cada una su
    `cmd` completo), para que el test compruebe CUANTAS veces se llamo
    y CON QUE ARGUMENTOS -- nunca solo que no revento (regla de
    verificacion de mocks del propio Dante).
    """
    real_run = subprocess.run
    calls = []

    def _fake_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd and cmd[0] == "gh":
            calls.append(list(cmd))
            return response_for_call(cmd)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    return calls


def _gh_completed(cmd, comments_created_at=(), created_at=None):
    """`CompletedProcess` con la misma forma que `gh issue view <n>
    --json comments,createdAt` devuelve de verdad -- `health.py` solo
    lee `comments`/`createdAt` del JSON (ver `_last_activity_at`), asi
    que es la unica forma que hace falta reproducir.
    """
    payload = {
        "comments": [{"createdAt": c} for c in comments_created_at],
        "createdAt": created_at,
    }
    return subprocess.CompletedProcess(
        args=cmd, returncode=0, stdout=json.dumps(payload), stderr=""
    )


# ---------------------------------------------------------------------------
# Fila 4
# ---------------------------------------------------------------------------


def test_work_commit_after_last_issue_activity_is_reported_as_unreflected_with_its_count(
    health, notes, tmp_repo, monkeypatch
):
    """Fila 4: un commit de trabajo posterior al ultimo movimiento de su
    issue sale como "sin reflejar", con su recuento.

    Fallo real que previene: el aviso del arranque que existe para que
    un plan no se quede atras calla justo cuando debia hablar.
    """
    root = Path(tmp_repo)
    issue_number = 47
    _write_work_commit(
        notes, root, "work_1.txt", "primer commit de trabajo",
        "trabajo A citando la issue", issue_number,
    )
    _write_work_commit(
        notes, root, "work_2.txt", "segundo commit de trabajo",
        "trabajo B citando la issue", issue_number,
    )

    # Fecha de actividad de la issue deliberadamente muy en el pasado --
    # ver supuesto 6 del docstring del modulo: cualquier commit real de
    # "ahora" queda despues, sin importar cuando corra esta suite.
    calls = _patch_gh(
        monkeypatch,
        lambda cmd: _gh_completed(cmd, created_at="2020-01-01T00:00:00Z"),
    )

    with _cwd(root):
        result = health.plans_unreflected()

    assert result == ((issue_number, 2),), (
        f"con dos commits de trabajo citando la issue #{issue_number}, ambos "
        "posteriores a su ultima actividad en gh, plans_unreflected() deberia "
        f"devolver exactamente (({issue_number}, 2),) -- salio {result!r}"
    )
    assert len(calls) == 1, (
        f"deberia consultarse gh UNA vez por issue (consulta simple, spec "
        f"Sec.10.4), no una por commit -- se observaron {len(calls)} "
        f"llamadas: {calls!r}"
    )
    assert str(issue_number) in calls[0], (
        f"la llamada a gh no menciona la issue #{issue_number} en sus "
        f"argumentos: {calls[0]!r}"
    )


# ---------------------------------------------------------------------------
# Fila 5
# ---------------------------------------------------------------------------


def test_work_commit_before_last_issue_activity_is_not_reported(
    health, notes, tmp_repo, monkeypatch
):
    """Fila 5: un commit ANTERIOR al ultimo movimiento de la issue no sale.

    Fallo real que previene: un aviso que salta siempre acaba
    ignorandose siempre.
    """
    root = Path(tmp_repo)
    issue_number = 48
    _write_work_commit(
        notes, root, "work_1.txt", "unico commit de trabajo",
        "trabajo citando la issue, ya reflejada", issue_number,
    )

    # "Ahora + 1 anyo", calculado en el momento del test -- ver supuesto 6:
    # queda despues del commit real sin importar cuando corra la suite,
    # a diferencia de una fecha fija cercana al presente que envejeceria mal.
    future = (datetime.now(timezone.utc) + timedelta(days=365)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    calls = _patch_gh(
        monkeypatch, lambda cmd: _gh_completed(cmd, created_at=future)
    )

    with _cwd(root):
        result = health.plans_unreflected()

    assert result == (), (
        f"el unico commit que cita la issue #{issue_number} es ANTERIOR a su "
        f"ultima actividad en gh -- plans_unreflected() deberia devolver (), "
        f"salio {result!r}"
    )
    assert len(calls) == 1, (
        f"deberia consultarse gh exactamente una vez para la issue "
        f"#{issue_number} -- se observaron {len(calls)} llamadas: {calls!r}"
    )


# ---------------------------------------------------------------------------
# Fila 6
# ---------------------------------------------------------------------------


def test_no_commit_citing_an_issue_returns_empty_without_calling_gh(
    health, notes, tmp_repo, monkeypatch
):
    """Fila 6: sin ningun commit que cite una issue, devuelve vacio SIN
    consultar nada fuera.

    Fallo real que previene: pagar una consulta externa en cada arranque
    para preguntar por algo que no existe.

    El repo tiene un commit de trabajo real -- pero SIN trailer `Issue:
    #N` -- para confirmar que lo que importa es el trailer, no la mera
    presencia de commits de trabajo en el historial.
    """
    root = Path(tmp_repo)
    _write_work_commit(
        notes, root, "work_1.txt", "commit de trabajo sin issue",
        "trabajo que no cita ninguna issue", None,
    )

    calls = _patch_gh(
        monkeypatch,
        lambda cmd: _gh_completed(cmd, created_at="2020-01-01T00:00:00Z"),
    )

    with _cwd(root):
        result = health.plans_unreflected()

    assert result == (), (
        f"sin ningun commit citando una issue, plans_unreflected() deberia "
        f"devolver (), salio {result!r}"
    )
    assert calls == [], (
        "plans_unreflected() consulto gh aunque ningun commit del historial "
        f"cita una issue -- llamadas observadas: {calls!r}"
    )


# ---------------------------------------------------------------------------
# T1 real (House + coordinador, 2026-08-08), lector 2 de 4 del mismo fallo:
# git escribe la fecha de un commit hecho en offset +00:00 (un contenedor sin
# TZ, un merge desde la web de GitHub, un bot) como `...T04:49:21Z`.
# `datetime.fromisoformat` de Python 3.10 no sabe leer esa `Z` (soporte
# anadido en 3.11), y `toolkit-ci.yml` fija Python 3.10.
#
# `_issue_commit_dates()` (health_plans.py ~96) llama a `fromisoformat`
# sobre la fecha de autor SIN red de seguridad -- un solo commit de trabajo
# en huso cero revienta `plans_unreflected()` entero, la red de seguridad
# que avisa cuando un plan se queda sin reflejar en su issue.
# ---------------------------------------------------------------------------


def test_zero_offset_work_commit_does_not_crash_the_coherence_check(
    health, notes, tmp_repo, monkeypatch
):
    """El huso cero se fuerza con `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` en
    `+00:00` -- verificado por House: git escribe la fecha con `Z` sea cual
    sea la zona horaria de la maquina que corre el test, asi el rojo no
    depende de en que huso este quien ejecuta pytest.

    Sin mock de `gh`: el fallo real esta en `_issue_commit_dates()`, que se
    ejecuta ANTES de que `plans_unreflected()` llegue a consultar `gh` --
    si esto crashea, tiene que crashear sin haber llamado a `gh` ni una
    vez (comprobado con `_patch_gh`, igual que la fila 6 de arriba).

    Este test SOLO reproduce el fallo en Python < 3.11 -- ver la entrega
    de esta tarea para la salida real bajo un interprete 3.10.
    """
    root = Path(tmp_repo)
    issue_number = 48

    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-01-01T00:00:00+00:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-01-01T00:00:00+00:00")
    _write_work_commit(
        notes, root, "work_zero_offset.txt", "commit de trabajo en huso cero",
        "trabajo citando la issue, hecho con offset +00:00", issue_number,
    )
    monkeypatch.delenv("GIT_AUTHOR_DATE", raising=False)
    monkeypatch.delenv("GIT_COMMITTER_DATE", raising=False)

    # El montaje es invalido si git no escribio de verdad el huso cero --
    # comprobado leyendo el historial por OTRO camino, nunca asumido.
    log_check = subprocess.run(
        ["git", "log", "-1", "--format=%aI"], cwd=root, capture_output=True, text=True
    )
    assert log_check.returncode == 0, f"git log fallo montando la prueba: {log_check.stderr}"
    assert log_check.stdout.strip().endswith("Z"), (
        f"el montaje de la prueba es invalido: el commit de trabajo no "
        f"quedo con sufijo Z (huso cero) -- {log_check.stdout!r}"
    )

    calls = _patch_gh(
        monkeypatch,
        lambda cmd: _gh_completed(cmd, created_at="2020-01-01T00:00:00Z"),
    )

    # Hoy, en Python < 3.11, esto no devuelve un resultado incompleto ni
    # "todo correcto": lanza `ValueError` sin llegar siquiera a consultar
    # `gh` -- el chequeo de coherencia del arranque revienta.
    with _cwd(root):
        result = health.plans_unreflected()

    assert result == ((issue_number, 1),), (
        f"con un commit de trabajo en huso cero posterior a la ultima "
        f"actividad de la issue #{issue_number}, plans_unreflected() "
        f"deberia devolver (({issue_number}, 1),) -- salio {result!r}"
    )
    assert len(calls) == 1, (
        f"deberia consultarse gh UNA vez por issue, igual que con un commit "
        f"de fecha normal -- se observaron {len(calls)} llamadas: {calls!r}"
    )


# ---------------------------------------------------------------------------
# Fila 7
# ---------------------------------------------------------------------------


def test_coherence_does_not_false_alarm_on_a_legitimately_archived_note(
    health, model, config, validator, indexes, notes, vocabulary, tmp_repo, make_note, make_context
):
    """Regresion (item 3 del endurecimiento de capa 4, 2026-08-02):
    `coherence()` gritaba en falso con cada nota archivada -- demostrado
    ejecutando (ver 'Revision 2026-08-02' en el docstring del modulo):
    tras un archivado legitimo, `('D-001: existe en git pero falta en el
    indice',)` salia siempre, sin que nada estuviera roto. Un chequeo que
    grita siempre acaba ignorandose siempre, y la discrepancia real se
    pierde en el ruido. Arreglado descontando `indexes.read_archive(root)`
    del lado 'falta en indice'.

    Archivado real, no fabricado: la nota se retira del indice vigente
    con `indexes.remove()` y se anade a `ARCHIVED.md` con
    `indexes.archive()` -- las dos piezas reales que ya construyen un
    archivado legitimo, sin inventar un tercer mecanismo.
    """
    from datetime import date

    root = Path(tmp_repo)
    note_id_a, note_id_b, index_name = _seed_two_synced_notes(
        notes, indexes, vocabulary, make_note, make_context, root
    )

    with _cwd(root):
        indexes.remove(note_id_a, index_name, notes.pm_root(root))
        indexes.archive(
            model.ArchiveLine(
                date=date(2026, 8, 2),
                type="M",
                id=note_id_a,
                zone1="product",
                zone2="notes-test",
                headline="MARK_HEALTH_ARCHIVED archived headline for the false-alarm regression",
                destination="closed",
                destination_detail="MARK_HEALTH_ARCHIVED_DETAIL regression test for coherence()",
            ),
            notes.pm_root(root),
        )

    with _cwd(root):
        lineas, notas, discrepancias = health.coherence(root)

    assert not any(note_id_a in d for d in discrepancias), (
        f"coherence() sigue reportando a {note_id_a!r} como discrepancia tras un "
        f"archivado legitimo -- el falso positivo que este test existe para prevenir: "
        f"{discrepancias!r}"
    )
    assert discrepancias == (), (
        f"con {note_id_a!r} legitimamente archivada y {note_id_b!r} sincronizada, "
        f"no deberia quedar ninguna discrepancia, salieron: {discrepancias!r}"
    )


# ---------------------------------------------------------------------------
# RETIRADA 2026-08-06 [orden del propietario]: aqui vivian las cinco filas
# de "coherence_rules() -- endurecimiento del 2026-08-02" (los cuatro
# escenarios comprobados a mano al escribirla, mas la fila del "vigilante
# mudo" -- "los numeros salen siempre, tambien cuando todo va bien") y,
# justo despues, `test_health_report_carries_the_real_rule_coherence_numbers`
# (la mitad de `health.py` de la tuberia "el informe de salud lleva los
# numeros de las reglas" -- las otras tres filas, sobre `boot.py`, vivian
# en `test_boot.py`, retiradas el mismo dia). Los seis existian para
# fijar UNA sola cosa: que `health.coherence_rules()` cruzase los commits
# `[remember]` del historial contra las lineas de `rules.md` y nombrase la
# divergencia en los dos sentidos.
#
# Ultron reescribio `rules.add()` para que YA NO comitee (`gitmem rule`
# escribe la linea y se acaba ahi, listo para que la arrastre el
# siguiente commit real -- ver `test_rules.py`/`test_rule_script.py`,
# mismo dia) y retiro `coherence_rules()` entera junto con
# `_rule_commit_texts()` y los campos `rule_commits`/`rule_lines`/
# `rule_discrepancies` de `HealthReport` -- decision correcta: sin
# commits de regla que cruzar contra el fichero, ya no hay divergencia
# real que estos seis tests puedan seguir demostrando. Los cuatro
# escenarios llamaban a `health.coherence_rules(root)` directamente (ya
# no existe, `AttributeError` de coleccion en cuanto se retire de
# produccion) y la fila del informe de salud leia
# `summary.rule_commits`/`rule_lines` (campos que ya no estan en
# `HealthReport`). Ninguno comprobaba de paso algo que siga siendo
# verdad -- a diferencia del `[GUARD]` de subcarpeta en `test_rules.py`,
# que se conservo adaptando SOLO su lector -- asi que se retiran enteros,
# junto con sus dos fixtures locales (`rules`/`emojis`, sin mas
# consumidores en este fichero tras esta retirada) y sus dos helpers de
# siembra a mano (`_delete_rule_line_by_hand`/
# `_append_uncommitted_rule_line_by_hand`, sin mas llamadores).
#
# RESUCITADA 2026-08-23 [I-003]: la premisa que justificaba esta
# retirada (ninguna regla nueva comitea nunca) queda revertida --
# `rules.add()` vuelve a comitear de verdad. Contrato nuevo, RED,
# en `test_health_rules_coherence_contract.py` (fichero hermano,
# no aqui) -- no se reescribe este bloque retirado, se anade uno
# nuevo al lado.
# ---------------------------------------------------------------------------


def test_gh_failure_raises_instead_of_reporting_all_clear(health, notes, tmp_repo):
    """Fila 7 -- la que mas importa: si la consulta externa falla o no
    esta disponible, `plans_unreflected()` falla en alto, y nunca
    devuelve "todo correcto".

    Fallo real que previene: el peor fallo posible de esta pieza --
    decir que un plan esta al dia porque no se pudo mirar.

    Sin ningun mock: `tmp_repo` es un repo git real recien creado, sin
    remoto de GitHub -- `gh issue view` contra el falla YA, de verdad,
    sin red (verificado en vivo antes de escribir este test:
    `returncode=1`, `stderr='no git remotes found\\n'`). Es la unica de
    las cuatro filas que no necesita fingir el limite externo -- basta
    con dejar que el fallo real ocurra.
    """
    root = Path(tmp_repo)
    issue_number = 49
    _write_work_commit(
        notes, root, "work_1.txt", "commit de trabajo con issue",
        "trabajo citando una issue que gh no puede resolver", issue_number,
    )

    with _cwd(root):
        with pytest.raises(RuntimeError) as exc_info:
            health.plans_unreflected()

    assert str(issue_number) in str(exc_info.value), (
        f"RuntimeError deberia nombrar la issue #{issue_number} que no se "
        f"pudo verificar -- salio: {exc_info.value!r}"
    )


# ---------------------------------------------------------------------------
# RETIRADA 2026-08-06 [orden del propietario, misma tanda que arriba]: aqui
# vivian `_zero_commit_repo()` y
# `test_coherence_rules_on_a_repo_with_zero_commits_does_not_crash`
# (hallazgo 2 de Moriarty, ronda 2 -- "una rama sin ningun commit todavia
# no debe reventar `coherence_rules()`"). Llamaba a
# `health.coherence_rules(root)` directamente, la misma funcion retirada
# arriba -- sin ella, no queda nada que este test pueda seguir
# demostrando. `_zero_commit_repo()` no tenia mas llamadores en este
# fichero, se retira con el.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# zones_state() -- fijado directo (encargo del orquestador, 2026-08-06,
# T3-4 de Cerberus). La funcion ya esta en produccion, extraida desde
# dentro de memory_mounted() el mismo dia (ver su propio docstring,
# lineas 407-434: "para que un segundo llamador... reutilice la MISMA
# distincion en vez de volver a leer el fichero por su cuenta"), pero
# hasta ahora solo tenia cobertura INDIRECTA via sus tres consumidores
# (memory_mounted() arriba en este mismo fichero, bin/memory/zones.py
# list, y el check homologo de git-memory-doctor.py). Este bloque la fija
# en un sitio propio: los tres estados que su propio docstring declara
# (absent/empty/populated) mas el caso de forma invalida, que hoy
# DEGRADA a "empty" via el `except ValueError` -- ese ultimo assert fija
# el contrato TAL COMO ESTA HOY (docstring, lineas 410-414: "contado aqui
# igual que cero zonas utilizables"), no una mejora deseada; si algun dia
# deja de comportarse asi, este test es el que lo dice primero.
# ---------------------------------------------------------------------------


@pytest.fixture
def zones():
    return import_lib_memory_module("zones")


def test_zones_state_on_a_missing_file_is_absent_with_zero_zones(health, tmp_path):
    """Estado 1: el fichero nunca se creo -- "absent", nunca un error ni
    una excepcion (proyecto recien instalado)."""
    path = tmp_path / "zones.json"

    state, count = health.zones_state(path)

    assert (state, count) == ("absent", 0), (
        f"un zones.json inexistente deberia dar ('absent', 0), salio "
        f"({state!r}, {count!r})"
    )


def test_zones_state_on_an_empty_object_is_empty_with_zero_zones(health, tmp_path):
    """Estado 2: fichero presente, `{}` valido, sin ninguna zona dada de
    alta -- "empty", distinto de "absent"."""
    path = tmp_path / "zones.json"
    path.write_text("{}", encoding="utf-8")

    state, count = health.zones_state(path)

    assert (state, count) == ("empty", 0), (
        f"un zones.json presente pero vacio deberia dar ('empty', 0), salio "
        f"({state!r}, {count!r})"
    )


def test_zones_state_with_one_real_zone_is_populated_with_its_real_count(
    health, zones, model, tmp_path
):
    """Estado 3: al menos una zona real -- "populated", con el numero
    real de zonas.

    Sembrado real via zones.add() [Sec.6.2, ya en produccion] -- nunca un
    zones.json escrito a mano, misma disciplina que test_zones.py.
    """
    path = tmp_path / "zones.json"
    zones.add(
        model.Zone(name="billing", description="cobros y pagos", aliases=()), path
    )

    state, count = health.zones_state(path)

    assert (state, count) == ("populated", 1), (
        f"una zona real dada de alta deberia dar ('populated', 1), salio "
        f"({state!r}, {count!r})"
    )


def test_zones_state_on_a_malformed_zone_shape_degrades_to_empty_not_a_crash(
    health, tmp_path
):
    """Contrato del `except ValueError`, fijado TAL COMO ESTA HOY: un
    zones.json sintacticamente valido a nivel superior (un objeto JSON no
    vacio) pero con una zona cuyo VALOR no es un objeto -- caso concreto
    `{"billing": "oops"}`, la misma forma que hace lanzar `ValueError` en
    `zones.load()` (ver `test_zones.py::
    test_regression_aliases_as_string_fails_loud_naming_file_and_zone`
    para el hermano de esta forma con "aliases": "front").

    `zones_state()` no deja pasar esa excepcion: la captura y devuelve
    "empty", el mismo resultado que un fichero realmente vacio -- "fallo
    en alto, nunca silencioso" es responsabilidad de `zones.load()` para
    quien SI necesita escribir en el fichero (docstring de la propia
    funcion, lineas 408-414); `zones_state()` solo decide si hay una zona
    UTILIZABLE hoy, y con esta forma no la hay.

    Este es el mismo caso concreto que el T2 de Cerberus senala como el
    falso-verde de `bin/git-memory-doctor.py::check_project_zones()`
    (ese check no pasa por `zones.load()` y por eso no lo detecta, ver
    `test_doctor_derived_expectations.py::
    TestDoctorRejectsInvalidZoneShape`) -- aqui, en la pieza de mas
    abajo, el mismo dato SI se detecta, y su contrato es degradar, no
    lanzar.
    """
    path = tmp_path / "zones.json"
    path.write_text(json.dumps({"billing": "oops"}), encoding="utf-8")

    state, count = health.zones_state(path)

    assert (state, count) == ("empty", 0), (
        f"una zona de forma invalida deberia degradar a ('empty', 0) via el "
        f"except ValueError de zones_state(), salio ({state!r}, {count!r})"
    )
