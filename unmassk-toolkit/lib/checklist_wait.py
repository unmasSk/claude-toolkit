"""
checklist_wait.py -- D-142: is this Stop a pause for agent work, or the close?

Claude Code's Stop input carries `background_tasks`, the list of tasks still
in flight. Only `subagent` and `workflow` entries mean the orchestrator is
waiting on agents and will be woken when they finish; a `shell` or `monitor`
can live for the whole session (dev server, `tail -f`), so on its own it
never counts as a wait. Anything that is not a list, or an entry that is not
an object, counts as nothing -- the gate then behaves exactly as without it.
"""

_AGENT_WORK_TYPES = ("subagent", "workflow")
_LABEL_FIELD = {"subagent": "agent_type", "workflow": "name"}


def _one_line(text: str) -> str:
    return " ".join(text.split())


def agent_wait_line(hook_input: dict) -> str:
    """The single stderr line naming the agent work this Stop waits on,
    or "" when nothing of type subagent/workflow is in flight."""
    tasks = hook_input.get("background_tasks")
    if not isinstance(tasks, list):
        return ""
    waits = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("type") not in _AGENT_WORK_TYPES:
            continue
        kind = task["type"]
        label = task.get(_LABEL_FIELD[kind])
        waits.append(f"{kind} {_one_line(label)}" if isinstance(label, str) and label.strip() else kind)
    if not waits:
        return ""
    return (
        f"checklist-gate: waiting on in-flight agent work ({'; '.join(waits)}) "
        "-- allowing this Stop, uncounted (D-142)\n"
    )
