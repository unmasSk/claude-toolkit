"""Contrato ROJO de `bin/memory/rule.py` -- PIEZAS.md Sec.10 (fila
`rule.py`).

`bin/memory/rule.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO: aceptacion, no barrido exhaustivo.

**No confundir con `tests/memory/test_rules.py`** (contrato de
`lib/memory/rules.py::add/read_all`, ya en produccion): este fichero
prueba el SCRIPT como proceso -- nunca importa `rules.add` para probarla,
solo usa `rules.read_all()` y `git log` reales como LECTORES para
verificar el efecto del script.

De donde sale cada cosa:

- PIEZAS.md Sec.10, fila `rule.py`: llama a `rules.add` · `rules.read_all`;
  admite "el texto de la regla"; imprime "confirmacion, o el fichero
  entero".
- `rules.py`, TEXTOS.md Sec.1.2, literal repetido: `gitmem rule "..."`
  y, con el tipo explicito, `gitmem rule "<texto>" --kind <user|claude>`
  (`rules.py::_reject_too_long`/`_reject_invalid_text`, comando de
  relanzamiento real ya en produccion).
- Encargo explicito de esta tarea: **"la regla acaba en los dos sitios --
  el registro y el fichero -- que es lo que ya costo un fallo hoy"**
  [`rules.py`, docstring: "el orden es el fichero primero, el commit
  despues... la escritura donde el sistema se puede corromper a si
  mismo"].

GRAMATICA DE CLI ASUMIDA para el modo lectura -- PIEZAS.md Sec.10 dice
que el script "imprime confirmacion, O el fichero entero" (dos salidas
posibles de la MISMA superficie, sin flag propio documentado). Se asume
que la ausencia del texto posicional dispara la lectura completa
(`rules.read_all()`), simetrico con como `argparse` ya trata un
posicional opcional en el resto del sistema -- ASUNCION documentada, no
hecho comprobado:

    rule.py "<texto>" --kind <user|claude>      # anade, confirma
    rule.py                                     # imprime rules.md entero

Round trip real, sin fabricar el texto esperado (unmassk-standards Sec.34):
"acaba en los dos sitios" se comprueba con DOS lectores reales,
independientes entre si y de lo que el script hizo por dentro: (1)
`rules.read_all()` (produccion) sobre el fichero, y (2) `git log` (vía
`run_git`, subprocess real) sobre el ULTIMO commit -- el mismo emoji real
(`emojis.CHANNEL_EMOJI["rule"]`, produccion) que ambos productores usan.

Con el script inexistente, todos estos tests fallan hoy por la misma
causa real: `python3 <ruta inexistente>` -- ver docstring de
`test_note_script.py` para el detalle del mensaje.
"""

import contextlib
import os

import pytest

from .conftest import (
    import_lib_memory_module,
    run_git,
    run_memory_script,
    seed_config_json,
)


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


def _git_head_message(repo):
    rc, out, err = run_git(["log", "-1", "--pretty=%B", "HEAD"], repo)
    assert rc == 0, f"git log fallo en el test: {err}"
    return out


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


