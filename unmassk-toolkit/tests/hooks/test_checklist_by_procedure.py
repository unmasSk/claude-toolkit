"""D-121 (#101 A3): la checklist de Flow depende del procedimiento.

Contrato test-first (Dante, 2026-10-18), mecanismo "opcion C" del mapa de
Bilbo: `checklists/flow.json` conserva `boxes` (la lista entera = Completo)
y gana una clave OPCIONAL `procedures`. El inject guarda la entrada entera
del manifiesto (con `procedures`) en el registro de sesion; el gate de Stop,
para una entrada con `procedures`, mira el tablero:

- existe la tarea "Procedimiento: Corto"  -> espera la lista Corto + ese selector;
- existe "Procedimiento: Trivial"         -> esa entrada no espera nada;
- existe "Procedimiento: Completo", o ningun selector -> la lista entera
  (`boxes`). En la duda, la mayor.

Entradas sin `procedures` (audit, council, close-session) y entradas viejas
de registro sin la clave nueva se comportan exactamente como hoy.

FORMA DE `procedures` QUE ESTE CONTRATO FIJA (el encargo dice "tres
selectores + la lista de Corto y la de Trivial", sin fijar la forma JSON;
esta es la que Ultron tiene que implementar):

    "procedures": {
        "Trivial":  {"selector": "Procedimiento: Trivial",  "boxes": []},
        "Corto":    {"selector": "Procedimiento: Corto",    "boxes": [...]},
        "Completo": {"selector": "Procedimiento: Completo"}
    }

`Completo` no lleva `boxes`: usa el `boxes` de nivel superior.

Valores esperados: salen del encargo (textos literales de la lista Corto,
escritos aqui a mano) y de manifiestos/registros que ESTE fichero escribe
-- nunca de leer el codigo nuevo. Los manifiestos temporales van al
`checklists/` real con nombre uuid y se borran en el teardown (fixture
`make_manifest` de conftest.py, el mismo patron que
test_skill_checklist_inject.py); `checklists/flow.json` real solo se LEE.

Clasificacion: las clases `TestGolden*` son el comportamiento anterior a
D-121 que tiene que sobrevivir; las `TestContract*` son el contrato D-121,
ya implementado (VERDE desde la pasada de Ultron, 2026-10-18).
"""

import json
import uuid

import pytest

from .conftest import (
    CHECKLISTS_DIR,
    GATE_HOOK,
    INJECT_HOOK,
    fake_home_env,
    make_skill_payload,
    make_stop_payload,
    registry_path,
    run_hook,
    task_board_dir,
    unique_skill_name,
    write_task,
)

# ── Los textos del contrato (escritos a mano desde el encargo) ──────────

SEL_TRIVIAL = "Procedimiento: Trivial"
SEL_CORTO = "Procedimiento: Corto"
SEL_COMPLETO = "Procedimiento: Completo"

# La lista Corto real que flow.json debe declarar (encargo, textos exactos).
FLOW_CORTO_BOXES = [
    "Gate: sin feature de Flow abierto antes de arrancar uno nuevo",
    "Triaje: procedimiento decidido (Trivial/Corto/Completo) y seam declarada",
    "Brainstorm: gray areas resueltas y modo de build (test-first/linear) decidido",
    "Corto — Ultron hizo el cambio",
    "Corto — Dante entregó el test del cambio (si el proyecto tiene tests)",
    "Corto — Cerberus revisó el código y el test",
    "Corto — se corrigió una sola vez lo que señaló (código, Ultron; tests, Dante)",
    "Close — las pruebas de lo tocado en verde",
    "Corto — commit y push hechos, rama fusionada y borrada si la hubo, issue cerrada si la hay, y se preguntó si seguir",
]

# Cajas de Completo que Corto NO lleva (verificadas a mano contra la
# lista entera de hoy: el plan, Moriarty, Yoda -- lo que motivo D-121).
FLOW_FULL_ONLY_SAMPLE = [
    "Plan: docs/plan/*.md escrito y Plan Checker pasado",
    "Verify fase B — con todo terminado, Moriarty entregó veredicto sobre código y tests",
    "Verify fase B — Yoda, a ciegas, dio su único veredicto y el camino al 110",
]

