# NOT lifted. Written for unmassk-trading by Dante, 2026-08-27.
#
# WHY THIS FILE EXISTS, next to a suite that already has 100% branch coverage:
# test_position_sizer.py came from the SAME repository as position_sizer.py, so
# every number in it was produced by the code it is checking. That proves the
# formula was implemented; it cannot prove the formula is right. This project's
# rule is that a test earns its place only when it compares two things written
# separately, so every expected value below was computed by hand from the
# definition in references/risk-and-sizing.md BEFORE the script was run, with
# the arithmetic shown in the comment so a reader can check it without running
# anything. Where the two disagreed, the code was reported -- never the hand
# figure adjusted.
#
# The definition being cross-checked (references/risk-and-sizing.md):
#     risk_amount   = account * risk_pct / 100
#     stop_distance = entry - stop                (per unit)
#     size          = FLOOR(risk_amount / stop_distance)   <- down, never up
#     position      = size * entry
#     actual_risk   = size * stop_distance
#     actual_pct    = actual_risk / account * 100
# FLOOR is to whole units without --fractional, and to --share-precision
# decimals with it.
#
# Everything here goes through the CLI -- the path a person actually uses --
# and reads the JSON report the script writes, never an internal function.
# Nothing is written inside the repository: the script is invoked by absolute
# path with cwd and --output-dir under pytest's tmp_path.
"""Independent cross-check of position_sizer.py's sizing arithmetic."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "position_sizer.py"


def run_sizer(tmp_path, *args):
    """Run position_sizer.py through its CLI and return (completed, report)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    reports = sorted(out_dir.glob("position_sizer_*.json"))
    report = json.loads(reports[-1].read_text(encoding="utf-8")) if reports else None
    return completed, report


def cli_args(case):
    args = [
        "--account-size", str(case["account"]),
        "--entry", str(case["entry"]),
        "--stop", str(case["stop"]),
        "--risk-pct", str(case["risk_pct"]),
    ]
    args += case.get("extra", [])
    return args


# ─── The hand-computed cases ─────────────────────────────────────────────────
#
# Every "size", "position", "risk" and "pct" below was computed from the
# definition above using exact rational arithmetic, not by running the script.

