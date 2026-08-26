"""Contrato ROJO, modo test-first (pase de CONTRATO, no barrido
exhaustivo): una opcion NUEVA de `bin/memory/search.py` que hoy NO
EXISTE -- una vista en cadena, cada nota viva con sus antecesoras
colgando debajo, reconstruidas de las lineas `-> replaced by M-xxx` de
`ARCHIVED.md` (via `indexes.read_archive`/`format.parse_archive_line`,
ya en produccion -- este fichero no los prueba a ellos, los reutiliza
por su camino real).

De donde sale el encargo -- ``gitmem search D-056`` (verificado en vivo
antes de escribir esto): "la memoria se guarda bien pero se lee mal ...
el enlace de sustitucion se ve por un solo lado". Esta pieza es la otra
mitad de ese mismo hallazgo: una vista que siga la cadena entera, no
solo el ultimo salto.

GRAMATICA DE CLI ASUMIDA -- ninguna forma previa existe en ningun
documento del proyecto para esta opcion (D-056 solo describe el
COMPORTAMIENTO, "el enlace de sustitucion se ve por un solo lado"; el
nombre del flag y la forma exacta del texto son parte del CONTRATO que
este fichero fija, pase de Dante en modo test-first, igual que ya hizo
`test_search_script.py` para `--id`/`--file` en su dia):

    search.py <ZONA-o-PALABRA> --chain

Se combina con el mismo positional que ya resuelve zona-o-palabra
[docstring de `bin/memory/search.py`] -- mismo patron que `--todo`, no
un segundo modo de invocacion aparte.

HOY `bin/memory/search.py::_parse_args` no declara `--chain` -- un test
que lo invoque falla con el "argumento no reconocido" real de argparse
(rc==2, "unrecognized arguments: --chain" en stderr, CERO traza de
pila). Ese es el ROJO correcto de una funcion ausente [encargo de esta
tarea] -- comprobado leyendo `bin/memory/search.py` antes de escribir
esto: `_parse_args` solo declara `query`/`--id`/`--file`/`--todo`.

CONTRATO ELEGIDO AQUI para el TEXTO, con su porque (pase de Dante, no
descrito en ningun sitio previo):

- **Tachado de una antecesora**: envuelta en `~~...~~` (convencion
  markdown de tachado, legible tanto por una persona como por el propio
  Claude que lee esta salida -- unico vocabulario de "tachado" ya
  entendido sin inventar un glifo nuevo sin precedente en
  `lib/memory/emojis.py`). La nota viva en la CABEZA de la cadena NO va
  envuelta -- es la unica vigente.
- **Cierre sin sucesora**: la palabra literal `cerrada` -- mismo
  vocabulario que `format_lines.py::_ARCHIVE_DESTINATIONS` ya usa para
  ese mismo destino (`"closed"`/`"closed: "`), nunca un termino nuevo.
- **El puntero Origin de una incidencia a la restriccion que nacio de
  cerrarla**: reutiliza el literal `Origin: <id>` que
  `report_render.py::_restriction_block` YA imprime hoy para ese mismo
  campo en el informe normal -- una vista en cadena que reimplementara
  su propio formato y "olvidara" ese campo (en vez de reusar el bloque
  ya existente) es exactamente el fallo que el punto (b) del encargo
  pide impedir.

DOS CASOS BORDE QUE EL ENCARGO FIJA EXPLICITAMENTE, cada uno con su
propia clase de test:

  (a) una nota cerrada con `remove.py --restriction no` (sin sucesora,
      `ARCHIVED.md` dice `-> closed: <motivo>`) es un FINAL LEGITIMO de
      cadena, etiquetada "cerrada" -- NUNCA un hueco ni un error.
  (b) el enlace incidencia->restriccion NO es un `Replaces` -- es el
      campo `Origin` de la restriccion que `remove.py --restriction new`
      hace nacer al cerrar la incidencia [`bin/memory/remove.py::
      _build_fence_candidate`, `origin=(args.id,)`, verificado leyendo
      el fichero]. Una vista de cadena/relacion armada SOLO a partir de
      `Replaces` perderia este enlace en silencio.

Round trip real, sin fabricar el texto esperado (unmassk-standards
Sec.34): las notas se siembran via `note.py`/`remove.py` como PROCESOS
(`seed_note_via_script`/`run_memory_script`), nunca escribiendo
`ARCHIVED.md`/los indices a mano.

Con `--chain` sin implementar todavia, TODOS los tests de este fichero
fallan HOY por la misma causa real: argparse rechaza el flag ausente --
nunca por una traza rota.
"""

