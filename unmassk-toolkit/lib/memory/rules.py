"""El fichero de reglas -- los remembers. Fuera del sistema, a proposito.
Contrato en docs/memoria-v2/PIEZAS.md Sec.9.7.

Un remember NO es memoria de proyecto: no lleva zonas, no pasa por la
aduana de zonas, no aparece en ninguna busqueda ni informe, y no lo lee
ningun agente [Sec.9.7, spec Sec.12]. El fallo que previene: un tercio de
toda la memoria del sistema anterior era configuracion de trabajo
disfrazada de memoria de proyecto, y ensuciaba todas las busquedas.

FORMATO DEL COMMIT, fijado en Sec.9.7 (no esta en TEXTOS.md):

    [remember][user] 🧠 <texto>
    [remember][claude] 🧠 <texto>

Solo titular, en espanol, sin cuerpo, tope de 200 caracteres -- el tope
se fijo con el dato delante (mediana 125, 15 de 19 remembers reales del
v1 caben en 200; los que no caben mezclaban varias reglas en una, y
partirlos en dos es mejor que alargar el tope).

``add()`` HOY (desde 2026-08-06) es UN SOLO PASO: escribe la linea en el
fichero de reglas, atomicamente, y se acaba ahi -- **sin tocar git para
nada, ni un commit vacio ni un commit con el fichero como pathspec**
[orden del propietario, mismo dia y mismo motivo que
``zones.py::_cmd_add()`` (``bin/memory/zones.py``): una sola tarde de
trabajo metio 18 commits propios de regla y 23 de zona en el historial
-- ``rules.md``, igual que ``zones.json``, es fichero de CONFIGURACION,
no una nota de memoria, y no le corresponde un commit por linea]. La
regla queda como una modificacion sin comitear en el arbol de trabajo,
lista para que la arrastre el SIGUIENTE commit real que pase por el
proyecto (``gitmem work``/``gitmem wip``/``gitmem note``/el cierre de
sesion) -- ninguno de los cuatro necesita cableado nuevo para esto:
todos comitean con ``git add --all`` sobre las rutas que reciben
[``notes_commit.stage_and_commit()``], asi que ``rules.md`` entra igual
que cualquier otro fichero modificado, con solo pasarlo como ruta.

**[corregido 2026-08-06] Lo que este docstring describia hasta hoy se
retira, no solo se desactualiza.** El flujo era de DOS pasos -- linea en
el fichero primero, un commit real despues con esa misma linea como
pathspec (antes de eso, mas atras todavia, un commit genuinamente vacio)
-- y esta seccion documentaba con detalle POR QUE ese orden y una
ventana real que ni el orden invertido podia cerrar: un ``SIGKILL`` entre
``atomic_write()`` (fichero ya con la linea nueva) y el commit dejaba la
linea escrita SIN ningun commit detras, sin ninguna excepcion que
disparara la restauracion. Esa ventana, y el mecanismo que la discutia
(``_restore_file_best_effort``, la restauracion de mejor esfuerzo si el
commit fallaba a medias), YA NO EXISTEN: sin ningun commit que pueda
fallar a medias, no hay nada que restaurar. ``add()`` escribe con
``gitcmd.atomic_write()`` (fichero temporal + ``fsync`` + ``os.replace()``,
atomico de verdad, Sec.7.1) y termina ahi -- un fallo a mitad de esa
escritura deja ``rules.md`` con su contenido ANTERIOR intacto por la
propia garantia de ``atomic_write()``, nunca a medias, nunca huerfano;
esta pieza no necesita (ni podria) reforzar esa garantia por su cuenta.

``health.coherence_rules()`` -- la funcion que cruzaba commits de regla
contra ``rules.md`` para cazar precisamente esa ventana -- **se retira
por este mismo cambio** [ver ``lib/memory/health.py``, mismo dia]: sin
ningun commit de regla que la propia escritura genere nunca mas, cada
linea nueva anadida de la forma normal es, desde hoy, indistinguible de
la corrupcion que ese chequeo existia para detectar -- seguiria
gritando, siempre, sobre cualquier regla nueva, un falso positivo
permanente en vez de un chequeo mudo.

RUTA DEL FICHERO DE REGLAS -- resuelta por el propietario en pleno
desarrollo (el encargo original decia ``.claude/commands/remember.md``,
una deduccion incorrecta del orquestador, corregida antes de cerrar esta
pieza). El dato real: el comando ``/remember`` es GENERAL (vive en
``commands/`` del toolkit, no se instala por proyecto) y su cuerpo son
INSTRUCCIONES para Claude, no un programa -- le dice que lea el fichero
de reglas del proyecto en el que esta y lo entregue entero. El fichero
vivo es ``.claude/project-memory/rules.md`` del proyecto, junto a los
ocho indices y a ``zones.json``/``config.json`` [PIEZAS.md Sec.9.7,
ARQUITECTURA.md Sec.207]. Como la ruta es relativa al proyecto, las
reglas de un proyecto nunca se enseñan en otro. La ruta sigue viviendo
en un UNICO punto, ``rules_file_path()``, por si se mueve mas adelante --
publica (sin guion bajo) desde 2026-08-02. El motivo original de esa
visibilidad -- que ``health.coherence_rules()`` (Sec.9.4) la necesitaba
para un ``root`` explicito que no siempre es el cwd del proceso -- se
retira junto con esa funcion el 2026-08-06 [ver mas arriba], pero la
ruta se queda publica igual: varios tests la ejercitan directamente
sobre un ``root`` de fuera (mismo patron que el resto del sistema,
``zones.load(path)``/``indexes.read(name, root)``), y sigue siendo el
unico punto de cambio si la ruta se mueve mas adelante. Mismo criterio
para ``iter_rule_texts()`` (el reconocimiento de una linea de regla,
antes ``_iter_rule_texts``): se hizo publica el mismo dia por el mismo
motivo, y se queda publica ahora que ``health.py`` ya no la reutiliza --
sigue siendo el UNICO reconocimiento de "esto es una linea de regla" en
todo el sistema, para cualquier lector futuro del fichero.

DUPLICACION DELIBERADA (Jaccard sobre texto): ``similar.py`` ya calcula
un solapamiento de vocabulario, pero esta atado a ``Note`` (headline +
description + why + keys, con filtro de zona) -- un remember no tiene
ninguno de esos campos [Sec.9.7: "fuera del sistema"]. El encargo de
esta pieza prohibe tocar cualquier otro fichero ("tu unico fichero es
rules.py"), asi que envolver un remember en un ``Note`` de mentira solo
para reusar ``similar.find_similar`` acoplaria este modulo a una forma
que no le pertenece, y no hay forma de extraer la logica compartida a
un tercer sitio sin salir del fichero permitido. La version local de
aqui (``_tokenize``/``_jaccard``) es deliberadamente minima -- las
mismas cuatro lineas de calculo, sin la parte especifica de ``Note``.

Que NO hace: no valida zonas, no pasa por ``validator.py`` (los
remembers no son ``Note``), no decide semantica ("dos frases distintas
que dicen lo mismo") -- ``similar_existing`` compara solo por texto; el
contraste por significado es punto abierto declarado por la
especificacion, excede a un script [Sec.9.7].

Quien lo llama: ``bin/memory/rule.py`` y el comando ``/remember``
[Sec.9.7] -- ninguno de los dos existe todavia.

``lib/memory/`` no importa nada del toolkit fuera de la biblioteca
estandar de Python [PIEZAS.md Sec.13]. Imports planos entre hermanos
[PIEZAS.md Sec.3.3bis]. Este proyecto no defiende contra un atacante
externo (un solo dueno) -- lo que importa es que el sistema no se
rompa a si mismo: desde el 2026-08-06 el UNICO sitio donde vive un
remember es ``rules.md`` [corregido -- hasta entonces habia dos, el
fichero y un commit propio], asi que el fallo que importa es una
escritura truncada o interrumpida a medias, lo que ``gitcmd.
atomic_write()`` existe para impedir.
"""

