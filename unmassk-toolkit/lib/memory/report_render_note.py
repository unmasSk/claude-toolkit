"""Convertir el informe de una nota por su identificador en texto --
molde en docs/memoria-v2/TEXTOS.md Sec.2.4 (dictado por el propietario,
2026-08-03), cierra DEUDA.md #24.

Fichero APARTE de `report_render.py` -- no una funcion mas alli -- por
el mismo techo de 500 lineas que ya partio `format.py`/`format_lines.py`
y `validator.py`/`validator_zones.py` [DEUDA.md puntos 12/14]. Reutiliza
las piezas ya publicas de `report_render.py` (`DIVIDER`/`THIN_DIVIDER`/
`header_line`/`utc_label`) en vez de duplicarlas -- mismo principio que
`vocabulary.TYPE_INDEX_FILES` se hizo publica para reuso entre hermanos.

`report.build_note()` ya resuelve QUE se enseña (la nota, su estado, y
sus hijos directos por puntero) -- este modulo solo lo pinta. No lee de
git ni de `zones.json`/`ARCHIVED.md` por su cuenta, ni decide nada que
`NoteReport` no traiga ya construido [mismo "Que NO hace" que
`report_render.py`, Sec.9.2].

Las cinco reglas del molde [TEXTOS Sec.2.4], una funcion o bloque por
regla:

1. La cabecera es la NOTA (id + tipo en castellano + estado), no la
   zona -- `render_note`, primeras tres lineas.
2. Todos los campos del commit, con su nombre y alineados; uno vacio no
   se imprime -- `_note_fields`. `Origin`/`Replaces` quedan FUERA a
   proposito: el propio molde los reserva para el racimo (regla 4),
   nunca los lista como campo de la nota.
3. Las dos zonas juntas, con la fecha REAL de escritura de la nota (no
   la hora del informe, que va en la cabecera) -- `render_note`, linea
   de zonas.
4. El racimo por punteros Origin/Replaces debajo; sin nada que cuelgue,
   el bloque entero no se imprime -- `_cluster_lines`.
5. El pie ofrece la zona, nunca `--todo` -- `render_note`, ultima linea.

DESVIACION declarada, mismo motivo que las cinco ya declaradas en
`report_render.py`: el texto de `Why`/`Description` no se envuelve en
varias lineas como en el ejemplo de TEXTOS -- tiene que sobrevivir
ENTERO y contiguo en el render (round-trip real, sin fabricar el texto
esperado -- unmassk-standards Sec.34), y envolver lo partiria en trozos
con su propia sangria.

`awaits:`/`Issue:` (los campos que solo llevan B/M) NO se alinean en la
misma columna que Why/Description/Keys -- llevan un unico espacio tras
los dos puntos (`"awaits: the user"`, `"Issue: #47"`, el mismo formato
que ya escribe `format.py::_body_field_line` para el campo real del
commit), a diferencia de Why/Description/Keys, que SI comparten columna
[TEXTOS Sec.2.4, regla 2, "alineados"]. El contrato en rojo original de
esta tarea (`test_search_script.py::TestByIdRule2...
test_an_absent_field_prints_no_label_at_all`) fijaba el texto
`"espera: the user"`, en castellano -- pasa a `"awaits: the user"`
[decision del propietario, DEUDA.md B19 punto 4, 2026-08-03:
"`awaits:` en todas partes", sin excepcion para este informe]; sigue
con un solo espacio, no una columna calculada.

Quien lo llama. `bin/memory/search.py`.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
[PIEZAS.md Sec.3.3bis].
"""

from emojis import TYPE_EMOJI
from model import Note, NoteReport
from report_render import DIVIDER, THIN_DIVIDER, header_line, utc_label
from vocabulary import TYPE_SPANISH_NAME

_FIELD_GAP = 2  # espacio minimo entre la etiqueta mas larga y el valor
_BODY_INDENT = "    "  # 4 espacios -- mismo indentado que TEXTOS Sec.2.4