# Manifiesto sintetico para los tests de gate/inject: independiente de
# flow.json, para que el gate se pruebe sin depender de su contenido real.
SYN_FULL = [
    "Gate: nada abierto",
    "Triaje: procedimiento decidido",
    "Plan escrito y revisado",
    "Ejecución — Ultron construyó",
    "Moriarty atacó lo arreglado",
    "Yoda dio su veredicto",
    "Close — pruebas en verde",
]
SYN_CORTO = [
    "Gate: nada abierto",
    "Triaje: procedimiento decidido",
    "Corto — Cerberus revisó el código",
    "Close — pruebas en verde",
]
SYN_FULL_ONLY = [b for b in SYN_FULL if b not in SYN_CORTO]

AUDIT_BOXES = [
    "Auditoría — informe entregado",
    "Auditoría — puntuación sobre 110",
]


def _procedures(corto_boxes):
    return {
        "Trivial": {"selector": SEL_TRIVIAL, "boxes": []},
        "Corto": {"selector": SEL_CORTO, "boxes": list(corto_boxes)},
        "Completo": {"selector": SEL_COMPLETO},
    }


def _flow_like_entry(skill, full=SYN_FULL, corto=SYN_CORTO):
    return {"skill": skill, "boxes": list(full), "procedures": _procedures(corto)}


def _plain_entry(skill, boxes):
    return {"skill": skill, "boxes": list(boxes)}


def _seed_entries(project_dir, session_id, entries, block_count=0):
    """Registro por-sesion con varias entradas, escrito directamente (sin
    pasar por el inject) en el esquema real de lib/checklist_state.py."""
    path = registry_path(project_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"session_id": session_id, "skills": entries, "block_count": block_count},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _write_board(fake_home, session_id, tasks):
    """`tasks`: lista de (subject, status). Ids 1..N."""
    board = task_board_dir(fake_home, session_id)
    for i, (subject, status) in enumerate(tasks, start=1):
        write_task(board, i, subject, status)
    return board


def _done(subjects):
    return [(s, "completed") for s in subjects]


def _gate(fake_home, project_dir, session_id):
    rc, parsed, stdout, stderr = run_hook(
        GATE_HOOK,
        make_stop_payload(project_dir, session_id),
        cwd=project_dir,
        env=fake_home_env(fake_home),
    )
    assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
    assert "Traceback" not in stderr, stderr
    return parsed, stdout, stderr


def _assert_silent(stdout):
    assert stdout.strip() == "", (
        f"el gate tenia que dejar cerrar en silencio; stdout={stdout!r}"
    )


def _assert_blocks(parsed, stdout):
    assert parsed is not None and parsed.get("decision") == "block", (
        f"el gate tenia que bloquear; stdout={stdout!r}"
    )
    return parsed.get("reason", "")


def _session():
    return f"sess-{uuid.uuid4().hex[:8]}"


def _inject_real_flow(fake_home, project_dir, sid):
    """Skill(unmassk-flow) por el inject real con el flow.json real, y
    prueba de que el registro quedo escrito con `procedures`: sin esto, un
    inject que no registra nada dejaria pasar al gate en silencio y los
    tests de extremo a extremo saldrian verdes por la razon equivocada."""
    rc, parsed, stdout, stderr = run_hook(
        INJECT_HOOK,
        make_skill_payload(project_dir, sid, "unmassk-flow"),
        cwd=project_dir,
        env=fake_home_env(fake_home),
    )
    assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
    path = registry_path(project_dir, sid)
    assert path.exists(), f"el inject no escribio registro; stderr={stderr!r}"
    registry = json.loads(path.read_text(encoding="utf-8"))
    assert len(registry["skills"]) == 1, registry
    assert "procedures" in registry["skills"][0], registry


# ═════════════════════════════ GOLDEN (verde hoy) ═══════════════════════

class TestGoldenEntriesWithoutProceduresUnaffected:
    """Bug que atrapan: que el filtrado por procedimiento se aplique a
    manifiestos que no lo declaran (audit dejaria de exigir sus casillas)."""

    def test_should_still_expect_audit_boxes_when_board_has_a_corto_selector(
        self, fake_home, project_dir
    ):
        sid = _session()
        _seed_entries(project_dir, sid, [_plain_entry("unmassk-audit", AUDIT_BOXES)])
        _write_board(fake_home, sid, [(SEL_CORTO, "completed"), (AUDIT_BOXES[0], "completed")])

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        assert AUDIT_BOXES[1] in reason, reason

    def test_should_pass_silently_when_plain_entry_is_complete(self, fake_home, project_dir):
        sid = _session()
        _seed_entries(project_dir, sid, [_plain_entry("unmassk-audit", AUDIT_BOXES)])
        _write_board(fake_home, sid, _done(AUDIT_BOXES))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])


