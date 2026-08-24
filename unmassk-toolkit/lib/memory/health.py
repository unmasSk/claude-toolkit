"""Comprobar que el sistema no se ha roto solo.

De que salida se deriva: el bloque CHECKS del arranque:

    ⚠️  plan #47: 3 commits sin reflejar en la issue
    ✓  no duplicate IDs (68 notes)
    ✓  indexes match git (68 lines / 68 notes)

Los dos ✓ importan tanto como el ⚠️: un chequeo que solo habla cuando
falla es indistinguible de uno que no se ejecuta. Por eso `coherence()`
siempre devuelve los dos numeros reales, gane o pierda la comparacion.

**No repara nada.** Detecta y enseña -- reparar los indices es un
comando aparte, explicito.

Ocho funciones: `coherence`, `coherence_rules`, `duplicates`,
`plans_unreflected`, `build`, `rebuild_plan`, `possible_unconverted_legacy`,
`memory_mounted`. `plans_unreflected` es el unico lector real del campo
`issue`. `build` compone `coherence`/`coherence_rules`/`duplicates`/
`plans_unreflected` en el `HealthReport` que el arranque pinta.
`rebuild_plan` es el mismo cruce que `coherence()` vuelto un plan de
reparacion, para `reindex.py`. `possible_unconverted_legacy` y
`memory_mounted` cierran dos fallos reales: un proyecto con memoria del
sistema anterior sin destilar se presentaba como vacio de verdad, y un
proyecto sin la memoria montada recibia el mismo informe en verde que
uno sano -- con un pie de arranque que invitaba a un comando garantizado
a fallar. Ver el docstring de cada funcion para el umbral y el mecanismo.

`coherence(root)` cruza dos fuentes, cada una con su propia pieza ya en
produccion:

- **Lineas de indice**: `indexes.read(name, root)` sobre los siete
  indices vigentes (sin `ARCHIVED.md` -- una nota archivada ya esta
  retirada).
- **Notas reales en git**: `query.by_zone(None, None)`, que sin filtro
  devuelve exactamente las notas que el historial completo reconoce.

La divergencia sale de comparar los dos conjuntos de IDs: lo que esta en
git y no en el indice, y lo que esta en el indice y no en git. Cada
discrepancia nombra el ID afectado.

`coherence_rules(root)` (I-003) compara el `rules.md` COMITEADO en HEAD
contra el `rules.md` real del arbol de trabajo -- nunca "arqueologia de
todo el historial" (una version anterior comparaba TODOS los commits de
regla contra el fichero, y eso gritaba siempre sobre lineas legitimas
escritas mientras `rules.add()` no comiteaba nada). Solo una linea
escrita hoy que todavia no llego a NINGUN commit diverge de HEAD.
`HealthReport` puebla `rule_head_lines`/`rule_file_lines`/
`rule_discrepancies`.

**Resiliente a un git corrupto, 2026-08-24**: un objeto de
`.git/objects` corrupto hacia que `coherence_rules()` (via
`query.show_file_at_head()`) reventara con `RuntimeError` sin capturar,
tumbando `build()`/`boot.build()` entero. `build()` lo captura: los tres
numeros quedan en cero y el motivo real va a
`HealthReport.rule_discrepancies_error` -- nunca tumba el resto del
informe.

`plans_unreflected()` vive en `health_plans.py` (partida por tamano);
`health.py` la reexpone bajo el mismo nombre.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca
estandar de Python. Import plano entre hermanos.
"""

from pathlib import Path

import ids
import indexes
import notes
import query
import rules
import zones
from health_plans import plans_unreflected
from model import HealthReport, IndexLine, Note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

_ARCHIVE_FILE = "ARCHIVED.md"

# Aviso A -- umbral de "esto puede ser memoria del sistema anterior sin
# destilar", anadido 2026-08-06. Un proyecto genuinamente recien creado
# acumula, en la practica, un punado de commits de arranque (scaffold
# inicial, primer README, primera estructura) antes de que la memoria se
# instale -- pocos, pero no cero. Fijado en MAS DE OCHO para dejar ese
# margen real y no gritar en el caso mas comun que existe (un proyecto
# que de verdad esta vacio de memoria porque acaba de nacer); un
# historial que ya pasa de ocho commits sin una sola nota reconocida ya
# no encaja en "recien creado" -- encaja en "hay trabajo real ahi
# dentro". El umbral no protege del caso donde SI importa acertar:
# `coherence()` YA distingue "cero notas" de "notas de verdad" para lo
# suyo; este umbral solo decide cuando vale la pena avisar de que ese
# cero podria no ser un cero real.
_LEGACY_MIN_COMMITS = 8


