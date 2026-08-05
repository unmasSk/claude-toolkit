"""Contador de identificadores y alarma de duplicados -- contrato en
docs/memoria-v2/PIEZAS.md Sec.7.2.

Para que: dar el siguiente identificador de un tipo, y avisar si hay dos
notas con el mismo id. De ahi salen las dos reglas que gobiernan el
modulo entero:

1. El contador es POR TIPO [spec Sec.3.1]: el titular usa un contador
   simple asignado leyendo el indice, y treinta decisiones no pueden
   mover el contador de memos -- si lo hicieran, apareceria un hueco en
   la numeracion de memos que haria pensar que faltan notas.
2. Detecta duplicados, NO los repara [spec Sec.3.1]: es alarma pasiva a
   proposito. Reparar automaticamente renumeraria una nota ya escrita, y
   con ella todos los punteros (Origin/Replaces) que la citan.

Recibe el indice ya cargado como parametro [PIEZAS.md Sec.7.3 "Quien lo
llama": "ids NO [lo llama]"] -- este modulo no lee ficheros ni llama a
git, solo opera sobre la tupla de ``IndexLine`` que le pasan.

Quien lo llama: ``notes.write`` (para el alta) y ``health.duplicates``
(para el aviso del arranque, TEXTOS Sec.3.1: "IDs sin duplicados (68
notas)") -- ninguno de los dos existe todavia (fases 2/3), asi que hoy
esta pieza no tiene consumidor real; el contrato ya declara quien lo
sera.
"""

from model import IndexLine


def next_id(type_: str, index: tuple[IndexLine, ...]) -> str:
    """Siguiente identificador de ``type_`` -- "D-001" en un indice vacio,
    "D-031" tras treinta decisiones existentes.

    Cuenta solo las lineas cuyo id empieza por "``type_``-": el contador
    es por tipo, nunca global -- treinta decisiones no mueven el
    contador de memos.
    """
    prefix = f"{type_}-"
    numbers = [
        int(line.id[len(prefix):])
        for line in index
        if line.id.startswith(prefix)
    ]
    next_number = max(numbers, default=0) + 1
    return f"{prefix}{next_number:03d}"


def find_duplicates(index: tuple[IndexLine, ...]) -> tuple[str, ...]:
    """Identificadores que aparecen mas de una vez en ``index``.

    Alarma pasiva: solo detecta y devuelve los ids repetidos, en el
    orden en que aparece cada uno por primera vez -- no muta ``index``,
    no renumera nada y no decide cual de las dos notas es la valida
    [spec Sec.3.1, "Que NO hace"].
    """
    seen: dict[str, int] = {}
    for line in index:
        seen[line.id] = seen.get(line.id, 0) + 1
    return tuple(id_ for id_, count in seen.items() if count > 1)
