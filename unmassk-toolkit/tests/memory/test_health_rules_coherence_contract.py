"""Contrato ROJO -- Moriarty rompio el arreglo de I-003 por dos sitios
(reproducido en vivo, relayado por el coordinador). Este fichero cubre el
primero: **`health.coherence_rules()` resucita**.

Se retiro el 2026-08-06 (ver `lib/memory/health.py`, docstring del
modulo, seccion "coherence_rules SE RETIRA") porque en ese momento
`rules.add()` habia dejado de comitear nada -- cada regla nueva, sin
excepcion, viviria en el fichero sin ningun commit de regla detras, y el
chequeo pasaria a gritar SIEMPRE, un falso positivo permanente. I-003
(2026-08-23) revierte esa premisa: `rules.add()` vuelve a comitear de
verdad (ver `test_rule_commit_contract.py`), asi que el motivo de la
retirada desaparece y el chequeo vuelve a tener sentido -- la misma red
que `coherence()` ya tiende a las notas, aplicada al fichero de reglas.

Firma historica (verificada leyendo el commit de retirada, `396e502^`,
antes de escribir este contrato -- no inventada):

    def coherence_rules(root: Path) -> tuple[int, int, tuple[str, ...]]

Devuelve `(commits, lineas, discrepancias)`: cuantos commits de regla
hay en el historial, cuantas lineas de regla tiene `rules.md`, y el
texto de cada divergencia en cualquiera de los dos sentidos, con la
MISMA redaccion literal que la version historica usaba (verificada
contra el commit `396e502^:unmassk-toolkit/lib/memory/health.py`, no
adivinada):

    "<texto>: existe en un commit de regla pero falta en el fichero de reglas"
    "<texto>: esta en el fichero de reglas pero no existe en ningun commit de regla"

Los tres escenarios que pide el encargo:
  (a) `rules.md` con una linea modificada/anadida SIN comitear -> el
      detector la nombra.
  (b) estado limpio -> silencio (discrepancias vacias), pero con los
      numeros reales (mismo criterio que la fila 3 de `coherence()`: un
      chequeo mudo es indistinguible de uno que no corre).
  (c) el estado EXACTO que deja un proceso matado entre la escritura y
      el commit -- montado a mano en el repo semilla, con el MISMO
      mecanismo de escritura que `add()` usa por dentro
      (`gitcmd.atomic_write`) -- detectado.

Round-trip real, sin fabricar el texto esperado (unmassk-standards
Sec.34): cada escenario siembra con `rules_lib.add()` de verdad (commit
real, per I-003) y compara el resultado de `coherence_rules()` contra
lo que esos mismos escritores reales produjeron -- nunca un valor
copiado a mano.

No se toca produccion desde este fichero -- `health.py`/`rules.py` los
arregla Ultron en paralelo.
"""

import contextlib
import os
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module, run_git

_RULES_RELPATH = ".claude/project-memory/rules.md"


@contextlib.contextmanager
def _cwd(path):
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


@pytest.fixture
def health_lib():
    return import_lib_memory_module("health")


@pytest.fixture
def rules_lib():
    return import_lib_memory_module("rules")


@pytest.fixture
def gitcmd_lib():
    return import_lib_memory_module("gitcmd")


@pytest.fixture
def boot_lib():
    return import_lib_memory_module("boot")


@pytest.fixture
def indexes_lib():
    return import_lib_memory_module("indexes")


@pytest.fixture
def notes_lib():
    return import_lib_memory_module("notes")


def _append_line_by_hand(gitcmd_lib, rules_lib, root, line_text):
    """Escribe una linea de regla nueva DIRECTAMENTE en el fichero, con el
    MISMO mecanismo que `rules.add()` usa por dentro (`gitcmd.
    atomic_write`) pero sin pasar por `add()` -- ni candado, ni commit.
    Reproduce, a proposito, tanto "una edicion a mano" (punto a) como el
    estado exacto que deja un proceso matado justo despues de escribir
    la linea y antes de comitearla (punto c): son la MISMA foto final.
    """
    path = rules_lib.rules_file_path(root)
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    gitcmd_lib.atomic_write(path, previous + line_text + "\n")


