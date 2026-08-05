"""Datos cerrados del sistema de memoria v2 -- contrato en docs/memoria-v2/PIEZAS.md Sec.6.1.

Una sola copia de todo lo que la aduana valida y todo lo que un
rechazo cita literalmente. Es la respuesta directa al fallo mejor
documentado del sistema v1: `Sources:` era obligatorio segun la
definicion de un agente y no vivia en la lista de claves que leian los
parsers, asi que los tres parsers lo descartaban en silencio -- 25
commits escribieron un campo que nadie llego a leer nunca
[medido -- TESTIGO]. La lista de lo valido tiene que ser la misma
pieza que valida, o hay dos verdades el primer dia.

SOLO DATOS. CERO FUNCIONES -- si algun dia hace falta una funcion
aqui, es senal de que la logica se esta colando en la capa de datos
(mismo principio que ya aplica ``emojis.py``).

``FIELDS`` es la pieza clave del proyecto entero: cada campo declara
la ruta ("modulo.funcion") de la funcion que lo lee de verdad. Como
``_FieldSpec.reader`` es un argumento obligatorio del dataclass (sin
valor por defecto), el propio interprete revienta la carga del modulo
en cuanto un campo se declare sin lector -- no hace falta ningun bucle
de validacion aparte; el principio se cae solo en vez de depender de
que alguien se acuerde.

Tabla campo -> lector, copiada de docs/memoria-v2/ARQUITECTURA.md
Sec.6 ("Auditoria: ningun campo sin lector"). Donde esa tabla lista
mas de un lector para un mismo campo (Keys, Replaces, Issue), se copia
el primero -- el mas directo -- como lector unico: el contrato de
``_FieldSpec.reader`` (docs/memoria-v2/PIEZAS.md Sec.6.1) fija una sola
cadena por campo, no una lista.

``Touched:`` (spec-sistema-memoria-v2.md Sec.3.3) no entra en
``FIELDS``: lo escribe exclusivamente el script desde el diff en TODO
commit de trabajo, no es un dato que una nota declare por tipo, y no
aparece en la tabla de ocho campos/ocho lectores de ARQUITECTURA.md
Sec.6 ("Ocho campos, ocho lectores").

``TYPES`` fija, por cada uno de los siete tipos, su descripcion literal
(la misma linea que sale en el rechazo "no sé qué tipo es esto" de
TEXTOS.md Sec.1.4) y sus campos obligatorios/permitidos, derivados de
spec-sistema-memoria-v2.md Sec.3.3 (que campo aplica a que tipo) y
Sec.4 (la tabla de los siete tipos y sus notas). ``description`` es
obligatorio en los siete (model.py, PIEZAS.md Sec.5.3); ``why`` es
obligatorio solo en D (spec Sec.4: "D | decision | ... con su Why
obligatorio") y recomendado -- por tanto permitido, no obligatorio --
en R/X/I (spec Sec.3.3, columna Idioma/Obligatorio de ``Why:``).
``keys`` es generico y sin restriccion de tipo (spec Sec.3.3: "Hasta 5
sinonimos"), por eso esta permitido en los siete. ``replaces`` solo
aparece en la columna "Como muere" de D/M/R (spec Sec.4); Q/X/I/B
mueren por otros mecanismos (asciende/cae, permanente, se cierra,
close) y no lo llevan. ``origin`` aparece citado para M (destilacion,
TEXTOS Sec.1.7; acta de plan, spec Sec.10.2), R (nace de una
incidencia candidata, spec Sec.4) y X (los automaticos que nacen
enlazados a su D, spec Sec.4). **Anadido tambien a D el 2026-08-03**
[decision del propietario, DEUDA.md B19 punto 1]: el propio molde de
TEXTOS.md Sec.2.1/2.4 enseña "D-041 · nace de D-030" -- una decision
que nace de otra decision -- y hasta esa fecha el sistema rechazaba el
ejemplo que el mismo documento usa para ilustrarse. Una decision SI
puede nacer de otra decision (se decide el login con Google, y de ahi
nace una mas pequena -- cuanto dura la sesion -- que sin puntero queda
suelta). Ningun otro tipo lo tiene citado.
``issue`` solo aparece citado para el acta de plan, que "es una M"
(ARQUITECTURA.md Sec.6, fila Issue; spec Sec.10.2) -- por eso solo M
lo permite. ``awaits`` es el campo ``espera:`` de spec Sec.4 ("B ...
Lleva campo `espera:` con el responsable"), obligatorio en B y en
ningun otro tipo. ``context`` no entra en ningun tipo: el contexto de
cierre vive "sin zonas, sin indice" (TEXTOS.md, titulo de Sec.1
"Contexto de cierre"), fuera del sistema de zonas/tipos que ``TYPES``
describe.

``TYPE_INDEX_FILES`` -- que fichero de ``INDEX_FILES`` le toca a cada
tipo de ``TYPES``, derivado de las siete muestras literales de
TEXTOS.md Sec.4 (una por tipo, cada una en el fichero cuyo nombre
coincide) -- **movido aqui el 2026-08-02** desde una copia privada de
``notes.py`` (``_TYPE_TO_INDEX_FILE``): ``vocabulary.py`` ya es la casa
de "los siete tipos" y de "los ocho ficheros de indice" por separado, asi
que la correspondencia entre ambos pertenece al mismo sitio -- una sola
copia, nunca dos. ``bin/memory/reindex.py`` leia antes la tabla privada
de ``notes.py`` directamente (sin nada publico que lo dijera); ahora los
dos -- ``notes.py`` y ``reindex.py`` -- importan esta misma constante.
``ARCHIVED.md`` queda fuera a proposito: nadie escribe ahi desde
``notes.write()`` -- es el destino de ``replace()``/``close()``, un
mecanismo aparte.

La comprobacion de abajo revienta la carga de este modulo si algun dia
se anade o quita un tipo de ``TYPES`` sin traer aqui su fichero de
indice -- mismo principio que ``_FieldSpec.reader`` ya aplica arriba para
lectores: el desajuste se cae solo en vez de depender de que alguien se
acuerde de tocar los dos sitios.
"""

