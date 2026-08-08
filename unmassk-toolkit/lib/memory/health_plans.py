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
2. **Preguntar a GitHub por la actividad real de esa issue.** Via `gh
   issue view <n> --json comments,createdAt` se lee la fecha del ultimo
   comentario, o -- si la issue no tiene comentarios todavia -- su fecha
   de creacion: sin comentarios, cualquier commit que la cite queda "sin
   reflejar" por definicion, no hay fecha mas temprana valida contra la
   que compararlo.

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

import query
import timefmt

_FIELD_SEP = "\x1f"
_ISSUE_TRAILER_RE = re.compile(r"^Issue: #(\d+)$", re.MULTILINE)
_GH_TIMEOUT = 10  # segundos -- spec Sec.10.4: "consulta simple, 0,85s medidos"


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
    de `_last_activity_at()` mas abajo es de OTRA fuente (la respuesta de
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


def _last_activity_at(issue_number: int) -> datetime:
    """La fecha de la ultima actividad real de la issue `issue_number` en
    GitHub: su ultimo comentario, o su fecha de creacion si todavia no
    tiene ninguno (sin comentarios, no hay una fecha mas temprana valida
    contra la que comparar -- cualquier commit que la cite queda "sin
    reflejar" por definicion).

    Nunca inventa un resultado si `gh` falla, no esta instalado, tarda
    mas de `_GH_TIMEOUT` o responde con una forma inesperada: lanza
    `RuntimeError` con la causa real en los cuatro casos. Devolver la
    fecha actual (o cualquier fecha) "ganaria" siempre la comparacion y
    ocultaria un commit sin reflejar de verdad -- el mismo fallo
    silencioso que esta pieza existe para impedir.
    """
    try:
        # encoding="utf-8", errors="replace": sin `encoding=`, `text=True`
        # decodifica con el codec de la consola (cp1252 en Windows) y un
        # caracter fuera de ese codec en la salida de `gh` revienta la
        # decodificacion en un hilo aparte -- el llamante recibe
        # `stdout = None` sin ninguna excepcion que capturar aqui [House,
        # 2026-08-08]. `errors="replace"` no es opcional: la salida de `gh`
        # no la controlamos.
        proc = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "comments,createdAt"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"gh issue view #{issue_number} no termino dentro de {_GH_TIMEOUT}s"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"no se pudo ejecutar 'gh' para consultar la issue #{issue_number} "
            f"(no esta instalado, o no es ejecutable): {exc}"
        ) from exc

    if proc.returncode != 0:
        # (proc.stderr or "") / (proc.stdout or ""): con encoding/errors
        # fijados arriba esto ya no deberia poder ser `None`, pero esta es
        # la rama de error -- la que de verdad tiene que contar la causa
        # real, nunca reventar con un AttributeError pelado por leerla.
        raise RuntimeError(
            f"gh issue view #{issue_number} fallo: "
            f"{(proc.stderr or '').strip() or (proc.stdout or '').strip()}"
        )

    try:
        data = json.loads(proc.stdout)
        comments = data.get("comments") or []
        raw = comments[-1]["createdAt"] if comments else data["createdAt"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"respuesta de 'gh issue view #{issue_number}' con forma inesperada: {exc}"
        ) from exc

    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def plans_unreflected() -> tuple[tuple[int, int], ...]:
    """Que planes tienen commits de trabajo mas nuevos que la ultima
    actividad de su issue en GitHub -- la linea `plan #47: 3 commits sin
    reflejar en la issue` del bloque AVISOS [spec Sec.10.4].

    Devuelve un par `(numero_de_issue, commits_sin_reflejar)` por cada
    issue con al menos un commit posterior a su ultima actividad --
    nunca una entrada con `0` (mismo principio que `health.coherence`: lo
    que no diverge no genera texto). Si ningun commit del historial cita
    una issue, devuelve `()` sin llamar a `gh` -- no hay nada que
    verificar.
    """
    by_issue = _issue_commit_dates()
    if not by_issue:
        return ()

    results = []
    for issue_number in sorted(by_issue):
        last_activity = _last_activity_at(issue_number)
        unreflected = sum(1 for date in by_issue[issue_number] if date > last_activity)
        if unreflected:
            results.append((issue_number, unreflected))
    return tuple(results)
