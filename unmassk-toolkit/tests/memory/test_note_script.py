"""Contrato ROJO de `bin/memory/note.py` -- PIEZAS.md Sec.10 (fila `note.py`).

`bin/memory/note.py` NO EXISTE TODAVIA. Modo test-first, pase de
CONTRATO (antes de Ultron): estos tests son la ACEPTACION -- lo que
define "hecho" para este script -- no el barrido exhaustivo de ramas
(ese llega en el pase de endurecimiento, tras la implementacion real).

De donde sale cada cosa que este fichero da por cierta, para que Ultron
no tenga que adivinar:

- La tabla de PIEZAS.md Sec.10, fila `note.py`: llama a `notes.write` ·
  `notes.replace` · `notes.discard_alternatives`; admite "tipo, --zones,
  titular, --why, --description, --keys, --stops, --origin, --replaces,
  --awaits, --issue"; imprime "confirmacion con el identificador nuevo,
  o el rechazo".
- Las cuatro filas de test comunes a los once scripts (misma seccion):
  todos los flags de una vez sin rebotar, fallo = codigo de retorno
  distinto de cero, nunca una traza de pila ante entrada mala, las
  siete clases de nota se crean de verdad.
- Las dos reglas fijadas para esta tarea especificamente (encargo del
  propietario, ya costaron un fallo real hoy): primera sentencia
  `force_utf8_streams()` (ya en produccion, `lib/memory/utf8.py`); el
  script resuelve el repositorio por el cwd del PROCESO, nunca por una
  ruta fija -- un lanzamiento desde otro sitio no puede tocar el
  repositorio equivocado.
- Las firmas reales de `lib/memory/notes.py` (`write(note, ctx)`,
  `replace(new, old_id, ctx)`, `discard_alternatives(decision,
  alternatives, ctx)`), `lib/memory/validator.py`
  (`Context(zones, existing_in_zone, known_ids, config)`,
  `validate_pain_question(note, stops)`), `lib/memory/validator_zones.py`
  (`validate_zones(note, zones)`) y `lib/memory/rejection.py`
  (`render_terminal(r)` -- "el que imprime el generador cuando rechaza
  en proceso", literal de su propio docstring) -- todas leidas del
  fichero real antes de escribir este contrato, ninguna supuesta.

GRAMATICA DE CLI ASUMIDA (no hay una unica fuente que la fije entera --
se deriva de los comandos de relanzamiento LITERALES que TEXTOS.md
repite en Sec.1.1/1.5/1.6/1.7/1.9/1.11, todos con la misma forma):

    note.py <TIPO> --zones <zona1> <zona2> "<titular>" \
        [--why "..."] [--description "..."] [--keys k1 k2 ...] \
        [--stops yes|no] [--origin <id1> <id2> ...] \
        [--replaces <ID>|none] [--awaits "..."] [--issue N]

Dos huecos que el contrato NO cierra, anotados aqui en vez de
inventados (encargo explicito: "si algo no te cuadra, anotalo y sigue"):

1. **`--issue`** dispara, segun TEXTOS.md Sec.1.9, una comprobacion real
   contra GitHub (`gh issue view`) -- pero esa comprobacion vive
   declarada como FUERA de `validator.py` ("la 8 [de las nueve
   validaciones]... no vive en esta pieza", `validator.py` cabecera).
   Ningun modulo de produccion de esta rama expone hoy esa funcion, y
   dependerla de `gh` real haria estos tests fragiles (red, auth) sin
   necesidad -- por eso NINGUN test de aqui usa `--issue`. Queda para
   quien escriba ese trozo real de `note.py`.
2. **`--stops`** no es un campo de `Note` (verificado en `model.py`): es
   una respuesta que solo `validator.validate_pain_question(note,
   stops)` consume, y esa funcion queda fuera de `validate_note()` por
   diseño (docstring de `validate_note`). Este contrato SI la ejercita
   (fila 4 de "Sus tests") porque tiene funcion real que llamar y texto
   real que comparar -- pero no fija que estructura de datos concreta
   usa `note.py` para pasar `stops` desde el CLI hasta esa llamada.

Los scripts se prueban EJECUTANDOSE, como procesos reales contra un
repositorio git temporal (`run_memory_script`, `tmp_repo` -- ambos de
`conftest.py`) -- nunca importando sus funciones [PIEZAS.md Sec.10].

Con el script inexistente, TODOS estos tests fallan hoy por la MISMA
causa real: `python3 <ruta inexistente>` devuelve un `returncode` de
Python (no de git, no de la aduana) y un stderr del tipo "can't open
file ... No such file or directory" -- ni las aserciones de contenido
(id real en el indice, texto de rechazo real) ni las de "cero
Traceback" pueden pasar por accidente contra ese mensaje.
"""

import json
import os
from datetime import datetime, timezone

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_memory_script,
    seed_zones_json,
)


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def vocabulary():
    return import_lib_memory_module("vocabulary")


@pytest.fixture
def model():
    return import_lib_memory_module("model")


@pytest.fixture
def validator():
    return import_lib_memory_module("validator")


@pytest.fixture
def rejection_mod():
    return import_lib_memory_module("rejection")


@pytest.fixture
def zones():
    return import_lib_memory_module("zones")


@pytest.fixture
def query():
    return import_lib_memory_module("query")


@pytest.fixture
def clusters():
    return import_lib_memory_module("clusters")


def _seed_zones_with_alias(repo, zones_spec):
    """Escribe `zones.json` a mano, mismo formato canonico que
    `zones.py::_serialize` documenta (`{nombre: {"description": ...,
    "aliases": [...]}}`) -- hace falta porque `seed_zones_json()` de
    `conftest.py` no admite alias (siempre `"aliases": []`), y los tests
    de mas abajo necesitan sembrar una zona CON alias, tal y como
    dejaria `zones.py add ... --aliases` un alta real. JSON literal, sin
    invocar `zones.add()` -- mismo criterio que ya aplica
    `seed_zones_json`: no se ejercita la mecanica de candado de esa
    pieza, solo hace falta que la zona exista con su alias antes de
    invocar el script bajo contrato.

    `zones_spec` es un dict `{nombre_canonico: [alias1, alias2, ...]}`.
    """
    pm = pm_path(repo)
    pm.mkdir(parents=True, exist_ok=True)
    data = {
        name: {"description": f"MARK zone description for {name}", "aliases": list(aliases)}
        for name, aliases in zones_spec.items()
    }
    (pm / "zones.json").write_text(json.dumps(data), encoding="utf-8")


