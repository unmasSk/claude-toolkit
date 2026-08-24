"""El menu del dia. Lo primero que se ve al abrir una sesion -- si esto
falla, el trabajo del dia empieza a ciegas.

Orden exacto de los cinco bloques: el NEXT con su contexto debajo, TODOS
los bloqueantes con a quien esperan, TODAS las restricciones sin tope,
los recuentos, los avisos (CHECKS).

Que NO hace: **solo compone y pinta**. No lee git directamente (llama a
`query`), no calcula salud (llama a `health.build()`), no escribe nada.

`root` sale de `notes.repo_root()`, nunca de `Path.cwd()` a secas:
`notes.pm_root(root)` es aritmetica de rutas pura sobre `root`, y si el
proceso arrancara desde una subcarpeta anidada esa composicion apuntaria
al sitio equivocado.

Se construye con `context`, `health`, `indexes`, `notes`, `query` --
nunca con `report`/`zones` (hueco declarado: las dos lineas de
TEXTOS.md Sec.3.2 que leen `zones.json` quedan fuera).

"Vigente" se deduce con `indexes.archived_ids(notes.pm_root(root))` --
una nota es vigente si su id no aparece en `ARCHIVED.md`. Un
`ARCHIVED.md` ausente cuenta como cero archivados, nunca como un fallo.
Blockers y restricciones salen de ese mismo filtro, sin tope.

Los tres recuentos sin fuente fijada en el contrato (`open_questions`,
`open_issues`, `open_incidents`):

- `open_questions`/`open_incidents`: cuenta de notas Q/I vigentes (Q
  asciende a M o cae a X, I se cierra -- las dos mueven la nota a
  ARCHIVED.md por el mismo mecanismo que D/M/R).
- `open_issues`: cuenta de numeros de issue DISTINTOS que llevan notas
  vigentes con `Note.issue` puesto (el campo es opcional en los siete
  tipos, no solo en el acta de plan). Se descarta a proposito una
  segunda llamada a `gh` -- `health.py` ya paga una por boot dentro de
  `plans_unreflected()`, y este modulo no calcula salud.

  La etiqueta que se pinta dice "issues with a live note", nunca "issues
  abiertas": el numero nunca pregunta a GitHub, solo cuenta notas
  locales sin archivar, y puede contradecir la linea de
  `plans_unreflected` (que SI consulta `gh`) en la misma pantalla.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca estandar
de Python. Import plano entre hermanos.
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
    # haya hecho otra maquina, para no presentar el ultimo cierre de
    # ESTA copia como si fuera el estado del proyecto. Un repositorio sin
    # un solo commit no tiene rama que leer todavia -- se sigue sin ella.
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
    """Privada: el lector real y publico de `awaits` es `render()` mas
    abajo (`vocabulary.FIELDS["awaits"].reader` declara `"boot.render"`).
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
    # "issues with a live note", no "issues abiertas" [correccion
    # 2026-08-02, hallazgo de Argus] ni "plans with a record" [hallazgo
    # de Cerberus, 2026-08-22, D-044/D-045]: ver el docstring del modulo,
    # parrafo de `open_issues`, para el porque -- este numero nunca
    # pregunta a GitHub (invariante de Argus, sigue intacta), y desde que
    # `issue` es opcional en los siete tipos ya no cuenta solo actas de
    # plan, asi que "plans" dejo de describir lo que mide.
    # Etiquetas estructurales en ingles [decision del propietario,
    # 2026-08-03]: RECUENTOS->COUNTS, el resto de cada fila igual.
    lines = [
        "COUNTS",
        f"   issues with a live note .  {summary.open_issues}",
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
    """Los ✓ importan tanto como los ⚠️: se imprime siempre el numero
    real, gane o pierda la comparacion, nunca el silencio de una linea
    ausente. Si `gh` fallo, `plans_unreflected_error` lo dice en vez de
    tumbar el arranque; cada discrepancia de indice o de regla nombra la
    nota/linea que diverge, no solo los numeros. `rule_discrepancies_error`
    sigue el mismo patron: si un git corrupto impidio evaluar el chequeo
    de reglas, esta seccion lo dice y nunca pinta "rules match git" para
    un chequeo que no corrio.

    Los ✓/⚠️ dependen de que la lista de discrepancias este vacia, nunca
    de comparar `lineas == notas` a secas (dos numeros pueden coincidir
    aunque el CONTENIDO diverja).

    Etiquetas estructurales en ingles: CHECKS, "no duplicate IDs"/
    "duplicate IDs", "indexes match git"/"indexes do not match git",
    "rules match git"/"rules do not match git". El contenido explicativo
    se queda en espanol.

    Desglose con archivadas: "N lineas / M notas" no explicaba por que
    M > N cuando hay notas archivadas -- si `archived_notes` es cero se
    pinta igual que siempre; si no, se desglosa "K live + J archived / M
    notas".

    Dos avisos (memoria del sistema anterior sin destilar / memoria no
    montada) rompen a proposito la regla de arriba: solo hablan cuando
    hay algo real que avisar, se callan del todo en un proyecto sano --
    no son un chequeo de coherencia, son una senal de sospecha y un
    requisito de arranque.
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

    # Resucitado 2026-08-23 [I-003, hallazgo real de Moriarty] -- mismas
    # dos etiquetas que la version original de 2026-08-02 fijaba antes de
    # retirarse el 2026-08-06 (ver `health.py`, "coherence_rules
    # RESUCITA"). Mismo criterio que arriba: se pinta SIEMPRE, gane o
    # pierda la comparacion (los ✓ importan tanto como los ⚠️), nunca solo
    # cuando falla.
    if report.rule_discrepancies_error is not None:
        lines.append(
            "   ⚠️  no se pudo comprobar si las reglas coinciden con git: "
            f"{report.rule_discrepancies_error}"
        )
    else:
        rule_numbers = f"{report.rule_file_lines} lines / {report.rule_head_lines} committed"
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
