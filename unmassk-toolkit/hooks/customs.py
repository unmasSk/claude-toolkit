#!/usr/bin/env python3
"""hooks/customs.py -- la aduana. PreToolUse/Bash: intercepta el commit,
llama al MISMO validador que usan los scripts (`validator.py`), y
bloquea con la pregunta dentro si lo rechaza.

Contrato: docs/memoria-v2/PIEZAS.md Sec.11 (tabla de hooks y "Sus
tests") y Sec.6.3/7.4/7.5, docs/spec-sistema-memoria-v2.md Sec.6 y P5,
docs/memoria-v2/TEXTOS.md Sec.1. Contrato en rojo satisfecho:
tests/memory/test_customs_hook.py (8 tests).

Las cinco reglas que la gobiernan [encargo]:

1. SE ENCIENDE SOLA -- `config.customs_enabled` nace en `None` ("sin
   ajuste explicito") [config.py Sec.6.3] y esta pieza la enciende en
   cuanto el proyecto tiene su primera nota escrita, sin boton
   [decision del propietario, DEUDA.md B19 punto 2, 2026-08-03]. La
   bandera se conserva solo para APAGARLA a mano: si el fichero dice
   `true`/`false` explicito, ese valor manda siempre sobre la deteccion
   automatica. Un proyecto recien instalado no tiene notas todavia, asi
   que la deteccion automatica lo deja apagado igual que antes -- el
   motivo original (no bloquear al sistema viejo el primer dia) se
   sostiene solo con esta regla, no hace falta un interruptor aparte.
2. Encendida, bloquea con el texto EXACTO del rechazo -- lo produce
   `rejection.py` a partir de lo que decide `validator.py`. Esta pieza
   no redacta nada suyo salvo los rechazos nuevos que no existen en
   TEXTOS.md (ver mas abajo: "commit corriente" y "reescribe historia").
3. `wip` (`🚧`) y `⏩` (cierre de sesion) pasan sin ni una pregunta.
4. Llama al MISMO validador -- `validator.py`, sus dos unicos
   consumidores son `notes.py` y este hook [Sec.7.5]. Ninguna regla de
   validacion de NOTA vive en este fichero.
5. Un commit corriente de codigo rebota remitiendo a `gitmem work`
   [decision del propietario, 2026-08-03, PIEZAS.md Sec.11.1: "siempre
   que se use git tiene que guardarse de una forma u otra en memoria"].
   `git commit --amend` y `git rebase` rebotan por un motivo DISTINTO
   (reescriben historia, violan P1) -- `git merge` y `git cherry-pick`
   NO rebotan, pasan siempre (ver la correccion de abajo).

CORRECCION DEL PROPIETARIO, 2026-08-03, DEFINITIVA -- sobre una version
intermedia de este mismo dia que trataba los cuatro caminos de abajo
como un unico "esto no es una nota, rebota a `gitmem work`". Esa lectura
era erronea: **"la aduana los ve pasar" no es "la aduana los bloquea
todos"** -- los ve y decide, y la decision parte en dos segun P1
("Nada se borra ni se reescribe jamas. Toda correccion es un commit
nuevo") y §10.4 (squash al fusionar):

| Comando | Decision | Por que |
|---|---|---|
| `git commit --amend` | **RECHAZA** | Reescribe un commit ya existente -- viola P1 |
| `git rebase` (salvo `--abort`/`--continue`/`--skip`) | **RECHAZA** | Reescribe historia en lote -- viola P1; su uso legitimo (limpiar la rama) ya tiene mecanismo: el squash al merge [spec Sec.10.4]. `--continue`/`--skip` PASAN [DEUDA.md B19 punto 3]: bloquear un rebase ya empezado deja al usuario atascado sin salida |
| `git merge` | **PASA** | Añade a la historia, no la reescribe; git ya lo registra por existir, y en el flujo con squash el commit final entra por la aduana como commit de trabajo normal |
| `git cherry-pick` | **PASA, a secas** | Añade, sin confirmacion -- seria friccion en una operacion rara. Su unico riesgo real, duplicar el identificador de una nota, ya tiene su alarma: el chequeo de IDs duplicados del arranque [spec Sec.3.1, alarma pasiva] |

**El razonamiento de fondo** [textual del propietario]: la regla no es
"todo commit lleva una nota de memoria". Git ES el sustrato [spec Sec.1
y P1]: un commit de merge ya queda registrado por existir en la
historia. Las notas son UN TIPO de commit, no un peaje que paga todo
commit. El registro del trabajo tiene sus propios canales ya diseñados
-- el contexto del cierre de sesion y la issue del plan.

**`git pull`** (hallazgo propio, reportado y NO añadido por decision del
propietario): con `merge` pasando, deja de ser un agujero -- los dos
añaden a la historia y los dos pasan igual.

ASUNCIONES DE FIRMA, DISCLOSED (PIEZAS.md Sec.0.2 -- un hueco puede ser
deliberado, se anota, no se rellena con criterio propio):

1. **`git rebase --abort`, `--continue` y `--skip` pasan los tres --
   solo se rechaza el `git rebase` que EMPIEZA uno** [decision del
   propietario, DEUDA.md B19 punto 3, 2026-08-03, que revoca la lectura
   anterior de este mismo punto]. El bloqueo va en la puerta de
   entrada, no a mitad del pasillo: si alguien ya esta dentro de un
   rebase -- lo empezo en su terminal, o vino de un conflicto --
   bloquear `--continue`/`--skip` lo deja atascado sin salida hacia
   delante y con el repositorio a medias, que es peor que el dano que
   se queria evitar. La lectura anterior (solo `--abort` exento) la
   tomo un agente por su cuenta sin que nadie la revisara.
2. **`merge`/`cherry-pick` aprueban SIEMPRE**, cualquier flag que
   traigan -- no hay exencion que comprobar porque no hay bloqueo del
   que eximir.
3. **`cherry-pick` nunca intenta leer un `-m`** (irrelevante ahora que
   siempre aprueba, pero documentado por si un dia deja de serlo):
   `cherry-pick -m <N>` no es un mensaje, es el numero de padre
   "mainline" de un commit de fusion.
4. **Los dos rechazos de reescritura de historia (amend, rebase) NO son
   de los diez de `TEXTOS.md` Sec.1** -- TEXTOS.md no cubre "reescribir
   historia", solo notas. Se construyen con `rejection.build()`, mismo
   contrato de tres partes que los diez [Sec.7.4], con redaccion propia
   citando P1/Sec.10.4 -- igual que ya hace
   `bin/memory/work.py::_protected_branch_rejection` para su propio
   rechazo sin plantilla en TEXTOS.md [visto en produccion antes de
   escribir esto]. Mismo trato para el rechazo de "commit corriente sin
   nota reconocible", que sigue en pie sin cambios.
5. **`-F <fichero>`/heredoc** no se leen como mensaje -- mismo limite ya
   declarado en `test_customs_hook.py` ("ASUNCIONES DE FIRMA" punto 2):
   sin `-m`/`--message` extraible, un `commit` corriente (sin
   `--amend`) cae en el rebote de "no es nota", nunca se aprueba a
   ciegas.
6. **El Context real para `validator.validate_note`** se arma leyendo
   el estado real del repositorio -- `zones.load`, `query.by_zone` (para
   `existing_in_zone` y, con `(None, None)`, para `known_ids`),
   `config.load` -- exactamente el mismo patron que
   `bin/memory/note.py::_build_context` [visto en produccion antes de
   escribir esto], no un `Context` vacio fabricado a mano. En un
   repositorio de pruebas recien creado (sin notas todavia) esto
   coincide byte a byte con un `Context` vacio, que es lo que
   `tests/memory/test_customs_hook.py::_expected_block_text` construye
   por separado para derivar el texto esperado.

Canal de salida [P5, "medido como fiable": `decision:block` llega al
modelo]: JSON `{"decision": "approve"}` / `{"decision": "block",
"reason": "..."}` por stdout, proceso SIEMPRE con `returncode == 0` --
la decision vive en el JSON, nunca en el codigo de salida. Mismo canal,
misma convencion de invocacion (payload de `Bash` `tool_input` por
stdin) que `hooks/pre-merge-gate.py`, ya en produccion.

Fallo cerrado ante cualquier excepcion no prevista: bloquea con un
diagnostico (nunca una traza de pila -- spec Sec.5.1, "un hook que
revienta al bloquear un commit deja al usuario con un volcado de pila
en vez de con la pregunta que tenia que contestar") -- mismo principio
que `config.py` fija para un fichero corrupto ("un vigilante que no
vigila y encima no lo dice"), y mismo patron que
`hooks/pre-merge-gate.py` ya aplica ("Fail closed on any unhandled
error -- never let a broken hook approve silently").
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

# ── Path setup -- lib/memory/ debe ser importable [mismo patron que
# hooks/boot_launcher.py y bin/memory/*.py, ya en produccion] ──────────

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(_HOOKS_DIR)
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import config  # noqa: E402
import format  # noqa: E402
import gitcmd  # noqa: E402
import indexes  # noqa: E402
import query  # noqa: E402
import rejection as rejection_  # noqa: E402
import validator  # noqa: E402
import vocabulary  # noqa: E402
import zones as zones_lib  # noqa: E402

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB -- mismo limite que hooks/pre-merge-gate.py

# ── Deteccion de "esto crea un commit", por FORMA de comando -- mismo
# mecanismo que hooks/pre-validate-commit-trailers.py::_is_direct_git_commit
# (tokenizar con shlex, localizar el token "git" real, saltar sus flags
# globales de valor) extendido a los cuatro subcomandos que crean un
# commit sin pasar por "git commit -m" [correccion del propietario]. ──

_GIT_PROGRAM_TOKEN_RE = re.compile(r"(?:^|/)git(?:\.exe)?$", re.IGNORECASE)
_GIT_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_SHELL_STATEMENT_SEPARATORS = ("&&", "||", ";", "|")
_COMMIT_CREATING_SUBCOMMANDS = {"commit", "merge", "rebase", "cherry-pick"}

# Los tres pasan sin bloquear -- solo se rechaza el `git rebase` que
# EMPIEZA uno. Ver "ASUNCIONES DE FIRMA" punto 1 del docstring
# [DEUDA.md B19 punto 3, decision del propietario, 2026-08-03].
_REBASE_PASSTHROUGH_FLAGS = frozenset({"--abort", "--continue", "--skip"})

# Mismas tres banderas, como regex sobre la cadena CRUDA -- unico uso:
# el fallback de `_find_commit_creating_statement` cuando `shlex` no
# tokeniza (comillas desbalanceadas, p.ej. un apostrofo sin escapar en
# el mensaje). Limites `(?<![\w-])`/`(?![\w-])` en vez de `\b` porque
# `-` no es caracter de palabra -- `\b` no marca frontera entre un
# espacio y un `-`. [hallazgo Moriarty T1, 2026-08-06: sin esto, el
# passthrough de rescate nunca ve `--abort`/`--continue`/`--skip` en
# ese camino].
_RESCUE_FLAG_RE = re.compile(
    r"(?<![\w-])(?:"
    + "|".join(re.escape(f) for f in sorted(_REBASE_PASSTHROUGH_FLAGS))
    + r")(?![\w-])"
)


def _split_statements(tokens):
    """Parte una lista de tokens por los separadores de sentencia de
    shell -- mismo patron que `pre-merge-gate.py`/
    `pre-validate-commit-trailers.py` ya aplican, para que
    `a && git commit -m x` evalue la sentencia real, no la cadena
    entera de un tiron.
    """
    statements = []
    current = []
    for tok in tokens:
        if tok in _SHELL_STATEMENT_SEPARATORS:
            statements.append(current)
            current = []
        else:
            current.append(tok)
    statements.append(current)
    return statements


def _shell_statements(command):
    """EL UNICO tokenizador de shell del fichero [fase 2 del contrato del
    `cd`, hallazgo Cerberus 2026-08-06 -- antes habia DOS mecanismos que
    resolvian el mismo problema de formas distintas: `shlex.split()`
    plano aqui, `shlex.shlex(punctuation_chars=True)` solo en
    `_resolve_effective_cwd`]. Devuelve la lista de SENTENCIAS (cada una
    ya partida por `_split_statements`) o `None` si `command` no tokeniza
    en absoluto (comillas desbalanceadas -- p.ej. un apostrofo sin
    escapar en un mensaje).

    `punctuation_chars=True` en vez del modo plano de `shlex.split()`:
    `;`/`&&`/`||`/`|` PEGADOS sin espacio a la palabra siguiente/anterior
    (`echo hi;git commit`, `cd /ruta;`) quedan FUERA de `wordchars` en
    este modo, asi que siempre tokenizan como separador propio -- en el
    modo plano se funden con la palabra vecina en un solo token
    (`'hi;git'`, `'/ruta;'`), y ni `_GIT_PROGRAM_TOKEN_RE` ni la
    deteccion de `cd` casan nunca contra ese token fundido [hallazgo
    Cerberus T1, 2026-08-06: con el modo plano, `_find_commit_creating_statement`
    devolvia `None` para el comando ENTERO -- el commit pasaba sin
    evaluacion alguna, ni rescate ni lectura de config.json]. Verificado
    en vivo que las comillas se siguen respetando igual en este modo
    (`'git commit -m "a;b"'` mantiene `;` DENTRO del token citado) y que
    sigue lanzando la misma `ValueError` ante comillas desbalanceadas que
    el modo plano -- mismo camino de fallback para quien la llama.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        tokens = list(lexer)
    except ValueError:
        return None
    return _split_statements(tokens)


