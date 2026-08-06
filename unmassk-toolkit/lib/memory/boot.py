"""El menu del dia -- contrato en docs/memoria-v2/PIEZAS.md Sec.9.5.

Para que: lo primero que se ve al abrir una sesion. Si esto falla, el
trabajo del dia empieza a ciegas.

De que salida se deriva: las dos formas literales del arranque,
TEXTOS.md Sec.3.1 (proyecto con contenido) y Sec.3.2 (proyecto recien
instalado) -- "los dos bloques son la salida, no un ejemplo" -- y el
orden exacto de sus cinco bloques que fija spec Sec.8.3: el `NEXT` con
su contexto debajo, TODOS los bloqueantes con a quien esperan, TODAS las
restricciones sin tope, los recuentos, los avisos.

Que NO hace [Sec.9.5]: **solo compone y pinta**. No lee git directamente
(llama a `query`), no calcula salud (llama a `health.build()`, Sec.9.4),
no escribe nada.

**`root` sale de `notes.repo_root()`, nunca de `Path.cwd()` a secas**
[correccion 2026-08-02]: `context.latest()`/`query.by_zone()` si pueden
resolver contra el cwd del proceso sin mas, porque solo lo usan como
`cwd=` de un `git log` -- git resuelve la raiz real del repositorio solo,
desde cualquier subcarpeta. Pero `notes.pm_root(root)` (usada aqui para
`indexes.archived_ids(...)`) es **aritmetica de rutas pura, sin tirar de
git** -- compone `<root>/.claude/project-memory` tal cual, confiando en
que `root` YA es la raiz pelada del repositorio. Lanzado desde una
subcarpeta anidada con `root = Path.cwd()`, esa composicion apunta al
sitio equivocado: se demostro ejecutando (`project=root.name` mostraba el
nombre de la subcarpeta, y los indices leidos no eran los reales). El
apano vivia antes en `bin/memory/boot.py` (`os.chdir()` a la raiz antes
de llamar); se corrige aqui, en la pieza, para que cualquier llamador
futuro (el hook del arranque, que aun no existe) no tenga que acordarse
de repetirlo. `notes.repo_root()` resuelve via `git rev-parse
--show-toplevel` [notes_commit.py], igual que ya hace el resto del
sistema para la misma raiz.

Se construye con `context`, `health`, `indexes`, `notes`, `query` --
NUNCA con `report`/`zones` [encargo explicito de esta tarea]. La
consecuencia de excluir `zones` es un hueco DECLARADO, no un olvido: las
dos lineas "." de TEXTOS.md Sec.3.2 (`los ocho indices existen y estan
vacios` / `zones.json: N zonas de trabajo...`) leen `zones.json`, y sin
importar `zones` este modulo no puede producirlas. Ningun test de
`test_boot.py` las pide -- quedan fuera de esta pasada, para quien la
audite despues, mismo criterio que ya aplican `health.py`/`report.py`
para sus propios huecos declarados.

**"Vigente" se deduce con `indexes.archived_ids(notes.pm_root(root))`**
-- fuente unica desde 2026-08-02: una nota es vigente si su identificador
no aparece en `ARCHIVED.md`. Antes de esa fecha este modulo (y
`report.py`, por separado) tenian cada uno su propia copia privada del
mismo calculo; ahora los dos llaman a la misma pieza de `indexes.py`
[revision 2026-08-02, hallazgo de Argus]. Un `ARCHIVED.md` que todavia
no existe cuenta como cero archivados, nunca como un fallo -- sin este
descuento, `build()` reventaba con `FileNotFoundError` en la
primerisima sesion de cualquier proyecto, antes de que hubiera una sola
nota que mostrar [mismo hallazgo, punto 1]. Blockers y restricciones
salen de ese mismo filtro, sin tope [spec Sec.8.3: "sin tope ni
presupuesto" -- el presupuesto de renderizado del v1 ocultaba el 94-96%
de la memoria].

**Los tres recuentos sin fila propia en Sec.9.5** (`open_questions`,
`open_issues`, `open_incidents`) no tienen fuente fijada por ningun texto
citado en el encargo -- lo declara el propio `test_boot.py` en su
docstring ("de donde sale cada numero... no esta fijado... fuera de esta
pasada"). Decision tomada aqui, con los textos delante, para que
`BootSummary` no quede con un campo sin llenar [el propietario esta
fuera; instruccion explicita de la tarea: "decide con los textos
delante y anota lo que decidas"]:

- `open_questions` / `open_incidents`: cuenta de notas Q / I vigentes
  (mismo filtro de "no archivada" que restricciones y bloqueantes) --
  spec Sec.3 confirma que Q "asciende a M o cae a X" y que I "se cierra"
  [spec, tabla de tipos], y las dos salidas mueven la nota a
  `ARCHIVED.md` por el mismo mecanismo que D/M/R. Sin campo nuevo, sin
  llamada externa nueva.
- `open_issues`: cuenta de numeros de issue DISTINTOS que llevan notas
  vigentes con `Note.issue` puesto -- ese campo "solo vive en el acta de
  plan" [model.py]. Se descarta a proposito una segunda llamada a `gh`
  (el `state` real de la issue en GitHub): `health.py` ya paga una
  llamada a `gh` por boot dentro de `plans_unreflected()`
  [`_GH_TIMEOUT`, "0.85s medidos" segun spec Sec.10.4] y anadir una
  segunda, redundante, en este modulo -- que el propio Sec.9.5 dice que
  "no calcula salud" -- inflaria el arranque con una dependencia externa
  mas por una fila que ningun test pide.

  **La etiqueta que se pinta NO dice "issues abiertas"** [correccion
  2026-08-02, hallazgo de Argus]: ese texto mentia -- el numero nunca
  pregunta a GitHub, solo cuenta actas de plan LOCALES sin archivar, asi
  que puede decir "0" con una issue real todavia abierta (su acta se
  archivo por limpieza rutinaria) o seguir en "1" con la issue ya cerrada
  hace meses (su acta nunca se archivo) -- y puede contradecir, en la
  misma pantalla, la linea de `plans_unreflected` de mas abajo, que SI
  consulta `gh` de verdad. `_recuentos_block()` pinta "planes con acta
  vigente", que es lo que el numero mide de verdad.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
[PIEZAS.md Sec.3.3bis].
"""

