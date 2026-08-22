"""Contrato de aceptacion, en ROJO -- el agujero que encontro Moriarty:
`lib/memory/report_render.py` nunca enseña `Note.issue`, para ningun
tipo de nota, en los DOS caminos que de verdad se usan para buscar
(`gitmem search <zona>` y `gitmem search <palabra>`, despachados por
`bin/memory/search.py` via `render_zone`/`render_word`).

Modo test-first, PASE DE CONTRATO (antes de que Ultron toque
produccion): granularidad de aceptacion, no el barrido exhaustivo de
ramas -- ese llega en el pase de endurecimiento, tras la
implementacion real.

QUE YA ESTA HECHO, leido en produccion antes de escribir esto (no
supuesto): D-044/D-045 (2026-08-22) ya abrieron `--issue` a los siete
tipos de nota en `lib/memory/vocabulary.py::TYPES[*].allowed_fields`, y
`report_render_note.py::_note_fields()` (el molde de `search.py --id`)
ya pinta `Issue: #N` para cualquier tipo -- confirmado leyendo el
fichero: `if note.issue is not None: lines.append(f"{_BODY_INDENT}
Issue: #{note.issue}")`, sin condicion de tipo, con el comentario
explicito "issue ya no es solo de M". Ese camino (por identificador) ya
sale bien HOY, ver `test_note_issue_field.py::
TestIssueSurvivesTheRoundTripThroughSearchById`.

EL AGUJERO REAL, en `lib/memory/report_render.py` (leido linea a
linea): ninguno de los siete bloques por tipo referencia `note.issue`:
`_restriction_block` (~111), `_blocker_block` (~122), `_decision_block`
(~130), `_memo_block` (~142), `_incident_block` (~146),
`_question_block` (~150), y `_cluster_block` (~157, el que arma el
racimo D/X dentro de `render_zone`). Consecuencia: guardas una nota con
`--issue 8181` (el numero entra bien en el commit, verificado por
`test_note_issue_field.py`), y al buscar por zona o por palabra -- el
camino que se usa de verdad, porque por identificador solo se busca si
ya se conoce el identificador -- la nota sale entera SIN el numero.
Perdida silenciosa de un dato que si se guardo.

FORMATO, no inventado aqui -- fijado por lo que YA pinta
`report_render_note.py::_note_fields()` para el mismo campo:
`"Issue: #{numero}"`, un solo espacio tras los dos puntos, sin columna
compartida con `Why:`/`Description:`/`Keys:` (esas SI se alinean; ver
`_BODY_INDENT`/`awaits:` en ese fichero, mismo criterio). Dentro de
`report_render.py` los bloques por tipo ya usan una sangria fija de
nueve espacios para su propia segunda linea (`"         Why: ..."`,
`"         Origin: ..."`, `"         Description: ..."`,
`"         awaits: ..."` -- verificado con `python3` letra a letra, no
a ojo) -- este contrato exige la MISMA sangria de nueve espacios para
`Issue:`, para que las dos superficies (por-id y por-zona/palabra) no
se contradigan en como se ve un campo de commit dentro del cuerpo de
una nota.

TRES TIPOS DE LOS SIETE, uno de decision, uno de incidencia y uno de
restriccion -- el encargo los pide explicitos, respetando los campos
obligatorios de cada uno segun `vocabulary.TYPES[*].required_fields`:
D exige `--why`; R exige `--stops yes`; I no exige nada extra.

COMO SE EVITA LA RED DE VERDAD PARA `gh issue view`
[unmassk-standards Sec.34.5]: mismo `gh` FALSO en el PATH del proceso
hijo que ya documenta `test_note_issue_field.py::_fake_gh_dir` --
version reducida aqui (solo el caso "existe", nunca "no existe": el
rechazo de issue inexistente ya tiene su propio contrato en ese otro
fichero, no se duplica).

SIEMBRA E IDA Y VUELTA REALES [unmassk-standards Sec.34]: cada nota
entra por un proceso REAL de `note.py` (`run_memory_script`,
conftest.py) -- nunca `notes.write()` llamado a mano ni un `Note`
construido en memoria. La comprobacion es contra la salida REAL de
`search.py` (mismo binario que `gitmem search` despacha), nunca contra
un objeto `ZoneReport`/`WordReport` en memoria. El numero que se
comprueba en cada aserto es la variable `issue_number` que este mismo
test le paso a `note.py --issue`, nunca un literal tecleado aparte --
ida y vuelta real, no un candidato fabricado.

Ningun test de aqui toca produccion. Si algo de esto no encajara con lo
que Ultron acaba implementando, es un hallazgo, no un arreglo silencioso
aqui.
"""