def _find_by_zone_and_headline(indexes_mod, vocabulary_mod, pm, zone1, zone2, headline):
    """Busca, en los siete indices VIGENTES (no ARCHIVED.md), la linea
    cuyo (zone1, zone2, headline) coincide con lo que este test pidio
    guardar -- el id real lo asigna el script por dentro (via
    `ids.next_id`), asi que nunca se supone de antemano, se DESCUBRE
    leyendo el indice real con el lector real (`indexes.read`), mismo
    patron que `test_notes.py::_index_line_for` ya establece para
    `notes.py`.
    """
    for name in vocabulary_mod.INDEX_FILES:
        if name == "ARCHIVED.md":
            continue
        for line in indexes_mod.read(name, pm):
            if line.zone1 == zone1 and line.zone2 == zone2 and line.headline == headline:
                return name, line
    return None, None


def _git_commit_count(repo):
    rc, out, err = run_git(["rev-list", "--count", "HEAD"], repo)
    assert rc == 0, f"git rev-list fallo en el test: {err}"
    return int(out)


class TestAcceptsAllFlagsWithoutBouncing:
    """Fila 1 de "Sus tests" [PIEZAS.md Sec.10]: el coste normal de
    guardar una nota es UN comando y CERO rechazos [spec P5]."""

    def test_decision_with_why_description_and_keys_in_one_call(self, tmp_repo, indexes, vocabulary):
        seed_zones_json(tmp_repo, ["product", "auth"])
        rc, out, err = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", "product", "auth",
                "login with JWT + Google OAuth",
                "--why", "sessions do not scale multi-tenant, Google avoids owning passwords",
                "--description", "Brainstorm on login. Server sessions, own password login, "
                                  "and JWT + Google OAuth were weighed.",
                "--keys", "token", "oauth", "sso",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in err and "Traceback" not in out

        pm = pm_path(tmp_repo)
        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "product", "auth", "login with JWT + Google OAuth"
        )
        assert name == "DECISIONS.md", f"la D no aparecio en su indice real: {out!r}"
        assert line.id in out, (
            f"el id real asignado por el script ({line.id!r}, leido del indice real) "
            f"no aparece en su propia salida: {out!r}"
        )

    def test_blocker_with_awaits_and_keys_in_one_call(self, tmp_repo, indexes, vocabulary):
        seed_zones_json(tmp_repo, ["product", "auth"])
        rc, out, err = run_memory_script(
            "note.py",
            [
                "B",
                "--zones", "product", "auth",
                "google workspace admin consent still pending",
                "--description", "Bulk user import needs the admin.directory.user.readonly scope "
                                  "approved by a Workspace admin.",
                "--awaits", "the client -- Marta, IT at Omawa",
                "--keys", "consent", "admin", "workspace",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in err and "Traceback" not in out

        pm = pm_path(tmp_repo)
        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "product", "auth",
            "google workspace admin consent still pending",
        )
        assert name == "BLOCKED.md", f"la B no aparecio en su indice real: {out!r}"


class TestFailureExitsNonzeroWithRealTextNoTraceback:
    """Filas 2 y 3 de "Sus tests": codigo de retorno distinto de cero, y
    lo que sale por pantalla es el rechazo real (o el error real de
    git), nunca una traza de pila."""

    def test_unknown_zone_is_rejected_with_the_real_customs_text(
        self, tmp_repo, model, validator, rejection_mod
    ):
        # Ninguna zona sembrada -- "billing" no existe en absoluto.
        seed_zones_json(tmp_repo, ["product", "auth"])
        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "billing", "auth",
                "webhooks arrive out of order",
                "--description", "Stripe retries for up to three days without ordering guarantees.",
                "--stops", "no",
            ],
            cwd=tmp_repo,
        )
        assert rc != 0, f"una zona inexistente tiene que rebotar: stdout={out!r}"
        assert "Traceback" not in err and "Traceback" not in out

        # Ronda de verdad, no fabricada: la MISMA funcion real que el
        # script tiene que usar por dentro, llamada aqui de forma
        # independiente con los mismos datos, para obtener el rechazo
        # real y su render real -- productor (script) y consumidor
        # (este assert) comparados, ninguno tecleado a mano [unmassk-
        # standards Sec.34].
        note = model.Note(
            type="M", id="", zone1="billing", zone2="auth",
            headline="webhooks arrive out of order",
            description="Stripe retries for up to three days without ordering guarantees.",
            timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        )
        zones = {
            "product": model.Zone(name="product", description="MARK", aliases=()),
            "auth": model.Zone(name="auth", description="MARK", aliases=()),
        }
        expected_rejection = validator.validate_zones(note, zones)
        assert expected_rejection is not None, "precondicion del test: la zona debe rebotar de verdad"
        expected_text = rejection_mod.render_terminal(expected_rejection)
        combined = out + err
        assert expected_text in combined, (
            f"el texto real del rechazo (calculado con el validador real) no aparece "
            f"en la salida del script.\nesperado:\n{expected_text}\n\nsalida real:\n{combined}"
        )

    def test_missing_stops_answer_for_a_memo_is_rejected_with_the_real_customs_text(
        self, tmp_repo, model, validator, rejection_mod
    ):
        seed_zones_json(tmp_repo, ["database", "backups"])
        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "database", "backups",
                "webhooks arrive out of order",
                "--description", "Stripe retries for up to three days without ordering guarantees.",
                # --stops omitido a proposito: TEXTOS.md Sec.1.5.
            ],
            cwd=tmp_repo,
        )
        assert rc != 0, f"falta --stops, tiene que rebotar: stdout={out!r}"
        assert "Traceback" not in err and "Traceback" not in out

        note = model.Note(
            type="M", id="", zone1="database", zone2="backups",
            headline="webhooks arrive out of order",
            description="Stripe retries for up to three days without ordering guarantees.",
            timestamp=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        )
        expected_rejection = validator.validate_pain_question(note, None)
        assert expected_rejection is not None, "precondicion del test: sin --stops tiene que rebotar"
        expected_text = rejection_mod.render_terminal(expected_rejection)
        combined = out + err
        assert expected_text in combined, (
            f"el texto real de 'falta una respuesta' no aparece en la salida.\n"
            f"esperado:\n{expected_text}\n\nsalida real:\n{combined}"
        )