import textwrap
from datetime import datetime, timezone

import context
import emojis
import health
import indexes
import notes
import query
import remote
import repo_guard
import timefmt
from model import BootSummary, ContextNote

_BOX_WIDTH = 72  # mismo ancho visual que report_render._BOX_WIDTH

# Literales exactos de TEXTOS.md Sec.3.2 (proyecto recien instalado),
# copiados byte a byte -- son la salida, no un ejemplo. Etiquetas
# estructurales en ingles [decision del propietario, 2026-08-03]:
# BLOQUEANTES->BLOCKERS, RESTRICCIONES->RESTRICTIONS -- el contenido
# explicativo (los porques, las descripciones) se queda en espanol.
_ZERO_BLOCKERS = "⛔ BLOCKERS ......  C E R O"
_ZERO_RESTRICTIONS = (
    "⚠️ RESTRICTIONS ....  C E R O",
    "                      No hay ningún muro puesto. Nada te va a parar",
    "                      porque nadie ha escrito todavía qué rompe qué.",
)
# "[NEXT]" literal, no "NEXT" a secas -- decision del propietario,
# 2026-08-03 (COLA.md Sec.5): el corchete es parte del titular, igual que
# en el commit de cierre (`format.build_context_message`). El indent de
# continuacion se deriva del ancho de la etiqueta, nunca un numero magico.
_NEXT_LABEL = "[NEXT] "
_NEXT_INDENT = " " * len(_NEXT_LABEL)
_NO_NEXT = (
    f"{_NEXT_LABEL}ninguno todavía. No hay ningún cierre de sesión escrito.",
    f"{_NEXT_INDENT}El primero lo escribe close-session al terminar hoy.",
)
_FIRST_NOTE_HINT = (
    "Cero no es silencio: es que todavía no se ha escrito nada. La primera",
    "nota se guarda así:",
    "",
    '  gitmem note <TIPO> --zones <zona1> <zona2> "titular en inglés" \\',
    '    --description "..." --stops <yes|no>',
)
_MAP_IS_SET = (
    "El mapa está puesto. Dime por dónde: el Next, una pregunta, una issue,",
    "o lo que traigas.",
)
# Pie del arranque cuando `health.memory_mounted` dice que falta algo --
# anadido 2026-08-06 [Aviso B, fallo 2 real: el pie de siempre
# (`_FIRST_NOTE_HINT`) invitaba a `--zones <zona1> <zona2>` con dos
# zonas inventadas, el primer comando garantizado a fallar cuando
# `zones.json` no tiene ninguna zona todavia -- `validator.validate_zones`
# rechaza cualquier nombre que no exista ya]. Ensena el orden real: las
# zonas se dan de alta ANTES de que exista una nota que pueda llevarlas.
_SETUP_MISSING_HINT = (
    "La memoria de este proyecto todavía no está montada del todo -- antes",
    "de guardar una nota hace falta dar de alta al menos una zona:",
    "",
    '  gitmem zones add <nombre> --description "..."',
    "",
    "Con al menos una zona dada de alta, la primera nota se guarda así:",
    "",
    '  gitmem note <TIPO> --zones <zona1> <zona2> "titular en inglés" \\',
    '    --description "..." --stops <yes|no>',
)


