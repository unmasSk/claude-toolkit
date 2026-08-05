"""Contrato ROJO de `hooks/boot_launcher.py` -- PIEZAS.md Sec.11 (fila
`boot_launcher.py`).

`hooks/boot_launcher.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo (ese llega en el endurecimiento,
paso 5 de la secuencia de capa, PIEZAS.md Sec.12bis).

Evento `SessionStart`. La ficha lo describe entero en una linea: "~20
lineas sin logica: llama a `bin/memory/boot.py`" -- y le pone una regla
aparte: se escribe una vez y no se itera jamas, porque un hook corre desde
la copia instalada del plugin (publicar version + actualizar + reiniciar
para cambiar una sola linea). No hay filas de PIEZAS.md Sec.11 asignadas a
este hook especificamente (esa tabla cubre los tres hooks juntos); el
contrato de este fichero se deriva de esa unica linea + de lo que ya existe
en produccion:

- `bin/memory/boot.py` (PIEZAS.md Sec.10, fila `boot.py`): "no admite
  argumentos, imprime el menu del dia" -- ya en verde, probado por proceso
  en `test_boot_script.py`. `boot_launcher.py` es SU llamador: el hook no
  reimplementa nada de lo que ese script ya hace, solo lo invoca.
- `TEXTOS.md` Sec.3.2 ("Proyecto recien instalado"): el texto que tiene que
  salir en un proyecto sin `.claude/project-memory/` -- ya lo produce
  `boot.build()`/`boot.render()` (verificado en produccion: "BLOQUEANTES
  ......  C E R O" para un repo recien creado). El hook no anade ni recorta
  nada de eso.
- Encargo explicito de esta tarea (punto 2): "que no reviente en un
  proyecto recien instalado -- esto ya tumbo el arranque dos veces en esta
  obra, y lo primero que veia el usuario era un error de Python".
- Encargo explicito (punto 3): "que un fallo del arranque no impida
  trabajar -- si `boot.py` falla, la sesion tiene que empezar igual". Mismo
  principio que ya declara `hooks/session-start-boot.py` (el SessionStart
  del sistema viejo, vivo en esta rama): "Exit codes: 0: Always (never
  blocks session start)".

Round trip real, sin fabricar el texto esperado (unmassk-standards Sec.34):
el texto exacto que el hook tiene que imprimir sale de invocar `boot.py`
POR SEPARADO, como proceso, contra el mismo repositorio (`run_memory_script`,
`conftest.py`, ya en verde) -- dos caminos escritos aparte que tienen que
coincidir. Se normaliza unicamente la etiqueta ` UTC` (cada invocacion usa
`datetime.now()` por separado, igual que en `test_boot_script.py`).

Payload REAL, no inventado: `make_session_start_payload()` (`conftest.py`)
esta construido a partir de la referencia oficial de esquemas de hook de
Claude Code (`hook-development/references/hook-input-schemas.md`, skill
`plugin-dev` instalada en esta maquina) -- campos comunes a todo hook
(`session_id`, `transcript_path`, `cwd`, `permission_mode`,
`hook_event_name`) mas los propios de `SessionStart` (`source`, `model`).
`hooks/session-start-boot.py` (mencionado en el encargo como referencia) NO
SIRVE como fuente de la forma del payload: no lee stdin en absoluto,
resuelve todo por `git` contra el cwd del proceso -- lo que confirma, de
paso, que un hook de este toolkit puede legitimamente no necesitar ningun
campo del payload para funcionar.

Tecnica para evitar afirmar una decision interna del hook (regla de esta
obra: "un test entra solo si compara dos cosas escritas por separado"; y
"si un test tuyo necesita afirmar una decision tomada dentro del lanzador,
es que hay logica que no deberia estar ahi"): NINGUN documento dice si el
hook resuelve el repositorio por `payload["cwd"]` o por el cwd heredado del
proceso -- las dos son plausibles (`hooks/pre-merge-gate.py` ya usa el
primer patron: "prefer an explicit cwd in the hook payload... fall back to
the hook process's own working directory"). Cada test de este fichero fija
el cwd del PROCESO DEL HOOK y `payload["cwd"]` al MISMO valor a proposito,
para que el resultado no depende de cual de los dos gane -- ver
`run_hook_with_payload()` en `conftest.py`.

Con el hook inexistente, todos estos tests fallan hoy por la misma causa
real: `python3 <ruta inexistente>` -- ver docstring de `run_memory_script`
en `conftest.py` para el detalle del mensaje.
"""

