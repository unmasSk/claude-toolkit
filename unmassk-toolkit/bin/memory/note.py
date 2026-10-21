#!/usr/bin/env python3
"""Save a memory note (D/M/R/Q/X/I/B) and print the result.

    note.py <TYPE> --zones <zone1> <zone2> "<headline>" \\
        [--why "..."] [--description "..."] [--keys k1 k2 ...] \\
        [--stops yes|no] [--origin <id1> <id2> ...] \\
        [--replaces <ID>|none] [--awaits "..."] [--issue N|none] \\
        [--work no] [--quote "..."] \\
        [--discard "<alternative headline>" "<why>" ...] \\
        [--promotes <Q id>] --searched "<searched>: <found>"

`--stops`, `--issue` and `--work` are checked before writing; they are not `Note` fields.
"""

import argparse
import collections
import dataclasses
import os
import shlex
import sys
from datetime import datetime, timezone

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

force_utf8_streams()

import config  # noqa: E402
import indexes  # noqa: E402
import notes  # noqa: E402
import query  # noqa: E402
import rejection as rejection_  # noqa: E402
import validator  # noqa: E402
import zones as zones_lib  # noqa: E402
from emojis import TYPE_EMOJI  # noqa: E402
from model import Note  # noqa: E402
from validator_pointers import takes  # noqa: E402
from vocabulary import MARKER_KEYS  # noqa: E402


def _issue_arg(value):
    """`--issue`: an `int` or the literal `"none"`."""
    if value == "none":
        return value
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--issue: {value!r} no es ni un numero ni el centinela 'none'"
        )