def build() -> BootSummary:
    """El estado real del proyecto, listo para `render()`. Lee TODO el
    historial una sola vez (`query.by_zone(None, None)`, los dos ejes en
    `None` no filtran nada) y deriva de ahi restricciones, bloqueantes y
    los tres recuentos -- ver el docstring del modulo para el porque de
    cada decision. `health.build()` compone el informe de salud aparte;
    este modulo nunca recalcula lo que ya calculo `health`.
    """
    root = notes.repo_root()
    # Lo primero de todo, antes de leer una sola nota: traerse lo que
    # haya hecho otra maquina. Sin esto el arranque lee el ultimo cierre
    # de ESTA copia y lo presenta como el estado del proyecto, sin que
    # nada delate que el trabajo de verdad esta en otra rama y en otro
    # sitio [decision del propietario, 2026-08-05].
    # Un repositorio recien creado, sin un solo commit, no tiene rama que
    # leer todavia -- y ese es el primer arranque de cualquier proyecto,
    # el caso mas comun que existe. Se sigue sin ella, nunca se revienta
    # [mismo criterio que `context.latest()` ya aplica a la rama sin
    # commits].
    try:
        branch = repo_guard.current_branch(root)
    except RuntimeError:
        branch = None
    remote_state = remote.state(root, branch)
    archived_ids = indexes.archived_ids(notes.pm_root(root))
    live_notes = tuple(
        note for note in query.by_zone(None, None) if note.id not in archived_ids
    )

    restrictions = tuple(
        sorted((n for n in live_notes if n.type == "R"), key=lambda n: n.id)
    )
    blockers = tuple(
        sorted((n for n in live_notes if n.type == "B"), key=lambda n: n.id)
    )
    questions = tuple(sorted((n for n in live_notes if n.type == "Q"), key=lambda n: n.id))
    incidents = tuple(sorted((n for n in live_notes if n.type == "I"), key=lambda n: n.id))
    open_questions = len(questions)
    open_incidents = len(incidents)
    open_issues = len({n.issue for n in live_notes if n.issue is not None})

    return BootSummary(
        project=root.name,
        generated_at=datetime.now(timezone.utc),
        remote=remote_state,
        # Un remoto ajeno no puede aportar el Next: ver context.latest().
        context=context.latest(all_refs=not remote_state.unrelated_remote),
        blockers=blockers,
        restrictions=restrictions,
        open_questions=open_questions,
        open_issues=open_issues,
        open_incidents=open_incidents,
        questions=questions,
        incidents=incidents,
        health=health.build(),
    )


def _box_border(left_corner: str, right_corner: str) -> str:
    return f"{left_corner}{'═' * (_BOX_WIDTH - 2)}{right_corner}"


def _box_content_line(left: str, right: str) -> str:
    inner = _BOX_WIDTH - 2
    gap = inner - len(left) - len(right)
    if gap < 1:
        gap = 1
    return f"║{left}{' ' * gap}{right}║"


# Ancho del texto plegado: el de la caja menos la sangria del Next.
_PROSE_WIDTH = _BOX_WIDTH - len(_NEXT_INDENT) - 2


