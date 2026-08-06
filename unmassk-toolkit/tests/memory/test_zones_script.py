"""Contrato de `bin/memory/zones.py` -- PIEZAS.md Sec.10 (fila `zones.py`).

`bin/memory/zones.py` YA EXISTE (implementado en una sesion anterior,
subcomandos en castellano: `alta`/`listar`/`buscar`). Este fichero anadia
el contrato original de ese alta; esta actualizacion (2026-08-04) endurece
DOS decisiones del propietario, tomadas hoy, sobre el mismo fichero:

**DECISION 1 -- los subcomandos pasan a ingles, sin alias ni periodo de
gracia.** `alta`/`listar`/`buscar` DEJAN de existir; los unicos validos
pasan a ser `add`/`list`/`find` [DEUDA.md B11, PLAN-CONSTRUCCION.md Sec.1:
"todo nombre que ve una maquina va en ingles: scripts, modulos, funciones,
campos, flags y subcomandos"]. `ARQUITECTURA.md` Sec.6bis y `DEUDA.md`
linea 365 siguen citando `gitmem zones alta` -- quedan desactualizados por
esta decision, corregirlos es trabajo de Alexandria, no de este fichero.

**DECISION 2 -- dar de alta un nombre que YA es una zona rebota, no
pisa.** Reproduce el fallo real de hoy: dos altas seguidas sobre el mismo
nombre borraban en silencio el alias y la descripcion de la primera, y
las dos imprimian el MISMO "dada de alta" -- nada distinguia crear de
destruir. El rebote es responsabilidad del SCRIPT (`_cmd_alta`, pronto
`_cmd_add`), no de `lib/memory/zones.py::add()` -- es el script quien
conoce el estado previo antes de llamar a `add()`; `zones.py::add()` en
si mismo sigue sin comprobar nada, tal como esta hoy (leido antes de
escribir este contrato).

**Busque en `docs/memoria-v2/TEXTOS.md` un texto ya fijado para "esa zona
ya existe" y no hay ninguno** -- Sec.1.1 es el rechazo OPUESTO ("zona que
NO existe"); ninguna otra seccion menciona duplicados de zona. Por eso
este contrato exige CONDUCTA (rebota, codigo de retorno distinto de cero,
el fichero no cambia byte a byte) mas UN dato real no fabricado (el
nombre de la zona sobre la que rebota tiene que aparecer en la salida),
nunca una frase de rechazo tecleada a mano.

**Choque contra un ALIAS de otra zona -- CERRADO (2026-08-04), decision
del orquestador que extiende la del propietario, revocable por el.**
`zones.resolve()` SI aplica alias (un nombre que coincide con el alias
de OTRA zona resuelve a esa otra zona), pero la Decision 2 de arriba solo
mira `args.name in existing` (nombres CANONICOS) -- el agujero que queda
al lado, destapado por Ultron al implementar esa decision: dar de alta un
nombre que ya es alias de otra zona no rebota hoy, crea una SEGUNDA zona
con ese nombre y secuestra el alias en silencio (`resolve()` deja de
llevar a la zona vieja). Misma familia de perdida silenciosa que la
Decision 2 ya cerro para el nombre canonico -- ver
`TestRegisteringANameThatIsAnotherZonesAliasBounces` mas abajo. Sin
molde en `TEXTOS.md` para esto tampoco (mismo grep que la Decision 2, sin
resultados) -- aqui ademas el rechazo tiene que DECIR de quien es el
alias (`facturacion` es alias de `billing`), porque el usuario no ve
`facturacion` en ningun listado y un "no" sin decir a quien pertenece no
tiene salida.

**Sin atacante externo, y sin concurrencia real de dos procesos** [encargo
de esta tarea, B22 -- "dos escrituras a la vez sobre el mismo fichero:
no se dan", decision del propietario 2026-08-04: "no va a pasar nunca.
Trabaja en una sola ventana"]. Este contrato no anade ningun test nuevo
de concurrencia. La clase `TestTwoConcurrentRegistrationsDoNotClobberEachOther`
de mas abajo YA EXISTIA antes de B22 y sigue en pie sin tocar su forma
(solo se actualiza el nombre del subcomando) -- es candidata a que el
propietario decida retirarla, anotado en el informe, no decidido aqui.

Round trip real, sin fabricar el texto esperado (unmassk-standards Sec.34):
"la deja legible" y "el fichero no cambia" se comprueban releyendo
`zones.json` con la funcion REAL de produccion, `zones.load()` -- nunca
abriendo el JSON a mano y comparando contra una forma tecleada. El "no
cambia" se comprueba ADEMAS byte a byte sobre el fichero real
(`Path.read_bytes()` antes/despues), tal como pide el encargo.

NOTA heredada del contrato original: no hay aqui un test de "falta el
nombre de la zona" (argparse). Se probo y se descarto a proposito --
mismo motivo que ya declara `test_context_script.py`: con el script
YA EXISTENTE, un fallo de argparse por falta de argumento y cualquier
otro fallo real dan igual la forma "codigo distinto de cero, sin
Traceback" -- hace falta contenido POSITIVO real para no ser vacuo, y
`zones.add()` no valida el contenido del nombre.
"""