import os
import sys

import pytest

from .conftest import (
    extract_note_id,
    path_without_real_gh,
    run_memory_script,
    seed_zones_json,
)

# CI incident 2026-08-22 (conftest.py::path_without_real_gh): en Windows,
# `subprocess.run(["gh", ...])` sin `shell=True` (produccion, no tocada
# aqui) nunca resuelve un fichero sin extension `.exe` via CreateProcess
# -- estructural, no arreglable desde el lado del test. Se salta
# explicito, nunca en silencio, en los tests que dependen de que el `gh`
# falso GANE la resolucion de `PATH`.
_WIN_GH_SKIP_REASON = (
    "tecnica de gh falso en PATH: en Windows, subprocess.run(['gh', ...]) "
    "sin shell=True nunca resuelve un fichero sin extension .exe -- "
    "estructural, no arreglable sin tocar validator_issue.py (fuera de "
    "alcance de Dante)"
)
_skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32", reason=_WIN_GH_SKIP_REASON
)

_ZONE1 = "reportissuezoneone"
_ZONE2 = "reportissuezonetwo"


def _fake_gh_dir(tmp_path, issue_number):
    """`gh` FALSO, ejecutable, solo entiende `gh issue view <N> --json
    number` para EXACTAMENTE `issue_number` y responde returncode 0 --
    version reducida de `test_note_issue_field.py::_fake_gh_dir` (mismo
    criterio, unmassk-standards Sec.34.5: imita la FORMA de la
    herramienta externa real, no su logica; el caso "no existe" ya vive
    en el otro fichero, no se duplica aqui).
    """
    gh_dir = tmp_path / "fake-gh-bin"
    gh_dir.mkdir(exist_ok=True)
    gh_path = gh_dir / "gh"
    script = f'''#!/usr/bin/env python3
import sys

ISSUE = "{issue_number}"

args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view" and args[2] == ISSUE:
    sys.stdout.write('{{"number": ' + ISSUE + '}}')
    sys.exit(0)

sys.stderr.write("fake gh (dante test double): unexpected invocation " + repr(args))
sys.exit(97)
'''
    gh_path.write_text(script, encoding="utf-8")
    gh_path.chmod(0o755)
    return str(gh_dir)


def _fake_gh_dir_multi(tmp_path, issue_numbers):
    """Igual que `_fake_gh_dir`, pero acepta VARIAS issues existentes en
    el mismo `gh` falso -- necesario para el test del racimo, que
    guarda dos notas reales (raiz + hija) con dos numeros de issue
    DISTINTOS en la misma llamada a `note.py`/mismo repo."""
    gh_dir = tmp_path / "fake-gh-bin-multi"
    gh_dir.mkdir(exist_ok=True)
    gh_path = gh_dir / "gh"
    known = tuple(str(n) for n in issue_numbers)
    script = f'''#!/usr/bin/env python3
import sys

KNOWN = {known!r}

args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view" and args[2] in KNOWN:
    sys.stdout.write('{{"number": ' + args[2] + '}}')
    sys.exit(0)

sys.stderr.write("fake gh (dante test double): unexpected invocation " + repr(args))
sys.exit(97)
'''
    gh_path.write_text(script, encoding="utf-8")
    gh_path.chmod(0o755)
    return str(gh_dir)