def _remote_block(state) -> list[str]:
    """Donde se dejo el trabajo y donde estas tu, desglosado bajo la caja.

    Fuera de la cabecera a proposito [decision del propietario,
    2026-08-05: "en el banner que aparezca el proyecto y la hora, y lo
    demas desglosado debajo"]: dentro iba apretado y el nombre de una
    rama larga se comia la linea entera.

    Va antes del Next porque cambia lo que hay que hacer: enterarse de
    que lo ultimo se hizo en otra rama, en otra maquina, DESPUES de leer
    el resto es enterarse tarde.
    """
    if state is None:
        return []

    lines = ["🌿 BRANCH"]

    if not state.fetched:
        lines.append("   ⚠️  fetch failed — everything below may be stale")
        if state.fetch_error:
            lines.append(f"      {state.fetch_error}")

    if state.latest is not None:
        where = remote._bare(state.latest.branch)
        lines.append(
            f"   Last worked on: {where} · {timefmt.ago(state.latest.when)}"
        )
    if state.current_branch:
        lines.append(f"   You are on: {state.current_branch}")

    if state.elsewhere:
        lines.append("")
        lines.append(
            "   ⚠️  the last work is NOT on your branch — it was left somewhere"
        )
        lines.append("      else, probably on another machine.")

    if state.unrelated_remote:
        lines.append("")
        lines.append(
            "   ⚠️  origin shares NO history with this repository — it points"
        )
        lines.append(
            "      at another project. Ahead/behind counts are meaningless"
        )
        lines.append("      here and are not shown. Do not pull.")

    if state.upstream_gone:
        lines.append(
            "   ⚠️  its remote branch no longer exists — merged and deleted"
        )

    if state.behind:
        lines.append(
            f"   ⚠️  behind origin by {state.behind} commit(s), already fetched"
        )
    if state.ahead:
        lines.append(f"   ⚠️  {state.ahead} commit(s) not pushed")

    return lines


def _looks_like_a_commit_line(line: str) -> bool:
    """Una linea de la lista que el cierre deja bajo el contexto: empieza
    por el corchete del tipo (`[D-030]...`), por el del checkpoint
    (`[WIP]`) o por un guion de lista."""
    stripped = line.lstrip()
    return stripped.startswith(("[", "- ", "* "))


def _next_block(ctx: ContextNote | None) -> list[str]:
    if ctx is None:
        return list(_NO_NEXT)
    lines = [
        f"{_NEXT_LABEL}{emojis.CHANNEL_EMOJI['next']} {ctx.headline}",
        f"{_NEXT_INDENT}Context (cerrado {timefmt.utc_label(ctx.timestamp)}):",
    ]
    # Prosa corrida, no una lista de puntos [decision del propietario,
    # 2026-08-03]. Se pliega al ancho de la caja: son unas cincuenta
    # lineas de texto y sin plegar salen como un parrafo unico que se
    # desborda por la derecha -- ilegible justo en lo que mas importa
    # leer del arranque.
    #
    # La lista de commits que el cierre deja al final del cuerpo NO se
    # pliega: cada linea es un titular con su tipo y sus zonas delante, y
    # partirla por la mitad rompe la unica columna que la hace ojeable.
    for paragraph in ctx.context.split("\n"):
        if not paragraph.strip():
            lines.append("")
        elif _looks_like_a_commit_line(paragraph):
            lines.append(f"{_NEXT_INDENT}{paragraph.rstrip()}")
        else:
            lines.extend(
                f"{_NEXT_INDENT}{chunk}"
                for chunk in textwrap.wrap(paragraph, width=_PROSE_WIDTH)
            )
    return lines


def _blockers_section(blockers) -> list[str]:
    """Privada -- 2026-08-04 [correccion, decision del orquestador,
    revocable]: era publica solo para que `vocabulary.FIELDS["awaits"]`
    tuviera un simbolo con ese nombre que encontrar por reflexion; a
    esta funcion, fuera de este fichero, no la llamaba nadie -- el mismo
    patron de "lector de mentira" que `report_render.render` (ver su
    docstring, ya borrado con la funcion). El lector real y publico de
    `awaits`, el que de verdad se invoca desde fuera del modulo y llega
    al campo, es `render()` mas abajo: `vocabulary.FIELDS["awaits"].reader`
    ahora declara `"boot.render"`.
    """
    if not blockers:
        return [_ZERO_BLOCKERS]
    lines = [f"⛔ BLOCKERS ({len(blockers)})", ""]
    for note in blockers:
        lines.append(f"   {note.id}  [{note.zone1}][{note.zone2}]   {note.headline}")
        if note.awaits:
            lines.append(f"          awaits: {note.awaits}")
    return lines