def _find_commit_creating_statement(command):
    """Devuelve `(subcommand, tokens_tras_el_subcomando, stmt_index)`
    para la primera sentencia de `command` que invoca `commit`/`merge`/
    `rebase`/`cherry-pick` como subcomando REAL de git -- o `None` si
    ninguna sentencia lo hace. `stmt_index` es la posicion de esa
    sentencia dentro de la lista que produce `_shell_statements`
    [contrato nuevo, fase 2 del `cd`, 2026-08-06: `_resolve_effective_cwd`
    la usa para no aplicar un `cd` que llega DESPUES de la sentencia de
    commit -- ver su propio docstring]; `None` cuando `command` no
    tokeniza (fallback de abajo, sin sentencias que indexar). Deteccion
    PURA de forma: que se haga con cada subcomando (aprobar siempre,
    rechazar salvo `--abort`, seguir el camino de nota...) es decision de
    `_decide_commit_creating`, no de esta funcion -- la aduana "los ve
    pasar" aqui; decide que hacer con cada uno en la capa de decision
    [correccion del propietario, 2026-08-03: "ver pasar no es bloquear"].

    Fallback si `command` no tokeniza (comillas desbalanceadas): trata
    cualquier aparicion textual de git+<subcomando> como candidata --
    fail closed en cuanto a flags NO reconocidos (no se puede verificar
    ninguno con precision, y con la aduana encendida hay que evaluar, no
    aprobar a ciegas). Mismo fallback que
    `pre-validate-commit-trailers.py::_is_direct_git_commit` ya aplica.

    UNICA excepcion, deliberada [hallazgo Moriarty T1, 2026-08-06]: las
    banderas de RESCATE `--abort`/`--continue`/`--skip` SI se buscan en
    la cadena cruda con `_RESCUE_FLAG_RE` y se devuelven como tokens.
    Sin esto, un comando ordinario con un apostrofo sin escapar en el
    mensaje (p.ej. `git commit -m 'WIP: don't lose this' && git rebase
    --abort`) hace que `shlex` falle, el fallback devuelva `(sub, [])`,
    y `_decide_rescue_passthrough`/`_decide_commit_creating` nunca vean
    el `--abort` -- bloqueando la unica salida real de un rebase en
    conflicto, justo lo que "ASUNCIONES DE FIRMA" punto 1 del docstring
    del modulo dice que no debe pasar. No se amplia el fallback a
    ninguna otra bandera: solo estas tres, solo para que el passthrough
    de rescate las reconozca.

    Segunda mitad del mismo hallazgo: encontrar el token de rescate no
    basta si el bucle elige el subcomando EQUIVOCADO primero. El regex
    `\bgit\b.*\b{sub}\b` no ancla a una sentencia -- casa la cadena
    ENTERA, asi que para `git commit -m '...' && git rebase --abort`
    tanto "commit" como "rebase" casan a la vez, y `for sub in
    _COMMIT_CREATING_SUBCOMMANDS` (un `set`, orden no determinista con
    `PYTHONHASHSEED` sin fijar) puede devolver "commit" primero -- con
    `rest_tokens=['--abort']` bajo `sub="commit"` el rescate sigue sin
    reconocerse, porque el camino de `commit` solo mira `--amend`, nunca
    las banderas de rebase. Cuando el texto crudo SI contiene una de las
    tres banderas de rescate, se comprueban antes `rebase`/`merge`/
    `cherry-pick` -- los tres subcomandos donde esas banderas importan
    (`merge`/`cherry-pick` aprueban siempre igualmente; ver
    `_decide_rescue_passthrough`) -- antes que el resto, en vez de
    dejarlo al orden del `set`. Sin bandera de rescate en el texto, el
    orden no cambia: mismo comportamiento de siempre.
    """
    statements = _shell_statements(command)
    if statements is None:
        rescue_tokens = _RESCUE_FLAG_RE.findall(command)
        order = _COMMIT_CREATING_SUBCOMMANDS
        if rescue_tokens:
            order = ("rebase", "merge", "cherry-pick") + tuple(
                sub for sub in _COMMIT_CREATING_SUBCOMMANDS
                if sub not in ("rebase", "merge", "cherry-pick")
            )
        for sub in order:
            if re.search(rf"\bgit\b.*\b{re.escape(sub)}\b", command):
                return sub, rescue_tokens, None
        return None

    for stmt_index, statement in enumerate(statements):
        n = len(statement)
        for i, tok in enumerate(statement):
            if not _GIT_PROGRAM_TOKEN_RE.search(tok):
                continue
            j = i + 1
            while j < n and statement[j].startswith("-"):
                flag = statement[j]
                j += 1
                if flag in _GIT_VALUE_FLAGS and "=" not in flag and j < n:
                    j += 1
            if j >= n:
                continue
            sub = statement[j].lower()
            if sub not in _COMMIT_CREATING_SUBCOMMANDS:
                continue
            return sub, statement[j + 1:], stmt_index
    return None


