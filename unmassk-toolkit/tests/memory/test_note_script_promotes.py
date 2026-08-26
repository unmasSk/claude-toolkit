"""Contrato ROJO de `--promotes` en `bin/memory/note.py` -- el tercer
destino de archivo que nadie escribe.

EL HUECO, verificado leyendo el codigo real antes de escribir esto (no
supuesto): `docs/memoria-v2/TEXTOS.md` Sec.4 (linea 727) fija TRES formas
literales de linea de `ARCHIVED.md` -- `replaced by <ID>` * `closed:
<motivo>` * `promoted to <ID>`. El LECTOR de las tres esta construido y
en produccion (`indexes.read_archive()` -> `format.parse_archive_line()`,
exigido por `PIEZAS.md` Sec.643 y Sec.802) -- pero el ESCRITOR solo cubre
dos: `lib/memory/notes.py::replace()` escribe `destination="replaced"`
(linea 360) y `notes.py::close()` escribe `destination="closed"` (linea
472). Ningun camino de produccion escribe jamas `destination="promoted"`.

QUE SIGNIFICA: `spec-sistema-memoria-v2.md` Sec.4 dice que una pregunta
(`Q`) abierta muere ascendiendo -- sube a memo (`M`) si la respuesta es
un hecho, o cae a descartada (`X`) si la respuesta es que no. Hoy esa
ascension no se puede escribir: la unica forma de retirar una `Q` es
`gitmem remove` (cierre generico, "closed: <motivo>"), que pierde en
que se convirtio la pregunta.

LA FORMA DEL COMANDO -- decision del orquestador, 2026-08-05, por
simetria con `--replaces` (mismo patron: la nota nueva declara a que
puntero se refiere, `notes.replace()`/`note.py::--replaces` ya en
produccion sirven de plantilla exacta):

    gitmem note M --zones <z1> <z2> "<titular>" --description "..." \\
        --stops no --promotes Q-007
    gitmem note X --zones <z1> <z2> "<titular>" --description "..." \\
        --promotes Q-007

Los tests de aqui ejecutan `bin/gitmem` (nunca `note.py` directo, y
nunca importando funciones) -- `bin/gitmem` ya esta en produccion y su
propio contrato (`test_gitmem_facade.py::TestAddsNoLogicOfItsOwn`)
exige que despache al script real BYTE A BYTE, un `subprocess.run` sin
logica propia (`bin/gitmem::_dispatch`, ya leido). Usar la fachada aqui
en vez de `note.py` directo es fiel al enunciado de la tarea ("por
donde entra el usuario") sin reinventar la mecanica de despacho.

`--promotes` NO EXISTE HOY en el `argparse` de `note.py` (leido antes de
escribir esto: `_parse_args()` no tiene ese flag). Con el flag ausente,
CUALQUIER llamada de este fichero falla hoy por la MISMA causa real:
`argparse` rechaza `--promotes` como argumento desconocido (returncode 2,
`error: unrecognized arguments: --promotes ...` en stderr) -- no un
rechazo de la aduana, no una traza de pila del propio script.

DOS DECISIONES DE ESTA TAREA, disclosed (no adivinadas en silencio):

1. **Titulares de la pregunta y de la nota que la asciende NO comparten
   vocabulario.** Verificado contra el validador real
   (`validator.validate_replacement` -> `similar.find_similar`,
   `SIMILARITY_THRESHOLD`): si el titular nuevo compartiera demasiadas
   palabras con el de la `Q` que promociona, y `note.promotes` no esta
   entre los campos que `validate_replacement` mira para saltarse esa
   comprobacion (solo mira `note.replaces`), la nota rebotaria por
   "esto pisa a algo ya escrito" -- un rechazo real pero AJENO al
   camino que este contrato quiere aislar. Mismo criterio que ya dejo
   escrito `test_note_script.py::TestCreatesAllSevenNoteTypesForReal`
   (0.109 de solapamiento maximo, muy por debajo del umbral 0.5) --
   aqui los titulares de cada pareja pregunta/nota comparten cero
   palabras de peso a proposito, precisamente para que un fallo de
   estos tests solo pueda venir de `--promotes`, nunca de una colision
   de similitud sin relacion.
2. **La atomicidad de un `git commit` que revienta a mitad
   (`BaseException` real, no un rechazo) no se reproduce aqui.**
   `write()`/`replace()`/`close()` ya comparten el mismo mecanismo de
   restauracion (`try`/`except BaseException` + snapshot, ver docstring
   de `notes.py`) y ya esta cubierto a ese nivel; este fichero es un
   contrato de ACEPTACION a nivel de script (modo test-first, pase de
   contrato -- PIEZAS de "hecho" declaradas por el propietario, no el
   barrido exhaustivo de ramas). Lo que SI prueba cada test de aqui,
   para el punto 6 del encargo ("que la pregunta no salga del indice
   sin que la nota nueva exista, o al reves"): en el camino feliz, un
   SOLO commit real y las tres piezas (indice vigente sin la `Q`,
   indice vigente con la nota nueva, `ARCHIVED.md` con la `Q`) leidas
   TODAS del mismo estado final; en los dos caminos de rebote, que
   NADA cambio (mismo recuento de commits, mismos ids vigentes en los
   dos indices implicados, `ARCHIVED.md` sigue sin la `Q`).

Ronda de verdad, nunca fabricada (unmassk-standards Sec.34): el destino
archivado (`ArchiveLine.destination`/`.destination_detail`) se lee
siempre con el LECTOR real (`indexes.read_archive()` ->
`format.parse_archive_line()`, ya en produccion) contra lo que el
comando ACABA de escribir en este mismo proceso de test -- nunca un
texto de `ARCHIVED.md` tecleado a mano.
"""

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_zones_json,
)

