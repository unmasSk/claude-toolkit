"""Formas de datos del sistema de memoria v2 -- contrato en docs/memoria-v2/PIEZAS.md Sec.5.3.

Declara UNA sola vez que forma tiene cada cosa que el sistema mueve.
Dieciseis dataclasses congeladas (``frozen=True``). CERO FUNCIONES, CERO
METODOS -- si a alguna le hace falta un metodo, es que la logica se
esta colando en la capa de datos, y eso va al modulo que corresponda
(mismo principio que ya aplican ``emojis.py`` y ``vocabulary.py``).

No importa ningun otro modulo del sistema -- es el UNICO que puede ser
importado por todos sin crear un ciclo, precisamente porque el no
importa a nadie [PIEZAS.md Sec.5.3 "Quien las usa"].

Las trece clases y de que salida sale cada una [PIEZAS.md Sec.5.3]:

- ``Note``        -- las siete plantillas de commit [TEXTOS Sec.5]
- ``ContextNote`` -- el commit de contexto de cierre, el [NEXT] [TEXTOS Sec.5]
- ``Zone``        -- el rechazo de zona inexistente [TEXTOS Sec.1.1]
- ``IndexLine``   -- la linea de los siete indices vigentes [TEXTOS Sec.4]
- ``ArchiveLine`` -- la linea del archivo, ARCHIVED.md [TEXTOS Sec.4]
- ``Rejection``   -- los diez rechazos de la aduana [TEXTOS Sec.1]
- ``Cluster``     -- el racimo del informe de zona [TEXTOS Sec.2.1]
- ``NoteReport``  -- el informe de una nota por su id [TEXTOS Sec.2.4] --
                     anadida 2026-08-03 (DEUDA.md #24)
- ``ZoneReport``  -- el informe de una zona, llena o vacia [TEXTOS Sec.2.1/2.2]
- ``WordChunk``   -- un trozo del informe por palabra, una pareja de zonas
                     (apareceio al escribir la firma de WordReport)
- ``WordReport``  -- la busqueda por palabra, atraviesa varias zonas [TEXTOS Sec.2.3]
- ``ChainThread`` -- una cabeza de cadena con sus antecesoras [D-056] --
                     anadida 2026-08-25 (bloc de legibilidad, `--chain`)
- ``ChainReport`` -- la vista en cadena de `search.py --chain` [D-056] --
                     anadida 2026-08-25
- ``WriteResult`` -- lo que devuelve toda escritura (la usaban seis
                     firmas sin estar declarada)
- ``HealthReport`` -- el bloque AVISOS del arranque [TEXTOS Sec.3.1]
- ``BootSummary`` -- el menu del dia [TEXTOS Sec.3.1 y Sec.3.2]

``Note`` es una sola clase para los siete tipos (D M R Q X I B), no
siete casi identicas: que campo es obligatorio en que tipo no es
forma, es regla, y su sitio es ``validator.validate_fields`` -- la
unica pieza que valida [decision del propietario, PIEZAS.md Sec.5.3].
``ContextNote`` se queda aparte porque ahi esos campos (zonas, id)
estarian vacios SIEMPRE, y un campo que nunca se rellena no es
opcional, es mentira.

``Zone`` no lleva el recuento de notas como campo: lo calcula quien lo
imprime, leyendo el indice -- ``zones.json`` no sabe cuantas notas hay.

``WordReport``/``WordChunk`` NO reutilizan ``ZoneReport``: sus
recuentos significan "notas que casaron", no "notas de la zona" --
mismo nombre, otro significado, es una trampa que este modulo evita
teniendo dos clases distintas.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Note:
    type: str                      # una de: D M R Q X I B
    id: str                        # "D-030"
    zone1: str
    zone2: str
    headline: str                  # ingles, <=80 caracteres
    description: str               # obligatorio en los siete tipos
    timestamp: datetime            # UTC, del autor del commit
    why: str | None = None         # obligatorio en D
    keys: tuple[str, ...] = ()     # hasta 5
    origin: tuple[str, ...] = ()   # punteros "de que nazco"
    replaces: str | None = None
    awaits: str | None = None      # solo en B
    issue: int | None = None       # opcional en los siete tipos; apunta a la issue del trabajo que la nota reclama


@dataclass(frozen=True)
class ContextNote:                 # el [NEXT] del cierre de sesion
    headline: str
    context: str                   # resumen en prosa corrida, no una lista de puntos
    keys: tuple[str, ...]
    timestamp: datetime


@dataclass(frozen=True)
class Zone:                        # una entrada de zones.json
    name: str
    description: str               # la linea que imprime el rechazo de zona
    aliases: tuple[str, ...]
    # el recuento de notas NO es campo: lo calcula quien lo imprime,
    # leyendo el indice


@dataclass(frozen=True)
class IndexLine:                   # una linea de los siete indices vigentes
    id: str
    zone1: str
    zone2: str
    headline: str
    # sin fecha y sin emoji, a proposito [TEXTOS Sec.6.6]


@dataclass(frozen=True)
class ArchiveLine:                 # una linea de ARCHIVED.md
    date: date
    type: str
    id: str
    zone1: str
    zone2: str
    headline: str
    destination: str               # "replaced" | "closed" | "promoted"
    destination_detail: str        # el ID nuevo, o el motivo del cierre


@dataclass(frozen=True)
class Rejection:                   # lo que produce la aduana al rechazar
    title: str                     # "la zona <<facturacion>> no existe"
    body: str
    relaunch: tuple[str, ...]      # los comandos exactos, aparte del cuerpo
    # separados para que el test "lleva el comando de relanzamiento" sea
    # mecanico y no una busqueda de texto dentro del cuerpo


@dataclass(frozen=True)
class Cluster:                     # una decision con lo que cuelga de ella
    root: Note
    children: tuple[Note, ...]     # por punteros Origin/Replaces, nunca por parecido
    archived_ids: frozenset[str]   # cuales de los hijos estan ya archivados
    # el estado de cada hijo (descartada/vigente/archivada) se deriva de
    # su tipo y de este conjunto: no es un campo suyo


@dataclass(frozen=True)
class NoteReport:                 # el informe de una nota por su id [TEXTOS Sec.2.4]
    note: Note
    generated_at: datetime
    archived: bool                 # vigente/archivada -- cabecera, regla 1
    cluster: Cluster | None        # lo que cuelga de ella; None si no cuelga nada


@dataclass(frozen=True)
class ZoneReport:
    zone: Zone
    generated_at: datetime
    live_count: int
    archived_count: int
    restrictions: tuple[Note, ...]
    blockers: tuple[Note, ...]
    decisions: tuple[Cluster, ...]
    memos: tuple[Note, ...]
    incidents: tuple[Note, ...]
    questions: tuple[Note, ...]
    # Cuales de las notas de arriba estan archivadas ahora mismo -- anadido
    # D-056 (2026-08-25): antes solo `Cluster.archived_ids` sabia distinguir
    # una nota archivada de una vigente; para el resto de tuplas planas
    # (restrictions/blockers/memos/incidents/questions) no habia campo
    # (hueco declarado en su dia, ver docstring de test_report.py, supuesto
    # 4). `report_render.py` lo usa para marcar `archivada` en el listado
    # sin tener que leer `indexes.py` por su cuenta [Sec.9.2, "que NO
    # hace"]. Mismo conjunto GLOBAL de ids archivados que ya calculaba
    # `build_zone` (no solo los de esta zona): comprobar pertenencia no
    # necesita que el conjunto este recortado.
    archived_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class WordChunk:                   # un trozo de la busqueda por palabra: una pareja de zonas
    zone1: str
    zone2: str
    notes: tuple[Note, ...]
    matched_ids: frozenset[str]    # cuales llevan el marcador ›
    # mismo campo y mismo motivo que `ZoneReport.archived_ids` (D-056) --
    # aqui tambien el mismo conjunto GLOBAL, repetido por trozo porque
    # `report_render.py` pinta un trozo a la vez y no recibe el informe
    # entero.
    archived_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class WordReport:
    word: str
    generated_at: datetime
    zone_count: int
    live_count: int
    chunks: tuple[WordChunk, ...]
    # NO reutiliza ZoneReport: sus recuentos son "notas que casaron", no
    # "notas de la zona". Mismo nombre, otro significado = trampa


@dataclass(frozen=True)
class ChainThread:                 # una cabeza de cadena con sus antecesoras [D-056]
    head: Note                     # vigente, o archivada sin sucesor (closed=True)
    closed: bool                   # True = cierre legitimo sin sucesora ("cerrada")
    ancestors: tuple[Note, ...]    # antecesoras via Replaces, la mas reciente primero
    replaced_by: str | None = None  # id de la sucesora real, si closed es False
    # porque la cabeza SI fue sustituida pero su sucesora vive fuera de
    # esta vista (otra pareja de zonas) -- nunca True junto a closed=True


@dataclass(frozen=True)
class ChainReport:                 # la vista en cadena, `search.py --chain` [D-056]
    query: str                     # zona o palabra tal cual se pidio
    generated_at: datetime
    threads: tuple[ChainThread, ...]


@dataclass(frozen=True)
class WriteResult:                 # lo que devuelve toda escritura
    ok: bool
    note_id: str | None            # el identificador asignado, si la hubo
    rejections: tuple[Rejection, ...]   # vacio si salio bien
    git_error: str | None          # el mensaje REAL de git, entero, si fallo


@dataclass(frozen=True)
class HealthReport:
    duplicate_ids: tuple[str, ...]
    index_lines: int               # los dos numeros del "indices coherentes
    git_notes: int                 #   con git (68 lineas / 68 notas)"
    index_discrepancies: tuple[str, ...]   # que nota diverge, no solo cuantas
    plans_unreflected: tuple[tuple[int, int], ...]   # (issue, commits sin reflejar)
    # motivo real si la consulta a gh fallo -- None si se pudo comprobar de
    # verdad (con o sin plans_unreflected) o si no habia nada que consultar
    plans_unreflected_error: str | None = None
    # rule_commits/rule_lines/rule_discrepancies existieron aqui entre el
    # 2026-08-02 y el 2026-08-06 -- los numeros de "reglas coherentes con
    # git" y que regla divergia, alimentados por health.coherence_rules().
    # Se retiraron los tres juntos, el mismo dia que esa funcion [orden
    # del propietario: rules.add() dejo de comitear, asi que no habia
    # ningun commit de regla que cruzar contra el fichero -- ver el
    # docstring de health.py, "coherence_rules SE RETIRA"]. Sin
    # productor, los tres campos habrian quedado zombi (ver
    # bench_caught/bench_total/bench_failures mas abajo para el
    # precedente de "lo que se retira, se retira entero").
    #
    # **RESUCITAN el 2026-08-23, con nombres NUEVOS** [I-003, hallazgo
    # real de Moriarty: `rules.add()` vuelve a comitear de verdad, asi
    # que un `kill -9` entre la escritura y el commit vuelve a poder
    # dejar una linea escrita sin commit detras, en silencio -- ver
    # `health.py`, "coherence_rules RESUCITA", para el porque completo].
    # No se reusan los nombres viejos porque el corte que comparan ya no
    # es el mismo: la version vieja cruzaba TODO el historial de commits
    # de regla contra las lineas del fichero; la nueva compara solo el
    # `rules.md` COMITEADO en HEAD contra el `rules.md` real del arbol
    # de trabajo -- "arqueologia de todo el historial" gritaria siempre
    # sobre las lineas legitimas de la era sin-commit (2026-08-06 a
    # 2026-08-23), que nunca tuvieron un commit PROPIO aunque ya viajen
    # dentro de HEAD.
    rule_head_lines: int = 0       # lineas de regla que HEAD tiene comiteadas ahora mismo
    rule_file_lines: int = 0       # lineas de regla que el fichero real tiene ahora mismo
    rule_discrepancies: tuple[str, ...] = ()   # que linea diverge, no solo cuantas
    # motivo real si un git corrupto impidio evaluar coherence_rules() --
    # None si se pudo comprobar de verdad. Mismo patron que plans_unreflected_error.
    rule_discrepancies_error: str | None = None
    # Cuantas de las `git_notes` de arriba estan archivadas -- anadido
    # 2026-08-03 [TEXTOS.md Sec.5, decision del propietario]: sin este
    # numero, "N lineas / M notas" no explica por que M > N cuando hay
    # notas archivadas (se excluyen de los indices vigentes a proposito).
    # `boot._avisos_block` lo usa para pintar el desglose "live + archived"
    # solo cuando archived_notes > 0.
    archived_notes: int = 0
    # bench.py se retira entero, 2026-08-03 [decision del propietario:
    # "no lo he autorizado en la vida"] -- bench_caught/bench_total/
    # bench_failures desaparecen del molde con el, sin dejar campo
    # huerfano.
    # Aviso A, anadido 2026-08-06 [ver health.possible_unconverted_legacy
    # para el umbral y el porque]: cuantos commits tiene el historial
    # cuando la señal "muchos commits, cero notas reconocidas" dispara --
    # `None` cuando no dispara (haya notas reconocidas, o el historial
    # sea corto de verdad, p.ej. un proyecto recien creado). El numero
    # real viaja aqui, nunca un bool suelto, para que `boot.py` no tenga
    # que recalcularlo para pintar el aviso.
    legacy_commits_suspected: int | None = None
    # Aviso B, anadido 2026-08-06 [ver health.memory_mounted para el
    # mecanismo]: que falta para poder guardar la primera nota en este
    # proyecto -- vacio cuando no falta nada (memoria montada de verdad).
    # Nombra cada pieza ausente por su nombre real, nunca un bool suelto.
    memory_setup_missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class BootSummary:
    project: str
    generated_at: datetime
    # Donde se dejo el trabajo y donde estas tu, tras traer del remoto.
    # `None` solo si el arranque corrio sin poder preguntarselo a git.
    remote: object | None
    context: ContextNote | None    # None el primer dia: el arranque lo dice en alto
    blockers: tuple[Note, ...]
    restrictions: tuple[Note, ...]     # todas, sin tope [spec Sec.8.3]
    open_questions: int
    open_issues: int
    open_incidents: int
    # Las preguntas y las incidencias vigentes, enteras y no solo
    # contadas: un numero suelto no dice cual te para hoy [decision del
    # propietario -- "con seis preguntas abiertas yo no me entero de
    # nada"]. Sin valor por defecto, como el resto: un molde a medio
    # llenar es justo lo que este campo existe para impedir.
    questions: tuple[Note, ...]
    incidents: tuple[Note, ...]
    health: HealthReport
