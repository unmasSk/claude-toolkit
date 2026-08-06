"""Comprobar que el sistema no se ha roto solo -- contrato en
docs/memoria-v2/PIEZAS.md Sec.9.4.

De que salida se deriva: el bloque `AVISOS` del arranque [TEXTOS.md
Sec.3.1]:

    ⚠️  plan #47: 3 commits sin reflejar en la issue
    ✓  IDs sin duplicados (68 notas)
    ✓  indices coherentes con git (68 lineas / 68 notas)

Los dos ✓ importan tanto como el ⚠️: un chequeo que solo habla cuando
falla es indistinguible de uno que no se ejecuta -- ya paso en el v1,
seis hooks corriendo version vieja durante dias sin que nada lo dijera.
Por eso `coherence()` siempre devuelve los dos numeros reales, gane o
pierda la comparacion, nunca solo la lista de discrepancias.

**No repara nada.** Detecta y enseña -- reparar los indices es un
comando aparte, explicito, con modo de solo-diagnostico [Sec.9.4, "Que
NO hace"].

**Superficie de esta pieza segun PIEZAS.md Sec.9.4 declara CINCO
funciones** (`coherence`, `coherence_rules`, `duplicates`,
`plans_unreflected`, `build`). De esas cinco, **CUATRO siguen vigentes
hoy** -- `coherence_rules` se retira el 2026-08-06 [ver "coherence_rules
SE RETIRA" mas abajo, donde vivia su parrafo propio hasta hoy].
`coherence` cubre las filas 1-3 de "Sus tests" (Sec.9.4). `plans_unreflected`
nacio sin fila propia porque `vocabulary.FIELDS["issue"].reader` la declara
como el UNICO lector real del campo `issue` (regla de los tres estados,
Sec.6.1 -- confirmado con el orquestador antes de escribirla). `duplicates`
(reutiliza `ids.find_duplicates`, Sec.7.2) se anadio el mismo dia que
`coherence_rules`. `build` compone las tres que quedan en el
`HealthReport` que el arranque pinta, sin volver a calcular nada.

**Una SEXTA funcion, `rebuild_plan`, se anade el 2026-08-02** -- fuera de
la superficie que Sec.9.4 declara letra por letra (ese numero no se toca
en esta tarea; queda anotado aqui para que este docstring no mienta sobre
su propio fichero). Ver su propio parrafo, junto a `duplicates`, para el
porque y el mecanismo.

**SEPTIMA y OCTAVA funciones, `possible_unconverted_legacy` y
`memory_mounted`, se anaden el 2026-08-06** -- tambien fuera de la
superficie letra por letra de Sec.9.4, mismo motivo que `rebuild_plan`.
Cierran los dos fallos reales encontrados ejecutando: un proyecto con
memoria del sistema ANTERIOR sin destilar se presentaba como vacio de
verdad (nada, en ningun sitio, avisaba de que habia memoria sin
convertir), y un proyecto SIN la memoria montada recibia el mismo
informe en verde que uno sano y vacio -- con un pie de arranque que
encima invitaba a un comando garantizado a fallar (`--zones <zona1>
<zona2>` sin que existiera ninguna zona). Ver el docstring de cada
funcion para el umbral, el mecanismo y el porque completo.

`coherence_rules(root)` existio entre el 2026-08-02 y el 2026-08-06 como
la hermana de `coherence()` para el fichero de reglas -- ver
"coherence_rules SE RETIRA" mas abajo para el porque completo de su
retirada.

`coherence(root)` cruza dos fuentes, cada una con su propia pieza ya en
produccion, sin reimplementar ninguna:

- **Lineas de indice**: `indexes.read(name, root)` sobre los SIETE
  indices vigentes (`vocabulary.INDEX_FILES` sin `ARCHIVED.md` -- una
  nota archivada ya esta retirada, no es "lo que hay ahora mismo").
- **Notas reales en git**: `query.by_zone(None, None)` con los dos ejes
  en `None` no filtra nada, asi que devuelve exactamente las notas que
  `query._all_notes()` extrae del historial completo (cada commit que
  `format.parse_message` reconoce como nota) -- la funcion PUBLICA que
  ya hace esto, en vez de reimplementar el parseo de `git log` una
  cuarta vez en el sistema.

La divergencia en los dos sentidos (fila 1 y fila 2 de la tabla) sale
de comparar los dos conjuntos de IDs: lo que esta en git y no en el
indice ("falta en indice"), y lo que esta en el indice y no en git
("no existe en git"). Cada discrepancia nombra el ID afectado en texto,
para que el informe pueda decir cual nota, no solo "algo diverge".

**`coherence_rules(root)` SE RETIRA el 2026-08-06** `[orden del
propietario]`. Vivio desde el 2026-08-02 `[decision del orquestador en
modo autonomo, derivada del hallazgo de Argus, PIEZAS.md Sec.9.4]` como
la hermana de `coherence()` para el fichero de reglas: un remember se
guardaba EN DOS SITIOS A LA VEZ (`rules.py`, Sec.9.7) -- un commit en
git y una linea en `.claude/project-memory/rules.md` -- y esta funcion
cruzaba los commits de regla reales del historial contra las lineas del
fichero para cazar un desfase entre los dos sitios (un proceso matado a
medio camino de la escritura antigua, o un `rules.md` tocado a mano).

Ese motivo desaparece el mismo dia que se retira esta funcion:
`rules.add()` (`lib/memory/rules.py`) deja de comitear nada -- escribe
la linea en `rules.md`, atomicamente, y se acaba ahi [ver el docstring
de ese modulo para el detalle completo]. Sin ningun commit de regla que
la propia escritura genere NUNCA MAS, `coherence_rules()` quedaria
ESTRUCTURALMENTE rota, no solo desactualizada: cada regla nueva, sin
excepcion, pasaria a vivir en el fichero sin ningun commit de regla
detras -- exactamente la forma que hasta hoy significaba "regla
perdida, avisa". El chequeo dejaria de detectar una corrupcion real y
pasaria a gritar SIEMPRE, sobre cualquier regla recien anadida, para
todo el mundo: un falso positivo permanente, peor que no tener el
chequeo.

Se retira ENTERA -- ella misma, `_rule_commit_texts()` (su unico
colaborador privado, el lector de commits de regla via
`query.run_git_log()`), los campos `HealthReport.rule_commits`/
`rule_lines`/`rule_discrepancies` (sin productor desde hoy, campos
zombi si se quedaran) y la linea "rules match git"/"rules do not match
git" que `boot._avisos_block()` pintaba en el bloque CHECKS
[`lib/memory/boot.py`] -- sin commits de regla no hay divergencia que
detectar, asi que CHECKS deja de mencionar las reglas en absoluto, ni
en verde ni en rojo. Varios tests existentes en `tests/memory/
test_boot.py`, `tests/memory/test_health.py` y una referencia de
docstring en `tests/memory/test_boundary.py` fijaban esta funcion --
fuera del alcance de esta tarea, quien la retire de produccion los
reconcilia por separado.

**`plans_unreflected()` vive desde el 2026-08-02 en `health_plans.py`**
-- partida fuera de aqui por tamano, mismo motivo y mismo techo que
`validator_pointers.py` (500 lineas; con el banco adversarial anadido,
esta pieza los habria pasado). `health.py` importa `plans_unreflected`
de alli de forma PLANA y lo reexpone bajo el mismo nombre, asi que
`health.plans_unreflected` -- el lector real que
`vocabulary.FIELDS["issue"].reader` declara -- sigue funcionando igual.
Ver el docstring de `health_plans.py` para el mecanismo completo (dos
pasos: commits que citan una issue via `query.run_git_log()`, actividad
real de esa issue via `gh issue view`) y el porque de nunca devolver un
resultado inventado si `gh` falla.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca
estandar de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
(`import ids`, `import indexes`, `import notes`, `import query`,
`import rules`, `from vocabulary import INDEX_FILES`)
[PIEZAS.md Sec.3.3bis].

**Revision 2026-08-02, primera tanda** -- tres correcciones sobre
`coherence()`/superficie (nota archivada gritaba en falso;
`duplicates()` declarada sin cuerpo; los indices se leian fuera de
`.claude/project-memory/`), detalle completo en la memoria de agente
`memoria-v2-build.md`, no repetido letra por letra aqui.

**Revision 2026-08-02, segunda tanda (hallazgos de Argus)** -- ver los
docstrings de `_current_index_lines`/`coherence`/`build` mas abajo:
indice o `ARCHIVED.md` ausentes cuentan como cero en vez de reventar
[punto 1], y `plans_unreflected_error` en `HealthReport` [punto 2].

**Revision 2026-08-02, ronda 2 (Moriarty)** -- tres hallazgos mas,
demostrados ejecutando, detalle en los docstrings de cada funcion: (1)
`build()` ya no tira el tercer valor de `coherence_rules()`, viaja en
`HealthReport.rule_discrepancies`; (2) `_rule_commit_texts()` y (3)
`_issue_commit_dates()` -- cada una con su propio `git log` directo, sin
pasar por `query.py` -- trataban una rama sin ningun commit todavia como
un fallo real en vez del estado valido que ya es en `query._git_log()`.

**Revision 2026-08-02, tercera tanda** -- consolidacion del lector de
`git log` [encargo del orquestador, Sec.8.2 "Es el unico lector del
historial"]: `_rule_commit_texts()`/`_issue_commit_dates()` tenian cada
una su propio `gitcmd.run(["log", ...])` a mano, el mismo patron de tres
lectores sincronizados que este modulo cita desde el dia 1 (TESTIGO
Sec.3). Las dos pasan ahora por `query.run_git_log()` -- mismo punto de
entrada que usa `context.latest()` -- y `gitcmd` deja de importarse aqui.
"""