_GIT_BASH_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)?$")


def _translate_git_bash_drive_path(target):
    """Traduce una ruta absoluta estilo Git Bash (`/c/Users/x`) a su forma
    nativa de Windows (`C:/Users/x`) -- SOLO llamarla en Windows
    (`os.name == "nt"`, comprobado por quien la llama, nunca aqui dentro).

    Git Bash en Windows escribe una ruta absoluta como `C:\\Users\\x` en su
    propio formato POSIX: `/c/Users/x` [hallazgo House, sin maquina Windows
    a mano, razonamiento verificado con `ntpath` importado en macOS --
    mismo modulo que usa Windows para `os.path` -- ver
    TestGitBashStyleAbsolutePathResolvesToTheRealTargetRepo en
    test_customs_hook.py]. `ntpath.isabs("/c/Users/x")` da `True` (empieza
    por `/`) SIN traducir el prefijo `/c/` a la unidad real -- la rama "ya
    es absoluta" de `_resolve_effective_cwd` la deja tal cual, y
    `ntpath.isdir("/c/Users/x")` busca una carpeta LITERAL `c` bajo la raiz
    de la unidad actual (normalmente no existe), asi que el `cd` se
    ignoraba en silencio y la aduana evaluaba el proyecto de la SESION en
    vez del de destino.

    Solo traduce el patron `/<letra-de-unidad>` o `/<letra>/resto` -- una
    letra de unidad es UNA SOLA letra seguida de `/` o de fin de cadena.
    `/c/Users/x` -> `C:/Users/x`; `/d/algo` -> `D:/algo`; `/casa/x` NO
    casa (la letra `c` esta seguida de `asa/x`, no de `/` ni de fin de
    cadena -- es una carpeta llamada "casa", no la unidad C) y se devuelve
    sin cambios. Una ruta ya nativa (`C:/Users/x`, no empieza por `/`)
    tampoco casa -- se devuelve sin cambios.

    Si el destino traducido no existe, el llamador ya cae al
    comportamiento de hoy (`cd` ignorado, `cwd` sin cambios) via el mismo
    chequeo `os.path.isdir` que ya tenia -- esta funcion no decide eso,
    solo traduce el FORMATO de la ruta.
    """
    match = _GIT_BASH_DRIVE_RE.match(target)
    if match is None:
        return target
    drive_letter, rest = match.group(1), match.group(2) or "/"
    return f"{drive_letter.upper()}:{rest}"