class TestCleanStateAfterRealAddsIsSilent:
    """Punto (b): con todas las reglas comiteadas de verdad, el detector
    no puede quedarse mudo sobre los numeros (mismo criterio que
    `coherence()`, fila 3) -- pero la lista de discrepancias si tiene
    que quedar vacia.
    """

    def test_two_real_rules_leave_zero_discrepancies_with_real_counts(
        self, tmp_repo, health_lib, rules_lib
    ):
        root = Path(tmp_repo)
        with _cwd(root):
            first = rules_lib.add(
                "never mock the database in integration tests",
                "user",
                quote="no mockees la base de datos",
            )
            second = rules_lib.add(
                "stop summarizing what you just did at the end",
                "claude",
                quote="none",
            )
        assert first.ok and second.ok, (
            f"la siembra tiene que comitear limpia: {first.git_error!r} / "
            f"{second.git_error!r}"
        )

        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert (commits, lines) == (2, 2), (
            f"con dos reglas reales, comiteadas una por una, se esperan "
            f"2 commits y 2 lineas -- salio commits={commits!r} lineas={lines!r}"
        )
        assert discrepancies == (), (
            f"un estado limpio no puede reportar ninguna discrepancia: {discrepancies!r}"
        )


class TestUncommittedLineByHandIsReported:
    """Puntos (a) y (c): una linea de regla anadida (o modificada)
    directamente en el fichero, sin comitear, es EXACTAMENTE la foto que
    deja un proceso matado entre la escritura y el commit de `add()` --
    montada aqui a mano, con el mismo mecanismo de escritura real
    (`gitcmd.atomic_write`), nunca simulando el crash de otra forma.
    """

    def test_a_line_added_by_hand_without_a_commit_is_named_in_the_gap(
        self, tmp_repo, health_lib, rules_lib, gitcmd_lib
    ):
        root = Path(tmp_repo)
        baseline_text = "never mock the database in integration tests"
        with _cwd(root):
            seeded = rules_lib.add(baseline_text, "user", quote="no mockees la base de datos")
        assert seeded.ok, f"la siembra base tiene que comitear limpia: {seeded.git_error!r}"

        orphan_text = "stop summarizing what you just did at the end"
        orphan_line = f"[remember][claude] \U0001F9E0 {orphan_text}"
        _append_line_by_hand(gitcmd_lib, rules_lib, root, orphan_line)

        # Prueba independiente, por el camino real, de que esta es EXACTAMENTE
        # la foto de un proceso matado a medio camino: el fichero cambio de
        # verdad, git no tiene ningun commit detras de ese cambio.
        rc_status, status_out, _err = run_git(
            ["status", "--porcelain", "--", _RULES_RELPATH], tmp_repo
        )
        assert rc_status == 0
        assert status_out.strip(), (
            f"precondicion del test: la linea anadida a mano tiene que quedar "
            f"como cambio real sin comitear -- git status --porcelain: {status_out!r}"
        )

        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert commits == 1, f"solo hay un commit de regla real (la siembra): {commits!r}"
        assert lines == 2, f"el fichero tiene dos lineas ahora (siembra + huerfana): {lines!r}"
        expected = f"{orphan_text}: esta en el fichero de reglas pero no existe en ningun commit de regla"
        assert expected in discrepancies, (
            f"el detector tiene que nombrar la linea huerfana con la redaccion "
            f"historica exacta: se esperaba {expected!r} entre {discrepancies!r}"
        )

    def test_a_committed_line_edited_by_hand_diverges_in_both_directions(
        self, tmp_repo, health_lib, rules_lib, gitcmd_lib
    ):
        """Variante "modificada" del punto (a): se toca a mano la MISMA
        linea ya comiteada (no se anade una nueva) -- el commit sigue
        citando el texto viejo, el fichero ya solo tiene el nuevo. La
        divergencia tiene que verse en los DOS sentidos a la vez.
        """
        root = Path(tmp_repo)
        original_text = "never mock the database in integration tests"
        with _cwd(root):
            seeded = rules_lib.add(original_text, "user", quote="no mockees la base de datos")
        assert seeded.ok, f"la siembra tiene que comitear limpia: {seeded.git_error!r}"

        path = rules_lib.rules_file_path(root)
        committed_content = path.read_text(encoding="utf-8")
        edited_text = "never mock the database, not even in integration tests"
        edited_content = committed_content.replace(original_text, edited_text)
        assert edited_content != committed_content, (
            "precondicion: el reemplazo tiene que cambiar de verdad el contenido"
        )
        with _cwd(root):
            gitcmd_lib.atomic_write(path, edited_content)

        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert commits == 1 and lines == 1, (
            f"un commit real, una linea real en el fichero (editada, no anadida): "
            f"commits={commits!r} lineas={lines!r}"
        )
        missing_from_file = (
            f"{original_text}: existe en un commit de regla pero falta en el "
            "fichero de reglas"
        )
        missing_from_git = (
            f"{edited_text}: esta en el fichero de reglas pero no existe en "
            "ningun commit de regla"
        )
        assert missing_from_file in discrepancies, (
            f"el texto viejo (solo en el commit ahora) tiene que salir nombrado: "
            f"se esperaba {missing_from_file!r} entre {discrepancies!r}"
        )
        assert missing_from_git in discrepancies, (
            f"el texto nuevo (solo en el fichero ahora) tiene que salir nombrado: "
            f"se esperaba {missing_from_git!r} entre {discrepancies!r}"
        )


