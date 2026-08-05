"""Emojis del sistema de memoria v2 -- contrato en docs/memoria-v2/PIEZAS.md Sec.5.2.

Tres mapeos inmutables. Cero funciones: es datos, no logica -- si algun
dia hace falta una funcion aqui, es senal de que la logica se esta
colando en la capa de datos.

No hay ninguna constante de color (ni ANSI, ni ``supports_color()``, ni
nada que dependa de ``isatty``). Decision cerrada del propietario
(2026-08-02, PIEZAS.md Sec.5.2): quien lee esto es Claude, no una
persona -- un codigo de color no aporta nada, es ruido dentro del texto.
El emoji si aporta, porque viaja DENTRO del texto y sobrevive a
cualquier canal (bloque del hook, mensaje de commit, fichero de indice,
terminal) sin depender de que algo lo interprete. Este modulo sustituye
a ``colors.py``, que declaraba siete constantes ANSI sin un solo
consumidor -- ese era el Fallo 1 que el contrato midio.

TYPE_EMOJI -- el emoji de cada uno de los siete tipos de nota del
vocabulario (D/M/R/Q/X/I/B), clave por el codigo de letra que ya usa la
CLI (``gitmem note D ...``). Se deriva de dos salidas, y solo dos: el
titular del commit (TEXTOS.md Sec.5, el emoji va DESPUES de los
corchetes) y la linea del fichero de archivo (TEXTOS.md Sec.4). Los
siete indices vigentes NO llevan emoji -- por eso el mapa tiene
exactamente estos dos consumidores y no ocho.

CHANNEL_EMOJI -- solo dos entradas, las dos resueltas por el propietario
(PIEZAS.md Sec.5.2 "Resuelto"): el Next (``"next"``, usado por
``format.build_context_message``) -- marca el TITULAR del commit de
cierre, que es el Next obligatorio (spec Sec.9: "el titular ES el
Next... con su emoji"), no el contexto; el cuerpo de ese mismo commit
es el contexto en prosa corrida, sin emoji propio. **Corregido
2026-08-03, decision del propietario (COLA.md Sec.5):** el marcador del
titular pasa de ``⏩`` a ``🧭`` -- el formato nuevo antepone el corchete
literal ``[NEXT]`` al titular (``[NEXT] 🧭 <titular>``), y el propietario
fijo ese glifo como el suyo en el molde literal que aprobo para
TEXTOS.md Sec.5. Reusa el mismo glifo que ``TYPE_EMOJI["D"]`` --mismo
criterio ya declarado para ``SECTION_EMOJI`` arriba: la misma pieza
visual puede senalar dos cosas distintas en dos mapeos separados. Y el
remember/regla (``"rule"``, un commit vacio de titular
``[remember][...] 🧠 <texto>`` [Sec.9.7]). **Productor real: ``rules.add()``**
(``rules.py`` Sec.9.7, capa 4) -- corregido 2026-08-02, hallazgo real: este
docstring seguia diciendo "PENDIENTE, el productor todavia NO EXISTE" y
"``rules.py`` tampoco existe todavia" mucho despues de que las dos cosas
dejaran de ser ciertas (``rules.add()`` importa ``CHANNEL_EMOJI`` y lo usa
en cada alta). Este fichero es capa 0 -- lo primero que alguien lee antes
de tocar nada -- y un "no existe" falso aqui puede llevar a borrar algo
que ya funciona.

**El wip (``"wip"``, 🚧) SI tiene productor desde 2026-08-03** [decision
del propietario, tras verificar un agujero real: ``validator.is_wip()``
ya sabia reconocer y eximir el marcador, pero ningun comando lo escribia
-- una puerta abierta sin llave]. **Productor real: ``bin/memory/
wip.py``** (capa 5), que antepone este marcador al mensaje antes de
llamar a ``notes.write_work()`` -- ya en produccion, sin reescribir su
plomeria. Este docstring decia "no tiene productor en este sistema" --
era cierto hasta esa fecha; queda anotado aqui mismo, no en un parrafo
aparte, para que quien lo lea no tenga que reconciliar dos verdades
distintas en el mismo fichero. ``validator._WIP_MARKER`` lee este mismo
valor (``CHANNEL_EMOJI["wip"]``), nunca un segundo literal "🚧" suelto.

SECTION_EMOJI -- las cabeceras de seccion del informe de zona
(TEXTOS.md Sec.2.1 y 2.3) y del arranque (TEXTOS.md Sec.3.1), clave por
el nombre en espanol de la familia de nota que encabezan. Comparten
glifo con TYPE_EMOJI porque la misma pieza visual senaliza dos cosas
distintas (el tipo de una nota vs. la cabecera de una seccion del
informe) -- por eso son constantes separadas y no una sola, aunque el
caracter coincida letra por letra. No hay entrada para "descartes": el
informe nunca les da una seccion propia, solo aparecen anidados bajo la
decision que los origino.

Quien lee este modulo: ``format.build_subject`` (el emoji del titular),
``indexes.archive`` (el de la linea de archivo),
``format.build_context_message`` (el de contexto), ``rules.add`` (el de
regla -- ver CHANNEL_EMOJI arriba), y ``report_render``/``boot`` (las
cabeceras de seccion).
"""

from types import MappingProxyType

TYPE_EMOJI = MappingProxyType(
    {
        "D": "🧭",  # decision
        "M": "📌",  # memo
        "R": "⚠️",  # restriccion (muro)
        "Q": "❓",  # pregunta abierta
        "X": "🚫",  # descarte -- permanente, no una papelera
        "I": "🔥",  # incidencia
        "B": "⛔",  # bloqueante
    }
)

CHANNEL_EMOJI = MappingProxyType(
    {
        "next": "⏩️",  # [NEXT] del titular -- el avance rapido, con selector de
        # variante para que se pinte como emoji y no plano [decision del
        # propietario, 2026-08-05: revoca el cambio a la brujula, que era
        # el marcador del contexto del sistema viejo]
        "rule": "🧠",  # remember -- regla guardada como commit vacio
        "wip": "🚧",  # checkpoint sin preguntas -- productor: bin/memory/wip.py
    }
)

SECTION_EMOJI = MappingProxyType(
    {
        "restricciones": "⚠️",  # cabecera "RESTRICCIONES" (TEXTOS.md 2.1, 2.3, 3.1)
        "bloqueantes": "⛔",  # cabecera "BLOQUEANTES" (TEXTOS.md 2.1, 3.1)
        "decisiones": "🧭",  # cabecera "DECISIONES" (TEXTOS.md 2.1, 2.3)
        "memos": "📌",  # cabecera "MEMOS" (TEXTOS.md 2.1, 2.3)
        "incidencias": "🔥",  # cabecera "INCIDENCIAS" (TEXTOS.md 2.1, 2.3)
        "preguntas": "❓",  # cabecera "LO QUE ESPERA DE TI" (TEXTOS.md 2.1, 2.3)
    }
)
