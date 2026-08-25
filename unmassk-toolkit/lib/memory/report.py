"""Decidir QUE se enseña de una zona y en que orden -- contrato en
docs/memoria-v2/PIEZAS.md Sec.9.2 (compartida con report_render.py, Sec.9.3).

Este fichero SOLO decide que datos entran y en que categoria. Convertir
eso en texto (la letra grande de "CERO NOTAS", el simbolo `>` de una
linea que caso, el orden final de impresion) es `report_render.py`, la
pieza siguiente -- no se adelanta aqui, es exactamente el reparto que
fija el encargo de esta tarea.

De que salida se deriva [TEXTOS.md]: el informe de zona con racimo
(Sec.2.1), la zona vacia (Sec.2.2) y la busqueda por palabra (Sec.2.3).

Con que se construye, y por que nunca una alternativa [PIEZAS.md Sec.9.2,
"quien los llama"]:

- ``query`` es el UNICO lector del historial [Sec.8.2] -- toda ``Note``
  de este modulo sale de ``query.by_zone``/``query.by_word``, nunca de
  parsear nada por cuenta propia.
- ``clusters`` agrupa el racimo de decisiones por punteros Origin/Replaces
  [Sec.9.1] -- nunca por parecido.
- ``indexes``/``zones`` dan el estado que ``query`` no puede dar por si
  solo: cuales notas estan archivadas, y la ficha de la zona (nombre real
  + descripcion).

UN HECHO REAL, MEDIDO EN VIVO en su dia (no supuesto), ya CORREGIDO
[revision 2026-08-02, ver ``notes.pm_root()`` para el incidente
completo]: ``notes.write()`` calculaba su ``root`` con
``gitcmd.repo_root(Path.cwd())`` y lo pasaba tal cual a
``indexes.seed()``/``indexes.insert()`` -- la raiz PELADA del
repositorio, sin ``.claude/project-memory`` por ningun lado -- mientras
que este modulo, ``zones.py`` y ``rules.py`` ya escribian/leian en
``<root>/.claude/project-memory/``. Con ``notes.write()`` arreglado
(escribe en ``notes.pm_root(root)``, ahora publica), el sistema entero
esta de acuerdo en una sola ruta.

Este modulo NO LEE NINGUNO DE LOS SIETE INDICES VIGENTES. No le hace
falta -- ``query`` ya da el historial COMPLETO (vigente y archivado,
porque git nunca borra un commit), asi que la unica pieza que de verdad
falta y que ningun indice vigente puede dar es "cual de estos
identificadores esta archivado ahora mismo", y esa la da
``indexes.archived_ids()`` -- fuente unica desde 2026-08-02 [hallazgo de
Argus]: antes este modulo tenia su propia copia privada de ese calculo
(``_archived_ids``) y de la ruta (``_pm_root``, byte a byte igual que
``notes.pm_root``); ahora usa ``notes.pm_root(root)`` y
``indexes.archived_ids(pm_root)`` directamente, las mismas que usan
``boot.py``/``health.py``. Un ``ARCHIVED.md`` que todavia no existe
cuenta como cero archivados, no como un fallo -- mismo criterio que el
resto del sistema.

SUPUESTO DECLARADO, sin fuente literal en Sec.9.2 (mismo tipo de hueco
que test_report.py ya declara en su propio docstring, supuesto 3): que
eje -- ``zone1``, ``zone2``, o los dos -- casa el parametro ``zone: str``
de ``build_zone``. Sec.9.2 no lo fija, y el propio test lo evita a
proposito sembrando siempre ``zone1 == zone2``. Aqui se elige **cualquiera
de los dos ejes** (una nota entra si `zone1 == zone` O `zone2 == zone`):
es la lectura mas util de "el informe de esta zona" -- una decision
etiquetada `plugin/release` importa tanto a quien mira `plugin` como a
quien mira `release` -- y es la unica opcion de las tres posibles
("solo zone1", "solo zone2", "cualquiera") que no deja invisible una nota
real con el propio ejemplo que trae el test (`zone1 == zone2`, donde las
tres opciones coinciden). Queda anotado, como pide Sec.9.2, para quien
lo audite despues.

Que NO hace [Sec.9.2]: no formatea (report_render). No devuelve nunca una
lista de commits -- buscar devuelve el estado de una zona, siempre
[spec Sec.8]. No decide que esta archivado por si solo -- se lo dice
`indexes.read_archive`.

Quien lo llama. `bin/memory/search.py` [Sec.9.2]. `dispatch` tambien lo
llamaba -- retirado entero [decision del propietario, 2026-08-03, B20]:
cada agente busca su propia memoria de proyecto, ya no hay un vigilante
que reparta por oficio.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
[PIEZAS.md Sec.3.3bis].
"""