class TestRepoWithoutAnyRuleYetDoesNotCrash:
    """Regresion minima heredada de la version historica (endurecimiento
    2026-08-02: "una rama sin ningun commit de regla no debe reventar
    coherence_rules()") -- aqui con un repo que SI tiene commits (el
    `init` de `tmp_repo`) pero CERO reglas todavia, nunca con una rama
    sin ningun commit en absoluto (eso rompe otras piezas del sistema
    antes de llegar a esta).
    """

    def test_zero_rules_reports_zero_and_zero_never_crashes(self, tmp_repo, health_lib):
        root = Path(tmp_repo)
        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert (commits, lines, discrepancies) == (0, 0, ()), (
            f"sin ninguna regla todavia, se esperan ceros y silencio -- salio "
            f"{(commits, lines, discrepancies)!r}"
        )


# ---------------------------------------------------------------------------
# Moriarty rompio la resurreccion por un borde real (relayado por el
# coordinador, verificado aqui de forma independiente antes de escribir
# ninguna asercion -- ver la sonda mas abajo). La PRIMERA regla de un
# proyecto (`rules.md` escrito en disco, JAMAS comiteado -- ni siquiera
# trackeado) mas un proceso matado entre la escritura y el commit hacia
# reventar `coherence_rules()` con un `RuntimeError`, sustituyendo el
# arranque entero por un banner de fallo con traceback -- peor que el
# silencio original que I-003 vino a arreglar.
#
# Causa raiz (leida en `query.py::show_file_at_head`, no adivinada):
# `_SHOW_PATH_MISSING_MARKER = "does not exist in"` solo reconoce la
# forma de git para un pathspec que NUNCA existio en ningun commit. Para
# un fichero que SI existe en el arbol de trabajo pero nunca se
# comiteo -- exactamente esta foto -- git dice otra cosa. Confirmado
# EJECUTANDO `git show HEAD:<ruta>` de verdad contra un repo desechable
# con ese estado exacto (no tomado de la palabra del coordinador):
#
#   returncode: 128
#   stderr: "fatal: path '.claude/project-memory/rules.md' exists on
#            disk, but not in 'HEAD'\n"
#
# "exists on disk" no esta en la lista de marcadores reconocidos --
# `show_file_at_head()` lo trata como un fallo real de git y revienta.
# Este fichero nunca toca `query.py`: solo prueba que
# `health.coherence_rules()` (y, en el segundo test, la tuberia completa
# del arranque) no propaga esa excepcion.
# ---------------------------------------------------------------------------


