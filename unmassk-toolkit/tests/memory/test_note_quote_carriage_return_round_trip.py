"""Contrato en ROJO -- Moriarty T1, punto 2 (2026-08-26): un `--quote`
con un `\\r` embebido seguido de un espacio se corrompe en silencio al
releerse, perdiendo un caracter real que SI sobrevive dentro del objeto
git.

EL FALLO, confirmado leyendo el codigo real y reproducido en vivo antes
de escribir esto (mismo criterio que el resto de esta rama, "se prueba
ejecutando, no leyendo"):

1. `note.py --quote "texto con CR\\r dentro"` escribe el valor CRUDO
   (con el `\\r` real dentro) en `Note.quote`, que `format.py::_body_field_line`
   pliega con `_fold("Quote", note.quote)` (`format.py:271-272`). `_fold_raw`
   (`format.py:117-126`) parte el valor por `"\\n"` UNICAMENTE -- un `\\r`
   sin `\\n` al lado no dispara ningun plegado, asi que la linea fisica
   real que git recibe en el commit es UNA SOLA: `"Quote: texto con
   CR\\r dentro"`, con el `\\r` viviendo dentro del contenido de esa
   linea, no como separador de linea.

2. `lib/memory/gitcmd.py::run()` (linea ~78-92) lee CUALQUIER salida de
   git con `subprocess.run(..., text=True, encoding="utf-8", errors=
   "replace")`, SIN `newline=""` -- el modo texto de `subprocess.run` no
   expone forma de desactivar la traduccion de saltos universal: CUALQUIER
   `\\r` en el `stdout` capturado (venga o no seguido de `\\n`, viva o no
   dentro del CONTENIDO de una linea) se traduce a `\\n` en el momento de
   decodificar. La linea fisica unica de arriba, releida a traves de
   CUALQUIER consumidor que pase por `gitcmd.run()` (o por cualquier otro
   subproceso de Python en modo texto -- el mismo efecto no es exclusivo
   de `gitcmd.py`), se convierte en DOS lineas: `"Quote: texto con CR"` y
   `" dentro"` -- el espacio que en el original iba PEGADO justo despues
   del `\\r` sobrevive como caracter, pero ahora es el PRIMER caracter de
   la segunda linea.

3. `format.py::_parse_fields` (linea ~296) trata cualquier linea que
   empiece por un espacio como CONTINUACION del campo anterior, y le
   quita ese espacio (`line[1:]`) para reconstruir el valor -- exactamente
   la misma regla que hace reversible un plegado real (`_fold_raw`). Pero
   aqui esa linea NO es una continuacion de verdad: es la traduccion
   accidental de un `\\r` interno. `_parse_fields` no puede distinguir
   los dos casos -- consume el espacio como si fuera el marcador de
   plegado, y ese espacio (un caracter REAL del texto original, no una
   marca de formato) desaparece para siempre. `Quote` termina siendo
   `"texto con CR\\ndentro"` -- ni el `\\r` original NI el espacio que lo
   seguia sobreviven.

Reproducido en vivo antes de escribir esto: `note.py I --issue none
--quote "texto con CR\\r dentro..."` guarda con `rc == 0`; `query.by_id()`
(canal DISTINTO del que escribio la nota -- lee `git log` por su cuenta,
nunca reutiliza el commit ya parseado por `note.py`) devuelve
`note.quote == "texto con CR\\ndentro..."` -- el espacio real, perdido.

Contrato (unmassk-standards Sec.34, round-trip productor<->consumidor):
lo escrito por `note.py` (el valor que ESTE test tecleo, nunca un
`repr()` de otra ejecucion) tiene que sobrevivir BYTE A BYTE al releerse
por `query.by_id()` -- canal independiente, en proceso, que nunca pasa
por lo que `note.py` ya parseo para imprimir su propia confirmacion.

Cada test compara dos cosas escritas por separado: el valor de `--quote`
que el PROPIO test construyo como argumento de `note.py` (el productor
real, invocado como proceso, nunca importado) contra lo que
`query.by_id()` (el consumidor real, importado por ruta de fichero,
nunca reimplementado a mano) lee de vuelta del commit real. Ninguna
cadena "esperada" se copia de una ejecucion anterior -- Sec.34, "nunca
una snapshot persistida".

Regresion fijada a proposito (GREEN hoy, control de no-sobrecorreccion):
el mismo mecanismo NO corrompe unicode con acentos, emoji, comillas
literales, saltos de linea reales (`\\n` sin `\\r`) ni texto que empieza
igual que una etiqueta de campo real (`"Description: ..."`) -- las cinco
formas que un futuro arreglo de este BREAK 2 no puede romper de paso.
Verificado en vivo antes de escribir esto: las cinco sobreviven
byte a byte hoy.

LIMITE explicito de esta tarea: solo test, en `tests/memory/`. No se
toca `lib/`, `bin/` ni `hooks/` -- el rojo es correcto al entregar.
"""

import os
from contextlib import contextmanager

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    run_git,
    run_memory_script,
    seed_zones_json,
)

_ZONE1 = "quotecrzone"
_ZONE2 = "quotecrzonetwo"


@pytest.fixture
def query_mod():
    return import_lib_memory_module("query")


@contextmanager
def _cwd(path):
    """Cambia el cwd del proceso a `path` durante el bloque, y lo
    restaura siempre -- mismo patron ya fijado en `test_report.py::_cwd`
    / `test_notes.py::_cwd`. `query.by_id()` lee `git log` contra
    `Path.cwd()` (no recibe `root` explicito -- ver su propio docstring),
    asi que llamarlo desde un test necesita este cambio temporal.
    """
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _note_args(note_type, headline, description, quote):
    return [
        note_type,
        "--zones", _ZONE1, _ZONE2,
        headline,
        "--description", description,
        "--issue", "none",
        "--quote", quote,
    ]