class TestAcceptsAllFlagsWithoutBouncing:
    def test_text_and_kind_in_one_call(self, tmp_repo):
        # --quote anadido 2026-08-23 (endurecimiento del propietario, mismo
        # dia): --quote es ahora obligatorio para CUALQUIER kind -- sin el,
        # esta llamada rebotaria por falta de cita, no por lo que este test
        # quiere probar (que text+--kind se aceptan juntos sin reventar).
        rc, out, err = run_memory_script(
            "rule.py",
            [
                "never mock the database in integration tests",
                "--kind",
                "user",
                "--quote",
                "no mockees la base de datos en los tests de integracion",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


# RETIRADA 2026-08-23 [I-003, orden del propietario -- "regla guardada sin
# comitear = fallo silencioso", incidente real, revoca la decision de
# 2026-08-06]: `TestRuleEndsUpInTheFileNotInAnOwnCommit` (3 tests) vivia
# aqui y fijaba el contrato EXACTAMENTE CONTRARIO al que rige desde I-003
# -- afirmaba que `gitmem rule` "YA NO comitea" y que la linea queda como
# cambio sin comitear en el arbol de trabajo. Ese contrato queda revertido:
# desde I-003, `gitmem rule` tiene que producir un commit real o no decir
# "guardada" (ver `test_rule_commit_contract.py`, el contrato nuevo).
#
# Cobertura de sus 3 tests, verificada antes de retirar (ninguna se pierde
# en silencio):
#   - `test_rule_ends_up_in_the_file_and_creates_no_commit` -- su mitad
#     "la regla aparece en el fichero" (via `rules.iter_rule_texts()`) ya
#     esta cubierta bajo el contrato nuevo por
#     `test_rule_commit_contract.py::TestGoodRuleEndsUpCommittedForReal::
#     test_kind_user_creates_exactly_one_commit_and_a_clean_tree`. Su otra
#     mitad ("cero commits nuevos") es precisamente lo que I-003 revierte.
#   - `test_rule_leaves_the_file_as_a_real_uncommitted_change` -- afirmaba
#     `git status --porcelain` SUCIO tras guardar; el contrato nuevo pide
#     lo opuesto (arbol LIMPIO), ya cubierto por el mismo test de arriba
#     (`assert status_out.strip() == ""`).
#   - `test_a_later_gitmem_work_picks_up_the_pending_rule_line` -- su
#     premisa (`gitmem rule` deja una linea pendiente que un `gitmem work`
#     posterior recoge) deja de darse en el flujo normal una vez que
#     `gitmem rule` comitea por si solo: no queda nada pendiente que
#     recoger. Sin equivalente en el contrato nuevo, y sin perdida de
#     cobertura real -- la capacidad generica de `gitmem work --path` de
#     comitear exactamente la ruta dada, con el contenido real en el blob,
#     ya tiene su propio test independiente de `rule.py`
#     (`test_work_script.py::
#     TestAcceptsAllFlagsWithoutBouncingAndCommitsExactlyGivenPaths::
#     test_two_paths_and_an_issue_trailer_in_one_call`), que no dependia
#     de esta clase ni se ve afectado por su retirada.
#
# Mismo criterio que la retirada de `_restore_file_best_effort` en
# `test_rules.py` (2026-08-06): un test que ya no puede fallar por la causa
# que dice probar (aqui, lo contrario: uno que ahora DEBE fallar porque el
# contrato que fijaba fue revertido por orden real) es peor que ausente --
# se retira entero, con el motivo dejado por escrito, en vez de reescribirlo
# a la fuerza o dejarlo en rojo por sorpresa para quien lea la suite.


class TestReadingModeShowsTheWholeFileForReal:
    def test_no_positional_argument_prints_the_real_rules_file_entirely(self, tmp_repo):
        rc_add1, out_add1, err_add1 = run_memory_script(
            "rule.py",
            [
                "never mock the database in integration tests",
                "--kind",
                "user",
                "--quote",
                "no mockees la base de datos en los tests de integracion",
            ],
            cwd=tmp_repo,
        )
        assert rc_add1 == 0, f"siembra fallo: stdout={out_add1!r} stderr={err_add1!r}"

        rc_add2, out_add2, err_add2 = run_memory_script(
            "rule.py",
            [
                "stop summarizing what you just did at the end",
                "--kind",
                "claude",
                "--quote",
                "none",
            ],
            cwd=tmp_repo,
        )
        assert rc_add2 == 0, f"siembra fallo: stdout={out_add2!r} stderr={err_add2!r}"

        rc, out, err = run_memory_script("rule.py", [], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        assert "never mock the database in integration tests" in out
        assert "stop summarizing what you just did at the end" in out


class TestFailureExitsNonzeroWithRealTextNoTraceback:
    def test_a_rule_over_two_hundred_characters_is_rejected_with_the_real_numbers(
        self, tmp_repo
    ):
        too_long = "x" * 201
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script("rule.py", [too_long, "--kind", "user"], cwd=tmp_repo)
        assert rc != 0, f"una regla de 201 caracteres tiene que rebotar: stdout={out!r}"
        combined = out + err
        assert "Traceback" not in combined
        assert "201" in combined and "200" in combined, (
            f"el rechazo real de rules.py nombra la longitud real y el tope "
            f"(rules.py::_reject_too_long): {combined!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, "un rechazo no puede haber producido un commit"


class TestSimilarExistingRuleIsWarnedBeforeAdding:
    """El hueco real (comprobado por el orquestador con `grep`, no de
    oidas): `rules.similar_existing()` esta escrita y probada en
    `lib/memory/rules.py` (Sec.9.7 de por si, `test_rules.py`), pero
    `bin/memory/rule.py::_cmd_add` nunca la llama -- va derecho a
    `rules.add(text, kind)`. Cero llamadores en produccion en todo el
    repo.

    Contrato, PIEZAS.md Sec.9.7 lineas 1250/1256 y su tabla de tests:
    "`similar_existing` compara por texto, y su resultado se ensena
    antes de anadir: si ya hay uno casi igual, se dice y se decide" /
    "Quien lo llama: `bin/memory/rule.py` y el comando `/remember`" /
    fila "Un remember casi identico a uno existente se detecta y se
    avisa antes de anadirlo" contra el fallo real "la pila de 114
    recordatorios duplicados que ya paso en el sistema anterior".

    `[actualizado 2026-08-04]` TEXTOS.md Sec.1.11b YA tiene texto
    literal para este rechazo ("REGLA NO GUARDADA -- ya tienes una que
    dice casi lo mismo", con el dueno entre corchetes junto al emoji,
    p.ej. "🧠 [user] sé escueto, not yapping") -- escrito DESPUES de que
    el hueco de este test se detectara. El test sigue sin fijar ese
    literal completo a proposito: `bin/memory/rule.py` todavia no lo
    imprime (es otro encargo, ver mas abajo), y fijar hoy un texto que
    el script no produce lo dejaria en rojo por el motivo equivocado.
    Lo que SI exige, con la conducta minima ya construida
    (`rules.similar_existing()`, en produccion): que el texto de la
    regla parecida aparezca en la salida antes de anadir la nueva, y --
    reforzado ahora que el dueno viaja en el resultado -- que aparezca
    JUNTO a su dueno real, en la misma linea (`[user]`/`[claude]`, el
    mismo formato de corchetes que Sec.1.11b ya usa y que
    `_RULE_LINE_RE` ya reconoce en el fichero), nunca fundido ni
    cruzado con el dueno de otra regla.

    Lo que este test deliberadamente NO fija: el estado final de la
    regla nueva tras el aviso. El propietario ya decidio el criterio
    (TEXTOS.md Sec.1.11b, 2026-08-04: "si es casi repetida, dejar solo
    1" -- se rechaza, no se guardan las dos), pero `bin/memory/rule.py`
    todavia no lo implementa -- ese rechazo, con su codigo de salida y
    su texto exacto, es OTRO encargo, no este.

    El "casi igual" no lo inventa el test: se pide a `rules.similar_existing()`
    de produccion, en una llamada INDEPENDIENTE de la del script (mismo
    patron que el resto de este fichero usa `rules.read_all()`/`git log`
    como lectores reales) -- el candidato y la regla ya guardada
    difieren solo en singular/plural ("tests" vs "test"), medido en vivo
    con el tokenizador real: Jaccard 0.75 >= `vocabulary.SIMILARITY_THRESHOLD`
    (0.5).
    """

    def test_a_near_duplicate_rule_surfaces_the_existing_similar_text_before_saving(
        self, tmp_repo, rules_lib
    ):
        existing_text = "never mock the database in integration tests"
        rc_seed, out_seed, err_seed = run_memory_script(
            "rule.py",
            [existing_text, "--kind", "user", "--quote", "no mockees la base de datos"],
            cwd=tmp_repo,
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        candidate_text = "never mock the database in integration test"

        # Lector independiente, producción real, llamado ANTES del
        # script -- no lo que el script "cree" que es parecido, sino lo
        # que `rules.py` (ya en producción, ya con sus propios tests)
        # calcula para ese mismo candidato contra el fichero que el
        # script acaba de escribir.
        with _cwd(tmp_repo):
            expected_similar = rules_lib.similar_existing(candidate_text)
        assert ("user", existing_text) in expected_similar, (
            "precondicion del test: rules.similar_existing() (produccion) tiene "
            f"que devolver ('user', {existing_text!r}) como parecido a "
            f"{candidate_text!r} para que el resto del test tenga sentido; "
            f"devolvio {expected_similar!r}"
        )

        # --quote (2026-08-23): sin ella, esta llamada rebotaria por falta
        # de cita ANTES de llegar al chequeo de parecido -- el rechazo que
        # este test quiere ver (casi-duplicado) nunca se dispararia.
        rc, out, err = run_memory_script(
            "rule.py",
            [candidate_text, "--kind", "user", "--quote", "otra cita, la del candidato"],
            cwd=tmp_repo,
        )
        combined = out + err
        assert "Traceback" not in combined

        for similar_kind, similar_text in expected_similar:
            matching_lines = [line for line in combined.splitlines() if similar_text in line]
            assert matching_lines, (
                "el script tiene que ensenar la regla parecida ya guardada "
                f"antes de anadir la nueva (PIEZAS.md Sec.9.7); no aparecio "
                f"{similar_text!r} en la salida: stdout={out!r} stderr={err!r}"
            )
            assert any(f"[{similar_kind}]" in line for line in matching_lines), (
                f"el script tiene que nombrar el dueno real ({similar_kind!r}) "
                f"junto al texto de la regla parecida {similar_text!r} -- "
                f"TEXTOS.md Sec.1.11b los muestra en la misma linea "
                f"('🧠 [dueno] texto'); no aparecieron juntos en ninguna "
                f"linea: stdout={out!r} stderr={err!r}"
            )

    def test_the_script_never_swaps_the_owner_of_two_near_duplicate_rules(
        self, tmp_repo, rules_lib
    ):
        """Reforzado 2026-08-04, ya que `similar_existing()` ahora devuelve
        pareja `(kind, texto)`: mirror a nivel de script del test de
        `test_rules.py`
        `test_similar_existing_keeps_each_owner_separate_when_two_rules_differ_only_in_kind`.
        Dos reglas casi identicas por texto pero con dueno DISTINTO
        (`user` vs `claude`) no son la misma regla -- el aviso del
        script tiene que nombrar a cada una con su dueno real, nunca
        fundirlas ni cruzar la etiqueta de una con el texto de la otra.

        Fallo real que esto previene, a nivel de script (no solo de
        libreria): sin el dueno correcto, un aviso de "regla repetida"
        no puede distinguir una instruccion del propietario de una nota
        que Claude se dejo a si mismo -- el mismo bloqueo que
        `test_rules.py` ya cerro en la libreria, aqui verificado tal
        como lo va a ver quien ejecute el script de verdad.
        """
        user_text = "MARK_ROW5_SCRIPT be terse when answering questions"
        claude_text = "MARK_ROW5_SCRIPT be terse while answering questions"
        candidate_text = "MARK_ROW5_SCRIPT be terse answering questions"

        rc_seed_user, out_seed_user, err_seed_user = run_memory_script(
            "rule.py",
            [user_text, "--kind", "user", "--quote", "cita real del propietario"],
            cwd=tmp_repo,
        )
        assert rc_seed_user == 0, (
            f"siembra [user] fallo: stdout={out_seed_user!r} stderr={err_seed_user!r}"
        )

        rc_seed_claude, out_seed_claude, err_seed_claude = run_memory_script(
            "rule.py", [claude_text, "--kind", "claude", "--quote", "none"], cwd=tmp_repo
        )
        assert rc_seed_claude == 0, (
            f"siembra [claude] fallo: stdout={out_seed_claude!r} stderr={err_seed_claude!r}"
        )

        with _cwd(tmp_repo):
            expected_similar = rules_lib.similar_existing(candidate_text)
        assert ("user", user_text) in expected_similar, (
            "precondicion del test: similar_existing() (produccion) tiene que "
            f"devolver ('user', {user_text!r}); devolvio {expected_similar!r}"
        )
        assert ("claude", claude_text) in expected_similar, (
            "precondicion del test: similar_existing() (produccion) tiene que "
            f"devolver ('claude', {claude_text!r}); devolvio {expected_similar!r}"
        )

        # --quote (2026-08-23): igual razon que en el escenario anterior --
        # sin ella esta llamada rebota por falta de cita, no llega al
        # chequeo de parecido que este test verifica.
        rc, out, err = run_memory_script(
            "rule.py",
            [candidate_text, "--kind", "user", "--quote", "cita del candidato mezclado"],
            cwd=tmp_repo,
        )
        combined = out + err
        assert "Traceback" not in combined

        for similar_kind, similar_text in expected_similar:
            matching_lines = [line for line in combined.splitlines() if similar_text in line]
            assert matching_lines, (
                "el script tiene que ensenar cada regla parecida ya guardada "
                f"antes de anadir la nueva; no aparecio {similar_text!r} en "
                f"la salida: stdout={out!r} stderr={err!r}"
            )
            assert any(f"[{similar_kind}]" in line for line in matching_lines), (
                f"el script tiene que nombrar el dueno real ({similar_kind!r}) "
                f"junto al texto de {similar_text!r} -- ni fundirlo ni "
                f"cruzarlo con el otro dueno: stdout={out!r} stderr={err!r}"
            )

    def test_an_unrelated_rule_does_not_trigger_a_spurious_similar_warning(
        self, tmp_repo, rules_lib
    ):
        unrelated_existing = "never mock the database in integration tests"
        rc_seed, out_seed, err_seed = run_memory_script(
            "rule.py",
            [unrelated_existing, "--kind", "user", "--quote", "no mockees la base de datos"],
            cwd=tmp_repo,
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        candidate_text = "stop summarizing what you just did at the end"

        with _cwd(tmp_repo):
            expected_similar = rules_lib.similar_existing(candidate_text)
        assert expected_similar == (), (
            "precondicion del test: los dos textos no deberian parecerse; "
            f"rules.similar_existing() devolvio {expected_similar!r}"
        )

        rc, out, err = run_memory_script(
            "rule.py",
            [candidate_text, "--kind", "user", "--quote", "deja de resumir, ya lo he visto"],
            cwd=tmp_repo,
        )
        combined = out + err
        assert "Traceback" not in combined
        assert unrelated_existing not in combined, (
            "sin ninguna regla parecida de verdad, el texto de la regla "
            f"anterior no deberia aparecer en la salida: {combined!r}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_accented_rule_survives_a_restricted_console_encoding(self, tmp_repo):
        rc, out, err = run_memory_script(
            "rule.py",
            [
                "nunca commitear sin revisar el diff primero, cuesta caro",
                "--kind",
                "claude",
                "--quote",
                "none",
            ],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"una regla valida no deberia fallar bajo cp1252: {combined!r}"
