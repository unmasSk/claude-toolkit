"""Deteccion de parecido entre notas -- contrato en docs/memoria-v2/PIEZAS.md Sec.6.5.

Para que: detectar si una nota nueva pisa a otra que ya esta escrita,
dentro de la misma zona. De ahi sale el equilibrio que gobierna todo el
modulo: si detecta de mas, el rechazo del validador (TEXTOS.md Sec.1.6)
salta siempre y se acaba ignorando siempre -- que es peor que no
tenerlo. Si detecta de menos, se duplica una decision y conviven dos
verdades sin que nadie lo note.

De que salida se deriva: del rechazo 1.6 [TEXTOS.md Sec.1.6], y el
texto manda sobre la firma. El rechazo imprime las candidatas con su
fecha, sus keys y su porque entero -- de ahi que esta pieza devuelva
notas ENTERAS, nunca identificadores: si devolviera identificadores,
el rechazo tendria que ir a buscarlas otra vez, y esa es la segunda
puerta de lectura que el diseno prohibe [PIEZAS.md Sec.6.5].

Recibe los datos ya cargados. No lee ficheros y no llama a git -- quien
la llama es el validador (``validator.validate_replacement``), que si
sabe de donde sacarlos [PIEZAS.md Sec.6.5 "Superficie"].

Que NO hace: no decide que pasa con el parecido -- eso es
``validator.validate_replacement``, que es quien rechaza pidiendo
``--replaces``. No busca fuera de la zona: comparar entre zonas
distintas es ruido por definicion, asi que una nota de otra zona ni
siquiera se puntua.

Que del v1 NO se trae [medido -- TESTIGO Sec.1]: ``recall_relevant``,
79 lineas de motor de relevancia con suelo de puntuacion y fraccion
superior propios, escrita, probada con ocho tests en verde, y CERO
consumidores en todo el repo -- la pieza que mejor explica por que
existe la puerta del llamador declarado. Por eso este modulo es
deliberadamente pequeno: una medida de solapamiento de vocabulario,
sin suelo de puntuacion ni logica de "top N" propia -- el umbral lo
fija quien llama (``threshold``), no este modulo.

La medida: Jaccard sobre el vocabulario (headline + description + why
+ keys, en minusculas) de cada nota. Simple y simetrica -- el propio
test_similar.py lo dice explicito: el umbral 0.5 de sus tests es
"deliberadamente generoso", separa solo "obviamente igual" de
"obviamente distinto", no acopla el test a una formula concreta.
"""

import re