from dataclasses import dataclass
from types import MappingProxyType

# **Pasan a privadas el 2026-08-04** [detector de codigo muerto: 0
# consumidores fuera de este fichero, 0 tests que las nombren -- ver
# test_boundary.py]. Siguen sin estar muertas: son los moldes con los que
# se arman ``FIELDS`` (8 usos) y ``TYPES`` (7 usos) mas abajo -- lo publico
# de este fichero es el DATO ya cerrado (``FIELDS``, ``TYPES`` y las
# constantes de debajo), no la clase con la que se construye.


@dataclass(frozen=True)
class _FieldSpec:
    """Un campo del cuerpo de una nota y quien lo lee de verdad."""

    reader: str  # "modulo.funcion", el modulo relativo a lib/memory/


@dataclass(frozen=True)
class _TypeSpec:
    """Uno de los siete tipos: su descripcion y sus campos."""

    description: str  # la linea que sale en el rechazo "no sé qué tipo es esto"
    required_fields: frozenset
    allowed_fields: frozenset


# El resumen del titular, no la linea entera [spec-sistema-memoria-v2.md
# Sec.3.1]. Subio de 60 a 80 por decision del propietario (2026-08-02).
HEADLINE_MAX = 80

# spec-sistema-memoria-v2.md Sec.3.3, campo Keys: "Hasta 5 sinonimos".
MAX_KEYS = 5

