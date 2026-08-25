"""Convertir el informe de cadena en texto -- flag `--chain` de
`bin/memory/search.py`, D-056 (memory legibility and integrity batch,
"el enlace de sustitucion se ve por un solo lado").

Fichero APARTE de `report_render.py` -- no una funcion mas alli -- mismo
techo de 500 lineas que ya partio `report_render_note.py`/
`report_render_blocks.py` [DEUDA.md puntos 12/14]. `report.build_chain()`
ya resolvio QUE se enseña (que notas son cabeza de su hilo, cuales
cuelgan debajo, cual es un cierre sin sucesor) -- este modulo solo lo
pinta, y solo con piezas YA existentes:

- `report_render_blocks.BLOCK_BY_TYPE` -- el MISMO bloque por tipo que
  ya usan `render_zone`/`render_word`, nunca un formato nuevo. Es lo que
  garantiza que el `Origin: <id>` de una restriccion (el enlace
  incidencia->restriccion, caso borde (b) del encargo) no se pierda al
  pintar la cadena: `restriction_block` ya lo imprime, y este modulo no
  reimplementa su propio bloque de restriccion.
- `report_render.DIVIDER`/`THIN_DIVIDER`/`header_line`/`utc_label`/
  `NO_MARK` -- las mismas piezas de caja que ya reutiliza
  `report_render_note.py`.

CONTRATO ELEGIDO AQUI para el texto (Dante, pase de test-first, sin
version previa en ningun documento):

- Antecesora tachada: envuelta en `~~...~~` (unico vocabulario de
  tachado, markdown, sin glifo nuevo). Se tacha SOLO la primera linea
  del bloque (id+titular) -- las lineas de detalle que cuelgan debajo
  (Why/Origin/Issue) se quedan sin tachar, legibles.
- Cierre sin sucesora: la palabra literal `cerrada`, pegada al final de
  la primera linea del bloque de la cabeza -- mismo vocabulario que
  `format_lines.py::_ARCHIVE_DESTINATIONS` ya usa para ese destino
  (`"closed"`).
- Sustituida cuya sucesora vive fuera de esta vista (otra pareja de
  zonas): `model.ChainThread.replaced_by` trae el id real de la
  sucesora [`report.py::_chain_closure`] -- pegado a la misma primera
  linea con el literal `sustituida por <id>`, NUNCA `cerrada`
  [regresion de Moriarty, `model.ChainThread.closed`, "True = cierre
  legitimo sin sucesora"]: una cabeza con sucesora real no es un cierre,
  es una vista que no alcanza a mostrarla.
- La cabeza NO pasa `archived=True` a su bloque (evitaria el literal
  `archivada` de D-056/`report_render_blocks.py`, que es la marca de
  LISTADO, no la de cierre de cadena): el propio `cerrada`/`sustituida
  por` de aqui ya dice que esta archivada, con la palabra que este
  contrato fija para cada contexto.

Quien lo llama. `bin/memory/search.py`, rama `--chain`.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos, en un solo
sentido -- este fichero no importa nada de `report_render_word.py` ni al
reves, y ninguno de los dos importa de aqui [PIEZAS.md Sec.3.3bis].
"""

from model import ChainReport, ChainThread, Note
from report_render import DIVIDER, NO_MARK, THIN_DIVIDER, header_line, utc_label
from report_render_blocks import BLOCK_BY_TYPE

_STRIKE = "~~"


def _note_block(note: Note, closed: bool, replaced_by: str | None = None) -> list[str]:
    """El bloque de ``note``, con su tipo real (nunca reimplementado
    aqui). Si ``closed``, el literal `cerrada` pegado a su primera
    linea. Si no, y ``replaced_by`` trae un id (sustituida pero su
    sucesora vive fuera de esta vista, ``report.py::_chain_closure``),
    el literal `sustituida por <id>` en su lugar -- nunca los dos a la
    vez [contrato del modulo, `model.ChainThread.closed`/
    `.replaced_by`]. ``archived=False`` siempre en la llamada al bloque
    -- ver el porque en el docstring del modulo."""
    block_fn = BLOCK_BY_TYPE[note.type]
    lines = list(block_fn(note, NO_MARK, False))
    if closed:
        lines[0] = f"{lines[0]}  cerrada"
    elif replaced_by is not None:
        lines[0] = f"{lines[0]}  sustituida por {replaced_by}"
    return lines


def _render_thread(thread: ChainThread) -> list[str]:
    """La cabeza mas sus antecesoras, la mas reciente primero -- orden
    que ``report.build_chain`` ya fijo, este modulo no reordena nada."""
    lines = _note_block(thread.head, closed=thread.closed, replaced_by=thread.replaced_by)
    for ancestor in thread.ancestors:
        ancestor_lines = _note_block(ancestor, closed=False)
        ancestor_lines[0] = f"{_STRIKE}{ancestor_lines[0]}{_STRIKE}"
        lines.extend(ancestor_lines)
    return lines


def render_chain(report: ChainReport) -> str:
    """La vista en cadena entera -- una cabeza por hilo, sus antecesoras
    tachadas debajo [D-056]."""
    lines = [DIVIDER]
    lines.append(
        header_line(
            f"  CADENA «{report.query}» · {len(report.threads)} hilos",
            utc_label(report.generated_at),
        )
    )
    lines.append(DIVIDER)

    if not report.threads:
        lines.append("")
        lines.append("  Ninguna nota de esta zona o palabra tiene cadena que mostrar.")
        lines.append(DIVIDER)
        return "\n".join(lines)

    for thread in report.threads:
        lines.append("")
        lines.extend(_render_thread(thread))

    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(f"  Vista normal, sin cadena:   gitmem search «{report.query}»")
    return "\n".join(lines)
