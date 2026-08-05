"""Rechazar un commit directo sobre la rama principal de un repositorio
protegido -- compartido por `bin/memory/work.py` y `bin/memory/wip.py`
[PIEZAS.md Sec.10.1, punto 3; decision del propietario, 2026-08-03: "el
checkpoint protege la rama principal, con la misma proteccion que
work.py" -- un checkpoint en la rama principal ES un commit en la rama
principal, y da igual que sea rapido].

Vivia SOLO dentro de `work.py` [ya en produccion desde 2026-08-02] --
logica de negocio metida en un guion, en pequeño incumplimiento de la
regla de PIEZAS.md Sec.10 ("un script... llama a UNA funcion de la
libreria... toda la logica esta debajo"). Se traslada aqui, SIN CAMBIAR
NI UNA LINEA de comportamiento ni el texto del rechazo, para que
`wip.py` pueda pedir la MISMA proteccion sin copiarla -- dos copias del
mismo control de seguridad es exactamente el patron que este sistema
existe para evitar [mismo principio que ``vocabulary.SIMILARITY_
THRESHOLD``, que vivia duplicado en `validator.py` y `rules.py` hasta
que se consolido en una sola constante].

"La rama principal": ningun texto de esta rama fija que nombre de rama
cuenta -- ASUNCION heredada tal cual de `work.py`: la lista fija
`main`/`master` (`git init` crea `main` por defecto en esta maquina,
verificado).

Que NO hace. No decide SI se llama -- eso lo decide cada script que lo
importa. `work.py` lo llama siempre; `wip.py` NO lo llamaba hasta esta
tarea, por diseño explicito -- el checkpoint nace "sin friccion de
preguntas de la aduana" [spec], pero eso NO es lo mismo que "sin
proteccion de rama", que es otro control, gobernado por
`config.repo_type` (fail-closed: protegido si no se declara). No lee
`config.json` por su cuenta -- lo recibe ya cargado (`Config`), para no
repetir la resolucion de `pm_root`/`config.load` en cada llamador.
"""

import gitcmd

# repo_type protegido -- mismo valor que el default fail-closed de
# config.Config [config.py::Config.repo_type docstring: "main protegido
# si no se declara"].
PROTECTED_REPO_TYPE = "gitflow"

# Nombres de rama que cuentan como "la rama principal" -- ver docstring
# del modulo: sin remoto del que preguntar, lista fija.
MAIN_BRANCH_NAMES = frozenset({"main", "master"})


def current_branch(root):
    """Rama actual del repositorio en `root`. Lanza `RuntimeError` con el
    stderr real de git si no se puede determinar -- mismo principio que
    `gitcmd.repo_root` ya aplica, nunca una cadena vacia en silencio.
    """
    result = gitcmd.run(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
    )
    if result.returncode != 0:
        raise RuntimeError(f"no se pudo leer la rama actual: {result.stderr}")
    return result.stdout.strip()


def protected_branch_rejection(branch, config_path=None):
    """Texto del rechazo: que ha pasado y que hacer [Sec.7.4]. Redaccion
    propia -- ningun documento la fija letra por letra. Texto identico
    al que `work.py` ya usaba antes de este traslado -- "reutiliza el
    texto que work.py ya tiene, no escribas uno nuevo" [encargo de esta
    tarea].

    [corregido 2026-08-04, encargo del propietario]: el rechazo decia
    "declaralo en config.json" y ahi dejaba a quien lo leyera -- probado
    en un proyecto recien creado, ese fichero NO EXISTE (ni
    `config.load()` ni ningun script de `bin/memory/` lo escribe jamas)
    y el mensaje no decia ni la ruta, ni el contenido, ni si tocaba
    crear o editar. `config_path` es la ruta YA RESUELTA por el llamador
    (`notes.pm_root(root) / "config.json"`, la misma que `config.load()`
    usa de verdad) -- esta funcion no la inventa ni la recalcula, sigue
    sin leer `config.json` por su cuenta [ver docstring del modulo].
    Opcional (`None` por defecto) para no romper la llamada directa de
    `test_rejection_text_matches_the_real_repo_guard_output_verbatim`
    (`tests/memory/test_wip_script.py`), que compara por SUBCADENA contra
    la salida real de `wip.py` -- por eso el texto generico de abajo se
    mantiene byte a byte igual que antes de esta correccion cuando no se
    pasa ruta, y el bloque nuevo solo se ANADE AL FINAL, nunca se inserta
    en medio: asi el texto viejo sigue siendo una subcadena literal del
    nuevo.
    """
    text = (
        f"❌ commit de trabajo rechazado: repo_type=\"{PROTECTED_REPO_TYPE}\" "
        f"(protegido) y la rama actual (\"{branch}\") es la rama principal.\n"
        "Que hacer: crea una rama de trabajo y commitea ahi "
        "(`git checkout -b <rama>`); o si este repositorio de verdad "
        "despliega directo desde su rama principal, declaralo en "
        "config.json con \"repo_type\": \"trunk\" (o el que corresponda "
        "distinto de \"gitflow\")."
    )
    if config_path is None:
        return text

    if config_path.exists():
        detail = (
            f"\nLa ruta exacta de ese fichero en este repositorio: "
            f"{config_path}\nYa existe -- anade (o cambia) ahi la clave "
            "\"repo_type\": \"trunk\" sin tocar el resto de sus ajustes "
            "(por ejemplo \"customs_enabled\" o \"test_command\", si ya "
            "los tiene)."
        )
    else:
        detail = (
            f"\nLa ruta exacta de ese fichero en este repositorio: "
            f"{config_path}\nNo existe todavia -- crealo con este "
            "contenido:\n"
            "  {\"repo_type\": \"trunk\"}"
        )
    return text + detail