def _resolve_effective_cwd(command, base_cwd, limit_index=None):
    """Directorio EFECTIVO tras aplicar cada sentencia `cd` de `command`
    que llega ANTES de la sentencia de commit, en orden, empezando en
    `base_cwd` -- `hook_input['cwd']` si vino en el payload, si no
    `os.getcwd()` [contrato del `cd`, 2026-08-06: la aduana miraba el
    proyecto de la SESION en vez del del COMANDO real].

    `limit_index`, si no es `None`, es el `stmt_index` que devuelve
    `_find_commit_creating_statement` -- solo se consideran sentencias
    con indice MENOR (las que ya se ejecutaron cuando bash llega a la
    sentencia de commit); la sentencia de commit misma y cualquier `cd`
    POSTERIOR quedan fuera [fase 2 del contrato, hallazgo Cerberus
    2026-08-06: un `cd` que llega DESPUES del commit (p.ej. `cd proyecto
    && git commit -m x && cd ..`) no puede pisar el directorio que ya
    era vigente EN EL MOMENTO del commit -- lo unico que bash conocia al
    ejecutar esa sentencia]. `None` (el default) no limita -- usado solo
    cuando `_find_commit_creating_statement` tampoco pudo indexar
    sentencias (su propio `stmt_index` tambien es `None`, caso en el que
    `_shell_statements(command)` aqui abajo va a fallar identico y
    devolver `base_cwd` sin cambios de todas formas).

    Reutiliza `_shell_statements` [el UNICO tokenizador de shell del
    fichero, ver su docstring] -- una sentencia cuenta como `cd` cuando
    su PRIMER token es exactamente `"cd"`, nunca por contener la
    subcadena "cd" en cualquier parte (mismo principio anti-falso-positivo
    que ya aplica la deteccion de `git commit`/`git log`, ver
    `TestCommitDetectionHasNoFalsePositivesOnMereMentions` mas arriba: la
    palabra "cd" dentro del MENSAJE de un commit vive dentro de UN SOLO
    token de `shlex` -- nunca es el primer token de su propia sentencia).

    Cada `cd` encontrado se aplica sobre el `cwd` YA actualizado por el
    `cd` anterior (bash real: cuando la sentencia de commit se ejecuta,
    el shell esta en el directorio del ULTIMO `cd` anterior a ella, sea o
    no la primera sentencia de la cadena) -- por eso "encadenados manda
    el ultimo" y "un `cd` que no esta al principio tambien se aplica"
    salen gratis de la misma iteracion secuencial, sin caso especial para
    ninguno de los dos.

    Sin argumento (`cd` a secas) va al HOME real del proceso, igual que
    bash. `~` se expande con `os.path.expanduser` (lee el `HOME` real
    del proceso en el momento de la llamada, no en el import -- por eso
    el test de expansion de `~` que fuerza un `HOME` de prueba via `env`
    del subproceso funciona sin ningun cambio aqui). Una ruta relativa
    se resuelve contra el `cwd` corriente (el `base_cwd` para el primer
    `cd`, el resultado del `cd` anterior para los siguientes).

    Si el destino resuelto NO es un directorio real (ruta inexistente,
    o `command` no tokeniza en absoluto -- comillas desbalanceadas), esa
    sentencia `cd` se ignora y `cwd` no cambia -- cae al comportamiento
    de hoy para esa sentencia, nunca revienta sin capturar [mismo
    principio que ya fija el escape hatch de fichero corrupto: una ruta
    que no resuelve no puede tumbar la evaluacion].

    En Windows (`os.name == "nt"`), una ruta absoluta estilo Git Bash
    (`/c/Users/x`) se traduce a su forma nativa (`C:/Users/x`) ANTES de
    comprobar `os.path.isabs`/`os.path.isdir` -- ver
    `_translate_git_bash_drive_path`. Fuera de Windows no se traduce nada
    (`/c/Users/x` puede ser una ruta real y valida en Linux/macOS).
    """
    statements = _shell_statements(command)
    if statements is None:
        return base_cwd
    if limit_index is not None:
        statements = statements[:limit_index]

    cwd = base_cwd
    for statement in statements:
        if not statement or statement[0] != "cd":
            continue
        raw_target = statement[1] if len(statement) > 1 else "~"
        target = os.path.expanduser(raw_target)
        if os.name == "nt":
            target = _translate_git_bash_drive_path(target)
        candidate = target if os.path.isabs(target) else os.path.join(cwd, target)
        if os.path.isdir(candidate):
            cwd = os.path.normpath(candidate)
    return cwd


