"""Contrato de lib/memory/rules.py -- PIEZAS.md Sec.9.7.

rules.py NO EXISTE TODAVIA. Estos siete tests deben fallar al importar,
por diseno -- es el ROJO del modo test-first (pasa de contrato, antes de
que Ultron implemente). Uno por fila de la tabla "Sus tests" de Sec.9.7,
ni uno mas:

  1. Se anade una regla y `read_all` devuelve el fichero entero.
  2. Una regla no aparece en ninguna busqueda de memoria.
  3. Anadir dos a la vez no pierde ninguna.
  4. El commit y el fichero acaban con lo mismo.
  5. Un remember casi identico a uno existente se detecta y se avisa
     antes de anadirlo.
  6. Un remember de 201 caracteres rebota.
  7. El comando entrega el fichero entero, nunca una seleccion.

El fixture `rules` importa por ruta de fichero (`import_lib_memory_module`,
ver conftest.py) para que cada test falle con la causa real
(`FileNotFoundError`: lib/memory/rules.py no existe todavia), en vez de un
unico error de coleccion para todo el fichero -- mismo patron que
test_notes.py y test_gitcmd.py. `rules` se pide PRIMERO en cada firma para
que sea ESE fallo el que se reporte antes que el de sus dependencias
(`query`, que ya esta en produccion).

FORMATO DEL COMMIT, tal cual lo fija Sec.9.7 -- no esta en TEXTOS.md, lo
fija el propietario el 2026-08-02 y se cita literal:

    [remember][user] 🧠 <texto>
    [remember][claude] 🧠 <texto>

Solo titular, en espanol, sin cuerpo, tope de 200 caracteres. El flujo es
de DOS pasos: (a) un commit vacio en git con ese titular -- "queda en git,
como todo lo demas"; (b) una linea en el fichero de reglas, que es de
donde se lee con `/remember`. La fila 4 de la tabla ("el commit y el
fichero acaban con lo mismo") es la que prueba exactamente esa costura:
si uno se queda atras, `/remember` entrega una lista incompleta sin
decirlo -- exactamente el modelo de amenaza de este proyecto, el sistema
rompiendose a si mismo por una regla que se escribe y desaparece. No hay
atacante externo en ningun test de este fichero.

CONTRA GIT DE VERDAD, no simulado: los siete tests usan el repositorio git
temporal real del fixture `tmp_repo` de conftest.py, sin mockear
subprocess ni el modulo `git`. `query.py` (fila 2) YA ESTA EN PRODUCCION
(trabajo previo, esta misma rama) -- se usa real, sin mock alguno.

PREGUNTAS -- no resueltas por Sec.9.7, no inventadas aqui (regla del
propio documento, Sec.0.2: "un hueco puede ser deliberado, se pregunta,
no se rellena"):

  (a) La ruta/nombre exacto de "el fichero de reglas" no aparece en
      Sec.9.7 ni en ARQUITECTURA.md/TEXTOS.md/PLAN-CONSTRUCCION.md/
      TRAZABILIDAD.md (grep hecho contra los cinco antes de escribir este
      fichero). La Superficie de Sec.9.7 tampoco declara un parametro
      `root`/`path` en ninguna de sus tres funciones -- a diferencia de
      TODO el resto del sistema (`zones.load(path)`, `indexes.read(name,
      root)`, `config.load(path)`), que nunca oculta una ruta. Por eso
      estos tests NUNCA fabrican ni asumen una ruta: solo llaman a
      `rules.add`/`rules.read_all`/`rules.similar_existing` tal cual las
      declara la Superficie, colocados DENTRO de `tmp_repo` (mismo patron
      que `_cwd` en test_notes.py, que cubre las dos formas posibles de
      que una pieza sin `root` explicito derive su raiz: `Path.cwd()` o
      `gitcmd.repo_root(Path.cwd())`).
  (b) `lib/memory/emojis.py` (ya en produccion) dice en su docstring que
      el remember es "un commit vacio que escribe `format.build_rule_
      message` y lee `rules.add`" -- pero `format.py` (ya en produccion,
      leido antes de escribir este fichero) NO tiene ninguna funcion
      `build_rule_message`, y la Superficie de Sec.9.7 tampoco declara
      que `rules.py` dependa de `format.py` para nada. Es, literalmente,
      el mismo mecanismo que ya mato a `Sources:` en el v1 y que la
      propia Sec.9.7 (dentro de su bloque "Resuelto") señala como
      cometido una vez en este mismo documento: un productor nombrado en
      prosa que no existe en ningun sitio. Estos tests no asumen que
      `format.build_rule_message` exista ni lo importan.

No se toca produccion: si `lib/memory/rules.py` no existe, estos tests se
quedan en rojo tal cual estan -- eso es lo esperado.
"""

