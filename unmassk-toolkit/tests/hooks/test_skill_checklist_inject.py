"""Contrato de `hooks/skill-checklist-inject.py` -- pieza 2 de
docs/plan/casillas-por-programa.md (D-052), evento `PostToolUse` sobre la
herramienta `Skill`.

Modo test-first, pase de CONTRATO: aceptacion -- una fila del contrato, un
test -- no el barrido exhaustivo de ramas (ese llega en el
endurecimiento, sobre el codigo real).

NOTA (2026-08-24): el encargo se escribio con el hook todavia inexistente
("los ficheros de hooks no existen aun -- el rojo esperado es por
ausencia"). Ultron lo implemento EN PARALELO mientras se escribia este
fichero, tal y como decia el propio encargo. Verificado leyendo
`hooks/skill-checklist-inject.py` y `lib/checklist_state.py` directamente
(nunca de memoria ni del diseno) antes de fijar cada asercion -- ver
`conftest.py`, docstring de modulo, "ESQUEMA REAL", para el detalle
completo del esquema de manifiesto/registro que este fichero ya no
adivina, sino que compara contra el codigo real.

De donde sale cada cosa que este fichero da por cierta:

- El encargo (contrato A, filas 1-4) fija el comportamiento observable.
- `docs/plan/casillas-por-programa.md`: la ruta de los manifiestos
  (`checklists/<skill>.json`, sibling de `hooks/`) y el canal de salida
  (`additionalContext` con "la orden literal de crear estas casillas,
  textualmente").
- `hook-input-schemas.md` (skill `plugin-dev`, instalada en esta maquina):
  forma real del payload de `PostToolUse` (`tool_name`, `tool_input` con
  `skill`/`args` para la herramienta `Skill`).
- El codigo real de `hooks/skill-checklist-inject.py` y
  `lib/checklist_state.py` para el esquema exacto de manifiesto, registro
  y envoltorio de `additionalContext` (`hookSpecificOutput.
  additionalContext`, confirmado en el fuente) -- ver `conftest.py`.

Round trip real (unmassk-standards Sec.34): el contenido de
`additionalContext` y el del registro de sesion se comparan contra los
ITEMS DEL MANIFIESTO tal y como los escribio `make_manifest()` (fixture de
`conftest.py`, un camino independiente del proceso del hook) -- nunca
contra una cadena fabricada a mano en este fichero.
"""

import json
import uuid

import pytest

from .conftest import (
    CHECKLISTS_DIR,
    INJECT_HOOK,
    fake_home_env,
    make_non_skill_payload,
    make_skill_payload,
    registry_path,
    run_hook,
    run_hook_raw,
    unique_skill_name,
)

# `fake_home`, `project_dir`, `make_manifest`, `make_corrupt_manifest` son
# fixtures de `@pytest.fixture` definidas en `conftest.py` -- se usan como
# parametro de test (pytest las descubre solas), nunca importadas aqui
# (mismo patron que `test_boot_launcher.py` con `tmp_repo`).


def _find_additional_context(parsed):
    """Busca `additionalContext` en la raiz o bajo `hookSpecificOutput`
    -- ver ASUNCION 3. Devuelve `None` si no esta en ninguno de los dos
    sitios (o si `parsed` es `None`)."""
    if not isinstance(parsed, dict):
        return None
    if isinstance(parsed.get("additionalContext"), str):
        return parsed["additionalContext"]
    hso = parsed.get("hookSpecificOutput")
    if isinstance(hso, dict) and isinstance(hso.get("additionalContext"), str):
        return hso["additionalContext"]
    return None


class TestSkillWithManifestWritesRegistryAndInjectsContext:
    """Contrato A.1: `Skill(<skill-con-manifiesto>)` -> registro
    por-sesion escrito + orden literal de crear las casillas."""

    def test_registry_matches_manifest_and_context_names_every_item(
        self, fake_home, project_dir, make_manifest
    ):
        skill = unique_skill_name()
        items = [
            "Confirmar el modo de build (test-first o lineal)",
            "Ejecutar Cerberus y Argus en paralelo",
            "Correr Moriarty el ultimo, siempre",
        ]
        make_manifest(skill, items)
        session_id = f"sess-{uuid.uuid4().hex[:8]}"

        payload = make_skill_payload(project_dir, session_id, skill)
        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert "Traceback" not in stdout and "Traceback" not in stderr

        reg_path = registry_path(project_dir, session_id)
        assert reg_path.exists(), (
            f"no se escribio el registro por-sesion en {reg_path} -- "
            f"stdout={stdout!r} stderr={stderr!r}"
        )
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
        skills = registry.get("skills")
        assert isinstance(skills, list) and len(skills) == 1, (
            f"esperaba una entrada en 'skills' (esquema real de "
            f"lib/checklist_state.py): registro={registry!r}"
        )
        entry = skills[0]
        assert entry.get("skill") == skill
        assert list(entry.get("boxes", [])) == items, (
            "el registro tiene que llevar las MISMAS casillas que el "
            f"manifiesto (round trip): manifiesto={items!r} "
            f"registro={entry.get('boxes')!r}"
        )

        context = _find_additional_context(parsed)
        assert context is not None, (
            "esperaba additionalContext (raiz o hookSpecificOutput) con "
            f"la orden de crear las casillas; stdout={stdout!r}"
        )
        for item in items:
            assert item in context, (
                f"additionalContext no menciona la casilla {item!r} "
                f"textualmente: {context!r}"
            )

    def test_works_without_optional_args_field(self, fake_home, project_dir, make_manifest):
        """`tool_input.args` es opcional segun el esquema real (fila
        `Skill` de "Tool Input Schemas") -- el hook no debe reventar ni
        callar por su ausencia."""
        skill = unique_skill_name()
        items = ["Unico paso"]
        make_manifest(skill, items)
        session_id = f"sess-{uuid.uuid4().hex[:8]}"

        payload = make_skill_payload(project_dir, session_id, skill)
        payload["tool_input"].pop("args", None)

        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert registry_path(project_dir, session_id).exists()