def _restrictions_block(restrictions) -> list[str]:
    if not restrictions:
        return list(_ZERO_RESTRICTIONS)
    lines = [f"⚠️ RESTRICTIONS ({len(restrictions)})", ""]
    for note in restrictions:
        lines.append(f"   {note.id}  [{note.zone1}][{note.zone2}]     {note.headline}")
        if note.why:
            lines.append(f"          {note.why}")
    return lines


def _recuentos_block(summary: BootSummary) -> list[str]:
    # "plans with a record", no "issues abiertas" [correccion 2026-08-02,
    # hallazgo de Argus]: ver el docstring del modulo, parrafo de
    # `open_issues`, para el porque -- este numero nunca pregunta a
    # GitHub, y la etiqueta vieja mentia sobre lo que mide de verdad.
    # Etiquetas estructurales en ingles [decision del propietario,
    # 2026-08-03]: RECUENTOS->COUNTS, el resto de cada fila igual.
    lines = [
        "COUNTS",
        f"   plans with a record .  {summary.open_issues}",
    ]
    # Una pregunta sin resolver y una incidencia abierta salen POR SU
    # NOMBRE, nunca como una cifra: un "3" no dice cual de las tres te
    # para hoy, y esa era justamente la queja -- "con seis preguntas
    # abiertas yo no me entero de nada". Las cuentas de arriba siguen
    # para lo que si es un numero.
    lines.extend(_named_block("❓ OPEN QUESTIONS", summary.questions))
    lines.extend(_named_block("🔥 OPEN INCIDENTS", summary.incidents))
    return lines


def _named_block(title: str, notes_seen) -> list[str]:
    if not notes_seen:
        return ["", f"{title} ....  C E R O"]
    lines = ["", f"{title} ({len(notes_seen)})", ""]
    for note in notes_seen:
        lines.append(f"   {note.id}  [{note.zone1}][{note.zone2}]   {note.headline}")
        if note.description:
            first = note.description.split("\n")[0]
            lines.extend(
                f"          {chunk}" for chunk in textwrap.wrap(first, width=_PROSE_WIDTH)
            )
    return lines