HAND_CASES = [
    # C1 -- the first example this plugin's own documentation quotes.
    #   risk_amount = 500 * 1.0/100                     = 5
    #   distance    = 67517 - 63000                     = 4517
    #   raw         = 5 / 4517                          = 0.00110692937791...
    #   floor to 8 dp                                   = 0.00110692
    #   position    = 0.00110692 * 67517                = 74.73591764   -> 74.74
    #   risk        = 0.00110692 * 4517                 = 4.99995764    -> 5.00
    #   pct         = 4.99995764 / 500 * 100            = 0.99999152    -> 1.0
    dict(id="C1_doc_example_wide_stop", account=500, entry=67517, stop=63000,
         risk_pct=1.0, extra=["--fractional", "--share-precision", "8"],
         size=0.00110692, position=74.74, risk=5.00, pct=1.0),

    # C2 -- the second documented example: a very tight stop, and the position
    # that comes out larger than the whole account.
    #   risk_amount = 5 ; distance = 67517 - 67010      = 507
    #   raw         = 5 / 507                           = 0.00986193293886...
    #   floor to 8 dp                                   = 0.00986193
    #   position    = 0.00986193 * 67517                = 665.84792781 -> 665.85
    #   risk        = 0.00986193 * 507                  = 4.99999851   -> 5.00
    #   pct         = 4.99999851 / 500 * 100            = 0.99999970   -> 1.0
    dict(id="C2_doc_example_tight_stop", account=500, entry=67517, stop=67010,
         risk_pct=1.0, extra=["--fractional", "--share-precision", "8"],
         size=0.00986193, position=665.85, risk=5.00, pct=1.0),

    # C3 -- whole units, division lands exactly on the boundary.
    #   risk_amount = 10000 * 2.0/100 = 200 ; distance = 100 - 90 = 10
    #   raw = 200 / 10 = 20 exactly    -> 20 shares (nothing to round)
    #   position = 20 * 100 = 2000 ; risk = 20 * 10 = 200 ; pct = 2.0
    dict(id="C3_whole_units_exact", account=10000, entry=100, stop=90,
         risk_pct=2.0, extra=[],
         size=20, position=2000.00, risk=200.00, pct=2.0),

    # C4 -- whole units, fraction .666 so rounding DOWN is observable:
    # rounding to nearest would give 17 shares and risk 102 (1.02%), i.e. MORE
    # than the 1% asked for.
    #   risk_amount = 10000 * 1.0/100 = 100 ; distance = 50 - 44 = 6
    #   raw = 100 / 6 = 16.6666...     -> floor 16   (nearest would be 17)
    #   position = 16 * 50 = 800 ; risk = 16 * 6 = 96 ; pct = 96/10000*100 = 0.96
    dict(id="C4_whole_units_floor_not_nearest", account=10000, entry=50, stop=44,
         risk_pct=1.0, extra=[],
         size=16, position=800.00, risk=96.00, pct=0.96),

    # C5 -- fractional at 2 dp, fraction .857 so rounding DOWN is observable:
    # nearest would give 1.43 and risk 10.01 -- over the budget.
    #   risk_amount = 1000 * 1.0/100 = 10 ; distance = 100 - 93 = 7
    #   raw = 10 / 7 = 1.42857142...   -> floor 1.42  (nearest would be 1.43)
    #   position = 1.42 * 100 = 142 ; risk = 1.42 * 7 = 9.94 ; pct = 0.994 -> 0.99
    dict(id="C5_fractional_2dp_floor_not_nearest", account=1000, entry=100, stop=93,
         risk_pct=1.0, extra=["--fractional", "--share-precision", "2"],
         size=1.42, position=142.00, risk=9.94, pct=0.99),

    # C6 -- 0.1% stop distance: the position is twenty times the account.
    #   risk_amount = 1000 * 2.0/100 = 20 ; distance = 50000 - 49950 = 50
    #   raw = 20 / 50 = 0.4 exactly
    #   position = 0.4 * 50000 = 20000 ; risk = 0.4 * 50 = 20 ; pct = 2.0
    dict(id="C6_tight_stop_position_20x_account", account=1000, entry=50000, stop=49950,
         risk_pct=2.0, extra=["--fractional", "--share-precision", "8"],
         size=0.4, position=20000.00, risk=20.00, pct=2.0),

    # C7 -- C1's inputs WITHOUT --fractional: the documented zero trap.
    #   raw = 0.00110692...            -> floor to whole units = 0
    #   position = 0 ; risk = 0 ; pct = 0
    dict(id="C7_sub_one_unit_without_fractional_is_zero", account=500, entry=67517,
         stop=63000, risk_pct=1.0, extra=[],
         size=0, position=0.00, risk=0.00, pct=0.0),

    # C8 -- C1's inputs at 4 dp instead of 8: coarser precision loses risk budget.
    #   raw = 0.00110692937791...      -> floor to 4 dp = 0.0011
    #   position = 0.0011 * 67517 = 74.2687        -> 74.27
    #   risk     = 0.0011 * 4517  = 4.9687         -> 4.97
    #   pct      = 4.9687 / 500 * 100 = 0.99374    -> 0.99
    dict(id="C8_share_precision_4", account=500, entry=67517, stop=63000,
         risk_pct=1.0, extra=["--fractional", "--share-precision", "4"],
         size=0.0011, position=74.27, risk=4.97, pct=0.99),

    # C9 -- big account, sub-1% risk, prices with cents.
    #   risk_amount = 250000 * 0.5/100 = 1250 ; distance = 1234.56 - 1200 = 34.56
    #   raw = 1250 / 34.56 = 36.16898148...  -> floor 36 whole shares
    #   position = 36 * 1234.56 = 44444.16
    #   risk = 36 * 34.56 = 1244.16 ; pct = 1244.16/250000*100 = 0.497664 -> 0.5
    dict(id="C9_large_account_half_percent", account=250000, entry=1234.56, stop=1200,
         risk_pct=0.5, extra=[],
         size=36, position=44444.16, risk=1244.16, pct=0.5),

    # C10 -- fractional, exact division, cheap asset.
    #   risk_amount = 2500 * 2.0/100 = 50 ; distance = 3.75 - 3.50 = 0.25
    #   raw = 50 / 0.25 = 200 exactly
    #   position = 200 * 3.75 = 750 ; risk = 200 * 0.25 = 50 ; pct = 2.0
    dict(id="C10_fractional_exact_division", account=2500, entry=3.75, stop=3.50,
         risk_pct=2.0, extra=["--fractional", "--share-precision", "8"],
         size=200.0, position=750.00, risk=50.00, pct=2.0),

    # C11 -- account and risk-pct both fractional, price in cents.
    #   risk_amount = 137.5 * 1.5/100 = 2.0625 ; distance = 9.87 - 9.12 = 0.75
    #   raw = 2.0625 / 0.75 = 2.75 exactly
    #   position = 2.75 * 9.87 = 27.1425 -> 27.14
    #   risk = 2.75 * 0.75 = 2.0625 -> 2.06 ; pct = 2.0625/137.5*100 = 1.5
    dict(id="C11_fractional_account_and_risk_pct", account=137.5, entry=9.87, stop=9.12,
         risk_pct=1.5, extra=["--fractional", "--share-precision", "8"],
         size=2.75, position=27.14, risk=2.06, pct=1.5),

    # C12 -- sub-euro asset with a 0.0001 stop: 10000 units, 50x the account.
    #   risk_amount = 100 * 1.0/100 = 1 ; distance = 0.5 - 0.4999 = 0.0001
    #   raw = 1 / 0.0001 = 10000 exactly
    #   position = 10000 * 0.5 = 5000 ; risk = 10000 * 0.0001 = 1 ; pct = 1.0
    dict(id="C12_penny_asset_tiny_stop", account=100, entry=0.5, stop=0.4999,
         risk_pct=1.0, extra=["--fractional", "--share-precision", "8"],
         size=10000.0, position=5000.00, risk=1.00, pct=1.0),

    # C13 -- 6 dp precision, non-terminating division, rounding DOWN observable:
    # nearest would give 0.318408.
    #   risk_amount = 800 * 2.0/100 = 16 ; distance = 2450.50 - 2400.25 = 50.25
    #   raw = 16 / 50.25 = 0.31840796019900...  -> floor 6 dp = 0.318407
    #   position = 0.318407 * 2450.50 = 780.2563535 -> 780.26
    #   risk = 0.318407 * 50.25 = 15.99995175 -> 16.00 ; pct = 1.99999396 -> 2.0
    dict(id="C13_fractional_6dp_floor_not_nearest", account=800, entry=2450.50,
         stop=2400.25, risk_pct=2.0, extra=["--fractional", "--share-precision", "6"],
         size=0.318407, position=780.26, risk=16.00, pct=2.0),

    # C14 -- C2 with the documented remedy, --max-position-pct 20, which binds:
    # the risk-based size (0.00986193) is cut to what 20% of the account buys.
    #   cap_raw = 500 * 20/100 / 67517 = 0.00148110846...  -> floor 8 dp = 0.0014811
    #   final = min(0.00986193, 0.0014811) = 0.0014811
    #   position = 0.0014811 * 67517 = 99.9994287 -> 100.00
    #   risk = 0.0014811 * 507 = 0.7509177 -> 0.75 ; pct = 0.15018354 -> 0.15
    dict(id="C14_max_position_pct_binds", account=500, entry=67517, stop=67010,
         risk_pct=1.0,
         extra=["--fractional", "--share-precision", "8", "--max-position-pct", "20"],
         size=0.0014811, position=100.00, risk=0.75, pct=0.15),
]