from datetime import datetime, timezone
from pathlib import Path

import clusters
import gitcmd
import indexes
import notes
import query
import zones as zones_mod
from model import (
    ArchiveLine,
    ChainReport,
    ChainThread,
    Cluster,
    Note,
    NoteReport,
    WordChunk,
    WordReport,
    Zone,
    ZoneReport,
)

_DECISION_TYPES = frozenset({"D", "X"})
_RESTRICTION_TYPES = frozenset({"R"})
_BLOCKER_TYPES = frozenset({"B"})
_MEMO_TYPES = frozenset({"M"})
_INCIDENT_TYPES = frozenset({"I"})
_QUESTION_TYPES = frozenset({"Q"})


def _repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def _zones_json_path(pm_root: Path) -> Path:
    return pm_root / "zones.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_zone(zone: str, pm_root: Path) -> Zone:
    """La ficha real de ``zone`` en ``zones.json``. Falla en alto si la
    zona no esta registrada -- el precondicion que TEXTOS Sec.2.2 fija
    para el informe de zona vacia ("la zona existe en zones.json") no
    incluye el caso de una zona nunca registrada; ese es otro flujo
    (TEXTOS Sec.1.1) que no es responsabilidad de este modulo.
    """
    zone_obj = zones_mod.load(_zones_json_path(pm_root)).get(zone)
    if zone_obj is None:
        raise ValueError(
            f"report.build_zone: la zona {zone!r} no esta registrada en zones.json"
        )
    return zone_obj


def _notes_touching_zone(zone: str) -> tuple[Note, ...]:
    """Todas las notas del historial (vigentes y archivadas -- git nunca
    borra un commit) cuyo ``zone1`` o ``zone2`` es ``zone``. Ver el
    supuesto del eje en el docstring del modulo.
    """
    seen: dict[str, Note] = {}
    for note in query.by_zone(zone, None) + query.by_zone(None, zone):
        seen[note.id] = note
    return tuple(seen.values())


def _filter_archived(
    notes: tuple[Note, ...], archived_ids: frozenset[str], include_archived: bool
) -> tuple[Note, ...]:
    if include_archived:
        return notes
    return tuple(n for n in notes if n.id not in archived_ids)


def _by_type(notes: tuple[Note, ...], types: frozenset[str]) -> tuple[Note, ...]:
    return tuple(sorted((n for n in notes if n.type in types), key=lambda n: n.id))


def build_zone(zone: str, include_archived: bool) -> ZoneReport:
    """El informe de ``zone``: recuentos siempre reales, contenido segun
    ``include_archived`` -- fila 2 y fila 3 de Sec.9.2, "Sus tests".
    """
    root = _repo_root()
    pm_root = notes.pm_root(root)
    zone_obj = _load_zone(zone, pm_root)
    archived_ids = indexes.archived_ids(pm_root)

    all_notes = _notes_touching_zone(zone)
    live_count = sum(1 for n in all_notes if n.id not in archived_ids)
    archived_count = sum(1 for n in all_notes if n.id in archived_ids)

    visible = _filter_archived(all_notes, archived_ids, include_archived)
    decisions = clusters.group(_by_type(visible, _DECISION_TYPES), archived_ids)

    return ZoneReport(
        zone=zone_obj,
        generated_at=_now(),
        live_count=live_count,
        archived_count=archived_count,
        restrictions=_by_type(visible, _RESTRICTION_TYPES),
        blockers=_by_type(visible, _BLOCKER_TYPES),
        decisions=decisions,
        memos=_by_type(visible, _MEMO_TYPES),
        incidents=_by_type(visible, _INCIDENT_TYPES),
        questions=_by_type(visible, _QUESTION_TYPES),
        archived_ids=archived_ids,
    )