import pytest


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


def _seed_question(repo, zone1, zone2, headline, description):
    """Da de alta una `Q` real via `gitmem note` -- nunca escrita a mano
    en el indice. Devuelve su id real, leido de la propia confirmacion
    del comando (`extract_note_id`), nunca supuesto.

    `--work no` [2026-08-26, D-065/D-066]: la aduana de issues rebota una
    Q sin --issue/--work antes de llegar a `--promotes`, que es lo que
    este fichero prueba -- ajeno al escenario bajo prueba aqui.
    """
    rc, out, err = run_gitmem_script(
        [
            "note", "Q", "--zones", zone1, zone2, headline, "--description", description,
            "--work", "no",
        ],
        cwd=repo,
    )
    assert rc == 0, f"la siembra de la pregunta fallo: stdout={out!r} stderr={err!r}"
    assert "Traceback" not in out and "Traceback" not in err
    return extract_note_id(out)


def _promote_args(note_type, zone1, zone2, headline, promotes_id, *, description=None, stops=None):
    """Argumentos completos para `run_gitmem_script()`, con el subcomando
    `note` YA incluido -- `run_gitmem_script()` (a diferencia de
    `run_memory_script()`) espera el subcomando como primer elemento del
    argv, `bin/gitmem::main()` lo lee de `argv[0]` antes de despachar.
    """
    args = ["note", note_type, "--zones", zone1, zone2, headline]
    if description is not None:
        args += ["--description", description]
    if stops is not None:
        args += ["--stops", stops]
    args += ["--promotes", promotes_id]
    return args


def _combined_has_a_real_rejection(out, err):
    """Marcador ESTRUCTURAL de un rechazo real de la aduana (`rejection.
    build` + `render_terminal`, ya en produccion, `_render()` en
    `rejection.py`) -- el emoji `⛔` y la seccion `Relanza:` los pone
    ESA pieza siempre, para cualquier rechazo, nunca un texto propio de
    este fichero. Sirve para distinguir "el sistema pregunto que hacer"
    de "el sistema revento" sin fabricar el texto exacto de un rechazo
    que todavia no existe en produccion (`--promotes` apuntando a un
    tipo equivocado, o a un id inexistente, no tienen molde en
    `TEXTOS.md` hoy).
    """
    combined = out + err
    return "⛔" in combined and "Relanza:" in combined