CASE_IDS = [c["id"] for c in HAND_CASES]


@pytest.mark.parametrize("case", HAND_CASES, ids=CASE_IDS)
def test_size_matches_the_hand_computed_size(case, tmp_path):
    """The unit count the script hands the user equals the one computed by hand."""
    completed, report = run_sizer(tmp_path, *cli_args(case))

    assert completed.returncode == 0, completed.stderr
    assert report["final_recommended_shares"] == case["size"]


@pytest.mark.parametrize("case", HAND_CASES, ids=CASE_IDS)
def test_money_numbers_match_the_hand_computed_ones(case, tmp_path):
    """Position value, risk in currency and risk as a percentage all agree."""
    completed, report = run_sizer(tmp_path, *cli_args(case))

    assert completed.returncode == 0, completed.stderr
    assert report["final_position_value"] == case["position"]
    assert report["final_risk_dollars"] == case["risk"]
    assert report["final_risk_pct"] == case["pct"]


# ─── The two examples the documentation quotes, pinned on stdout ─────────────


def test_documented_example_wide_stop_prints_the_documented_lines(tmp_path):
    """references/risk-and-sizing.md quotes these three lines verbatim.

    Hand check: 5 / 4517 = 0.00110692937... -> 0.00110692 units,
    x 67517 = 74.74 of position, x 4517 = 5.00 of risk = 1.0% of 500.
    """
    completed, _ = run_sizer(
        tmp_path,
        "--account-size", "500", "--entry", "67517", "--stop", "63000",
        "--risk-pct", "1.0", "--fractional", "--share-precision", "8",
    )

    assert completed.returncode == 0, completed.stderr
    assert "Final: 0.00110692 shares @ $67517.0" in completed.stdout
    assert "Position: $74.74" in completed.stdout
    assert "Risk: $5.00 (1.0%)" in completed.stdout