import re
from pathlib import Path
from typing import NamedTuple

import gitcmd
import rejection
from emojis import CHANNEL_EMOJI
from model import Rejection, WriteResult
from vocabulary import SIMILARITY_THRESHOLD

# Tope de Sec.9.7 -- constante propia, no vocabulary.HEADLINE_MAX: ese
# tope (80) es del titular de una Note: dominio distinto, valor distinto,
# declarado explicitamente como "fuera del sistema" [Sec.9.7].
_TEXT_MAX_CHARS = 200

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Reconoce una linea de regla ya escrita en el fichero: "[remember][kind]
# <emoji> <texto>". El emoji se casa con \S+ (no con el literal fijo) por
# el mismo motivo que format._SUBJECT_RE usa \S+ para el suyo: no atar el
# regex a un caracter exacto que vive en otro modulo.
_RULE_LINE_RE = re.compile(r"^\[remember\]\[(?P<kind>[^\]]+)\]\s+\S+\s+(?P<text>.+)$")

# Cabecera literal del fichero de reglas -- mismo patron que
# ``indexes._header_for`` aplica a sus vecinos (DECISIONS.md, etc.):
# "Lo escribe el script. No editar. Si diverge, manda git." Coherente con
# que el fichero vive junto a los ocho indices y a zones.json/config.json
# [PIEZAS.md Sec.9.7, ARQUITECTURA.md Sec.207].
_RULES_HEADER = "# RULES — reglas de trabajo (remember). Lo escribe el script. No editar. Si diverge, manda git.\n"


