"""La unica implementacion de <<esto es valido>> en todo el sistema --
contrato en docs/memoria-v2/PIEZAS.md Sec.7.5.

De que salida se deriva: de las nueve validaciones de la aduana
[spec-sistema-memoria-v2.md Sec.6] y de los diez rechazos que las
expresan [TEXTOS.md Sec.1]. De esas nueve, la 9 (el error de git se
propaga entero) NO entra aqui: exige llamar a git, y este modulo NI
ABRE FICHEROS NI LLAMA A GIT -- vive en la pieza que si hace esa
llamada (``notes.py``, capa 3). Las siete originales si tienen su
funcion aqui, una por rechazo [TEXTOS.md Sec.1.1 a 1.7 y 1.11].

**La 8 (la issue del acta existe de verdad en GitHub) SI entra aqui
desde el 2026-08-02** `[decision del propietario, PIEZAS.md Sec.10.1,
punto 1]`: aunque exige llamar a algo externo (``gh``), el script que
la dispara (``bin/memory/note.py``) "no valida nada" -- toda decision
de <<esto es valido>> tiene que salir de esta pieza, la unica
implementacion del contrato. ``validate_issue`` es, por tanto, la
UNICA funcion de este modulo que rompe la pureza de las demas (llama a
``subprocess``) -- ver su propio docstring para el porque y el trato
que aplica (mismo patron que ``health.plans_unreflected`` ya fija para
``gh``: *no se puede comprobar* nunca es *esta bien*).

LA PROPIEDAD QUE NO SE ROMPE PARA LAS OTRAS NUEVE FUNCIONES: SON PURAS.
Todo lo que necesitan saber del mundo lo reciben en ``Context``, que
trae quien las llama. Por eso se prueban enteras sin que exista un
solo commit, y por eso el generador y la aduana obtienen la misma
respuesta ante los mismos datos -- octava regla del contrato: mismos
datos, mismo veredicto, siempre.

QUE NO HACE, y es la mitad del contrato. No escribe nada: no repara,
no da de alta zonas, no normaliza en disco -- ``normalize_keys``
devuelve la forma buena, quien la guarda es el generador. Por eso la
key mal escrita no es un rechazo [TEXTOS.md Sec.1.8]: un hook no puede
escribir. No busca por su cuenta: ``zones`` y ``similar`` los llama
este modulo por dentro (para que no exista una segunda puerta), pero
los datos que consultan ya vienen cargados en ``Context``.

QUIEN LO LLAMA. ``notes.py`` (y a traves suyo los cuatro scripts que
escriben) y ``hooks/customs.py`` para las nueve funciones puras.
``validate_issue`` la llama, ademas, directamente ``bin/memory/note.py``
-- no a traves de ``notes.py``, porque ninguna de las cinco operaciones
de esa pieza conoce el flag ``--issue`` como pregunta previa (mismo
trato que ``validate_pain_question``/``validate_distillation``, que
tampoco pasan por ``validate_note``).

ASUNCIONES DE FIRMA, DISCLOSED (PIEZAS.md Sec.7.5 solo fija la firma
completa de ``Context`` y de ``validate_note``; las diez funciones
internas se citan con ``(...)``):

- ``validate_pain_question(note, stops)`` y ``validate_distillation(note,
  is_distillation)`` reciben datos (la respuesta a la pregunta del
  dolor, si la nota es una destilacion) que NO son campos de ``Note``
  ni de ``Context`` -- por eso ``validate_note`` NO las llama: solo
  puede invocarse antes de que exista la ``Note`` definitiva, con la
  respuesta como dato aparte que trae quien arma esa nota todavia sin
  terminar (mismo principio de pureza que hace a ``Context`` externo,
  ver test_validator.py, fila 2/3). Quien las llama con esos datos es
  ``notes.py``/los scripts de capa 5, no ``validate_note``.

- ``validate_note`` agrega las funciones que se derivan por completo de
  ``note`` + ``ctx``: ``_validate_type``, ``validate_zones``,
  ``validate_headline``, ``validate_fields``, ``validate_pointers`` y
  ``validate_replacement``. ``normalize_keys`` no entra: no produce un
  ``Rejection``, es un aviso al guardar. ``is_wip`` tampoco: opera
  sobre el titular de un commit que nunca llega a ser ``Note``.

- ``validate_replacement`` usa un umbral de similitud fijo,
  ``vocabulary.SIMILARITY_THRESHOLD`` (0.5) -- el mismo "deliberadamente
  generoso" que fija ``test_similar.py`` para separar "obviamente igual"
  de "obviamente distinto" [PIEZAS.md Sec.6.5: "el umbral lo fija quien
  llama, no ese modulo"]. Vive en ``vocabulary.py`` (dato cerrado, Sec.6.1)
  porque ``rules.py`` necesita el mismo valor para el mismo tipo de
  mecanismo -- una sola copia, dos lectores [revision 2026-08-02, hallazgo
  de Argus]. ``Config`` no declara un campo de umbral (solo
  ``customs_enabled``, ``repo_type``, ``test_command`` -- PIEZAS.md
  Sec.6.3), asi que no hay otro sitio del que sacarlo.

- ``validate_pointers`` (partida a ``validator_pointers.py``, ver mas
  abajo) distingue un identificador de nota real de un hash de commit
  v1 citado en ``origin`` para una destilacion, y desde el 2026-08-02
  recibe tambien ``existing_in_zone`` para el banco adversarial
  [PIEZAS.md Sec.14 fila 2] -- ver el docstring de ese fichero para el
  detalle completo.

- ``normalize_keys(keys, headline)`` recibe el titular porque la propia
  fila de la Superficie lo exige ("ninguna ya en el titular")  y ese
  dato no vive en ninguna otra parte de la firma.

No importa nada fuera de la biblioteca estandar de Python y de sus
hermanos de ``lib/memory/`` [PIEZAS.md Sec.13], importados PLANOS
[PIEZAS.md Sec.3.3bis].

LA LEGALIDAD DEL NOMBRE DE ZONA VIVE EN ``validator_zones.py``, LA
COMPROBACION DE LA ISSUE EN ``validator_issue.py`` Y LA DE LOS PUNTEROS
EN ``validator_pointers.py`` -- las tres partidas de aqui por tamano
[DEUDA.md punto 14; la tercera, 2026-08-02, mismo techo, con el banco
adversarial de PIEZAS.md Sec.14]. Sigue siendo una sola implementacion:
este modulo importa ``validate_zones``/``validate_issue``/
``validate_pointers`` de alli de forma PLANA y las reexpone bajo el
mismo nombre, asi que ``validator.validate_zones``/
``validator.validate_issue``/``validator.validate_pointers`` no cambian
para nadie que los llame. Ver el docstring de cada fichero para el
porque de su corte.

``validate_issue_gate`` **anadida el 2026-08-26** [D-065/D-066, la
aduana de issues de Q/I] -- vive en ``validator_issue.py`` junto a
``validate_issue`` (mismo asunto: la pregunta previa al guardado sobre
si una Q/I necesita issue), reexportada aqui de la misma forma plana.
Recibe ``issue``/``work`` sin resolver (no campos de ``Note``, mismo
trato que ``stops``/``is_distillation`` -- ver "ASUNCIONES DE FIRMA"
arriba) porque solo ``bin/memory/note.py`` conoce la diferencia entre
"ausente" y el centinela literal ``"none"``. No entra en
``validate_note`` por la misma razon que ``validate_pain_question`` no
entra: solo puede invocarse antes de que la ``Note`` este terminada.
"""