def build_word(word: str, include_archived: bool) -> WordReport:
    """La busqueda por palabra: un ``WordChunk`` por pareja de zonas que
    caso, con el estado COMPLETO de esa pareja (fila 5 de Sec.9.2, "Sus
    tests") y que notas de esa pareja casaron de verdad.

    ``WordReport.word`` se guarda en minusculas -- es la palabra
    BUSCADA (una llave), no el texto de ninguna nota, y la comparacion
    en ``query.by_word`` ya es insensible a mayusculas [hallazgo en
    vivo 2026-08-06, docstring de ``query.by_word``]. Sin esto el
    informe repetia la palabra tal cual se tecleo (`WINDOWS`) aunque la
    busqueda ya encontrara `windows`/`Windows` por igual -- normalizar
    aqui, en el constructor, y no en ``report_render.py``, porque este
    modulo es el que "decide QUE se enseña" [docstring de
    ``report_render.py``]; el pintor solo pinta lo que recibe. Las
    lineas que casaron dentro de cada nota siguen con su texto
    ORIGINAL -- eso no cambia, solo la palabra buscada que se repite en
    la cabecera y en el pie del informe.
    """
    root = _repo_root()
    pm_root = notes.pm_root(root)
    archived_ids = indexes.archived_ids(pm_root)

    matched_ids_by_pair: dict[tuple[str, str], set[str]] = {}
    for note, _matched_lines in query.by_word(word):
        matched_ids_by_pair.setdefault((note.zone1, note.zone2), set()).add(note.id)

    chunks = []
    for (zone1, zone2), matched_ids_here in matched_ids_by_pair.items():
        pair_notes = _filter_archived(
            query.by_zone(zone1, zone2), archived_ids, include_archived
        )
        matched_ids = frozenset(n.id for n in pair_notes if n.id in matched_ids_here)
        chunks.append(
            WordChunk(
                zone1=zone1,
                zone2=zone2,
                notes=pair_notes,
                matched_ids=matched_ids,
                archived_ids=archived_ids,
            )
        )
    chunks.sort(key=lambda c: (c.zone1, c.zone2))

    return WordReport(
        word=word.lower(),
        generated_at=_now(),
        zone_count=len(chunks),
        live_count=sum(len(c.matched_ids) for c in chunks),
        chunks=tuple(chunks),
    )


def build_note(note_id: str) -> NoteReport | None:
    """El informe de una nota concreta por su identificador -- TEXTOS.md
    Sec.2.4 (molde dictado por el propietario, 2026-08-03), cierra
    DEUDA.md #24. ``None`` si ``note_id`` no existe -- nunca lanza,
    nunca fabrica un informe vacio [mismo contrato que ``query.by_id``].

    A diferencia de ``build_zone``, el racimo aqui NO sale de
    ``clusters.group`` -- esa funcion elige la raiz del racimo por "la
    nota viva mas reciente" [spec Sec.8], un criterio pensado para el
    informe de ZONA (donde ninguna nota concreta es "la pedida"). Aqui
    la nota PEDIDA es la raiz siempre, sea cual sea su tipo o su
    estado: regla 4 del molde es literalmente "lo que cuelga de ELLA".
    Se buscan sus hijos DIRECTOS -- quien la nombra en ``origin``, o
    quien la nombra en ``replaces`` -- entre las notas que comparten
    alguna de sus DOS zonas (una nota vive en dos zonas; un hijo podria
    estar solo en una de ellas, no necesariamente en las dos) -- mismo
    universo de busqueda que ``_notes_touching_zone`` ya usa para el
    informe de zona, invocado aqui para cada una de las dos zonas de la
    nota. Un hijo cuyo puntero cae fuera de ese universo (otra pareja
    de zonas por completo) queda fuera -- mismo criterio de "puntero
    roto = nota huerfana" que ``clusters.group`` ya declara para el
    informe de zona.

    Si no hay ningun hijo, ``cluster`` es ``None`` -- "el bloque entero
    no se imprime" [regla 4]. ``notes.pm_root``/``indexes.archived_ids``
    dan el unico dato que ``query`` no puede dar por si solo: si la
    propia nota, o cada hijo, esta archivado hoy.
    """
    note = query.by_id(note_id)
    if note is None:
        return None

    root = _repo_root()
    pm_root = notes.pm_root(root)
    archived_ids = indexes.archived_ids(pm_root)

    related: dict[str, Note] = {}
    for zone in {note.zone1, note.zone2}:
        for n in _notes_touching_zone(zone):
            related[n.id] = n
    related.pop(note_id, None)

    children = tuple(
        sorted(
            (
                n for n in related.values()
                if note_id in n.origin or n.replaces == note_id
            ),
            key=lambda n: n.id,
        )
    )
    cluster = None
    if children:
        cluster = Cluster(
            root=note,
            children=children,
            archived_ids=frozenset(n.id for n in children if n.id in archived_ids),
        )

    return NoteReport(
        note=note,
        generated_at=_now(),
        archived=note_id in archived_ids,
        cluster=cluster,
    )


