"""RED contract: the installer's stale-hook cleanup must only remove the
toolkit's OWN old local-install hook entries, never the owner's hooks.

Today `lib/install_inspect.py` flags any hook command containing "hooks/" or
"bin/" (without ${CLAUDE_PLUGIN_ROOT}) and `lib/install_apply.py::
_cleanup_stale_settings_hooks` then deletes the WHOLE `hooks` key. Real
victim: the owner's PreToolUse hook in monyma-forms/.claude/settings.json.

Ground truth is not hand-typed for the toolkit side: the old install's real
settings are read live from this repo's git history (the commit that shipped
`.claude/settings.json` with the old local hooks, and the original
settings-snippet.json that used `.claude/hooks/`). If that history is not
reachable (shallow clone), those tests skip loudly rather than substitute a
fixture. The owner's monyma command is the one verbatim literal, taken from
the real file on the owner's machine.

Driven through the real entry: bin/git-memory-install.py --auto on a temp git
repo, HOME isolated.
"""
import copy
import json
import os
import subprocess

import pytest

from conftest import INSTALL, SOURCE_ROOT, git_cmd, run_script

OLD_LOCAL_SETTINGS_REV = "90680b6e"   # shipped .claude/settings.json: "python3 hooks/<x>.py"
OLD_SNIPPET_REV = "a5afd66f"          # original settings-snippet.json: "python3 .claude/hooks/<x>.py"

MONYMA_USER_HOOK = {
    "matcher": "Bash|Edit|Write",
    "hooks": [{"type": "command",
               "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/papel-gate.py"'}],
}


def _git_show(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=SOURCE_ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        pytest.skip(f"git history for {rev}:{path} not reachable (shallow clone): "
                    "old-install ground truth NOT verified")
    return json.loads(r.stdout)


def _old_hooks(rev, path):
    return _git_show(rev, path)["hooks"]


def _commands(hooks):
    out = []
    for groups in hooks.values():
        for g in groups:
            out.extend(h["command"] for h in g.get("hooks", []))
    return out


@pytest.fixture
def repo(tmp_path):
    r = str(tmp_path / "repo")
    os.makedirs(os.path.join(r, ".claude"))
    git_cmd(["init"], r)
    git_cmd(["commit", "--allow-empty", "-m", "init"], r)
    return r


def _install(repo, tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return run_script(INSTALL, repo, ["--auto"], env={"HOME": str(home), "USERPROFILE": str(home)})


def _write(repo, data, indent=2):
    p = os.path.join(repo, ".claude", "settings.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    return p


def _read(repo):
    with open(os.path.join(repo, ".claude", "settings.json"), encoding="utf-8") as f:
        return json.load(f)


def test_should_keep_owner_hook_when_only_owner_hook_present(repo, tmp_path):
    settings = {"hooks": {"PreToolUse": [copy.deepcopy(MONYMA_USER_HOOK)]}}
    _write(repo, settings)
    _install(repo, tmp_path)
    assert _read(repo) == settings


def test_should_not_rewrite_settings_when_no_toolkit_entry_is_stale(repo, tmp_path):
    p = _write(repo, {"model": "opus", "hooks": {"PreToolUse": [MONYMA_USER_HOOK]}}, indent=4)
    with open(p, "ab") as f:
        f.write(b"   \n")  # odd trailing whitespace: any json.dump rewrite would normalise it
    before = open(p, "rb").read()
    _install(repo, tmp_path)
    assert open(p, "rb").read() == before


@pytest.mark.parametrize("rev,path", [
    (OLD_LOCAL_SETTINGS_REV, ".claude/settings.json"),
    (OLD_SNIPPET_REV, "settings-snippet.json"),
])
def test_should_remove_only_old_toolkit_entries_and_keep_everything_else(repo, tmp_path, rev, path):
    old = _old_hooks(rev, path)
    old_cmds = _commands(old)
    other_plugin = {"hooks": [{"type": "command",
                               "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/other.py"}]}
    mixed = copy.deepcopy(old)
    mixed.setdefault("PreToolUse", []).append(copy.deepcopy(MONYMA_USER_HOOK))
    mixed["PostToolUse"] = mixed.get("PostToolUse", []) + [other_plugin]
    mixed["Notification"] = [{"hooks": [{"type": "command", "command": "afplay /System/x.aiff"}]}]
    settings = {"model": "opus", "permissions": {"allow": ["Bash(ls:*)"]}, "hooks": mixed}
    _write(repo, settings)
    _install(repo, tmp_path)
    got = _read(repo)
    assert got["model"] == "opus"
    assert got["permissions"] == {"allow": ["Bash(ls:*)"]}
    got_cmds = _commands(got["hooks"])
    for c in old_cmds:
        assert c not in got_cmds
    assert MONYMA_USER_HOOK["hooks"][0]["command"] in got_cmds
    assert other_plugin["hooks"][0]["command"] in got_cmds
    assert "afplay /System/x.aiff" in got_cmds
    assert MONYMA_USER_HOOK in got["hooks"]["PreToolUse"]
    assert all(groups for groups in got["hooks"].values())  # no empty event left behind


def test_should_drop_hooks_key_only_when_every_entry_was_toolkit_old_install(repo, tmp_path):
    old = _old_hooks(OLD_LOCAL_SETTINGS_REV, ".claude/settings.json")
    _write(repo, {"model": "opus", "hooks": old})
    _install(repo, tmp_path)
    got = _read(repo)
    assert got.get("model") == "opus"
    assert not got.get("hooks")


def test_should_remove_toolkit_command_from_shared_group_and_keep_owner_command(repo, tmp_path):
    old = _old_hooks(OLD_LOCAL_SETTINGS_REV, ".claude/settings.json")
    old_cmd = _commands(old)[0]
    event = next(e for e, gs in old.items() if gs[0]["hooks"][0]["command"] == old_cmd)
    owner_cmd = {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/papel-gate.py"'}
    shared = {"matcher": "Bash", "hooks": [{"type": "command", "command": old_cmd}, owner_cmd]}
    _write(repo, {"hooks": {event: [shared]}})
    _install(repo, tmp_path)
    got = _read(repo)
    assert got["hooks"] == {event: [{"matcher": "Bash", "hooks": [owner_cmd]}]}