from pathlib import Path

import ids
import indexes
import notes
import query
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
    del repositorio [correccion 2026-08-02, ver `notes.pm_root()`].

    Un indice AUSENTE cuenta como CERO lineas para ESE fichero, nunca
    revienta [revision 2026-08-02, punto 1 del encargo]: un proyecto
    recien instalado no tiene ninguno de los ocho todavia (`seed()` nunca
    corrio), y eso es su estado real, no un fallo -- sin este descuento,
    `health.build()`/`boot.build()` reventaban en la primerisima sesion
    de cualquier proyecto. Si el proyecto SI tiene notas y falta justo un
    fichero (corrupcion real, no "nunca sembrado"), el hueco no queda en
    silencio: `coherence()` sigue viendo `index_lines != git_notes` mas
    abajo -- este descuento nunca inventa coherencia, solo evita reventar
    antes de poder compararlo.
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
    texto de cada divergencia encontrada en cualquiera de los dos
    sentidos (vacio si todo coincide).

    Una nota archivada (`indexes.archived_ids(root)`) nunca cuenta como
    "falta en el indice" -- ya salio de los indices vigentes a proposito
    [ver "Revision 2026-08-02" en el docstring del modulo]. Un indice o
    un `ARCHIVED.md` que todavia no existen cuentan como cero, nunca como
    un fallo que tumbe esta funcion [`_current_index_lines`,
    `indexes.archived_ids`, punto 1 del encargo] -- una corrupcion real
    (falta justo un fichero, con el resto ya sembrado) sigue saliendo
    como `index_lines != git_notes` mas abajo, nunca en silencio.

    **Las archivadas TAMBIEN se cruzan contra git, no solo se restan**
    [2026-08-04, hallazgo real (Moriarty): antes `archived_ids` solo se
    usaba para DESCONTAR de "falta en el indice" -- nunca se comprobaba
    que cada id archivado correspondiera a una nota real de git. Con
    `ARCHIVED.md` corrompido (ver `notes.py::_reject_close_reason_multiline`,
    arreglado el mismo dia) esto dejaba pasar una entrada fantasma sin
    decir nada: el arranque pintaba `✓ indexes match git` con "K live + J
    archived / M notes" donde J venia inflado por un id que nunca existio
    en git -- un visto bueno verde cuyos propios numeros no sumaban]. Un
    id archivado que no existe en ningun commit real de git es tan
    discrepancia como las otras dos -- se anade al mismo desglose que ya
    pinta `boot._avisos_block` bajo "indexes match/do not match git", sin
    tocar ese fichero ni `HealthReport`: la lista de discrepancias ya
    viajaba entera hasta alli.
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