def _extract_dash_m_message(tokens):
    """El valor que sigue a `-m`/`--message`/`--message=...` -- primera
    aparicion, mismo mecanismo que asume
    `test_customs_hook.py` ("ASUNCIONES DE FIRMA" punto 2). `None` si no
    hay ninguno (heredoc, `-F fichero`, o simplemente ausente -- p.ej.
    un `--amend` que reutiliza el mensaje anterior).
    """
    for i, tok in enumerate(tokens):
        if tok in ("-m", "--message"):
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith("--message="):
            return tok[len("--message="):]
    return None


# ── Los dos rechazos nuevos -- ninguno existe en TEXTOS.md, redaccion
# propia con el mismo contrato de tres partes que los diez [Sec.7.4].
# Ver "ASUNCIONES DE FIRMA" punto 4 del docstring del modulo. ───────────


def _non_note_commit_rejection():
    """`git commit` corriente (sin `--amend`) cuyo mensaje no es wip, ni
    `⏩`, ni una nota reconocible -- rebota remitiendo a `gitmem work`
    [regla 5 del docstring del modulo, sin cambios por la correccion del
    2026-08-03].
    """
    what = (
        "esto crea un commit fuera de gitmem: un `git commit` cuyo "
        "mensaje no es una nota de memoria reconocible (ni una nota "
        "D/M/R/Q/X/I/B, ni wip, ni el cierre ⏩)"
    )
    options = (
        "La memoria es el registro de cada cosa que hacemos: con la aduana",
        "encendida, todo commit que use git directamente tiene que quedar",
        "registrado -- que se toco y a que issue iba",
        "[decision del propietario, 2026-08-03, PIEZAS.md Sec.11.1].",
        "",
        "Si esto es una nota de memoria (una decision, un memo, una",
        "restriccion...) usa `gitmem note`. Si es trabajo de codigo, usa",
        "`gitmem work`.",
    )
    command = (
        'gitmem work "<mensaje>" --path <ruta1> [--path <ruta2> ...] [--issue N]',
    )
    return rejection_.build(
        kind="non_note_commit", what=what, options=options, command=command
    )


