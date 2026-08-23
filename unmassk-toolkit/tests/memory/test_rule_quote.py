"""Contrato ROJO -- `gitmem rule "<texto>"` exige la cita LITERAL del
propietario, sea cual sea el `--kind`.

Encargo aprobado el 2026-08-23, ENDURECIDO el mismo dia (segundo mensaje
del propietario, tras revisar el primer borrador): flag nuevo `--quote
"<palabras literales de Bex>"`, obligatorio al anadir CUALQUIER regla --
`[user]` (el default) Y `[claude]` por igual. La unica salida es el
literal `--quote none` ("Claude se pone una regla a si mismo, el
propietario no dijo nada") -- con ese valor exacto, la regla se guarda
SIN parte de cita, para cualquiera de los dos `kind` (incluido `user`,
de forma explicita: alguien puede querer una regla `[user]` sin cita a
proposito, y `--quote none` es como lo declara sin ambiguedad). Motivo
citado del primer borrador, sigue vigente: el 2026-08-20 Claude guardo
una regla `[user]` ("jamas guias") que el propietario nunca dijo -- la
regla queda respaldada por sus propias palabras, no por una parafrasis
de Claude; el endurecimiento extiende esa misma garantia a las reglas
`[claude]`, que antes se escapaban sin cita por defecto.

Contra que codigo se escribe este contrato -- leido antes de escribir
ni una linea de test:

  - `lib/memory/rules.py::add(text, kind)` -- HOY solo dos parametros, sin
    `quote`. `_reject_invalid_kind`/`_reject_invalid_text`/`_reject_too_long`
    ya fijan el patron de rechazo (via `rejection.build()`, con `what`/
    `options`/`command`) que un rechazo nuevo por cita ausente tiene que
    seguir -- este fichero no fija el `kind` exacto de ese rechazo (eso lo
    elige Ultron), solo que aparezca por el CAMINO real: `rejection.
    render_terminal()` imprime siempre "Relanza:" seguido del comando de
    relanzamiento (`rejection.py::_render`, ya en produccion, comun a los
    tres rechazos existentes de este modulo).
  - `bin/memory/rule.py::_parse_args` -- HOY declara solo `text` y
    `--kind`; `--quote` NO EXISTE. Por eso, HOY, cualquier llamada de este
    fichero que use `--quote` revienta con el error de argparse
    "unrecognized arguments: --quote" -- ese es el ROJO real de los
    escenarios 2/4/6/7 de mas abajo, no un rechazo de la aduana.

CONTRADICCION DETECTADA CONTRA EL ENCARGO -- reportada, no resuelta en
silencio (CLAUDE.md, "un hueco puede ser deliberado, se pregunta, no se
rellena"; "manda el codigo" cuando un texto y el codigo discrepan): el
encargo pide, para el escenario 2, "exactamente un commit nuevo cuyo
mensaje lleve la regla". `lib/memory/rules.py::add()` (docstring, linea
~20, decision del propietario del 2026-08-06, la mas reciente de las dos
fechas) dice literalmente que `add()` es HOY "UN SOLO PASO... sin tocar
git para nada, ni un commit vacio ni un commit con el fichero como
pathspec", y `tests/memory/test_rule_script.py::
TestRuleEndsUpInTheFileNotInAnOwnCommit` ya fija esa conducta como
regresion ("gitmem rule ya no debe crear ningun commit"). Pedir aqui "un
commit nuevo" chocaria de frente con ese test ya en verde -- las dos
cosas no pueden ser ciertas a la vez. Este fichero seria la NUEVA
verdad si el encargo pretende revertir esa decision, pero eso excede el
alcance declarado ("--quote obligatorio"), asi que no se asume: el
escenario 2 de aqui abajo comprueba, en su lugar, la conducta que el
codigo actual ya garantiza para cualquier `add()` con exito (HEAD no se
mueve, `rules.md` queda como cambio sin comitear) y dejo esta nota para
que quien orquesta decida.

Todo lo demas del encargo se escribe tal cual: formato exacto de la
linea con cita (`[remember][user] <emoji> <texto> — «<cita>»`), la
escapatoria literal `--quote none` (para `[claude]` Y para `[user]`,
sin parte de cita en la linea resultante), cita vacia/solo espacios
rechazada igual que ausente (`--quote none` es la UNICA forma valida de
"sin cita" -- una cadena vacia o en blanco sigue sin ser una cita real),
lectura hacia atras compatible con lineas antiguas sin cita, y que el
detector de casi-duplicados siga mirando solo el TEXTO (nunca la cita).

Como el resto de este directorio: SCRIPT como proceso real
(`run_memory_script`, nunca importando `rules.add`/`_cmd_add` para
probarlas), lectores de produccion reales (`rules.read_all()`,
`rules.iter_rule_texts()`, `rules.similar_existing()`, `git` de verdad
via `run_git`) -- nunca un fixture que fabrique el resultado esperado a
mano (unmassk-standards Sec.34).
"""

