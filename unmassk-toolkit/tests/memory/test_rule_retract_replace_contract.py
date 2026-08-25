"""Contrato ROJO -- test-first, pase de CONTRATO (aceptacion, no barrido
exhaustivo): `gitmem rule` gana capacidad de RETIRAR y SUSTITUIR una
regla. Hoy (`lib/memory/rules.py`/`bin/memory/rule.py`) solo existen
`add()`/`read_all()` -- ninguna funcion de retiro ni de sustitucion
existe en ningun sitio del repo (verificado con grep antes de escribir
este fichero: cero apariciones de `retract`/`replace` en
`lib/memory/rules*.py`). Este fichero falla hoy por AUSENCIA de la
funcion/flag, no por un bug -- es el contrato que Ultron implementa
despues.

ENCARGO, cuatro puntos (orden del propietario, relayado por el
coordinador):

1. Retirar una regla identificandola por su texto exacto -- el unico
   reconocimiento que existe hoy es `_RULE_LINE_RE`/`iter_rule_texts()`.
   Tras retirarla, ni `gitmem rule` en modo lectura ni
   `rules_lib.read_all()` la devuelven.
2. Sustituir una regla: retira la vieja y anade la nueva de forma
   ATOMICA (o las dos, o ninguna).
3. La escritura pasa por el mismo camino atomico fichero+git
   (`rules_commit.commit_or_restore`), de modo que
   `health.py::coherence_rules` NO reporte una discrepancia falsa de
   "edicion a mano" despues de retirar. Test explicito: retiro una
   linea -> `coherence_rules` reporta limpio.
4. Retirar una regla cuyo texto NO existe se rechaza limpiamente -- no
   un no-op silencioso que parezca exito.

DISENO DE CONTRATO, EXPLICITO PORQUE NO EXISTIA NINGUNO ANTES (ninguna
zona lo tenia guardado -- `gitmem search "retirar regla"` / "sustituir
regla" / "rule retract", las tres 0 resultados, comprobado antes de
escribir esto, no adivinado): este fichero FIJA la forma de la
superficie nueva, en el mismo estilo que `test_rule_script.py` ya fijo
una ASUNCION documentada para el modo lectura sin texto posicional.

  CLI:
    rule.py --retract "<texto exacto>" --kind <user|claude>
    rule.py "<texto nuevo>" --replaces "<texto viejo>" \\
            --kind <user|claude> [--quote "<cita>"|none]

  Libreria (`lib/memory/rules.py`), mismo patron que `add()` -- devuelve
  `WriteResult`, `ok=True` implica commit real, nunca solo fichero:
    retract(text: str, kind: str) -> WriteResult
    replace(old_text: str, new_text: str, kind: str, quote=...) -> WriteResult

  `--kind` es OBLIGATORIO para `--retract`/`--replaces`, a diferencia de
  `add()` donde tiene un valor por defecto: `similar_existing()` (ya en
  produccion) establece que una regla `[user]` y una `[claude]` con el
  MISMO texto no son la misma regla -- identificar solo por texto seria
  ambiguo en cuanto existieran las dos. Exigir `--kind` evita que el
  contrato tenga que inventar una resolucion de ambiguedad que nadie
  pidio (esa resolucion, si hace falta, es otro encargo).

  El texto que identifica la regla a retirar/sustituir es el texto
  BASE, sin la cita -- `rules.strip_quote_suffix()` se aplica antes de
  comparar, igual que ya hace `similar_existing()`. Quien retira una
  regla se refiere a lo que dijo, no a la cita que la acompana en el
  fichero; obligar a retipear la cita para retirar seria un fallo de
  usabilidad que ningun texto del proyecto pide.

Round-trip real, sin fabricar el valor esperado (unmassk-standards
Sec.34): cada aserto usa un lector INDEPENDIENTE del script/funcion bajo
prueba -- `rules_lib.read_all()`/`iter_rule_texts()` (produccion, pero
llamada aparte) y `git show HEAD:<ruta>`/`git rev-list --count HEAD`
(subprocess real via `run_git`), nunca una funcion que el propio codigo
bajo prueba usa por dentro para verificarse a si misma.

No se modifica `lib/memory/rules.py`, `lib/memory/rules_commit.py` ni
`bin/memory/rule.py` desde este fichero -- solo tests.
"""