import re
from dataclasses import dataclass

from config import Config
import emojis
from model import Note, Rejection, Zone
import rejection as rejection_
import similar
from validator_issue import validate_issue, validate_issue_gate
from validator_pointers import carry_answer_flags, validate_pointers
from validator_zones import validate_zones

from vocabulary import (
    HEADLINE_MAX,
    MARKER_KEYS,
    MAX_KEYS,
    PAIN_QUESTION,
    SIMILARITY_THRESHOLD,
    TYPES,
)

# Los dos valores literales del flag CLI [TEXTOS.md Sec.1.5].
_STOPS_YES = "yes"

_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Una sola fuente del glifo -- desde 2026-08-03 `bin/memory/wip.py` es su
# productor real [emojis.py, docstring de CHANNEL_EMOJI]; nunca un
# segundo literal "🚧" suelto que pueda desincronizarse de ese.
_WIP_MARKER = emojis.CHANNEL_EMOJI["wip"]
_WIP_PREFIX = "[WIP]"


@dataclass(frozen=True)
class Context:
    """Todo lo que el validador necesita saber del mundo.

    Lo trae quien lo llama: el validador NI abre ficheros NI llama a
    git [PIEZAS.md Sec.7.5, "Superficie"].
    """

    zones: dict[str, Zone]
    existing_in_zone: tuple[Note, ...]
    known_ids: frozenset[str]
    config: Config


