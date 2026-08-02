"""Fixtures y helpers compartidos para los tests de unmassk-memory (v2).

Paso 0.3 de FASE 0 (ver docs/memoria-v2/PLAN-CONSTRUCCION.md): "un repo
git temporal, helpers para dar de alta notas y aserciones de indice. De
momento solo lo que haga falta para que un test tonto pase; los helpers
de nota se completan en la fase 2."

Escrito desde cero -- no reutiliza ninguna linea de
unmassk-toolkit/tests/conftest.py (restriccion A del plan: "desde cero,
sin reutilizar nada del v1"). Del v1 se hereda la leccion medida (que
forma tiene un fixture de repo temporal que funciona), nunca el codigo.

Regla transversal del plan: los nombres que ve una maquina (funciones,
fixtures, ficheros) van en ingles; los comentarios y docstrings, en
espanol.
"""

import os
import subprocess

import pytest


def run_git(args, cwd):
    """Ejecuta un comando git en `cwd` y devuelve (returncode, stdout, stderr).

    No fusiona ni sobreescribe variables de entorno: la identidad git de
    esta maquina ya esta configurada globalmente (user.name/user.email
    en ~/.gitconfig, verificado antes de escribir este fixture), asi que
    `git commit` la resuelve sin ayuda. Si algun dia estos tests corren
    en un runner sin identidad global (CI limpio), `git commit` fallara
    aqui con returncode != 0 de forma ruidosa -- ese es el momento de
    anadir un fallback explicito de identidad (mismo patron que el v1
    documenta en su propio conftest.py), no antes: anticipar esa
    infraestructura sin haber visto el fallo real es exactamente el tipo
    de pieza que el plan pide no copiar sin necesidad.
    """
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


@pytest.fixture
def tmp_repo(tmp_path):
    """Crea un repo git temporal con un commit inicial vacio y devuelve su ruta.

    Usa `tmp_path` (fixture nativa de pytest, un directorio unico por
    test que pytest limpia solo) en vez de gestionar un directorio
    temporal a mano.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    repo_path = str(repo)

    rc_init, _out_init, err_init = run_git(["init"], repo_path)
    assert rc_init == 0, f"git init fallo en el fixture tmp_repo: {err_init}"

    rc_commit, _out_commit, err_commit = run_git(
        ["commit", "--allow-empty", "-m", "init"], repo_path
    )
    assert rc_commit == 0, (
        f"git commit inicial fallo en el fixture tmp_repo: {err_commit}"
    )

    return repo_path


def register_note(repo, note_type, **fields):
    """Da de alta una nota de memoria (tipo + campos) en `repo`.

    ESQUELETO INTENCIONADO -- no una implementacion a medias ni un TODO
    abandonado. El propio plan (paso 0.3) dice textualmente: "los
    helpers de nota se completan en la fase 2". Ahora mismo no existen
    `lib/notes.py` (paso 2.4 -- la transaccion validar -> indice ->
    commit) ni `lib/ids.py` (paso 2.3 -- el contador de IDs por tipo),
    asi que cualquier cuerpo real aqui inventaria esa logica en vez de
    reutilizarla, justo lo que la restriccion D del plan prohibe ("el
    validador/generador es una sola pieza").

    Ningun test de la FASE 0 debe llamar a esta funcion todavia -- por
    eso lanza NotImplementedError en vez de simular un commit: un
    esqueleto que devuelve silenciosamente un resultado inventado seria
    peor que uno que grita que aun no existe.

    Cuando llegue la fase 2, este cuerpo pasa a invocar la funcion real
    de `lib/notes.py` (el nombre exacto lo fija el paso 2.4) y devuelve
    lo que esa funcion devuelva -- sin reimplementar aqui validacion,
    generacion de indice ni commit.
    """
    raise NotImplementedError(
        "register_note() se completa en la fase 2 (paso 2.4, lib/notes.py, "
        "y paso 2.3, lib/ids.py -- ver PLAN-CONSTRUCCION.md). Ningun test "
        "de la fase 0 debe depender de este helper todavia."
    )


def assert_index_contains(repo, index_name, note_id):
    """Comprueba que el fichero de indice `index_name` de `repo` contiene la linea de `note_id`.

    ESQUELETO INTENCIONADO, misma razon que `register_note()` arriba:
    `lib/indexes.py` (paso 2.2 -- sembrar, insertar, retirar, archivar,
    recuentos de los ocho ficheros de indice) todavia no existe. El
    formato de la linea de indice tampoco (`lib/format.py`, paso 1.5) --
    reimplementarlo aqui a mano duplicaria una verdad que el plan exige
    que viva en una sola pieza.

    Lanza NotImplementedError en vez de leer el fichero a ciegas y
    comparar contra una linea inventada a mano: eso seria fabricar el
    resultado esperado en vez de derivarlo del formato real (la misma
    regla que rige los round-trips de §34 en unmassk-standards).

    Cuando llegue la fase 2, este cuerpo pasa a leer el fichero de
    indice real (via `lib/indexes.py`) y comprobar la presencia de la
    linea que `lib/format.py` genero para `note_id`.
    """
    raise NotImplementedError(
        "assert_index_contains() se completa en la fase 2 (paso 2.2, "
        "lib/indexes.py, y paso 1.5, lib/format.py -- ver "
        "PLAN-CONSTRUCCION.md). Ningun test de la fase 0 debe depender de "
        "este helper todavia."
    )
