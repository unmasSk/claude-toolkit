"""Agrupar una decision con lo que cuelga de ella -- contrato en
docs/memoria-v2/PIEZAS.md Sec.9.1.

De que salida se deriva: del racimo del informe de zona [TEXTOS.md
Sec.2.1] --

    D-030  login with JWT + Google OAuth                    2026-04-11
      |- X-012  server-side sessions          descartada . Origin D-030
      |- D-041  session lifetime raised        vigente   . Origin D-030
      `- D-036  logout only clears the cookie  archivada . replaced by D-052

La regla, y es innegociable [spec Sec.8]: se agrupa por PUNTEROS
(``Origin``, ``Replaces``), nunca por parecido ni por keys. Un racimo
armado por similitud cambia segun el algoritmo y no se puede auditar;
uno armado por punteros es el mismo siempre y falla en alto: si un
puntero apunta a algo que no esta en el conjunto recibido, la nota
queda huerfana -- un racimo de una -- y esa es la senal, no un fallo
[plan Sec.4.1]. Por eso un puntero cuyo destino no esta en ``notes`` se
ignora sin mas: no cuenta como arista, no lanza excepcion.

Los dos punteros no apuntan en el mismo sentido semantico, y el
agrupado tiene que tratarlos distinto para que el titulo salga bien:

- ``Origin``: el hijo apunta al ancestro (``child.origin`` contiene el
  id del padre). El ancestro -- el que no apunta a nadie mas dentro del
  racimo -- es la raiz de esa cadena.
- ``Replaces``: quien lleva el campo es la nota NUEVA, y apunta a la
  VIEJA que sustituye. Aqui la fuente del puntero es la raiz, y el
  destino pasa a colgar como hijo -- justo al reves que Origin.

"El titulo del racimo es la nota viva mas reciente" [spec Sec.8]: si
una decision sustituye a otra, manda la nueva. Una nota que es blanco
de un ``Replaces`` ajeno queda descartada como raiz (esta superada); una
nota que apunta a un ancestro via ``Origin`` tambien queda descartada
como raiz (no es el extremo alto de la cadena). Entre lo que sobra tras
esas dos exclusiones, el desempate es el id mas bajo -- deterministico,
no depende de en que orden llegaron las notas ni de la iteracion de un
set/dict [fila 4 de la tabla de tests, "mismo conjunto -> mismos
racimos, siempre"].

Que NO hace [PIEZAS.md Sec.9.1]: no lee nada -- recibe las notas ya
cargadas. No ordena para presentar -- eso es ``report_render``. No
decide que esta archivado -- se lo dan en ``archived_ids``.

Quien la llama: ``report.build``.
"""

from model import Cluster, Note


def group(notes: tuple[Note, ...], archived_ids: frozenset[str]) -> tuple[Cluster, ...]:
    """Agrupa ``notes`` en racimos por punteros Origin/Replaces.

    Cada racimo enlaza, transitivamente, todas las notas conectadas
    entre si por ``origin`` o ``replaces`` (union-find sobre los ids
    presentes en ``notes``). Una nota sin ningun puntero, o cuyos
    punteros apuntan fuera del conjunto recibido, queda sola en su
    propio racimo de una -- sin excepcion, sin aviso [fila 2 de la
    tabla de tests].

    La salida esta ordenada por ``root.id``, y ``children`` dentro de
    cada racimo tambien por id: ningun orden depende de en que
    secuencia llegaron las notas de entrada [fila 4].
    """
    by_id = {note.id: note for note in notes}

    parent = {note_id: note_id for note_id in by_id}

    def find(note_id: str) -> str:
        while parent[note_id] != note_id:
            parent[note_id] = parent[parent[note_id]]
            note_id = parent[note_id]
        return note_id

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    # ids que apuntan a un ancestro (Origin) presente en el conjunto --
    # nunca pueden ser raiz de su cadena.
    points_to_ancestor: set[str] = set()
    # id viejo -> quien(es) lo sustituyen via Replaces, dentro del conjunto.
    superseded_by: dict[str, set[str]] = {}

    for note in notes:
        ancestors = {origin_id for origin_id in note.origin if origin_id in by_id}
        if ancestors:
            points_to_ancestor.add(note.id)
            for ancestor_id in ancestors:
                union(note.id, ancestor_id)
        if note.replaces is not None and note.replaces in by_id:
            superseded_by.setdefault(note.replaces, set()).add(note.id)
            union(note.id, note.replaces)

    components: dict[str, list[str]] = {}
    for note_id in by_id:
        components.setdefault(find(note_id), []).append(note_id)

    result = []
    for member_ids in components.values():
        superseded_ids = {mid for mid in member_ids if mid in superseded_by}
        candidates = [
            mid
            for mid in member_ids
            if mid not in superseded_ids and mid not in points_to_ancestor
        ]
        if not candidates:
            # Red de seguridad para datos mal formados (p.ej. un ciclo de
            # Replaces) -- no hay adversario externo que lo provoque a
            # proposito, pero el sistema no debe reventar contra si mismo
            # [CLAUDE.md "el sistema contra si mismo"]. El desempate por
            # id mas bajo sigue siendo deterministico.
            candidates = member_ids

        root_id = min(candidates)
        child_ids = sorted(mid for mid in member_ids if mid != root_id)
        children = tuple(by_id[cid] for cid in child_ids)
        cluster_archived = frozenset(cid for cid in child_ids if cid in archived_ids)

        result.append(
            Cluster(root=by_id[root_id], children=children, archived_ids=cluster_archived)
        )

    result.sort(key=lambda cluster: cluster.root.id)
    return tuple(result)