import contextlib
import importlib.util
import os
from pathlib import Path

import pytest

from .conftest import (
    BIN_MEMORY_DIR,
    import_lib_memory_module,
    run_git,
    run_memory_script,
    seed_config_json,
)

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
def rules_lib():
    return import_lib_memory_module("rules")


@pytest.fixture
def health_lib():
    return import_lib_memory_module("health")


def _commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _porcelain_status_for_rules_file(repo):
    rc, out, err = run_git(["status", "--porcelain", "--", _RULES_RELPATH], repo)
    assert rc == 0, f"git status fallo en el test: {err}"
    return out


def _head_blob(repo):
    rc, out, err = run_git(["show", f"HEAD:{_RULES_RELPATH}"], repo)
    assert rc == 0, f"git show fallo leyendo el blob comiteado: {err}"
    return out


@contextlib.contextmanager
def _forced_git_index_lock(repo):
    """Mismo mecanismo real ya usado en `test_rule_commit_contract.py` --
    `.git/index.lock` de verdad, fuerza el fallo REAL de cualquier `git
    add`/`git commit` posterior en ese repo.
    """
    lock_path = os.path.join(repo, ".git", "index.lock")
    with open(lock_path, "w", encoding="utf-8"):
        pass
    try:
        yield
    finally:
        os.remove(lock_path)


def _seed_rule(tmp_repo, text, kind="user", quote="none"):
    rc, out, err = run_memory_script(
        "rule.py", [text, "--kind", kind, "--quote", quote], cwd=tmp_repo
    )
    assert rc == 0, f"siembra fallo: stdout={out!r} stderr={err!r}"
    return out


# ---------------------------------------------------------------------------
# Punto 1 -- retirar por texto exacto: desaparece de fichero, git y lectura.
# ---------------------------------------------------------------------------


class TestRetractRemovesTheRuleFromEveryReader:
    def test_retract_creates_a_real_commit_and_the_text_is_gone_everywhere(
        self, tmp_repo, rules_lib
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"
        _seed_rule(tmp_repo, text, kind="user")
        after_seed = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["--retract", text, "--kind", "user"], cwd=tmp_repo
        )
        assert rc == 0, f"retirar una regla existente no puede rebotar: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after_retract = _commit_count(tmp_repo)
        assert after_retract == after_seed + 1, (
            "retirar una regla tiene que producir un commit real (mismo "
            f"criterio que I-003 para add()): antes={after_seed}, "
            f"despues={after_retract}"
        )

        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == "", (
            f"tras retirar, rules.md no puede quedar sucio: {status_out!r}"
        )

        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert not any(text in t for t in file_texts), (
            f"la regla retirada sigue apareciendo en rules_lib.read_all(): {file_texts!r}"
        )

        blob = _head_blob(tmp_repo)
        assert text not in blob, (
            f"la regla retirada sigue en el blob comiteado de HEAD: {blob!r}"
        )

        rc_read, out_read, err_read = run_memory_script("rule.py", [], cwd=tmp_repo)
        assert rc_read == 0, f"stdout={out_read!r} stderr={err_read!r}"
        assert text not in out_read, (
            f"el modo lectura de gitmem rule sigue mostrando la regla retirada: {out_read!r}"
        )

    def test_retract_matches_by_bare_text_even_when_the_stored_line_carries_a_quote(
        self, tmp_repo, rules_lib
    ):
        """La cita viaja como sufijo de la linea escrita
        (`rules_similarity._QUOTE_SUFFIX_RE`) -- retirar por el texto
        BASE (sin la cita) tiene que encontrar y quitar la linea igual,
        via `strip_quote_suffix()`. Quien retira no tiene por que
        retipear la cita.
        """
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "stop summarizing what you just did at the end"
        _seed_rule(tmp_repo, text, kind="claude", quote="no resumas lo que acabas de hacer")

        with _cwd(tmp_repo):
            seeded_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert any(t.startswith(text) and t != text for t in seeded_texts), (
            f"precondicion: la linea sembrada tiene que llevar la cita como "
            f"sufijo, distinta del texto base: {seeded_texts!r}"
        )

        rc, out, err = run_memory_script(
            "rule.py", ["--retract", text, "--kind", "claude"], cwd=tmp_repo
        )
        assert rc == 0, (
            f"retirar por el texto base (sin la cita) tiene que encontrar la "
            f"linea igual: stdout={out!r} stderr={err!r}"
        )

        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert file_texts == (), (
            f"la unica regla del fichero (con cita) tenia que desaparecer: {file_texts!r}"
        )