def _seed_and_read_back(tmp_repo, query_mod, note_type, headline, description, quote):
    """Guarda una nota real via `note.py` (proceso, nunca importado) con
    `--quote` puesto a `quote`, y la relee via `query.by_id()` (canal
    independiente, en proceso). Devuelve `(note_id, quote_read_back)`.
    """
    seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
    rc, out, err = run_memory_script(
        "note.py", _note_args(note_type, headline, description, quote), cwd=tmp_repo,
    )
    assert rc == 0, (
        f"la siembra real deberia guardarse sin rebotar -- stdout={out!r} "
        f"stderr={err!r}"
    )
    note_id = extract_note_id(out)

    with _cwd(tmp_repo):
        note = query_mod.by_id(note_id)
    assert note is not None, (
        f"query.by_id({note_id!r}) no encontro la nota que note.py acaba "
        f"de confirmar guardada -- fallo de fixture, no del contrato"
    )
    return note_id, note.quote


class TestEmbeddedCarriageReturnFollowedBySpaceLosesARealCharacter:
    """El BREAK 2 en si: rojo hoy, `query.by_id()` devuelve un `quote`
    distinto del que se tecleo -- un caracter real (el espacio que
    seguia al `\\r`) desaparece."""

    def test_quote_survives_the_round_trip_byte_for_byte(self, tmp_repo, query_mod):
        original_quote = (
            "no hace falta abrir nada para esto\r que ya lo sabiamos del trimestre pasado"
        )

        note_id, quote_read_back = _seed_and_read_back(
            tmp_repo, query_mod, "I",
            "an incident whose owner quote has a raw carriage return",
            "reproducing the CR-followed-by-space silent corruption",
            original_quote,
        )

        assert quote_read_back == original_quote, (
            f"{note_id}: la cita real ({original_quote!r}) no sobrevivio "
            f"byte a byte a query.by_id() -- volvio {quote_read_back!r}. "
            f"Diferencia: se perdio el caracter en la posicion "
            f"{next((i for i, (a, b) in enumerate(zip(original_quote, quote_read_back or '')) if a != b), 'longitud distinta')}"
        )

    def test_quote_survives_the_round_trip_via_the_real_commit_object_too(
        self, tmp_repo, query_mod,
    ):
        """Segunda comprobacion, canal DISTINTO todavia: el objeto commit
        real de git, leido con `git cat-file` en modo BINARIO (sin
        `text=True`, sin traduccion de saltos) -- para separar "el dato
        sobrevive dentro de git" de "el LECTOR de Python lo traduce mal
        al decodificar". Si esta pasa y la de arriba falla, el fallo
        esta confirmado en la capa de lectura (`gitcmd.py`/`format.py`),
        nunca en la escritura del commit.
        """
        import subprocess

        original_quote = (
            "otra cita real\r con un espacio justo despues del retorno de carro"
        )

        note_id, _ = _seed_and_read_back(
            tmp_repo, query_mod, "Q",
            "a question whose owner quote also has a raw carriage return",
            "second channel: reading the raw git object in binary mode",
            original_quote,
        )

        raw = subprocess.run(
            ["git", "log", "-1", "--pretty=%B", "HEAD"],
            cwd=tmp_repo,
            capture_output=True,
            timeout=20,
        ).stdout
        decoded = raw.decode("utf-8")

        assert original_quote in decoded, (
            f"{note_id}: el `\\r` real de la cita tiene que sobrevivir "
            f"DENTRO del objeto commit -- leido en binario (sin traduccion "
            f"de saltos), el fragmento {original_quote!r} no aparece en "
            f"{decoded!r}. Si esto falla, el dato ya se perdio al "
            f"ESCRIBIR, no solo al releer -- contradiria la premisa del "
            f"BREAK 2 (que el objeto git conserva el byte)."
        )


class TestOrdinaryQuoteContentAlreadySurvivesTheRoundTrip:
    """Control de no-sobrecorreccion, GREEN hoy -- cinco formas de
    contenido que un arreglo del BREAK 2 no puede romper de paso.
    Verificado en vivo antes de escribir esto: las cinco sobreviven byte
    a byte hoy, sin que nadie las toque todavia.
    """

    @pytest.mark.parametrize(
        "case_name,quote",
        [
            (
                "acentos_y_enes",
                "el dueño dijo que no, sin ningún remordimiento ni añadidos",
            ),
            (
                "emoji",
                "no hace falta 🔥 abrir nada para esto, ya lo sabíamos",
            ),
            (
                "comillas_literales",
                'el dueño dijo "no hace falta" literalmente, con comillas',
            ),
            (
                "salto_de_linea_real_sin_cr",
                "primera linea de la cita\nsegunda linea, sin retorno de carro",
            ),
            (
                "texto_que_imita_un_campo",
                "Description: esto no es un campo real, es solo texto citado "
                "que empieza igual que una etiqueta",
            ),
        ],
    )
    def test_survives_byte_for_byte(self, tmp_repo, query_mod, case_name, quote):
        note_id, quote_read_back = _seed_and_read_back(
            tmp_repo, query_mod, "I",
            f"an incident used only to pin the {case_name} control case",
            f"control case for the CR-round-trip contract: {case_name}",
            quote,
        )

        assert quote_read_back == quote, (
            f"{note_id} ({case_name}): este caso ya sobrevive hoy y tiene "
            f"que seguir haciendolo -- se tecleo {quote!r}, volvio "
            f"{quote_read_back!r}"
        )