def _current_index_lines(root: Path) -> tuple[IndexLine, ...]:
    """Las lineas de nota de los SIETE indices VIGENTES (sin
    `ARCHIVED.md`) -- compartido por `coherence()` y `duplicates()`.

    Lee en `notes.pm_root(root)`, no en `root` a secas -- los ocho
    indices viven en `.claude/project-memory/`, nunca en la raiz pelada
    del repositorio.

    Un indice AUSENTE cuenta como CERO lineas para ESE fichero, nunca
    revienta: un proyecto recien instalado no tiene ninguno de los ocho
    todavia, y eso es su estado real. Si el proyecto SI tiene notas y
    falta justo un fichero (corrupcion real), el hueco no queda en
    silencio: `coherence()` sigue viendo `index_lines != git_notes`.
    """
    pm = notes.pm_root(root)
    lines: list[IndexLine] = []
    for name in INDEX_FILES:
        if name == _ARCHIVE_FILE:
            continue
        try:
            lines.extend(indexes.read(name, pm))
        except FileNotFoundError:
            continue
    return tuple(lines)


def coherence(root: Path) -> tuple[int, int, tuple[str, ...]]:
    """Cruza los siete indices vigentes contra el historial real de git.

    Devuelve `(lineas, notas, discrepancias)`: cuantas lineas de nota
    tienen los indices vigentes, cuantas notas reales hay en git, y el
    texto de cada divergencia en cualquiera de los dos sentidos (vacio si
    todo coincide).

    Una nota archivada nunca cuenta como "falta en el indice" -- ya salio
    de los indices vigentes a proposito. Un indice o `ARCHIVED.md`
    ausentes cuentan como cero, nunca como un fallo que tumbe esta
    funcion -- una corrupcion real sigue saliendo como
    `index_lines != git_notes` mas abajo.

    Las archivadas TAMBIEN se cruzan contra git, no solo se restan: un id
    archivado que no existe en ningun commit real de git es tan
    discrepancia como las otras dos (una entrada fantasma en
    `ARCHIVED.md` inflaria "K live + J archived / M notes" sin que nada
    lo dijera).
    """
    root = Path(root)
    index_lines = _current_index_lines(root)
    git_notes = query.by_zone(None, None)
    archived_ids = indexes.archived_ids(notes.pm_root(root))

    index_ids = {line.id for line in index_lines}
    git_ids = {note.id for note in git_notes}

    discrepancies = tuple(
        f"{note_id}: existe en git pero falta en el indice"
        for note_id in sorted(git_ids - index_ids - archived_ids)
    ) + tuple(
        f"{note_id}: esta en el indice pero no existe en git"
        for note_id in sorted(index_ids - git_ids)
    ) + tuple(
        f"{note_id}: archivado pero no existe en git"
        for note_id in sorted(archived_ids - git_ids)
    )

    return len(index_lines), len(git_notes), discrepancies


def _head_rules_content(root: Path) -> str:
    """El contenido de `rules.md` tal como lo tiene comiteado HEAD --
    nunca el arbol de trabajo. Delega en `query.show_file_at_head()`:
    `query.py` es el unico lector del historial de git en todo
    `lib/memory/`.
    """
    relpath = rules.rules_file_path(root).relative_to(root).as_posix()
    return query.show_file_at_head(relpath, root)


def coherence_rules(root: Path) -> tuple[int, int, tuple[str, ...]]:
    """Cruza el `rules.md` COMITEADO en HEAD contra el `rules.md` real del
    arbol de trabajo.

    Devuelve `(lineas_head, lineas_fichero, discrepancias)` -- mismo
    criterio que `coherence()`: los dos numeros reales siempre, gane o
    pierda la comparacion.

    Una linea en el fichero pero no en HEAD es la ventana de I-003: se
    escribio pero el commit que la iba a fijar nunca llego. Una linea en
    HEAD pero ya no en el fichero es la direccion contraria -- alguien
    borro o revirtio a mano una linea ya comiteada.

    Comparacion ciega a la cita: `rules.strip_quote_suffix()` se aplica
    antes de comparar -- el contenido que importa es la REGLA, nunca la
    cita que la acompana.

    Un `rules.md` que todavia no existe no es un fallo: cero reglas es
    un estado valido, `lineas=0` en los dos lados.
    """
    root = Path(root)
    head_content = _head_rules_content(root)

    path = rules.rules_file_path(root)
    file_content = path.read_text(encoding="utf-8") if path.exists() else ""

    head_texts = tuple(
        rules.strip_quote_suffix(text) for text in rules.iter_rule_texts(head_content)
    )
    file_texts = tuple(
        rules.strip_quote_suffix(text) for text in rules.iter_rule_texts(file_content)
    )

    head_set = set(head_texts)
    file_set = set(file_texts)

    discrepancies = tuple(
        f"{text}: existe en un commit de regla pero falta en el fichero de reglas"
        for text in sorted(head_set - file_set)
    ) + tuple(
        f"{text}: esta en el fichero de reglas pero no existe en ningun commit de regla"
        for text in sorted(file_set - head_set)
    )

    return len(head_texts), len(file_texts), discrepancies