class TestSkillWithoutManifestIsSilent:
    """Contrato A.2: skill sin manifiesto -> silencio total, exit 0."""

    def test_no_output_and_no_registry_written(self, fake_home, project_dir):
        skill = unique_skill_name(prefix="skill-nunca-tiene-manifiesto")
        session_id = f"sess-{uuid.uuid4().hex[:8]}"

        payload = make_skill_payload(project_dir, session_id, skill)
        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", f"esperaba silencio total, salio: {stdout!r}"
        assert not registry_path(project_dir, session_id).exists()


class TestNonSkillToolIsSilent:
    """Contrato A.3: herramienta distinta de `Skill` -> silencio."""

    def test_bash_tool_produces_no_output(self, fake_home, project_dir):
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        payload = make_non_skill_payload(project_dir, session_id, tool_name="Bash")

        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert stdout.strip() == "", f"esperaba silencio total, salio: {stdout!r}"
        assert not registry_path(project_dir, session_id).exists()


class TestCorruptOrMalformedManifestFailsOpen:
    """Contrato A.4: manifiesto corrupto o error interno -> deja pasar
    avisando por stderr, exit 0, nunca rompe la llamada."""

    def test_invalid_json_manifest_fails_open(
        self, fake_home, project_dir, make_corrupt_manifest
    ):
        skill = unique_skill_name(prefix="skill-manifiesto-corrupto")
        make_corrupt_manifest(skill)
        session_id = f"sess-{uuid.uuid4().hex[:8]}"

        payload = make_skill_payload(project_dir, session_id, skill)
        rc, parsed, stdout, stderr = run_hook(
            INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
        )

        assert rc == 0, (
            f"un manifiesto corrupto NUNCA debe romper la llamada; "
            f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        )
        assert stderr.strip() != "", "el fallo tiene que avisar por stderr"
        assert "Traceback" not in stdout and "Traceback" not in stderr
        assert not registry_path(project_dir, session_id).exists()

    def test_manifest_missing_boxes_key_fails_open(self, fake_home, project_dir):
        """JSON valido pero sin la clave `boxes` (esquema real, ver
        `conftest.py` "ESQUEMA REAL" punto 2) -- `_load_manifest` hace
        `data["boxes"]` sin comprobar antes, asi que esto es un
        `KeyError` real capturado por el mismo camino que un manifiesto
        corrupto: avisa y deja pasar, nunca revienta ni fabrica un
        registro incompleto.

        Escribe el manifiesto directamente (no via `make_manifest`, que
        siempre incluye `boxes`) para dejar la forma incompleta a
        proposito; limpieza manual en `try/finally`.
        """
        skill = unique_skill_name(prefix="skill-manifiesto-sin-boxes")
        pre_existing_dir = CHECKLISTS_DIR.exists()
        CHECKLISTS_DIR.mkdir(parents=True, exist_ok=True)
        path = CHECKLISTS_DIR / f"{skill}.json"
        path.write_text(json.dumps({"skill": skill}), encoding="utf-8")

        try:
            session_id = f"sess-{uuid.uuid4().hex[:8]}"
            payload = make_skill_payload(project_dir, session_id, skill)
            rc, parsed, stdout, stderr = run_hook(
                INJECT_HOOK, payload, cwd=project_dir, env=fake_home_env(fake_home)
            )

            assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
            assert "Traceback" not in stdout and "Traceback" not in stderr
            assert not registry_path(project_dir, session_id).exists()
        finally:
            path.unlink(missing_ok=True)
            if not pre_existing_dir and CHECKLISTS_DIR.exists():
                try:
                    next(CHECKLISTS_DIR.iterdir())
                except StopIteration:
                    CHECKLISTS_DIR.rmdir()

    def test_totally_malformed_stdin_fails_open(self, fake_home, project_dir):
        """Entrada estandar que ni siquiera es JSON -- mismo principio de
        "nunca rompe la llamada" que un manifiesto corrupto (protocolo 4
        del diseno se lee como una regla general de fail-open ante
        cualquier error interno, no solo el manifiesto)."""
        rc, stdout, stderr = run_hook_raw(
            INJECT_HOOK,
            "esto no es json en absoluto {{{",
            cwd=project_dir,
            env=fake_home_env(fake_home),
        )

        assert rc == 0, f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        assert "Traceback" not in stdout and "Traceback" not in stderr