def validate_note(note: Note, ctx: Context) -> tuple[Rejection, ...]:
    """Todas las reglas derivables de ``note`` + ``ctx``. Vacio = valida.

    No incluye ``validate_pain_question`` ni ``validate_distillation``:
    las dos necesitan un dato (la respuesta al dolor, si es una
    destilacion) que no es campo de ``Note`` ni de ``Context`` -- ver
    "ASUNCIONES DE FIRMA" en el docstring del modulo. Tampoco incluye
    ``normalize_keys`` (no produce ``Rejection``) ni ``is_wip`` (opera
    sobre un titular de commit que nunca llega a ser ``Note``).
    """
    checks = (
        _validate_type(note),
        validate_zones(note, ctx.zones),
        validate_headline(note.headline),
        validate_fields(note),
        validate_pointers(note, ctx.known_ids, ctx.existing_in_zone),
        validate_replacement(note, ctx.existing_in_zone),
    )
    return tuple(r for r in checks if r is not None)


def validate_headline(headline: str) -> Rejection | None:
    """Fila 1 [TEXTOS.md Sec.1.11]. Longitud contra ``HEADLINE_MAX``."""
    length = len(headline)
    if length <= HEADLINE_MAX:
        return None

    what = f"el titular tiene {length} caracteres y el tope son {HEADLINE_MAX}"
    options = (
        f'  "{headline}"',
        "",
        "El titular es lo unico que se ve en el indice y en el arranque: si no se",
        "lee de un vistazo, deja de cumplir su funcion. No se corta solo, porque",
        "cortarlo borraria justo la parte que suele importar.",
        "",
        "Dos salidas:",
        "",
        "  acortalo          quedate con la prohibicion; el detalle va a Description",
        "  parte en dos      si dice dos cosas, son dos notas",
    )
    command = (
        "gitmem note <TIPO> --zones <zona1> <zona2> "
        f'"<titular de hasta {HEADLINE_MAX} caracteres>" --description "..."',
    )
    return rejection_.build(
        kind="headline_too_long", what=what, options=options, command=command
    )