class TestCreatesAllSevenNoteTypesForReal:
    """Fila 4 de "Sus tests": las siete clases de nota se crean de
    verdad, en un repositorio descartable -- que el camino completo no
    se pruebe nunca de punta a punta es el fallo real que esta fila
    previene."""

    def test_each_of_the_seven_types_produces_a_real_commit_and_index_line(
        self, tmp_repo, indexes, vocabulary
    ):
        # Zona ya en minuscula -- orden del propietario, 2026-08-07: el
        # nombre de zona se normaliza siempre a minuscula al escribir y al
        # resolver [lib/memory/zones.py::normalize]. Sembrar "sevenTypes"
        # (identificador arbitrario, sin significado -- solo tenia que ser
        # unico) y comparar despues contra esa misma cadena con mayuscula
        # intercalada dejaba de casar: la nota se guarda bien, en
        # "seventypes", y la busqueda literal contra "sevenTypes" no la
        # encontraba. No es lo que este test quiere probar -- lo que
        # prueba es que las siete clases de nota se crean de verdad, no el
        # comportamiento de normalizacion de zonas (eso vive en
        # test_zones.py). Se sembra ya en minuscula para no tocar esa
        # mecanica en absoluto.
        seed_zones_json(tmp_repo, ["product", "seventypes"])
        before = _git_commit_count(tmp_repo)

        # (tipo, titular, descripcion, flags extra obligatorios para ESE
        # tipo segun vocabulary.TYPES.required_fields, ya en produccion,
        # leido antes de escribir esta tabla).
        #
        # Titular y descripcion son de SIETE ASUNTOS DISTINTOS -- no
        # variaciones de la misma frase de relleno. La version anterior
        # de este test usaba "<tipo> seven types case" / "MARK description
        # for <tipo>" para las siete, y eso disparaba el rechazo REAL de
        # "esto pisa a algo ya escrito" (validator -> similar.find_similar,
        # umbral vocabulary.SIMILARITY_THRESHOLD=0.5): la D y la M median
        # 0.545 de solapamiento Jaccard entre si -- el sistema hacia lo
        # correcto, el test estaba mal montado (siete notas de siete tipos
        # distintos no tienen titulares casi iguales en la realidad).
        # Verificado con la pieza real (similar.find_similar +
        # vocabulary.SIMILARITY_THRESHOLD) antes de fijar esta tabla: el
        # solapamiento maximo entre cualquier par de las siete de aqui es
        # 0.109, muy por debajo del umbral -- ninguna deberia rebotar
        # contra otra de la misma tanda.
        cases = [
            (
                "D",
                "switch payment provider from Stripe to Adyen",
                "Adyen supports the local payout rails our EU customers need; "
                "Stripe does not.",
                ["--why", "lower fees for EU payouts and native SEPA support "
                          "outweigh migration cost"],
            ),
            (
                "M",
                "search index rebuild takes six hours on cold start",
                "Elasticsearch reindexing the full catalog from scratch takes "
                "about six hours on an empty cluster.",
                ["--stops", "no"],
            ),
            (
                "R",
                "never write to the shared inventory table outside the checkout worker",
                "A second writer racing the checkout worker double-decremented "
                "stock twice last quarter.",
                ["--stops", "yes"],
            ),
            (
                "Q",
                "should returns count against the seller's rating",
                "Support keeps asking whether a returned order should lower a "
                "seller's star rating.",
                # 2026-08-26, D-065/D-066: la aduana de issues en Q/I
                # exige --issue o --work -- este test prueba las siete
                # altas reales, no la aduana en si.
                ["--work", "no"],
            ),
            (
                "X",
                "dropped the idea of a custom image CDN",
                "Evaluated running our own image resizing CDN instead of "
                "Cloudinary; cost and maintenance were not worth it.",
                [],
            ),
            (
                "I",
                "checkout page crashed for guest users after the coupon field shipped",
                "A null pointer on the new coupon input crashed checkout for "
                "anyone without an account for about forty minutes.",
                ["--work", "no"],
            ),
            (
                "B",
                "waiting on legal to approve the new refund policy wording",
                "Marketing cannot publish the updated refund policy page until "
                "legal signs off on the new wording.",
                ["--awaits", "legal -- refund policy sign-off"],
            ),
        ]
        expected_index_file = {
            "D": "DECISIONS.md", "M": "MEMOS.md", "R": "RESTRICTIONS.md",
            "Q": "QUESTIONS.md", "X": "DISCARDED.md", "I": "INCIDENTS.md",
            "B": "BLOCKED.md",
        }

        for type_letter, headline, description, extra_flags in cases:
            rc, out, err = run_memory_script(
                "note.py",
                [
                    type_letter,
                    "--zones", "product", "seventypes",
                    headline,
                    "--description", description,
                    *extra_flags,
                ],
                cwd=tmp_repo,
            )
            assert rc == 0, f"tipo {type_letter} no se pudo crear: stdout={out!r} stderr={err!r}"

            pm = pm_path(tmp_repo)
            name, line = _find_by_zone_and_headline(
                indexes, vocabulary, pm, "product", "seventypes", headline
            )
            assert name == expected_index_file[type_letter], (
                f"tipo {type_letter}: se esperaba en {expected_index_file[type_letter]}, "
                f"encontrado en {name!r}"
            )
            assert line.id.startswith(f"{type_letter}-"), (
                f"el id real {line.id!r} no empieza por el prefijo de su propio tipo"
            )

        after = _git_commit_count(tmp_repo)
        assert after - before == len(cases), (
            f"se esperaban {len(cases)} commits nuevos (uno por tipo), hubo {after - before}"
        )