def rules_file_path(root: Path) -> Path:
    """Ruta del fichero de reglas -- ver "RUTA DEL FICHERO DE REGLAS" en
    el docstring del modulo. Un unico punto de cambio.

    Publica (sin guion bajo) desde 2026-08-02, cuando `health.coherence_rules`
    la necesitaba para leer el fichero de un `root` explicito que no
    siempre coincide con el cwd del proceso. Esa funcion se retira el
    2026-08-06 [ver docstring del modulo], pero la ruta se queda publica:
    varios tests la siguen ejercitando directamente sobre un `root` de
    fuera.
    """
    return root / ".claude" / "project-memory" / "rules.md"


def _lock_resource(root: Path) -> Path:
    """Candado GLOBAL propio de este modulo, mismo espiritu que
    ``notes._lock_resource`` -- envuelve la lectura-modificacion-escritura
    completa del fichero (leer el contenido previo, anadir la linea,
    escribir) para que dos ``add()`` concurrentes no pierdan ninguna
    regla [correccion 2026-08-06: hasta entonces tambien serializaba
    ``git add``/``git commit``, retirados de ``add()`` ese mismo dia --
    ver docstring del modulo]. Vive dentro de ``.git/`` para no aparecer
    en ``git status``.
    """
    return root / ".git" / "memory-rules"