# Interna desde 2026-08-04 [detector de codigo muerto: 0 llamadores fuera
# de este fichero, 0 tests propios]. No esta muerta: la unica puerta real
# del validador desde fuera es `validate_note` (~linea 152), y esta es una
# de las seis funciones que agrega. NO se generaliza a las otras siete
# `validate_*` de este modulo -- no estan todas en el mismo caso:
# `validate_pain_question`, `validate_issue` y `normalize_keys` SI tienen
# llamador externo (`bin/memory/note.py`/`bin/memory/remove.py`); y
# `validate_headline`, `validate_fields`, `validate_replacement` y
# `validate_distillation`, aunque tampoco tengan llamador externo, SI
# tienen test propio -- se dejan como estan.
def _validate_type(note: Note) -> Rejection | None:
    """El arbol de tipos [TEXTOS.md Sec.1.4]. Si no encaja, pregunta que es."""
    if note.type in TYPES:
        return None

    what = "no se que tipo es esto"
    options = [
        f'"{note.headline}" no encaja limpiamente en ningun tipo.',
        "",
    ]
    for letter, spec in TYPES.items():
        options.append(f"  {letter}  {spec.description}")
    options.append("")
    options.append(
        "Partela en dos, o elige uno, y relanza. Que no encaje es informacion:"
    )
    options.append(
        "si de verdad no es ninguno de los siete, dilo en el chat antes de forzarlo."
    )
    command = (
        f'gitmem note <TIPO> --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..."',
    )
    return rejection_.build(
        kind="type_not_recognized",
        what=what,
        options=tuple(options),
        command=command,
    )


def validate_fields(note: Note) -> Rejection | None:
    """Fila 5 [TEXTOS.md Sec.1, via vocabulary.TYPES]. Obligatorios y no permitidos."""
    type_spec = TYPES.get(note.type)
    if type_spec is None:
        return None  # tipo desconocido -- responsabilidad de _validate_type

    present = _present_fields(note)
    missing_required = sorted(type_spec.required_fields - present)
    not_allowed = sorted(present - type_spec.allowed_fields)

    if not missing_required and not not_allowed:
        return None

    lines = []
    if missing_required:
        lines.append(
            f"Faltan campos obligatorios para el tipo {note.type}: "
            f"{', '.join(missing_required)}"
        )
    if not_allowed:
        lines.append(
            f"Estos campos no existen para el tipo {note.type}: "
            f"{', '.join(not_allowed)}"
        )
    what = f"el campo no encaja con el tipo {note.type}"
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..."',
    )
    return rejection_.build(
        kind="field_not_allowed", what=what, options=tuple(lines), command=command
    )


def _present_fields(note: Note) -> frozenset[str]:
    """Que campos opcionales trae `note` de verdad. Texto libre en blanco
    (`""`/`"   "`) no cuenta como presente -- CONTENIDO tras `strip()`,
    no existencia, para `description`/`why`/`awaits`."""
    present = {"description"} if note.description and note.description.strip() else set()
    if note.why is not None and note.why.strip():
        present.add("why")
    if note.keys:
        present.add("keys")
    if note.origin:
        present.add("origin")
    if note.replaces is not None:
        present.add("replaces")
    if note.awaits is not None and note.awaits.strip():
        present.add("awaits")
    if note.issue is not None:
        present.add("issue")
    if note.quote is not None and note.quote.strip():
        present.add("quote")
    return frozenset(present)


def normalize_keys(keys: tuple[str, ...], headline: str) -> tuple[str, ...]:
    """Vocabulario controlado, tope de cinco, ninguna ya en el titular.

    No escribe nada [PIEZAS.md Sec.7.5, "Que NO hace"]: devuelve la
    forma buena, quien la guarda en disco es el generador. Por eso una
    key marcadora mal escrita nunca es un rechazo -- es un aviso al
    guardar [TEXTOS.md Sec.1.8].
    """
    headline_words = frozenset(_WORD_RE.findall(headline.lower()))
    normalized: list[str] = []
    seen: set[str] = set()
    for key in keys:
        canonical = MARKER_KEYS.get(key.lower(), key.lower())
        if canonical in seen or canonical in headline_words:
            continue
        seen.add(canonical)
        normalized.append(canonical)
        if len(normalized) >= MAX_KEYS:
            break
    return tuple(normalized)