class TestForceUtf8StreamsFirstStatement:
    """Regla fijada para esta tarea: la primera sentencia ejecutable
    fuerza la codificacion de salida. Sin ella, un rechazo con emojis
    (todo rechazo lleva `⛔` -- `rejection.py::_render`) revienta con
    `UnicodeEncodeError` bajo una consola de codepage heredado en vez de
    ensenar la pregunta que el usuario tiene que contestar. Reproducible
    en cualquier sistema operativo forzando `PYTHONIOENCODING=cp1252`
    [tecnica ya usada en esta rama para el mismo problema, issue #52 --
    ver memoria del agente]."""

    def test_rejection_with_emoji_survives_a_restricted_console_encoding(self, tmp_repo):
        seed_zones_json(tmp_repo, ["product", "auth"])
        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                # Zona inexistente a proposito: dispara un rechazo real,
                # que SIEMPRE lleva el emoji `⛔` por delante del titular
                # [rejection.py::_render].
                "--zones", "doesnotexist", "auth",
                "webhooks arrive out of order",
                "--description", "MARK description",
                "--stops", "no",
            ],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        assert rc != 0, f"la zona inexistente tiene que rebotar tambien bajo cp1252: {out!r}"
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert "⛔" in combined, (
            "el emoji del rechazo real tiene que sobrevivir bajo una consola "
            f"cp1252 -- force_utf8_streams() no protegio la salida: {combined!r}"
        )


class TestRepoResolvedByProcessCwd:
    """Regla fijada para esta tarea: el script resuelve el repositorio
    por el directorio donde se ejecuta, nunca por una ruta fija --
    lanzado hoy mismo desde un sitio distinto de la raiz del repo, un
    fallo asi metio 70 commits falsos en la rama de verdad [DEUDA.md
    punto 21]. La red que impide escribir en el repo real de este
    proyecto (`conftest.py::_guard_against_writing_to_the_real_repo`)
    cubre la mitad negativa; este test cubre la mitad POSITIVA: lanzado
    desde una subcarpeta de `tmp_repo` (no su raiz), el commit tiene que
    aparecer en `tmp_repo` de todas formas."""

    def test_launched_from_a_nested_subdirectory_still_writes_to_that_same_repo(
        self, tmp_repo, indexes, vocabulary
    ):
        nested = os.path.join(tmp_repo, "src", "some", "nested", "place")
        os.makedirs(nested, exist_ok=True)
        # Zona ya en minuscula -- mismo motivo que en
        # TestCreatesAllSevenNoteTypesForReal de mas arriba: "nestedCwd" es
        # un identificador arbitrario (solo tenia que ser unico), y el
        # nombre de zona se normaliza siempre a minuscula al escribir
        # [lib/memory/zones.py::normalize, orden del propietario,
        # 2026-08-07]. Este test prueba que el script resuelve el
        # repositorio por el cwd del proceso, no el comportamiento de
        # normalizacion de zonas -- se sembra ya en minuscula para no
        # rozar esa mecanica.
        seed_zones_json(tmp_repo, ["product", "nestedcwd"])
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "product", "nestedcwd",
                "note written from a nested cwd",
                "--description", "MARK description",
                "--stops", "no",
            ],
            cwd=nested,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            "el commit no aparecio en tmp_repo aunque el script se lanzo desde "
            "una subcarpeta suya -- ¿esta resolviendo el repositorio por una "
            "ruta fija en vez de por el cwd del proceso?"
        )

        pm = pm_path(tmp_repo)
        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "product", "nestedcwd", "note written from a nested cwd"
        )
        assert name == "MEMOS.md" and line is not None


# ---------------------------------------------------------------------------
# T1 de Moriarty (2026-08-04), reproducido en vivo por el orquestador antes
# de encargar esta tarea:
#
#   zones.py add product --description "..." --aliases prod
#   note.py M --zones prod checkout "latency issue on checkout" ...  -> M-001 guardada
#   indice real (MEMOS.md)                                           -> [M-001][prod][checkout]
#   search.py product   ->  CERO NOTAS
#   search.py prod      ->  CERO NOTAS
#
# Guardar una nota con el ALIAS de una zona confirma exito (rc==0, id
# asignado) y despues no se vuelve a encontrar por zona NUNCA MAS -- ni por
# el alias usado, ni por el nombre canonico. Causa ya localizada, no
# reinvestigada aqui: `note.py::_build_candidate()` (bin/memory/note.py,
# lineas ~118-119) mete `args.zones[0]`/`[1]` TAL CUAL en
# `Note.zone1`/`zone2`, sin pasar por `zones.resolve()`. Mientras tanto
# `validator_zones.py::_validate_zone_name()` SI acepta el alias como zona
# valida (`zones_.resolve(name, zones) is not None`) -- con razon, un alias
# ES un nombre valido. Nadie normaliza entre "esto es valido" (el validador)
# y "esto es lo que se escribe" (`_build_candidate`).
#
# Conducta que fija cada test de aqui abajo: una nota dada de alta con el
# ALIAS de una zona se guarda con el NOMBRE CANONICO, y aparece al buscar
# por los dos -- el alias tecleado y el nombre real.
# ---------------------------------------------------------------------------