def _replaces_arg(value):
    """`--replaces`: an id as typed, or the word `none` in any case, kept as lowercase `"none"`."""
    return "none" if value.lower() == "none" else value


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="note.py")
    parser.add_argument("type", help="D M R Q X I B")
    parser.add_argument("--zones", nargs=2, metavar=("ZONE1", "ZONE2"), required=True)
    parser.add_argument("headline")
    parser.add_argument("--why", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--keys", nargs="+", default=())
    parser.add_argument("--stops", choices=("yes", "no"), default=None)
    parser.add_argument("--origin", nargs="+", default=())
    parser.add_argument("--replaces", type=_replaces_arg, default=None)
    parser.add_argument("--awaits", default=None)
    parser.add_argument("--issue", type=_issue_arg, default=None)
    # Q/I issue gate: a "yes" is answered with `--issue`.
    parser.add_argument("--work", choices=("no",), default=None)
    parser.add_argument("--quote", default=None)
    parser.add_argument("--promotes", default=None)  # promotes a Q
    # Required, but enforced in `main()` so the user gets the question, not argparse usage.
    parser.add_argument("--searched", default=None)
    parser.add_argument(
        "--discard", action="append", nargs=2, metavar=("HEADLINE", "WHY"), default=None
    )
    return parser.parse_args(argv)


def _existing_in_zone_pair(zone1, zone2, archived):
    """Live notes of the zone pair in either order, deduplicated, excluding `archived`."""
    seen: set[str] = set()
    matches = []
    for note in (*query.by_zone(zone1, zone2), *query.by_zone(zone2, zone1)):
        if note.id in seen:
            continue
        seen.add(note.id)
        if note.id not in archived:
            matches.append(note)
    return tuple(matches)


def _build_context(pm, zone1, zone2):
    """Build the validator `Context` and resolve both zones to canonical names.

    Returns `(ctx, zone1, zone2)`. `known_ids` includes archived notes.
    """
    zones_map = zones_lib.load(pm / "zones.json")
    zone1 = zones_lib.resolve(zone1, zones_map) or zone1
    zone2 = zones_lib.resolve(zone2, zones_map) or zone2
    archived = indexes.archived_ids(pm)
    existing_in_zone = _existing_in_zone_pair(zone1, zone2, archived)
    known_ids = frozenset(n.id for n in query.by_zone(None, None))
    cfg = config.load(pm / "config.json")
    ctx = validator.Context(
        zones=zones_map,
        existing_in_zone=existing_in_zone,
        known_ids=known_ids,
        config=cfg,
    )
    return ctx, zone1, zone2


def _corrected_key_pairs(raw_keys, normalized_keys):
    """Return `(typed, canonical)` pairs for the marker keys that were corrected."""
    normalized_set = set(normalized_keys)
    pairs = []
    for raw in raw_keys:
        canonical = MARKER_KEYS.get(raw.lower(), raw.lower())
        if canonical != raw.lower() and canonical in normalized_set:
            pairs.append((raw, canonical))
    return pairs


def _build_candidate(args, normalized_keys, zone1, zone2):
    # "none" is stored as no issue; the gate gets the raw `args.issue`.
    issue = args.issue if isinstance(args.issue, int) else None
    return Note(
        type=args.type,
        id="",
        zone1=zone1,
        zone2=zone2,
        headline=args.headline,
        description=args.description or "",
        timestamp=datetime.now(timezone.utc),
        why=args.why,
        keys=normalized_keys,
        origin=tuple(args.origin),
        replaces=args.replaces,
        awaits=args.awaits,
        issue=issue,
        quote=args.quote,
        searched=args.searched,
    )


def _build_discard_candidates(discard_pairs, zone1, zone2, searched):
    """One `X` note per `--discard` (headline, why) pair, in the decision's zones."""
    return tuple(
        Note(
            type="X",
            id="",
            zone1=zone1,
            zone2=zone2,
            headline=headline,
            description=why,
            timestamp=datetime.now(timezone.utc),
            searched=searched,
        )
        for headline, why in discard_pairs
    )


def _print_success(result, args, normalized_keys):
    lines = [f"✅ {result.note_id} guardada"]
    corrected = _corrected_key_pairs(args.keys, normalized_keys)
    if corrected:
        plural = "s" if len(corrected) > 1 else ""
        lines[0] += f" — con {len(corrected)} key{plural} corregida{plural}"
        lines.append("")
        for raw, canonical in corrected:
            lines.append(f"  {raw}  →  {canonical}")
    print("\n".join(lines))


def _print_success_with_discards(decision_result, alternatives, discard_results, args, normalized_keys):
    """Print the corrected keys and the discards first, the decision's line last."""
    corrected = _corrected_key_pairs(args.keys, normalized_keys)
    suffixes = []
    lines = []
    if corrected:
        plural_k = "s" if len(corrected) > 1 else ""
        suffixes.append(f"con {len(corrected)} key{plural_k} corregida{plural_k}")
        for raw, canonical in corrected:
            lines.append(f"  {raw}  →  {canonical}")
        lines.append("")
    plural_x = "s" if len(discard_results) != 1 else ""
    suffixes.append(f"con {len(discard_results)} alternativa{plural_x} descartada{plural_x}")
    for alternative, result in zip(alternatives, discard_results):
        lines.append(f"  {TYPE_EMOJI['X']} {result.note_id}  {alternative.headline}")
    lines.append("")
    lines.append(f"✅ {decision_result.note_id} guardada — " + ", ".join(suffixes))
    print("\n".join(lines))


def _relaunch_words(command, headline):
    """Return the shell words of a relaunch command, with the quoted headline removed."""
    rest = command.replace(f'"{headline}"', "", 1)
    try:
        return set(shlex.split(rest))
    except ValueError:  # unbalanced quote outside the headline: fall back to plain words
        return set(rest.split())


def _carry_cli_flags(one_rejection, args):
    """Append `--promotes`, `--discard` and the issue-gate answers to `gitmem note` relaunches."""
    promotes = f" --promotes {shlex.quote(args.promotes)}" if args.promotes is not None else ""
    discards = "".join(f" --discard {shlex.join(pair)}" for pair in args.discard or ())
    work = f" --work {args.work}" if args.work is not None else ""
    issue = f" --issue {args.issue}" if args.issue is not None else ""
    quote = f" --quote {shlex.quote(args.quote)}" if args.quote is not None else ""

    def carried(command):
        if not command.startswith("gitmem note "):
            return command
        given = _relaunch_words(command, args.headline)
        if "--promotes" not in given:
            command += promotes
        if "--discard" not in given:
            command += discards
        # `--work`, `--issue none` and `--quote` only fit Q/I; `--issue` and `--work` exclude each other.
        words = command.split()
        gate_type = len(words) > 2 and takes(words[2], "quote")
        if "--issue" not in given and "--work" not in given:
            if issue and (gate_type or args.issue != "none"):
                command += issue
            elif gate_type:
                command += work
        if "--quote" not in given and gate_type:
            command += quote
        return command

    return dataclasses.replace(one_rejection, relaunch=tuple(map(carried, one_rejection.relaunch)))


def _print_rejection(one_rejection, args, *, carry_cli=True):
    """Print a rejection; its relaunches carry `--searched` and, if `carry_cli`, the CLI flags."""
    if carry_cli:
        one_rejection = _carry_cli_flags(one_rejection, args)
    carried = validator.carry_searched(one_rejection, args.searched, "gitmem note ")
    print(rejection_.render_terminal(carried))


def _without_discards(argv, dropped):
    """Return `argv` without the `--discard` pairs in `dropped`, once per count."""
    left = collections.Counter(dropped)
    out, i = [], 0
    while i < len(argv):
        token = argv[i]
        is_discard = len(token) >= 4 and "--discard".startswith(token)
        pair = tuple(argv[i + 1:i + 3])
        if is_discard and left[pair] > 0:
            left[pair] -= 1
            i += 3
            continue
        out.append(token)
        i += 1
    return out


def _print_refused_discards(rejections, alternatives, ctx, argv):
    """Print refused discards without relaunches, then one relaunch of the decision without them."""
    for one_rejection in rejections:
        print(rejection_.render_terminal(dataclasses.replace(one_rejection, relaunch=())))
        print()
    dropped = collections.Counter(
        (alt.headline, alt.description) for alt, _found in notes.refused_alternatives(alternatives, ctx)
    )
    listed = tuple(f"  --discard {shlex.join(pair)}" for pair in sorted(dropped.elements()))
    summary = rejection_.build(
        kind="discard_refused",
        what="no se ha guardado nada: ni la decision ni sus descartes",
        options=("Estas alternativas rebotan:", "", *listed, "",
                 "Guarda la decision sin ellas:"),
        command=(shlex.join(["gitmem", "note", *_without_discards(argv, dropped)]),),
    )
    print(rejection_.render_terminal(summary))


def _handle_discard(candidate, args, normalized_keys, ctx, zone1, zone2, argv):
    """Write a decision with `--discard` alternatives; nothing is written if any is refused."""
    alternatives = _build_discard_candidates(args.discard, zone1, zone2, args.searched)
    decision_called = []

    def write_decision(decision, c):
        decision_called.append(True)
        return _write_decision(decision, args, c)

    results = notes.discard_alternatives(candidate, alternatives, ctx, write_decision=write_decision)
    decision_result = results[0]

    if not decision_result.ok:
        if decision_result.rejections and not decision_called:
            _print_refused_discards(decision_result.rejections, alternatives, ctx, argv)
            return 1
        if decision_result.rejections:
            for one_rejection in decision_result.rejections:
                _print_rejection(one_rejection, args)
            return 1
        print(f"git fallo al guardar la nota: {decision_result.git_error}", file=sys.stderr)
        return 1

    discard_results = results[1:]
    failed = [result for result in discard_results if not result.ok]
    if failed:
        for result in failed:
            if result.rejections:
                for one_rejection in result.rejections:
                    _print_rejection(one_rejection, args, carry_cli=False)
            else:
                print(f"git fallo al guardar un descarte: {result.git_error}", file=sys.stderr)
        saved = [decision_result.note_id] + [r.note_id for r in discard_results if r.ok]
        print(
            f"⚠️ ya quedaron guardadas: {', '.join(saved)} -- no relances el comando "
            "entero, o la decision se escribe dos veces; guarda solo los descartes que faltan",
            file=sys.stderr,
        )
        return 1

    _print_success_with_discards(decision_result, alternatives, discard_results, args, normalized_keys)
    return 0


def _write_decision(candidate, args, ctx):
    """Write the note via `notes.promote()`, `notes.replace()` or `notes.write()`."""
    if args.promotes is not None:
        return notes.promote(candidate, args.promotes, ctx)
    if args.replaces is not None and args.replaces != "none":
        return notes.replace(candidate, args.replaces, ctx)
    return notes.write(candidate, ctx)


def _handle_write_or_replace(candidate, args, normalized_keys, ctx):
    """Write the note without `--discard` and print the result."""
    result = _write_decision(candidate, args, ctx)
    if not result.ok:
        if result.rejections:
            for one_rejection in result.rejections:
                _print_rejection(one_rejection, args)
            return 1
        print(f"git fallo al guardar la nota: {result.git_error}", file=sys.stderr)
        return 1

    _print_success(result, args, normalized_keys)
    return 0


def main(argv):
    args = _parse_args(argv)

    searched_rejection = validator.validate_searched(args.searched, ["gitmem", "note", *argv])
    if searched_rejection is not None:
        print(rejection_.render_terminal(searched_rejection))
        return 1

    root = notes.repo_root()
    pm = notes.pm_root(root)
    ctx, zone1, zone2 = _build_context(pm, args.zones[0], args.zones[1])

    normalized_keys = validator.normalize_keys(tuple(args.keys), args.headline)
    candidate = _build_candidate(args, normalized_keys, zone1, zone2)

    pain_rejection = validator.validate_pain_question(candidate, args.stops)
    if pain_rejection is not None:
        _print_rejection(pain_rejection, args)
        return 1

    # Raw `args.issue`: tells "absent" from an explicit "none".
    gate_rejection = validator.validate_issue_gate(candidate, args.issue, args.work)
    if gate_rejection is not None:
        _print_rejection(gate_rejection, args)
        return 1

    try:
        issue_rejection = validator.validate_issue(candidate, candidate.issue)
    except RuntimeError as exc:
        print(f"no se pudo comprobar la issue #{candidate.issue}: {exc}", file=sys.stderr)
        return 1
    if issue_rejection is not None:
        _print_rejection(issue_rejection, args)
        return 1

    if args.discard:
        return _handle_discard(candidate, args, normalized_keys, ctx, zone1, zone2, argv)

    return _handle_write_or_replace(candidate, args, normalized_keys, ctx)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"note.py: {exc}", file=sys.stderr)
        sys.exit(1)