def validate_pain_question(note: Note, stops: str | None) -> Rejection | None:
    """Filas 2 y 3 [TEXTOS.md Sec.1.5]. Solo aplica a M y R.

    `stops` no es un campo de `Note` -- solo puede llegar de quien
    arma la nota todavia sin terminar, ver "ASUNCIONES DE FIRMA" en el
    docstring del modulo.
    """
    if note.type not in ("M", "R"):
        return None

    if stops is None:
        what = "falta una respuesta"
        options = (
            "Toda M y toda R contestan lo mismo antes de entrar:",
            "",
            f"  {PAIN_QUESTION}",
            "",
            "  si  ->  es un muro. Entra como R y sale en TODOS los arranques.",
            "  no  ->  es un hecho. Entra como M y se lee cuando se busca su zona.",
        )
        command = (  # 2026-08-05: arrastra origin/replaces/awaits ya dados (carry_answer_flags)
            f'gitmem note M --zones {note.zone1} {note.zone2} '
            f'"{note.headline}" --description "..."{carry_answer_flags(note, skip=frozenset({"--stops"}))} --stops no',
            f'gitmem note R --zones {note.zone1} {note.zone2} '
            f'"{note.headline}" --description "..."{carry_answer_flags(note, skip=frozenset({"--stops"}))} --stops yes',
        )
        return rejection_.build(
            kind="missing_pain_answer", what=what, options=options, command=command
        )

    expected_type = "R" if stops == _STOPS_YES else "M"
    if note.type == expected_type:
        return None

    answer_word = "si" if expected_type == "R" else "no"
    kind_word = "muro" if expected_type == "R" else "hecho"
    what = (
        f'contestaste "{answer_word}" a "{PAIN_QUESTION}" -- entonces es un '
        f"{kind_word}, entra como {expected_type}, no {note.type}"
    )
    options = (
        f"{PAIN_QUESTION} -> {answer_word}",
        f"eso corresponde al tipo {expected_type}, no {note.type}.",
    )
    command = (  # 2026-08-05: arrastra origin/replaces/awaits ya dados
        f'gitmem note {expected_type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..."{carry_answer_flags(note, skip=frozenset({"--stops"}))} --stops {stops}',
    )
    return rejection_.build(
        kind="pain_answer_wrong_type", what=what, options=options, command=command
    )


def validate_replacement(
    note: Note, existing_in_zone: tuple[Note, ...]
) -> Rejection | None:
    """Fila 4 [TEXTOS.md Sec.1.6]. Parecida sin `--replaces` rebota con las
    candidatas completas dentro.
    """
    if note.replaces is not None:
        return None

    candidates = similar.find_overlapping(
        note, existing_in_zone, threshold=SIMILARITY_THRESHOLD
    )
    if not candidates:
        return None

    what = f"esto pisa a algo que ya esta escrito en [{note.zone1}][{note.zone2}]"
    options = [
        f"Tu nota comparte terreno con estas de [{note.zone1}][{note.zone2}]. "
        "Di que pasa con ellas antes de entrar:",
        "",
    ]
    for candidate in candidates:
        options.append(
            f"  {candidate.id}   {candidate.timestamp.date().isoformat()}   "
            f"{candidate.headline}"
        )
        if candidate.keys:
            options.append(f"          keys: {', '.join(candidate.keys)}")
        if candidate.why:
            options.append(f"          Why: {candidate.why}")
        options.append("")
    options.extend(
        [
            "Tres salidas, y solo tres:",
            "",
            "  la sustituye   --replaces <id>       la vieja sale del indice a ARCHIVED",
            "  conviven       --replaces none       las dos siguen vigentes",
            "  es duplicado   no la guardes; si hay que matizar, cierra la vieja:",
            '                 gitmem remove <id> "..." --restriction no',
            # Corregido 2026-08-04: la linea de arriba decia
            # 'gitmem close <id> "..."' -- `close` no existe (se renombro a
            # `remove`, DEUDA.md B4) y ademas `remove.py` exige
            # `--restriction no|new` (bin/memory/remove.py:53, required=True),
            # asi que ni renombrando el subcomando bastaba. Cerrar una nota
            # por ser duplicado no hace nacer ningun muro, asi que la
            # disyuntiva `no|new` resuelve a `no`.
        ]
    )
    first_id = candidates[0].id
    command = (  # 2026-08-05: arrastra stops/origin/awaits ya dados
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}"{carry_answer_flags(note, skip=frozenset({"--replaces"}))} --why "..." --description "..." --replaces {first_id}',
    )
    return rejection_.build(
        kind="overlapping_note", what=what, options=tuple(options), command=command
    )