def _archive_lines_by_id(pm_root: Path) -> dict[str, ArchiveLine]:
    """``ARCHIVED.md`` indexado por id -- fuente para saber, de una nota
    ya archivada, POR QUE lo esta (``destination``: ``replaced``/
    ``closed``/``promoted``) [D-056, vista en cadena, caso borde (a)].
    Un ``ARCHIVED.md`` que todavia no existe cuenta como "nada archivado
    con destino conocido", mismo criterio declarado que ya aplica
    ``indexes.archived_ids`` a la ausencia del fichero.
    """
    try:
        lines = indexes.read_archive(pm_root)
    except FileNotFoundError:
        return {}
    return {line.id: line for line in lines}


def _chain_is_superseded(
    note_id: str,
    archive_lines: dict[str, ArchiveLine],
    by_id: dict[str, Note],
    superseded_within_matched: frozenset[str],
) -> bool:
    """``True`` si ``note_id`` tiene una sustituta VISIBLE dentro de
    ``by_id`` (el conjunto ``matched`` de esta vista) -- solo entonces
    puede dejar de ser cabeza de su propio hilo. ``ARCHIVED.md`` manda
    cuando tiene una linea de destino ``"replaced"``: su
    ``destination_detail`` es el id real de la sustituta [ver
    ``model.ArchiveLine.destination_detail``, "el ID nuevo"], y esa
    sustituta tiene que estar en ``by_id`` para contar -- si la cabeza
    viva del linaje se re-archivo bajo OTRA pareja de zonas, la
    sustituta real no toca la zona pedida y no aparece en ``by_id``:
    en ese caso ``note_id`` NO esta sustituida DESDE ESTA VISTA, y
    tiene que quedar como cabeza de su propio hilo (con sus propias
    antecesoras colgando debajo) en vez de desaparecer entera --
    regresion de Moriarty, "--chain nunca enseña menos que --todo".
    A falta de linea en ``ARCHIVED.md`` (fichero ausente, o el id
    nunca se archivo por esta via) se cae al indicio local: algun otro
    puntero ``Replaces`` DENTRO del conjunto pedido ya lo nombra como
    su viejo -- ese indicio ya vive solo dentro de ``by_id`` por
    construccion, no hace falta comprobarlo aparte.
    """
    line = archive_lines.get(note_id)
    if line is not None:
        if line.destination != "replaced":
            return False
        return line.destination_detail in by_id
    return note_id in superseded_within_matched


def _chain_ancestors(head: Note, by_id: dict[str, Note]) -> tuple[Note, ...]:
    """Las antecesoras de ``head``, caminando hacia atras por
    ``Note.replaces`` -- la mas reciente primero [D-056, "las
    antecesoras cuelgan en orden"]. Un puntero cuyo destino no esta en
    ``by_id`` (la nota vieja no caso la palabra/zona pedida) se busca
    igual por ``query.by_id`` -- la cadena entera tiene que verse,
    nunca solo la parte que la busqueda encontro por su cuenta. Un
    ciclo mal formado (red de seguridad, sin adversario que lo
    provoque a proposito [CLAUDE.md "el sistema contra si mismo"]) para
    la marcha en vez de repetir para siempre.
    """
    ancestors: list[Note] = []
    seen = {head.id}
    cursor = head
    while cursor.replaces and cursor.replaces not in seen:
        prev = by_id.get(cursor.replaces)
        if prev is None:
            prev = query.by_id(cursor.replaces)
        if prev is None:
            break
        ancestors.append(prev)
        seen.add(prev.id)
        cursor = prev
    return tuple(ancestors)