def duplicates(root: Path) -> tuple[str, ...]:
    """Identificadores repetidos entre los siete indices vigentes.

    Reutiliza `ids.find_duplicates` sobre las lineas ya leidas -- alarma
    pasiva, no repara nada.
    """
    root = Path(root)
    return ids.find_duplicates(_current_index_lines(root))


def _total_commit_count() -> int:
    """Cuantos commits tiene el historial completo, para
    `possible_unconverted_legacy`. Pasa por `query.run_git_log()`, el
    unico punto de entrada a `git log`. Una rama sin ningun commit vale
    `0`, nunca una excepcion.
    """
    raw_stdout = query.run_git_log("--pretty=format:%H")
    return sum(1 for record in raw_stdout.split("\0") if record)


def _possible_unconverted_legacy(total_commits: int, git_notes: int) -> int | None:
    """"Esto puede ser memoria del sistema anterior sin destilar" -- la
    señal es una desproporcion, no un calculo de contenido: muchos
    commits en el historial y cero notas que `coherence()` sepa
    reconocer. No lee el contenido de esos commits ni sugiere ningun
    comando de destilacion.

    Devuelve el numero real de commits cuando la señal dispara
    (`git_notes == 0` y `total_commits` pasa `_LEGACY_MIN_COMMITS`),
    `None` en cualquier otro caso -- incluido un proyecto recien creado
    con dos o tres commits de arranque.
    """
    if git_notes == 0 and total_commits > _LEGACY_MIN_COMMITS:
        return total_commits
    return None


def zones_state(zones_path: Path) -> tuple[str, int]:
    """Tres estados reales de `zones.json` -- ausente, vacio (incluido un
    fichero corrupto: `zones.load()` lanza `ValueError`, contado aqui
    igual que cero zonas utilizables) y poblado (al menos una zona real).

    Reutilizada por `bin/memory/zones.py list` y `git-memory-doctor.py`
    para que los dos distingan "nunca existio" de "existe vacio" con el
    mismo criterio.

    Devuelve `(estado, numero_de_zonas)`. `numero_de_zonas` es siempre 0
    para "absent" y "empty".
    """
    if not zones_path.exists():
        return "absent", 0
    try:
        zone_count = len(zones.load(zones_path))
    except ValueError:
        zone_count = 0
    if zone_count == 0:
        return "empty", 0
    return "populated", zone_count


def _memory_mounted(root: Path) -> tuple[bool, tuple[str, ...]]:
    """"Este proyecto no tiene la memoria montada" -- comprueba solo lo
    que de verdad hace falta para que `notes.write()` pueda aceptar una
    nota real: los ocho indices vigentes, `zones.json` con al menos una
    zona dada de alta, y `config.json` (solo existencia).

    Devuelve `(montada, faltantes)`. `faltantes` nombra cada pieza
    ausente por su nombre real -- nunca un booleano suelto, para que el
    arranque pueda enseñar el orden correcto (zonas primero, nota
    despues). Un `zones.json` corrupto cuenta aqui igual que si no
    existiera ninguna zona utilizable.
    """
    root = Path(root)
    pm = notes.pm_root(root)
    missing: list[str] = []

    missing_indices = tuple(name for name in INDEX_FILES if not (pm / name).exists())
    if missing_indices:
        missing.append(".claude/project-memory/: faltan " + ", ".join(missing_indices))

    state, _zone_count = zones_state(pm / "zones.json")
    if state == "absent":
        missing.append("zones.json (no existe)")
    elif state == "empty":
        missing.append("zones.json (existe, pero no tiene ninguna zona dada de alta)")

    config_path = pm / "config.json"
    if not config_path.exists():
        missing.append("config.json (no existe)")

    return (not missing, tuple(missing))