# ---------------------------------------------------------------------------
# Punto 4 -- retirar un texto que no existe se rechaza limpio, nunca un
# no-op silencioso que parezca exito.
# ---------------------------------------------------------------------------


class TestRetractingAnAbsentRuleBouncesCleanly:
    def test_retract_of_a_text_never_saved_is_rejected_not_a_silent_success(
        self, tmp_repo, rules_lib
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        never_saved = "this exact sentence was never saved as a rule"
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["--retract", never_saved, "--kind", "user"], cwd=tmp_repo
        )
        combined = out + err
        assert "Traceback" not in combined
        assert rc != 0, (
            f"retirar un texto que no existe tiene que rebotar, nunca "
            f"comportarse como exito silencioso: stdout={out!r}"
        )
        assert never_saved in combined, (
            f"el rechazo tiene que nombrar el texto real que no se encontro: {combined!r}"
        )
        keywords = ("no existe", "no encontr", "no hay ninguna regla", "no se encontr")
        assert any(k in combined.lower() for k in keywords), (
            f"el rechazo tiene que explicar, en palabras, que ese texto no "
            f"esta guardado -- ninguna de {keywords!r} aparecio en {combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, (
            "un retiro rechazado (texto ausente) no puede haber producido "
            f"ningun commit: antes={before}, despues={after}"
        )

    def test_retract_with_the_wrong_kind_bounces_instead_of_silently_matching_nothing(
        self, tmp_repo, rules_lib
    ):
        """La regla existe, pero bajo OTRO kind -- exige el mismo rechazo
        limpio que un texto totalmente ausente, nunca un "no encontre
        nada, no pasa nada" silencioso.
        """
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"
        _seed_rule(tmp_repo, text, kind="user")
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["--retract", text, "--kind", "claude"], cwd=tmp_repo
        )
        combined = out + err
        assert "Traceback" not in combined
        assert rc != 0, (
            f"la regla existe como [user], no como [claude] -- retirarla con "
            f"el kind equivocado tiene que rebotar: stdout={out!r}"
        )
        # Vacuous-green pitfall (ver memoria de Dante, rule-quote-contract-notes):
        # con `--retract` todavia sin existir, argparse YA rebota con
        # "unrecognized arguments" -- eso satisfaria un `rc != 0` desnudo sin
        # haber ejercitado nunca el rechazo real de kind equivocado. Forzamos
        # que este test solo pase el dia que exista un rechazo de NEGOCIO.
        assert "unrecognized arguments" not in combined, (
            f"este rechazo tiene que venir de la logica real de retiro (kind "
            f"equivocado), no del argparse generico por falta del flag "
            f"--retract: {combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, "un retiro rechazado no puede producir ningun commit"

        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert any(text in t for t in file_texts), (
            f"la regla [user] original tiene que seguir intacta tras el "
            f"intento fallido con kind equivocado: {file_texts!r}"
        )


# ---------------------------------------------------------------------------
# Punto 2 -- sustituir: retira la vieja y anade la nueva de forma ATOMICA.
# ---------------------------------------------------------------------------


class TestReplaceSwapsBothRulesAtomically:
    def test_replace_removes_the_old_text_and_adds_the_new_one_in_the_same_step(
        self, tmp_repo, rules_lib
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        old_text = "never mock the database in integration tests"
        new_text = "never mock the database, not even in integration tests"
        _seed_rule(tmp_repo, old_text, kind="user")
        after_seed = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py",
            [new_text, "--replaces", old_text, "--kind", "user", "--quote", "none"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert not any(old_text in t for t in file_texts), (
            f"el texto viejo tiene que haber desaparecido: {file_texts!r}"
        )
        assert any(new_text in t for t in file_texts), (
            f"el texto nuevo tiene que estar presente: {file_texts!r}"
        )

        blob = _head_blob(tmp_repo)
        assert old_text not in blob, f"el blob de HEAD no puede llevar el texto viejo: {blob!r}"
        assert new_text in blob, f"el blob de HEAD tiene que llevar el texto nuevo: {blob!r}"

        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == "", (
            f"tras un replace bueno, rules.md no puede quedar sucio: {status_out!r}"
        )

        after_replace = _commit_count(tmp_repo)
        assert after_replace > after_seed, (
            "un replace bueno tiene que dejar un commit real detras (retiro + "
            f"alta, mismo criterio que I-003): antes={after_seed}, "
            f"despues={after_replace}"
        )

    def test_a_failed_replace_leaves_the_old_rule_completely_intact(self, tmp_repo, rules_lib):
        """`replace()` es atomica -- si el commit real falla a mitad de
        camino, la regla vieja tiene que seguir exactamente como estaba
        (fichero Y HEAD) y la nueva no puede aparecer en ningun sitio.
        Probado a nivel de libreria (`rules_lib.replace()` directo, mismo
        patron que `TestFailedCommitLeavesNoStagedLeftovers` en
        `test_rule_commit_contract.py`) porque el escenario vive dentro
        de la funcion misma -- el script solo reenvia lo que devuelve.
        """
        seed_config_json(tmp_repo, repo_type="trunk")
        old_text = "never mock the database in integration tests"
        new_text = "never mock the database, not even in integration tests"

        with _cwd(tmp_repo):
            seeded = rules_lib.add(old_text, "user", quote="no mockees la base de datos")
        assert seeded.ok, f"la siembra tiene que comitear limpia: {seeded.git_error!r}"

        before_head_blob = _head_blob(tmp_repo)
        before = _commit_count(tmp_repo)

        with _forced_git_index_lock(tmp_repo):
            with _cwd(tmp_repo):
                result = rules_lib.replace(old_text, new_text, "user", quote="none")

        assert result.ok is False, (
            f"con .git/index.lock puesto, replace() tiene que fallar: {result!r}"
        )
        assert result.git_error, (
            f"el error real de git tiene que quedar visible en git_error: {result!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, (
            "un replace que fallo de verdad no puede haber dejado ningun commit "
            f"nuevo: antes={before}, despues={after}"
        )

        after_head_blob = _head_blob(tmp_repo)
        assert after_head_blob == before_head_blob, (
            "el commit de HEAD tiene que quedar exactamente igual que antes del "
            f"intento de replace fallido: antes={before_head_blob!r} "
            f"despues={after_head_blob!r}"
        )

        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == "", (
            "un replace fallido no puede dejar rules.md como cambio sin "
            f"comitear (ni la vieja a medio quitar ni la nueva a medio poner): "
            f"{status_out!r}"
        )

        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert any(old_text in t for t in file_texts), (
            f"la regla vieja tiene que seguir intacta tras el fallo: {file_texts!r}"
        )
        assert not any(new_text in t for t in file_texts), (
            f"la regla nueva no puede haber aparecido tras un replace fallido: {file_texts!r}"
        )


# ---------------------------------------------------------------------------
# Punto 3 -- mismo camino atomico fichero+git que add(): coherence_rules()
# reporta limpio despues de un retiro, nunca una discrepancia falsa de
# "edicion a mano".
# ---------------------------------------------------------------------------


class TestCoherenceRulesStaysCleanAfterRetract:
    def test_retract_through_the_real_commit_path_leaves_coherence_rules_silent(
        self, tmp_repo, rules_lib, health_lib
    ):
        root = Path(tmp_repo)
        seed_config_json(tmp_repo, repo_type="trunk")
        kept_text = "stop summarizing what you just did at the end"
        removed_text = "never mock the database in integration tests"
        _seed_rule(tmp_repo, removed_text, kind="user")
        _seed_rule(tmp_repo, kept_text, kind="claude")

        rc, out, err = run_memory_script(
            "rule.py", ["--retract", removed_text, "--kind", "user"], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert discrepancies == (), (
            "retirar una regla por el camino atomico real (commit_or_restore) "
            "no puede dejar coherence_rules() gritando una discrepancia falsa "
            f"de 'edicion a mano': {discrepancies!r}"
        )
        assert lines == 1, (
            f"tras retirar una de las dos, solo debe quedar una linea real en "
            f"el fichero: {lines!r}"
        )

    def test_a_failed_replace_also_leaves_coherence_rules_silent(
        self, tmp_repo, rules_lib, health_lib
    ):
        """Espejo del test anterior para el camino de fallo de `replace()`:
        `commit_or_restore()` ya se encarga de dejar el arbol de trabajo
        identico a HEAD cuando el commit revienta -- coherence_rules()
        tiene que seguir en silencio, no interpretar el intento fallido
        como una edicion a mano.
        """
        root = Path(tmp_repo)
        seed_config_json(tmp_repo, repo_type="trunk")
        old_text = "never mock the database in integration tests"
        with _cwd(root):
            seeded = rules_lib.add(old_text, "user", quote="no mockees la base de datos")
        assert seeded.ok, f"la siembra tiene que comitear limpia: {seeded.git_error!r}"

        with _forced_git_index_lock(tmp_repo):
            with _cwd(root):
                result = rules_lib.replace(
                    old_text, "never mock the database, not even in tests", "user", quote="none"
                )
        assert result.ok is False, f"el replace forzado tenia que fallar: {result!r}"

        with _cwd(root):
            commits, lines, discrepancies = health_lib.coherence_rules(root)

        assert discrepancies == (), (
            "un replace fallido, ya restaurado por commit_or_restore(), no "
            f"puede dejar coherence_rules() reportando una discrepancia: {discrepancies!r}"
        )


# ---------------------------------------------------------------------------
# CASO 1 (Cerberus, 2026-08-25) -- `--replaces` sin el texto nuevo
# posicional revienta HOY con la traza cruda de un TypeError de Python en
# vez de un rechazo limpio y explicado.
# ---------------------------------------------------------------------------


def _import_rule_module_for_constants():
    """Carga `bin/memory/rule.py` por ruta de fichero SOLO para leer su
    constante `_KIND_REQUIRED_MSG` -- nunca para llamar a ninguna de sus
    funciones (`run_memory_script` sigue siendo el UNICO camino que
    EJECUTA el script de verdad, PIEZAS.md Sec.10: "un script se prueba
    como lo usa una persona"). Mismo patron que
    `test_rejection_relaunch_commands.py::_import_bin_memory_module`:
    nombre de modulo prefijado para no chocar con los `import` planos
    que el propio `rule.py` hace durante su `exec_module()` (`import
    rejection as rejection_`, `import rules as rules_lib`).
    """
    path = os.path.join(BIN_MEMORY_DIR, "rule.py")
    spec = importlib.util.spec_from_file_location("bin_memory_rule_for_kind_msg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReplaceWithoutNewTextBouncesCleanlyInsteadOfCrashing:
    """`rule.py --replaces "<texto viejo>" --kind user` SIN el texto
    nuevo posicional (olvido natural: `--retract "<texto>" --kind <k>`
    SI se basta con un solo argumento -- `--replaces` no) llega hoy a
    `_cmd_replace(args.text, args.replaces, args.kind, args.quote)` con
    `new_text=None`. `_cmd_replace` solo guarda `kind is None`
    (`_KIND_REQUIRED_MSG`) -- nunca comprueba `new_text`/`args.text` --
    asi que la llamada sigue hasta `rules.replace()`
    (`lib/memory/rules.py:248`, `"\\n" in new_text`), que revienta con
    `TypeError: argument of type 'NoneType' is not a container or
    iterable`.

    El `try/except Exception` de `__main__` (`bin/memory/rule.py`,
    ultimas lineas) SI evita que salga una traza de pila cruda -- pero
    el mensaje que imprime es el texto crudo de ese `TypeError` de
    Python (`rule.py: argument of type 'NoneType' is not a container or
    iterable`), que ni dice que falta el texto nuevo de la regla ni
    dice como arreglarlo. Este test exige el rechazo CORRECTO: limpio,
    explicado, sin la palabra `NoneType` ni la palabra `Traceback` en
    ningun lado.
    """

    def test_replaces_without_the_new_positional_text_rejects_cleanly_not_with_a_python_crash(
        self, tmp_repo, rules_lib
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        old_text = "never mock the database in integration tests"
        _seed_rule(tmp_repo, old_text, kind="user")
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["--replaces", old_text, "--kind", "user"], cwd=tmp_repo
        )
        combined = out + err

        assert rc != 0, (
            f"--replaces sin el texto nuevo tiene que rebotar, nunca salir "
            f"OK: stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in combined, (
            f"PIEZAS.md Sec.10 prohibe una traza de pila cruda: {combined!r}"
        )
        assert "NoneType" not in combined, (
            "el TypeError crudo de Python ('argument of type NoneType is "
            f"not a container or iterable') no puede llegar tal cual al "
            f"usuario: {combined!r}"
        )
        assert "nuevo" in combined.lower(), (
            "el rechazo tiene que explicar que falta el texto NUEVO de la "
            f"regla, no un mensaje generico: {combined!r}"
        )

        # Ni el crash de hoy ni el rechazo limpio de manana pueden dejar
        # nada a medio escribir ni comiteado -- la regla vieja intacta.
        after = _commit_count(tmp_repo)
        assert after == before, (
            "un intento de --replaces sin texto nuevo no puede dejar ningun "
            f"commit nuevo: antes={before}, despues={after}"
        )
        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == "", (
            f"rules.md no puede quedar sucio tras el intento: {status_out!r}"
        )
        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert any(old_text in t for t in file_texts), (
            f"la regla vieja tiene que seguir intacta: {file_texts!r}"
        )


# ---------------------------------------------------------------------------
# CASO 2 (Cerberus, 2026-08-25) -- cobertura del guardia
# `_KIND_REQUIRED_MSG`: Cerberus lo verifico A MANO en los dos caminos
# (`--retract`, `--replaces`) y funciona; no tenia test todavia.
# ---------------------------------------------------------------------------


class TestKindRequiredGuardBouncesCleanlyOnBothFlags:
    """`_KIND_REQUIRED_MSG` (`bin/memory/rule.py`, guardia compartido de
    `_cmd_retract`/`_cmd_replace`) rechaza `--retract`/`--replaces` sin
    `--kind` ANTES de tocar `rules_lib`. Cada flag tiene su propio `if
    kind is None`, asi que los dos caminos se cubren por separado --
    ninguno pasa por el otro.
    """

    def test_retract_without_kind_bounces_with_the_exact_guard_message(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py",
            ["--retract", "never mock the database in integration tests"],
            cwd=tmp_repo,
        )
        combined = out + err

        module = _import_rule_module_for_constants()
        expected_message = module._KIND_REQUIRED_MSG.format(flag="--retract")

        assert rc != 0, (
            f"--retract sin --kind tiene que rebotar: stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in combined, f"sin traza de pila: {combined!r}"
        assert expected_message in combined, (
            "el rechazo tiene que llevar el mensaje real del guardia (no uno "
            f"reescrito a mano en el test): esperado={expected_message!r} "
            f"salida={combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, "un rebote de --kind no puede dejar ningun commit"

    def test_replaces_with_text_but_without_kind_bounces_with_the_exact_guard_message(
        self, tmp_repo
    ):
        seed_config_json(tmp_repo, repo_type="trunk")
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py",
            [
                "never mock the database, not even in tests",
                "--replaces",
                "never mock the database in integration tests",
            ],
            cwd=tmp_repo,
        )
        combined = out + err

        module = _import_rule_module_for_constants()
        expected_message = module._KIND_REQUIRED_MSG.format(flag="--replaces")

        assert rc != 0, (
            f"--replaces sin --kind tiene que rebotar: stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in combined, f"sin traza de pila: {combined!r}"
        assert expected_message in combined, (
            "el rechazo tiene que llevar el mensaje real del guardia (no uno "
            f"reescrito a mano en el test): esperado={expected_message!r} "
            f"salida={combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, "un rebote de --kind no puede dejar ningun commit"