class TestZoneAliasIsResolvedToCanonicalNameOnWrite:
    def test_alias_in_first_zone_slot_is_stored_and_found_as_canonical(
        self, tmp_repo, indexes, vocabulary, zones
    ):
        _seed_zones_with_alias(tmp_repo, {"product": ["prod"], "checkout": []})

        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "prod", "checkout",
                "latency issue on checkout",
                "--description", "MARK description for the alias-in-first-slot case",
                "--stops", "no",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"el alta con el alias tiene que guardarse: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        note_id = extract_note_id(out)

        pm = pm_path(tmp_repo)
        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "product", "checkout", "latency issue on checkout"
        )
        assert name == "MEMOS.md" and line is not None, (
            f"la nota tiene que aparecer en su indice real BAJO EL NOMBRE "
            f"CANONICO (product), no bajo el alias usado (prod) ni "
            f"desaparecida del todo -- salida del alta: {out!r}"
        )
        assert line.zone1 == "product", (
            f"zone1 del indice real tiene que ser el nombre canonico "
            f"'product', no el alias tecleado en el CLI: {line.zone1!r}"
        )
        assert line.id == note_id

        # `prod` tiene que seguir resolviendo a `product` despues del
        # alta -- si esto fallara, el alta habria corrompido zones.json en
        # vez de solo escribir mal el indice.
        zones_map = zones.load(pm / "zones.json")
        assert zones.resolve("prod", zones_map) == "product"

        rc_canonical, out_canonical, err_canonical = run_memory_script(
            "search.py", ["product"], cwd=tmp_repo
        )
        assert rc_canonical == 0, f"stdout={out_canonical!r} stderr={err_canonical!r}"
        assert note_id in out_canonical, (
            f"buscar por el NOMBRE CANONICO tiene que encontrar la nota "
            f"dada de alta con su alias: {out_canonical!r}"
        )

        rc_alias, out_alias, err_alias = run_memory_script(
            "search.py", ["prod"], cwd=tmp_repo
        )
        assert rc_alias == 0, f"stdout={out_alias!r} stderr={err_alias!r}"
        assert note_id in out_alias, (
            f"buscar por el ALIAS usado al dar de alta tambien tiene que "
            f"encontrar la nota: {out_alias!r}"
        )

    def test_alias_in_second_zone_slot_is_stored_and_found_as_canonical(
        self, tmp_repo, indexes, vocabulary, zones
    ):
        _seed_zones_with_alias(tmp_repo, {"checkout": [], "billing": ["facturacion"]})

        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "checkout", "facturacion",
                "payment retries duplicate the charge",
                "--description", "MARK description for the alias-in-second-slot case",
                "--stops", "no",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"el alta con el alias tiene que guardarse: stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        note_id = extract_note_id(out)

        pm = pm_path(tmp_repo)
        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "checkout", "billing", "payment retries duplicate the charge"
        )
        assert name == "MEMOS.md" and line is not None, (
            f"la nota tiene que aparecer bajo el NOMBRE CANONICO en la "
            f"SEGUNDA zona (billing), no bajo el alias tecleado "
            f"(facturacion) ni desaparecida del todo -- salida del alta: {out!r}"
        )
        assert line.zone2 == "billing", (
            f"zone2 del indice real tiene que ser el nombre canonico "
            f"'billing', no el alias tecleado en el CLI: {line.zone2!r}"
        )
        assert line.id == note_id

        zones_map = zones.load(pm / "zones.json")
        assert zones.resolve("facturacion", zones_map) == "billing"

        rc_canonical, out_canonical, err_canonical = run_memory_script(
            "search.py", ["billing"], cwd=tmp_repo
        )
        assert rc_canonical == 0, f"stdout={out_canonical!r} stderr={err_canonical!r}"
        assert note_id in out_canonical, (
            f"buscar por el NOMBRE CANONICO tiene que encontrar la nota "
            f"dada de alta con su alias en la segunda zona: {out_canonical!r}"
        )

        rc_alias, out_alias, err_alias = run_memory_script(
            "search.py", ["facturacion"], cwd=tmp_repo
        )
        assert rc_alias == 0, f"stdout={out_alias!r} stderr={err_alias!r}"
        assert note_id in out_alias, (
            f"buscar por el ALIAS usado al dar de alta tambien tiene que "
            f"encontrar la nota: {out_alias!r}"
        )


class TestZoneNameCaseIsNormalizedToLowercaseEverywhere:
    """Orden del propietario, 2026-08-07: el nombre de zona va siempre en
    minuscula -- dos sesiones nombrando la misma zona distinto (`Boot` /
    `boot`) acababan con dos zonas que nunca se cruzaban entre si, y las
    notas de una eran invisibles desde la otra: memoria perdida sin un
    solo error por pantalla. Mismo tipo de fallo, misma forma de prueba,
    que la clase de arriba (`TestZoneAliasIsResolvedToCanonicalNameOnWrite`)
    ya fija para alias -- este es su gemelo para mayusculas.

    Round-trip real de punta a punta, no una unidad aislada: alta con el
    script real de zonas (mayuscula inicial) -> resolucion (las tres
    formas llegan a la misma zona) -> la puerta de la nota (se acepta en
    mayuscula, se guarda en minuscula) -> se encuentra buscando por
    cualquiera de las tres formas. Un solo test -- fija el comportamiento
    nuevo, no vuelve a probar zones.py entero por dentro (esa cobertura
    exhaustiva, si hace falta, es tarea de test_zones.py/
    test_zones_script.py, ninguno de los dos tocados aqui)."""

    def test_mixed_case_zone_created_resolved_and_written_all_land_on_the_same_lowercase_zone(
        self, tmp_repo, indexes, vocabulary, zones
    ):
        seed_zones_json(tmp_repo, ["product"])

        # Punto 1 del encargo: el alta con mayuscula inicial guarda en
        # minuscula y lo dice.
        rc_add, out_add, err_add = run_memory_script(
            "zones.py",
            ["add", "Boot", "--description", "MARK zone description for boot"],
            cwd=tmp_repo,
        )
        assert rc_add == 0, f"stdout={out_add!r} stderr={err_add!r}"
        assert "boot" in out_add, (
            f"el alta tiene que confirmar el nombre real guardado (minuscula), "
            f"no solo repetir 'Boot' tal cual se tecleo: {out_add!r}"
        )

        pm = pm_path(tmp_repo)
        zones_map = zones.load(pm / "zones.json")
        assert "boot" in zones_map and "Boot" not in zones_map, (
            f"zones.json tiene que guardar una UNICA zona en minuscula, "
            f"nunca 'Boot' y 'boot' como dos zonas distintas que nunca se "
            f"cruzan -- exactamente el fallo que motivo esta orden: {list(zones_map)!r}"
        )

        # Punto 2: las tres formas resuelven a la misma zona canonica.
        for spelling in ("Boot", "BOOT", "boot"):
            assert zones.resolve(spelling, zones_map) == "boot", (
                f"{spelling!r} tiene que resolver a la zona canonica 'boot'"
            )

        # Punto 3: la puerta de la nota acepta la zona en mayuscula
        # porque existe en minuscula, y la nota se guarda en minuscula.
        rc_note, out_note, err_note = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "product", "BOOT",
                "boot sequence prints the wrong session id",
                "--description", "MARK description for the zone-case round trip",
                "--stops", "no",
            ],
            cwd=tmp_repo,
        )
        assert rc_note == 0, f"stdout={out_note!r} stderr={err_note!r}"
        assert "Traceback" not in out_note and "Traceback" not in err_note
        note_id = extract_note_id(out_note)

        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "product", "boot",
            "boot sequence prints the wrong session id",
        )
        assert name == "MEMOS.md" and line is not None, (
            f"la nota tiene que aparecer en el indice real bajo 'boot' "
            f"(minuscula), no bajo 'BOOT' tal cual se tecleo en el CLI ni "
            f"desaparecida del todo -- salida del alta: {out_note!r}"
        )
        assert line.zone2 == "boot", (
            f"zone2 del indice real tiene que ser 'boot' en minuscula, "
            f"nunca 'BOOT': {line.zone2!r}"
        )
        assert line.id == note_id

        # Se encuentra buscando por cualquiera de las tres formas -- si
        # fallara con alguna, seria la misma perdida silenciosa que
        # motivo el cambio: una nota real, invisible desde otra sesion
        # que tecleo la zona distinto.
        for spelling in ("Boot", "BOOT", "boot"):
            rc_s, out_s, err_s = run_memory_script("search.py", [spelling], cwd=tmp_repo)
            assert rc_s == 0, f"stdout={out_s!r} stderr={err_s!r}"
            assert note_id in out_s, (
                f"buscar por {spelling!r} tiene que encontrar la nota guardada "
                f"bajo 'boot': {out_s!r}"
            )