import contextlib
import os
from pathlib import Path

import pytest

from .conftest import import_lib_memory_module, run_git, run_memory_script


@contextlib.contextmanager
def _cwd(path):
    """Mismo helper que `test_rule_script.py`/`test_rules.py`: cambia el
    cwd del proceso durante el bloque y lo restaura siempre."""
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


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _rules_file_exists(rules_lib, repo):
    return rules_lib.rules_file_path(Path(repo)).exists()


# ---------------------------------------------------------------------------
# Escenario 1 -- regla [user] (kind por defecto) sin --quote rebota.
# ---------------------------------------------------------------------------


class TestUserRuleWithoutQuoteIsRejected:
    """HOY (sin `--quote` en `_parse_args`) esta llamada tiene EXITO --
    `rc == 0`, la regla se guarda sin cita. Ese es el ROJO real de este
    escenario: se espera rechazo (`rc != 0`) y hoy no lo hay.
    """

    def test_missing_quote_bounces_with_no_traceback_and_shows_the_relaunch_shape(
        self, tmp_repo, rules_lib
    ):
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script("rule.py", ["ser breve"], cwd=tmp_repo)
        combined = out + err

        assert rc != 0, (
            "una regla [user] sin --quote tiene que rebotar -- hoy se guarda "
            f"sin cita, rc={rc}, stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in combined, f"rechazo con traza de pila: {combined!r}"
        assert "--quote" in combined, (
            f"el rechazo tiene que nombrar el flag que falta, --quote: {combined!r}"
        )
        # Misma forma que los tres rechazos ya en produccion de este modulo
        # (rejection.py::_render, comun a los tres): "Relanza:" seguido del
        # comando de relanzamiento real.
        assert "Relanza:" in combined, (
            f"el rechazo no ensena la forma de relanzamiento (rejection.py::_render, "
            f"'Relanza:' + comando): {combined!r}"
        )
        assert "gitmem rule" in combined, (
            f"el comando de relanzamiento no menciona 'gitmem rule': {combined!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, "un rechazo no puede haber producido ningun commit"
        assert not _rules_file_exists(rules_lib, tmp_repo), (
            "un rechazo por falta de cita no puede haber tocado rules.md -- "
            "el fichero no deberia existir todavia"
        )


# ---------------------------------------------------------------------------
# Escenario 2 -- regla [user] CON --quote: se guarda, una linea con las
# dos cosas separadas visiblemente. Formato exacto elegido por el encargo:
# "[remember][user] 🧠 ser breve — «no te enrolles, tio»".
# ---------------------------------------------------------------------------


class TestUserRuleWithQuoteIsSavedWithBothTexts:
    """HOY revienta con "unrecognized arguments: --quote" (argparse) --
    `--quote` no existe todavia en `_parse_args`. Ese es el ROJO real.
    """

    def test_rule_and_literal_quote_land_in_one_line_visibly_separated(
        self, tmp_repo, rules_lib, emojis_lib
    ):
        text = "ser breve"
        quote = "no te enrolles, tio"

        rc, out, err = run_memory_script(
            "rule.py", [text, "--quote", quote], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in (out + err)

        with _cwd(tmp_repo):
            content = rules_lib.read_all()

        assert text in content, f"el texto de la regla no aparece en rules.md: {content!r}"
        assert quote in content, f"la cita literal no aparece en rules.md: {content!r}"
        assert "«" in content and "»" in content, (
            f"la cita no queda visiblemente separada del texto (se esperaban "
            f"guillemets «»): {content!r}"
        )

        emoji = emojis_lib.CHANNEL_EMOJI["rule"]
        expected_line = f"[remember][user] {emoji} {text} — «{quote}»"
        assert expected_line in content, (
            f"la linea escrita no casa con el formato exacto elegido por el "
            f"encargo -- esperado {expected_line!r}, fichero real: {content!r}"
        )

        with _cwd(tmp_repo):
            texts = rules_lib.iter_rule_texts(content)
        assert f"{text} — «{quote}»" in texts, (
            "iter_rule_texts() (el UNICO reconocimiento de linea de regla del "
            f"sistema) no reconoce la linea con cita como una regla valida: {texts!r}"
        )

    def test_a_successful_add_moves_no_head_and_leaves_the_file_uncommitted(
        self, tmp_repo
    ):
        """Ver la nota de contradiccion en el docstring del modulo: el
        encargo pide "exactamente un commit nuevo" para este escenario,
        pero `rules.add()` (produccion, decision del propietario del
        2026-08-06) nunca comitea nada -- lo comprueba ya
        `test_rule_script.py::TestRuleEndsUpInTheFileNotInAnOwnCommit`.
        Esta pieza se queda con la conducta que el codigo YA garantiza
        (HEAD sin mover, `rules.md` como cambio sin comitear) en vez de
        pedir un commit que el propio modulo declara retirado -- no se
        inventa una tercera conducta.
        """
        rules_relpath = ".claude/project-memory/rules.md"
        _rc, head_before, _err = run_git(["rev-parse", "HEAD"], tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["ser breve", "--quote", "no te enrolles, tio"], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        _rc, head_after, _err = run_git(["rev-parse", "HEAD"], tmp_repo)
        assert head_after == head_before, (
            "gitmem rule con --quote no debe crear ningun commit -- "
            f"antes={head_before!r} despues={head_after!r}"
        )

        rc_status, status_out, err_status = run_git(
            ["status", "--porcelain", "--", rules_relpath], tmp_repo
        )
        assert rc_status == 0, f"git status fallo en el test: {err_status}"
        assert status_out.strip(), (
            "rules.md deberia quedar como cambio sin comitear tras gitmem rule "
            f"--quote -- git status --porcelain no muestra nada: {status_out!r}"
        )


# ---------------------------------------------------------------------------
# Escenario 3 -- ENDURECIDO 2026-08-23 (segundo mensaje del propietario):
# regla [claude] SIN --quote ahora rebota IGUAL que una [user] sin --quote
# -- ya no hay escape implicito por omision, solo el literal --quote none.
# ---------------------------------------------------------------------------


class TestClaudeRuleWithoutQuoteIsNowRejectedToo:
    """Version original de este escenario (retirada, no solo cambiada de
    valor esperado): pedia `rc == 0` para `--kind claude` sin `--quote`,
    misma conducta que una regla `[user]`. El propietario endurecio el
    encargo el mismo dia: ahora TODA regla exige `--quote`, sin excepcion
    implicita por `kind` -- la unica excepcion es explicita
    (`--quote none`, escenario 3b/3c mas abajo). Mismas aserciones que
    `TestUserRuleWithoutQuoteIsRejected` de arriba, aplicadas a `--kind
    claude`, para que el rechazo no dependa de un `kind` concreto.
    """

    def test_missing_quote_bounces_for_claude_kind_too(self, tmp_repo, rules_lib):
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["leer los patrones antes", "--kind", "claude"], cwd=tmp_repo
        )
        combined = out + err

        assert rc != 0, (
            "una regla [claude] sin --quote tiene que rebotar igual que una "
            f"[user] -- rc={rc}, stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in combined, f"rechazo con traza de pila: {combined!r}"
        assert "--quote" in combined, (
            f"el rechazo tiene que nombrar el flag que falta, --quote: {combined!r}"
        )
        assert "Relanza:" in combined, (
            f"el rechazo no ensena la forma de relanzamiento (rejection.py::_render, "
            f"'Relanza:' + comando): {combined!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, "un rechazo no puede haber producido ningun commit"
        assert not _rules_file_exists(rules_lib, tmp_repo), (
            "un rechazo por falta de cita no puede haber tocado rules.md"
        )


# ---------------------------------------------------------------------------
# Escenario 3b/3c -- la UNICA salida sin cita: el literal `--quote none`.
# Vale para las dos `kind` -- para `[claude]` es el caso previsto por el
# encargo ("Claude se pone una regla a si mismo"), para `[user]` es la
# declaracion explicita de que esa regla concreta no lleva cita, a
# proposito, no por omision.
# ---------------------------------------------------------------------------


def test_claude_rule_with_quote_none_is_accepted_without_a_quote_part(tmp_repo, rules_lib):
    text = "leer los patrones antes"

    rc, out, err = run_memory_script(
        "rule.py", [text, "--kind", "claude", "--quote", "none"], cwd=tmp_repo
    )
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    assert "Traceback" not in (out + err)

    with _cwd(tmp_repo):
        content = rules_lib.read_all()
        texts = rules_lib.iter_rule_texts(content)

    assert text in texts, (
        f"la regla [claude] con --quote none no aparece (sin cita) en "
        f"iter_rule_texts(): {texts!r}"
    )
    assert "«" not in content.split(text, 1)[-1].split("\n", 1)[0], (
        f"--quote none no deberia dejar parte de cita en la linea: {content!r}"
    )
    assert "none" not in content.split(text, 1)[-1].split("\n", 1)[0], (
        f"el literal 'none' es solo la SEÑAL de 'sin cita' -- no debe colarse "
        f"como si fuera el texto de una cita real: {content!r}"
    )


def test_user_rule_with_quote_none_is_also_accepted_explicitly(tmp_repo, rules_lib):
    """Mismo escape para `[user]` -- declarar `--quote none` a proposito
    (no simplemente omitir `--quote`, que sigue rebotando -- escenario 1)
    es una forma valida de decir "esta regla [user] no lleva cita", con
    el mismo resultado que la version [claude]: sin parte de cita.
    """
    text = "ser breve"

    rc, out, err = run_memory_script(
        "rule.py", [text, "--quote", "none"], cwd=tmp_repo
    )
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    assert "Traceback" not in (out + err)

    with _cwd(tmp_repo):
        content = rules_lib.read_all()
        texts = rules_lib.iter_rule_texts(content)

    assert text in texts, (
        f"la regla [user] con --quote none no aparece (sin cita) en "
        f"iter_rule_texts(): {texts!r}"
    )
    assert "«" not in content.split(text, 1)[-1].split("\n", 1)[0], (
        f"--quote none no deberia dejar parte de cita en la linea: {content!r}"
    )


# ---------------------------------------------------------------------------
# Escenario 4 -- regla [claude] CON --quote (opcional, se acepta si se da):
# la linea lleva la cita igual que una [user].
# ---------------------------------------------------------------------------


def test_claude_rule_with_quote_carries_the_quote_too(tmp_repo, rules_lib):
    rc, out, err = run_memory_script(
        "rule.py", ["x", "--kind", "claude", "--quote", "y"], cwd=tmp_repo
    )
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    assert "Traceback" not in (out + err)

    with _cwd(tmp_repo):
        content = rules_lib.read_all()

    assert "«y»" in content, (
        f"una regla [claude] con --quote tiene que llevar la cita igual que "
        f"una [user]: {content!r}"
    )


# ---------------------------------------------------------------------------
# Escenario 5 -- lectura hacia atras: `gitmem rule` (sin args) imprime el
# fichero entero, la linea con cita sale intacta, Y una linea ANTIGUA sin
# cita (formato de antes de este cambio) sigue imprimiendose y sigue
# contando para iter_rule_texts() -- las reglas viejas no dejan de ser
# validas.
# ---------------------------------------------------------------------------


def test_reading_back_shows_old_format_and_new_quoted_lines_together(
    tmp_repo, rules_lib, emojis_lib
):
    root = Path(tmp_repo)
    old_text = "regla vieja"
    emoji = emojis_lib.CHANNEL_EMOJI["rule"]

    # Siembra directa de una linea EN FORMATO ANTIGUO (sin cita) -- no via
    # rule.py, para no depender de ninguna conducta todavia sin construir.
    rules_path = rules_lib.rules_file_path(root)
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(f"[remember][user] {emoji} {old_text}\n", encoding="utf-8")

    new_text = "regla nueva con cita"
    new_quote = "cita literal de verdad"
    rc_add, out_add, err_add = run_memory_script(
        "rule.py", [new_text, "--quote", new_quote], cwd=tmp_repo
    )
    assert rc_add == 0, f"stdout={out_add!r} stderr={err_add!r}"

    rc_read, out_read, err_read = run_memory_script("rule.py", [], cwd=tmp_repo)
    assert rc_read == 0, f"stdout={out_read!r} stderr={err_read!r}"
    assert "Traceback" not in (out_read + err_read)

    assert old_text in out_read, (
        f"la regla vieja (sin cita) desaparecio de la lectura completa: {out_read!r}"
    )
    assert new_text in out_read and new_quote in out_read, (
        f"la regla nueva con cita no sale intacta en la lectura completa: {out_read!r}"
    )

    with _cwd(tmp_repo):
        texts = rules_lib.iter_rule_texts(rules_lib.read_all())
    assert old_text in texts, (
        "iter_rule_texts() dejo de reconocer una linea vieja sin cita -- las "
        f"reglas anteriores a este cambio tienen que seguir siendo validas: {texts!r}"
    )


# ---------------------------------------------------------------------------
# Escenario 6 -- cita vacia o solo espacios se rechaza igual que ausente.
# ---------------------------------------------------------------------------


class TestBlankQuoteIsRejectedLikeMissing:
    """HOY revienta con "unrecognized arguments: --quote" (argparse) --
    mismo ROJO real que el escenario 2, aqui con dos valores distintos de
    --quote en la misma llamada.
    """

    @pytest.mark.parametrize("blank_quote", ["", "   "])
    def test_blank_quote_bounces_without_writing_anything(
        self, tmp_repo, rules_lib, blank_quote
    ):
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "rule.py", ["ser breve", "--quote", blank_quote], cwd=tmp_repo
        )
        combined = out + err

        assert rc != 0, (
            f"una cita vacia o solo espacios ({blank_quote!r}) tiene que rebotar "
            f"igual que una cita ausente: rc={rc}, stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in combined
        assert "--quote" in combined
        # No basta con "rc != 0": hoy, CUALQUIER uso de --quote ya revienta
        # con el error generico de argparse ("unrecognized arguments"),
        # porque el flag ni siquiera existe todavia -- eso satisfaria las
        # aserciones de arriba sin haber construido ningun rechazo
        # semantico real. Se exige explicitamente el rechazo de negocio
        # (mismo patron que el escenario 1: `rejection.build()` +
        # `rejection.render_terminal()`, "Relanza:" + comando), y se
        # descarta el mensaje generico de argparse -- asi este test es
        # ROJO hoy por el motivo correcto (--quote no existe) y solo se
        # pondra en VERDE cuando --quote exista Y rechace en blanco de
        # verdad, nunca antes por casualidad.
        assert "unrecognized arguments" not in combined, (
            f"el rechazo tiene que ser el rechazo de negocio por cita en blanco, "
            f"no el error generico de argparse por --quote inexistente: {combined!r}"
        )
        assert "Relanza:" in combined, (
            f"el rechazo no ensena la forma de relanzamiento (rejection.py::_render, "
            f"'Relanza:' + comando): {combined!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, "un rechazo no puede haber producido ningun commit"
        assert not _rules_file_exists(rules_lib, tmp_repo), (
            "una cita en blanco no puede haber tocado rules.md"
        )


# ---------------------------------------------------------------------------
# Escenario 7 -- el rechazo por casi-duplicado (Jaccard sobre el TEXTO,
# rules.py::similar_existing) tiene que seguir disparando aunque las citas
# sean distintas -- la cita nunca debe colarse en el calculo de parecido,
# ni tapar un duplicado real.
# ---------------------------------------------------------------------------


def test_near_duplicate_rejection_fires_even_with_different_quotes(tmp_repo, rules_lib):
    """Mismo par de textos (singular/plural) que ya prueba
    `test_rule_script.py::test_a_near_duplicate_rule_surfaces_the_existing_
    similar_text_before_saving` -- Jaccard 0.75, por encima del
    `vocabulary.SIMILARITY_THRESHOLD` (0.5) -- aqui con una cita DISTINTA
    en cada llamada para comprobar que el parecido se sigue midiendo solo
    sobre el texto de la regla, nunca sobre la cita.
    """
    existing_text = "never mock the database in integration tests"
    rc_seed, out_seed, err_seed = run_memory_script(
        "rule.py",
        [existing_text, "--quote", "no mockees la base de datos en tests"],
        cwd=tmp_repo,
    )
    assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

    candidate_text = "never mock the database in integration test"
    candidate_quote = "una cita completamente distinta, sin relacion con la anterior"

    with _cwd(tmp_repo):
        expected_similar = rules_lib.similar_existing(candidate_text)
    assert ("user", existing_text) in expected_similar, (
        "precondicion del test: similar_existing() (produccion) tiene que seguir "
        f"marcando {candidate_text!r} como parecido a {existing_text!r} por TEXTO, "
        f"cita aparte; devolvio {expected_similar!r}"
    )

    rc, out, err = run_memory_script(
        "rule.py",
        [candidate_text, "--quote", candidate_quote],
        cwd=tmp_repo,
    )
    combined = out + err
    assert "Traceback" not in combined
    assert rc != 0, (
        "una regla casi identica en TEXTO tiene que rebotar por parecido aunque "
        f"la cita sea distinta: stdout={out!r} stderr={err!r}"
    )
    assert existing_text in combined, (
        f"el rechazo por parecido no ensena el texto de la regla ya guardada: {combined!r}"
    )

    with _cwd(tmp_repo):
        texts = rules_lib.iter_rule_texts(rules_lib.read_all())
    # No se usa "candidate_text not in content" (substring sobre el
    # fichero entero): "...integration test" es un PREFIJO literal de
    # "...integration tests" (la regla ya sembrada), asi que esa
    # comprobacion daria una falsa alarma incluso si el rechazo funciona
    # bien -- coincidencia de subcadena, no una entrada real. Se compara
    # contra las entradas YA PARSEADAS por iter_rule_texts() (produccion),
    # por igualdad exacta o por el mismo texto seguido de su propia cita.
    candidate_landed = any(
        entry == candidate_text or entry.startswith(f"{candidate_text} — «")
        for entry in texts
    )
    assert not candidate_landed, (
        "la regla casi duplicada se guardo pese al rechazo -- la cita distinta "
        f"no puede tapar un duplicado real de texto: {texts!r}"
    )