def _env_with_fake_gh(fake_gh_dir):
    return {"PATH": fake_gh_dir + os.pathsep + path_without_real_gh()}


def _seed_with_issue(repo, note_type, headline, description, issue, extra_flags, env):
    args = [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        "--issue", str(issue),
        *extra_flags,
    ]
    return run_memory_script("note.py", args, cwd=repo, env=env)


def _seed_without_issue(repo, note_type, headline, description, extra_flags):
    args = [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        *extra_flags,
    ]
    return run_memory_script("note.py", args, cwd=repo, env=None)


# (tipo, titular, descripcion, flags extra obligatorios) -- un
# decision, un incidencia, un restriccion, tres asuntos DISTINTOS
# [mismo criterio anti-similitud que test_note_issue_field.py, para
# que ninguno rebote contra otro via similar.find_similar].
_DECISION_INCIDENT_RESTRICTION = [
    (
        "D",
        "retire the manual quarterly export spreadsheet",
        "The spreadsheet is rebuilt by hand every quarter and drifts from "
        "the real numbers within a week; the dashboard already covers it.",
        ["--why", "one source of truth beats a hand-built copy nobody "
                  "remembers to update"],
    ),
    (
        "I",
        "the weekly digest email silently stopped sending for a month",
        "The mailer's API key expired and the retry logic swallowed the "
        "401 without ever surfacing it to anyone on the team.",
        [],
    ),
    (
        "R",
        "never truncate the audit log table, even in a staging reset",
        "A staging reset script truncated the audit log along with the "
        "rest of the schema and erased evidence needed for a compliance "
        "review the following week.",
        ["--stops", "yes"],
    ),
]


@_skip_on_windows
class TestIssueSurvivesZoneSearchAcrossThreeTypes:
    """Item 1 del encargo: `gitmem search <zona>` (`render_zone`, via
    `_restriction_block`/`_incident_block`/`_cluster_block` -- D pasa
    por el racimo de decisiones, no por `_decision_block` suelto, ver
    `report_render.py::_cluster_section`) tiene que enseñar el numero
    de issue con el que se guardo la nota.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags",
        _DECISION_INCIDENT_RESTRICTION,
        ids=[case[0] for case in _DECISION_INCIDENT_RESTRICTION],
    )
    def test_type_issue_number_appears_in_zone_search_output(
        self, tmp_repo, tmp_path, note_type, headline, description, extra_flags
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 5151
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo, note_type, headline, description, issue_number, extra_flags, env
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} tendria que "
            f"guardarse sin rebotar -- stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [_ZONE1], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {_ZONE1} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert f"Issue: #{issue_number}" in search_out, (
            f"el numero de issue con el que se guardo {note_id} (tipo "
            f"{note_type}, {issue_number}) no aparece en 'gitmem search "
            f"{_ZONE1}' -- salida real:\n{search_out!r}"
        )


@_skip_on_windows
class TestIssueSurvivesWordSearchAcrossThreeTypes:
    """Item 2 del encargo: `gitmem search <palabra>` (`render_word`, via
    `_restriction_block`/`_incident_block`/`_decision_block` -- la
    busqueda por palabra recibe `WordChunk.notes` en bruto, sin racimo,
    ver desviacion 3 del docstring de `report_render.py`) tiene que
    enseñar el mismo numero.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags,word",
        [
            (t, h, d, f, w)
            for (t, h, d, f), w in zip(
                _DECISION_INCIDENT_RESTRICTION,
                ("spreadsheet", "digest", "truncate"),
            )
        ],
        ids=[case[0] for case in _DECISION_INCIDENT_RESTRICTION],
    )
    def test_type_issue_number_appears_in_word_search_output(
        self, tmp_repo, tmp_path, note_type, headline, description, extra_flags, word
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 5252
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo, note_type, headline, description, issue_number, extra_flags, env
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} tendria que "
            f"guardarse sin rebotar -- stdout={out!r} stderr={err!r}"
        )
        assert word in headline, (
            f"la palabra de busqueda {word!r} tiene que salir literal del "
            f"propio titular para que el round trip sea real: {headline!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [word], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {word} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert f"Issue: #{issue_number}" in search_out, (
            f"el numero de issue con el que se guardo {note_id} (tipo "
            f"{note_type}, {issue_number}) no aparece en 'gitmem search "
            f"{word}' -- salida real:\n{search_out!r}"
        )


