"""La red de seguridad de planes sin reflejar -- partida fuera de
`health.py` por tamano [mismo techo, mismo motivo que
`validator_zones.py`/`validator_pointers.py`: 500 lineas; con el banco
adversarial anadido, `health.py` habria pasado ese techo, PIEZAS.md
Sec.14].

Este fichero NO es una segunda pieza: `health.py` importa
`plans_unreflected` de aqui de forma PLANA [PIEZAS.md Sec.3.3bis] y lo
reexpone bajo el mismo nombre, asi que `health.plans_unreflected` sigue
funcionando exactamente igual para cualquiera que lo llame --
``vocabulary.FIELDS["issue"].reader`` sigue apuntando a
``"health.plans_unreflected"`` sin que ese texto cambie.

QUE ES LO QUE SE PARTIO. `plans_unreflected()` implementa la "red de
seguridad en el boot" [spec-sistema-memoria-v2.md Sec.10.4]: *"si hay
commits `Issue: #N` posteriores al ultimo comentario de la issue ->
aviso 'plan #47: N commits sin reflejar'"*. Su mecanismo, tal como el
propio Sec.10.4 lo fija ("deteccion exacta verificada: `git log
--grep=\"^Issue: #N\"`, cero falsos positivos"), se realiza aqui en dos
pasos:

1. **Descubrir que commits citan una issue.** `write_work` (notes.py
   Sec.8.1) y el campo `Issue` de una nota (format.py Sec.6.4) escriben
   el MISMO literal exacto: `f"Issue: #{n}"` como linea propia del
   cuerpo del commit. No hay ningun lector publico de `query.py` que
   devuelva esto -- las cuatro funciones de `query.py` son de NOTAS
   (`format.parse_message`), y un commit de trabajo no es una nota (no
   encaja en ninguna de las siete plantillas, `parse_message` devuelve
   `None` para el). Por eso este modulo lee el historial COMPLETO con
   `query.run_git_log()` (el UNICO punto de entrada a `git log` de todo
   el sistema desde el 2026-08-02) y filtra del lado de Python con una
   regex anclada por linea (`^Issue: #(\\d+)$`, `re.MULTILINE`) -- la
   MISMA disciplina de "leer todo, filtrar en Python" que
   `query._all_notes()` ya establece para no depender de la semantica
   multilinea de `git log --grep` del binario instalado, aplicada aqui a
   un texto que `query.py` no sabe leer (no es una nota).
2. **Preguntar a GitHub por la actividad real de esas issues**, en UNA
   sola consulta GraphQL (`gh api graphql`) que pide SOLO las citadas,
   bajo un tope total [D-130, I-005: una llamada por issue paso de los
   30 s del hook; listar todas las del repositorio crece con su historia
   entera]. De cada issue se lee la fecha del ultimo comentario, o -- si
   no tiene comentarios todavia -- su fecha de creacion: sin
   comentarios, cualquier commit que la cite queda "sin reflejar" por
   definicion, no hay fecha mas temprana valida contra la que
   compararlo.

**Si `gh` falla o no esta instalado, `plans_unreflected()` NUNCA
devuelve un resultado inventado.** Lanza `RuntimeError` con la causa
real -- devolver `()` (o cualquier cifra) cuando la comprobacion no pudo
hacerse seria exactamente el fallo silencioso que este proyecto existe
para impedir, coherente con `query.run_git_log()`, que ya aplica el
mismo criterio un nivel mas abajo para un fallo real de `git`. Cuando
NINGUN commit cita una issue, `gh` no se llama nunca -- no hay nada que
verificar.

No importa nada fuera de la biblioteca estandar de Python y de sus
hermanos de `lib/memory/` [PIEZAS.md Sec.13], importados PLANOS
[PIEZAS.md Sec.3.3bis].
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import boot_common
import query
import timefmt

_FIELD_SEP = "\x1f"
_ISSUE_TRAILER_RE = re.compile(r"^Issue: #(\d+)$", re.MULTILINE)
_GH_DEADLINE_ENV = "UNMASSK_GH_DEADLINE_SECONDS"
# Tope propio; en el arranque lo recorta `boot_common.network_budget`.
_GH_DEADLINE_DEFAULT = 15.0
# Un alias por issue citada; `{owner}`/`{repo}` los rellena `gh` desde el
# repositorio del directorio actual.
_GH_QUERY = (
    "query($owner: String!, $name: String!) {"
    " repository(owner: $owner, name: $name) {%s} }"
)
_GH_ISSUE_FIELD = (
    "i%d: issue(number: %d) { state title createdAt comments(last: 1) { nodes { createdAt } } }"
)


def _issue_commit_dates() -> dict[int, tuple[datetime, ...]]:
    """Fecha de autor de cada commit que lleva un trailer `Issue: #N`
    literal (escrito por `notes.write_work` o por el campo `Issue` de una
    nota, mismo texto exacto en los dos casos -- `format.py` Sec.6.4),
    agrupadas por numero de issue.

    Lee el historial COMPLETO via `query.run_git_log()` y hace el
    filtrado del lado de Python con una regex anclada por linea, en vez
    de depender de la semantica multilinea de `git log --grep` del
    binario instalado. `run_git_log()` falla en alto (`RuntimeError` con
    el `stderr` real) si `git log` no puede leerse: devolver un
    diccionario vacio aqui se leeria como "ningun commit cita una issue",
    exactamente el fallo silencioso que esta pieza existe para impedir.

    Una rama sin ningun commit todavia devuelve `{}` sin lanzar --
    `query.run_git_log()` ya trata ese caso como estado valido (cadena
    vacia), nunca como el fallo real de la rama de abajo.

    `%at` (segundos-epoch), no `%aI` (ISO-8601 con sufijo `Z` en huso
    cero, que `datetime.fromisoformat` de Python 3.10 no sabe leer)
    [decision del propietario, 2026-08-08 -- ver
    `timefmt.from_git_seconds`]. Esta es la fecha de un commit de GIT; la
    de `_last_activity_by_issue()` mas abajo es de OTRA fuente (la respuesta de
    `gh`, ya en ISO-8601 de verdad) y se queda con su propio parseo --
    unificar las dos en un solo lector mezclaria dos formatos distintos
    bajo un nombre que promete uno solo.
    """
    raw_stdout = query.run_git_log(f"--pretty=format:%at{_FIELD_SEP}%B")

    by_issue: dict[int, list[datetime]] = {}
    for record in raw_stdout.split("\0"):
        if not record:
            continue
        author_date, _sep, body = record.partition(_FIELD_SEP)
        commit_date = timefmt.from_git_seconds(author_date)
        for match in _ISSUE_TRAILER_RE.finditer(body):
            by_issue.setdefault(int(match.group(1)), []).append(commit_date)

    return {number: tuple(dates) for number, dates in by_issue.items()}


def _gh_deadline() -> float:
    """Tope TOTAL, en segundos, de la consulta a GitHub [D-130]. Se lee de
    `UNMASSK_GH_DEADLINE_SECONDS` en cada llamada; un valor que no es un
    numero positivo y finito vuelve al defecto, nunca revienta el arranque
    por una errata."""
    return boot_common.env_seconds(_GH_DEADLINE_ENV, _GH_DEADLINE_DEFAULT)


def _gh_graphql(issue_numbers: list[int]) -> tuple[int, str, str]:
    """`(returncode, stdout, stderr)` de UNA sola consulta GraphQL que pide
    solo las issues citadas [D-130: nada de una llamada por issue, I-005].

    Lanza `RuntimeError` con la causa real si `gh` no esta instalado o
    pasa del tope total. Un `returncode` distinto de cero NO se lanza
    aqui: `gh` sale con 1 cuando una issue citada no existe y aun asi
    devuelve el resto en `stdout`.
    """
    # El tope propio, recortado a lo que quede del arranque: el fetch ya
    # gasto su parte [Moriarty T2, 2026-10-19].
    deadline = boot_common.network_budget(_gh_deadline())
    if deadline <= 0:
        raise RuntimeError(
            "gh api graphql no se lanzo: no quedaba tiempo dentro del tope del arranque"
        )
    deadline = round(max(deadline, 0.1), 1)
    fields = " ".join(_GH_ISSUE_FIELD % (n, n) for n in issue_numbers)
    try:
        # encoding="utf-8", errors="replace": sin `encoding=`, `text=True`
        # decodifica con el codec de la consola (cp1252 en Windows) y un
        # caracter fuera de ese codec revienta en un hilo aparte -- el
        # llamante recibe `stdout = None` sin excepcion [House, 2026-08-08].
        proc = subprocess.run(
            [
                "gh", "api", "graphql",
                "-F", "owner={owner}", "-F", "name={repo}",
                "-f", f"query={_GH_QUERY % fields}",
            ],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=deadline,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh api graphql no termino dentro de {deadline:g}s") from exc
    except OSError as exc:
        raise RuntimeError(
            f"no se pudo ejecutar 'gh' (no esta instalado, o no es ejecutable): {exc}"
        ) from exc
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _last_activity_by_issue(
    issue_numbers: list[int],
) -> tuple[dict[int, datetime], dict[int, tuple[str, str]], tuple[int, ...]]:
    """La fecha de la ultima actividad real de cada issue citada (su
    ultimo comentario, o su fecha de creacion si no tiene ninguno), su
    `(state, title)` de la misma respuesta, y los numeros citados que no
    vuelven (borrada, transferida, un numero que es una PR).

    Nunca inventa un resultado: un fallo de `gh` o una respuesta con forma
    inesperada lanza `RuntimeError`; un numero que no vuelve no se da por
    "reflejado", se devuelve aparte para que el arranque lo nombre.
    """
    returncode, stdout, stderr = _gh_graphql(issue_numbers)
    try:
        repository = json.loads(stdout)["data"]["repository"]
    except (KeyError, TypeError, ValueError):
        repository = None
    if not isinstance(repository, dict):
        if returncode != 0:
            raise RuntimeError(f"gh api graphql fallo: {stderr.strip() or stdout.strip()}")
        raise RuntimeError(
            f"respuesta de 'gh api graphql' con forma inesperada: {stdout.strip()[:200]}"
        )

    activity: dict[int, datetime] = {}
    states: dict[int, tuple[str, str]] = {}
    try:
        for number in issue_numbers:
            issue = repository.get(f"i{number}")
            if issue is None:
                continue
            dates = [c["createdAt"] for c in issue["comments"]["nodes"]]
            raw = max(dates) if dates else issue["createdAt"]
            activity[number] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            states[number] = (str(issue["state"]), str(issue["title"]))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError(f"respuesta de 'gh api graphql' con forma inesperada: {exc}") from exc

    missing = tuple(n for n in issue_numbers if n not in activity)
    return activity, states, missing


def plans_unreflected() -> tuple[tuple[int, int], ...]:
    """Que planes tienen commits de trabajo mas nuevos que la ultima
    actividad de su issue en GitHub -- la linea `plan #47: 3 commits sin
    reflejar en la issue` del bloque AVISOS [spec Sec.10.4].

    Devuelve un par `(numero_de_issue, commits_sin_reflejar)` por cada
    issue con al menos un commit posterior a su ultima actividad --
    nunca una entrada con `0` (mismo principio que `health.coherence`: lo
    que no diverge no genera texto). Si ningun commit del historial cita
    una issue, devuelve `()` sin llamar a `gh` -- no hay nada que
    verificar. Solo la primera parte de `issues_checked()`: el estado de
    cada issue y los numeros sin respuesta los usa `health.build()`.
    """
    return issues_checked()[0]


def issues_checked() -> tuple[
    tuple[tuple[int, int], ...], tuple[tuple[int, str, str], ...], tuple[int, ...]
]:
    """`plans_unreflected()`, el `(numero, state, title)` de cada issue
    citada y los numeros citados que GitHub no devolvio, sacados de la
    MISMA consulta (R-025: una sola llamada por arranque). Falla en alto
    igual que `plans_unreflected()`.
    """
    by_issue = _issue_commit_dates()
    if not by_issue:
        return (), (), ()

    issue_numbers = sorted(by_issue)
    last_activity_by_issue, states, missing = _last_activity_by_issue(issue_numbers)
    results = []
    for issue_number in issue_numbers:
        if issue_number in missing:
            continue
        last_activity = last_activity_by_issue[issue_number]
        unreflected = sum(1 for date in by_issue[issue_number] if date > last_activity)
        if unreflected:
            results.append((issue_number, unreflected))
    issue_states = tuple((n, *states[n]) for n in issue_numbers if n in states)
    return tuple(results), issue_states, missing