def duplicates(root: Path) -> tuple[str, ...]:
    """Identificadores repetidos entre los siete indices vigentes -- el
    "IDs sin duplicados (N notas)" del arranque [TEXTOS.md Sec.3.1].

    Reutiliza `ids.find_duplicates` (Sec.7.2) sobre las lineas ya leidas
    -- alarma pasiva, no repara nada [mismo contrato que `ids.py`]. `root`
    se normaliza a `Path` igual que `coherence()`.
    """
    root = Path(root)
    return ids.find_duplicates(_current_index_lines(root))


def _total_commit_count() -> int:
    """Cuantos commits tiene el historial completo -- para el Aviso A
    (`possible_unconverted_legacy`), anadido 2026-08-06.

    Pasa por `query.run_git_log()`, el UNICO punto de entrada a `git log`
    de todo el sistema desde el 2026-08-02 [ver "tercera tanda" en el
    docstring del modulo] -- nunca un `git rev-list --count` aparte, que
    seria un cuarto lector de historial paralelo al ya consolidado. Una
    rama sin ningun commit todavia devuelve cadena vacia (estado valido,
    `run_git_log()`) y aqui vale `0`, nunca una excepcion.
    """
    raw_stdout = query.run_git_log("--pretty=format:%H")
    return sum(1 for record in raw_stdout.split("\0") if record)


