"""Leer y escribir el (arrow) del cierre de sesion -- contrato en
docs/memoria-v2/PIEZAS.md Sec.9.6.

Para que: el (arrow) es el "siguiente paso" que un arranque enseña
(TEXTOS Sec.3.1, primera linea). Perder el hilo entre sesiones es el
UNICO fallo que esta pieza existe para prevenir -- por eso escribir es
un commit vacio, sin zonas, sin identificador, sin linea de indice y
sin lapida [spec Sec.9], y leer es "el ultimo que hay, el que sea".

**La tension de `paths`, y como se resuelve** [encargo del propietario,
2026-08-02, sin fuente literal en Sec.9.6 -- se deja dicho aqui porque
no esta escrito en ningun otro sitio]: `gitcmd.commit(message, paths,
allow_empty)` exige `paths` no vacio (revienta con `ValueError` si no
[gitcmd.py Sec.7.1]) porque su contrato es "commitea EXACTAMENTE estas
rutas" -- pero un cierre de sesion no toca ningun fichero, no hay indice
que escribir. Llamar a `gitcmd.commit()` con una lista vacia no es una
opcion. La resolucion usa `gitcmd.commit_empty(message)` -- la pieza
UNICA de git para un commit genuinamente vacio (`--cleanup=verbatim` +
`--allow-empty`, sin `paths` ni `--`; ver por que del `--cleanup=verbatim`
en el docstring de `gitcmd.commit()`: sin el, git recorta el espacio de
continuacion que `format._fold_raw` deja en una linea plegada en blanco,
y un punto de contexto con un salto de linea propio desaparecería al
releerse). `rules.add()` (Sec.9.7) necesita exactamente lo mismo por el
mismo motivo -- las dos llamaban antes a `gitcmd.run()` con la misma
invocacion construida a mano, cada una por su lado; `commit_empty()`
existe para que esa duplicacion (y el riesgo de que a una se le olvide
el `--cleanup=verbatim`) deje de ser posible [PIEZAS.md Sec.7.1].

**Sin candado.** Los demas escritores de este sistema (`notes.py`,
`indexes.py`) toman `gitcmd.file_lock()` porque hacen una
lectura-modificacion-escritura de un fichero COMPARTIDO (un indice) que
dos escritores concurrentes podrian pisarse. `write()` no lee ni
modifica ningun fichero compartido -- es un commit vacio suelto. Dos
`git commit` concurrentes de verdad ya se serializan por el candado
propio de git sobre `.git/index.lock`; si chocan, el segundo devuelve
un `GitResult.returncode != 0` con el `stderr` real de git, que
`write()` propaga tal cual en `WriteResult.git_error` -- un fallo con
causa, no una corrupcion silenciosa.

**Sin aduana.** [spec Sec.9.6 tabla "Sus tests", fila 3] `write()` no
llama a `validator` para nada -- ni `validate_headline` ni ninguna otra
funcion de esa pieza. Es la unica escritura del sistema exenta a
proposito: es lo ultimo que se escribe en una sesion, y una pregunta ahi
es friccion en el peor momento.

**`latest()` reconstruye el timestamp real de git**, mismo patron ya
establecido en `query.py` para `Note`: `format.parse_context_message`
solo puede devolver un marcador de posicion (`datetime.now()`, ver su
propio docstring) porque el texto del commit nunca lleva la fecha --
quien la necesita la obtiene aparte, de `git log`, y reconstruye el
objeto con `dataclasses.replace`. Sin esto, el consumidor declarado
(`boot.build`, que enseña "Context (cerrado <fecha> UTC):" en TEXTOS
Sec.3.1) recibiria la hora en que se LEYO el arranque, no la hora en
que se CERRO la sesion -- dos cosas distintas.

**Un fallo real de `git log` no se confunde con "no hay contexto
todavia"**: si `git log` devuelve un `returncode != 0` genuino,
`latest()` propaga `RuntimeError` con el `stderr` real -- devolver
`None` ahi seria el mismo silencio que `query.py` (Sec.8.2, fila 2)
declara inaceptable para un fallo real de git.

Quien llama [Sec.9.6]: `bin/memory/context.py` (el protocolo de cierre)
y `boot.build`. Ninguno de los dos existe todavia -- mismo estado que
`model.py`/`ids.py` cuando se escribieron (la pieza precede a su
llamador en este orden de capas), no es un hueco de wiring.

`lib/memory/` no importa nada del toolkit fuera de la biblioteca
estandar de Python [PIEZAS.md Sec.13]. Import plano entre hermanos
[PIEZAS.md Sec.3.3bis].
"""

import dataclasses
from datetime import datetime

import format
import gitcmd
from model import ContextNote, WriteResult
from query import run_git_log