# Ocho campos, ocho lectores -- ARQUITECTURA.md Sec.6.
#
# "why"/"description" -> "report_render.render_zone" (no "report_render.
# render") y "awaits" -> "boot.render" (no "boot.blockers_section")
# [correccion 2026-08-04, decision del orquestador, revocable]: el lector
# declarado tiene que ser una funcion publica que alguien llame DE
# VERDAD desde fuera de su modulo. Antes de esta fecha, "report_render.
# render" apuntaba a un intermediario fantasma que existia solo para
# que este chequeo lo encontrara -- ver el docstring que le quedo a
# "report_render.py" en el sitio donde vivia esa funcion, ya borrada.
# "boot.blockers_section" pasa a privada (razon identica, ver el
# docstring de "boot.py"); su lector real, el que de verdad se invoca
# desde fuera y llega al campo, es "boot.render".
FIELDS = MappingProxyType(
    {
        "why": _FieldSpec(reader="report_render.render_zone"),
        "keys": _FieldSpec(reader="query.by_word"),
        "description": _FieldSpec(reader="report_render.render_zone"),
        "origin": _FieldSpec(reader="clusters.group"),
        "replaces": _FieldSpec(reader="clusters.group"),
        "awaits": _FieldSpec(reader="boot.render"),
        "issue": _FieldSpec(reader="health.plans_unreflected"),
        "context": _FieldSpec(reader="context.latest"),
    }
)

# Los siete tipos [TEXTOS.md Sec.1.4 -- letra y descripcion literales;
# spec-sistema-memoria-v2.md Sec.3.3 y Sec.4 -- que campo aplica a cada uno].
TYPES = MappingProxyType(
    {
        "D": _TypeSpec(
            description="se eligió entre opciones",
            required_fields=frozenset({"description", "why"}),
            allowed_fields=frozenset(
                {"description", "why", "keys", "replaces", "origin"}
            ),
        ),
        "M": _TypeSpec(
            description="un hecho estable del proyecto",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset(
                {"description", "keys", "origin", "replaces", "issue"}
            ),
        ),
        "R": _TypeSpec(
            description="un muro: saltarlo rompe algo",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset(
                {"description", "why", "keys", "origin", "replaces"}
            ),
        ),
        "Q": _TypeSpec(
            description="pregunta abierta, sin respuesta todavía",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset({"description", "keys"}),
        ),
        "X": _TypeSpec(
            description="se estudió y se descartó",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset({"description", "why", "keys", "origin"}),
        ),
        "I": _TypeSpec(
            description="se rompió algo: causa y qué se hizo",
            required_fields=frozenset({"description"}),
            allowed_fields=frozenset({"description", "why", "keys"}),
        ),
        "B": _TypeSpec(
            description="pendiente de fuera; bloquea",
            required_fields=frozenset({"description", "awaits"}),
            allowed_fields=frozenset({"description", "awaits", "keys"}),
        ),
    }
)

# Cada variante -> su forma canonica [TEXTOS.md Sec.1.8]. La forma
# canonica tambien mapea a si misma, para que normalizar sea idempotente.
MARKER_KEYS = MappingProxyType(
    {
        "antipattern": "antipattern",
        "anti-pattern": "antipattern",
        "antipatron": "antipattern",
        "antipatrón": "antipattern",
        "security": "security",
        "seguridad": "security",
        "sec": "security",
        "performance": "performance",
        "perf": "performance",
        "rendimiento": "performance",
        "legal": "legal",
        "legales": "legal",
        "compliance": "legal",
    }
)

# [spec-sistema-memoria-v2.md Sec.3.2 y TEXTOS.md Sec.1.2]
ZONE_BLACKLIST = frozenset({"claude", "user", "session", "project", "workflow"})

# "audit" -> sus dos resoluciones [spec-sistema-memoria-v2.md Sec.3.2 y
# TEXTOS.md Sec.1.3]: registro (zona2, el modulo de la aplicacion) y
# codeaudit (zona1, las auditorias de agentes).
ILLEGAL_WORDS = MappingProxyType({"audit": ("registro", "codeaudit")})

# La pregunta literal, UNA sola copia en todo el sistema [TEXTOS.md Sec.1.5].
PAIN_QUESTION = "¿puede costar datos, horas o producción caída?"

# El umbral de "obviamente igual" que separa una nota parecida de una
# distinta -- "deliberadamente generoso" [PIEZAS.md Sec.6.5: "el umbral
# lo fija quien llama, no ese modulo" (similar.find_similar), y "el mismo
# 'deliberadamente generoso' que fija test_similar.py"]. Vivia -- LITERAL,
# dos copias -- en validator.py:96 y rules.py:117 [revision 2026-08-02,
# hallazgo de Argus]: el mismo patron (un numero escrito mas de una vez)
# que en el sistema anterior llego a estar escrito TRES veces, y las tres
# fallaron. Una sola copia aqui; validator.py y rules.py lo importan.
SIMILARITY_THRESHOLD = 0.5