def _possible_unconverted_legacy(total_commits: int, git_notes: int) -> int | None:
    """Aviso A -- "esto puede ser memoria del sistema anterior sin
    destilar" [encargo 2026-08-06, fallo 1 real: un proyecto con once
    commits y tres de ellos con decisiones reales del sistema anterior en
    el cuerpo (`Memo:`/`Why:`/`Decision:`) recibia el mismo informe verde
    que uno vacio de verdad, sin que nada, en ningun sitio del sistema,
    avisara de que hay memoria sin convertir].

    La señal es una desproporcion, no un calculo de contenido: MUCHOS
    commits en el historial y CERO notas que `query`/`coherence()` sepan
    reconocer. Este modulo no lee el CONTENIDO de esos commits -- eso es
    trabajo de la destilacion, un protocolo aparte que esta funcion nunca
    invoca ni sugiere [encargo explicito: "no propongas ningun comando"].
    Solo dice, con los dos numeros reales, que la proporcion es rara y
    por que puede serlo.

    Devuelve el numero real de commits cuando la señal dispara (`git_notes
    == 0` y `total_commits` pasa `_LEGACY_MIN_COMMITS`, ver su propio
    comentario para el porque del umbral), `None` en cualquier otro caso
    -- incluido el caso mas comun, un proyecto real con notas reconocidas
    de sobra, y el caso que este aviso existe para NO ensuciar: un
    proyecto recien creado con dos o tres commits de arranque.
    """
    if git_notes == 0 and total_commits > _LEGACY_MIN_COMMITS:
        return total_commits
    return None