class TestQuestionPromotesToMemoInOneCommit:
    """Punto 1 del encargo: una pregunta que asciende a memo -- la `Q`
    sale de `QUESTIONS.md`, entra en `ARCHIVED.md` con `→ promoted to
    <id de la M nueva>`, y la `M` nueva existe y es valida. Punto 5 (ida
    y vuelta real) y punto 6 (nunca a medias) van incluidos: se leen las
    tres piezas del estado final con el lector real, en el mismo test.
    """

    def test_promotes_moves_the_question_to_archived_as_a_new_memo_in_one_commit(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "support"])
        q_id = _seed_question(
            tmp_repo, "product", "support",
            "does support need a dedicated escalation channel for enterprise tickets",
            "Enterprise accounts keep escalating through the generic queue and it gets lost.",
        )

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_gitmem_script(
            _promote_args(
                "M", "product", "support",
                "database backups now run hourly instead of nightly for the archive cluster",
                q_id,
                description="Confirmed with infra: hourly backups shipped last week.",
                stops="no",
            ),
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        new_id = extract_note_id(out)

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            f"promover una pregunta tiene que quedar en UN SOLO commit, "
            f"igual que replace() -- hubo {after - before} commits nuevos"
        )

        pm = pm_path(tmp_repo)
        live_questions = {line.id for line in indexes.read("QUESTIONS.md", pm)}
        assert q_id not in live_questions, (
            f"la pregunta ({q_id}) tiene que salir de QUESTIONS.md tras "
            f"ascender -- sigue ahi: {sorted(live_questions)!r}"
        )

        live_memos = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert new_id in live_memos, (
            f"la memo nueva ({new_id}) tiene que quedar vigente en MEMOS.md: "
            f"{sorted(live_memos)!r}"
        )

        archived = indexes.read_archive(pm)
        archived_by_id = {line.id: line for line in archived}
        assert q_id in archived_by_id, (
            f"la pregunta ({q_id}) tiene que aparecer en ARCHIVED.md, y no "
            f"aparece ninguna: {sorted(archived_by_id)!r}"
        )
        archived_line = archived_by_id[q_id]
        # Contra el lector real (indexes.read_archive -> format.parse_archive_line),
        # nunca un texto tecleado a mano [TEXTOS.md Sec.4].
        assert archived_line.destination == "promoted", (
            f"el destino tiene que ser 'promoted', no {archived_line.destination!r}"
        )
        assert archived_line.destination_detail == new_id, (
            f"el detalle del destino tiene que nombrar la memo nueva real "
            f"({new_id}), y dice {archived_line.destination_detail!r}"
        )


class TestQuestionFallsToDiscardedInOneCommit:
    """Punto 2 del encargo: la misma ascension, cuando la respuesta es
    que no -- la `Q` cae a `X` (descartada) en vez de subir a `M`."""

    def test_promotes_moves_the_question_to_archived_as_a_new_discard_in_one_commit(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["ui", "reports"])
        q_id = _seed_question(
            tmp_repo, "ui", "reports",
            "should the marketing site show live inventory counts on product pages",
            "Marketing asked if we can surface live stock levels on the storefront.",
        )

        before = _git_commit_count(tmp_repo)
        rc, out, err = run_gitmem_script(
            _promote_args(
                "X", "ui", "reports",
                "the vendor integration for freight quotes was dropped this sprint",
                q_id,
                description="Live inventory needs a new vendor feed; not worth it this quarter.",
            ),
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        new_id = extract_note_id(out)

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            f"promover una pregunta a descarte tiene que quedar en UN SOLO "
            f"commit -- hubo {after - before} commits nuevos"
        )

        pm = pm_path(tmp_repo)
        live_questions = {line.id for line in indexes.read("QUESTIONS.md", pm)}
        assert q_id not in live_questions, (
            f"la pregunta ({q_id}) tiene que salir de QUESTIONS.md: "
            f"{sorted(live_questions)!r}"
        )

        live_discards = {line.id for line in indexes.read("DISCARDED.md", pm)}
        assert new_id in live_discards, (
            f"el descarte nuevo ({new_id}) tiene que quedar vigente en "
            f"DISCARDED.md: {sorted(live_discards)!r}"
        )

        archived = indexes.read_archive(pm)
        archived_by_id = {line.id: line for line in archived}
        assert q_id in archived_by_id, (
            f"la pregunta ({q_id}) tiene que aparecer en ARCHIVED.md: "
            f"{sorted(archived_by_id)!r}"
        )
        archived_line = archived_by_id[q_id]
        assert archived_line.destination == "promoted", (
            f"el destino tiene que ser 'promoted' tambien cuando cae a "
            f"descarte -- lo unico que cambia es el TIPO del id nuevo, no "
            f"la palabra del destino [TEXTOS.md Sec.4]: es {archived_line.destination!r}"
        )
        assert archived_line.destination_detail == new_id, (
            f"el detalle tiene que nombrar el descarte real ({new_id}): "
            f"{archived_line.destination_detail!r}"
        )


