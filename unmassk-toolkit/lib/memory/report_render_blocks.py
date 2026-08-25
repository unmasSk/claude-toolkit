"""El bloque de una nota suelta (una linea con id+titular, mas sus
campos) para cada uno de los siete tipos -- partido fuera de
`report_render.py` por el mismo techo de 500 lineas que ya partio
`report_render_note.py` [DEUDA.md puntos 12/14], esta vez al anadir las
dos marcas de D-056 (memory legibility batch: `archivada`/`(↺ old_id)`,
ver `_status_suffix`) mas el flag `--chain`.

Fichero APARTE, no una funcion mas en `report_render.py` -- reusado por
DOS hermanos, no uno: `report_render.py` lo usa para pintar el informe
de zona y la busqueda por palabra (`render_zone`/`render_word`, via
`_section`); `report_render_chain.py` (vista `--chain`, D-056) lo usa
para pintar cada nota de una cadena con el MISMO bloque de su tipo --
nunca reimplementa el formato, para que el `Origin:` de una restriccion
no se pierda en la vista en cadena [caso borde (b) del encargo]. Import
en un solo sentido -- este fichero no importa nada de `report_render.py`
ni de `report_render_chain.py` -- para que no haya ciclo [mismo
principio que `zones.py`/`zones_query.py`, PIEZAS.md Sec.3.3bis].

Que NO hace: no decide que notas se pintan ni en que orden -- eso es
`report.py` (que) y `report_render.py`/`report_render_chain.py` (donde).
Solo sabe convertir UNA nota, ya con su marcador y su estado archivado
resueltos por quien llama, en sus lineas de texto.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
[PIEZAS.md Sec.3.3bis].
"""

from model import Note


def _status_suffix(note: Note, archived: bool) -> str:
    """Lo que cuelga, pegado, al final de la PROPIA linea de bloque de
    una nota en un listado -- nunca en una linea aparte, para que
    ``_own_block_line`` (el ancla de los tests) lo vea sin ambiguedad
    [D-056, memory legibility batch]:

    - ``archivada``, si ``archived`` es ``True`` -- mismo vocabulario
      que YA usa el sistema para el mismo estado en otros dos sitios
      (cabecera de ``--id``, ``report_render_note.py``; hijo de racimo,
      ``report_render._cluster_block``), nunca un glifo nuevo.
    - ``(↺ {old_id})``, si ``note.replaces`` esta puesto -- la flecha de
      vuelta hacia la nota que sustituyo, visible SIN ``--todo`` (la
      nota nueva es vigente y ya aparece por defecto).

    Una nota sin ninguno de los dos no lleva sufijo -- cadena vacia,
    para que el resto de bloques (sin archivados ni sustituciones)
    salgan byte a byte igual que antes de este cambio.
    """
    parts: list[str] = []
    if archived:
        parts.append("archivada")
    if note.replaces:
        parts.append(f"(↺ {note.replaces})")
    if not parts:
        return ""
    return "  " + "  ".join(parts)


def restriction_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [
        f"{marker}{note.id}  [{note.zone1}][{note.zone2}]  {note.headline}"
        f"{_status_suffix(note, archived)}"
    ]
    if note.why:
        lines.append(f"         Why: {note.why}")
    if note.origin:
        lines.append(f"         Origin: {', '.join(note.origin)}")
    if note.keys:
        lines.append(f"         Keys: {', '.join(note.keys)}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def blocker_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [
        f"{marker}{note.id}  [{note.zone1}][{note.zone2}]  {note.headline}"
        f"{_status_suffix(note, archived)}"
    ]
    if note.awaits:
        lines.append(f"         awaits: {note.awaits}")
    lines.append(f"         Description: {note.description}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def decision_block(note: Note, marker: str, archived: bool) -> list[str]:
    """Nota D/X suelta, sin racimo -- usada solo por ``render_word``, que
    recibe ``WordChunk.notes`` en bruto y no un ``Cluster`` (ver
    desviacion 3 del docstring de ``report_render.py``)."""
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.why:
        lines.append(f"         Why: {note.why}")
    if note.origin:
        lines.append(f"         Origin: {', '.join(note.origin)}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def memo_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def incident_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def question_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.description:
        lines.append(f"         {note.description}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


# Mapa tipo -> bloque, publico para que quien pinta (`report_render.py`,
# `report_render_chain.py`) elija el bloque correcto sin un `if/elif`
# repetido en cada uno. X comparte bloque con D: `clusters.group`/
# `report.py::_DECISION_TYPES` ya tratan D/X como el mismo tipo de nota
# suelta.
BLOCK_BY_TYPE = {
    "R": restriction_block,
    "B": blocker_block,
    "D": decision_block,
    "X": decision_block,
    "M": memo_block,
    "I": incident_block,
    "Q": question_block,
}