import re

from .conftest import (
    extract_note_id,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)

_FENCE_ID_RE = re.compile(r"([A-Z]-\d+)\s+guardada\s+—\s+muro nacido de")


def _extract_restriction_id_from_fence_output(stdout):
    """El id real que `remove.py --restriction new` acabo de asignar al
    muro, leido de SU PROPIA confirmacion
    (`"⚠️ {id} guardada — muro nacido de {incident_id}"`,
    `bin/memory/remove.py::_create_fence`) -- distinto del literal
    `"✅ ... guardada"` que usa `note.py` (`conftest.extract_note_id` no
    sirve aqui: el emoji y el verbo que sigue son otros)."""
    match = _FENCE_ID_RE.search(stdout)
    assert match is not None, (
        f"no se encontro el id del muro nuevo en la salida de remove.py: {stdout!r}"
    )
    return match.group(1)


def _struck(out, note_id):
    """`True` si `note_id` aparece envuelto en el tachado `~~...~~`
    elegido por este contrato en algun punto de `out` -- comprobacion de
    presencia, no de una linea concreta, porque la forma exacta del
    anidado (sangria, guiones de arbol) es parte de lo que Ultron
    todavia tiene que decidir al implementar."""
    pattern = re.compile(rf"~~[^~]*{re.escape(note_id)}[^~]*~~")
    return pattern.search(out) is not None