import contextlib
import os
import re

import pytest

from .conftest import (
    import_lib_memory_module,
    make_session_start_payload,
    run_git,
    run_hook_raw_stdin,
    run_hook_with_payload,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)

_UTC_LABEL_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")

HOOK_NAME = "boot_launcher.py"


def _normalize_timestamps(text):
    return _UTC_LABEL_RE.sub("<UTC>", text)


@pytest.fixture
def boot_lib():
    return import_lib_memory_module("boot")


@contextlib.contextmanager
def _cwd(path):
    """Mismo helper que en `test_boot_script.py`/`test_notes.py`."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _build_expected(repo, boot_lib):
    """El texto REAL que `boot.py` produce para `repo` -- llamando a las
    piezas de produccion (`boot.build`/`boot.render`) en el MISMO proceso
    de test, nunca fabricado a mano. Segundo camino, independiente del
    proceso del hook, para el round trip de Sec.34.
    """
    with _cwd(repo):
        return boot_lib.render(boot_lib.build())


def _report_of(repo):
    """El informe REAL que dejo `boot.py`: desde 2026-08-05 el arranque
    escribe un fichero y por pantalla solo deja donde esta [decision del
    propietario: "no se le puede inyectar, se tiene que crear el archivo
    y el lo lee"]. Comparar contra su stdout compararia contra el
    puntero, no contra el informe."""
    from pathlib import Path

    return Path(repo, ".claude", ".unmassk", "boot-latest.txt").read_text(
        encoding="utf-8"
    )


class TestLauncherReproducesRealBootOutput:
    """Contrato: PIEZAS.md Sec.11 fila `boot_launcher.py` -- "llama a
    `bin/memory/boot.py`". El test que de verdad importa: la salida del
    hook, comparada contra la salida de `boot.py` invocado por separado
    como proceso -- dos caminos escritos aparte."""

    def test_matches_boot_py_on_freshly_installed_project(self, tmp_repo, boot_lib):
        """Repo con un commit inicial, sin `.claude/project-memory/` en
        absoluto -- el caso "recien instalado" de TEXTOS.md Sec.3.2."""
        payload = make_session_start_payload(tmp_repo)
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected), (
            "boot_launcher.py no reproduce byte a byte lo que boot.py "
            "produce por separado contra el mismo repositorio -- ¿el hook "
            "reimplementa algo, o recorta la salida?"
        )

    def test_matches_boot_py_on_unborn_branch(self, tmp_path, boot_lib):
        """El caso MAS extremo de "recien instalado": `git init` sin un
        solo commit todavia -- ni siquiera el inicial que trae `tmp_repo`.
        Prueba directa de `is_unborn_branch` (`query.py`) a traves del
        hook, no solo del script (ya cubierto en `test_boot_script.py`)."""
        repo = tmp_path / "unborn"
        repo.mkdir()
        rc_init, _out_init, err_init = run_git(["init"], str(repo))
        assert rc_init == 0, f"git init fallo en el test: {err_init}"

        payload = make_session_start_payload(str(repo))
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=str(repo))
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        expected = _build_expected(str(repo), boot_lib)
        assert _normalize_timestamps(_report_of(str(repo)).rstrip("\n")) == _normalize_timestamps(expected)

    def test_matches_boot_py_with_real_content(self, tmp_repo, boot_lib):
        """Con contenido real (un bloqueante, una restriccion, un cierre de
        contexto) -- mismo round trip, contra un proyecto que ya no esta
        vacio. Si el hook recortara o reordenara algo, dejaria de coincidir
        con `boot.render(boot.build())`, que no recorta nada."""
        seed_zones_json(tmp_repo, ["auth", "product", "deploy", "infra"])
        rc_b, out_b, err_b = seed_note_via_script(
            tmp_repo, "B", "product", "auth",
            "google workspace admin consent still pending",
            description="MARK description", awaits="el cliente (Marta, IT)",
        )
        assert rc_b == 0, f"siembra fallo: stdout={out_b!r} stderr={err_b!r}"

        rc_r, out_r, err_r = seed_note_via_script(
            tmp_repo, "R", "deploy", "infra",
            "no auth deploy on Friday without a tested rollback",
            why="viernes sin vuelta atras ensayada", description="MARK description",
            stops="yes",
        )
        assert rc_r == 0, f"siembra fallo: stdout={out_r!r} stderr={err_r!r}"

        rc_ctx, out_ctx, err_ctx = run_memory_script(
            "next.py",
            [
                "implement discussed changes to close-session skill",
                "--context", "Revisado el diseno del checkpoint",
            ],
            cwd=tmp_repo,
        )
        assert rc_ctx == 0, f"cierre de contexto fallo: stdout={out_ctx!r} stderr={err_ctx!r}"

        payload = make_session_start_payload(tmp_repo)
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected)

    def test_launcher_adds_no_wrapper_text_beyond_boot_py_output(self, tmp_repo):
        """Contrato explicito de la ficha: "~20 lineas SIN LOGICA". Ningun
        prefijo/banner propio del hook (al estilo `[crew] ...` de
        `session-start-crew.py`, que SI tiene logica propia) deberia
        aparecer nunca en su salida -- solo lo que `boot.py` produjo. La
        igualdad exacta de los tests de arriba ya lo prueba; este test lo
        deja dicho como su propia aserta, por si algun dia esa igualdad se
        relaja a un `in` y esta garantia se pierde sin que nadie lo note."""
        payload = make_session_start_payload(tmp_repo)
        rc, out, _err = run_hook_with_payload(HOOK_NAME, payload, cwd=tmp_repo)
        assert rc == 0
        assert "[boot_launcher]" not in out
        assert "boot_launcher.py:" not in out

    def test_matches_boot_py_when_launched_from_a_nested_subdirectory(self, tmp_repo, boot_lib):
        """`boot.build()` resuelve `root` con `git rev-parse
        --show-toplevel` -- funciona igual lanzado desde una subcarpeta
        anidada del repo. Prueba que el hook no rompe eso pasando algun
        cwd distinto por su cuenta."""
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)

        payload = make_session_start_payload(nested)
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=nested)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        expected = _build_expected(tmp_repo, boot_lib)
        assert _normalize_timestamps(_report_of(tmp_repo).rstrip("\n")) == _normalize_timestamps(expected), (
            "el arranque no coincide con el del repo -- ¿el hook resuelve "
            "por una ruta fija en vez de por el repositorio real?"
        )


class TestFreshlyInstalledProjectDoesNotCrash:
    """Encargo explicito, punto 2: "esto ya tumbo el arranque dos veces en
    esta obra, y lo primero que veia el usuario era un error de Python".
    Solapa en mecanica con el grupo de arriba (mismos repos), pero declara
    su propia razon de ser: si algun dia el round trip se retira, esta
    garantia de "nunca revienta" tiene que seguir en pie por si sola."""

    def test_no_traceback_and_exit_zero_on_project_with_one_commit_and_no_memory(self, tmp_repo):
        payload = make_session_start_payload(tmp_repo)
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

    def test_no_traceback_and_exit_zero_on_zero_commit_repo(self, tmp_path):
        repo = tmp_path / "unborn2"
        repo.mkdir()
        rc_init, _out_init, err_init = run_git(["init"], str(repo))
        assert rc_init == 0, f"git init fallo en el test: {err_init}"

        payload = make_session_start_payload(str(repo))
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=str(repo))
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestBootFailureNeverBlocksSession:
    """Encargo explicito, punto 3: "un fallo del arranque no impide
    trabajar. Si `boot.py` falla, la sesion tiene que empezar igual. La
    memoria ayuda, nunca bloquea." Mismo principio que ya declara
    `hooks/session-start-boot.py`: "Exit codes: 0: Always (never blocks
    session start)".

    El fallo de `boot.py` usado aqui es REAL, no simulado: fuera de un
    repositorio git, `git rev-parse --show-toplevel` falla de verdad, y
    `bin/memory/boot.py` ya lo captura y sale con returncode 1 (verificado
    en vivo antes de escribir este contrato: "boot.py: git rev-parse
    --show-toplevel fallo en ...: fatal: not a git repository", rc=1, sin
    traza de pila). El hook envuelve ESE fallo real, no uno inventado."""

    def test_launcher_exits_zero_when_boot_py_fails_outside_a_git_repo(self, tmp_path):
        plain_dir = tmp_path / "not_a_git_repo"
        plain_dir.mkdir()

        # Control: boot.py por separado, contra el mismo directorio,
        # falla de verdad -- si esto dejara de fallar (p.ej. alguien
        # inicializa un repo git ahi sin querer), el test de abajo dejaria
        # de probar lo que dice probar.
        rc_direct, _out_direct, _err_direct = run_memory_script(
            "boot.py", [], cwd=str(plain_dir)
        )
        assert rc_direct != 0, (
            "control fallido: boot.py deberia fallar fuera de un "
            "repositorio git -- si ya no falla, este test ya no prueba "
            "el fallo real que dice probar"
        )

        payload = make_session_start_payload(str(plain_dir))
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=str(plain_dir))
        assert rc == 0, (
            f"el hook de SessionStart tiene que salir con 0 SIEMPRE, "
            f"incluso cuando boot.py falla -- la memoria ayuda, nunca "
            f"bloquea. Obtenido rc={rc}, stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err

    def test_launcher_exits_zero_when_target_directory_does_not_exist_at_all(self, tmp_path):
        """Mas extremo que el anterior: el directorio ni siquiera existe
        en disco. Si el hook lanza `boot.py` con ese `cwd` (heredado o via
        `payload["cwd"]`), la propia llamada a crear el subproceso puede
        fallar (`FileNotFoundError`) ANTES de que `boot.py` llegue a
        ejecutarse -- el hook tiene que capturar tambien ESO sin
        reventar, no solo el fallo de git."""
        missing = str(tmp_path / "does" / "not" / "exist")
        assert not os.path.exists(missing)

        # El proceso del hook en si necesita un cwd real para poder
        # arrancar -- se fija en un directorio que SI existe (tmp_path),
        # y es SOLO el payload el que apunta al directorio inexistente,
        # para aislar el fallo en la resolucion interna del hook.
        payload = make_session_start_payload(missing)
        rc, out, err = run_hook_with_payload(HOOK_NAME, payload, cwd=str(tmp_path))
        assert rc == 0, (
            f"un cwd inexistente en el payload no deberia poder tumbar la "
            f"sesion -- obtenido rc={rc}, stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err


class TestStdinRobustness:
    """`session-start-boot.py` y `session-start-crew.py` (los otros dos
    SessionStart de esta rama, ambos vivos) no leen stdin en absoluto --
    prueba de que un hook de este toolkit puede legitimamente no necesitar
    ningun campo del payload. Si `boot_launcher.py` SI lo lee (p.ej. para
    `payload["cwd"]`), tiene que sobrevivir a un stdin vacio o mal formado
    sin reventar -- no es un escenario de atacante externo (no hay
    atacante en el modelo de amenaza de esta obra), es robustez interna:
    el arnes que invoca el hook no deberia poder tumbar la sesion por si
    mismo manda un payload raro."""

    def test_launcher_survives_empty_stdin(self, tmp_repo, boot_lib):
        rc, out, err = run_hook_raw_stdin(HOOK_NAME, "", cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

    def test_launcher_survives_malformed_json_on_stdin(self, tmp_repo):
        rc, out, err = run_hook_raw_stdin(HOOK_NAME, "{not valid json", cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestSurvivesRestrictedConsoleEncoding:
    """Mismo caso que `TestForceUtf8StreamsFirstStatement` en
    `test_boot_script.py`, aplicado al hook: robustez de plataforma
    (unmassk-standards Sec.5), no un ataque -- una consola de codepage
    restringido (tipico en Windows) es un fallo del sistema contra si
    mismo si el arranque no lo tolera."""

    def test_launcher_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "auth", "product", "decision con acentos: sesion, codigo",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        payload = make_session_start_payload(tmp_repo)
        rc, out, err = run_hook_with_payload(
            HOOK_NAME, payload, cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"el arranque no deberia fallar bajo cp1252: {combined!r}"
