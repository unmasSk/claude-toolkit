"""Contrato ROJO, modo test-first (pase de CONTRATO, no barrido
exhaustivo): dos cosas del render de listas de `bin/memory/search.py`
que hoy salen INDISTINGUIBLES y no deberian.

De donde sale el encargo -- ``gitmem search D-056`` (zona
``memory/architecture``, comprobado en vivo antes de escribir esto):

    D-056  memory legibility and integrity batch scoped and ordered
           from Moria review
    Why: la memoria se guarda bien pero se lee mal: el enlace de
    sustitucion se ve por un solo lado y en --todo las archivadas salen
    identicas a las vivas, lo que hizo a un Claude cantar una
    contradiccion falsa entre dos notas supuestamente vivas.

DOS FALLOS, DOS GRUPOS DE TESTS:

1. **Una nota archivada no lleva ninguna marca visual en las listas**
   (``gitmem search <palabra> --todo``, tambien zona). Hoy
   ``report_render.py::_memo_block``/``_restriction_block``/
   ``_incident_block``/``_decision_block`` imprimen SOLO
   ``{marcador}{id}  {titular}`` -- el estado archivada/vigente no esta
   en ese texto en ningun sitio (solo aparece, agregado, en la CABECERA
   del informe: "... N vigentes . M archivadas"). Verificado leyendo
   ``lib/memory/report_render.py`` antes de escribir este fichero.

2. **El enlace de sustitucion (`Note.replaces`) solo se ve por un
   lado.** Hoy ``report_render_note.py::_note_fields`` EXCLUYE
   ``Origin``/``Replaces`` a proposito (regla 2 de su propio molde,
   TEXTOS Sec.2.4: "esos punteros se reservan para el racimo"). El
   racimo (regla 4) SI los muestra, pero solo desde el lado de quien
   MIRA la nota vieja via ``--id`` (el hijo cuelga "nace de {root_id}")
   -- nunca desde el lado de la nota NUEVA vista por su propio ``--id``,
   y nunca en las listas de palabra/zona, donde ``_memo_block`` (y
   hermanos) no imprimen ``replaces`` en absoluto.

CONTRATO ELEGIDO AQUI (literal de texto que este fichero fija, no una
version anterior descrita en ningun documento -- pase de CONTRATO de
Dante, D-056 solo pide EL COMPORTAMIENTO, no las palabras exactas):

- Marca de archivada en listado: la palabra ``archivada`` en la propia
  linea del bloque de la nota -- mismo vocabulario que YA usa el
  sistema para el mismo estado en otros dos sitios (cabecera de
  ``--id``, ``report_render_note.py``; estado de un hijo del racimo,
  ``report_render.py::_cluster_block``), nunca un glifo nuevo inventado
  sin precedente.
- "Sustituye a" en la vista propia de la nota NUEVA (``--id``): el
  texto literal ``sustituye a {old_id}`` -- misma familia que el
  ``nace de {root_id}`` ya literal que usa
  ``report_render_note.py::_cluster_lines`` para el otro sentido del
  mismo tipo de puntero.
- Flecha de vuelta en el listado, junto a la nota NUEVA: ``(↺ {old_id})``
  -- pegada a su propia linea de bloque, visible SIN ``--todo`` (la nota
  nueva es vigente y ya aparece por defecto; exigir ``--todo`` solo para
  ver que sustituyo a algo escondería la marca detras de un flag que no
  tiene que ver con lo que se esta preguntando).

Round trip real, sin fabricar el texto esperado (unmassk-standards
Sec.34): las notas se siembran via `note.py` como PROCESO
(`seed_note_via_script`), y `search.py` se invoca tambien como PROCESO
(`run_memory_script`) -- el camino real de quien usa el sistema, nunca
una llamada directa a un helper interno.

Con el comportamiento sin implementar todavia, todos los tests de este
fichero fallan HOY por la causa real: la marca/el texto/la flecha que
cada uno busca no esta en la salida -- nunca por una traza rota (los
dos scripts que se invocan, `note.py` y `search.py`, ya existen y estan
en verde).
"""

import re

from .conftest import (
    extract_note_id,
    run_memory_script,
    seed_note_via_script,
    seed_zones_json,
)


def _own_block_line(out, note_id):
    """La linea que DECLARA `note_id` como la nota propia de ese bloque
    (marcador de dos caracteres -- '› ' o dos espacios -- seguido del id
    y DOS espacios antes del titular, formato literal de
    `report_render.py::_memo_block` y hermanos) -- nunca una linea que
    solo lo NOMBRA como referencia de otra nota (p.ej. una futura marca
    `(↺ M-old)` colgada del titular de la nota que lo sustituyo). Ancla
    al principio de linea a proposito, para que las dos formas no se
    puedan confundir aunque el id aparezca dos veces en la misma
    salida.
    """
    pattern = re.compile(rf"^(?:› |  ){re.escape(note_id)}  ", re.MULTILINE)
    match = pattern.search(out)
    assert match is not None, (
        f"no se encontro la linea propia (bloque) de {note_id} en la salida: {out!r}"
    )
    line_start = match.start()
    newline_pos = out.find("\n", line_start)
    line_end = newline_pos if newline_pos != -1 else len(out)
    return out[line_start:line_end]


