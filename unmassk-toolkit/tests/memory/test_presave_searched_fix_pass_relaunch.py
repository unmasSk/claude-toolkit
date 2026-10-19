"""#95 part 2c fix pass, points 4-7 (see the full list in
test_presave_searched_fix_pass.py, split 2026-10-19 for Yoda's size
finding): `--discard` carries the search, relaunches that are obeyed
literally and read back, a multi-line rule `--searched` folded, and the
customs hook's relaunches. Every expected value is what this test typed.
"""

import shlex

import pytest

from .conftest import (
    extract_note_id,
    run_gitmem_script,
    seed_config_json,
    seed_zones_json,
)
from .presave_searched_fix_support import (  # noqa: F401  (query_mod is a fixture)
    _SEARCHED,
    _ZONE1,
    _ZONE2,
    _cwd,
    _fill_holes,
    _message_of,
    _read_back,
    _relaunch_lines,
    _rules_lines,
    _run_customs,
    query_mod,
)


# ── 4. --discard carries the search ──────────────────────────────────────


class TestDiscardCarriesSearched:
    """Bug caught: the X notes `--discard` writes losing the `--searched`
    of the decision they come from (F1)."""

    def test_should_give_every_discarded_alternative_the_same_searched(
        self, tmp_repo, query_mod
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = run_gitmem_script([
            "note", "D", "--zones", _ZONE1, _ZONE2, "move sessions to postgres",
            "--why", "one database less", "--description", "redis retired",
            "--discard", "keep sessions in redis", "an extra cluster to run",
            "--discard", "store sessions in cookies", "too large for the header",
            "--searched", _SEARCHED,
        ], cwd=tmp_repo)
        assert rc == 0, f"{out!r} {err!r}"

        with _cwd(tmp_repo):
            notes = query_mod.by_zone(_ZONE1, _ZONE2)
        by_headline = {n.headline: n for n in notes}

        assert set(by_headline) == {"move sessions to postgres", "keep sessions in redis",
                                    "store sessions in cookies"}
        assert {h: n.searched for h, n in by_headline.items()} == {
            "move sessions to postgres": _SEARCHED,
            "keep sessions in redis": _SEARCHED,
            "store sessions in cookies": _SEARCHED,
        }


# ── 5. relaunches obeyed literally ───────────────────────────────────────


_RULE_OLD = "never squash the step commits of a branch"
_RULE_NEAR = "never squash the step commits of the branch"
_RULE_OTHER = "tag every release commit with its version"


def _seed_rule(repo, text, kind, quote):
    rc, out, err = run_gitmem_script(
        ["rule", text, "--kind", kind, "--quote", quote, "--searched", "seed: nada"], cwd=repo,
    )
    assert rc == 0, f"seeding the rule failed: {out!r} {err!r}"


def _rule_line(repo, text):
    # `[remember][<kind>] <emoji> <text>[ — «<quote>»]`
    matches = [line for line in _rules_lines(repo)
               if line.split(" — «")[0].endswith(" " + text)]
    assert len(matches) == 1, f"expected one rule {text!r}, rules.md has {_rules_lines(repo)!r}"
    return matches[0]


class TestRuleNearDuplicateRelaunch:
    """Bug caught (F2): the near-duplicate bounce offering a bare
    `gitmem rule "..."` -- obeyed, it bounces on D-098 again and, without
    --kind, a [claude] rule comes back as [user]."""

    @pytest.mark.parametrize("kind,quote", [
        ("claude", "none"),
        ("user", "no me aplastes los commits, ¿vale?"),
    ], ids=["claude-quote-none", "user-real-quote"])
    def test_should_carry_kind_quote_and_searched_and_save_when_obeyed(
        self, tmp_repo, kind, quote
    ):
        _seed_rule(tmp_repo, _RULE_OLD, kind, quote)

        rc, out, err = run_gitmem_script(
            ["rule", _RULE_NEAR, "--kind", kind, "--quote", quote, "--searched", _SEARCHED],
            cwd=tmp_repo,
        )
        assert rc != 0, f"must bounce as a near duplicate: {out!r}"
        offered = [line.strip() for line in (out + err).splitlines()
                   if line.strip().startswith('gitmem rule "..."')]
        assert len(offered) == 1, f"no rewrite relaunch offered: {out!r}"
        tokens = shlex.split(offered[0])

        assert tokens[tokens.index("--kind") + 1] == kind
        assert tokens[tokens.index("--quote") + 1] == quote
        assert tokens[tokens.index("--searched") + 1] == _SEARCHED

        obeyed = [_RULE_OTHER if t == "..." else t for t in tokens[1:]]
        rc2, out2, err2 = run_gitmem_script(obeyed, cwd=tmp_repo)
        assert rc2 == 0, f"obeying the relaunch bounced again: {out2!r} {err2!r}"
        assert f"[{kind}]" in _rule_line(tmp_repo, _RULE_OTHER)


class TestRuleMissingQuoteRelaunch:
    """Bug caught: the missing-quote relaunch dropping --kind (a [claude]
    rule saved as [user]) and --replaces (obeyed, a replace adds a second
    rule and the old one stays)."""

    def test_should_keep_kind_on_an_add(self, tmp_repo):
        rc, out, err = run_gitmem_script(
            ["rule", _RULE_OTHER, "--kind", "claude", "--searched", _SEARCHED], cwd=tmp_repo,
        )
        assert rc != 0, f"must bounce for the missing quote: {out!r}"
        none_relaunch = [r for r in _relaunch_lines(out + err, "gitmem rule ")
                         if "--quote none" in r]
        assert len(none_relaunch) == 1, f"{out + err!r}"

        rc2, out2, err2 = run_gitmem_script(shlex.split(none_relaunch[0])[1:], cwd=tmp_repo)

        assert rc2 == 0, f"{out2!r} {err2!r}"
        assert "[claude]" in _rule_line(tmp_repo, _RULE_OTHER)

    def test_should_keep_replaces_and_kind_on_a_replace(self, tmp_repo):
        _seed_rule(tmp_repo, _RULE_OLD, "claude", "none")
        rc, out, err = run_gitmem_script(
            ["rule", _RULE_OTHER, "--replaces", _RULE_OLD, "--kind", "claude",
             "--searched", _SEARCHED], cwd=tmp_repo,
        )
        assert rc != 0, f"must bounce for the missing quote: {out!r}"
        none_relaunch = [r for r in _relaunch_lines(out + err, "gitmem rule ")
                         if "--quote none" in r]
        assert len(none_relaunch) == 1, f"{out + err!r}"

        rc2, out2, err2 = run_gitmem_script(shlex.split(none_relaunch[0])[1:], cwd=tmp_repo)

        assert rc2 == 0, f"{out2!r} {err2!r}"
        rules = _rules_lines(tmp_repo)
        assert len(rules) == 1, f"the replace left the old rule behind: {rules!r}"
        assert "[claude]" in _rule_line(tmp_repo, _RULE_OTHER)


class TestFieldMismatchRelaunch:
    """Bug caught: the field-mismatch relaunch offering only
    `--description "..."` -- obeyed, a D without --why (a B without
    --awaits) bounces again on the very same field."""

    @pytest.mark.parametrize("note_type,headline,flag,value,attr", [
        ("D", "retire the internal wiki", "--why", "one source of truth", "why"),
        ("B", "waiting on the vendor backfill", "--awaits", "vendor support", "awaits"),
    ], ids=["D-why", "B-awaits"])
    def test_should_offer_the_missing_required_field_and_save_when_obeyed(
        self, tmp_repo, query_mod, note_type, headline, flag, value, attr
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc, out, err = run_gitmem_script(
            ["note", note_type, "--zones", _ZONE1, _ZONE2, headline,
             "--description", "first try", "--searched", _SEARCHED], cwd=tmp_repo,
        )
        assert rc != 0, f"must bounce for the missing {flag}: {out!r}"
        relaunches = _relaunch_lines(out + err, "gitmem note ")
        assert len(relaunches) == 1, f"{out + err!r}"

        obeyed = _fill_holes(shlex.split(relaunches[0])[1:],
                             {flag: value, "--description": "second try"})
        rc2, out2, err2 = run_gitmem_script(obeyed, cwd=tmp_repo)

        assert rc2 == 0, f"obeying the relaunch bounced again: {out2!r} {err2!r}"
        note = _read_back(tmp_repo, query_mod, extract_note_id(out2))
        assert getattr(note, attr) == value
        assert note.description == "second try"
        assert note.searched == _SEARCHED


# ── 6. a multi-line --searched on a rule is folded ───────────────────────


class TestRuleSearchedFolded:
    """Bug caught: a rule's `--searched` written with raw line breaks --
    its second line lands in the commit body as a bare line (here one that
    looks like a `Why:` field)."""

    def test_should_fold_each_extra_line_with_a_leading_space(self, tmp_repo):
        rc, out, err = run_gitmem_script(
            ["rule", _RULE_OTHER, "--kind", "user", "--quote", "none",
             "--searched", "line one\nWhy: line two"], cwd=tmp_repo,
        )
        assert rc == 0, f"{out!r} {err!r}"

        body = _message_of(tmp_repo).split("\n\n", 1)[1]

        assert body == "Searched: line one\n Why: line two"


# ── 7. the hook ──────────────────────────────────────────────────────────


_CONTINUED_NOTE = (
    f'gitmem note D --zones {_ZONE1} {_ZONE2} "retire the internal wiki" \\\n'
    '  --why "one source of truth" \\\n'
    '  --description "nobody updates it"'
)


class TestCustomsLineContinuation:
    """Bug caught (SEC-LOW-001): shlex turns `\\`+newline into a lone "\\n"
    token -- the hook's relaunch then carries a literal line break (obeyed,
    it bounces), and a `--searched` placed after a continuation reads as
    unanswered."""

    def test_should_offer_a_one_line_relaunch_that_saves_when_obeyed(
        self, tmp_repo, query_mod
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        seed_config_json(tmp_repo, customs_enabled=True)

        decision = _run_customs(tmp_repo, _CONTINUED_NOTE)

        assert decision.get("decision") == "block", f"{decision!r}"
        relaunches = _relaunch_lines(decision["reason"], "gitmem note ")
        assert len(relaunches) == 1, f"{decision['reason']!r}"
        tokens = shlex.split(relaunches[0])
        assert all("\n" not in t for t in tokens), f"literal newline in {tokens!r}"
        i = tokens.index("--searched")
        tokens[i + 1] = _SEARCHED

        rc, out, err = run_gitmem_script(tokens[1:], cwd=tmp_repo)

        assert rc == 0, f"obeying the hook's relaunch failed: {out!r} {err!r}"
        note = _read_back(tmp_repo, query_mod, extract_note_id(out))
        assert (note.why, note.description, note.searched) == (
            "one source of truth", "nobody updates it", _SEARCHED)

    def test_should_count_a_searched_given_after_a_continuation(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = _CONTINUED_NOTE + ' \\\n  --searched \\\n  "wiki: nada escrito"'

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "approve", f"{decision!r}"


class TestCustomsAmendBounce:
    """Bug caught: the `--amend` bounce suggesting a `gitmem note ...
    --replaces` without `--searched` -- obeyed, it bounces on D-098."""

    def test_should_suggest_a_replace_that_carries_searched(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)

        decision = _run_customs(tmp_repo, 'git commit --amend -m "fix the note"')

        assert decision.get("decision") == "block", f"{decision!r}"
        suggestions = [r.split("  #")[0] for r in
                       _relaunch_lines(decision["reason"], "gitmem note ")]
        assert len(suggestions) == 1, f"{decision['reason']!r}"
        tokens = shlex.split(suggestions[0])
        assert "--replaces" in tokens
        assert "--searched" in tokens
        assert tokens[tokens.index("--searched") + 1].strip(), f"empty --searched in {tokens!r}"