# Los ocho, y solo ocho [spec-sistema-memoria-v2.md Sec.7]. MEMORY.md y
# PLANS.md quedan fuera a proposito: la propia especificacion los rechaza.
INDEX_FILES = (
    "DECISIONS.md",
    "MEMOS.md",
    "RESTRICTIONS.md",
    "QUESTIONS.md",
    "INCIDENTS.md",
    "DISCARDED.md",
    "BLOCKED.md",
    "ARCHIVED.md",
)

# Que fichero de INDEX_FILES le toca a cada tipo de TYPES -- ver el
# docstring del modulo, parrafo "TYPE_INDEX_FILES", para el porque de
# esta tabla y de donde vino. ARCHIVED.md queda fuera: no es el destino
# de ninguna escritura de `notes.write()`.
TYPE_INDEX_FILES = MappingProxyType(
    {
        "D": "DECISIONS.md",
        "M": "MEMOS.md",
        "R": "RESTRICTIONS.md",
        "Q": "QUESTIONS.md",
        "I": "INCIDENTS.md",
        "X": "DISCARDED.md",
        "B": "BLOCKED.md",
    }
)

assert set(TYPE_INDEX_FILES) == set(TYPES), (
    "vocabulary.py: TYPE_INDEX_FILES ha quedado desincronizado de TYPES -- "
    "todo tipo del vocabulario cerrado necesita su fichero de indice "
    "declarado aqui"
)

# El nombre en castellano de cada tipo, para la cabecera del informe por
# identificador [TEXTOS.md Sec.2.4, molde dictado por el propietario,
# 2026-08-03: "D-030 · decisión · vigente"] -- **anadido 2026-08-03**
# (tarea "informe de nota por id", DEUDA.md #24). Ningun texto de esta
# rama tenia, hasta esta tabla, un nombre en castellano por tipo; se
# tuvo que reconstruir cada uno por separado, y no todos tienen el
# mismo respaldo:
#
# CONFIRMADOS por texto literal ya escrito: "decisión" (el propio molde
# de TEXTOS Sec.2.4); "pregunta", "descarte" e "incidencia" (TEXTOS
# Sec.6, punto 1: "Los emojis. ❓ pregunta · 🚫 descarte (no una
# papelera...) · 🔥 incidencia"). "memo" es la misma palabra en los dos
# idiomas, no hace falta traducirla.
#
# "bloqueante" lo confirma el CONTRATO EN ROJO de esta misma tarea
# (tests/memory/test_search_script.py,
# TestByIdRule2AllCommitFieldsNamedAlignedAndNeverEmpty::
# test_an_absent_field_prints_no_label_at_all: "assert f'{note_id} ·
# bloqueante · vigente' in out") -- un test, no TEXTOS.md, pero un test
# en este sistema es tan contrato como el texto.
#
# "restricción" es el UNICO nombre de esta tabla SIN NINGUN respaldo
# literal (ni texto ni test) -- derivado por simetria con el resto para
# que la cabecera funcione con los siete tipos, no solo con los cinco
# confirmados. Declarado aqui expresamente para quien audite esta
# pieza: si el propietario fija otro nombre, es el unico que cambia.
TYPE_SPANISH_NAME = MappingProxyType(
    {
        "D": "decisión",
        "M": "memo",
        "R": "restricción",  # NO CONFIRMADO -- ver nota de arriba
        "Q": "pregunta",
        "X": "descarte",
        "I": "incidencia",
        "B": "bloqueante",
    }
)

assert set(TYPE_SPANISH_NAME) == set(TYPES), (
    "vocabulary.py: TYPE_SPANISH_NAME ha quedado desincronizado de TYPES -- "
    "todo tipo del vocabulario cerrado necesita su nombre en castellano "
    "declarado aqui"
)