def _repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(_WORD_RE.findall(text.lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Interseccion sobre union. Dos vocabularios vacios no son
    "identicos" -- son datos ausentes; 0.0, nunca division por cero."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def iter_rule_texts(content: str) -> tuple[str, ...]:
    """Los textos (sin prefijo `[remember][kind] emoji `) de cada linea de
    regla reconocida en `content`. Una linea que no case (p.ej. un
    comentario, o una linea en blanco) se salta en silencio -- mismo
    principio que ``format.parse_message``: un fichero con algo escrito a
    mano no tumba la lectura entera.

    Publica (sin guion bajo): es el UNICO reconocimiento de "esto es una
    linea de regla" en todo el sistema. Hasta el 2026-08-06 tambien la
    reutilizaba `health.coherence_rules` sobre el cuerpo de un commit --
    esa funcion se retira ese mismo dia [ver docstring del modulo], pero
    la forma (solo texto, sin `kind`) se queda intacta: `similar_existing()`
    la sigue usando por debajo (via `_iter_rule_lines()`) y hay un
    consumidor de test directo (`test_rule_script.py`).
    """
    texts = []
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is not None:
            texts.append(match.group("text"))
    return tuple(texts)


class _RuleMatch(NamedTuple):
    """Una candidata de `similar_existing()`: dueno (`kind`) + texto --
    detalle privado de este modulo, no una forma del sistema (Sec.5.3
    reserva eso a ``model.py``; mismo criterio ya usado en este repo por
    ``report_render.py::_TypeSplit``). Un ``NamedTuple`` hereda de
    ``tuple`` y compara igual que una pareja plana con los mismos
    valores (``("user", texto) == _RuleMatch("user", texto)``) -- quien
    llama nunca necesita conocer este tipo, solo comparar por igualdad.
    """

    kind: str
    text: str


def _iter_rule_lines(content: str) -> tuple[tuple[str, str], ...]:
    """Como `iter_rule_texts()` pero conservando el `kind` (dueno) de
    cada linea -- uso EXCLUSIVO de `similar_existing()`, mas abajo en
    este mismo fichero.

    `iter_rule_texts()` en si no se toca ni cambia de forma: descarta el
    grupo `kind` a proposito porque tiene su propio consumidor real que
    depende de que siga devolviendo solo texto (`test_rule_script.py`;
    hasta el 2026-08-06 tambien `health.coherence_rules()`, retirada ese
    dia [ver docstring del modulo]) -- cambiar esa forma rompe esa
    costura. Esta funcion reutiliza el mismo `_RULE_LINE_RE` (mismo
    reconocimiento de linea, nunca una segunda copia del patron) y
    simplemente conserva el campo que `iter_rule_texts()` descarta.
    """
    lines = []
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is not None:
            lines.append((match.group("kind"), match.group("text")))
    return tuple(lines)


def _reject_too_long(text: str) -> Rejection:
    length = len(text)
    what = f"la regla tiene {length} caracteres y el tope son {_TEXT_MAX_CHARS}"
    options = (
        f'  "{text}"',
        "",
        "Una regla es un titular sin cuerpo -- lo que no cabe en el tope no",
        "llega a leerse nunca. Si mezcla varias cosas, son varias reglas.",
    )
    command = (f'gitmem rule "<hasta {_TEXT_MAX_CHARS} caracteres>"',)
    return rejection.build(
        kind="rule_too_long", what=what, options=options, command=command
    )


def _reject_invalid_kind(kind: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero -- mismo momento y mismo
    criterio que `_reject_invalid_text`, aplicado al campo `kind`
    [correccion 2026-08-02, hallazgo 5b de Moriarty, ronda 2: `add()`
    validaba el texto de la regla pero no el tipo]. `_RULE_LINE_RE`
    reconoce el tipo con `[^\\]]+` dentro de una sola linea -- un `kind`
    con un salto de linea parte la linea escrita en dos al releer, y
    ninguna de las dos vuelve a casar con `_RULE_LINE_RE`: la regla entera
    queda invisible, el mismo fallo ya cazado para el texto, aqui sin
    proteccion hasta ahora.
    """
    if "\n" in kind:
        what = "el tipo de la regla lleva un salto de linea"
        options = (
            f"  {kind!r}",
            "",
            "El fichero de reglas es una linea por regla. Un salto de linea en el",
            "tipo rompe ese formato igual que ya lo rompia en el texto: al",
            "releer, la linea se parte en dos y ninguna de las dos vuelve a",
            "reconocerse como regla -- la regla entera queda invisible.",
        )
    else:
        what = "el tipo de la regla esta vacio"
        options = (
            "Un tipo en blanco (o solo espacios) no identifica quien la escribio.",
        )
    command = ('gitmem rule "<texto>" --kind <user|claude>',)
    return rejection.build(
        kind="rule_invalid_kind", what=what, options=options, command=command
    )


def _reject_invalid_text(text: str) -> Rejection:
    """Rebota ANTES de tocar git o el fichero -- mismo momento que
    `_reject_too_long`. Dos casos:

    - Un salto de linea: el fichero de reglas es una-linea-por-regla
      (`_RULE_LINE_RE`); un texto con `\\n` se commitearia entero pero
      al escribirlo en el fichero rompe ese formato, y al releer solo se
      recupera el trozo anterior al salto -- el resto queda huerfano e
      invisible. Es el mismo fallo ya cazado y arreglado en `format.py`
      (un titular con salto de linea hacia desaparecer la nota entera),
      aqui sin el mecanismo de plegado de `format.py` porque `rules.py`
      es deliberadamente minimo [ver docstring del modulo] -- rechazar
      es la unica salida que no rompe el formato de una linea por regla.
    - Vacio o solo espacios: una regla en blanco no dice nada.
    """
    if "\n" in text:
        what = "la regla lleva un salto de linea"
        options = (
            f"  {text!r}",
            "",
            "El fichero de reglas es una linea por regla. Un salto de linea rompe",
            "ese formato: al releer, solo se recupera el trozo anterior al salto y",
            "el resto queda huerfano e invisible -- el mismo fallo ya arreglado en",
            "el formato de las notas, aqui sin forma de plegarlo.",
        )
    else:
        what = "la regla esta vacia"
        options = (
            "Una regla en blanco (o solo espacios) no dice nada.",
        )
    command = (f'gitmem rule "<hasta {_TEXT_MAX_CHARS} caracteres, una sola linea>"',)
    return rejection.build(
        kind="rule_invalid_text", what=what, options=options, command=command
    )


def add(text: str, kind: str) -> WriteResult:
    """Anade una regla: una linea mas en el fichero de reglas, escrita de
    forma atomica -- UN SOLO PASO, sin tocar git para nada [orden del
    propietario, 2026-08-06, ver docstring del modulo]. La linea queda
    como una modificacion sin comitear en el arbol de trabajo, lista para
    que la arrastre el siguiente commit real del proyecto.

    Si `text` supera `_TEXT_MAX_CHARS`, lleva un salto de linea, o esta
    vacio/solo espacios, rebota SIN tocar el fichero. Lo mismo si `kind`
    lleva un salto de linea o esta vacio/solo espacios [correccion
    2026-08-02, hallazgo 5b de Moriarty, ronda 2 -- ver
    `_reject_invalid_kind`: antes solo `text` se validaba, y un `kind` mal
    formado rompia la estructura de una-linea-por-regla igual que ya lo
    hacia un `text` sin proteger].

    No hay ningun paso que pueda fallar a medias y dejar algo que
    restaurar: `gitcmd.atomic_write()` (fichero temporal + `fsync` +
    `os.replace()`) es atomico de verdad -- un fallo a mitad de la
    escritura deja `rules.md` con su contenido ANTERIOR intacto, por la
    propia garantia de esa funcion [ver docstring del modulo, correccion
    2026-08-06: el mecanismo de restauracion de mejor esfuerzo que existia
    aqui, `_restore_file_best_effort`, se retira con este cambio -- solo
    tenia sentido cuando `add()` tambien comiteaba y ese commit podia
    fallar a medias].
    """
    if "\n" in kind or not kind.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(_reject_invalid_kind(kind),), git_error=None
        )
    if "\n" in text or not text.strip():
        return WriteResult(
            ok=False, note_id=None, rejections=(_reject_invalid_text(text),), git_error=None
        )
    if len(text) > _TEXT_MAX_CHARS:
        return WriteResult(
            ok=False, note_id=None, rejections=(_reject_too_long(text),), git_error=None
        )

    root = _repo_root()
    with gitcmd.file_lock(_lock_resource(root)):
        emoji = CHANNEL_EMOJI["rule"]
        subject = f"[remember][{kind}] {emoji} {text}"

        path = rules_file_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            previous_content = path.read_text(encoding="utf-8")
        else:
            previous_content = _RULES_HEADER + "\n"
        gitcmd.atomic_write(path, previous_content + subject + "\n")

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)


def read_all() -> str:
    """El fichero de reglas ENTERO, sin filtrar -- lo que ``/remember``
    entrega a Claude [Sec.9.7]. Cadena vacia si todavia no hay ninguna
    regla, nunca una excepcion.

    Bajo el mismo candado que ``add()``: sin esto, un lector podria caer
    justo en medio de la transaccion de un ``add()`` concurrente (fichero
    ya escrito, commit todavia en marcha) -- una inconsistencia real,
    aunque de una fraccion de segundo, entre lo que el fichero ya dice y
    lo que git todavia no sabe.
    """
    root = _repo_root()
    with gitcmd.file_lock(_lock_resource(root)):
        path = rules_file_path(root)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")


def similar_existing(text: str) -> tuple[_RuleMatch, ...]:
    """Las reglas ya guardadas que se parecen a `text`, por texto -- se
    ensena antes de anadir [Sec.9.7]. El contraste por significado (dos
    frases distintas que dicen lo mismo) NO se construye: la
    especificacion lo declara punto abierto, excede a un script.

    Cada candidata es una pareja `(kind, text)` -- el dueno junto al
    texto, nunca el texto solo [endurecimiento 2026-08-04, bloqueo del
    rechazo de Sec.1.11b de TEXTOS.md]. Una regla `[user]` y una
    `[claude]` con el mismo texto NO son la misma regla: una es una
    instruccion del propietario, la otra una nota que Claude se dejo a
    si mismo. Sin el dueno, "casi repetida" no se puede juzgar -- el
    rechazo de Sec.1.11b necesita mostrar de quien es cada candidata
    (``🧠 [user] <texto>``), y una cadena suelta obligaria al que llama a
    volver a partir el texto para recuperar algo que este modulo ya sabe
    al leerlo. El criterio de parecido (umbral, tokenizado) no cambia:
    solo cambia lo que se devuelve por cada candidata que ya pasaba el
    corte.
    """
    candidate = _tokenize(text)
    matches = []
    for kind, existing_text in _iter_rule_lines(read_all()):
        if _jaccard(candidate, _tokenize(existing_text)) >= SIMILARITY_THRESHOLD:
            matches.append(_RuleMatch(kind, existing_text))
    return tuple(matches)
