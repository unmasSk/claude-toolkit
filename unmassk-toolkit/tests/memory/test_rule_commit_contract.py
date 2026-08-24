"""Contrato ROJO -- I-003 (2026-08-23): "gitmem rule reports success without
committing the rule" (`git log`: commit `3b6590a`
"[I-003][memory][skills] gitmem rule reports success without committing the
rule", seguido de `582590c`, ambos en HEAD de este repo a fecha de escritura).

Encargo, tres puntos:

1. DUPLICADOS: guardar una regla igual o muy parecida a una ya existente
   rechaza sin guardar, muestra la(s) candidata(s) y explica como relanzar.
2. NUEVO (I-003): el mensaje de exito solo se imprime si la regla quedo
   COMITEADA de verdad -- tras guardar, `rules.md` esta limpio en
   `git status` y existe un commit real con la regla dentro. Si el commit
   falla, el mensaje NO dice "guardada" y el error real se ve.
3. CASO BUENO: guardar una regla claramente distinta se guarda y comitea
   como siempre, con `--kind user` y `--kind claude`, y `--quote` sigue
   siendo obligatorio.

CONTRADICCION ENCONTRADA Y RESUELTA POR EL PROPIETARIO, NO EN SILENCIO: el
docstring de produccion (`lib/memory/rules.py`: "``add()`` HOY (desde
2026-08-06) es UN SOLO PASO... sin tocar git para nada, ni un commit vacio
ni un commit con el fichero como pathspec [orden del propietario]") fijaba
el contrato EXACTAMENTE CONTRARIO al que este fichero escribe: "nunca
comitea". Ese contrato de 2026-08-06 queda revertido por I-003, un
incidente real presentado por el propietario el 2026-08-23 (`git log`
real, commits `3b6590a`/`582590c`, visibles en este mismo repo) -- no es
una peticion inventada por esta tarea, es la misma fecha y el mismo canal
(`.claude/project-memory/INCIDENTS.md`) que ya uso el resto del sistema
para encargos reales. **Confirmado por el propietario, via el
coordinador, en la fase siguiente de esta misma tarea**: "la contradicción
que señalaste queda resuelta por el propietario: I-003 ... revoca la
decisión de 2026-08-06. Manda lo que él dice." La clase que fijaba el
contrato viejo, `test_rule_script.py::
TestRuleEndsUpInTheFileNotInAnOwnCommit` (3 tests), queda RETIRADA por
esta misma orden -- ver el banner de retirada en `test_rule_script.py`
(mismo sitio, cita I-003 explicita) para el detalle de que cobertura se
preservo aqui y cual dejo de aplicar por cambio de premisa.

Precedente historico relevante para quien implemente el punto 2:
`lib/memory/rules.py` ya documenta, retirado el 2026-08-06, un mecanismo
de rescate para exactamente este escenario (`_restore_file_best_effort`,
ver `test_rules.py` lineas ~416-441: "commit fallido -> fichero vuelve a
su contenido anterior, o se borra entero si era el primer remember").
Este contrato NUEVO solo exige, en las palabras literales del encargo,
que el mensaje no diga "guardada" y que el error se vea -- no exige
restaurar el fichero, y este fichero de tests no lo fabrica: se deja
anotado para que quien implemente decida con el propietario delante.

"AMBIGUEDAD ENCONTRADA, NO RESUELTA POR ADIVINACION" (punto 1): el
encargo pide mostrar "la(s) regla(s) candidata(s) con su numero". Ni
TEXTOS.md Sec.1.11b (el rechazo ya escrito y ya implementado en
`rule.py::_render_similar_rejection`) ni ningun otro texto del proyecto
muestran un numero/id junto a una regla candidata -- una regla no tiene
identificador, a diferencia de una Note (Sec.1.6 tampoco usa numeros,
"ensena las notas candidatas enteras en vez de sus identificadores").
Este fichero NO inventa un campo "numero" que no existe en ningun
sitio: se prueba lo que YA esta especificado y en produccion (dueno +
texto completo de la candidata, instrucciones de relanzamiento), y se
deja constancia de la ambiguedad aqui en vez de rellenarla con
criterio propio.

Round-trip real, sin fabricar el valor esperado (unmassk-standards
Sec.34): cada aserte usa un lector INDEPENDIENTE del script bajo prueba
-- `git rev-list --count HEAD` / `git status --porcelain` / `git show
HEAD:<ruta>` / `git log -1 --pretty=%B` (subprocess real, via
`run_git`), nunca una funcion que el propio script usa por dentro.

No se modifica `lib/memory/rules.py` ni `bin/memory/rule.py` desde este
fichero -- solo tests, modo test-first (contrato en rojo, Ultron
implementa despues).
"""