class TestFirstEverRuleNeverCommittedDoesNotCrash:
    def test_uncommitted_first_ever_rule_is_reported_never_a_crash(
        self, tmp_repo, health_lib, rules_lib, gitcmd_lib
    ):
        root = Path(tmp_repo)
        # `tmp_repo` ya trae un commit ajeno de fabrica ("init") -- HEAD
        # existe, pero nunca ha visto `rules.md`. La primera regla se
        # escribe DIRECTAMENTE en disco, con el mismo mecanismo que
        # `add()` usa por dentro, sin pasar por `add()` en absoluto --
        # nunca `git add`, nunca un commit -- para dejar exactamente la
        # foto de un proceso matado tras la primera regla del proyecto.
        orphan_text = "MARK_FIRST_EVER una regla que nunca llego a comitearse"
        orphan_line = f"[remember][user] \U0001F9E0 {orphan_text}"
        path = rules_lib.rules_file_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        gitcmd_lib.atomic_write(path, orphan_line + "\n")

        # Precondicion verificada con un lector independiente (git de
        # verdad, no `health_lib`): confirma que este repo esta
        # exactamente en la forma de fallo que el hallazgo describe,
        # antes de pedirle nada a `coherence_rules()`.
        rc_show, _show_out, show_err = run_git(
            ["show", "HEAD:.claude/project-memory/rules.md"], tmp_repo
        )
        assert rc_show != 0 and "exists on disk" in show_err, (
            f"precondicion del test: se esperaba el fallo real 'exists on disk, "
            f"but not in HEAD', salio: rc={rc_show!r} stderr={show_err!r}"
        )

        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert (commits, lines) == (0, 1), (
            f"cero lineas comiteadas todavia, una sola en el fichero real -- "
            f"salio commits={commits!r} lineas={lines!r}"
        )
        expected = (
            f"{orphan_text}: esta en el fichero de reglas pero no existe en "
            "ningun commit de regla"
        )
        assert expected in discrepancies, (
            f"la linea huerfana tiene que salir NOMBRADA, nunca provocar un "
            f"crash: discrepancias={discrepancies!r}"
        )

    def test_full_boot_pipeline_does_not_crash_and_paints_the_warning(
        self, tmp_repo, health_lib, rules_lib, gitcmd_lib, boot_lib, indexes_lib, notes_lib
    ):
        """La misma foto, pero verificando la tuberia REAL del arranque
        (`boot.build()` -> `boot.render()`) en vez de llamar a
        `coherence_rules()` en aislamiento -- el sitio donde el
        coordinador dice que el fallo se ve de verdad: el informe entero
        sustituido por un banner de fallo, nunca el CHECKS normal.
        """
        root = Path(tmp_repo)
        indexes_lib.seed(notes_lib.pm_root(root))

        orphan_text = "MARK_FIRST_EVER_BOOT una regla que nunca llego a comitearse"
        orphan_line = f"[remember][user] \U0001F9E0 {orphan_text}"
        path = rules_lib.rules_file_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        gitcmd_lib.atomic_write(path, orphan_line + "\n")

        with _cwd(root):
            summary = boot_lib.build()
            rendered = boot_lib.render(summary)

        assert "Traceback" not in rendered, (
            f"el arranque no puede sustituirse por un banner de fallo con "
            f"traceback -- render real:\n{rendered}"
        )

        avisos_split = rendered.split("CHECKS", 1)
        assert len(avisos_split) == 2, f"el render no trae ninguna seccion CHECKS:\n{rendered}"
        avisos_block = avisos_split[1]

        assert "rules do not match git" in avisos_block, (
            "la primera regla sin comitear tiene que disparar el aviso normal "
            f"en CHECKS, nunca un crash:\n{avisos_block}"
        )
        assert orphan_text in avisos_block, (
            f"el aviso tiene que nombrar la regla huerfana concreta:\n{avisos_block}"
        )


# ---------------------------------------------------------------------------
# Punto 2 del encargo ("de regalo si es barato"): `rules.md` existente y
# comiteado en un repo cuyo HEAD lo "perdio" por un commit raro. Evaluado,
# NO forzado -- cualquier montaje realista que se me ocurre (un `git rm
# --cached` seguido de un `--amend`, o un `reset --hard` a un commit
# anterior a que `rules.md` existiera) reduce a UNA de estas dos formas,
# ninguna nueva: (a) el fichero sigue en disco pero el arbol lo perdio de
# su indice -- exactamente la MISMA forma de fallo de git ya cubierta
# arriba ("exists on disk, but not in HEAD"), o (b) el fichero desaparece
# tambien del disco al mover HEAD (`reset --hard` restaura el arbol de
# trabajo) -- la forma "no existe en ningun sitio" que ya cubre
# `TestRepoWithoutAnyRuleYetDoesNotCrash` mas arriba. No se fuerza un
# tercer test para simular una tercera forma de fallo que no existe:
# dicho aqui en vez de escribir cobertura que no demuestra nada nuevo.
# ---------------------------------------------------------------------------