import threading

import pytest

from .conftest import import_lib_memory_module, pm_path, run_memory_script


@pytest.fixture
def zones_lib():
    return import_lib_memory_module("zones")


class TestAcceptsAllFlagsWithoutBouncing:
    def test_add_with_description_and_aliases_in_one_call(self, tmp_repo):
        rc, out, err = run_memory_script(
            "zones.py",
            [
                "add", "billing",
                "--description", "cobros, pasarela de pago, suscripciones",
                "--aliases", "cobros", "pagos",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestRegisteredZoneIsReadableBackForReal:
    """"da de alta una zona y la deja legible" -- releida con la funcion
    REAL de produccion (`zones.load`), nunca comparando contra el JSON
    tecleado a mano."""

    def test_zones_load_finds_the_zone_with_its_real_description_and_aliases(
        self, tmp_repo, zones_lib
    ):
        rc, out, err = run_memory_script(
            "zones.py",
            [
                "add", "billing",
                "--description", "cobros, pasarela de pago, suscripciones",
                "--aliases", "cobros", "pagos",
            ],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        zones_path = pm_path(tmp_repo) / "zones.json"
        loaded = zones_lib.load(zones_path)
        assert "billing" in loaded, f"zones.json no tiene la zona recien dada de alta: {loaded!r}"
        zone = loaded["billing"]
        assert zone.description == "cobros, pasarela de pago, suscripciones"
        assert zone.aliases == ("cobros", "pagos")


class TestTwoConcurrentRegistrationsDoNotClobberEachOther:
    """Preexistente al contrato de hoy -- B22 (2026-08-04) descarta el caso
    de dos escrituras a la vez como algo que "no se da" ("trabaja en una
    sola ventana"). No se toca su forma en este pase, solo el nombre del
    subcomando (decision 1); queda anotada en el informe como candidata a
    retirar, decision del propietario, no de este fichero.
    """

    def test_two_zones_py_processes_registering_different_zones_at_once(
        self, tmp_repo, zones_lib
    ):
        errors = []

        def _register(name, description):
            rc, out, err = run_memory_script(
                "zones.py",
                ["add", name, "--description", description],
                cwd=tmp_repo,
            )
            if rc != 0:
                errors.append((name, rc, out, err))

        thread_a = threading.Thread(target=_register, args=("billing", "cobros y pagos"))
        thread_b = threading.Thread(target=_register, args=("invoices", "documentos de factura"))
        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        assert not errors, f"un alta concurrente fallo: {errors}"

        zones_path = pm_path(tmp_repo) / "zones.json"
        loaded = zones_lib.load(zones_path)
        assert "billing" in loaded and "invoices" in loaded, (
            "una de las dos altas concurrentes se perdio -- "
            f"zones.json solo tiene: {sorted(loaded)}"
        )


class TestForceUtf8StreamsFirstStatement:
    def test_accented_description_survives_a_restricted_console_encoding(self, tmp_repo):
        rc, out, err = run_memory_script(
            "zones.py",
            ["add", "facturacion", "--description", "facturación, IVA y notas de crédito"],
            cwd=tmp_repo,
            env={"PYTHONIOENCODING": "cp1252", "LANG": "C", "LC_ALL": "C"},
        )
        combined = out + err
        assert "UnicodeEncodeError" not in combined
        assert "UnicodeDecodeError" not in combined
        assert "Traceback" not in combined
        assert rc == 0, f"un alta valida no deberia fallar bajo cp1252: {combined!r}"


# ---------------------------------------------------------------------------
# Decision 1 (2026-08-04) -- los subcomandos pasan a ingles, sin alias ni
# periodo de gracia. Las clases de arriba ya prueban que `add` funciona
# (parte positiva); las de aqui abajo prueban las dos mitades que faltaban:
# `list`/`find` tambien tienen que funcionar bajo su nombre nuevo, y los
# tres nombres viejos tienen que dejar de estar reconocidos de verdad --
# no solo "fallar", sino fallar SIN haber hecho el efecto que hacian antes.
# ---------------------------------------------------------------------------


class TestNewEnglishSubcommandsWork:
    def test_list_runs_without_bouncing(self, tmp_repo):
        rc, out, err = run_memory_script("zones.py", ["list"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err

    def test_find_runs_without_bouncing(self, tmp_repo):
        rc, out, err = run_memory_script("zones.py", ["find", "bill"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        assert "Traceback" not in out and "Traceback" not in err


class TestOldSpanishSubcommandsNoLongerExist:
    """"Los nombres viejos dejan de existir -- no hay alias ni periodo de
    gracia: nada externo depende de ellos, todo esto esta sin publicar. Un
    test tiene que comprobar que el nombre viejo YA NO FUNCIONA" [encargo
    de esta tarea].

    Para `alta` (el unico de los tres que ESCRIBE), `rc != 0` solo no
    basta -- ver la nota de
    `capa5-read-scripts-and-facade-contract-notes.md` sobre el pitfall de
    confundir "codigo de retorno distinto de cero" con "hizo lo que tenia
    que hacer": el chequeo real es que la zona NO aparezca dada de alta,
    releido con la funcion de produccion `zones.load()`. Para
    `listar`/`buscar` (solo lectura, nada que sembrar y comprobar por su
    ausencia) el dato positivo real es el propio token que se tecleo --
    argparse SIEMPRE lo repite tal cual en su "invalid choice: '<token>'"
    [verificado en vivo contra el binario de hoy: `zones.py add billing
    --description x` -> `invalid choice: 'add' (choose from 'alta',
    'listar', 'buscar')`], asi que exigir que el token real aparezca en la
    salida no es fabricar texto del proyecto -- es el propio contrato de
    argparse.
    """

    def test_alta_no_longer_registers_a_zone(self, tmp_repo, zones_lib):
        rc, out, err = run_memory_script(
            "zones.py",
            ["alta", "billing", "--description", "cobros y pagos"],
            cwd=tmp_repo,
        )
        zones_path = pm_path(tmp_repo) / "zones.json"
        loaded = zones_lib.load(zones_path) if zones_path.exists() else {}
        assert "billing" not in loaded, (
            "el subcomando viejo 'alta' sigue dando de alta zonas de verdad -- "
            f"deberia haber dejado de existir: {loaded!r}"
        )
        assert rc != 0, f"'alta' deberia dejar de ser un subcomando reconocido: rc={rc}"

    def test_listar_is_rejected_as_an_unknown_subcommand(self, tmp_repo):
        rc, out, err = run_memory_script("zones.py", ["listar"], cwd=tmp_repo)
        assert rc != 0, f"'listar' deberia dejar de ser un subcomando reconocido: stdout={out!r} stderr={err!r}"
        assert "listar" in (out + err), (
            "el rechazo de subcomando desconocido tiene que nombrar el token "
            f"real tecleado, no uno generico: stdout={out!r} stderr={err!r}"
        )

    def test_buscar_is_rejected_as_an_unknown_subcommand(self, tmp_repo):
        rc, out, err = run_memory_script("zones.py", ["buscar", "bill"], cwd=tmp_repo)
        assert rc != 0, f"'buscar' deberia dejar de ser un subcomando reconocido: stdout={out!r} stderr={err!r}"
        assert "buscar" in (out + err), (
            "el rechazo de subcomando desconocido tiene que nombrar el token "
            f"real tecleado, no uno generico: stdout={out!r} stderr={err!r}"
        )


# ---------------------------------------------------------------------------
# Decision 2 (2026-08-04) -- dar de alta una zona que ya existe rebota, no
# pisa. Reproduce el fallo real de hoy: dos altas sobre "billing" y la
# segunda borraba en silencio el alias y la descripcion de la primera.
# ---------------------------------------------------------------------------


class TestRegisteringAnExistingZoneNameBounces:
    """El primer alta tiene que triunfar de verdad (con el subcomando
    nuevo, `add`) para que el segundo intento sea una repeticion real, no
    un fallo por otra causa. El choque contra un ALIAS ajeno (no un nombre
    canonico) queda fuera a proposito -- ver el docstring del modulo.
    """

    def test_second_registration_of_the_same_name_is_rejected_and_the_file_is_untouched(
        self, tmp_repo, zones_lib
    ):
        zones_path = pm_path(tmp_repo) / "zones.json"

        rc_first, out_first, err_first = run_memory_script(
            "zones.py",
            [
                "add", "billing",
                "--description", "cobros y pagos",
                "--aliases", "facturacion",
            ],
            cwd=tmp_repo,
        )
        assert rc_first == 0, (
            "el PRIMER alta tiene que triunfar de verdad para que el segundo "
            f"intento sea una repeticion real: stdout={out_first!r} stderr={err_first!r}"
        )

        before_bytes = zones_path.read_bytes()
        before_loaded = zones_lib.load(zones_path)
        assert "billing" in before_loaded, (
            f"la siembra del propio test no dejo la zona legible: {before_loaded!r}"
        )

        rc_second, out_second, err_second = run_memory_script(
            "zones.py",
            ["add", "billing", "--description", "otra descripcion"],
            cwd=tmp_repo,
        )
        assert "Traceback" not in out_second and "Traceback" not in err_second

        assert rc_second != 0, (
            "dar de alta un nombre que YA es una zona tiene que rebotar, no pisar "
            f"lo que habia: stdout={out_second!r} stderr={err_second!r}"
        )
        assert "billing" in (out_second + err_second), (
            "el rebote tiene que nombrar la zona real sobre la que rebota, no un "
            f"mensaje generico: stdout={out_second!r} stderr={err_second!r}"
        )

        after_bytes = zones_path.read_bytes()
        assert after_bytes == before_bytes, (
            "zones.json tiene que quedar BYTE A BYTE como estaba -- el fallo real "
            "de hoy fue que la segunda alta borraba el alias y la descripcion de "
            f"la primera sin avisar.\nantes={before_bytes!r}\ndespues={after_bytes!r}"
        )

        after_loaded = zones_lib.load(zones_path)
        assert set(after_loaded) == set(before_loaded), (
            f"el conjunto de zonas cambio: antes={sorted(before_loaded)} "
            f"despues={sorted(after_loaded)}"
        )
        zone_before = before_loaded["billing"]
        zone_after = after_loaded["billing"]
        assert zone_after.description == zone_before.description, (
            f"la descripcion cambio: antes={zone_before.description!r} "
            f"despues={zone_after.description!r}"
        )
        assert zone_after.aliases == zone_before.aliases, (
            f"los alias cambiaron: antes={zone_before.aliases!r} "
            f"despues={zone_after.aliases!r}"
        )


# ---------------------------------------------------------------------------
# El agujero al lado de la Decision 2 -- cerrado por decision del
# orquestador (2026-08-04), extendiendo la del propietario. Ver el
# docstring del modulo, parrafo "Choque contra un ALIAS de otra zona".
# ---------------------------------------------------------------------------


class TestRegisteringANameThatIsAnotherZonesAliasBounces:
    """Distinto del test de arriba (`TestRegisteringAnExistingZoneNameBounces`):
    ese siembra "billing" con el alias "facturacion" pero solo reintenta dar
    de alta "billing" (su propio nombre canonico) por segunda vez -- nunca
    intenta registrar "facturacion" como nombre NUEVO. Ese caso concreto --
    colisionar contra el propio alias de la unica zona sembrada -- no esta
    cubierto por ningun test existente antes de este; no hay duplicacion.

    Reproduce el agujero real: "billing" ya tiene el alias "facturacion";
    dar de alta una zona NUEVA llamada "facturacion" tiene que rebotar
    igual que si "facturacion" fuera ya un nombre canonico, dejar
    `zones.json` intacto byte a byte, Y nombrar en la salida tanto el
    alias como la zona duena (`billing`) -- a diferencia del rebote por
    nombre canonico, aqui el usuario no ve "facturacion" en ningun
    listado, asi que un rebote que solo diga "ya existe" no le da ninguna
    salida.
    """

    def test_registering_a_name_that_is_another_zones_alias_is_rejected_and_names_the_owner(
        self, tmp_repo, zones_lib
    ):
        zones_path = pm_path(tmp_repo) / "zones.json"

        rc_first, out_first, err_first = run_memory_script(
            "zones.py",
            [
                "add", "billing",
                "--description", "cobros y pagos",
                "--aliases", "facturacion",
            ],
            cwd=tmp_repo,
        )
        assert rc_first == 0, (
            "el PRIMER alta (billing, con alias facturacion) tiene que "
            f"triunfar de verdad para que el choque de alias sea real: "
            f"stdout={out_first!r} stderr={err_first!r}"
        )

        before_bytes = zones_path.read_bytes()
        before_loaded = zones_lib.load(zones_path)
        assert "billing" in before_loaded and "facturacion" in before_loaded["billing"].aliases, (
            f"la siembra del propio test no dejo el alias legible: {before_loaded!r}"
        )
        assert zones_lib.resolve("facturacion", before_loaded) == "billing", (
            "la siembra del propio test no deja resolve('facturacion') "
            f"apuntando a billing todavia: {before_loaded!r}"
        )

        rc_second, out_second, err_second = run_memory_script(
            "zones.py",
            ["add", "facturacion", "--description", "otra cosa"],
            cwd=tmp_repo,
        )
        assert "Traceback" not in out_second and "Traceback" not in err_second

        assert rc_second != 0, (
            "dar de alta un nombre que YA es alias de otra zona tiene que "
            "rebotar igual que un nombre canonico -- hoy crea una segunda "
            f"zona y secuestra el alias: stdout={out_second!r} stderr={err_second!r}"
        )
        combined_second = out_second + err_second
        assert "facturacion" in combined_second, (
            "el rebote tiene que nombrar el alias real sobre el que choca: "
            f"{combined_second!r}"
        )
        assert "billing" in combined_second, (
            "el rebote tiene que decir de QUIEN es ese alias -- el usuario no "
            f"ve 'facturacion' en ningun listado, un 'ya existe' sin decir de "
            f"quien no le da salida: {combined_second!r}"
        )

        after_bytes = zones_path.read_bytes()
        assert after_bytes == before_bytes, (
            "zones.json tiene que quedar BYTE A BYTE como estaba -- registrar "
            "'facturacion' no puede crear una segunda zona que secuestre el "
            f"alias de la primera.\nantes={before_bytes!r}\ndespues={after_bytes!r}"
        )

        after_loaded = zones_lib.load(zones_path)
        assert set(after_loaded) == set(before_loaded), (
            f"el conjunto de zonas cambio: antes={sorted(before_loaded)} "
            f"despues={sorted(after_loaded)}"
        )
        assert zones_lib.resolve("facturacion", after_loaded) == "billing", (
            "resolve('facturacion') tiene que seguir llevando a billing -- si "
            "llevara a otra zona (o a ninguna), el alias quedo secuestrado en "
            "silencio, el mismo fallo que el rebote existe para evitar"
        )


# ---------------------------------------------------------------------------
# RED (encargo del orquestador, 2026-08-06) -- `zones.py list` enmascara
# "zones.json no existe" como "zones.json existe pero esta vacio". Las dos
# ramas de `_cmd_list()` pasan por `zones_lib.load(path)`, y esa funcion
# devuelve `{}` en ambos casos: fichero ausente (captura `FileNotFoundError`,
# `lib/memory/zones.py::load`, docstring: "Un fichero ausente se trata como
# 'todavia no hay ninguna zona'") y fichero presente con el objeto JSON
# vacio `{}` -- exactamente el mismo `len(zones_map) == 0` en los dos casos,
# asi que `_cmd_list()` imprime el MISMO texto (`f"zones.json tiene 0
# zonas:"`) para dos hechos distintos.
#
# `lib/memory/health.py::memory_mounted()` YA distingue estos dos casos para
# su propio informe (lineas ~448-457, citadas tal cual):
#
#     zones_path = pm / "zones.json"
#     if not zones_path.exists():
#         missing.append("zones.json (no existe)")
#     else:
#         ...
#         if zone_count == 0:
#             missing.append("zones.json (existe, pero no tiene ninguna zona
#             dada de alta)")
#
# Este contrato no fabrica un texto nuevo para "no existe": reutiliza el
# MISMO texto que `memory_mounted()` ya imprime en produccion hoy (no un
# texto tecleado a mano por este fichero de test) -- el encargo pide
# explicitamente reusar esa logica, no una segunda lectura silenciosa.
# ---------------------------------------------------------------------------


class TestListDistinguishesAbsentFromEmptyZonesJson:
    """`zones list` en un proyecto recien instalado (zones.json nunca
    sembrado) y en un proyecto donde zones.json existe pero quedo con
    `{}` (todas las zonas borradas a mano, o un alta que fallo a mitad)
    son dos estados distintos -- el primero significa "todavia no se ha
    dado de alta ninguna zona nunca", el segundo "alguien ya toco este
    fichero y hoy no queda ninguna zona en el". Hoy `zones.py list`
    imprime la misma linea para los dos.
    """

    def test_missing_and_empty_zones_json_produce_different_output(self, tmp_repo):
        zones_path = pm_path(tmp_repo) / "zones.json"
        assert not zones_path.exists(), (
            "asuncion del fixture: tmp_repo empieza sin zones.json"
        )

        rc_missing, out_missing, err_missing = run_memory_script(
            "zones.py", ["list"], cwd=tmp_repo
        )
        assert rc_missing == 0, f"stdout={out_missing!r} stderr={err_missing!r}"
        assert "Traceback" not in out_missing and "Traceback" not in err_missing

        zones_path.parent.mkdir(parents=True, exist_ok=True)
        zones_path.write_text("{}", encoding="utf-8")

        rc_empty, out_empty, err_empty = run_memory_script(
            "zones.py", ["list"], cwd=tmp_repo
        )
        assert rc_empty == 0, f"stdout={out_empty!r} stderr={err_empty!r}"
        assert "Traceback" not in out_empty and "Traceback" not in err_empty

        assert out_missing != out_empty, (
            "'zones list' imprime el MISMO mensaje tanto si zones.json "
            "nunca se creo como si existe pero quedo vacio -- son dos "
            "hechos distintos y tienen que leerse distinto.\n"
            f"ausente: {out_missing!r}\n"
            f"vacio:   {out_empty!r}"
        )

    def test_missing_zones_json_says_it_does_not_exist(self, tmp_repo):
        zones_path = pm_path(tmp_repo) / "zones.json"
        assert not zones_path.exists()

        rc, out, err = run_memory_script("zones.py", ["list"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        assert "no existe" in out, (
            "cuando zones.json nunca se ha creado, la salida tiene que "
            "decirlo explicitamente -- mismo texto que "
            "health.memory_mounted() ya usa hoy para este mismo hecho "
            "(lib/memory/health.py: \"zones.json (no existe)\"), no una "
            f"frase nueva inventada por este test: {out!r}"
        )

    def test_present_but_empty_zones_json_does_not_claim_it_does_not_exist(
        self, tmp_repo
    ):
        zones_path = pm_path(tmp_repo) / "zones.json"
        zones_path.parent.mkdir(parents=True, exist_ok=True)
        zones_path.write_text("{}", encoding="utf-8")

        rc, out, err = run_memory_script("zones.py", ["list"], cwd=tmp_repo)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        assert "no existe" not in out, (
            "zones.json SI existe en disco (esta prueba lo escribe antes de "
            "invocar el script) -- la salida no puede decir que no existe, "
            f"eso mentiria sobre un fichero que esta ahi mismo: {out!r}"
        )