class TestControlWithCanonicalNamesStillWorksAsBaseline:
    """Control en verde, punto 3 del encargo: sin ningun alias de por
    medio, dar de alta y buscar por el nombre canonico ya funciona hoy.
    Si este test tambien fallara, el problema no seria la resolucion de
    alias sino algo mas amplio en `note.py`/`search.py` -- y las dos
    clases de arriba dejarian de ser una prueba limpia del alias."""

    def test_canonical_names_in_both_slots_are_found_by_search(
        self, tmp_repo, indexes, vocabulary
    ):
        seed_zones_json(tmp_repo, ["product", "checkout"])

        rc, out, err = run_memory_script(
            "note.py",
            [
                "M",
                "--zones", "product", "checkout",
                "cart abandonment spikes on mobile",
                "--description", "MARK description for the canonical-names control case",
                "--stops", "no",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        note_id = extract_note_id(out)

        pm = pm_path(tmp_repo)
        name, line = _find_by_zone_and_headline(
            indexes, vocabulary, pm, "product", "checkout", "cart abandonment spikes on mobile"
        )
        assert name == "MEMOS.md" and line is not None
        assert line.zone1 == "product" and line.zone2 == "checkout"
        assert line.id == note_id

        rc_search, out_search, err_search = run_memory_script(
            "search.py", ["product"], cwd=tmp_repo
        )
        assert rc_search == 0, f"stdout={out_search!r} stderr={err_search!r}"
        assert note_id in out_search


# ---------------------------------------------------------------------------
# Segundo fallo de la misma tanda (2026-08-04), reproducido por el
# orquestador antes de encargar esta tarea:
#
#   note.py D --zones product auth "login with sessions" --why "..." ...   -> D-001
#   note.py D --zones product auth "login with JWT" --why "..." --replaces D-001
#     -> "OK guardada" D-002
#
#   DECISIONS.md:  [D-001][product][auth] login with sessions   <- SIGUE VIVA
#                  [D-002][product][auth] login with JWT
#   ARCHIVED.md:   vacio
#
# `--replaces <ID>` confirma exito y deja las DOS notas vigentes
# contradiciendose para siempre; la vieja nunca sale del indice ni entra en
# el archivo. Causa ya localizada, no reinvestigada aqui: `bin/memory/
# note.py::main()` (linea 168) llama SIEMPRE a `notes.write()`, nunca a
# `notes.replace()` -- la unica funcion (ya implementada, ya probada a
# nivel de libreria) que archiva la vieja y escribe la nueva en el MISMO
# commit [PIEZAS.md Sec.8.1, notes.py::replace() docstring: "la nota
# nueva, su linea de indice, la vieja fuera de su indice, y su linea en
# ARCHIVED.md con destino 'replaced by <new_id>'"]. El puntero `Replaces:`
# SI llega a escribirse en el commit de la nueva (`Note.replaces` viaja tal
# cual hasta `format.build_message` via `write()`) -- lo que falta es la
# mitad que archiva la vieja, no el puntero en si.
#
# `discard_alternatives` queda fuera a proposito -- otro flujo, no tocado
# aqui (encargo explicito de esta tarea).
#
# Conducta que fija la primera clase: con `--replaces <ID>`, la vieja sale
# de su indice VIGENTE y entra en ARCHIVED.md con destino "replaced by
# <nueva>", en un solo commit. La segunda clase es el CONTROL: el centinela
# `--replaces none` («conviven las dos, a proposito» -- literal de
# `validator.py::validate_replacement`, "conviven  --replaces none  las
# dos siguen vigentes») ya funciona hoy (note.py solo llama a write(), que
# no archiva nada) y el arreglo de arriba no puede romperlo.
# ---------------------------------------------------------------------------


class TestReplacesArchivesTheOldNoteInTheSameCommit:
    def test_replaces_moves_the_old_note_to_archived_in_one_commit(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "auth"])

        rc_old, out_old, err_old = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", "product", "auth",
                "login with sessions",
                "--why", "simplest thing that could work at the time",
                "--description", "MARK description for the original decision",
            ],
            cwd=tmp_repo,
        )
        assert rc_old == 0, f"stdout={out_old!r} stderr={err_old!r}"
        assert "Traceback" not in out_old and "Traceback" not in err_old
        old_id = extract_note_id(out_old)

        before = _git_commit_count(tmp_repo)
        rc_new, out_new, err_new = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", "product", "auth",
                "login with JWT",
                "--why", "sessions do not scale across multiple app servers",
                "--description", "MARK description for the replacement decision",
                "--replaces", old_id,
            ],
            cwd=tmp_repo,
        )
        assert rc_new == 0, f"stdout={out_new!r} stderr={err_new!r}"
        assert "Traceback" not in out_new and "Traceback" not in err_new
        new_id = extract_note_id(out_new)

        after = _git_commit_count(tmp_repo)
        assert after == before + 1, (
            f"la sustitucion tiene que quedar en UN SOLO commit "
            f"[notes.py::replace() docstring] -- hubo {after - before} "
            f"commits nuevos en vez de 1"
        )

        pm = pm_path(tmp_repo)
        live_lines = indexes.read("DECISIONS.md", pm)
        live_ids = {line.id for line in live_lines}
        assert old_id not in live_ids, (
            f"la vieja ({old_id}) tiene que salir del indice VIGENTE tras "
            f"la sustitucion -- sigue ahi contradiciendo a la nueva: "
            f"{sorted(live_ids)!r}"
        )
        assert new_id in live_ids, (
            f"la nueva ({new_id}) tiene que quedar vigente: {sorted(live_ids)!r}"
        )

        archived = indexes.read_archive(pm)
        archived_by_id = {line.id: line for line in archived}
        assert old_id in archived_by_id, (
            f"la vieja ({old_id}) tiene que aparecer en ARCHIVED.md, y no "
            f"aparece ninguna -- ARCHIVED.md sigue vacio: {sorted(archived_by_id)!r}"
        )
        archived_line = archived_by_id[old_id]
        # Estructural, contra el ArchiveLine real que devuelve el lector real
        # (indexes.read_archive -> format.parse_archive_line) -- nunca un
        # texto tecleado a mano [TEXTOS.md Sec.4, "los tres destinos,
        # literales: replaced by <ID> · closed: <motivo> · promoted to <ID>"].
        assert archived_line.destination == "replaced", (
            f"el destino tiene que ser 'replaced', no {archived_line.destination!r}"
        )
        assert archived_line.destination_detail == new_id, (
            f"el detalle del destino tiene que nombrar la nota nueva real "
            f"({new_id}), y dice {archived_line.destination_detail!r}"
        )