def _chain_closure(
    note_id: str,
    is_archived: bool,
    archive_lines: dict[str, ArchiveLine],
) -> tuple[bool, str | None]:
    """Decide ``closed``/``replaced_by`` para una cabeza de hilo que ya
    paso el filtro de ``_chain_is_superseded`` -- vigente, archivada sin
    sucesora, o archivada con una sucesora real que vive FUERA de esta
    vista [regresion de Moriarty, "una cabeza sustituida nunca puede
    salir 'cerrada'"]. ``model.ChainThread.closed`` (linea 191) solo
    puede ser ``True`` en un cierre LEGITIMO sin sucesora -- eso lo
    viola de raiz una nota con ``ArchiveLine.destination == "replaced"``,
    tenga o no la sucesora visible aqui: SI tiene sucesora, luego no es
    un cierre legitimo, solo una vista que no alcanza a mostrarla.

    Nota vigente: ni cerrada ni sustituida. Nota archivada sin linea en
    ``ARCHIVED.md`` (fichero ausente, o id nunca archivado por esta via):
    se cae al mismo criterio a ciegas que ya usaba este modulo antes de
    este arreglo (``closed=True``) -- no hay fuente que distinga el
    porque, y "cerrada" sigue siendo mejor que inventar un estado sin
    evidencia. Nota archivada con linea ``"closed"``: cierre legitimo,
    ``closed=True``. Nota archivada con linea ``"replaced"``: NUNCA
    cerrada -- ``replaced_by`` es ``destination_detail``, el id real de
    la sucesora [``model.ArchiveLine.destination_detail``, "el ID
    nuevo"], visible o no en esta vista.
    """
    if not is_archived:
        return False, None
    line = archive_lines.get(note_id)
    if line is not None and line.destination == "replaced":
        return False, line.destination_detail
    return True, None


def _chain_threads(
    matched: tuple[Note, ...],
    archived_ids: frozenset[str],
    archive_lines: dict[str, ArchiveLine],
) -> tuple[ChainThread, ...]:
    """Reparte ``matched`` en hilos: una cabeza (vigente, archivada sin
    sucesor, o archivada con sucesor que vive fuera de ``matched`` --
    linaje cuya cabeza real se re-archivo bajo otra pareja de zonas)
    con sus antecesoras colgando debajo [D-056]. Una nota sustituida
    por otra del propio conjunto nunca es cabeza -- aparece como
    antecesora de quien la sustituyo, via ``_chain_ancestors``. La
    etiqueta de cierre de la cabeza (``closed``/``replaced_by``) la
    decide ``_chain_closure`` -- nunca el simple ``note.id in
    archived_ids`` de antes, que confundia "cerrada" con "sustituida
    pero invisible desde aqui" [regresion de Moriarty].
    """
    by_id = {n.id: n for n in matched}
    superseded_within_matched = frozenset(n.replaces for n in matched if n.replaces)

    threads = []
    for note in sorted(matched, key=lambda n: n.id):
        if _chain_is_superseded(note.id, archive_lines, by_id, superseded_within_matched):
            continue
        closed, replaced_by = _chain_closure(
            note.id, note.id in archived_ids, archive_lines
        )
        threads.append(
            ChainThread(
                head=note,
                closed=closed,
                ancestors=_chain_ancestors(note, by_id),
                replaced_by=replaced_by,
            )
        )
    return tuple(threads)


def build_chain(text: str) -> ChainReport:
    """La vista en cadena de ``text`` (zona o palabra, misma resolucion
    que ``build_zone``/``build_word``) -- ``search.py --chain`` [D-056,
    "el enlace de sustitucion se ve por un solo lado"]. Siempre trae el
    historial COMPLETO (vigente y archivado): a diferencia de
    ``build_zone``/``build_word``, esta vista no tiene un
    ``include_archived`` que pedir -- las antecesoras SON archivadas por
    definicion, y esconderlas sin ``--todo`` vaciaria la cadena entera.

    El enlace ``Origin`` de una incidencia hacia el muro que nacio de
    cerrarla NUNCA se pierde aqui: no es un ``Replaces``, asi que ningun
    hilo lo agrupa -- el muro aparece como su propia cabeza (vigente,
    sin antecesoras via Replaces) y `report_render_chain.py` reutiliza
    el mismo bloque de restriccion que ya imprime `Origin: <id>` [caso
    borde (b) del encargo] -- este modulo no reimplementa ese campo.
    """
    root = _repo_root()
    pm_root = notes.pm_root(root)
    archived_ids = indexes.archived_ids(pm_root)
    archive_lines = _archive_lines_by_id(pm_root)

    zones_map = zones_mod.load(_zones_json_path(pm_root))
    resolved_zone = zones_mod.resolve(text, zones_map)
    if resolved_zone is not None:
        matched = _notes_touching_zone(resolved_zone)
    else:
        matched = tuple(note for note, _matched_lines in query.by_word(text))

    return ChainReport(
        query=text,
        generated_at=_now(),
        threads=_chain_threads(matched, archived_ids, archive_lines),
    )