class TestChainFlagIsRecognizedByTheCli:
    def test_chain_flag_does_not_bounce_as_an_unrecognized_argument(self, tmp_repo):
        seed_zones_json(tmp_repo, ["ops", "infra"])
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "ops", "infra",
            "background jobs retry with exponential backoff",
            description="MARK description", stops="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"

        rc, out, err = run_memory_script("search.py", ["backoff", "--chain"], cwd=tmp_repo)
        assert rc == 0, (
            f"--chain tiene que ser un flag real de search.py, no un "
            f"argumento no reconocido: stdout={out!r} stderr={err!r}"
        )
        assert "unrecognized arguments" not in err, (
            f"argparse todavia no conoce --chain: {err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err


class TestChainViewShowsLiveNoteWithStruckThroughAncestorsBelow:
    def test_replace_chain_of_two_ancestors_renders_live_on_top_struck_below(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["cache", "infra"])
        rc_old, out_old, err_old = seed_note_via_script(
            tmp_repo, "M", "cache", "infra",
            "cache invalidation done via manual flush",
            description="MARK description", stops="no",
        )
        assert rc_old == 0, f"siembra vieja fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_mid, out_mid, err_mid = seed_note_via_script(
            tmp_repo, "M", "cache", "infra",
            "cache invalidation done via TTL expiry",
            description="MARK description", stops="no", replaces=old_id,
        )
        assert rc_mid == 0, f"siembra intermedia fallo: stdout={out_mid!r} stderr={err_mid!r}"
        mid_id = extract_note_id(out_mid)

        rc_new, out_new, err_new = seed_note_via_script(
            tmp_repo, "M", "cache", "infra",
            "cache invalidation done via pub-sub events",
            description="MARK description", stops="no", replaces=mid_id,
        )
        assert rc_new == 0, f"siembra nueva fallo: stdout={out_new!r} stderr={err_new!r}"
        new_id = extract_note_id(out_new)

        rc, out, err = run_memory_script(
            "search.py", ["invalidation", "--chain"], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        assert new_id in out and mid_id in out and old_id in out, (
            f"la cadena entera (viva + dos antecesoras) tiene que aparecer: {out!r}"
        )
        assert not _struck(out, new_id), (
            f"la nota VIVA (cabeza de la cadena) no puede salir tachada: {out!r}"
        )
        assert _struck(out, mid_id), (
            f"la antecesora intermedia tiene que salir tachada [D-056, "
            f"vista en cadena]: {out!r}"
        )
        assert _struck(out, old_id), (
            f"la antecesora mas vieja tiene que salir tachada: {out!r}"
        )
        assert out.index(mid_id) < out.index(old_id), (
            f"las antecesoras cuelgan en orden -- la mas reciente primero: {out!r}"
        )


class TestChainViewCountsAClosedIncidentWithoutASuccessorAsALegitimateEnd:
    """Caso borde (a) del encargo."""

    def test_closed_incident_with_no_replacement_is_labeled_closed_not_a_gap(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["ops", "reliability"])
        # work="no" [2026-08-26, D-065/D-066]: la aduana de issues rebota
        # una I sin --issue/--work antes de llegar a la vista en cadena
        # que este fichero prueba -- ajeno al escenario bajo prueba aqui.
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "I", "ops", "reliability",
            "background retries silently drop failed jobs",
            description="MARK_ROOTCAUSE a retry budget was never enforced",
            work="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        incident_id = extract_note_id(out_seed)

        rc_close, out_close, err_close = run_memory_script(
            "remove.py",
            [incident_id, "retry budget added and tested", "--restriction", "no"],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"cierre fallo: stdout={out_close!r} stderr={err_close!r}"

        rc, out, err = run_memory_script(
            "search.py", ["retries", "--chain"], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        assert incident_id in out, (
            f"una incidencia cerrada sin sucesora no puede desaparecer de la "
            f"vista en cadena -- eso seria un hueco silencioso: {out!r}"
        )
        lines_with_id = [line for line in out.splitlines() if incident_id in line]
        assert any("cerrada" in line for line in lines_with_id), (
            f"tiene que quedar etiquetada 'cerrada' -- un final legitimo de "
            f"cadena, no un error [encargo, caso borde (a)]: {lines_with_id!r}"
        )


class TestChainViewNeverDropsTheIncidentToRestrictionOriginLink:
    """Caso borde (b) del encargo: el enlace incidencia->restriccion es
    `Origin`, no `Replaces` -- una vista de cadena armada solo a partir
    de `Replaces` lo perderia en silencio."""

    def test_origin_link_from_a_closed_incident_to_its_born_restriction_survives(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["data", "migrations"])
        # work="no" [2026-08-26, D-065/D-066]: mismo motivo que arriba --
        # ajeno al enlace Origin incidencia->restriccion bajo prueba.
        rc_seed, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "I", "data", "migrations",
            "database migration silently left an old index behind",
            description="MARK_ROOTCAUSE the migration script never dropped the old index",
            work="no",
        )
        assert rc_seed == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        incident_id = extract_note_id(out_seed)

        rc_close, out_close, err_close = run_memory_script(
            "remove.py",
            [
                incident_id, "root cause found and documented",
                "--restriction", "new",
                "--restriction-text",
                "no migration merges without a dry run against staging",
                "--why", "the ghost index kept eating disk quietly for weeks",
            ],
            cwd=tmp_repo,
        )
        assert rc_close == 0, f"cierre fallo: stdout={out_close!r} stderr={err_close!r}"
        restriction_id = _extract_restriction_id_from_fence_output(out_close)

        rc, out, err = run_memory_script(
            "search.py", ["migration", "--chain"], cwd=tmp_repo
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        assert incident_id in out, (
            f"la incidencia cerrada tiene que seguir presente en la vista "
            f"en cadena: {out!r}"
        )
        assert restriction_id in out, (
            f"la restriccion viva que nacio de ella tiene que aparecer: {out!r}"
        )
        assert f"Origin: {incident_id}" in out, (
            f"el enlace Origin de la restriccion hacia la incidencia que la "
            f"origino no puede perderse en la vista en cadena -- no es un "
            f"Replaces [encargo, caso borde (b)]: {out!r}"
        )


class TestChainViewNeverShowsFewerArchivedNotesOfAZoneThanTheOldTodoView:
    """Regresion (repro de Moriarty, verificado leyendo `report.py` antes
    de escribir esto): `build_chain`/`_chain_threads`
    (`lib/memory/report.py`) construyen el universo de la zona con una
    UNICA llamada a `_notes_touching_zone(zone)` y solo caminan hacia
    atras DENTRO de ese conjunto. Cuando la cabeza viva de un linaje se
    re-archiva bajo OTRA pareja de zonas, su sucesora ya no toca la zona
    vieja -- queda fuera del conjunto, y con ella el linaje entero:
    `_chain_is_superseded` la marca "sustituida" via `ARCHIVED.md`
    (`destination == "replaced"`) sin que su sustituta aparezca en
    ningun sitio de la salida, asi que el linaje entero desaparece de
    `search <zona-vieja> --chain`.

    `search <zona-vieja> --todo` (`report.build_zone` con
    `include_archived=True`, la vista VIEJA que `--chain` viene a
    mejorar [D-056]) no tiene este problema: filtra por tipo/archivado
    sobre el mismo `_notes_touching_zone(zone)`, sin exigir que la
    sucesora tambien toque la zona. Invariante exigido aqui: `--chain`
    de una zona NUNCA enseña menos notas archivadas de esa zona que
    `--todo` de la misma zona -- una vista nueva que enseña MENOS
    memoria que la vieja es perdida silenciosa [CLAUDE.md "el sistema
    contra si mismo"], no una mejora.
    """

    def test_lineage_whose_head_moved_to_another_zone_pair_still_appears_in_chain_of_the_old_zone(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["alpha", "beta", "gamma", "delta"])

        rc1, out1, err1 = seed_note_via_script(
            tmp_repo, "M", "alpha", "beta",
            "batch export retried without a cap on attempts",
            description="MARK description", stops="no",
        )
        assert rc1 == 0, f"siembra 1 fallo: stdout={out1!r} stderr={err1!r}"
        m1 = extract_note_id(out1)

        rc2, out2, err2 = seed_note_via_script(
            tmp_repo, "M", "alpha", "beta",
            "batch export retried with a fixed attempt cap",
            description="MARK description", stops="no", replaces=m1,
        )
        assert rc2 == 0, f"siembra 2 fallo: stdout={out2!r} stderr={err2!r}"
        m2 = extract_note_id(out2)

        rc3, out3, err3 = seed_note_via_script(
            tmp_repo, "M", "alpha", "beta",
            "batch export retried with exponential backoff between attempts",
            description="MARK description", stops="no", replaces=m2,
        )
        assert rc3 == 0, f"siembra 3 fallo: stdout={out3!r} stderr={err3!r}"
        m3 = extract_note_id(out3)

        # La cabeza del linaje se re-archiva bajo OTRA pareja de zonas --
        # exactamente el caso del repro de Moriarty. m4 nunca toca
        # 'alpha'/'beta'.
        rc4, out4, err4 = seed_note_via_script(
            tmp_repo, "M", "gamma", "delta",
            "batch export retried with a circuit breaker instead of retries",
            description="MARK description", stops="no", replaces=m3,
        )
        assert rc4 == 0, f"siembra 4 fallo: stdout={out4!r} stderr={err4!r}"
        m4 = extract_note_id(out4)

        rc_todo, out_todo, err_todo = run_memory_script(
            "search.py", ["alpha", "--todo"], cwd=tmp_repo
        )
        assert rc_todo == 0, f"stdout={out_todo!r} stderr={err_todo!r}"
        assert "Traceback" not in out_todo and "Traceback" not in err_todo

        # Sanity de la vista VIEJA: confirma que el linaje SI sigue en el
        # repositorio y SI es visible por --todo -- si esto fallara, la
        # siembra estaria mal construida, no seria el hallazgo bajo
        # prueba.
        for note_id in (m1, m2, m3):
            assert note_id in out_todo, (
                f"{note_id} tiene que aparecer archivado en 'search alpha "
                f"--todo' -- si no aparece aqui la siembra esta mal hecha, "
                f"no es el hallazgo bajo prueba: {out_todo!r}"
            )

        rc_chain, out_chain, err_chain = run_memory_script(
            "search.py", ["alpha", "--chain"], cwd=tmp_repo
        )
        assert rc_chain == 0, f"stdout={out_chain!r} stderr={err_chain!r}"
        assert "Traceback" not in out_chain and "Traceback" not in err_chain

        for note_id in (m1, m2, m3):
            assert note_id in out_chain, (
                f"'search alpha --chain' tiene que seguir mostrando "
                f"{note_id} como hilo archivado, igual que ya hace "
                f"'search alpha --todo' -- su cabeza de linaje ({m4!r}) se "
                f"re-archivo bajo otra pareja de zonas ([gamma][delta]), "
                f"pero el linaje entero sigue tocando 'alpha'; una vista "
                f"nueva que enseña MENOS memoria que la vieja es perdida "
                f"silenciosa: {out_chain!r}"
            )


class TestChainViewLabelsASupersededNoteAsReplacedNeverAsClosed:
    """Regresion sobre el fix anterior (repro de Moriarty, verificado
    leyendo `report.py` antes de escribir esto): la clase de arriba
    (`TestChainViewNeverShowsFewerArchivedNotesOfAZoneThanTheOldTodoView`)
    ya fijo que el linaje NO desaparece cuando su cabeza real se
    re-archiva bajo otra pareja de zonas. Pero la cabeza que reaparece
    (`m3` en este mismo repro) sale etiquetada `cerrada`
    (`report.py::_chain_threads`, linea `closed=note.id in
    archived_ids` -- no distingue "cierre legitimo sin sucesora" de
    "sustituida, pero la sucesora vive fuera de este conjunto").

    El propio contrato de `model.ChainThread.closed`
    (`lib/memory/model.py:191`, "True = cierre legitimo sin sucesora")
    ya lo prohibe: `m3` SI tiene una sucesora real (`m4`, sembrada con
    `--replaces m3` en `[gamma][delta]`) -- que esa sucesora no toque
    'alpha' no la convierte en un cierre legitimo. Etiquetarla `cerrada`
    dice al lector que el linaje TERMINO en `m3`, cuando en realidad
    sigue vivo en `m4`, solo que invisible desde esta vista -- mentira
    de la vista, no del dato [CLAUDE.md "el sistema contra si mismo":
    una vista que da a entender que algo termino cuando sigue vivo en
    otra zona].

    Control ya existente y en verde, sin tocar aqui: una incidencia
    REALMENTE cerrada sin sucesora (`destination == "closed"`) SI debe
    decir `cerrada` --
    `TestChainViewCountsAClosedIncidentWithoutASuccessorAsALegitimateEnd`
    mas arriba en este mismo fichero ya lo fija y sigue en verde.

    Tecnica de aserto sobre el TEXTO -- deliberadamente agnostica a la
    frase exacta que elija Ultron (mismo criterio que
    [[deuda17-freshness-disclosure-contract-notes]]): no exige el
    literal `"sustituida por"` (Dante no impone produccion aqui, solo el
    contrato de comportamiento), exige las DOS invariantes que el
    encargo fija -- (1) `m3` NUNCA sale etiquetada `cerrada` cuando
    tiene sucesora real, (2) la etiqueta de `m3` NOMBRA a su sucesora
    real (`m4`) en la misma linea, para que quien lea sepa que el
    linaje continua en vez de asumir que termino ahi.
    """

    def test_replaced_head_that_moved_to_another_zone_pair_is_not_labeled_closed(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["alpha", "beta", "gamma", "delta"])

        rc1, out1, err1 = seed_note_via_script(
            tmp_repo, "M", "alpha", "beta",
            "batch export retried without a cap on attempts",
            description="MARK description", stops="no",
        )
        assert rc1 == 0, f"siembra 1 fallo: stdout={out1!r} stderr={err1!r}"
        m1 = extract_note_id(out1)

        rc2, out2, err2 = seed_note_via_script(
            tmp_repo, "M", "alpha", "beta",
            "batch export retried with a fixed attempt cap",
            description="MARK description", stops="no", replaces=m1,
        )
        assert rc2 == 0, f"siembra 2 fallo: stdout={out2!r} stderr={err2!r}"
        m2 = extract_note_id(out2)

        rc3, out3, err3 = seed_note_via_script(
            tmp_repo, "M", "alpha", "beta",
            "batch export retried with exponential backoff between attempts",
            description="MARK description", stops="no", replaces=m2,
        )
        assert rc3 == 0, f"siembra 3 fallo: stdout={out3!r} stderr={err3!r}"
        m3 = extract_note_id(out3)

        # La cabeza real del linaje se re-archiva bajo OTRA pareja de
        # zonas -- m3 reaparece como cabeza de su propio hilo dentro de
        # la vista de 'alpha' (fix del hallazgo anterior de Moriarty),
        # pero SI tiene una sucesora real: m4.
        rc4, out4, err4 = seed_note_via_script(
            tmp_repo, "M", "gamma", "delta",
            "batch export retried with a circuit breaker instead of retries",
            description="MARK description", stops="no", replaces=m3,
        )
        assert rc4 == 0, f"siembra 4 fallo: stdout={out4!r} stderr={err4!r}"
        m4 = extract_note_id(out4)

        rc_chain, out_chain, err_chain = run_memory_script(
            "search.py", ["alpha", "--chain"], cwd=tmp_repo
        )
        assert rc_chain == 0, f"stdout={out_chain!r} stderr={err_chain!r}"
        assert "Traceback" not in out_chain and "Traceback" not in err_chain
        assert m3 in out_chain, (
            f"{m3} tiene que seguir apareciendo como cabeza de su propio "
            f"hilo dentro de 'alpha' -- si no aparece, la siembra o el fix "
            f"anterior (perdida de linaje cruzando zona) se rompieron, no "
            f"es el hallazgo bajo prueba aqui: {out_chain!r}"
        )

        lines_with_m3 = [
            line for line in out_chain.splitlines() if m3 in line
        ]
        assert not any("cerrada" in line for line in lines_with_m3), (
            f"{m3} tiene una sucesora real ({m4}) -- solo vive fuera de "
            f"esta vista porque se re-archivo bajo [gamma][delta]. "
            f"Etiquetarla 'cerrada' aqui dice que el linaje TERMINO en "
            f"{m3}, cuando en realidad sigue vivo en {m4}: mentira de la "
            f"vista, no un cierre legitimo [model.ChainThread.closed, "
            f"'True = cierre legitimo SIN sucesora']: {lines_with_m3!r}"
        )
        assert any(m4 in line for line in lines_with_m3), (
            f"la etiqueta de {m3} tiene que nombrar a su sucesora real "
            f"({m4}) -- p.ej. 'sustituida por {m4}' o equivalente -- para "
            f"que quien lea la vista sepa que el linaje continua en otra "
            f"zona en vez de asumir que termino ahi: {lines_with_m3!r}"
        )