class TestNoteWithoutIssueLeavesNoOrphanLabel:
    """Item 3 del encargo: "no se enseñan etiquetas huerfanas" [TEXTOS
    Sec.2.4, ya citado en `report_render_note.py`] -- una nota SIN
    `--issue` no debe pintar ningun `Issue:` en ninguno de los dos
    caminos. Un solo tipo (D) representando el guard: el resto de tipos
    comparten la misma condicion `if note.issue is not None` que este
    test fija como contrato, y las clases de arriba ya cubren D/I/R con
    issue puesto -- repetir el guard por tipo seria multiplicar el
    mismo assert sin cazar un fallo distinto (granularidad de
    aceptacion, no el barrido exhaustivo de ramas).
    """

    _HEADLINE = "keep using the existing pagination cursor format"
    _DESCRIPTION = (
        "Considered switching to offset-based pagination for the reports "
        "API; the cursor format already handles concurrent inserts "
        "correctly and offset pagination would reintroduce that bug."
    )
    _WHY = "cursor pagination is already correct under concurrent writes"

    def test_zone_search_shows_no_issue_label(self, tmp_repo):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = _seed_without_issue(
            tmp_repo, "D", self._HEADLINE, self._DESCRIPTION, ["--why", self._WHY]
        )
        assert rc == 0, (
            f"un D sin --issue tendria que guardarse sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [_ZONE1], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {_ZONE1} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert "Issue:" not in search_out, (
            f"una nota sin --issue no deberia pintar ninguna etiqueta "
            f"'Issue:' huerfana en 'gitmem search {_ZONE1}' -- salida "
            f"real:\n{search_out!r}"
        )
        assert f"Why: {self._WHY}" in search_out, (
            "el guard de 'sin issue' no puede vaciar el resto del bloque -- "
            f"'Why:' deberia seguir saliendo igual: {search_out!r}"
        )

    def test_word_search_shows_no_issue_label(self, tmp_repo):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = _seed_without_issue(
            tmp_repo, "D", self._HEADLINE, self._DESCRIPTION, ["--why", self._WHY]
        )
        assert rc == 0, (
            f"un D sin --issue tendria que guardarse sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )

        rc_search, search_out, search_err = run_memory_script(
            "search.py", ["pagination"], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py pagination fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert "Issue:" not in search_out, (
            f"una nota sin --issue no deberia pintar ninguna etiqueta "
            f"'Issue:' huerfana en 'gitmem search pagination' -- salida "
            f"real:\n{search_out!r}"
        )
        assert f"Why: {self._WHY}" in search_out, (
            "el guard de 'sin issue' no puede vaciar el resto del bloque -- "
            f"'Why:' deberia seguir saliendo igual: {search_out!r}"
        )


# ---------------------------------------------------------------------------
# PASE DE ENDURECIMIENTO (Ultron ya implemento -- 497 pasan, 1 se salta).
# Cierra los huecos marcados a proposito arriba: los cuatro tipos que
# faltaban (bloqueador, memo, pregunta, descarte), el `--issue 0` (un
# numero valido que un `if note.issue:` por verdad/falsedad borraria en
# silencio -- tiene que quedar `is not None`, fijado por los dos
# caminos), y el racimo de `_cluster_block`: la raiz lo enseña, los
# hijos no llevan ninguna segunda linea de ningun campo -- ni siquiera
# `Why:` -- asi que tampoco `Issue:`; eso es deliberado, no un olvido,
# y este test lo deja fijado para el proximo que lo mire.
# ---------------------------------------------------------------------------

# (tipo, titular, descripcion, flags extra obligatorios) -- bloqueador,
# memo, pregunta, descarte. Cuatro asuntos DISTINTOS entre si y de los
# tres ya cubiertos arriba (D/I/R), mismo criterio anti-similitud.
_BLOCKER_MEMO_QUESTION_DISCARD = [
    (
        "B",
        "waiting on the search vendor to fix cross-region replication lag",
        "Search results in the EU region lag the US region by several "
        "minutes during peak hours until the vendor ships their fix.",
        ["--awaits", "search vendor support -- replication lag ticket"],
    ),
    (
        "M",
        "the nightly cleanup job prunes sessions older than thirty days",
        "Confirmed with infra that the retention window is thirty days, "
        "matching the value already hardcoded in the cron job.",
        ["--stops", "no"],
    ),
    (
        "Q",
        "should an expired invite link show a different error than a used one",
        "Support keeps getting tickets where users can't tell whether their "
        "invite expired or was already claimed by someone else.",
        [],
    ),
    (
        "X",
        "dropped the idea of caching search results client-side",
        "Evaluated a client-side cache for repeated searches; the results "
        "change too often for a cache to stay correct without invalidation "
        "logic more complex than the problem it would solve.",
        [],
    ),
]

# Palabra literal del titular de cada entrada de arriba, en el mismo
# orden -- usada solo por la busqueda por palabra.
_BLOCKER_MEMO_QUESTION_DISCARD_WORDS = ("replication", "cleanup", "invite", "caching")


@_skip_on_windows
class TestIssueSurvivesZoneSearchAcrossRemainingFourTypes:
    """Cierra el hueco declarado en la primera pasada: bloqueador, memo,
    pregunta y descarte, por `gitmem search <zona>` -- mismo patron que
    `TestIssueSurvivesZoneSearchAcrossThreeTypes` de arriba (D/I/R), sin
    duplicar su andamiaje. `X` entra aqui por el camino del RACIMO
    (`_cluster_block`, via `_cluster_section` -- `report.build_zone`
    mete D y X juntos en `decisions`), un racimo de una nota sola
    (sin Origin/Replaces, queda de raiz de su propio racimo) -- mismo
    codigo que ya exercita D, confirma que X tambien lo atraviesa.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags",
        _BLOCKER_MEMO_QUESTION_DISCARD,
        ids=[case[0] for case in _BLOCKER_MEMO_QUESTION_DISCARD],
    )
    def test_type_issue_number_appears_in_zone_search_output(
        self, tmp_repo, tmp_path, note_type, headline, description, extra_flags
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 6363
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo, note_type, headline, description, issue_number, extra_flags, env
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} tendria que "
            f"guardarse sin rebotar -- stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [_ZONE1], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {_ZONE1} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert f"Issue: #{issue_number}" in search_out, (
            f"el numero de issue con el que se guardo {note_id} (tipo "
            f"{note_type}, {issue_number}) no aparece en 'gitmem search "
            f"{_ZONE1}' -- salida real:\n{search_out!r}"
        )


@_skip_on_windows
class TestIssueSurvivesWordSearchAcrossRemainingFourTypes:
    """Mismo cierre que la clase anterior, por `gitmem search <palabra>`
    -- mismo patron que `TestIssueSurvivesWordSearchAcrossThreeTypes`.
    `X` entra aqui por `_decision_block` (racimo suelto, sin raiz/hijos
    -- `render_word` no arma `Cluster`, ver desviacion 3 del docstring
    de `report_render.py`), un camino DISTINTO del que atraviesa por
    zona -- confirma que la Issue de X sobrevive por los dos caminos,
    no solo por el de la raiz de racimo.
    """

    @pytest.mark.parametrize(
        "note_type,headline,description,extra_flags,word",
        [
            (t, h, d, f, w)
            for (t, h, d, f), w in zip(
                _BLOCKER_MEMO_QUESTION_DISCARD,
                _BLOCKER_MEMO_QUESTION_DISCARD_WORDS,
            )
        ],
        ids=[case[0] for case in _BLOCKER_MEMO_QUESTION_DISCARD],
    )
    def test_type_issue_number_appears_in_word_search_output(
        self, tmp_repo, tmp_path, note_type, headline, description, extra_flags, word
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 6464
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo, note_type, headline, description, issue_number, extra_flags, env
        )
        assert rc == 0, (
            f"tipo {note_type} con --issue {issue_number} tendria que "
            f"guardarse sin rebotar -- stdout={out!r} stderr={err!r}"
        )
        assert word in headline, (
            f"la palabra de busqueda {word!r} tiene que salir literal del "
            f"propio titular para que el round trip sea real: {headline!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [word], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {word} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert f"Issue: #{issue_number}" in search_out, (
            f"el numero de issue con el que se guardo {note_id} (tipo "
            f"{note_type}, {issue_number}) no aparece en 'gitmem search "
            f"{word}' -- salida real:\n{search_out!r}"
        )


@_skip_on_windows
class TestIssueZeroIsNotFalsyOnEitherSearchPath:
    """El cero es un numero de issue valido -- `Note.issue: int | None`,
    el centinela de "no se dio" es `None`, nunca `0` (`model.py:68`,
    `validator_issue.py::validate_issue`: `if issue is None: return
    None`, ninguna comprobacion de rango). Un futuro `if note.issue:`
    (verdad/falsedad) en vez de `if note.issue is not None:` en
    cualquiera de los bloques de `report_render.py` borraria el cero en
    silencio sin que ningun test lo notara si solo se prueban numeros
    no-cero -- fijado aqui, explicito, por los dos caminos.
    """

    def test_zero_survives_zone_search(self, tmp_repo, tmp_path):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 0
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        rc, out, err = _seed_with_issue(
            tmp_repo,
            "M",
            "the staging environment resets its database every Sunday",
            "Confirmed with infra: staging gets a full database reset "
            "every Sunday at 04:00 UTC as part of the weekly refresh job.",
            issue_number,
            ["--stops", "no"],
            env,
        )
        assert rc == 0, (
            f"un M con --issue 0 tendria que guardarse sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [_ZONE1], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {_ZONE1} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert "Issue: #0" in search_out, (
            f"la nota {note_id} se guardo con --issue 0 (numero valido, "
            f"distinto de 'sin issue') -- 'Issue: #0' tendria que salir "
            f"en 'gitmem search {_ZONE1}', no desaparecer por ser "
            f"falsy -- salida real:\n{search_out!r}"
        )

    def test_zero_survives_word_search(self, tmp_repo, tmp_path):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        issue_number = 0
        fake_gh_dir = _fake_gh_dir(tmp_path, issue_number)
        env = _env_with_fake_gh(fake_gh_dir)

        headline = "the staging environment resets its database every Sunday"
        rc, out, err = _seed_with_issue(
            tmp_repo,
            "M",
            headline,
            "Confirmed with infra: staging gets a full database reset "
            "every Sunday at 04:00 UTC as part of the weekly refresh job.",
            issue_number,
            ["--stops", "no"],
            env,
        )
        assert rc == 0, (
            f"un M con --issue 0 tendria que guardarse sin rebotar -- "
            f"stdout={out!r} stderr={err!r}"
        )
        note_id = extract_note_id(out)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", ["staging"], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py staging fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert "Issue: #0" in search_out, (
            f"la nota {note_id} se guardo con --issue 0 (numero valido, "
            f"distinto de 'sin issue') -- 'Issue: #0' tendria que salir "
            f"en 'gitmem search staging', no desaparecer por ser falsy "
            f"-- salida real:\n{search_out!r}"
        )


@_skip_on_windows
class TestClusterRootShowsIssueChildrenDoNot:
    """Decision deliberada de Ultron, fijada tal cual esta: la RAIZ de un
    racimo (`_cluster_block`) enseña su `Issue:` -- los HIJOS no,
    porque ningun hijo lleva una segunda linea para NINGUN campo (ni
    siquiera `Why:`, que si tiene la raiz -- ver `_cluster_block`,
    el bucle de `children` solo escribe una linea por hijo: id,
    headline, estado y puntero, nunca un campo aparte). Este test no
    pide que se abra esa linea -- pide que la asimetria quede FIJADA a
    proposito, para que el proximo que la lea sepa que es una decision,
    no un olvido: si algun dia alguien "completa" los hijos con su
    propio `Issue:`, este test tiene que notarlo (se rompe la mitad
    "los hijos no ensucian").

    Racimo real de dos notas por PUNTERO (`clusters.py`, nunca por
    parecido): una D raiz con `--issue`, y una X hija que la cita con
    `--origin <id de la raiz>` y trae su PROPIO `--issue`, un numero
    DISTINTO -- si el numero del hijo apareciera en cualquier parte del
    informe, seria la prueba de que se colo por donde no debe (no hay
    otro sitio de donde ese numero exacto pudiera salir).
    """

    def test_child_issue_number_never_appears_only_roots_does(self, tmp_repo, tmp_path):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        root_issue = 7171
        child_issue = 8282
        fake_gh_dir = _fake_gh_dir_multi(tmp_path, (root_issue, child_issue))
        env = _env_with_fake_gh(fake_gh_dir)

        rc_root, out_root, err_root = _seed_with_issue(
            tmp_repo,
            "D",
            "standardize all internal cron jobs on UTC timestamps",
            "Half the cron jobs logged local time and half logged UTC, "
            "making cross-job incident timelines impossible to reconcile.",
            root_issue,
            ["--why", "reconciling incident timelines across jobs needs one "
                      "consistent clock"],
            env,
        )
        assert rc_root == 0, (
            f"la raiz D con --issue {root_issue} tendria que guardarse sin "
            f"rebotar -- stdout={out_root!r} stderr={err_root!r}"
        )
        root_id = extract_note_id(out_root)

        rc_child, out_child, err_child = _seed_with_issue(
            tmp_repo,
            "X",
            "dropped the idea of a per-job local-time override flag",
            "Considered letting individual cron jobs opt out of UTC for "
            "readability; not worth the reconciliation cost it reopens.",
            child_issue,
            ["--origin", root_id],
            env,
        )
        assert rc_child == 0, (
            f"la hija X con --origin {root_id} y --issue {child_issue} "
            f"tendria que guardarse sin rebotar -- stdout={out_child!r} "
            f"stderr={err_child!r}"
        )
        child_id = extract_note_id(out_child)

        rc_search, search_out, search_err = run_memory_script(
            "search.py", [_ZONE1], cwd=tmp_repo
        )
        assert rc_search == 0, (
            f"search.py {_ZONE1} fallo -- stdout={search_out!r} "
            f"stderr={search_err!r}"
        )
        assert root_id in search_out and child_id in search_out, (
            f"el racimo entero tendria que salir (raiz {root_id} + hija "
            f"{child_id}) -- salida real:\n{search_out!r}"
        )
        assert f"Issue: #{root_issue}" in search_out, (
            f"la raiz {root_id} se guardo con --issue {root_issue} -- "
            f"tendria que salir en el racimo -- salida real:\n{search_out!r}"
        )
        assert str(child_issue) not in search_out, (
            f"la hija {child_id} se guardo con --issue {child_issue}, pero "
            f"los hijos del racimo no llevan ninguna segunda linea de "
            f"ningun campo -- ese numero no puede aparecer en ningun sitio "
            f"del informe (decision deliberada, ver docstring de la clase) "
            f"-- salida real:\n{search_out!r}"
        )