import threading
from contextlib import contextmanager
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module, run_git


@pytest.fixture
def rules():
    return import_lib_memory_module("rules")


@pytest.fixture
def query():
    return import_lib_memory_module("query")


@contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo restaura
    siempre. Mismo helper y misma razon que en test_notes.py: la
    Superficie de `rules.py` (Sec.9.7) no declara un parametro de raiz en
    ninguna de sus tres funciones, asi que colocarse DENTRO de `tmp_repo`
    antes de llamarlas cubre cualquier forma en que la pieza derive la
    raiz del repositorio (`Path.cwd()` directo, o `gitcmd.repo_root(
    Path.cwd())`).
    """
    import os

    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


# ---------------------------------------------------------------------------
# Fila 1
# ---------------------------------------------------------------------------


def test_add_one_rule_then_read_all_returns_the_whole_file(rules, tmp_repo):
    """Fila 1: se anade una regla y `read_all` devuelve el fichero entero.

    Fallo real que previene: entregar la mitad de las reglas y que Claude
    trabaje con la otra mitad sin saberlo.
    """
    root = Path(tmp_repo)
    marker = (
        "MARK_ROW1 solo fallos reales del dia a dia, nada de casos limite "
        "academicos"
    )

    with _cwd(root):
        result = rules.add(marker, "user")
        assert result.ok, f"add() fallo inesperadamente: {result.git_error}"
        content = rules.read_all()

    assert marker in content, (
        "read_all() no devuelve el texto completo de la regla recien anadida "
        f"-- el fichero no es 'entero': {content!r}"
    )


# ---------------------------------------------------------------------------
# Fila 2
# ---------------------------------------------------------------------------


def test_added_rule_never_appears_in_any_memory_search(rules, query, tmp_repo):
    """Fila 2: una regla no aparece en ninguna busqueda de memoria.

    Fallo real que previene: el ruido del v1 -- un tercio de toda la
    memoria era configuracion de trabajo disfrazada de memoria de
    proyecto, y ensuciaba todas las busquedas.

    `query.py` ya esta en produccion: se usa real, contra el mismo repo
    temporal donde se acaba de escribir la regla, sin mock alguno.
    """
    root = Path(tmp_repo)
    token = "MARK_ROW2_UNIQUE_TOKEN_never_surface_in_query"
    marker = f"{token} nunca debe salir en una busqueda de memoria de proyecto"

    with _cwd(root):
        result = rules.add(marker, "user")
        assert result.ok, f"add() fallo inesperadamente: {result.git_error}"
        hits = query.by_word(token)

    assert hits == (), (
        "la regla recien anadida aparecio en query.by_word() -- las reglas no "
        f"son notas de proyecto y no deben salir en ninguna busqueda: {hits!r}"
    )


# ---------------------------------------------------------------------------
# Fila 3
# ---------------------------------------------------------------------------


def test_adding_several_rules_at_the_same_time_loses_none(rules, tmp_repo):
    """Fila 3: anadir dos a la vez no pierde ninguna.

    Fallo real que previene: una regla que se escribe y desaparece --
    perdida silenciosa. Se usan varios hilos reales llamando a
    `rules.add()` a la vez contra el mismo repo (mismo patron que
    test_notes.py::test_concurrent_writes_to_same_index_serialize), no
    solo dos, para ensanchar la ventana de carrera.
    """
    root = Path(tmp_repo)
    n_writers = 4
    texts = [f"MARK_ROW3_{i} regla concurrente numero {i}" for i in range(n_writers)]
    results = [None] * n_writers
    errors = []

    def _do_add(i):
        try:
            results[i] = rules.add(texts[i], "user")
        except Exception as exc:  # se reporta, no se traga
            errors.append(exc)

    with _cwd(root):
        threads = [
            threading.Thread(target=_do_add, args=(i,), daemon=True)
            for i in range(n_writers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        still_alive = [t for t in threads if t.is_alive()]
        assert not still_alive, (
            f"{len(still_alive)} hilo(s) no terminaron dentro del plazo -- add() "
            "parece haberse colgado bajo escritura concurrente"
        )
        assert not errors, f"add() lanzo bajo escritura concurrente: {errors}"
        assert all(r is not None for r in results), "algun hilo nunca produjo resultado"

        failed = [r for r in results if not r.ok]
        assert not failed, (
            f"{len(failed)} anadido(s) concurrentes fallaron: "
            f"{[r.git_error for r in failed]}"
        )

        content = rules.read_all()

    missing = [text for text in texts if text not in content]
    assert not missing, (
        f"estas reglas anadidas a la vez desaparecieron del fichero: {missing} -- "
        "la perdida silenciosa que esta fila existe para prevenir"
    )


# ---------------------------------------------------------------------------
# Fila 4 -- reescrita DOS VECES. Primero 2026-08-06 [orden del propietario]:
# `gitmem rule` dejo de comitear (fichero solo, sin commit propio). Esa
# version RETIRADA 2026-08-23 [I-003, orden del propietario -- "regla
# guardada sin comitear = fallo silencioso", incidente real,
# `.claude/project-memory/INCIDENTS.md`, confirmado explicitamente por el
# propietario via el coordinador: "la contradicción... queda resuelta por
# el propietario: I-003... revoca la decisión de 2026-08-06"]. Contrato
# vigente desde I-003: `add()` tiene que producir EXACTAMENTE un commit
# real con la regla dentro y dejar `rules.md` limpio en `git status` --
# Ultron ya lo implemento (verificado por el coordinador, 7/7 en verde en
# `test_rule_commit_contract.py`). Estas dos filas se reescriben aqui a
# nivel de LIBRERIA (llamando a `rules.add()` directamente, sin pasar por
# el script) porque ese nivel -- "add() en si mismo comitea" -- no estaba
# cubierto por `test_rule_commit_contract.py`, que solo ejercita el
# comportamiento vía `bin/memory/rule.py` como proceso.
# ---------------------------------------------------------------------------


def test_add_creates_exactly_one_real_commit_containing_the_rule(rules, tmp_repo):
    """Contrato I-003, a nivel de libreria: `add()` no solo escribe la
    linea -- tiene que dejarla COMITEADA de verdad. Medido con DOS
    lectores reales e independientes de lo que `add()` hace por dentro:
    `git rev-list --count HEAD` (el commit existe, y es exactamente uno
    mas) y `git show HEAD:<ruta>` (el blob comiteado lleva el texto real,
    no solo el arbol de trabajo).
    """
    root = Path(tmp_repo)
    marker = "MARK_ROW4 la regla queda comiteada de verdad, nunca solo en el arbol"
    rules_relpath = ".claude/project-memory/rules.md"

    _rc, count_before, _err = run_git(["rev-list", "--count", "HEAD"], tmp_repo)

    with _cwd(root):
        result = rules.add(marker, "claude", quote="none")
        assert result.ok, f"add() fallo inesperadamente: {result.git_error}"

    _rc, count_after, _err = run_git(["rev-list", "--count", "HEAD"], tmp_repo)
    assert int(count_after) == int(count_before) + 1, (
        "add() tiene que producir EXACTAMENTE un commit nuevo (I-003): "
        f"antes={count_before!r} despues={count_after!r}"
    )

    rc_show, show_out, err_show = run_git(["show", f"HEAD:{rules_relpath}"], tmp_repo)
    assert rc_show == 0, f"git show fallo leyendo el blob comiteado: {err_show}"
    assert marker in show_out, (
        f"el commit real de add() no lleva el texto de la regla: {show_out!r}"
    )


def test_add_leaves_the_rules_file_clean_in_git_status(rules, tmp_repo):
    """Contrato I-003, a nivel de libreria: tras `add()`, `rules.md` NO
    puede seguir apareciendo como cambio sin comitear -- lo contrario del
    contrato de 2026-08-06 que esta fila fijaba antes (`git status
    --porcelain` real, nunca inferido del valor de retorno de `add()`).
    """
    root = Path(tmp_repo)
    marker = "MARK_ROW4B una regla guardada no puede dejar el arbol sucio (I-003)"
    rules_relpath = ".claude/project-memory/rules.md"

    with _cwd(root):
        result = rules.add(marker, "user", quote="una cita literal cualquiera")
        assert result.ok, f"add() fallo inesperadamente: {result.git_error}"

    _rc, status_out, _err = run_git(["status", "--porcelain", "--", rules_relpath], tmp_repo)

    assert status_out.strip() == "", (
        "tras add(), rules.md no deberia aparecer como cambio sin comitear "
        f"(I-003 -- una regla comiteada es una regla guardada): {status_out!r}"
    )


# ---------------------------------------------------------------------------
# Fila 5
# ---------------------------------------------------------------------------


def test_similar_existing_rule_is_detected_before_adding(rules, tmp_repo):
    """Fila 5: un remember casi identico a uno existente se detecta y se
    avisa antes de anadirlo.

    Fallo real que previene: la pila de 114 recordatorios duplicados que
    ya paso en el sistema anterior.

    Incluye un control negativo (un texto sin relacion NO se marca como
    parecido) en el mismo test: no es una fila aparte, es la prueba de
    que el detector no dispara siempre -- "un rechazo que salta siempre
    acaba ignorandose siempre" es exactamente el criterio que Sec.7.5
    (validator.py) usa para el mismo tipo de mecanismo.
    """
    root = Path(tmp_repo)
    original = (
        "MARK_ROW5 solo fallos reales del dia a dia, nada de casos limite "
        "academicos"
    )
    near_duplicate = (
        "MARK_ROW5 solo fallos reales del dia a dia, sin casos limite "
        "academicos"
    )
    unrelated = "MARK_ROW5_OTHER espanol llano, sin jerga ni metaforas inventadas"

    with _cwd(root):
        add_result = rules.add(original, "user")
        assert add_result.ok, f"add() fallo inesperadamente: {add_result.git_error}"

        similar_hits = rules.similar_existing(near_duplicate)
        unrelated_hits = rules.similar_existing(unrelated)

    assert similar_hits, (
        "similar_existing() no detecto un remember casi identico al que ya "
        "existe -- la pila de duplicados del v1 se repite"
    )
    # Forma fijada por el bloqueo de #<regla repetida> (2026-08-04): cada
    # candidata es una pareja (kind, text), nunca solo el texto -- una
    # regla [user] y una [claude] con el mismo texto NO son la misma
    # regla, y sin el dueno "casi repetida" no se puede juzgar. Se compara
    # por igualdad de tupla (funciona igual si la implementacion real
    # devuelve tuplas planas o un NamedTuple local, ver
    # `test_similar_existing_reports_the_real_owner_of_the_match` mas
    # abajo para el porque de esta forma) -- nunca una cadena que haya que
    # volver a partir para sacar el dueno.
    assert ("user", original) in similar_hits, (
        f"similar_existing() no devolvio la pareja (dueno, texto) de la regla "
        f"original ya guardada con kind='user' -- devolvio {similar_hits!r}"
    )
    assert not unrelated_hits, (
        f"similar_existing() marco como parecido un texto sin relacion alguna: "
        f"{unrelated_hits!r}"
    )


# ---------------------------------------------------------------------------
# Fila 6
# ---------------------------------------------------------------------------


def test_rule_over_200_characters_is_rejected(rules, tmp_repo):
    """Fila 6: un remember de 201 caracteres rebota.

    Fallo real que previene: reglas que crecen hasta mezclar tres cosas
    en una y dejan de aplicarse -- el tope se fijo con el dato delante
    (Sec.9.7: mediana 125, 15 de 19 remembers reales caben en 200).

    Incluye el limite exacto (200, que SI debe aceptarse) en el mismo
    test para probar que es un tope real y no un error de conteo -- mismo
    criterio que Sec.7.5 prueba "80 caracteres" junto a "81 rebota".
    """
    root = Path(tmp_repo)
    text_201 = "x" * 201
    text_200 = "y" * 200

    with _cwd(root):
        result_over = rules.add(text_201, "user")
        result_at_boundary = rules.add(text_200, "user")

    assert result_over.ok is False, (
        "add() acepto un remember de 201 caracteres -- el tope de 200 no se aplica"
    )
    assert result_over.rejections, (
        "add() rechazo el remember de 201 caracteres sin devolver ningun Rejection"
    )
    assert result_at_boundary.ok is True, (
        "add() rechazo un remember de exactamente 200 caracteres (el tope, no por "
        f"encima de el): {result_at_boundary.git_error}"
    )


# ---------------------------------------------------------------------------
# Fila 7
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Endurecimiento 2026-08-02 (paso 5 de PIEZAS.md Sec.12bis) -- dos
# hallazgos de revision, ya arreglados en produccion, que faltaba fijar
# con test para que nadie los reintroduzca. Ninguna de las dos es una
# fila nueva de la tabla "Sus tests" de Sec.9.7 -- son regresiones sobre
# comportamiento ya descrito en el docstring del propio modulo.
#
# RETIRADAS 2026-08-06 [orden del propietario]: `test_failed_commit_
# reverts_the_file_to_its_previous_content` y `test_failed_first_ever_
# commit_deletes_the_file_entirely` vivian aqui. Las dos plantaban un
# `.git/index.lock` real para forzar el FALLO del segundo paso del flujo
# viejo (commit vacio tras el fichero) y comprobaban que `_restore_file_
# best_effort` devolvia el fichero a como estaba (o lo borraba entero, si
# era el primer remember del proyecto) -- la red de rescate de un commit
# que no llega a completarse.
#
# Con `add()` reescrito para NO comitear nunca (ver la fila 4 de arriba,
# reescrita el mismo dia), ese segundo paso deja de existir: no hay ningun
# commit que pueda fallar a medio camino, asi que no hay nada que
# `_restore_file_best_effort` tenga que revertir ni que borrar. El
# escenario que estos dos tests montaban (indice bloqueado, commit
# rechazado por git) ya no ocurre nunca dentro de `add()` -- plantar
# `.git/index.lock` y llamar a `add()` ahora simplemente no toca git en
# absoluto, y el test perderia su unica razon de fallar. Se retiran
# enteros en vez de dejarlos en verde por casualidad (un test que ya no
# puede fallar por la causa que dice probar es peor que ausente). No se
# duplica cobertura en su lugar: la fila 4 de arriba (HEAD no se mueve) y
# el `test_invalid_text_bounces_before_touching_git_or_the_file`/
# `test_invalid_kind_bounces_before_touching_git_or_the_file` de mas abajo
# (que ya comprueban "cero commits nuevos" para el camino de RECHAZO por
# validacion, sin tocar el mecanismo de rescate) siguen cubriendo lo que
# de verdad importa hoy.
# ---------------------------------------------------------------------------


def test_invalid_text_bounces_before_touching_git_or_the_file(rules, tmp_repo):
    """Item 2 del endurecimiento: una regla con salto de linea, vacia o
    solo con espacios rebota ANTES de tocar git o el fichero.

    Fallo real que previene: antes, un texto con salto de linea se
    commiteaba entero pero al escribirlo en el fichero rompia el formato
    de una-linea-por-regla -- al releer, solo se recuperaba el trozo
    anterior al salto y el resto quedaba huerfano e invisible.

    Se comprueban las tres formas en el mismo test (mismo criterio que la
    fila 6 de arriba, que junta "201 rebota" y "200 se acepta"): salto de
    linea, cadena vacia, y solo espacios. Cada una se compara contra un
    conteo REAL de commits (`git log --format=%H` antes/despues, git de
    verdad, nunca simulado) para probar que NINGUN commit nuevo se creo --
    "antes de tocar git" no se demuestra solo con `ok=False`, se demuestra
    con el historial real sin cambios.
    """
    root = Path(tmp_repo)

    def _commit_count():
        _rc, out, _err = run_git(["rev-list", "--count", "HEAD"], str(root))
        return int(out)

    rules_path = root / ".claude" / "project-memory" / "rules.md"

    commits_before = _commit_count()
    assert not rules_path.exists(), (
        "el fixture de este test asume que rules.md no existe todavia al empezar"
    )

    with _cwd(root):
        result_newline = rules.add("primera linea\nsegunda linea", "user")
        result_empty = rules.add("", "user")
        result_blank = rules.add("   ", "user")

    for label, result in (
        ("salto de linea", result_newline),
        ("cadena vacia", result_empty),
        ("solo espacios", result_blank),
    ):
        assert result.ok is False, f"add() acepto un texto invalido ({label})"
        assert result.rejections, (
            f"add() rechazo un texto invalido ({label}) sin devolver ningun Rejection"
        )
        assert result.git_error is None, (
            f"add() con texto invalido ({label}) devolvio un git_error -- deberia "
            f"rebotar ANTES de intentar ningun commit: {result.git_error!r}"
        )

    assert _commit_count() == commits_before, (
        "add() con texto invalido creo al menos un commit real -- deberia rebotar "
        "antes de tocar git en cualquiera de los tres casos"
    )
    assert not rules_path.exists(), (
        "add() con texto invalido creo el fichero de reglas -- deberia rebotar "
        "antes de tocar el fichero en cualquiera de los tres casos"
    )


def test_invalid_kind_bounces_before_touching_git_or_the_file(rules, tmp_repo):
    """Hallazgo 5b de Moriarty, ronda 2 -- `add()` validaba el texto de la
    regla pero no el tipo (`kind`): un `kind` con salto de linea rompe la
    estructura de una-linea-por-regla igual que ya la rompia un `text`
    sin proteger (`_RULE_LINE_RE` reconoce el tipo con `[^\\]]+` dentro
    de una sola linea) -- la regla entera queda invisible al releer, sin
    ninguna proteccion hasta ahora.

    Mismo criterio que `test_invalid_text_bounces_before_touching_git_or_
    the_file` de arriba: las tres formas invalidas (salto de linea,
    cadena vacia, solo espacios) en un solo test, contra un conteo REAL
    de commits antes/despues (git de verdad, nunca simulado) para probar
    que NINGUN commit se creo -- "antes de tocar git" se demuestra con el
    historial real sin cambios, no solo con `ok=False`.
    """
    root = Path(tmp_repo)

    def _commit_count():
        _rc, out, _err = run_git(["rev-list", "--count", "HEAD"], str(root))
        return int(out)

    rules_path = root / ".claude" / "project-memory" / "rules.md"

    commits_before = _commit_count()
    assert not rules_path.exists(), (
        "el fixture de este test asume que rules.md no existe todavia al empezar"
    )

    with _cwd(root):
        result_newline = rules.add("regla con tipo invalido", "user\nclaude")
        result_empty = rules.add("otra regla con tipo invalido", "")
        result_blank = rules.add("otra regla mas con tipo invalido", "   ")

    for label, result in (
        ("salto de linea", result_newline),
        ("cadena vacia", result_empty),
        ("solo espacios", result_blank),
    ):
        assert result.ok is False, f"add() acepto un kind invalido ({label})"
        assert result.rejections, (
            f"add() rechazo un kind invalido ({label}) sin devolver ningun Rejection"
        )
        assert result.git_error is None, (
            f"add() con kind invalido ({label}) devolvio un git_error -- deberia "
            f"rebotar ANTES de intentar ningun commit: {result.git_error!r}"
        )

    assert _commit_count() == commits_before, (
        "add() con kind invalido creo al menos un commit real -- deberia rebotar "
        "antes de tocar git en cualquiera de los tres casos"
    )
    assert not rules_path.exists(), (
        "add() con kind invalido creo el fichero de reglas -- deberia rebotar "
        "antes de tocar el fichero en cualquiera de los tres casos"
    )


def test_read_all_returns_every_rule_regardless_of_kind_never_a_selection(
    rules, tmp_repo
):
    """Fila 7: el comando entrega el fichero entero, nunca una seleccion.

    Fallo real que previene: trabajar con la mitad de las reglas sin
    saber que falta la otra mitad.

    A diferencia de la fila 1 (una sola regla), aqui se anaden TRES
    reglas mezclando los dos `kind` (`user` y `claude`) y se comprueba
    que `read_all()` las devuelve TODAS -- sin filtrar por tipo, sin
    quedarse solo con la mas reciente.
    """
    root = Path(tmp_repo)
    rule_user_1 = "MARK_ROW7_USER1 primera regla de usuario"
    rule_claude_1 = "MARK_ROW7_CLAUDE1 primera regla de claude"
    rule_user_2 = "MARK_ROW7_USER2 segunda regla de usuario"

    with _cwd(root):
        for text, kind in (
            (rule_user_1, "user"),
            (rule_claude_1, "claude"),
            (rule_user_2, "user"),
        ):
            result = rules.add(text, kind)
            assert result.ok, f"add({text!r}, {kind!r}) fallo: {result.git_error}"

        content = rules.read_all()

    missing = [
        text for text in (rule_user_1, rule_claude_1, rule_user_2) if text not in content
    ]
    assert not missing, (
        f"read_all() no devolvio estas reglas: {missing} -- una seleccion en vez "
        "del fichero entero, nunca las tres a la vez"
    )


# ---------------------------------------------------------------------------
# Endurecimiento 2026-08-04 -- el rechazo de "regla repetida" (Sec.1.11b de
# TEXTOS.md) no se puede construir porque `similar_existing()` devolvia
# SOLO el texto de cada candidata, nunca de quien es -- `iter_rule_texts()`
# (linea ~189-207) descarta a proposito el grupo `kind` que `_RULE_LINE_RE`
# si captura. Comprobado ANTES de escribir estos tests que
# `iter_rule_texts()` tiene otro consumidor real en produccion
# (`health.coherence_rules`, `health.py:264` y `:290`, sobre el cuerpo de
# un commit y sobre el fichero) ademas de `similar_existing`, y un tercero
# de test (`test_rule_script.py:119`) -- por eso el cambio de forma va
# SOLO en lo que `similar_existing()` devuelve, nunca en
# `iter_rule_texts()` en si, que se queda intacta.
#
# Una regla `[user]` y una `[claude]` con el mismo texto NO son la misma
# regla -- una es una instruccion del propietario, la otra una nota que
# Claude se dejo a si mismo. Sin el dueno, "casi repetida" no se puede
# juzgar. Forma elegida: cada candidata es una pareja `(kind, text)`,
# nunca una cadena que el consumidor tenga que volver a partir --
# comparada aqui por igualdad de tupla (`("user", texto) in hits`), que
# funciona igual si la pieza real devuelve tuplas planas o instancias de
# un `NamedTuple` local (mismo patron ya usado en este mismo repo por
# `report_render.py::_TypeSplit`: un NamedTuple compara igual que una
# tupla plana con los mismos valores) -- este test no fija cual de las
# dos elige Ultron.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["user", "claude"])
def test_similar_existing_reports_the_real_owner_of_the_match(rules, tmp_repo, kind):
    """El dueno que `similar_existing()` devuelve para una candidata tiene
    que ser el MISMO con el que esa regla se guardo -- probado para los
    dos dueños posibles, `user` y `claude`, no solo uno.

    Compara dos cosas escritas por separado: el `kind` que este test le
    paso a `rules.add()` al escribir la regla, contra el `kind` que
    `rules.similar_existing()` devuelve al leerla de vuelta -- el que
    escribe contra el que lee, nunca un valor tecleado a mano por
    duplicado.
    """
    root = Path(tmp_repo)
    original = f"MARK_ROW5_OWNER_{kind.upper()} be terse, cut the fluff, go straight to the point"
    near_duplicate = f"MARK_ROW5_OWNER_{kind.upper()} be terse, no fluff, go straight to the point"

    with _cwd(root):
        add_result = rules.add(original, kind)
        assert add_result.ok, f"add() fallo inesperadamente: {add_result.git_error}"

        hits = rules.similar_existing(near_duplicate)

    assert (kind, original) in hits, (
        f"similar_existing() no devolvio ({kind!r}, {original!r}) tras guardar "
        f"esa misma regla con kind={kind!r} -- devolvio {hits!r}. El dueno "
        "que se lee tiene que ser el mismo con el que se escribio."
    )


def test_similar_existing_keeps_each_owner_separate_when_two_rules_differ_only_in_kind(
    rules, tmp_repo
):
    """Dos reglas con texto casi identico pero dueno DISTINTO (`user` vs
    `claude`) no son la misma regla -- `similar_existing()` tiene que
    enseñar las dos, cada una con su dueno real, nunca fundirlas en una
    ni etiquetar la de un dueno con el otro.

    Fallo real que esto previene: sin el dueno, un aviso de "regla
    repetida" no puede distinguir una instruccion del propietario de una
    nota que Claude se dejo a si mismo -- exactamente el bloqueo que
    impide construir el rechazo de Sec.1.11b hoy.
    """
    root = Path(tmp_repo)
    user_text = "MARK_ROW5_MIXED be terse when answering questions"
    claude_text = "MARK_ROW5_MIXED be terse while answering questions"
    candidate = "MARK_ROW5_MIXED be terse answering questions"

    with _cwd(root):
        user_result = rules.add(user_text, "user")
        assert user_result.ok, f"add() del remember [user] fallo: {user_result.git_error}"
        claude_result = rules.add(claude_text, "claude")
        assert claude_result.ok, (
            f"add() del remember [claude] fallo: {claude_result.git_error}"
        )

        hits = rules.similar_existing(candidate)

    assert ("user", user_text) in hits, (
        f"similar_existing() no devolvio ('user', {user_text!r}) -- la regla "
        f"[user] desaparecio o quedo mal etiquetada: {hits!r}"
    )
    assert ("claude", claude_text) in hits, (
        f"similar_existing() no devolvio ('claude', {claude_text!r}) -- la "
        f"regla [claude] desaparecio o quedo mal etiquetada: {hits!r}"
    )
    assert ("claude", user_text) not in hits and ("user", claude_text) not in hits, (
        f"similar_existing() cruzo el dueno de una regla con el texto de la "
        f"otra: {hits!r}"
    )


def test_remember_from_a_plain_subfolder_of_the_same_repo_still_works(rules, tmp_repo):
    """[GUARD] -- sigue funcionando igual que hoy desde una subcarpeta
    NORMAL del mismo repositorio (ningun repositorio anidado dentro).
    Misma razon que su gemelo en test_context.py: no depende de ningun
    arreglo, git ya resuelve esto correctamente por su cuenta -- debe
    seguir en VERDE antes y despues.

    Lector cambiado 2026-08-06 [orden del propietario, mismo dia que el
    reescrito de `add()` a "ya no comitea"]: antes se comprobaba mirando
    `git log -1 --format=%s` -- con `add()` sin commit propio, HEAD nunca
    se mueve, asi que ese lector ya no puede probar nada (ni aunque la
    resolucion de raiz estuviera rota, el log seguiria intacto). Lo que
    este test comprueba sigue siendo real y valioso -- que la raiz del
    repositorio se resuelve bien desde una subcarpeta normal, no solo
    desde la raiz -- asi que se conserva, cambiando SOLO el lector: se
    lee el fichero real (`rules.rules_file_path(project_root)`, la misma
    funcion de un unico punto que `add()` usa por dentro, aqui llamada con
    la raiz EXPLICITA, nunca dependiente del cwd) para confirmar que la
    linea aterrizo en `.claude/project-memory/rules.md` de la RAIZ del
    repo, no en ningun sitio relativo a la subcarpeta desde la que se
    llamo.
    """
    project_root = Path(tmp_repo)
    subfolder = project_root / "src" / "some" / "module"
    subfolder.mkdir(parents=True)

    marker = "MARK_SUBFOLDER_RULE remember anadido desde una subcarpeta normal"

    with _cwd(subfolder):
        result = rules.add(marker, "user")

    assert result.ok, (
        f"add() no dio ok=True desde una subcarpeta normal del mismo "
        f"repositorio: {result.git_error}"
    )

    rules_path = rules.rules_file_path(project_root)
    assert rules_path.exists(), (
        "add() desde una subcarpeta normal no escribio el fichero de reglas "
        f"en la raiz real del repositorio: {rules_path!r} no existe"
    )
    content = rules_path.read_text(encoding="utf-8")
    assert marker in content, (
        "el remember anadido desde una subcarpeta normal del mismo repositorio "
        f"no aparece en rules.md, leido directamente de la raiz real: {content!r}"
    )