def _history_rewrite_rejection(subcommand):
    """`git commit --amend` o `git rebase` (salvo `--abort`) -- los dos
    reescriben commits que ya estan en la historia, violando P1 ("nada se
    borra ni se reescribe jamas. Toda correccion es un commit nuevo").
    Familia DISTINTA de `_non_note_commit_rejection`: el motivo no es
    "esto no es una nota", es "esto reescribe historia" -- el usuario
    tiene que leer POR QUE no puede hacerlo, no solo que use otro comando
    [correccion del propietario, 2026-08-03].
    """
    if subcommand == "commit":
        what = "esto reescribe un commit ya existente: `git commit --amend`"
        relaunch = (
            'gitmem note <TIPO> --zones <zona1> <zona2> "..." --replaces <ID>'
            "  # si es una nota que hay que corregir",
            'gitmem work "<mensaje>" --path <ruta1> [--path <ruta2> ...]'
            "  # si es codigo: arreglalo en un commit nuevo",
        )
    else:
        what = "esto reescribe historia en lote: `git rebase`"
        relaunch = (
            'git merge --squash <rama> && gitmem work "<mensaje>" '
            "--path <ruta1> [--path <ruta2> ...]",
        )

    options = (
        "P1: nada se borra ni se reescribe jamas. Toda correccion es un",
        "commit nuevo (sustitucion, cierre, alta) -- nunca una reescritura",
        "de lo que ya esta en la historia.",
        "",
        "Si el motivo es limpiar la rama antes de mostrarla, ese uso ya",
        "tiene mecanismo propio: el squash al fusionar [spec Sec.10.4].",
        "Deja los commits como estan y haz squash al hacer merge.",
    )
    return rejection_.build(
        kind="history_rewrite", what=what, options=options, command=relaunch
    )


def _corrupt_file_rejection(filename, exc):
    """`.claude/project-memory/config.json` o `zones.json` no es JSON
    valido -- p.ej. un merge o un rebase que se dejo a medias con
    marcadores de conflicto sin resolver dentro. Antes de esto, el
    `except Exception` generico de `main()` bloqueaba con el volcado
    crudo de la excepcion -- sin decir como repararlo -- para CUALQUIER
    sentencia detectada como creadora de commit, incluidos los cuatro
    comandos de RESCATE (`git merge`/`git rebase` `--abort`/`--continue`)
    que son la unica salida real de un merge/rebase en conflicto.

    Decision del propietario ("bloquear con salida clara", hallazgo
    reportado 2026-08-06): un commit normal SIGUE bloqueado (no hay
    bandera fiable que leer de un fichero roto), pero el `reason` tiene
    que decir COMO repararlo, no solo nombrarlo -- mismo contrato de tres
    partes que los demas rechazos sin plantilla en TEXTOS.md [Sec.7.4,
    ver "ASUNCIONES DE FIRMA" punto 4 del docstring del modulo]. Los
    cuatro comandos de rescate ya no llegan aqui en absoluto -- ver
    `_decide_rescue_passthrough`, que los aprueba ANTES de tocar
    config.json/zones.json.
    """
    what = (
        f"`.claude/project-memory/{filename}` no se puede leer o no es "
        f"valido ({exc})"
    )
    options = (
        "Revisa el fichero a mano -- la causa mas probable es un merge o",
        "un rebase que se dejo a medias con marcadores de conflicto sin",
        "resolver dentro (`<<<<<<<` / `=======` / `>>>>>>>`). Corrige o",
        "edita el contenido hasta que vuelva a ser JSON valido y",
        "reintenta el commit.",
    )
    command = (
        f"# edita .claude/project-memory/{filename} a mano y valida que sea JSON",
    )
    return rejection_.build(
        kind="corrupt_memory_file", what=what, options=options, command=command
    )