# Mismos separadores que query.py (Sec.8.2): NUL entre commits (`-z`),
# `\x1f` entre campos dentro de uno -- un commit real nunca puede
# contener un NUL, y el mensaje crudo (`%B`) va ultimo para que un
# `\x1f` que aparezca dentro del propio mensaje nunca particione de mas.
_FIELD_SEP = "\x1f"
_LOG_FORMAT = f"--pretty=format:%aI{_FIELD_SEP}%B"


def write(ctx: ContextNote) -> WriteResult:
    """Escribe `ctx` como un commit vacio -- el (arrow) del cierre de
    sesion. Sin candado, sin aduana, sin indice: ver el docstring del
    modulo para el porque de cada una de las tres ausencias.
    """
    message = format.build_context_message(ctx)
    result = gitcmd.commit_empty(message)

    if result.returncode != 0:
        return WriteResult(ok=False, note_id=None, rejections=(), git_error=result.stderr)
    return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def latest(all_refs: bool = True) -> ContextNote | None:
    """El (arrow) mas reciente, o `None` si nunca se cerro ninguna
    sesion todavia. `git log` ya devuelve los commits del mas nuevo al
    mas viejo -- el primer registro que `format.parse_context_message`
    reconoce como cierre de sesion ES el vigente, sin mas logica: un
    cierre nuevo pisa al anterior por construccion, nunca conviven.

    Esta funcion depende de que `format.parse_context_message` distinga
    "esto no es un cierre" de "es un cierre sin puntos" [correccion
    2026-08-02, hallazgo 3 de Moriarty, ronda 2 -- ver el docstring de esa
    funcion para el detalle completo]: con la ambiguedad vieja, un cierre
    real sin puntos de contexto (un valor perfectamente valido) se
    interpretaba aqui como "sigo buscando", y este bucle devolvia el
    cierre MAS ANTIGUO que si tenia puntos -- perdiendo exactamente el
    hilo entre sesiones que esta pieza existe para no perder. No hizo
    falta tocar nada en este fichero: el arreglo vive entero en el lector
    unico del formato, nunca en un segundo parseo aqui.

    **Una rama sin ningun commit todavia es un estado VALIDO, no un
    fallo** [correccion 2026-08-02, hallazgo 2 de Moriarty, ronda 2]: un
    proyecto recien creado, sin un solo commit, no tiene ningun cierre de
    sesion que enseñar -- es exactamente el caso que esta funcion ya
    declara como `None`, nunca un `RuntimeError`. Antes de este arreglo,
    `boot.build()` (que llama a `context.latest()` sin capturar nada)
    reventaba en el primerisimo arranque de cualquier proyecto, antes de
    que existiera un solo commit de verdad -- demostrado ejecutando.

    **Desde el 2026-08-02 esta funcion ya no habla con `git log`
    directamente** [encargo del orquestador -- "solo puede haber un
    lector del historial", Sec.8.2]: antes tenia su propia invocacion de
    `gitcmd.run(["log", ...])` a mano, sin reintento y con su propia
    copia del reconocimiento de "rama sin commits" -- el mismo patron de
    tres implementaciones que Sec.8.2 declara prohibido, y que ya habia
    costado arreglar el caso de rama sin commits cuatro veces por
    separado (una por lector). Ahora pasa por `query.run_git_log()`, que
    ademas de tratar la rama sin commits como estado valido reintenta un
    fallo transitorio -- reintento que esta funcion no tenia antes.
    """
    # `--all` y no solo la rama de ahora [decision del propietario,
    # 2026-08-05]: se trabaja en mas de una maquina, y el ultimo cierre
    # puede estar en una rama que aqui ni siquiera esta desplegada -- se
    # dejo el trabajo en la tienda sobre `feat/x` y en casa se abre `dev`.
    # Mirando solo la rama de ahora se devuelve un cierre de hace dias
    # como si fuera el estado del proyecto, sin que nada lo delate.
    # `--date-order` para que el mas reciente EN EL TIEMPO salga primero
    # aunque venga de otra rama; sin el, git ordena por topologia y el de
    # la rama ajena puede quedar detras.
    # `all_refs=False` cuando el remoto configurado NO es de este
    # proyecto: `--all` entra tambien en `refs/remotes`, y como TODOS los
    # proyectos del propietario usan este mismo sistema, el cierre de otro
    # proyecto tiene exactamente la misma forma y se devolvia como si
    # fuera el de este -- titular, contexto y todo, en la primera linea
    # del arranque y sin un solo aviso [Argus, 2026-08-05].
    extra = ("--all", "--date-order") if all_refs else ("--date-order",)
    raw_stdout = run_git_log(_LOG_FORMAT, extra)

    for record in raw_stdout.split("\0"):
        if not record:
            continue
        author_date, raw_message = record.split(_FIELD_SEP, 1)
        parsed = format.parse_context_message(raw_message.rstrip("\n"))
        if parsed is not None:
            return dataclasses.replace(parsed, timestamp=datetime.fromisoformat(author_date))
    return None