def _avisos_block(summary: BootSummary) -> list[str]:
    """Los ✓ importan tanto como los ⚠️ [health.py, docstring]: se
    imprime siempre el numero real, gane o pierda la comparacion, nunca
    el silencio de una linea ausente.

    Tres anadidos 2026-08-02 (hallazgos de Argus): (1) si `gh` fallo,
    `plans_unreflected_error` lo dice en esta misma seccion en vez de
    tumbar el arranque entero -- nunca un cero inventado en su lugar
    [punto 2]; (2) cada discrepancia de indice nombra la nota que
    diverge, no solo los dos numeros [punto 4]; (3) las reglas [`health.
    coherence_rules`] se pintan junto a los otros dos chequeos, tambien
    cuando estan bien [punto 3, "el vigilante mudo"].

    **Ronda 2 (hallazgo 1 de Moriarty) -- el visto bueno que mentia:**
    los ✓/⚠️ ya no comparan `lineas == notas`/`lineas == commits` (dos
    numeros que pueden coincidir aunque el CONTENIDO diverja, demostrado
    ejecutando) -- dependen de que la lista de discrepancias este vacia,
    y las de reglas se imprimen linea a linea, igual que las de indice.

    Etiquetas estructurales en ingles [decision del propietario,
    2026-08-03]: AVISOS->CHECKS, "IDs sin duplicados"->"no duplicate IDs"
    (y su contraparte "duplicate IDs"), "indices coherentes con
    git"->"indexes match git" (contraparte "indexes do not match git"),
    "reglas coherentes con git"->"rules match git" (contraparte "rules do
    not match git"). El contenido explicativo (el motivo real de cada
    aviso) se queda en espanol.

    **Desglose con archivadas, 2026-08-03** [TEXTOS.md Sec.5, decision del
    propietario]: "N lineas / M notas" no explicaba por que M > N cuando
    hay notas archivadas -- ahora, si `report.archived_notes` es cero se
    pinta igual que siempre; si no, se desglosa "K live + J archived / M
    notas" con `report.index_lines` como K (las lineas vigentes, que
    coinciden con las notas vivas cuando todo es coherente) y
    `report.archived_notes` como J.

    `bench.py` se retira entero, 2026-08-03 [decision del propietario:
    "no lo he autorizado en la vida"] -- esta seccion ya no pinta ningun
    veredicto de banco adversarial.

    **Dos avisos mas, anadidos 2026-08-06 [Aviso A/B, fallos 1 y 2
    reales, ver `health.possible_unconverted_legacy`/`health.memory_mounted`]
    -- y los DOS, a proposito, rompen la regla de arriba de "los ✓
    importan tanto como los ⚠️": solo hablan cuando hay algo real que
    avisar, se callan del todo en un proyecto sano [encargo explicito:
    "los dos avisos nuevos tienen que callarse"]. No son un chequeo de
    coherencia como los tres de arriba (una comparacion que siempre tiene
    un resultado, gane o pierda) -- son una senal de sospecha (Aviso A) y
    un requisito de arranque (Aviso B), y un requisito cumplido no es
    noticia.
    """
    report = summary.health
    lines = ["CHECKS"]

    if report.legacy_commits_suspected is not None:
        lines.append(
            f"   ⚠️  {report.legacy_commits_suspected} commits en el historial, "
            f"0 notas reconocidas -- puede ser memoria del sistema anterior "
            "sin destilar"
        )

    if report.memory_setup_missing:
        lines.append("   ⚠️  la memoria de este proyecto no está montada:")
        for text in report.memory_setup_missing:
            lines.append(f"      - {text}")

    if report.plans_unreflected_error is not None:
        lines.append(
            "   ⚠️  no se pudo comprobar si hay planes sin reflejar: "
            f"{report.plans_unreflected_error}"
        )
    else:
        for issue_number, unreflected in report.plans_unreflected:
            plural = "" if unreflected == 1 else "s"
            lines.append(
                f"   ⚠️  plan #{issue_number}: {unreflected} commit{plural} sin "
                "reflejar en la issue"
            )

    if report.duplicate_ids:
        lines.append(f"   ⚠️  duplicate IDs: {', '.join(report.duplicate_ids)}")
    else:
        lines.append(f"   ✓  no duplicate IDs ({report.git_notes} notes)")

    if report.archived_notes:
        numbers = (
            f"{report.index_lines} live + {report.archived_notes} archived / "
            f"{report.git_notes} notes"
        )
    else:
        numbers = f"{report.index_lines} lines / {report.git_notes} notes"
    if not report.index_discrepancies:
        lines.append(f"   ✓  indexes match git ({numbers})")
    else:
        lines.append(f"   ⚠️  indexes do not match git ({numbers})")
    for text in report.index_discrepancies:
        lines.append(f"      - {text}")

    rule_numbers = f"{report.rule_lines} lines / {report.rule_commits} commits"
    if not report.rule_discrepancies:
        lines.append(f"   ✓  rules match git ({rule_numbers})")
    else:
        lines.append(f"   ⚠️  rules do not match git ({rule_numbers})")
    for text in report.rule_discrepancies:
        lines.append(f"      - {text}")

    return lines


def render(summary: BootSummary) -> str:
    """El texto completo del arranque -- orden fijo de cinco bloques
    [spec Sec.8.3], mas la cabecera y el cierre. Nunca recorta nada:
    restricciones y bloqueantes salen enteros, sin tope.
    """
    lines: list[str] = []
    lines.append(_box_border("╔", "╗"))
    lines.append(
        _box_content_line(
            f"  MEMORY · {summary.project}", f"{timefmt.utc_label(summary.generated_at)} "
        )
    )
    lines.append(_box_border("╚", "╝"))
    lines.append("")

    remote_block = _remote_block(summary.remote)
    if remote_block:
        lines.extend(remote_block)
        lines.append("")

    lines.extend(_next_block(summary.context))
    lines.append("")
    lines.extend(_blockers_section(summary.blockers))
    lines.append("")
    lines.extend(_restrictions_block(summary.restrictions))
    lines.append("")
    lines.extend(_recuentos_block(summary))
    lines.append("")
    lines.extend(_avisos_block(summary))
    lines.append("")

    if summary.health.memory_setup_missing:
        lines.extend(_SETUP_MISSING_HINT)
    elif summary.health.git_notes == 0:
        lines.extend(_FIRST_NOTE_HINT)
    else:
        lines.extend(_MAP_IS_SET)

    return "\n".join(lines)