def zones_state(zones_path: Path) -> tuple[str, int]:
    """Tres estados reales de `zones.json` -- ausente (nunca creado),
    vacio (presente pero sin ninguna zona dada de alta, incluido un
    fichero corrupto: `zones.load()` lanza `ValueError` a proposito
    ["fallo en alto, nunca silencioso", su propio docstring], contado
    aqui igual que cero zonas utilizables, mismo criterio que
    `memory_mounted()` ya aplicaba antes de esta funcion existir) y
    poblado (al menos una zona real).

    Extraida de dentro de `memory_mounted()` [2026-08-06] para que un
    segundo llamador (`bin/memory/zones.py list`, y el chequeo homologo
    de `git-memory-doctor.py`) reutilice la MISMA distincion en vez de
    volver a leer el fichero por su cuenta -- el fallo real que esto
    cierra: `zones.py list` imprimia el mismo texto ("zones.json tiene 0
    zonas") tanto si el fichero nunca existio como si existia vacio.

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
    """Aviso B -- "este proyecto no tiene la memoria montada" [encargo
    2026-08-06, fallo 2 real: el mismo informe en verde salia en un
    proyecto sin `.claude/project-memory/`, sin `zones.json` y sin
    indices -- tres vistos buenos y ni una palabra de que ahi no hay nada
    montado. Y la unica llamada a la accion del arranque en ese estado
    (`_FIRST_NOTE_HINT`, "la primera nota se guarda asi: `gitmem note ...
    --zones <zona1> <zona2>`") pedia dos zonas cuando no existe ninguna
    -- el primer comando que un usuario nuevo prueba, garantizado a
    fallar contra `validator.validate_zones`].

    Comprueba solo lo que de verdad hace falta para que `notes.write()`
    pueda aceptar una nota real, nunca mas: los ocho indices vigentes en
    `notes.pm_root(root)` [mismos ocho ficheros de `vocabulary.INDEX_FILES`
    que `_current_index_lines()`/`rebuild_plan()` ya recorren], `zones.json`
    con AL MENOS una zona dada de alta [`zones.load()`, Sec.6.2 --
    reutilizado tal cual, nunca una segunda lectura de JSON a mano], y
    `config.json` [Sec.6.3, solo existencia: su contenido no cambia si se
    puede guardar una nota o no].

    Devuelve `(montada, faltantes)`. `faltantes` nombra cada pieza
    ausente por su nombre real -- nunca un booleano suelto, que obligaria
    a quien lo pinta (`boot.py`) a adivinar el porque, y es exactamente lo
    que el pie del arranque necesita para enseñar el orden correcto
    (zonas primero, nota despues) en vez del hint de dos zonas
    inventadas. Un `zones.json` corrupto [`zones.load()` lanza
    `ValueError` a proposito -- ver su propio docstring, "fallo en alto,
    nunca silencioso"] cuenta aqui igual que si no existiera ninguna zona
    utilizable: no puede guardarse una nota con el de todos modos, y esta
    comprobacion no es el sitio que grita la corrupcion en si (eso ya lo
    hace `zones.load()` en alto para quien SI necesita escribir en el
    fichero) -- aqui solo importa si la primera nota puede guardarse hoy.
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
    """El mismo cruce que `coherence()` hace para diagnosticar, aqui vuelto
    un PLAN de reparacion -- anadido 2026-08-02, movido desde
    `bin/memory/reindex.py::_rebuild()` [hallazgo real: el script
    reimplementaba treinta lineas de esta misma logica de cruce, y la
    regla de Sec.10 para los once/diez scripts es "recibe argumentos,
    llama a una funcion e imprime" -- un script que decide QUE falta y a
    QUE fichero le toca es logica que se le habia colado].

    **NO escribe nada** -- `health.py` "no repara, detecta y enseña" [ver
    docstring del modulo]; esta funcion sigue esa misma regla: solo
    calcula. Quien aplica el plan (`indexes.insert()`/`indexes.remove()`)
    sigue siendo `reindex.py`, el unico llamador -- el reparto entre
    "decidir" (aqui) y "escribir e imprimir" (el script) no cambia con
    este movimiento, solo el sitio donde vive la decision.

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
    """Compone el `HealthReport` que `boot.build()` pinta [Sec.9.5, "no
    calcula salud (llama a health)"] -- junta lo que ya existe, sin volver
    a calcular nada: `coherence(root)`, `duplicates(root)` (cierra el
    circulo que `ids.py` declaraba desde su dia -- "IDs sin duplicados"
    del arranque necesitaba a `health.duplicates` como llamador real) y
    `plans_unreflected()`.

    **`root` sale de `notes.repo_root()`, nunca de `Path.cwd()` a secas**
    [correccion 2026-08-02, mismo agujero y mismo arreglo que
    `boot.build()` -- ver su propio docstring para el porque completo]:
    `coherence(root)`/`duplicates(root)` hacen, por dentro,
    `notes.pm_root(root)` -- aritmetica de rutas pura, sin tirar de git --
    para localizar los ocho indices; si `root` fuera `Path.cwd()` y el
    proceso arrancara desde una subcarpeta anidada, esa composicion
    apuntaria al sitio equivocado. `notes.repo_root()` resuelve via `git
    rev-parse --show-toplevel` [notes_commit.py], igual que ya hace el
    resto del sistema para la misma raiz, y se lo pasa tal cual a
    `coherence`/`duplicates`: una sola raiz para las dos llamadas.

    **Revision 2026-08-02 (hallazgos de Argus):** si `plans_unreflected()`
    revienta (falla `gh`: sin red, sin autenticar, issue borrada -- su
    propio docstring sigue sin tragar la excepcion), eso YA NO tumba
    `build()` entero: se captura aqui una vez, `plans_unreflected` queda
    `()` y el motivo real va a `plans_unreflected_error` -- nunca un `()`
    sin ese campo (mentiria "todo correcto"), nunca tampoco tumbar el
    resto del informe (indices, IDs), que sigue siendo real.

    **`coherence_rules()` se retira el 2026-08-06** [ver su propio
    parrafo en el docstring del modulo] -- `build()` deja de llamarla y
    `HealthReport` deja de llevar `rule_commits`/`rule_lines`/
    `rule_discrepancies`: entraron aqui el 2026-08-02 (hallazgos de
    Argus, y despues el tercer valor en la ronda 2 de Moriarty) y salen
    juntos, el mismo dia que su unico productor.

    **`bench.py` se retira entero, 2026-08-03** [decision del propietario:
    "no lo he autorizado en la vida"] -- este modulo ya no importa
    `bench`, no llama a ningun banco adversarial, y `HealthReport` ya no
    lleva `bench_caught`/`bench_total`/`bench_failures`. Sin campo
    huerfano: lo que se retira, se retira entero.

    **`archived_notes` se anade 2026-08-03** [TEXTOS.md Sec.5, "El aviso
    de coherencia, cuando hay notas archivadas"]: el desglose que
    `boot._avisos_block` pinta ("N live + K archived / M notas") necesita
    saber cuantas de las `git_notes` que ya calculo `coherence()` estan
    archivadas -- se reutiliza `indexes.archived_ids(notes.pm_root(root))`,
    la misma fuente unica que `coherence()` ya consulta por dentro para no
    contar un archivado como "falta en el indice"; aqui solo se cuenta,
    nunca se recalcula la pertenencia.
    """
    root = notes.repo_root()
    index_lines, git_notes, index_discrepancies = coherence(root)
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
    )