import textnorm
from model import Note

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(note: Note) -> frozenset:
    """Vocabulario de una nota: headline + description + why + keys, en
    minusculas y sin acentos (``textnorm.normalize_text``, compartida con
    `zones.py`/`rules_similarity.py` -- ver el docstring de `textnorm.py`).

    ``why`` es opcional (``None`` fuera de tipo D, ver model.py); se
    omite cuando falta en vez de tratarlo como cadena vacia. Las keys
    entran palabra a palabra, no como frase, porque cada key ya es un
    termino independiente [TEXTOS.md Sec.1.8].
    """
    parts = [note.headline, note.description]
    if note.why:
        parts.append(note.why)
    parts.extend(note.keys)

    text = textnorm.normalize_text(" ".join(parts))
    return frozenset(_WORD_RE.findall(text))


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Solapamiento de dos vocabularios: interseccion sobre union.

    Dos vocabularios vacios no son "identicos" -- son datos ausentes, y
    tratarlos como parecido perfecto inflaria el rechazo justo en el
    caso con menos evidencia. Devuelve 0.0 ahi, nunca division por cero.
    """
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _zone_pair(note: Note) -> frozenset:
    """La pareja de zonas de una nota como CONJUNTO, no como secuencia.

    Solo para las puertas de duplicado de este modulo (``find_similar``,
    ``_find_exact_key_match``) [BREAK 2 de Moriarty, test
    ``TestSameKeysZonesSwappedStillBounces``]: dos notas sobre el mismo
    asunto con la pareja de zonas escrita al reves (``gamma delta`` vs
    ``delta gamma``) tienen que verse como la MISMA pareja aqui. No toca
    como se guardan o se resuelven las zonas en ningun otro sitio del
    sistema -- ``zone1``/``zone2`` siguen teniendo su rol y su orden en
    el resto del modelo; esto es solo la comparacion dentro de esta
    deteccion de duplicados.
    """
    return frozenset((note.zone1, note.zone2))


def find_similar(
    candidate: Note,
    existing: tuple[Note, ...],
    threshold: float,
) -> tuple[Note, ...]:
    """Candidatas de ``existing`` que pisan a ``candidate``, notas enteras.

    Compara solo contra notas de la MISMA zona -- ``zone1`` y ``zone2``
    las dos, nunca solo la primera: comparar entre zonas distintas es
    ruido por definicion [PIEZAS.md Sec.6.5]. La pareja se compara como
    CONJUNTO, sin orden (``_zone_pair``) -- no decide que hacer con
    el parecido; eso es ``validator.validate_replacement``.
    """
    candidate_words = _tokens(candidate)
    candidate_zones = _zone_pair(candidate)
    matches = []
    for note in existing:
        if _zone_pair(note) != candidate_zones:
            continue
        if _jaccard(candidate_words, _tokens(note)) >= threshold:
            matches.append(note)
    return tuple(matches)


def _find_exact_key_match(
    candidate: Note,
    existing: tuple[Note, ...],
) -> tuple[Note, ...]:
    """Candidatas de ``existing`` que comparten el MISMO conjunto de
    ``keys`` (conjunto, no secuencia -- el orden no importa) en la MISMA
    pareja de zonas que ``candidate`` -- la pareja tambien se compara
    como CONJUNTO (``_zone_pair``): ``zone1``/``zone2`` intercambiados
    cuentan como la misma pareja [BREAK 2 de Moriarty].

    Puerta DISTINTA de ``find_similar``: un titular lo bastante distinto
    diluye el Jaccard por debajo del umbral aunque las dos notas traten
    exactamente el mismo asunto -- las keys ya lo dicen sin depender del
    vocabulario del titular/descripcion.

    El conjunto VACIO nunca cuenta como coincidencia: es ausencia de
    dato, no un valor que comparar (mismo principio que ``_jaccard``
    aplica al vocabulario vacio). Sin este guarda, dos notas cualquiera
    sin ``--keys`` en la misma zona -- el caso mas comun -- chocarian
    siempre.

    Recibe las keys YA NORMALIZADAS (``validator.normalize_keys`` corre
    antes de construir cualquier ``Note``, tanto la candidata como las ya
    guardadas) -- esta funcion no normaliza nada por su cuenta.
    """
    candidate_keys = frozenset(candidate.keys)
    if not candidate_keys:
        return ()

    candidate_zones = _zone_pair(candidate)
    matches = []
    for note in existing:
        if _zone_pair(note) != candidate_zones:
            continue
        if frozenset(note.keys) == candidate_keys:
            matches.append(note)
    return tuple(matches)


def find_overlapping(
    candidate: Note,
    existing: tuple[Note, ...],
    threshold: float,
) -> tuple[Note, ...]:
    """Union de las dos puertas de duplicado que usa
    ``validator.validate_replacement``: parecido lexico (``find_similar``)
    y coincidencia EXACTA del conjunto de keys (``_find_exact_key_match``).

    Dedup por ``id`` si una misma nota cae por las dos puertas a la vez,
    preservando el orden en que aparece primero (parecido antes que
    coincidencia exacta).
    """
    seen: set[str] = set()
    matches: list[Note] = []
    for note in (
        *find_similar(candidate, existing, threshold),
        *_find_exact_key_match(candidate, existing),
    ):
        if note.id not in seen:
            seen.add(note.id)
            matches.append(note)
    return tuple(matches)