def rebuild_plan(root: Path) -> tuple[tuple[tuple[Note, str], ...], tuple[tuple[str, str], ...]]:
    """El mismo cruce que `coherence()` hace para diagnosticar, aqui
    vuelto un PLAN de reparacion -- movido desde
    `bin/memory/reindex.py::_rebuild()`, que reimplementaba esta misma
    logica.

    NO escribe nada -- solo calcula. Quien aplica el plan
    (`indexes.insert()`/`indexes.remove()`) sigue siendo `reindex.py`.

    Devuelve `(to_insert, to_remove)`:
    - `to_insert`: pares `(nota, fichero_destino)` -- una nota real de git
      que no esta archivada y todavia no aparece en ningun indice vigente.
    - `to_remove`: pares `(id, fichero)` -- una linea de indice cuya nota
      ya no existe en git.

    Mismo criterio que `_current_index_lines()` para un indice o
    `ARCHIVED.md` ausentes: cuentan como vacios, nunca revientan -- un
    proyecto recien instalado (`seed()` sin correr todavia) es un estado
    valido, no un fallo. `indexes.seed()` sigue siendo responsabilidad de
    quien llama, exactamente igual que antes de que esta funcion existiera.
    """
    root = Path(root)
    pm = notes.pm_root(root)
    archived = indexes.archived_ids(pm)
    git_notes = {note.id: note for note in query.by_zone(None, None)}

    ids_by_file: dict[str, set[str]] = {}
    for name in INDEX_FILES:
        if name == _ARCHIVE_FILE:
            continue
        try:
            ids_by_file[name] = {line.id for line in indexes.read(name, pm)}
        except FileNotFoundError:
            ids_by_file[name] = set()
    all_index_ids: set[str] = set().union(*ids_by_file.values()) if ids_by_file else set()

    to_insert = tuple(
        (git_notes[note_id], TYPE_INDEX_FILES[git_notes[note_id].type])
        for note_id in sorted(git_notes)
        if note_id not in archived
        and note_id not in all_index_ids
        and git_notes[note_id].type in TYPE_INDEX_FILES
    )
    to_remove = tuple(
        (note_id, name)
        for name, ids_here in ids_by_file.items()
        for note_id in sorted(ids_here)
        if note_id not in git_notes
    )
    return to_insert, to_remove


def build() -> HealthReport:
    """Compone el `HealthReport` que `boot.build()` pinta -- junta lo que
    ya existe, sin volver a calcular nada: `coherence`, `coherence_rules`,
    `duplicates`, `plans_unreflected`.

    `root` sale de `notes.repo_root()`, nunca de `Path.cwd()` a secas: si
    el proceso arrancara desde una subcarpeta anidada, `Path.cwd()`
    apuntaria al sitio equivocado para `notes.pm_root(root)`.

    Si `plans_unreflected()` o `coherence_rules()` revientan (falla `gh`;
    un git corrupto), eso no tumba `build()` entero: se captura aqui, el
    resultado queda vacio y el motivo real va a su propio campo `_error`
    -- nunca tumba el resto del informe (indices, IDs), que sigue siendo
    real.

    `bench.py` (banco adversarial) se retiro entero -- decision del
    propietario, "no lo he autorizado en la vida"; sin campo huerfano.

    `archived_notes`: cuantas de las `git_notes` que ya calculo
    `coherence()` estan archivadas, para el desglose "N live + K archived
    / M notas" que pinta `boot._avisos_block`.
    """
    root = notes.repo_root()
    index_lines, git_notes, index_discrepancies = coherence(root)
    try:
        rule_head_lines, rule_file_lines, rule_discrepancies = coherence_rules(root)
        rule_discrepancies_error = None
    except RuntimeError as exc:
        rule_head_lines, rule_file_lines, rule_discrepancies = 0, 0, ()
        rule_discrepancies_error = str(exc)
    try:
        unreflected = plans_unreflected()
        unreflected_error = None
    except RuntimeError as exc:
        unreflected = ()
        unreflected_error = str(exc)

    archived_notes = len(indexes.archived_ids(notes.pm_root(root)))

    legacy_commits_suspected = _possible_unconverted_legacy(_total_commit_count(), git_notes)
    _mounted, memory_setup_missing = _memory_mounted(root)

    return HealthReport(
        duplicate_ids=duplicates(root),
        index_lines=index_lines,
        git_notes=git_notes,
        index_discrepancies=index_discrepancies,
        plans_unreflected=unreflected,
        plans_unreflected_error=unreflected_error,
        archived_notes=archived_notes,
        legacy_commits_suspected=legacy_commits_suspected,
        memory_setup_missing=memory_setup_missing,
        rule_head_lines=rule_head_lines,
        rule_file_lines=rule_file_lines,
        rule_discrepancies=rule_discrepancies,
        rule_discrepancies_error=rule_discrepancies_error,
    )