# ── Interruptor de la aduana -- DEUDA.md B19 punto 2. `config.py` solo
# carga tres ajustes de UN fichero [Sec.6.3, "Que NO hace"]: decidir si
# el proyecto YA tiene memoria propia es responsabilidad de este hook,
# su unico consumidor, no de `config.py`. Reutiliza `indexes.read`/
# `read_archive` (ya en produccion, Sec.7.3) -- nunca lee los ficheros a
# mano ni escanea git log: un indice que no existe todavia (`seed()` no
# corrio) es "cero notas", el mismo criterio que "sin fichero" en
# `config.py`. ───────────────────────────────────────────────────────


def _project_has_notes(pm):
    """`True` en cuanto `.claude/project-memory/` tiene al menos una nota
    -- vigente en cualquiera de los siete indices, o archivada. Un
    proyecto recien instalado (directorio ausente, o los ocho ficheros
    sembrados y vacios) devuelve `False`, que es exactamente el estado
    en el que la aduana tenia que nacer apagada por el motivo original
    (no bloquear al sistema viejo el primer dia).
    """
    if not pm.exists():
        return False

    for name in vocabulary.TYPE_INDEX_FILES.values():
        try:
            if indexes.read(name, pm):
                return True
        except FileNotFoundError:
            continue

    try:
        if indexes.read_archive(pm):
            return True
    except FileNotFoundError:
        pass

    return False


def _customs_active(cfg, pm):
    """El valor EFECTIVO de la aduana -- no `cfg.customs_enabled` a
    secas. Un ajuste explicito en `config.json` (`true` o `false`)
    manda siempre; sin ajuste (`None`, el default nuevo de `Config`), se
    enciende sola en cuanto el proyecto tiene su primera nota [DEUDA.md
    B19 punto 2].
    """
    if cfg.customs_enabled is not None:
        return cfg.customs_enabled
    return _project_has_notes(pm)


def _decide_rescue_passthrough(subcommand, rest_tokens):
    """Aprueba SIEMPRE, sin tocar config.json/zones.json -- solo para los
    casos en los que la decision final es identica este la aduana activa
    o no [ver `_decide_commit_creating`: `merge`/`cherry-pick` aprueban
    siempre; `rebase` con `--abort`/`--continue`/`--skip` tambien].
    `None` para cualquier otro caso -- ese SI depende de si la aduana
    esta activa (p.ej. `rebase` sin esas banderas, o un `commit` corriente
    aprueban con la aduana apagada y bloquean con ella encendida), asi que
    sigue gated detras de `config.load`/`_customs_active`, sin cambio de
    comportamiento.

    Comprobado ANTES de leer ningun fichero [hallazgo reportado,
    2026-08-06]: con `config.json` corrupto, `config.load()` lanzaba
    incondicionalmente para CUALQUIER subcomando, asi que su excepcion
    bloqueaba tambien los cuatro comandos de RESCATE
    (`git merge`/`git rebase` `--abort`/`--continue`) que son la unica
    salida real de un merge/rebase en conflicto -- dejando al usuario
    atascado. Como el resultado para estos casos no depende de ningun
    fichero, resolverlos antes de leer ninguno es un cambio de orden, no
    de comportamiento.
    """
    if subcommand in ("merge", "cherry-pick"):
        return {"decision": "approve"}
    if subcommand == "rebase" and _REBASE_PASSTHROUGH_FLAGS.intersection(rest_tokens):
        return {"decision": "approve"}
    return None


# ── Decision -- separada de la lectura/escritura de stdin/stdout, y
# partida en piezas pequeñas [regla de 50 LOC por funcion]. ─────────────


def _decide_note(note, pm, cfg):
    """El commit trae un mensaje que SI parsea como `Note` -- se valida
    con el Context real del repositorio [ver "ASUNCIONES DE FIRMA"
    punto 6]."""
    try:
        zones_map = zones_lib.load(pm / "zones.json")
    except Exception as exc:
        reason = rejection_.render_hook_block(_corrupt_file_rejection("zones.json", exc))
        return {"decision": "block", "reason": reason}
    archived = indexes.archived_ids(pm)
    existing_in_zone = tuple(
        n for n in query.by_zone(note.zone1, note.zone2) if n.id not in archived
    )
    known_ids = frozenset(n.id for n in query.by_zone(None, None))
    ctx = validator.Context(
        zones=zones_map,
        existing_in_zone=existing_in_zone,
        known_ids=known_ids,
        config=cfg,
    )
    rejections = validator.validate_note(note, ctx)
    if not rejections:
        return {"decision": "approve"}
    reason = "\n\n".join(rejection_.render_hook_block(r) for r in rejections)
    return {"decision": "block", "reason": reason}