def test_documented_example_tight_stop_prints_the_documented_lines(tmp_path):
    """Same trade, stop at 67010: 5 / 507 = 0.00986193293... -> 0.00986193 units.

    x 67517 = 665.85 of position on a 500 account -- larger than the account,
    which the documentation records as happening silently.
    """
    completed, report = run_sizer(
        tmp_path,
        "--account-size", "500", "--entry", "67517", "--stop", "67010",
        "--risk-pct", "1.0", "--fractional", "--share-precision", "8",
    )

    assert completed.returncode == 0, completed.stderr
    assert "Final: 0.00986193 shares @ $67517.0" in completed.stdout
    assert "Position: $665.85" in completed.stdout
    assert "Risk: $5.00 (1.0%)" in completed.stdout
    assert report["final_position_value"] > report["parameters"]["account_size"]


def test_a_position_larger_than_the_account_is_still_exit_zero_and_unflagged(tmp_path):
    """665.85 bought on a 500 account: no warning anywhere, exit 0.

    This is a documented trap, not an accident -- pinned so that a future
    change that starts warning cannot land without this test going red and
    the documentation being updated with it.
    """
    completed, report = run_sizer(
        tmp_path,
        "--account-size", "500", "--entry", "67517", "--stop", "67010",
        "--risk-pct", "1.0", "--fractional", "--share-precision", "8",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "warn" not in completed.stdout.lower()
    assert report["binding_constraint"] is None
    assert report["constraints_applied"] == []


# ─── Rounding direction: DOWN, never to nearest ──────────────────────────────
#
# Each of these four picks inputs whose exact division does NOT land on the
# precision boundary AND whose next digit is >= 5, so floor and round-to-nearest
# give different answers. Rounding up would risk more money than asked for, so
# the wrong direction is a silent overspend, not a cosmetic difference.


def test_rounding_is_down_at_eight_decimals(tmp_path):
    """5 / 4517 = 0.001106929377... -> floor 0.00110692, nearest would be 0.00110693."""
    _, report = run_sizer(
        tmp_path,
        "--account-size", "500", "--entry", "67517", "--stop", "63000",
        "--risk-pct", "1.0", "--fractional", "--share-precision", "8",
    )

    assert report["final_recommended_shares"] == 0.00110692
    assert report["final_recommended_shares"] != 0.00110693
    assert report["final_risk_dollars"] <= 5.00


def test_rounding_is_down_at_six_decimals(tmp_path):
    """16 / 50.25 = 0.318407960199... -> floor 0.318407, nearest would be 0.318408."""
    _, report = run_sizer(
        tmp_path,
        "--account-size", "800", "--entry", "2450.50", "--stop", "2400.25",
        "--risk-pct", "2.0", "--fractional", "--share-precision", "6",
    )

    assert report["final_recommended_shares"] == 0.318407
    assert report["final_recommended_shares"] != 0.318408
    assert report["final_risk_dollars"] <= 16.00


def test_rounding_is_down_at_two_decimals(tmp_path):
    """10 / 7 = 1.428571... -> floor 1.42, nearest would be 1.43 (risk 10.01 > 10)."""
    _, report = run_sizer(
        tmp_path,
        "--account-size", "1000", "--entry", "100", "--stop", "93",
        "--risk-pct", "1.0", "--fractional", "--share-precision", "2",
    )

    assert report["final_recommended_shares"] == 1.42
    assert report["final_recommended_shares"] != 1.43
    assert report["final_risk_dollars"] == 9.94


def test_rounding_is_down_on_whole_units(tmp_path):
    """100 / 6 = 16.666... -> floor 16, nearest would be 17 (risk 102 = 1.02%)."""
    _, report = run_sizer(
        tmp_path,
        "--account-size", "10000", "--entry", "50", "--stop", "44",
        "--risk-pct", "1.0",
    )

    assert report["final_recommended_shares"] == 16
    assert report["final_recommended_shares"] != 17
    assert report["final_risk_dollars"] == 96.00
    assert report["final_risk_pct"] == 0.96


@pytest.mark.parametrize(
    "account, entry, stop, risk_pct, extra",
    [
        (500, 67517, 63000, 1.0, ["--fractional", "--share-precision", "8"]),
        (800, 2450.50, 2400.25, 2.0, ["--fractional", "--share-precision", "6"]),
        (1000, 100, 93, 1.0, ["--fractional", "--share-precision", "2"]),
        (10000, 50, 44, 1.0, []),
        (250000, 1234.56, 1200, 0.5, []),
    ],
    ids=["8dp", "6dp", "2dp", "whole_units", "whole_units_cents"],
)
def test_the_realised_risk_never_exceeds_the_requested_budget(
    account, entry, stop, risk_pct, extra, tmp_path
):
    """The consequence of flooring, stated as the property that matters.

    Requested budget = account * risk_pct / 100. Whatever the rounding, the
    money actually at risk must land at or below it -- never above.
    """
    budget = account * risk_pct / 100
    _, report = run_sizer(
        tmp_path,
        "--account-size", str(account), "--entry", str(entry), "--stop", str(stop),
        "--risk-pct", str(risk_pct), *extra,
    )

    assert report["final_risk_dollars"] <= budget


# ─── The zero-share trap ─────────────────────────────────────────────────────


def test_sub_one_unit_without_fractional_returns_zero_shares_and_exit_zero(tmp_path):
    """500 account, 67517 entry, 63000 stop, no --fractional.

    Hand check: 5 / 4517 = 0.0011 units, floored to whole units = 0. The script
    reports a plausible-looking zero, says nothing about it, and exits 0. That
    is the documented trap: pinned here so it cannot change in silence, in
    either direction -- a future error message is a documentation change too.
    """
    completed, report = run_sizer(
        tmp_path,
        "--account-size", "500", "--entry", "67517", "--stop", "63000",
        "--risk-pct", "1.0",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "Final: 0 shares @ $67517.0" in completed.stdout
    assert "Position: $0.00" in completed.stdout
    assert "Risk: $0.00 (0.0%)" in completed.stdout
    assert report["final_recommended_shares"] == 0


def test_the_fractional_flag_is_the_only_difference_between_zero_and_a_position(tmp_path):
    """Identical inputs, one flag apart: 0 units versus 0.00110692 units.

    Both hand-computed from the same raw 5 / 4517 = 0.001106929...: floored to
    whole units it is 0, floored to 8 decimals it is 0.00110692.
    """
    base = [
        "--account-size", "500", "--entry", "67517", "--stop", "63000",
        "--risk-pct", "1.0",
    ]
    _, whole = run_sizer(tmp_path / "whole", *base)
    _, frac = run_sizer(tmp_path / "frac", *base, "--fractional", "--share-precision", "8")

    assert whole["final_recommended_shares"] == 0
    assert whole["final_risk_dollars"] == 0.00
    assert frac["final_recommended_shares"] == 0.00110692
    assert frac["final_risk_dollars"] == 5.00


def test_share_precision_alone_changes_the_size_and_the_risk_taken(tmp_path):
    """Same trade at 4 dp and at 8 dp: 0.0011 versus 0.00110692.

    Hand-computed from 5 / 4517 = 0.001106929377...: floored to 4 decimals it
    is 0.0011 (risk 4.97), floored to 8 it is 0.00110692 (risk 5.00). Coarser
    precision leaves budget unused; it never overspends.
    """
    base = [
        "--account-size", "500", "--entry", "67517", "--stop", "63000",
        "--risk-pct", "1.0", "--fractional", "--share-precision",
    ]
    _, four = run_sizer(tmp_path / "p4", *base, "4")
    _, eight = run_sizer(tmp_path / "p8", *base, "8")

    assert four["final_recommended_shares"] == 0.0011
    assert four["final_risk_dollars"] == 4.97
    assert eight["final_recommended_shares"] == 0.00110692
    assert eight["final_risk_dollars"] == 5.00


def test_the_max_position_cap_binds_and_is_named(tmp_path):
    """--max-position-pct 20 on the tight-stop trade: 665.85 becomes 100.00.

    Hand check: 500 * 20/100 / 67517 = 0.001481108... -> floor 8 dp = 0.0014811,
    which is below the risk-based 0.00986193, so it wins. 0.0014811 * 67517 =
    99.9994287 -> 100.00, and the risk drops to 0.0014811 * 507 = 0.75 (0.15%).
    """
    _, report = run_sizer(
        tmp_path,
        "--account-size", "500", "--entry", "67517", "--stop", "67010",
        "--risk-pct", "1.0", "--fractional", "--share-precision", "8",
        "--max-position-pct", "20",
    )

    assert report["final_recommended_shares"] == 0.0014811
    assert report["final_position_value"] == 100.00
    assert report["final_risk_dollars"] == 0.75
    assert report["final_risk_pct"] == 0.15
    assert report["binding_constraint"] == "max_position_pct"
