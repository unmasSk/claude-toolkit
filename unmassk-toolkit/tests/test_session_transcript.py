"""Contract tests for the close-session extractor (session_transcript.py): what
the owner typed comes out, and nothing else.

Plan docs/plan/fix-close-transcript.md, step 1.1. Driven through the script's
command line, on .jsonl fixtures built from real record shapes, against a
disposable git repo. Window: test_session_transcript_window.py; redo close:
test_session_transcript_redo.py.
"""

import json

import pytest

from session_transcript_harness import commit, make_repo, run
from session_transcript_records_helpers import (
    LINKED_SESSIONS, assistant, builtin_command, human, image_block, owner_mid_turn,
    owner_mid_turn_blocks, peer_message, skill_body, slash_command, subagent_handback,
    task_notification, text_block, ts, write_transcript,
)


@pytest.fixture
def closed_repo(tmp_path):
    """A repo whose last close happened before the transcript starts."""
    repo = make_repo(tmp_path)
    commit(repo, "[DECISION][x] 🧭 earlier work", "06:00:00")
    commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    return repo


# ── (a) owner messages typed mid-turn ───────────────────────────────────

OWNER_MID_TURN = "Recuerda cerrar la ventana del garaje antes de cenar."


def test_should_output_owner_message_when_typed_mid_turn(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")), assistant("Hola Bex.", ts("08:00:05"))]
    records += owner_mid_turn(OWNER_MID_TURN, ts("08:51:38"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert len(result.user_turns_with(OWNER_MID_TURN)) == 1, result.conversation


def test_should_output_mid_turn_message_once_when_queue_operations_repeat_it(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00"))] + owner_mid_turn(OWNER_MID_TURN, ts("08:51:38"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert result.conversation.count(OWNER_MID_TURN) == 1, result.conversation


def test_should_place_mid_turn_message_between_the_turns_around_it(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")),
               assistant("ANTES del mensaje", ts("08:51:00"))]
    records += owner_mid_turn(OWNER_MID_TURN, ts("08:51:38"))
    records += [assistant("DESPUES del mensaje", ts("08:52:00"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)
    conversation = result.conversation

    assert 0 <= conversation.find("ANTES del mensaje") < conversation.find(OWNER_MID_TURN) \
        < conversation.find("DESPUES del mensaje"), conversation


def test_should_bound_mid_turn_messages_by_since(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn("mensaje viejo a mitad de turno", ts("08:10:00"))
    records += owner_mid_turn("mensaje nuevo a mitad de turno", ts("08:40:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript, "--since", "2026-10-19T08:30:00")

    assert (result.anywhere_in_conversation("mensaje viejo a mitad de turno"),
            len(result.user_turns_with("mensaje nuevo a mitad de turno"))) == (False, 1)


@pytest.mark.parametrize("make_record", [peer_message, subagent_handback, task_notification],
                         ids=["peer-session", "subagent-handback", "task-notification"])
def test_should_drop_queued_command_when_origin_is_not_the_owner(tmp_path, closed_repo,
                                                                 make_record):
    records = [human("hola", ts("08:00:00")),
               make_record("TEXTO-QUE-NO-ES-DEL-DUENO", ts("08:20:00"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert not result.anywhere_in_conversation("TEXTO-QUE-NO-ES-DEL-DUENO"), result.conversation


def test_should_leave_out_an_inline_sidechain_record_of_the_top_level_transcript(tmp_path,
                                                                               closed_repo):
    inline = human("TEXTO-DE-UNA-CADENA-LATERAL", ts("08:10:00"))
    inline["isSidechain"] = True
    transcript = write_transcript(tmp_path / "s.jsonl", [human("hola", ts("08:00:00")), inline])

    result = run(tmp_path, closed_repo, transcript)

    assert (len(result.user_turns_with("hola")),
            result.anywhere_in_conversation("TEXTO-DE-UNA-CADENA-LATERAL")) == (1, False), \
        result.conversation


# ── (b) slash commands: what the owner typed, `/name args` ──────────────

CLOSE_ARGS = "y apunta que el martes toca pintar la valla"


def test_should_output_command_args_when_owner_types_a_slash_command(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")),
               slash_command("unmassk-toolkit:unmassk-close-session", CLOSE_ARGS, ts("08:50:47"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert len(result.user_turns_with(CLOSE_ARGS)) == 1, result.conversation


def test_should_drop_skill_body_when_it_follows_the_slash_command(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")),
               slash_command("unmassk-toolkit:unmassk-close-session", CLOSE_ARGS, ts("08:50:47")),
               skill_body("CUERPO-DE-LA-SKILL Base directory for this skill", ts("08:50:47"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert not result.anywhere_in_conversation("CUERPO-DE-LA-SKILL"), result.conversation


@pytest.mark.parametrize("name", ["clear", "reload-plugins"])
def test_should_output_the_name_of_a_builtin_command_the_owner_typed(tmp_path, closed_repo,
                                                                     name):
    transcript = write_transcript(tmp_path / "s.jsonl", [
        human("ANTES-DEL-COMANDO", ts("08:00:00")),
        builtin_command(name, "", ts("08:10:00")),
        human("DESPUES-DEL-COMANDO", ts("08:20:00"))])

    result = run(tmp_path, closed_repo, transcript)

    said = [turn.split("\n", 1)[1].strip() for turn in result.user_turns_with(f"/{name}")]

    assert (len(result.turns), said) == (3, [f"/{name}"]), result.conversation


def test_should_output_name_and_args_together_when_owner_types_a_skill_command(tmp_path,
                                                                               closed_repo):
    name = "unmassk-toolkit:unmassk-close-session"
    transcript = write_transcript(tmp_path / "s.jsonl", [
        human("hola", ts("08:00:00")), slash_command(name, CLOSE_ARGS, ts("08:50:47"))])

    result = run(tmp_path, closed_repo, transcript)
    said = [turn.split("\n", 1)[1].strip() for turn in result.user_turns_with(f"/{name}")]

    assert said == [f"/{name} {CLOSE_ARGS}"], result.conversation


# ── (f) a mid-turn owner message whose prompt is a list of blocks ───────

BLOCKS_OWNER = "Mañana hay que llevar el coche al taller."


def test_should_output_owner_text_when_list_prompt_leads_with_a_system_reminder(tmp_path,
                                                                               closed_repo):
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn_blocks([text_block(LINKED_SESSIONS), text_block(BLOCKS_OWNER)],
                                     ts("08:20:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert (result.conversation.count(BLOCKS_OWNER), len(result.user_turns_with(BLOCKS_OWNER)),
            result.anywhere_in_conversation("Linked sessions now")) == (1, 1, False), \
        result.conversation


def test_should_output_owner_text_when_list_prompt_carries_an_image(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn_blocks([image_block(), text_block(BLOCKS_OWNER)], ts("08:20:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert (len(result.user_turns_with(BLOCKS_OWNER)),
            result.anywhere_in_conversation("IMAGEN-BASE64")) == (1, False), result.conversation


def test_should_output_every_text_block_when_list_prompt_has_several(tmp_path, closed_repo):
    second = "Y comprar pan de camino."
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn_blocks([text_block(LINKED_SESSIONS), text_block(BLOCKS_OWNER),
                                      text_block(second)], ts("08:20:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)
    both = [turn for turn in result.user_turns_with(BLOCKS_OWNER) if second in turn]

    assert (len(both), result.anywhere_in_conversation("Linked sessions now")) == (1, False), \
        result.conversation


# ── (g) transcript lines that are not records ───────────────────────────


@pytest.mark.parametrize("raw_line", ["42", "null", "[1, 2]", '"just a string"'],
                         ids=["number", "null", "list", "string"])
def test_should_keep_going_when_a_line_parses_to_non_dict_json(tmp_path, closed_repo, raw_line):
    path = tmp_path / "s.jsonl"
    write_transcript(path, [human("ANTES-DE-LA-LINEA-RARA", ts("08:00:00"))])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(raw_line + "\n")
        handle.write(json.dumps(human("DESPUES-DE-LA-LINEA-RARA", ts("08:10:00"))) + "\n")

    result = run(tmp_path, closed_repo, str(path))

    assert (len(result.user_turns_with("ANTES-DE-LA-LINEA-RARA")),
            len(result.user_turns_with("DESPUES-DE-LA-LINEA-RARA"))) == (1, 1), result.text


def test_should_count_in_a_note_the_lines_that_do_not_parse(tmp_path, closed_repo):
    """A mangled line mid-file and a truncated last one (a transcript still being
    written) are counted in the header, never dropped unseen, and do not stop the close."""
    good = [human("ANTES-DE-LA-LINEA-ROTA", ts("08:00:00")),
            human("DESPUES-DE-LA-LINEA-ROTA", ts("08:10:00"))]
    clean = write_transcript(tmp_path / "clean" / "s.jsonl", good)
    broken = tmp_path / "broken" / "s.jsonl"
    lines = [json.dumps(record, ensure_ascii=False) for record in good]
    with open(write_transcript(broken, []), "w", encoding="utf-8") as handle:
        handle.write(lines[0] + "\n{esto no es json\n" + lines[1] + "\n"
                     + lines[1][: len(lines[1]) // 2])

    baseline = run(tmp_path, closed_repo, clean, out_name="clean.txt")
    result = run(tmp_path, closed_repo, str(broken), out_name="broken.txt")
    added = [line for line in result.header.split("\n")
             if line not in baseline.header.split("\n") and not line.startswith("transcript:")]
    counted = [line for line in added if line.startswith("note:") and " 2 " in f" {line} "]

    assert (len(added), len(counted), len(result.turns)) == (1, 1, 2), result.header