class TestReplacesNoneSentinelStillLetsBothNotesCoexist:
    """Control en verde, encargo explicito de esta tarea: el centinela
    `--replaces none` no puede romperse con el arreglo de la clase de
    arriba -- este caso ya funciona hoy."""

    def test_replaces_none_keeps_both_notes_live_and_archived_stays_empty(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "auth"])

        rc_first, out_first, err_first = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", "product", "auth",
                "login with sessions",
                "--why", "simplest thing that could work at the time",
                "--description", "MARK description for the first coexisting decision",
            ],
            cwd=tmp_repo,
        )
        assert rc_first == 0, f"stdout={out_first!r} stderr={err_first!r}"
        first_id = extract_note_id(out_first)

        rc_second, out_second, err_second = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", "product", "auth",
                "login with JWT",
                "--why", "sessions do not scale across multiple app servers",
                "--description", "MARK description for the second coexisting decision",
                "--replaces", "none",
            ],
            cwd=tmp_repo,
        )
        assert rc_second == 0, f"stdout={out_second!r} stderr={err_second!r}"
        assert "Traceback" not in out_second and "Traceback" not in err_second
        second_id = extract_note_id(out_second)

        pm = pm_path(tmp_repo)
        live_lines = indexes.read("DECISIONS.md", pm)
        live_ids = {line.id for line in live_lines}
        assert first_id in live_ids and second_id in live_ids, (
            f"con --replaces none las DOS tienen que seguir vigentes -- "
            f"'conviven a proposito': {sorted(live_ids)!r}"
        )

        archived = indexes.read_archive(pm)
        assert not archived, (
            f"con --replaces none no se archiva nada -- ARCHIVED.md tiene "
            f"que seguir vacio: {archived!r}"
        )


# ---------------------------------------------------------------------------
# `discard_alternatives` sin enganchar -- decision del propietario, 2026-08-04
# ("hay que engancharlo, por supuesto"):
#
# `lib/memory/notes.py::discard_alternatives(decision, alternatives, ctx)`
# esta escrita y probada a nivel de libreria [PIEZAS.md Sec.8.1: "un commit
# por descarte, cada uno con su identificador y su linea de indice... una
# decision con dos alternativas produce tres commits, y los tres indices
# cuadran"] y HOY no la llama nadie: `bin/memory/note.py` no tiene ningun
# flag que llegue hasta ella -- verificado leyendo el fichero real antes de
# escribir esto, mismo patron que ya tuvo `notes.replace()` hasta hace un
# rato (clase `TestReplacesArchivesTheOldNoteInTheSameCommit`, mas arriba).
#
# FORMA DE FLAG DECIDIDA AQUI (unico punto de diseno de esta tarea, encargo
# explicito del propietario): `--discard <titular> <porque>`, repetible una
# vez por alternativa (`argparse action="append", nargs=2`), a la misma
# altura que `--origin`/`--keys`/`--replaces` en la gramatica ya fijada en
# la cabecera de este fichero. Linea de comando completa, sobre el mismo
# ejemplo literal de TEXTOS.md Sec.2.1 (D-030 con X-012/X-013):
#
#   note.py D --zones product auth "login with JWT + Google OAuth" \
#       --why "sessions do not scale multi-tenant; Google avoids owning \
#       passwords" \
#       --description "Brainstorm on login options: server sessions, own \
#       password login, and JWT + Google OAuth were weighed." \
#       --discard "server-side sessions" \
#                 "sticky routing complicates horizontal scaling" \
#       --discard "own password login" \
#                 "maintaining passwords costs us one incident a year"
#
# El SEGUNDO valor de cada pareja llena `Note.description` de la
# alternativa, NUNCA `Note.why`: leido de `vocabulary.py` antes de fijar
# esto, `TYPES["X"].required_fields == frozenset({"description"})` --
# `why` es OPCIONAL para X. Si el "porque" fuese a `why` en su lugar, cada
# alternativa nacería sin su UNICO campo obligatorio y
# `validator.validate_fields` la rebotaria siempre: el flag nunca podria
# guardar nada. `discard_alternatives()` prepende el id de la decision al
# `origin` de cada alternativa por si sola [notes.py:292-293] -- por eso
# `--discard` no admite un tercer valor para origen: repetirlo desde
# `note.py` duplicaria el puntero.
#
# TEXTOS.md NO trae un molde de salida para este comando (comprobado --
# ningun "note.py" ni "discard" aparece en ese fichero): estos tests exigen
# solo la CONDUCTA real (codigo de salida, commits reales, indice real,
# `Origin` real via `query`/`clusters`), nunca un texto de pantalla
# inventado a mano.
# ---------------------------------------------------------------------------