def _note_fields(note: Note) -> list[str]:
    """Los campos del commit con su nombre -- regla 2. `Why`/
    `Description`/`Keys` comparten UNA columna de valor (alineados); un
    campo ausente (`None`, tupla vacia) no genera ninguna linea: "no se
    enseñan etiquetas huerfanas" [TEXTOS Sec.2.4]. `awaits:`/`Issue:`
    (B/M) van aparte, con el formato literal de un espacio -- ver
    desviacion en el docstring del modulo.
    """
    aligned: list[tuple[str, str]] = []
    if note.why:
        aligned.append(("Why", note.why))
    aligned.append(("Description", note.description))
    if note.keys:
        aligned.append(("Keys", ", ".join(note.keys)))

    width = max(len(label) for label, _ in aligned) + _FIELD_GAP
    lines = [
        f"{_BODY_INDENT}{label}{' ' * (width - len(label))}{value}"
        for label, value in aligned
    ]

    # `awaits:` en ingles, sin excepcion [DEUDA.md B19 punto 4] -- antes
    # de esta decision el molde de TEXTOS Sec.2.4 fijaba `espera:` aqui,
    # en castellano, distinto del arranque.
    if note.type == "B" and note.awaits:
        lines.append(f"{_BODY_INDENT}awaits: {note.awaits}")
    if note.type == "M" and note.issue is not None:
        lines.append(f"{_BODY_INDENT}Issue: #{note.issue}")
    return lines


def _child_status(child: Note, archived_ids: frozenset) -> str:
    """descartada/archivada/vigente -- mismo criterio que
    ``report_render._cluster_block`` ya aplica para el racimo del
    informe de zona (X es siempre descarte permanente, el resto se lee
    contra ``archived_ids``)."""
    if child.type == "X":
        return "descartada"
    if child.id in archived_ids:
        return "archivada"
    return "vigente"


def _cluster_lines(report: NoteReport) -> list[str]:
    """El bloque "LO QUE CUELGA DE ELLA" -- regla 4. Ni el titulo se
    imprime si ``report.cluster`` es ``None``: "un titular vacio es
    ruido" [TEXTOS Sec.2.4].

    El pie de cada hijo dice literalmente "nace de {id de la nota
    pedida}" -- el texto exacto del molde -- para las TRES formas de
    puntero que ``report.build_note`` ya resolvio como hijo directo
    (Origin hacia la nota pedida, o Replaces hacia ella); no distingue
    cual de las dos fue, porque el molde tampoco lo hace.
    """
    if report.cluster is None:
        return []
    root_id = report.note.id
    lines = ["", THIN_DIVIDER, "  LO QUE CUELGA DE ELLA", ""]
    for child in report.cluster.children:
        status = _child_status(child, report.cluster.archived_ids)
        lines.append(
            f"  {TYPE_EMOJI[child.type]} {child.id}  {child.headline}  "
            f"{status} · nace de {root_id}"
        )
    return lines


def render_note(report: NoteReport) -> str:
    """El informe de una nota por su identificador -- las cinco reglas
    de TEXTOS.md Sec.2.4, en orden."""
    note = report.note
    status = "archivada" if report.archived else "vigente"

    lines = [
        DIVIDER,
        header_line(
            f"  {note.id} · {TYPE_SPANISH_NAME[note.type]} · {status}",
            utc_label(report.generated_at),
        ),
        DIVIDER,
        "",
        f"{TYPE_EMOJI[note.type]}  {note.headline}",
        header_line(
            f"{_BODY_INDENT}[{note.zone1}] [{note.zone2}]",
            f"escrita {note.timestamp:%Y-%m-%d}",
        ),
        "",
    ]
    lines.extend(_note_fields(note))
    lines.extend(_cluster_lines(report))
    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(f"  La zona entera:   gitmem search {note.zone1}")
    return "\n".join(lines)