def _decide_commit_creating(subcommand, rest_tokens, pm, cfg):
    """La aduana encendida, sobre una sentencia que SI crea un commit --
    parte en dos segun P1 [correccion del propietario, 2026-08-03, tabla
    del docstring del modulo]: `merge`/`cherry-pick` SIEMPRE aprueban
    (añaden a la historia, no la reescriben); `rebase` (salvo `--abort`)
    y `commit --amend` SIEMPRE rechazan (reescriben); un `commit`
    corriente sigue el camino de siempre -- wip/`⏩` pasan sin pregunta,
    una nota real se valida, cualquier otra cosa rebota a `gitmem work`.
    """
    if subcommand in ("merge", "cherry-pick"):
        return {"decision": "approve"}

    if subcommand == "rebase":
        if _REBASE_PASSTHROUGH_FLAGS.intersection(rest_tokens):
            return {"decision": "approve"}
        reason = rejection_.render_hook_block(_history_rewrite_rejection("rebase"))
        return {"decision": "block", "reason": reason}

    # subcommand == "commit"
    if "--amend" in rest_tokens:
        reason = rejection_.render_hook_block(_history_rewrite_rejection("commit"))
        return {"decision": "block", "reason": reason}

    message = _extract_dash_m_message(rest_tokens)
    if message is not None:
        if validator.is_wip(message):
            return {"decision": "approve"}
        if format.parse_context_message(message) is not None:
            return {"decision": "approve"}
        note = format.parse_message(message)
        if note is not None:
            return _decide_note(note, pm, cfg)

    reason = rejection_.render_hook_block(_non_note_commit_rejection())
    return {"decision": "block", "reason": reason}


def _decide(hook_input):
    """Toda la logica de decision sobre un payload YA parseado -- devuelve
    el dict JSON que `main()` imprime tal cual. Separado de `main()` para
    que la lectura de stdin/escritura de stdout no se mezcle con la
    decision [regla de 50 LOC por funcion].
    """
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input") or {}
    if tool_name != "Bash":
        return {"decision": "approve"}

    command = tool_input.get("command", "")
    if not command:
        return {"decision": "approve"}

    found = _find_commit_creating_statement(command)
    if found is None:
        return {"decision": "approve"}
    subcommand, rest_tokens, stmt_index = found

    passthrough = _decide_rescue_passthrough(subcommand, rest_tokens)
    if passthrough is not None:
        return passthrough

    # cwd base: prefiere un `cwd` explicito del payload del hook (no lo
    # manda Claude Code hoy, pero se comprueba a la defensiva -- mismo
    # patron que hooks/pre-merge-gate.py); si no, el cwd heredado del
    # proceso -- comportamiento SIN CAMBIOS respecto a antes de este
    # contrato. Un `cd <ruta>` dentro de `command` QUE LLEGA ANTES de la
    # sentencia de commit (al principio, encadenado, o no al principio)
    # desplaza el directorio EFECTIVO desde esa base -- bash ya esta ahi
    # para cuando se ejecuta la sentencia que crea el commit real
    # [contrato del `cd`, 2026-08-06 -- antes de esto la aduana evaluaba
    # siempre contra el proyecto de la SESION, nunca el del COMANDO]. Un
    # `cd` que llega DESPUES de esa sentencia (`stmt_index`) NO se aplica
    # -- ese es el directorio a donde bash se movio TRAS commitear, ya
    # sin relacion con el commit que se acaba de crear [fase 2, hallazgo
    # Cerberus 2026-08-06].
    session_cwd = hook_input.get("cwd") or os.getcwd()
    cwd = _resolve_effective_cwd(command, session_cwd, limit_index=stmt_index)

    try:
        root = gitcmd.repo_root(Path(cwd))
    except RuntimeError:
        # No hay repositorio git de verdad en `cwd` -- git mismo va a
        # rechazar el comando por su cuenta; no es responsabilidad de
        # esta pieza suplir ese diagnostico.
        return {"decision": "approve"}

    pm = root / ".claude" / "project-memory"
    try:
        cfg = config.load(pm / "config.json")
    except Exception as exc:
        reason = rejection_.render_hook_block(_corrupt_file_rejection("config.json", exc))
        return {"decision": "block", "reason": reason}

    if not _customs_active(cfg, pm):
        return {"decision": "approve"}

    return _decide_commit_creating(subcommand, rest_tokens, pm, cfg)


def main():
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        try:
            hook_input = json.loads(raw) if raw.strip() else {}
        except ValueError:
            hook_input = {}
        result = _decide(hook_input)
    except Exception as exc:
        result = {
            "decision": "block",
            "reason": f"customs.py: fallo inesperado, bloqueando por seguridad: {exc}",
        }

    try:
        json.dump(result, sys.stdout)
        sys.stdout.flush()
    except Exception:
        pass


if __name__ == "__main__":
    main()