import contextlib
import os
import threading
from pathlib import Path

import pytest

from .conftest import (
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
def emojis_lib():
    return import_lib_memory_module("emojis")


def _commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _head_message(repo):
    rc, out, err = run_git(["log", "-1", "--pretty=%B", "HEAD"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _porcelain_status_for_rules_file(repo):
    rc, out, err = run_git(["status", "--porcelain", "--", _RULES_RELPATH], repo)
    assert rc == 0, f"git status fallo en el test: {err}"
    return out


@contextlib.contextmanager
def _forced_git_index_lock(repo):
    """Mismo mecanismo real ya usado en `test_work_script.py`/
    `test_next_script.py`/`test_remove_script.py`/`test_wip_script.py`/
    `test_notes.py`: crea `.git/index.lock` DE VERDAD antes de que el
    script bajo prueba corra, forzando el fallo REAL de cualquier
    `git add`/`git commit` posterior en ese repo (git rechaza con
    `fatal: Unable to create '.../index.lock': File exists.`, nunca
    simulado). Limpia el candado en un `finally` para no dejarlo huerfano
    entre tests.
    """
    lock_path = os.path.join(repo, ".git", "index.lock")
    with open(lock_path, "w", encoding="utf-8"):
        pass
    try:
        yield
    finally:
        os.remove(lock_path)


@contextlib.contextmanager
def _forced_pre_commit_hook_rejects(repo):
    """Planta un hook `pre-commit` REAL que siempre rechaza (`exit 1`) --
    a diferencia de `_forced_git_index_lock` (que bloquea el `git add`
    tambien, antes de que nada quede staged), este hook deja que `git add`
    corra con normalidad y solo hace fallar el `git commit` que le sigue
    -- exactamente el escenario donde `stage_and_commit()` ya dejo el
    indice con el contenido NUEVO staged antes de que el commit reviente.
    Limpia el hook en un `finally` para no dejarlo huerfano entre tests.
    """
    hooks_dir = os.path.join(repo, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-commit")
    with open(hook_path, "w", encoding="utf-8") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    os.chmod(hook_path, 0o755)
    try:
        yield
    finally:
        os.remove(hook_path)


# ---------------------------------------------------------------------------
# Punto 3 -- caso bueno: se guarda Y se comitea de verdad
# ---------------------------------------------------------------------------


class TestGoodRuleEndsUpCommittedForReal:
    """Reemplaza, para el caso bueno, el contrato de
    `TestRuleEndsUpInTheFileNotInAnOwnCommit` (ver contradiccion avisada
    en el docstring del modulo). `repo_type="trunk"` sembrado a proposito
    -- si Ultron reutiliza la proteccion de rama principal de
    `work.py`/`note.py` para este commit nuevo, un repo sin sembrar
    rebotaria por eso, no por lo que este test quiere probar.
    """

    def test_kind_user_creates_exactly_one_commit_and_a_clean_tree(self, tmp_repo, rules_lib):
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py",
            [text, "--kind", "user", "--quote", "no mockees la base de datos, nunca"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "guardada" in out, (
            f"una regla aceptada tiene que confirmar el guardado: stdout={out!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before + 1, (
            "gitmem rule tiene que producir EXACTAMENTE un commit nuevo al "
            f"guardar una regla buena: antes={before}, despues={after}"
        )

        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == "", (
            "tras un guardado bueno, rules.md no deberia quedar como cambio "
            f"sin comitear: {status_out!r}"
        )

        with _cwd(tmp_repo):
            file_texts = rules_lib.iter_rule_texts(rules_lib.read_all())
        assert any(text in t for t in file_texts), (
            f"la regla no aparece en rules.md (rules.read_all() real): {file_texts!r}"
        )

    def test_kind_claude_with_quote_none_also_commits_for_real(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "stop summarizing what you just did at the end"
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", [text, "--kind", "claude", "--quote", "none"], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "guardada" in out

        after = _commit_count(tmp_repo)
        assert after == before + 1, (
            f"kind=claude tambien tiene que comitear de verdad: antes={before}, "
            f"despues={after}"
        )

        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == ""

    def test_the_real_commit_blob_and_message_carry_the_documented_subject(
        self, tmp_repo, emojis_lib
    ):
        """El formato del commit ya esta fijado en `rules.py` (docstring,
        "FORMATO DEL COMMIT, fijado en Sec.9.7"): `[remember][<kind>]
        <emoji> <texto>` -- la MISMA linea que `add()` ya calcula como
        `subject` para escribirla en el fichero (produccion,
        `rules.py::add`, variable `subject`). No se fabrica un mensaje de
        commit propio para este test: se deriva del emoji real
        (`emojis_lib.CHANNEL_EMOJI["rule"]`, produccion) y del texto real.
        """
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"
        kind = "user"

        rc, out, err = run_memory_script(
            "rule.py",
            [text, "--kind", kind, "--quote", "no mockees la base de datos"],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        rc_show, show_out, err_show = run_git(
            ["show", f"HEAD:{_RULES_RELPATH}"], tmp_repo
        )
        assert rc_show == 0, f"git show fallo leyendo el blob comiteado: {err_show}"
        assert text in show_out, (
            f"el blob comiteado no lleva el texto real de la regla: {show_out!r}"
        )

        message = _head_message(tmp_repo)
        emoji = emojis_lib.CHANNEL_EMOJI["rule"]
        assert f"[remember][{kind}]" in message, (
            f"el mensaje del commit real no lleva el prefijo documentado "
            f"(Sec.9.7): {message!r}"
        )
        assert emoji in message and text in message, (
            f"el mensaje del commit real no lleva el emoji/texto documentados: {message!r}"
        )


# ---------------------------------------------------------------------------
# Punto 2 -- NUEVO (I-003): sin commit real, nunca "guardada"
# ---------------------------------------------------------------------------


class TestFailedCommitNeverClaimsSuccess:
    """`.git/index.lock` real (mismo mecanismo que el resto de la suite,
    ver `_forced_git_index_lock`) fuerza el fallo REAL de cualquier
    `git add`/`git commit` que Ultron cablee dentro de `add()`. Hoy
    (produccion sin tocar git en absoluto) esta prueba falla porque el
    mensaje de exito se imprime siempre que la validacion pasa, sin
    importar git -- exactamente el sintoma de I-003.
    """

    def test_index_lock_blocks_the_commit_and_hides_the_success_message(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"

        with _forced_git_index_lock(tmp_repo):
            rc, out, err = run_memory_script(
                "rule.py",
                [text, "--kind", "user", "--quote", "no mockees la base de datos"],
                cwd=tmp_repo,
            )

        combined = out + err
        assert "Traceback" not in combined
        assert rc != 0, (
            f"con .git/index.lock puesto, el guardado tiene que fallar: stdout={out!r}"
        )
        assert "guardada" not in out, (
            "el mensaje de exito NO puede aparecer si el commit real fallo "
            f"(I-003): stdout={out!r}"
        )
        assert "index.lock" in combined, (
            f"el error REAL de git tiene que llegar a la salida, no un mensaje "
            f"generico: {combined!r}"
        )

    def test_index_lock_leaves_no_new_commit_behind(self, tmp_repo):
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"
        before = _commit_count(tmp_repo)

        with _forced_git_index_lock(tmp_repo):
            run_memory_script(
                "rule.py",
                [text, "--kind", "user", "--quote", "no mockees la base de datos"],
                cwd=tmp_repo,
            )

        after = _commit_count(tmp_repo)
        assert after == before, (
            "un commit que fallo de verdad no puede haber dejado ningun commit "
            f"nuevo: antes={before}, despues={after}"
        )


# ---------------------------------------------------------------------------
# Punto 1 -- duplicados: rechaza sin comitear, muestra dueno + texto +
# como relanzar. Se combina con el commit real del sembrado para que este
# test tambien sea ROJO hoy (el sembrado, en produccion actual, nunca
# comitea -- ver el bloque de arriba).
# ---------------------------------------------------------------------------


class TestNearDuplicateNeverCommitsEitherRuleTwice:
    def test_near_duplicate_is_rejected_and_creates_no_new_commit(self, tmp_repo, rules_lib):
        seed_config_json(tmp_repo, repo_type="trunk")
        existing_text = "never mock the database in integration tests"
        before_seed = _commit_count(tmp_repo)

        rc_seed, out_seed, err_seed = run_memory_script(
            "rule.py",
            [existing_text, "--kind", "user", "--quote", "no mockees la base de datos"],
            cwd=tmp_repo,
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        after_seed = _commit_count(tmp_repo)
        assert after_seed == before_seed + 1, (
            "la siembra (una regla buena) tiene que comitear de verdad antes de "
            f"seguir: antes={before_seed}, despues={after_seed}"
        )

        candidate_text = "never mock the database in integration test"
        with _cwd(tmp_repo):
            expected_similar = rules_lib.similar_existing(candidate_text)
        assert ("user", existing_text) in expected_similar, (
            "precondicion: rules.similar_existing() (produccion) tiene que "
            f"devolver ('user', {existing_text!r}); devolvio {expected_similar!r}"
        )

        rc, out, err = run_memory_script(
            "rule.py",
            [candidate_text, "--kind", "user", "--quote", "otra cita, la del candidato"],
            cwd=tmp_repo,
        )
        combined = out + err
        assert "Traceback" not in combined
        assert rc != 0, f"una casi-duplicada tiene que rebotar: stdout={out!r}"
        assert "guardada" not in out, (
            f"una regla rechazada por casi-duplicada no puede confirmarse: {out!r}"
        )

        for similar_kind, similar_text in expected_similar:
            matching_lines = [line for line in combined.splitlines() if similar_text in line]
            assert matching_lines, (
                "el rechazo tiene que ensenar la regla candidata ya guardada: "
                f"no aparecio {similar_text!r} en {combined!r}"
            )
            assert any(f"[{similar_kind}]" in line for line in matching_lines), (
                f"el rechazo tiene que nombrar el dueno real ({similar_kind!r}) "
                f"junto al texto candidato: {combined!r}"
            )
        assert "reesc" in combined.lower() or "gitmem rule" in combined, (
            "el rechazo tiene que explicar como relanzar (reescribir la regla si "
            f"de verdad son distintas): {combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == after_seed, (
            "una regla rechazada por casi-duplicada no puede haber producido "
            f"ningun commit nuevo: antes={after_seed}, despues={after}"
        )

    def test_missing_quote_still_bounces_before_touching_git(self, tmp_repo):
        """Regresion: la exigencia de `--quote` (ya en produccion,
        `test_rule_quote.py`) tiene que seguir rebotando ANTES de tocar
        git una vez que el commit real quede cableado -- nunca debe
        comitear una regla que en realidad se rechazo por falta de cita.
        """
        seed_config_json(tmp_repo, repo_type="trunk")
        text = "never mock the database in integration tests"
        before = _commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", [text, "--kind", "user"], cwd=tmp_repo
        )
        combined = out + err
        assert "Traceback" not in combined
        assert rc != 0, f"sin --quote, la regla tiene que rebotar: stdout={out!r}"
        assert "cita" in combined, (
            f"el rechazo real de rules.py nombra la falta de cita: {combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, (
            "un rechazo por falta de cita no puede haber producido ningun commit "
            f"nuevo: antes={before}, despues={after}"
        )


# ---------------------------------------------------------------------------
# Hallazgos de revision, confirmados con repro en vivo por el coordinador
# (misma incidencia I-003, tras la implementacion de Ultron): el commit
# real que `add()` intenta ahora puede fallar de DOS formas distintas de
# las ya cubiertas arriba (`.git/index.lock` bloqueando TODO, add incluido)
# -- un hook que rechaza el commit DESPUES de que `git add` ya corrio, y
# un commit fallido sobre la PRIMERA regla del proyecto (sin `rules.md`
# previo). Ambas se prueban a nivel de LIBRERIA (`rules_lib.add()`
# directo, `_cwd` real) porque el escenario vive dentro de `add()` mismo
# -- el script (`bin/memory/rule.py`) solo reenvia lo que `add()`
# devuelve, no anade logica propia de recuperacion.
# ---------------------------------------------------------------------------


class TestFailedCommitLeavesNoStagedLeftovers:
    """Hallazgo 1: un commit rechazado DESPUES de que `git add` ya dejo
    el contenido nuevo en el indice (hook de pre-commit, no un
    `.git/index.lock` que habria bloqueado tambien el `add`) deja hoy el
    indice con el contenido RECHAZADO mientras
    `notes_commit.restore_snapshot_best_effort()` ya devolvio el FICHERO
    a su version anterior -- una desincronizacion indice/arbol de trabajo
    ("MM" en `git status --porcelain`) que ni `ok=False` ni el fichero
    revertido delatan por si solos. Contrato: `ok=False` con `git_error`
    visible Y `git status --porcelain -- rules.md` COMPLETAMENTE limpio.
    """

    def test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree(
        self, tmp_repo, rules_lib
    ):
        # Repo semilla: una regla ya guardada y comiteada de verdad ANTES
        # de plantar el hook -- si el hook estuviera puesto desde el
        # principio, ni siquiera esta siembra podria comitear. El hook
        # solo se plantea para el segundo `add()`, el que este test
        # quiere ver rechazado.
        with _cwd(tmp_repo):
            seed_result = rules_lib.add(
                "never mock the database in integration tests",
                "user",
                quote="no mockees la base de datos",
            )
        assert seed_result.ok, f"la siembra tiene que comitear limpia: {seed_result.git_error}"

        rejected_text = "stop summarizing what you just did at the end"
        with _forced_pre_commit_hook_rejects(tmp_repo):
            with _cwd(tmp_repo):
                result = rules_lib.add(rejected_text, "claude", quote="none")

        assert result.ok is False, (
            f"un commit rechazado por el hook de pre-commit tiene que devolver "
            f"ok=False: {result!r}"
        )
        assert result.git_error, (
            f"el error real de git (el rechazo del hook) tiene que quedar visible "
            f"en git_error, no un ok=False mudo: {result!r}"
        )

        status_out = _porcelain_status_for_rules_file(tmp_repo)
        assert status_out.strip() == "", (
            "tras un commit rechazado, rules.md tiene que quedar COMPLETAMENTE "
            "limpio -- ni el indice (contenido rechazado ya staged) ni el arbol "
            f"de trabajo (ya restaurado) pueden diferir de HEAD: git status "
            f"--porcelain -- rules.md = {status_out!r} (se espera cadena vacia, "
            "no 'MM')"
        )

        with _cwd(tmp_repo):
            content_after = rules_lib.read_all()
        assert rejected_text not in content_after, (
            "el fichero no puede seguir con el texto rechazado tras la "
            f"restauracion: {content_after!r}"
        )


class TestFirstEverRuleWithFailedCommitLeavesNoOrphanFile:
    """Hallazgo 2: en un repo SIN `rules.md` todavia, un commit fallido
    (`.git/index.lock`) deja hoy un `rules.md` huerfano -- solo la
    cabecera, sin ninguna regla -- que no existia antes de llamar a
    `add()`. Pasa porque `previous_content` para "el fichero no existia"
    es la cabecera (no `None`/ausencia), y `restore_snapshot_best_effort()`
    siempre ESCRIBE ese valor, nunca borra el fichero. Contrato: `ok=False`
    Y `rules.md` NO existe despues, exactamente como antes de la llamada.
    """

    def test_index_lock_on_a_fresh_repo_leaves_no_rules_file_behind(
        self, tmp_repo, rules_lib
    ):
        rules_relpath = ".claude/project-memory/rules.md"
        rules_path = os.path.join(tmp_repo, rules_relpath)
        assert not os.path.exists(rules_path), (
            "precondicion del test: repo fresco, sin rules.md todavia"
        )

        with _forced_git_index_lock(tmp_repo):
            with _cwd(tmp_repo):
                result = rules_lib.add(
                    "never mock the database in integration tests",
                    "user",
                    quote="no mockees la base de datos",
                )

        assert result.ok is False, (
            f"con .git/index.lock puesto, add() tiene que fallar: {result!r}"
        )
        assert result.git_error, (
            f"el error real de git tiene que quedar visible en git_error: {result!r}"
        )

        leftover = None
        if os.path.exists(rules_path):
            with open(rules_path, encoding="utf-8") as fh:
                leftover = fh.read()
        assert leftover is None, (
            "la PRIMERA regla del proyecto, con un commit fallido, no puede dejar "
            "un rules.md huerfano (solo cabecera) que antes no existia -- "
            f"contenido encontrado: {leftover!r}"
        )


# ---------------------------------------------------------------------------
# Segundo hallazgo de Moriarty (reproducido en vivo, relayado por el
# coordinador): una escritura AJENA a `rules.md` -- que no pasa por
# `add()`, no toma su candado -- puede aterrizar en la ventana entre la
# LECTURA de `add()` (`path.read_text()`, el contenido previo) y su
# ESCRITURA (`gitcmd.atomic_write`). `add()` construye el nuevo
# contenido a partir de esa lectura ya vieja, asi que su propia
# escritura pisa lo que la edicion ajena acaba de dejar -- una perdida
# silenciosa de esa edicion. Contrato: tras `add()`, las DOS lineas
# (la ajena y la propia) tienen que estar presentes, tanto en el
# fichero como en el commit real que `add()` produce.
#
# FRONTERA DOCUMENTADA [I-003, ronda de Moriarty 2026-08-23, relayada por
# el coordinador -- no un hallazgo nuevo de este pase, una aclaracion de
# alcance]: `rules.py::add()` (produccion) cierra esto leyendo el
# fichero DOS VECES -- una lectura temprana y una "relectura final" lo
# mas cerca posible de `gitcmd.atomic_write()` (ver
# `_read_current_rules_content()` en `rules.py`). El test de mas abajo
# parchea `Path.read_text` filtrando por `self.name == "rules.md"`, asi
# que dispara en LAS DOS lecturas por igual -- la escritura externa del
# hilo se libera durante la PRIMERA (la temprana), y para cuando la
# SEGUNDA (la relectura final) se ejecuta, esa escritura externa ya
# aterrizo y se recoge fresca. Esto pina exactamente la mitad CERRADA
# del contrato: una edicion externa que aterriza ANTES de la relectura
# final de `add()` nunca se pierde. Una edicion externa que aterrizara
# DENTRO del instante relectura-final -> `atomic_write()` (una ventana
# de un solo `read_text()` de ancho, sin ningun punto intermedio donde
# inyectar un tercer parón) queda FUERA de contrato -- ninguna cantidad
# de relecturas cierra ese ultimo instante sin una escritura
# compare-and-swap real a nivel de sistema de ficheros, que este
# proyecto no tiene ni necesita para su modelo de amenaza (un solo
# dueno, nunca dos procesos disparando al mismo tiempo por diseno). No
# se escribe aqui un test que exija esa ultima ventana cerrada -- pedir
# eso seria exigir lo imposible con las piezas que existen. El test de
# abajo, tal como esta escrito, ya es la prueba de la mitad que SI esta
# cerrada; no hace falta anadir nada mas.
# ---------------------------------------------------------------------------


class TestExternalEditLandingInsideAddIsNeverLost:
    def test_external_write_between_read_and_write_survives_in_file_and_commit(
        self, tmp_repo, rules_lib, monkeypatch
    ):
        root = Path(tmp_repo)
        rules_path = rules_lib.rules_file_path(root)

        # Siembra previa real: sin ella, `rules.md` todavia no existe y
        # `add()` toma la rama que NUNCA llama a `Path.read_text()` (usa
        # la cabecera fija en su lugar) -- el parche de mas abajo
        # necesita que exista un fichero real para leer, igual que
        # cualquier add() que no sea la primera regla del proyecto.
        with _cwd(tmp_repo):
            baseline = rules_lib.add(
                "baseline para forzar que add() lea el fichero de verdad",
                "claude",
                quote="none",
            )
        assert baseline.ok, f"la siembra base tiene que comitear limpia: {baseline.git_error!r}"

        read_done = threading.Event()
        external_done = threading.Event()
        original_read_text = Path.read_text

        def _delayed_read_text(self, *args, **kwargs):
            result = original_read_text(self, *args, **kwargs)
            # Filtra por nombre, no por igualdad exacta de Path: solo nos
            # interesa la lectura de `rules.md` que hace `add()` por
            # dentro, nunca cualquier otra lectura incidental que pudiera
            # ocurrir durante la misma llamada (p.ej. de git).
            if self.name == "rules.md":
                read_done.set()
                assert external_done.wait(timeout=10), (
                    "el hilo externo nunca senalizo que termino su escritura"
                )
            return result

        own_text = "never mock the database in integration tests"
        external_text = "MARK_EXTERNAL una edicion ajena que no pasa por add()"

        def _external_editor():
            assert read_done.wait(timeout=10), "add() nunca llego a leer el fichero"
            # E/S de bajo nivel, deliberadamente SIN pasar por rules_lib ni
            # por su candado -- un editor externo (a mano, otro proceso, un
            # merge de git) no conoce ese mecanismo.
            with open(rules_path, "r", encoding="utf-8") as fh:
                current = fh.read()
            with open(rules_path, "w", encoding="utf-8") as fh:
                fh.write(current + f"[remember][claude] \U0001F9E0 {external_text}\n")
            external_done.set()

        monkeypatch.setattr(Path, "read_text", _delayed_read_text)
        editor_thread = threading.Thread(target=_external_editor, daemon=True)
        editor_thread.start()

        with _cwd(tmp_repo):
            result = rules_lib.add(own_text, "user", quote="no mockees la base de datos")

        editor_thread.join(timeout=10)
        assert not editor_thread.is_alive(), "el hilo externo no termino a tiempo"

        assert result.ok, (
            f"add() no deberia fallar solo porque hubo una escritura externa "
            f"concurrente: {result.git_error!r}"
        )

        with _cwd(tmp_repo):
            content_after = rules_lib.read_all()
        assert own_text in content_after, (
            f"la propia regla de add() tiene que seguir en el fichero: {content_after!r}"
        )
        assert external_text in content_after, (
            f"la edicion externa desaparecio del fichero -- perdida silenciosa "
            f"que este contrato existe para prevenir: {content_after!r}"
        )

        rc_show, show_out, err_show = run_git(["show", f"HEAD:{_RULES_RELPATH}"], tmp_repo)
        assert rc_show == 0, f"git show fallo leyendo el blob comiteado: {err_show}"
        assert own_text in show_out and external_text in show_out, (
            f"el commit real de add() tiene que llevar LAS DOS lineas, no solo "
            f"la propia: {show_out!r}"
        )


# ---------------------------------------------------------------------------
# Tercer hallazgo de Moriarty: `--quote` sin sanear. Una cita con salto de
# linea parte la regla escrita en dos lineas fisicas (rompe el formato
# una-linea-por-regla que `_RULE_LINE_RE` exige) y corrompe la linea
# siguiente al releer; una cita desmesuradamente larga no tiene ningun
# tope, a diferencia del texto de la regla (`_TEXT_MAX_CHARS`). Las dos
# tienen que rebotar ANTES de tocar fichero o git -- una cita normal
# sigue intacta.
# ---------------------------------------------------------------------------


class TestQuoteIsSanitizedBeforeTouchingFileOrGit:
    def test_quote_with_a_newline_bounces_before_touching_file_or_git(
        self, tmp_repo, rules_lib
    ):
        root = Path(tmp_repo)
        text = "never mock the database in integration tests"
        broken_quote = "no mockees\nla base de datos"

        before = _commit_count(tmp_repo)
        with _cwd(root):
            result = rules_lib.add(text, "user", quote=broken_quote)

        assert result.ok is False, (
            f"una cita con salto de linea tiene que rebotar, nunca escribirse: {result!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, (
            "un rechazo de cita no puede haber producido ningun commit nuevo: "
            f"antes={before}, despues={after}"
        )

        rules_path = rules_lib.rules_file_path(root)
        assert not rules_path.exists(), (
            "una cita invalida tiene que rebotar ANTES de tocar el fichero -- "
            f"no deberia existir rules.md todavia: {rules_path!r}"
        )

    def test_an_oversized_quote_bounces_with_a_documented_cap(self, tmp_repo, rules_lib):
        root = Path(tmp_repo)
        text = "never mock the database in integration tests"
        # Deliberadamente muy por encima de cualquier tope razonable (el
        # propio texto de la regla ya tope a 200) -- no se fija aqui EL
        # numero exacto del tope de la cita (todavia no existe en
        # produccion, lo decide Ultron), solo que rebota y que el rechazo
        # cita un numero real, no un "demasiado larga" sin dato.
        oversized_quote = "x" * 2000

        before = _commit_count(tmp_repo)
        with _cwd(root):
            result = rules_lib.add(text, "user", quote=oversized_quote)

        assert result.ok is False, (
            f"una cita desmesurada tiene que rebotar, nunca escribirse: {result!r}"
        )
        assert result.rejections, (
            f"el rebote de una cita desmesurada tiene que traer un Rejection real, "
            f"no solo ok=False mudo: {result!r}"
        )
        combined = " ".join(
            f"{rej.title} {rej.body}" for rej in result.rejections
        )
        assert any(char.isdigit() for char in combined), (
            f"el rechazo tiene que citar un tope documentado (un numero real), "
            f"no solo decir que es demasiado larga: {combined!r}"
        )

        after = _commit_count(tmp_repo)
        assert after == before, (
            "un rechazo de cita no puede haber producido ningun commit nuevo: "
            f"antes={before}, despues={after}"
        )

        rules_path = rules_lib.rules_file_path(root)
        assert not rules_path.exists(), (
            "una cita invalida tiene que rebotar ANTES de tocar el fichero -- "
            f"no deberia existir rules.md todavia: {rules_path!r}"
        )

    def test_a_normal_quote_still_saves_and_commits_as_before(self, tmp_repo, rules_lib):
        """Regresion: saneando la cita no puede romper el caso normal ya
        cubierto por `TestGoodRuleEndsUpCommittedForReal` -- se repite
        aqui, en el mismo fichero que introduce el saneo, para que
        cualquier endurecimiento futuro de este bloque se vea obligado a
        pasar tambien por el camino feliz.
        """
        root = Path(tmp_repo)
        text = "stop summarizing what you just did at the end"
        normal_quote = "no resumas lo que acabas de hacer, ya lo he visto"

        before = _commit_count(tmp_repo)
        with _cwd(root):
            result = rules_lib.add(text, "claude", quote=normal_quote)

        assert result.ok, f"una cita normal no puede rebotar: {result.git_error!r}"
        after = _commit_count(tmp_repo)
        assert after == before + 1, (
            f"una cita normal tiene que seguir comiteando de verdad: antes={before}, "
            f"despues={after}"
        )
        with _cwd(root):
            content_after = rules_lib.read_all()
        assert text in content_after and normal_quote in content_after, (
            f"el texto y la cita normales tienen que seguir en el fichero: {content_after!r}"
        )