class TestArchivedNoteCarriesAVisualMarkTheLiveSiblingLacks:
    """Fallo 1: en `gitmem search <palabra> --todo`, una nota archivada y
    una viva salen identicas salvo por el recuento de la cabecera --
    D-056 lo cita como la causa directa de una contradiccion falsa."""

    def test_replaced_note_is_marked_archivada_and_its_replacement_is_not(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["auth", "product"])
        rc_old, out_old, err_old = seed_note_via_script(
            tmp_repo, "M", "auth", "product",
            "sessions used memcache for storage",
            description="MARK description", stops="no",
        )
        assert rc_old == 0, f"siembra vieja fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_new, out_new, err_new = seed_note_via_script(
            tmp_repo, "M", "auth", "product",
            "sessions now use redis for storage",
            description="MARK description", stops="no", replaces=old_id,
        )
        assert rc_new == 0, f"siembra nueva fallo: stdout={out_new!r} stderr={err_new!r}"
        new_id = extract_note_id(out_new)

        rc, out, err = run_memory_script("search.py", ["sessions", "--todo"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        old_line = _own_block_line(out, old_id)
        new_line = _own_block_line(out, new_id)

        assert "archivada" in old_line, (
            f"la nota archivada tiene que llevar una marca que la distinga "
            f"de una viva en su propia linea de listado [D-056]: {old_line!r}"
        )
        assert "archivada" not in new_line, (
            f"la nota viva NO puede llevar la marca de archivada: {new_line!r}"
        )


class TestReplacementLinkVisibleFromTheNewNotesOwnIdView:
    """Fallo 2, lado 1: `search.py --id <nueva>` tiene que decir que
    sustituye a la vieja -- hoy `report_render_note.py::_note_fields`
    excluye `replaces` a proposito (regla 2 de su propio molde)."""

    def test_new_notes_own_view_names_the_note_it_replaced(self, tmp_repo):
        seed_zones_json(tmp_repo, ["billing", "invoices"])
        rc_old, out_old, err_old = seed_note_via_script(
            tmp_repo, "M", "billing", "invoices",
            "legacy pricing used a flat monthly fee",
            description="MARK description", stops="no",
        )
        assert rc_old == 0, f"siembra vieja fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_new, out_new, err_new = seed_note_via_script(
            tmp_repo, "M", "billing", "invoices",
            "pricing now uses usage-based tiers",
            description="MARK description", stops="no", replaces=old_id,
        )
        assert rc_new == 0, f"siembra nueva fallo: stdout={out_new!r} stderr={err_new!r}"
        new_id = extract_note_id(out_new)

        rc, out, err = run_memory_script("search.py", ["--id", new_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        assert f"sustituye a {old_id}" in out, (
            f"la vista de la nota NUEVA por su propio --id tiene que decir "
            f"a que nota sustituyo [D-056, enlace de sustitucion por los "
            f"dos lados]: {out!r}"
        )

    def test_a_note_without_any_replaces_link_never_prints_the_phrase(self, tmp_repo):
        seed_zones_json(tmp_repo, ["billing", "invoices"])
        rc, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "billing", "invoices",
            "invoices are emailed within five minutes of issuance",
            description="MARK description", stops="no",
        )
        assert rc == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["--id", note_id], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "sustituye a" not in out, (
            f"una nota sin ningun puntero replaces no puede decir que "
            f"sustituye a nada -- falso positivo: {out!r}"
        )


class TestReplacementLinkVisibleInListings:
    """Fallo 2, lado 2: en las listas (`search.py <palabra>`, con o sin
    `--todo`), junto a la nota que sustituyo a otra tiene que aparecer
    una marca de vuelta hacia la vieja -- hoy ninguno de los bloques de
    `report_render.py` imprime `replaces` en absoluto."""

    def test_the_new_notes_listing_line_carries_a_return_arrow_to_the_old_id(
        self, tmp_repo
    ):
        seed_zones_json(tmp_repo, ["ops", "billing"])
        rc_old, out_old, err_old = seed_note_via_script(
            tmp_repo, "M", "ops", "billing",
            "invoice pdf export used synchronous rendering",
            description="MARK description", stops="no",
        )
        assert rc_old == 0, f"siembra vieja fallo: stdout={out_old!r} stderr={err_old!r}"
        old_id = extract_note_id(out_old)

        rc_new, out_new, err_new = seed_note_via_script(
            tmp_repo, "M", "ops", "billing",
            "invoice pdf export now uses async rendering",
            description="MARK description", stops="no", replaces=old_id,
        )
        assert rc_new == 0, f"siembra nueva fallo: stdout={out_new!r} stderr={err_new!r}"
        new_id = extract_note_id(out_new)

        # SIN --todo a proposito: la nota nueva es vigente y ya aparece
        # por defecto -- la marca de que sustituyo a algo no puede
        # depender de un flag que solo controla si lo ARCHIVADO se ve.
        rc, out, err = run_memory_script("search.py", ["invoice"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        new_line = _own_block_line(out, new_id)
        assert f"(↺ {old_id})" in new_line, (
            f"junto a la nota que sustituyo a {old_id} tiene que colgar la "
            f"marca de vuelta [D-056]: {new_line!r}"
        )

    def test_a_plain_live_note_without_a_replaces_link_shows_no_arrow(self, tmp_repo):
        seed_zones_json(tmp_repo, ["ops", "billing"])
        rc, out_seed, err_seed = seed_note_via_script(
            tmp_repo, "M", "ops", "billing",
            "invoice pdf export retries three times on failure",
            description="MARK description", stops="no",
        )
        assert rc == 0, f"siembra fallo: stdout={out_seed!r} stderr={err_seed!r}"
        note_id = extract_note_id(out_seed)

        rc, out, err = run_memory_script("search.py", ["invoice"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        own_line = _own_block_line(out, note_id)
        assert "↺" not in own_line, (
            f"una nota sin ningun replaces no puede llevar la flecha de "
            f"vuelta -- falso positivo: {own_line!r}"
        )