class TestGoldenOldRegistryEntryWithoutProceduresKey:
    """Bug: una entrada de registro escrita antes de D-121 (sin la clave)
    tomada como Corto/Trivial por ver un selector en el tablero."""

    def test_should_expect_full_list_when_old_entry_and_corto_selector(
        self, fake_home, project_dir
    ):
        sid = _session()
        _seed_entries(project_dir, sid, [_plain_entry("unmassk-flow", SYN_FULL)])
        _write_board(fake_home, sid, [(SEL_CORTO, "completed")] + _done(SYN_CORTO))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        for box in SYN_FULL_ONLY:
            assert box in reason, f"falta {box!r} en {reason!r}"


class TestGoldenNoSelectorMeansFullList:
    """Bug: sin selector en el tablero, el gate eligiendo la lista corta
    (o ninguna) en vez de la mayor."""

    def test_should_block_on_full_only_boxes_when_no_selector(self, fake_home, project_dir):
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done(SYN_CORTO))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        for box in SYN_FULL_ONLY:
            assert box in reason, f"falta {box!r} en {reason!r}"

    def test_should_pass_when_no_selector_and_full_list_completed(
        self, fake_home, project_dir
    ):
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done(SYN_FULL))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_match_full_list_ignoring_case_and_accents(self, fake_home, project_dir):
        """Casefold + sin tildes sigue valiendo para la lista entera."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        typed = [
            "GATE: NADA ABIERTO",
            "triaje: procedimiento decidido",
            "plan escrito y revisado",
            "Ejecucion — ULTRON construyo",
            "moriarty ataco lo arreglado",
            "YODA dio su veredicto",
            "close — pruebas en verde",
        ]
        _write_board(fake_home, sid, _done(typed))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])


class TestGoldenFullFlowManifestKeepsItsFullList:
    """Bug: que al añadir `procedures` a flow.json se recorte `boxes`
    (Completo dejaria de exigir plan, Moriarty y Yoda)."""

    def test_should_keep_full_only_boxes_in_top_level_boxes(self):
        data = json.loads((CHECKLISTS_DIR / "flow.json").read_text(encoding="utf-8"))
        for box in FLOW_FULL_ONLY_SAMPLE + FLOW_CORTO_BOXES[:3]:
            assert box in data["boxes"], f"{box!r} ya no esta en flow.json boxes"


# ═════════════════════════════ CONTRATO D-121 ═══════════════════════════

class TestContractRealFlowManifestDeclaresProcedures:
    """Bug: flow.json sin la clave, o con la lista Corto mal copiada (una
    casilla Corto que el modelo no puede casar bloquearia cada Corto)."""

    def test_should_declare_three_selectors_and_corto_and_trivial_lists(self):
        data = json.loads((CHECKLISTS_DIR / "flow.json").read_text(encoding="utf-8"))
        procedures = data.get("procedures")
        assert isinstance(procedures, dict), f"flow.json sin 'procedures': claves={list(data)}"
        assert procedures["Trivial"] == {"selector": SEL_TRIVIAL, "boxes": []}
        assert procedures["Corto"] == {"selector": SEL_CORTO, "boxes": FLOW_CORTO_BOXES}
        assert procedures["Completo"]["selector"] == SEL_COMPLETO
        assert "boxes" not in procedures["Completo"], (
            "Completo usa el 'boxes' de nivel superior, no una copia"
        )


class TestContractInjectStoresProceduresAndPrintsThreeLists:
    """Bug: el inject descarta `procedures` al registrar (el gate nunca
    podria filtrar) o no le dice al modelo que cree el selector."""

    def test_should_round_trip_procedures_into_registry(
        self, fake_home, project_dir, make_manifest
    ):
        skill = unique_skill_name()
        path = make_manifest(skill, SYN_FULL)
        path.write_text(
            json.dumps(_flow_like_entry(skill), ensure_ascii=False), encoding="utf-8"
        )
        sid = _session()

        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK,
            make_skill_payload(project_dir, sid, skill),
            cwd=project_dir,
            env=fake_home_env(fake_home),
        )

        assert rc == 0, stderr
        registry = json.loads(registry_path(project_dir, sid).read_text(encoding="utf-8"))
        entry = registry["skills"][0]
        assert entry["skill"] == skill
        assert entry["boxes"] == SYN_FULL
        assert entry.get("procedures") == _procedures(SYN_CORTO), entry

    def test_should_name_all_three_selectors_and_corto_boxes_in_message(
        self, fake_home, project_dir, make_manifest
    ):
        skill = unique_skill_name()
        path = make_manifest(skill, SYN_FULL)
        path.write_text(
            json.dumps(_flow_like_entry(skill), ensure_ascii=False), encoding="utf-8"
        )
        sid = _session()

        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK,
            make_skill_payload(project_dir, sid, skill),
            cwd=project_dir,
            env=fake_home_env(fake_home),
        )

        context = parsed["hookSpecificOutput"]["additionalContext"]
        for text in [SEL_TRIVIAL, SEL_CORTO, SEL_COMPLETO] + SYN_CORTO + SYN_FULL:
            assert text in context, f"el mensaje no nombra {text!r}: {context!r}"


class TestContractInjectRefusesMalformedProcedures:
    """Bug: un `procedures` mal escrito (selector vacio) registrado igual:
    el gate no podria casarlo nunca. Contrato: no se registra nada, se
    avisa por stderr y la llamada a la skill no se rompe (exit 0)."""

    @pytest.mark.parametrize("bad_selector", ["", "   "])
    def test_should_warn_and_register_nothing_when_a_selector_is_blank(
        self, fake_home, project_dir, make_manifest, bad_selector
    ):
        skill = unique_skill_name()
        path = make_manifest(skill, SYN_FULL)
        entry = _flow_like_entry(skill)
        entry["procedures"]["Corto"]["selector"] = bad_selector
        path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        sid = _session()

        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK,
            make_skill_payload(project_dir, sid, skill),
            cwd=project_dir,
            env=fake_home_env(fake_home),
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stderr.strip() != "", "el manifiesto malo tiene que avisar por stderr"
        assert "Traceback" not in stdout and "Traceback" not in stderr
        assert not registry_path(project_dir, sid).exists(), (
            "un manifiesto con 'procedures' mal formado no debe registrar nada"
        )


class TestContractGateFiltersByProcedure:
    def test_should_pass_when_corto_selector_and_corto_list_completed(
        self, fake_home, project_dir
    ):
        """Bug: Corto obligado a marcar Moriarty/Yoda/plan (el de D-121)."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done([SEL_CORTO] + SYN_CORTO))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_block_on_corto_box_only_when_corto_selected(self, fake_home, project_dir):
        """Bug: con Corto elegido, el gate pide casillas que no son de Corto
        (o deja pasar una de Corto pendiente)."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(
            fake_home,
            sid,
            _done([SEL_CORTO] + SYN_CORTO[:-1]) + [(SYN_CORTO[-1], "pending")],
        )

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        assert SYN_CORTO[-1] in reason, reason
        for box in SYN_FULL_ONLY:
            assert box not in reason, f"Corto no debe pedir {box!r}: {reason!r}"

    def test_should_expect_the_corto_selector_itself_to_be_completed(
        self, fake_home, project_dir
    ):
        """Contrato: Corto = su lista + ese selector."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, [(SEL_CORTO, "in_progress")] + _done(SYN_CORTO))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        assert SEL_CORTO in reason, reason
        for box in SYN_FULL_ONLY:
            assert box not in reason, f"Corto no debe pedir {box!r}: {reason!r}"

    def test_should_expect_nothing_when_trivial_selected(self, fake_home, project_dir):
        """Bug: un cambio de un boton bloqueado por 16 casillas."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done([SEL_TRIVIAL]))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    @pytest.mark.parametrize("status", ["pending", "in_progress"])
    def test_should_never_block_when_trivial_selector_is_left_open(
        self, fake_home, project_dir, status
    ):
        """D-121: Trivial = ninguna casilla, ni siquiera su selector. Bug:
        el selector Trivial exigido como casilla (bloquearia el cambio
        de un boton por no tachar 'Procedimiento: Trivial')."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, [(SEL_TRIVIAL, status)])

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_take_corto_when_trivial_and_corto_both_present(
        self, fake_home, project_dir
    ):
        """En la duda, la mayor: Trivial no puede ganar a Corto. Bug:
        Trivial elegido -> pase en silencio con una casilla Corto pendiente;
        o Completo elegido -> pide plan/Moriarty/Yoda."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(
            fake_home,
            sid,
            _done([SEL_TRIVIAL, SEL_CORTO] + SYN_CORTO[:-1]) + [(SYN_CORTO[-1], "pending")],
        )

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        assert SYN_CORTO[-1] in reason, reason
        for box in SYN_FULL_ONLY:
            assert box not in reason, f"Corto no debe pedir {box!r}: {reason!r}"

    def test_should_expect_full_list_when_completo_selected(self, fake_home, project_dir):
        """Bug: Completo tratado como Corto (o como Trivial)."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done([SEL_COMPLETO] + SYN_CORTO))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        for box in SYN_FULL_ONLY:
            assert box in reason, f"falta {box!r} en {reason!r}"

    def test_should_pass_when_completo_selected_and_full_list_completed(
        self, fake_home, project_dir
    ):
        """Bug: el selector Completo exigido como casilla extra que el
        modelo nunca crearia por error, o el selector rompiendo el pase."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done([SEL_COMPLETO] + SYN_FULL))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_take_the_bigger_list_when_corto_and_completo_both_present(
        self, fake_home, project_dir
    ):
        """En la duda, la mayor: Corto no puede ganar a Completo."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        _write_board(fake_home, sid, _done([SEL_CORTO, SEL_COMPLETO] + SYN_CORTO))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        for box in SYN_FULL_ONLY:
            assert box in reason, f"falta {box!r} en {reason!r}"

    def test_should_match_corto_selector_and_boxes_ignoring_case_and_accents(
        self, fake_home, project_dir
    ):
        """Bug: el selector comparado byte a byte (el modelo escribe
        'procedimiento: CORTO' y acaba en la lista entera)."""
        sid = _session()
        _seed_entries(project_dir, sid, [_flow_like_entry("unmassk-flow")])
        typed = [
            "procedimiento: CORTO",
            "gate: NADA abierto",
            "TRIAJE: procedimiento decidido",
            "corto — cerberus reviso el codigo",
            "Close — Pruebas En Verde",
        ]
        _write_board(fake_home, sid, _done(typed))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])


