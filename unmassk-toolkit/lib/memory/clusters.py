"""Group notes into clusters by their Origin/Replaces pointers, never by similarity.

The root is the newest live note: not replaced by another and not pointing to an ancestor; ties go to the lowest id."""

from model import Cluster, Note


def group(notes: tuple[Note, ...], archived_ids: frozenset[str]) -> tuple[Cluster, ...]:
    """Return clusters sorted by root id, children by id; pointers outside ``notes`` are ignored."""
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

    # Ids pointing to an in-set Origin ancestor: never a root.
    points_to_ancestor: set[str] = set()
    # Old id -> the in-set ids that replace it.
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
            # Malformed data (e.g. a Replaces cycle): fall back to the lowest id.
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