class TestPromotesOnlyAcceptsAQuestion:
    """Punto 3 del encargo: `--promotes` apuntando a una nota que no es
    `Q` se rechaza -- nada se escribe, y el rechazo es un rechazo real
    de la aduana (marcadores estructurales), no una traza de pila."""

    def test_promotes_pointing_at_a_decision_bounces_without_writing_anything(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "auth"])
        rc_d, out_d, err_d = run_gitmem_script(
            [
                "note", "D", "--zones", "product", "auth",
                "keep using the existing session store for now",
                "--why", "no budget this quarter for a migration",
                "--description", "MARK description for the decision used as a bad --promotes target.",
            ],
            cwd=tmp_repo,
        )
        assert rc_d == 0, f"stdout={out_d!r} stderr={err_d!r}"
        d_id = extract_note_id(out_d)

        pm = pm_path(tmp_repo)
        decisions_before = {line.id for line in indexes.read("DECISIONS.md", pm)}
        memos_before = {line.id for line in indexes.read("MEMOS.md", pm)}
        archived_before = indexes.read_archive(pm)
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_gitmem_script(
            _promote_args(
                "M", "product", "auth",
                "session store migration timeline for next quarter",
                d_id,
                description="MARK description for the note that should never be written.",
                stops="no",
            ),
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"--promotes apuntando a una D (no una Q) tiene que rebotar: "
            f"stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err
        assert _combined_has_a_real_rejection(out, err), (
            f"el rebote tiene que ser un rechazo real de la aduana (⛔ + "
            f"'Relanza:'), no un crash ni un mensaje propio del script: "
            f"stdout={out!r} stderr={err!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, (
            f"un --promotes rechazado no puede dejar ningun commit nuevo -- "
            f"hubo {after - before}"
        )

        decisions_after = {line.id for line in indexes.read("DECISIONS.md", pm)}
        assert decisions_after == decisions_before, (
            "la D usada como blanco erroneo tiene que seguir intacta en su "
            f"indice: antes {sorted(decisions_before)!r}, despues {sorted(decisions_after)!r}"
        )
        memos_after = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert memos_after == memos_before, (
            f"no puede haber aparecido ninguna memo nueva: antes "
            f"{sorted(memos_before)!r}, despues {sorted(memos_after)!r}"
        )
        assert indexes.read_archive(pm) == archived_before, (
            "ARCHIVED.md no puede haber cambiado con un --promotes rechazado"
        )


class TestPromotesToNonexistentQuestionBounces:
    """Punto 4 del encargo: apuntar `--promotes` a un id que no existe
    se rechaza, igual que el sistema ya hace con los demas punteros
    (`Replaces`/`Origin` -- `validator_pointers.validate_pointers`,
    "dangling_pointer")."""

    def test_promotes_pointing_at_a_nonexistent_question_bounces_without_writing_anything(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "auth"])
        fake_id = "Q-999999"

        pm = pm_path(tmp_repo)
        # Repositorio recien instalado: ningun indice existe todavia en
        # disco (nadie ha escrito una nota real en este `tmp_repo`).
        # `indexes.seed()` es la MISMA funcion idempotente que `write()`
        # llama por dentro antes de leer nada [notes.py::write() docstring]
        # -- se usa aqui solo para fijar la linea base "cero notas" antes
        # del intento rechazado, sin reimplementar nada de `notes.py`.
        indexes.seed(pm)
        memos_before = {line.id for line in indexes.read("MEMOS.md", pm)}
        questions_before = {line.id for line in indexes.read("QUESTIONS.md", pm)}
        archived_before = indexes.read_archive(pm)
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_gitmem_script(
            _promote_args(
                "M", "product", "auth",
                "clarified session lifetime policy for the next audit",
                fake_id,
                description="MARK description for the note that should never be written.",
                stops="no",
            ),
            cwd=tmp_repo,
        )
        assert rc != 0, (
            f"--promotes apuntando a {fake_id!r} (que no existe) tiene que "
            f"rebotar: stdout={out!r} stderr={err!r}"
        )
        assert "Traceback" not in out and "Traceback" not in err
        assert _combined_has_a_real_rejection(out, err), (
            f"el rebote tiene que ser un rechazo real de la aduana (⛔ + "
            f"'Relanza:'), no un crash: stdout={out!r} stderr={err!r}"
        )
        assert fake_id in (out + err), (
            f"el rechazo tiene que nombrar el id colgante ({fake_id}) igual "
            f"que ya hace el rechazo de Replaces/Origin: stdout={out!r} stderr={err!r}"
        )

        after = _git_commit_count(tmp_repo)
        assert after == before, (
            f"un --promotes rechazado no puede dejar ningun commit nuevo -- "
            f"hubo {after - before}"
        )
        memos_after = {line.id for line in indexes.read("MEMOS.md", pm)}
        assert memos_after == memos_before, (
            f"no puede haber aparecido ninguna memo nueva: antes "
            f"{sorted(memos_before)!r}, despues {sorted(memos_after)!r}"
        )
        questions_after = {line.id for line in indexes.read("QUESTIONS.md", pm)}
        assert questions_after == questions_before, (
            "QUESTIONS.md no puede haber cambiado -- no habia ninguna pregunta "
            "real que retirar"
        )
        assert indexes.read_archive(pm) == archived_before, (
            "ARCHIVED.md no puede haber cambiado con un --promotes rechazado"
        )