class TestContractFlowAndAuditInOneSession:
    """Bug: el procedimiento de Flow filtrando tambien las casillas de
    otra skill cargada en la misma sesion."""

    def test_should_block_only_on_audit_box_when_corto_flow_done(self, fake_home, project_dir):
        sid = _session()
        _seed_entries(
            project_dir,
            sid,
            [_flow_like_entry("unmassk-flow"), _plain_entry("unmassk-audit", AUDIT_BOXES)],
        )
        _write_board(fake_home, sid, _done([SEL_CORTO] + SYN_CORTO + AUDIT_BOXES[:1]))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        assert AUDIT_BOXES[1] in reason, reason
        for box in SYN_FULL_ONLY:
            assert box not in reason, f"Corto no debe pedir {box!r}: {reason!r}"

    def test_should_still_expect_audit_boxes_when_flow_is_trivial(self, fake_home, project_dir):
        sid = _session()
        _seed_entries(
            project_dir,
            sid,
            [_flow_like_entry("unmassk-flow"), _plain_entry("unmassk-audit", AUDIT_BOXES)],
        )
        _write_board(fake_home, sid, _done([SEL_TRIVIAL]))

        reason = _assert_blocks(*_gate(fake_home, project_dir, sid)[:2])

        for box in AUDIT_BOXES:
            assert box in reason, reason
        for box in SYN_FULL:
            assert box not in reason, f"Trivial no debe pedir {box!r}: {reason!r}"

    def test_should_pass_when_corto_flow_and_audit_all_done(self, fake_home, project_dir):
        sid = _session()
        _seed_entries(
            project_dir,
            sid,
            [_flow_like_entry("unmassk-flow"), _plain_entry("unmassk-audit", AUDIT_BOXES)],
        )
        _write_board(fake_home, sid, _done([SEL_CORTO] + SYN_CORTO + AUDIT_BOXES))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])


class TestContractEndToEndThroughRealFlowSkill:
    """Por la puerta real: Skill(unmassk-flow) con el flow.json real ->
    registro -> Stop. Bug: las piezas sueltas funcionan pero el cableado
    inject->registro->gate pierde el procedimiento."""

    def test_should_close_a_corto_session_with_only_the_corto_boxes(
        self, fake_home, project_dir
    ):
        sid = _session()
        _inject_real_flow(fake_home, project_dir, sid)
        _write_board(fake_home, sid, _done([SEL_CORTO] + FLOW_CORTO_BOXES))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])

    def test_should_close_a_trivial_session_with_only_the_selector(
        self, fake_home, project_dir
    ):
        sid = _session()
        _inject_real_flow(fake_home, project_dir, sid)
        _write_board(fake_home, sid, _done([SEL_TRIVIAL]))

        _assert_silent(_gate(fake_home, project_dir, sid)[1])