class TestDiscardFlagWiresIntoNotesDiscardAlternatives:
    def test_decision_with_two_discards_produces_three_commits_and_real_origin_links(
        self, tmp_repo, indexes, query, clusters, monkeypatch
    ):
        seed_zones_json(tmp_repo, ["product", "auth"])
        before = _git_commit_count(tmp_repo)

        discard_pairs = [
            ("server-side sessions", "sticky routing complicates horizontal scaling"),
            ("own password login", "maintaining passwords costs us one incident a year"),
        ]
        args = [
            "D",
            "--zones", "product", "auth",
            "login with JWT + Google OAuth",
            "--why", "sessions do not scale multi-tenant; Google avoids owning passwords",
            "--description", "Brainstorm on login options: server sessions, own "
                              "password login, and JWT + Google OAuth were weighed.",
        ]
        for headline, why in discard_pairs:
            args += ["--discard", headline, why]

        rc, out, err = run_memory_script("note.py", args, cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err
        decision_id = extract_note_id(out)

        after = _git_commit_count(tmp_repo)
        assert after - before == 3, (
            f"una decision con dos alternativas descartadas tiene que producir "
            f"TRES commits [notes.py::discard_alternatives docstring, "
            f"PIEZAS.md Sec.8.1] -- hubo {after - before}"
        )

        pm = pm_path(tmp_repo)
        decision_lines = indexes.read("DECISIONS.md", pm)
        assert any(line.id == decision_id for line in decision_lines), (
            f"la decision no aparece en su indice real: {out!r}"
        )

        discarded_lines = indexes.read("DISCARDED.md", pm)
        found_by_headline = {line.headline: line for line in discarded_lines}
        assert set(found_by_headline) == {headline for headline, _why in discard_pairs}, (
            f"las dos alternativas tienen que aparecer, y solo ellas, en "
            f"DISCARDED.md: {sorted(found_by_headline)!r}"
        )

        monkeypatch.chdir(tmp_repo)
        for headline, why in discard_pairs:
            line = found_by_headline[headline]
            assert line.zone1 == "product" and line.zone2 == "auth", (
                f"la alternativa tiene que quedar en la MISMA zona que la "
                f"decision: {line.zone1!r}/{line.zone2!r}"
            )

            note = query.by_id(line.id)
            assert note is not None, (
                f"{line.id} (leido del indice real) no se encuentra por su "
                f"propio id via query.by_id -- el lector real y el escritor "
                f"real no cuadran"
            )
            assert note.type == "X", f"la alternativa tiene que ser tipo X, es {note.type!r}"
            assert note.description == why, (
                f"el 'porque' tecleado en --discard tiene que llegar, sin "
                f"transformar, a Note.description de la alternativa: "
                f"esperado {why!r}, real {note.description!r}"
            )
            assert note.origin == (decision_id,), (
                f"el Origin de cada descarte lo tiene que poner "
                f"discard_alternatives() por su cuenta, apuntando SOLO a la "
                f"decision real -- origin real: {note.origin!r}"
            )

        # Ronda de verdad: el escritor real (note.py -> discard_alternatives
        # -> git commit) contra el lector real (query.by_zone + git log) y el
        # agrupador real (clusters.group, por punteros, nunca por parecido)
        # [unmassk-standards Sec.34] -- nada de esto se fabrica a mano.
        zone_notes = query.by_zone("product", "auth")
        zone_clusters = clusters.group(zone_notes, archived_ids=frozenset())
        decision_cluster = next(
            (cluster for cluster in zone_clusters if cluster.root.id == decision_id), None
        )
        assert decision_cluster is not None, (
            f"la decision tiene que ser raiz de su propio racimo real, "
            f"armado por punteros Origin reales, no supuestos: "
            f"racimos reales {zone_clusters!r}"
        )
        child_ids = {child.id for child in decision_cluster.children}
        expected_child_ids = {found_by_headline[headline].id for headline, _why in discard_pairs}
        assert child_ids == expected_child_ids, (
            f"el racimo real de la decision tiene que colgar de sus DOS "
            f"alternativas descartadas, ni mas ni menos: {sorted(child_ids)!r} "
            f"vs esperado {sorted(expected_child_ids)!r}"
        )


class TestDiscardFlagAbsentStillWritesAPlainDecisionInOneCommit:
    """Control explicito, encargo del propietario: comprobar ANTES de
    escribir "que el alta normal, sin descartes, siga funcionando igual.
    Ese control en verde es obligatorio: es lo que se rompe si el flag se
    cuela donde no debe" -- sin `--discard`, `note.py` no puede tocar
    `notes.discard_alternatives` en absoluto, y el resultado tiene que ser
    identico al de antes de esta tarea: un commit, nada en DISCARDED.md."""

    def test_decision_without_discard_flag_still_produces_a_single_commit(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ["product", "auth"])
        before = _git_commit_count(tmp_repo)

        rc, out, err = run_memory_script(
            "note.py",
            [
                "D",
                "--zones", "product", "auth",
                "login with JWT + Google OAuth, no alternatives recorded",
                "--why", "sessions do not scale multi-tenant; Google avoids owning passwords",
                "--description", "MARK description for the no-discard control case.",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

        after = _git_commit_count(tmp_repo)
        assert after - before == 1, (
            f"sin --discard tiene que seguir siendo UN commit, exactamente "
            f"como antes de esta tarea -- hubo {after - before}"
        )

        pm = pm_path(tmp_repo)
        discarded = indexes.read("DISCARDED.md", pm)
        assert not discarded, (
            f"sin --discard, DISCARDED.md tiene que seguir vacio: {discarded!r}"
        )
