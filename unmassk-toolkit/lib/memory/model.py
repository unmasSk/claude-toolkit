"""Frozen data shapes of the memory system; data only, no methods.

Imports no other module of the system, so every module can import it without a cycle.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Note:
    type: str                      # one of: D M R Q X I B
    id: str                        # "D-030"
    zone1: str
    zone2: str
    headline: str                  # English, <=80 characters
    description: str               # required in every type
    timestamp: datetime            # UTC, commit author date
    why: str | None = None         # required in D
    keys: tuple[str, ...] = ()     # up to 5
    origin: tuple[str, ...] = ()   # pointers to the notes it comes from
    replaces: str | None = None
    awaits: str | None = None      # B only
    issue: int | None = None       # optional; the issue of the work the note claims
    quote: str | None = None       # Q/I only; the owner's literal "no" when --issue none
    searched: str | None = None    # what was searched and found before saving (--searched)


@dataclass(frozen=True)
class ContextNote:                 # the session-close [NEXT]
    headline: str
    context: str                   # running prose summary, not a bullet list
    keys: tuple[str, ...]
    timestamp: datetime


@dataclass(frozen=True)
class Zone:                        # one entry of zones.json
    name: str
    description: str               # the line the unknown-zone rejection prints
    aliases: tuple[str, ...]
    # the note count is not a field: the printer computes it from the index


@dataclass(frozen=True)
class IndexLine:                   # one line of the live indexes
    id: str
    zone1: str
    zone2: str
    headline: str
    # no date and no emoji, on purpose


@dataclass(frozen=True)
class ArchiveLine:                 # one line of ARCHIVED.md
    date: date
    type: str
    id: str
    zone1: str
    zone2: str
    headline: str
    destination: str               # "replaced" | "closed" | "promoted"
    destination_detail: str        # the new ID, or the closing reason


@dataclass(frozen=True)
class Rejection:                   # what the gate produces when it refuses
    title: str                     # "la zona <<facturacion>> no existe"
    body: str
    relaunch: tuple[str, ...]      # the exact commands, kept apart from the body


@dataclass(frozen=True)
class Cluster:                     # a decision with what hangs from it
    root: Note
    children: tuple[Note, ...]     # by Origin/Replaces pointers, never by similarity
    archived_ids: frozenset[str]   # which children are already archived


@dataclass(frozen=True)
class NoteReport:                 # the report of one note by its id
    note: Note
    generated_at: datetime
    archived: bool                 # live/archived, shown in the header
    cluster: Cluster | None        # what hangs from it; None if nothing


@dataclass(frozen=True)
class ZoneReport:
    zone: Zone
    generated_at: datetime
    live_count: int
    archived_count: int
    restrictions: tuple[Note, ...]
    blockers: tuple[Note, ...]
    decisions: tuple[Cluster, ...]
    memos: tuple[Note, ...]
    incidents: tuple[Note, ...]
    questions: tuple[Note, ...]
    # Which notes above are archived now; by note, not id, since a repeated id may have a live twin.
    archived_notes: frozenset[Note] = frozenset()


@dataclass(frozen=True)
class WordChunk:                   # one zone pair of a word search
    zone1: str
    zone2: str
    notes: tuple[Note, ...]
    matched_ids: frozenset[str]    # which ones carry the › marker
    # same as `ZoneReport.archived_notes`, per chunk
    archived_notes: frozenset[Note] = frozenset()


@dataclass(frozen=True)
class WordReport:
    word: str
    generated_at: datetime
    zone_count: int
    live_count: int
    chunks: tuple[WordChunk, ...]
    # Not a ZoneReport: its counts are matched notes, not the zone's notes.


@dataclass(frozen=True)
class ChainThread:                 # a chain head with its predecessors
    head: Note                     # live, or archived without successor (closed=True)
    closed: bool                   # True = legitimately closed without successor
    ancestors: tuple[Note, ...]    # predecessors via Replaces, most recent first
    replaced_by: str | None = None  # id of the real successor, if closed is False
    # set when the successor lives outside this view (another zone pair); never with closed=True


@dataclass(frozen=True)
class ChainReport:                 # the chain view, `search.py --chain`
    query: str                     # zone or word as requested
    generated_at: datetime
    threads: tuple[ChainThread, ...]


@dataclass(frozen=True)
class WriteResult:                 # what every write returns
    ok: bool
    note_id: str | None            # the assigned id, if any
    rejections: tuple[Rejection, ...]   # empty on success
    git_error: str | None          # git's real, full message on failure


@dataclass(frozen=True)
class HealthReport:
    duplicate_ids: tuple[str, ...]
    index_lines: int               # the two numbers of "índices coherentes
    git_notes: int                 #   con git (68 líneas / 68 notas)"
    index_discrepancies: tuple[str, ...]   # which note diverges, not just how many
    plans_unreflected: tuple[tuple[int, int], ...]   # (issue, unreflected commits)
    # real reason when the gh query failed (issue_states is then empty); None otherwise
    plans_unreflected_error: str | None = None
    rule_head_lines: int = 0       # rule lines committed in HEAD
    rule_file_lines: int = 0       # rule lines in the working-tree file
    rule_discrepancies: tuple[str, ...] = ()   # which line diverges, not just how many
    # real reason when a broken git prevented coherence_rules(); None otherwise
    rule_discrepancies_error: str | None = None
    # how many of `git_notes` are archived (explains notes > index lines)
    archived_notes: int = 0
    # commit count when "many commits, zero recognised notes" fires; None otherwise
    legacy_commits_suspected: int | None = None
    # what is missing to save the first note here; empty when memory is mounted
    memory_setup_missing: tuple[str, ...] = ()
    # (sha, note) of each live copy of an id in `duplicate_ids`
    duplicate_notes: tuple[tuple[str, Note], ...] = ()
    # (number, state, title) of each cited issue, from the same gh query
    issue_states: tuple[tuple[int, str, str], ...] = ()
    # cited issues that query did not return (deleted, transferred, PR)
    issues_unanswered: tuple[int, ...] = ()
    # install files left uncommitted on a protected branch
    install_uncommitted: tuple[str, ...] = ()


@dataclass(frozen=True)
class BootSummary:
    project: str
    generated_at: datetime
    # Where the work was left and where you are, after fetching; None if git could not be asked.
    remote: object | None
    context: ContextNote | None    # None on the first day: the boot says so
    blockers: tuple[Note, ...]
    restrictions: tuple[Note, ...]     # all of them, no cap
    open_questions: int
    open_issues: int
    open_incidents: int
    # The live questions and incidents themselves, not just counted.
    questions: tuple[Note, ...]
    incidents: tuple[Note, ...]
    health: HealthReport
    # Live work notes (not X) with `issue` set, of issues still open on GitHub.
    issues: tuple[Note, ...] = ()