def validate_distillation(note: Note, is_distillation: bool) -> Rejection | None:
    """Fila 6 [TEXTOS.md Sec.1.7]. Toda destilacion exige fuentes.

    `is_distillation` no es un campo de `Note` -- lo sabe de antemano
    quien construye la nota (fase de instalacion unica, spec Sec.13),
    ver "ASUNCIONES DE FIRMA" en el docstring del modulo.
    """
    if not is_distillation or note.origin:
        return None

    what = "una destilacion sin fuentes no es una destilacion"
    options = (
        "Compactar es decir DE QUE. Sin Origin no hay forma de volver a lo que",
        "resumiste ni de comprobar si lo resumiste bien.",
        "",
        "Pon los hashes v1 de los que sale, separados por espacios.",
        # Corregido 2026-08-04: decia "separados por comas" -- falso,
        # note.py:86 usa --origin con nargs="+" (espacios); con comas
        # los tres hashes entraban como un unico origen, mal enlazado [TEXTOS.md Sec.1.7].
    )
    command = (
        f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..." --origin <hash1> <hash2> ...',
    )
    return rejection_.build(
        kind="distillation_without_sources",
        what=what,
        options=options,
        command=command,
    )


def validate_incident_close_question(note: Note, restriction: str | None) -> Rejection | None:
    """Fila 10 [TEXTOS.md Sec.1.10]. Solo aplica a incidencias (I-...).

    `restriction` no es un campo de `Note`, ver "ASUNCIONES DE FIRMA"
    arriba. Anadida 2026-08-04 [decision del propietario, P5]: cerrar
    una I sin decir si nace un muro no es el error crudo de argparse --
    el sistema pregunta, con sus dos comandos de relanzamiento dentro.
    """
    if note.type != "I" or restriction is not None:
        return None

    what = f"{note.id} no se cierra sin contestar esto"
    options = (
        "¿de esta cicatriz sale muro?",
        "",
        f"  {note.id}  [{note.zone1}][{note.zone2}]  {note.headline}",
        f"         causa: {note.description}",
        "",
        "  sí  →  nace una R en esta misma zona y sale en todos los arranques",
        "  no  →  se cierra sin más; nadie vuelve a enterarse",
    )
    command = (
        f'gitmem remove {note.id} "..." --restriction no',
        f'gitmem remove {note.id} "..." --restriction new '
        f'--restriction-text "..." --why "..."',
    )
    return rejection_.build(
        kind="incident_close_question", what=what, options=options, command=command
    )


def is_wip(subject: str) -> bool:
    """Fila 7. El commit exento de toda pregunta [TEXTOS.md, cabecera de emojis].

    Marcado con `[WIP]` literal y el emoji de wip DELANTE del titular
    [decision del propietario, 2026-08-05: el corchete se anade para que
    se lea igual que el `[NEXT]` del cierre]. Su productor es
    `bin/memory/wip.py`. Es solo el predicado: el punto donde hace que
    ninguna pregunta se dispare vive en `hooks/customs.py`.

    Se sigue reconociendo la forma anterior -- el emoji suelto, sin
    corchete -- porque ya hay checkpoints escritos asi y dejar de
    reconocerlos los sometería a preguntas que en su dia no tuvieron.
    """
    return subject.startswith((f"{_WIP_PREFIX} {_WIP_MARKER}", _WIP_MARKER))
