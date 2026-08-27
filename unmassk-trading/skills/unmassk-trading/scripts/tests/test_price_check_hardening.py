"""Hardening sweep for price_check.py -- the exhaustive pass, after the code.

``test_price_check.py`` is the acceptance contract: written before there was an
implementation, at the granularity of "what does done mean". It stays as it is.

This file is the second entry: every function, every branch, every error path,
measured against the real code rather than against an idea of it. Two gaps the
review named are here too -- the slashless ``--pair BTCEUR`` form, and the
guards on ``--max-spread-bps`` / ``--max-age-seconds``, which are the most
likely thing a user ever touches and the only thing between a typo and a check
that silently never fires.

Nothing here reaches the network: the transport (``http_get``), the clock and
the fetchers are all injectable, and the one function that does open a socket
(``_http_get``) is exercised against a monkeypatched ``urlopen``. The live
round-trips live in the contract file and stay there.

Two behaviours are pinned deliberately as they ARE, not as one might wish:
  * a frozen quote delivered instantly reads as fresh (see the test named for
    it) -- receipt time is not price time, and the script cannot see that;
  * zero venues answering is SINGLE_SOURCE, with a reason that says so.
Both are named in full so a future change to either is a deliberate edit of a
test, never a silent drift.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from pathlib import Path

import pytest

import price_check as pc

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
PAIR = "BTC/EUR"
SCRIPT = Path(__file__).resolve().parents[1] / "price_check.py"

KRAKEN_BODY = json.dumps({"error": [], "result": {"XXBTZEUR": {"c": ["68644.20000", "0.00002"]}}})
BINANCE_BODY = json.dumps({"symbol": "BTCEUR", "price": "68656.96000000"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def http_returning(body):
    """Injectable transport that records every (url, timeout) it was handed."""

    def http_get(url, timeout=None):
        http_get.calls.append((url, timeout))
        return body

    http_get.calls = []
    return http_get


def http_raising(exc):
    def http_get(url, timeout=None):
        http_get.calls.append((url, timeout))
        raise exc

    http_get.calls = []
    return http_get


def quote(source="kraken", price="68644.20000", fetched_at=NOW):
    return pc.Quote(
        source=source,
        price=None if price is None else Decimal(price),
        fetched_at=fetched_at,
    )


def fetcher_of(value):
    def fetch(pair):
        fetch.calls.append(pair)
        if isinstance(value, Exception):
            raise value
        return value

    fetch.calls = []
    return fetch


def report_for(kraken, binance, **kwargs):
    kwargs.setdefault("now", NOW)
    return pc.check_prices(
        pair=PAIR,
        fetchers={"kraken": fetcher_of(kraken), "binance": fetcher_of(binance)},
        **kwargs,
    )


class NoOffsetTZ(tzinfo):
    """A tzinfo that admits it does not know its offset -- legal, and useless
    for computing an age. datetime.utcoffset() returning None is a real state,
    not a lab case: it is what a partially built tzinfo hands back."""

    def utcoffset(self, dt):
        return None

    def tzname(self, dt):
        return "UNKNOWN"

    def dst(self, dt):
        return None


# ===========================================================================
# 1. _utc_now / _http_get -- the two functions that touch the outside world
# ===========================================================================
def test_utc_now_is_timezone_aware_and_in_utc():
    stamp = pc._utc_now()
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timedelta(0)


def test_http_get_sends_a_named_user_agent_and_forwards_the_timeout(monkeypatch):
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    body = pc._http_get("https://example.invalid/x", timeout=3)
    assert body == '{"ok": true}'
    assert seen["url"] == "https://example.invalid/x"
    assert seen["timeout"] == 3
    assert "unmassk-trading" in "".join(seen["headers"].values())


def test_http_get_decodes_the_body_as_utf8(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return '{"msg":"café ✓"}'.encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout=None: FakeResponse())
    assert json.loads(pc._http_get("https://example.invalid/x"))["msg"] == "café ✓"


def test_http_get_default_timeout_is_the_declared_one(monkeypatch):
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout=None):
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    pc._http_get("https://example.invalid/x")
    assert seen["timeout"] == pc.DEFAULT_TIMEOUT_SECONDS


# ===========================================================================
# 2. _read_body -- every transport failure becomes a named SourceError
# ===========================================================================
@pytest.mark.parametrize(
    "exc,token",
    [
        (urllib.error.HTTPError("http://x", 400, "Bad Request", {}, None), "http 400"),
        (urllib.error.HTTPError("http://x", 429, "Too Many Requests", {}, None), "429"),
        (urllib.error.HTTPError("http://x", 503, "Service Unavailable", {}, None), "503"),
        (TimeoutError("timed out"), "timeout"),
        (urllib.error.URLError(TimeoutError("timed out")), "timeout"),
        (urllib.error.URLError("timed out"), "timeout"),
        (urllib.error.URLError("name resolution failed"), "transport failure"),
        (ConnectionResetError("connection reset by peer"), "transport failure"),
        (OSError("network is unreachable"), "transport failure"),
    ],
    ids=[
        "http-400",
        "http-429",
        "http-503",
        "timeout-error",
        "urlerror-wrapping-timeout",
        "urlerror-saying-timed-out",
        "urlerror-other",
        "connection-reset",
        "os-error",
    ],
)
def test_every_transport_failure_is_a_named_source_error(exc, token):
    with pytest.raises(pc.SourceError) as caught:
        pc._read_body("kraken", "http://x", http_raising(exc), 8)
    assert caught.value.source == "kraken"
    assert token in caught.value.reason.lower()


def test_a_transport_failure_keeps_the_original_exception_chained():
    """__cause__ preserved: the reason string is for the user, the chain is for
    whoever has to debug it."""
    original = TimeoutError("timed out")
    with pytest.raises(pc.SourceError) as caught:
        pc._read_body("binance", "http://x", http_raising(original), 8)
    assert caught.value.__cause__ is original


def test_the_timeout_message_states_the_limit_that_was_actually_used():
    with pytest.raises(pc.SourceError) as caught:
        pc._read_body("kraken", "http://x", http_raising(TimeoutError()), 2.5)
    assert "2.5" in caught.value.reason


def test_read_body_returns_the_body_untouched_on_success():
    http = http_returning(KRAKEN_BODY)
    assert pc._read_body("kraken", "http://x", http, 8) == KRAKEN_BODY
    assert http.calls == [("http://x", 8)]


# ===========================================================================
# 3. _parse_json / _price_from
# ===========================================================================
@pytest.mark.parametrize(
    "body,token",
    [
        ("", "malformed"),
        ("   ", "malformed"),
        ('{"error":[],"result":{"XXBTZEUR":{"c":["686', "malformed"),
        ("<html>503 backend down</html>", "malformed"),
        (None, "malformed"),
    ],
    ids=["empty", "whitespace", "truncated", "html-error-page", "none"],
)
def test_an_unparseable_body_is_named_malformed(body, token):
    with pytest.raises(pc.SourceError) as caught:
        pc._parse_json("kraken", body)
    assert token in caught.value.reason.lower()


@pytest.mark.parametrize(
    "body", ["[1,2]", '"just a string"', "42", "null", "true"],
    ids=["list", "string", "number", "null", "bool"],
)
def test_a_json_document_that_is_not_an_object_is_refused(body):
    with pytest.raises(pc.SourceError) as caught:
        pc._parse_json("binance", body)
    assert "not a json object" in caught.value.reason.lower()


def test_parse_json_returns_the_mapping_on_success():
    assert pc._parse_json("binance", '{"price":"1.5"}') == {"price": "1.5"}


@pytest.mark.parametrize(
    "raw,token",
    [
        (None, "unusable"),
        (0, "unusable"),
        (1.5, "unusable"),
        (True, "unusable"),
        ([], "unusable"),
        ({}, "unusable"),
        ("", "unusable"),
        ("   ", "unusable"),
        ("abc", "unreadable"),
        ("1,5", "unreadable"),
        ("1.2.3", "unreadable"),
        ("NaN", "not a positive number"),
        ("Infinity", "not a positive number"),
        ("-Infinity", "not a positive number"),
        ("0", "not a positive number"),
        ("0.00000000", "not a positive number"),
        ("-1.5", "not a positive number"),
    ],
    ids=[
        "none", "int", "float", "bool", "list", "dict", "empty", "blank",
        "letters", "comma-decimal", "two-dots", "nan", "inf", "neg-inf",
        "zero", "padded-zero", "negative",
    ],
)
def test_a_price_that_is_not_a_positive_decimal_string_is_a_named_failure(raw, token):
    """A number that arrives as a JSON float has already been through a binary
    float before this code ever saw it, so it is refused rather than trusted."""
    with pytest.raises(pc.SourceError) as caught:
        pc._price_from("kraken", raw, "c")
    assert token in caught.value.reason.lower()
    assert "c" in caught.value.reason


def test_a_price_keeps_every_digit_and_its_surrounding_whitespace_is_tolerated():
    assert pc._price_from("kraken", " 70123.456789012345678 ", "c") == Decimal(
        "70123.456789012345678"
    )
    assert str(pc._price_from("binance", "68656.96000000", "price")) == "68656.96000000"


# ===========================================================================
# 4. _split_pair and the symbol each venue is actually asked for
#    (review gap 1: the slashless form had no test)
# ===========================================================================
@pytest.mark.parametrize(
    "pair,expected",
    [
        ("BTC/EUR", ("BTC", "EUR")),
        ("BTCEUR", ("BTC", "EUR")),
        ("btc/eur", ("BTC", "EUR")),
        ("btceur", ("BTC", "EUR")),
        ("ETH/EUR", ("ETH", "EUR")),
        ("ETHEUR", ("ETH", "EUR")),
        ("BTC/USDT", ("BTC", "USDT")),
        ("BTC/USD", ("BTC", "USD")),
    ],
    ids=[
        "slashed", "slashless", "lowercase-slashed", "lowercase-slashless",
        "eth-slashed", "eth-slashless", "four-letter-quote", "usd",
    ],
)
def test_the_pair_splits_the_same_with_or_without_the_slash(pair, expected):
    assert pc._split_pair(pair) == expected


@pytest.mark.parametrize(
    "pair,kraken_symbol,binance_symbol",
    [
        ("BTC/EUR", "XBTEUR", "BTCEUR"),
        ("BTCEUR", "XBTEUR", "BTCEUR"),
        ("btc/eur", "XBTEUR", "BTCEUR"),
        ("btceur", "XBTEUR", "BTCEUR"),
        ("ETH/EUR", "ETHEUR", "ETHEUR"),
        ("ETHEUR", "ETHEUR", "ETHEUR"),
        ("BTC/USDT", "XBTUSDT", "BTCUSDT"),
    ],
    ids=["slashed", "slashless", "lower-slashed", "lower-slashless", "eth", "eth-slashless", "usdt"],
)
def test_each_venue_is_asked_for_its_own_spelling_of_the_pair(
    pair, kraken_symbol, binance_symbol
):
    """BTC/EUR -> Kraken XBTEUR -> response key XXBTZEUR: three spellings of
    one pair, and the whole chain is pinned here."""
    kraken_http = http_returning(KRAKEN_BODY)
    binance_http = http_returning(BINANCE_BODY)
    pc.fetch_kraken(pair, http_get=kraken_http, clock=lambda: NOW)
    pc.fetch_binance(pair, http_get=binance_http, clock=lambda: NOW)
    assert kraken_http.calls[0][0] == f"{pc.KRAKEN_URL}?pair={kraken_symbol}"
    assert binance_http.calls[0][0] == f"{pc.BINANCE_URL}?symbol={binance_symbol}"


def test_the_slashless_form_does_not_reach_the_xbt_alias_for_a_four_letter_quote():
    """BTCUSDT splits as BTCU/SDT, so the BTC->XBT alias never fires and Kraken
    is asked for BTCUSDT. It fails loudly at the venue rather than quoting the
    wrong thing -- pinned so the asymmetry is a known limit, not a surprise.
    Written with a slash (BTC/USDT) it resolves correctly, as the test above
    shows."""
    http = http_returning(KRAKEN_BODY)
    pc.fetch_kraken("BTCUSDT", http_get=http, clock=lambda: NOW)
    assert http.calls[0][0].endswith("pair=BTCUSDT")
    assert "XBT" not in http.calls[0][0]


@pytest.mark.parametrize("pair", ["", "EUR", "/", "/EUR", "BTC/"], ids=["empty", "three-letters", "slash-only", "no-base", "no-quote"])
def test_a_pair_that_cannot_be_split_still_ends_as_a_named_venue_failure(pair):
    """There is no client-side whitelist of pairs on purpose: the venue is the
    authority on what it lists. What matters is that a nonsense pair produces a
    named refusal and never a price."""
    http = http_returning(json.dumps({"error": ["EQuery:Unknown asset pair"]}))
    with pytest.raises(pc.SourceError) as caught:
        pc.fetch_kraken(pair, http_get=http, clock=lambda: NOW)
    assert "unknown asset pair" in caught.value.reason.lower()


def test_the_pair_is_url_encoded_never_pasted_raw():
    http = http_returning(KRAKEN_BODY)
    pc.fetch_kraken("BTC/EUR", http_get=http, clock=lambda: NOW)
    assert "/" not in http.calls[0][0].split("?", 1)[1]


# ===========================================================================
# 5. _kraken_price / _binance_price -- every shape the venues can send
# ===========================================================================
@pytest.mark.parametrize(
    "body,token",
    [
        (json.dumps({"error": ["EQuery:Unknown asset pair"]}), "unknown asset pair"),
        (json.dumps({"error": ["EGeneral:Temporary lockout"], "result": {}}), "lockout"),
        (json.dumps({"error": [{"code": 7}], "result": {}}), "venue error"),
        (json.dumps({"error": []}), "empty or missing result"),
        (json.dumps({"error": [], "result": {}}), "empty or missing result"),
        (json.dumps({"error": [], "result": None}), "empty or missing result"),
        (json.dumps({"error": [], "result": [1, 2]}), "empty or missing result"),
        (json.dumps({"error": [], "result": {"A": {"c": ["1"]}, "B": {"c": ["2"]}}}), "ambiguous"),
        (json.dumps({"error": [], "result": {"K": {}}}), "missing field 'c'"),
        (json.dumps({"error": [], "result": {"K": {"c": []}}}), "missing field 'c'"),
        (json.dumps({"error": [], "result": {"K": {"c": None}}}), "missing field 'c'"),
        (json.dumps({"error": [], "result": {"K": [1, 2]}}), "missing field 'c'"),
        (json.dumps({"error": [], "result": {"K": "not a mapping"}}), "missing field 'c'"),
        (json.dumps({"error": [], "result": {"K": {"c": ["0.00"]}}}), "not a positive number"),
        (json.dumps({"error": [], "result": {"K": {"c": [None]}}}), "missing field 'c'"),
        (json.dumps({"error": [], "result": {"K": {"c": [123.45]}}}), "unusable"),
    ],
    ids=[
        "200-with-error-array", "error-with-empty-result", "non-string-error",
        "no-result-key", "empty-result", "null-result", "result-not-a-mapping",
        "two-pairs", "no-c-field", "empty-c-list", "null-c", "entry-is-a-list",
        "entry-is-a-string", "zero-price", "c-list-holding-null", "c-holding-a-json-float",
    ],
)
def test_every_broken_kraken_shape_is_a_named_failure(body, token):
    with pytest.raises(pc.SourceError) as caught:
        pc._kraken_price(body)
    assert caught.value.source == "kraken"
    assert token in caught.value.reason.lower()


def test_kraken_accepts_the_last_price_as_a_bare_string_as_well_as_a_list():
    """Kraken sends c as [price, volume]; a bare string is accepted rather than
    crashed on, because the alternative is a hard failure on a usable price."""
    assert pc._kraken_price(json.dumps({"error": [], "result": {"K": {"c": "5.50"}}})) == Decimal(
        "5.50"
    )


def test_kraken_reads_the_price_from_the_response_key_whatever_it_is_called():
    for key in ("XXBTZEUR", "XBTEUR", "SOMETHINGELSE"):
        body = json.dumps({"error": [], "result": {key: {"c": ["68644.20000", "1"]}}})
        assert pc._kraken_price(body) == Decimal("68644.20000")


def test_kraken_ignores_the_rest_of_the_ticker_payload():
    body = json.dumps(
        {
            "error": [],
            "result": {
                "XXBTZEUR": {
                    "a": ["68644.30000", "1", "1.000"],
                    "b": ["68644.20000", "1", "1.000"],
                    "c": ["68644.20000", "0.00002398"],
                    "o": "67812.80000",
                }
            },
        }
    )
    assert pc._kraken_price(body) == Decimal("68644.20000")


@pytest.mark.parametrize(
    "body,token",
    [
        (json.dumps({"symbol": "BTCEUR"}), "missing field 'price'"),
        (json.dumps({}), "missing field 'price'"),
        (json.dumps({"price": None}), "unusable"),
        (json.dumps({"price": ""}), "unusable"),
        (json.dumps({"price": 68656.96}), "unusable"),
        (json.dumps({"price": "abc"}), "unreadable"),
        (json.dumps({"price": "0.00000000"}), "not a positive number"),
        (json.dumps({"price": "-1.00000000"}), "not a positive number"),
        (json.dumps({"code": -1121, "msg": "Invalid symbol."}), "missing field 'price'"),
    ],
    ids=[
        "no-price-key", "empty-object", "null-price", "empty-price",
        "json-float-price", "letters", "zero", "negative", "binance-error-object",
    ],
)
def test_every_broken_binance_shape_is_a_named_failure(body, token):
    with pytest.raises(pc.SourceError) as caught:
        pc._binance_price(body)
    assert caught.value.source == "binance"
    assert token in caught.value.reason.lower()


def test_binance_reads_the_price_it_was_sent():
    assert pc._binance_price(BINANCE_BODY) == Decimal("68656.96000000")


def test_both_fetchers_forward_the_timeout_they_were_given():
    kraken_http = http_returning(KRAKEN_BODY)
    binance_http = http_returning(BINANCE_BODY)
    pc.fetch_kraken(PAIR, http_get=kraken_http, clock=lambda: NOW, timeout=1.5)
    pc.fetch_binance(PAIR, http_get=binance_http, clock=lambda: NOW, timeout=1.5)
    assert kraken_http.calls[0][1] == 1.5
    assert binance_http.calls[0][1] == 1.5


@pytest.mark.parametrize("fetcher_name", ["fetch_kraken", "fetch_binance"])
def test_a_fetcher_stamps_receipt_time_after_the_body_arrives(fetcher_name):
    order = []
    bodies = {"fetch_kraken": KRAKEN_BODY, "fetch_binance": BINANCE_BODY}

    def http_get(url, timeout=None):
        order.append("http")
        return bodies[fetcher_name]

    def clock():
        order.append("clock")
        return NOW

    result = getattr(pc, fetcher_name)(PAIR, http_get=http_get, clock=clock)
    assert order == ["http", "clock"]
    assert result.fetched_at == NOW


@pytest.mark.parametrize("fetcher_name", ["fetch_kraken", "fetch_binance"])
def test_a_failed_fetch_produces_no_quote_at_all(fetcher_name):
    """Not a Quote with price None, not a zero: nothing. The caller cannot
    accidentally read a price that was never received."""
    with pytest.raises(pc.SourceError):
        getattr(pc, fetcher_name)(
            PAIR, http_get=http_raising(TimeoutError()), clock=lambda: NOW
        )


# ===========================================================================
# 6. _receipt_age -- the arithmetic that decides fresh from stale
# ===========================================================================
@pytest.mark.parametrize(
    "delta,expected_age",
    [
        (timedelta(0), 0),
        (timedelta(seconds=1), 1),
        (timedelta(seconds=59), 59),
        (timedelta(seconds=60), 60),
        (timedelta(microseconds=1), 1),
        (timedelta(seconds=0.5), 1),
        (timedelta(seconds=59, microseconds=1), 60),
        (timedelta(days=1), 86400),
    ],
    ids=["zero", "one", "just-under", "at-the-limit", "a-microsecond",
         "half-a-second", "just-under-plus-a-hair", "a-whole-day"],
)
def test_a_partial_second_always_rounds_a_quote_older_never_younger(delta, expected_age):
    """total_seconds() is a float and floor() would round a quote YOUNGER than
    it is, which is the direction that lets a stale price through."""
    age, _ = pc._receipt_age(NOW - delta, NOW, 86400)
    assert age == expected_age


def test_a_quote_one_microsecond_past_the_limit_is_already_stale():
    age, problem = pc._receipt_age(NOW - timedelta(seconds=60, microseconds=1), NOW, 60)
    assert age == 61
    assert "past the 60s limit" in problem


def test_a_quote_exactly_at_the_limit_is_not_stale():
    age, problem = pc._receipt_age(NOW - timedelta(seconds=60), NOW, 60)
    assert age == 60
    assert problem is None


@pytest.mark.parametrize(
    "fetched_at,token",
    [
        (None, "no receipt time"),
        (datetime(2026, 8, 27, 12, 0, 0), "no timezone"),
        (datetime(2026, 8, 27, 12, 0, 0, tzinfo=NoOffsetTZ()), "no timezone"),
    ],
    ids=["missing", "naive", "tzinfo-without-an-offset"],
)
def test_an_age_that_cannot_be_established_yields_no_age_and_a_problem(fetched_at, token):
    age, problem = pc._receipt_age(fetched_at, NOW, 60)
    assert age is None
    assert token in problem


@pytest.mark.parametrize("seconds", [1, 300, 86400], ids=["a-second", "five-minutes", "a-day"])
def test_a_future_stamp_is_a_problem_no_matter_how_far_ahead(seconds):
    age, problem = pc._receipt_age(NOW + timedelta(seconds=seconds), NOW, 60)
    assert age == -seconds
    assert "future" in problem
    assert "clock skew" in problem


def test_an_age_measured_across_timezones_uses_the_instant_not_the_wall_clock():
    """Same instant, written in Tokyo time. An implementation comparing naive
    wall clocks would call this nine hours old."""
    tokyo = timezone(timedelta(hours=9))
    age, problem = pc._receipt_age(NOW.astimezone(tokyo), NOW, 60)
    assert age == 0
    assert problem is None


# ===========================================================================
# 7. _spread_bps -- the number that must never be a comforting zero
# ===========================================================================
@pytest.mark.parametrize(
    "prices",
    [
        [],
        [Decimal("1")],
        [Decimal("1"), None],
        [None, Decimal("1")],
        [None, None],
    ],
    ids=["none-at-all", "one-price", "second-missing", "first-missing", "both-missing"],
)
def test_a_spread_that_cannot_be_computed_is_none_never_zero(prices):
    assert pc._spread_bps(prices) is None


def test_a_non_positive_mid_price_yields_no_spread_rather_than_a_division():
    assert pc._spread_bps([Decimal("-5"), Decimal("-5")]) is None
    assert pc._spread_bps([Decimal("-5"), Decimal("5")]) is None


@pytest.mark.parametrize(
    "low,high,expected",
    [
        ("100", "100", "0"),
        ("99.75", "100.25", "50"),
        ("99.70", "100.30", "60"),
        ("100.25", "99.75", "50"),
        ("50", "150", "10000"),
    ],
    ids=["identical", "fifty-bps", "sixty-bps", "order-does-not-matter", "one-hundred-percent"],
)
def test_the_spread_is_the_same_arithmetic_whichever_venue_is_higher(low, high, expected):
    assert pc._spread_bps([Decimal(low), Decimal(high)]) == Decimal(expected)


def test_identical_prices_give_exactly_zero_and_that_zero_is_meaningful():
    """A 0 here means the two venues really agreed. That is why a MISSING
    venue must not produce the same 0 -- see the test above."""
    assert pc._spread_bps([Decimal("68644.20"), Decimal("68644.20")]) == 0


def test_a_difference_below_float_resolution_is_still_a_difference():
    tiny = pc._spread_bps(
        [Decimal("10000.00000000000000001"), Decimal("10000.00000000000000002")]
    )
    assert tiny > 0


# ===========================================================================
# 8. _decide -- the precedence, and what it says out loud
# ===========================================================================
def test_a_single_fetcher_can_never_reach_OK_on_its_own():
    """One venue is not a cross-check, however good its answer is."""
    report = pc.check_prices(
        pair=PAIR, fetchers={"kraken": fetcher_of(quote("kraken"))}, now=NOW
    )
    assert report["verdict"] == "SINGLE_SOURCE"
    assert report["spread_bps"] is None


def test_zero_venues_answering_says_so_instead_of_naming_a_survivor():
    """SINGLE_SOURCE with nothing left is the one place the verdict name reads
    optimistically, so the reason has to carry the truth."""
    report = report_for(
        pc.SourceError("kraken", "timeout after 8s"),
        pc.SourceError("binance", "HTTP 503 Service Unavailable"),
    )
    assert report["verdict"] == "SINGLE_SOURCE"
    assert "no venue answered" in report["reason"]
    assert "only price left" not in report["reason"]
    assert report["spread_bps"] is None
    assert report["sources"]["kraken"]["price"] is None
    assert report["sources"]["binance"]["price"] is None


def test_one_venue_left_is_named_as_the_one_that_nothing_cross_checks():
    report = report_for(pc.SourceError("kraken", "timeout after 8s"), quote("binance"))
    assert "kraken unavailable" in report["reason"]
    assert "binance is the only price left" in report["reason"]


def test_a_quote_that_arrives_without_a_price_is_reported_as_unavailable():
    """A fetcher that hands back a Quote with no price is a bug upstream; the
    report must not present it as a working venue."""
    report = report_for(quote("kraken", price=None), quote("binance"))
    assert report["verdict"] == "SINGLE_SOURCE"
    assert "no price in the response" in report["reason"]
    assert report["sources"]["kraken"]["price"] is None


def test_a_dead_venue_outranks_a_stale_one_and_a_stale_one_outranks_a_spread():
    dead = report_for(
        pc.SourceError("kraken", "timeout after 8s"),
        quote("binance", "100.30", NOW - timedelta(seconds=999)),
    )
    assert dead["verdict"] == "SINGLE_SOURCE"
    stale = report_for(
        quote("kraken", "99.70", NOW - timedelta(seconds=999)), quote("binance", "100.30")
    )
    assert stale["verdict"] == "STALE"
    assert Decimal(stale["spread_bps"]) == Decimal("60")


def test_both_venues_stale_names_both_of_them():
    report = report_for(
        quote("kraken", "100.00", NOW - timedelta(seconds=120)),
        quote("binance", "100.00", NOW - timedelta(seconds=300)),
    )
    assert report["verdict"] == "STALE"
    assert "kraken" in report["reason"]
    assert "binance" in report["reason"]
    assert "120s old" in report["reason"]
    assert "300s old" in report["reason"]


def test_the_disagree_reason_says_the_prices_were_not_averaged():
    report = report_for(quote("kraken", "99.70"), quote("binance", "100.30"))
    assert report["verdict"] == "DISAGREE"
    assert "never averaged" in report["reason"]
    assert "60" in report["reason"]


def test_the_ok_reason_states_both_limits_it_was_measured_against():
    report = report_for(quote("kraken", "100.00"), quote("binance", "100.00"))
    assert report["verdict"] == "OK"
    assert "50" in report["reason"]
    assert "60s" in report["reason"]


def test_a_frozen_quote_delivered_instantly_reads_as_fresh_and_this_script_cannot_see_it():
    """HONEST LIMIT, pinned as it is rather than wished away.

    age_seconds is measured from RECEIPT, not from when the venue last moved
    the price. A venue serving a two-hour-old price instantly is reported as
    zero seconds old and passes the freshness gate. Neither Kraken's Ticker nor
    Binance's /ticker/price carries a price timestamp, so there is nothing to
    measure that with today.

    What the STALE guard does catch: a quote handed over by a caller, a clock
    that jumped, and a timestamp that cannot be read at all. What it does not
    catch is this. The day a venue timestamp is wired in, this test is the one
    that has to be deliberately rewritten -- which is the point of it.
    """
    frozen_price_from_two_hours_ago = quote("kraken", "60000.00", NOW)
    moving_price_now = quote("binance", "60000.00", NOW)
    report = report_for(frozen_price_from_two_hours_ago, moving_price_now)
    assert report["verdict"] == "OK"
    assert report["sources"]["kraken"]["age_seconds"] == 0


# ===========================================================================
# 9. check_prices -- assembly, and the threshold coercion
# ===========================================================================
@pytest.mark.parametrize(
    "limit", [50, "50", Decimal("50"), 50.0], ids=["int", "str", "decimal", "float"]
)
def test_a_spread_limit_arrives_as_a_decimal_however_it_was_written(limit):
    report = report_for(quote("kraken", "99.75"), quote("binance", "100.25"), max_spread_bps=limit)
    assert Decimal(report["spread_bps"]) == Decimal("50")
    assert report["verdict"] == "OK"


def test_a_float_threshold_does_not_drag_binary_noise_into_the_comparison():
    """Decimal(0.1) is 0.1000000000000000055511151231257827. Decimal(str(0.1))
    is 0.1. The second one is what a user typing 0.1 meant."""
    report = report_for(
        quote("kraken", "100.00"), quote("binance", "100.001"), max_spread_bps=0.1
    )
    assert "0.1000000000000000055" not in report["reason"]


def test_the_check_instant_is_sampled_once_after_every_venue_has_answered():
    order = []

    def watched(name):
        def fetch(pair):
            order.append(name)
            return quote(name, "100.00", NOW)

        return fetch

    def clock():
        order.append("clock")
        return NOW

    report = pc.check_prices(
        pair=PAIR,
        fetchers={"kraken": watched("kraken"), "binance": watched("binance")},
        clock=clock,
    )
    assert order == ["kraken", "binance", "clock"]
    assert order.count("clock") == 1
    assert report["checked_at"] == NOW.isoformat()


def test_an_explicit_now_wins_over_the_clock():
    other = NOW + timedelta(hours=5)
    report = pc.check_prices(
        pair=PAIR,
        fetchers={"kraken": fetcher_of(quote("kraken")), "binance": fetcher_of(quote("binance"))},
        now=NOW,
        clock=lambda: other,
    )
    assert report["checked_at"] == NOW.isoformat()


def test_every_fetcher_is_asked_even_when_the_first_one_dies():
    """A dead first venue must not cancel the second: SINGLE_SOURCE is only
    honest if the survivor was actually tried."""
    kraken = fetcher_of(pc.SourceError("kraken", "timeout after 8s"))
    binance = fetcher_of(quote("binance"))
    pc.check_prices(pair=PAIR, fetchers={"kraken": kraken, "binance": binance}, now=NOW)
    assert kraken.calls == [PAIR]
    assert binance.calls == [PAIR]


def test_an_unexpected_exception_from_a_fetcher_is_not_swallowed():
    """Only SourceError means "this venue failed". Anything else is a bug in
    the program and must reach the surface instead of turning into a verdict."""
    with pytest.raises(ZeroDivisionError):
        pc.check_prices(
            pair=PAIR,
            fetchers={
                "kraken": fetcher_of(ZeroDivisionError("bug")),
                "binance": fetcher_of(quote("binance")),
            },
            now=NOW,
        )


def test_the_pair_is_echoed_exactly_as_the_caller_wrote_it():
    report = pc.check_prices(
        pair="btceur",
        fetchers={"kraken": fetcher_of(quote("kraken")), "binance": fetcher_of(quote("binance"))},
        now=NOW,
    )
    assert report["pair"] == "btceur"


def test_every_source_row_carries_the_same_four_keys_whatever_happened():
    report = report_for(pc.SourceError("kraken", "timeout after 8s"), quote("binance"))
    for name, row in report["sources"].items():
        assert set(row) == {"price", "fetched_at", "age_seconds", "error"}, name


def test_a_source_that_worked_carries_no_error_and_a_source_that_failed_carries_no_price():
    report = report_for(pc.SourceError("kraken", "timeout after 8s"), quote("binance"))
    assert report["sources"]["kraken"]["error"] == "timeout after 8s"
    assert report["sources"]["kraken"]["price"] is None
    assert report["sources"]["kraken"]["age_seconds"] is None
    assert report["sources"]["binance"]["error"] is None
    assert report["sources"]["binance"]["price"] is not None


def test_the_whole_report_survives_a_json_round_trip_without_a_single_float():
    report = report_for(quote("kraken", "99.70"), quote("binance", "100.30"))
    again = json.loads(json.dumps(report))
    assert again == report
    assert isinstance(again["spread_bps"], str)
    assert isinstance(again["sources"]["kraken"]["price"], str)


# ===========================================================================
# 10. The two command-line guards (review gap 2)
# ===========================================================================
def test_the_declared_upper_bounds_are_the_ones_the_guards_use():
    assert pc.MAX_SPREAD_LIMIT_BPS == Decimal("10000")
    assert pc.MAX_AGE_LIMIT_SECONDS == 86400
    assert pc.MAX_AGE_LIMIT_SECONDS == pc.SECONDS_PER_DAY


@pytest.mark.parametrize(
    "text,token",
    [
        ("abc", "not a number"),
        ("", "not a number"),
        ("  ", "not a number"),
        ("50bps", "not a number"),
        ("1,5", "not a number"),
        ("NaN", "must be above 0"),
        ("Infinity", "must be above 0"),
        ("-Infinity", "must be above 0"),
        ("0", "must be above 0"),
        ("-1", "must be above 0"),
        ("-0.0001", "must be above 0"),
        ("10001", "at most 10000"),
        ("999999", "at most 10000"),
    ],
    ids=[
        "letters", "empty", "blank", "suffix", "comma-decimal", "nan", "inf",
        "neg-inf", "zero", "negative", "tiny-negative", "just-over", "far-over",
    ],
)
def test_a_spread_limit_that_would_disable_the_check_is_refused_by_name(text, token):
    """A limit of 0 makes every check DISAGREE; a limit of a million makes the
    check permanently pass. Both are a check that is not a check."""
    with pytest.raises(Exception) as caught:
        pc._spread_limit(text)
    assert token in str(caught.value).lower()
    assert repr(text) in str(caught.value)


@pytest.mark.parametrize(
    "text,expected",
    [("50", "50"), ("1", "1"), ("0.0001", "0.0001"), ("10000", "10000"), ("  50  ", "50")],
    ids=["default", "one", "very-tight", "the-ceiling", "padded"],
)
def test_a_usable_spread_limit_is_accepted_as_an_exact_decimal(text, expected):
    value = pc._spread_limit(text)
    assert value == Decimal(expected)
    assert isinstance(value, Decimal)


@pytest.mark.parametrize(
    "text,token",
    [
        ("abc", "not a whole number"),
        ("", "not a whole number"),
        ("10.5", "not a whole number"),
        ("60s", "not a whole number"),
        ("1e3", "not a whole number"),
        ("0", "must be above 0"),
        ("-1", "must be above 0"),
        ("-3600", "must be above 0"),
        ("86401", "at most 86400"),
        ("999999", "at most 86400"),
    ],
    ids=[
        "letters", "empty", "fractional", "suffix", "scientific", "zero",
        "negative", "very-negative", "just-over", "far-over",
    ],
)
def test_an_age_limit_that_would_disable_the_check_is_refused_by_name(text, token):
    """--max-age-seconds 0 would mark every quote stale; a limit past a day
    means nothing is ever stale. Neither is a freshness gate."""
    with pytest.raises(Exception) as caught:
        pc._age_limit(text)
    assert token in str(caught.value).lower()
    assert repr(text) in str(caught.value)


@pytest.mark.parametrize(
    "text,expected",
    [("60", 60), ("1", 1), ("86400", 86400), (" 30 ", 30), ("+30", 30)],
    ids=["default", "one-second", "the-ceiling", "padded", "signed"],
)
def test_a_usable_age_limit_is_accepted_as_a_whole_number_of_seconds(text, expected):
    value = pc._age_limit(text)
    assert value == expected
    assert type(value) is int


@pytest.mark.parametrize(
    "argv",
    [
        ["--max-spread-bps", "0"],
        ["--max-spread-bps", "-1"],
        ["--max-spread-bps", "abc"],
        ["--max-spread-bps", "10001"],
        ["--max-age-seconds", "0"],
        ["--max-age-seconds", "-5"],
        ["--max-age-seconds", "10.5"],
        ["--max-age-seconds", "86401"],
        ["--nonsense"],
    ],
    ids=[
        "spread-zero", "spread-negative", "spread-letters", "spread-over-ceiling",
        "age-zero", "age-negative", "age-fractional", "age-over-ceiling", "unknown-flag",
    ],
)
def test_the_command_line_refuses_a_bad_limit_loudly_and_runs_nothing(argv, capsys):
    called = []

    def must_not_run(pair):
        called.append(pair)
        return quote()

    with pytest.raises(SystemExit) as caught:
        pc.main(argv, fetchers={"kraken": must_not_run, "binance": must_not_run}, now=NOW)
    assert caught.value.code == 2
    assert called == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage:" in captured.err.lower()


def test_a_tighter_limit_from_the_command_line_actually_reaches_the_decision(capsys):
    fetchers = {
        "kraken": fetcher_of(quote("kraken", "100.00", NOW - timedelta(seconds=30))),
        "binance": fetcher_of(quote("binance", "100.01", NOW - timedelta(seconds=30))),
    }
    assert pc.main(["--max-age-seconds", "10"], fetchers=fetchers, now=NOW) == pc.EXIT_CODES["STALE"]
    assert json.loads(capsys.readouterr().out)["verdict"] == "STALE"

    fetchers = {
        "kraken": fetcher_of(quote("kraken", "100.00")),
        "binance": fetcher_of(quote("binance", "100.01")),
    }
    assert pc.main(["--max-spread-bps", "0.5"], fetchers=fetchers, now=NOW) == pc.EXIT_CODES[
        "DISAGREE"
    ]
    assert json.loads(capsys.readouterr().out)["verdict"] == "DISAGREE"


def test_the_parser_defaults_are_the_documented_ones():
    args = pc._parser().parse_args([])
    assert args.pair == "BTC/EUR"
    assert args.max_spread_bps == Decimal("50")
    assert args.max_age_seconds == 60


def test_the_help_text_names_both_limits_and_their_defaults(capsys):
    with pytest.raises(SystemExit) as caught:
        pc.main(["--help"])
    assert caught.value.code == 0
    out = capsys.readouterr().out
    assert "--max-spread-bps" in out
    assert "--max-age-seconds" in out
    assert "50" in out
    assert "60" in out


# ===========================================================================
# 11. main -- the exit code is the part a caller cannot ignore
# ===========================================================================
def test_the_four_exit_codes_are_distinct_and_leave_2_to_argparse():
    assert pc.EXIT_CODES == {"OK": 0, "DISAGREE": 3, "STALE": 4, "SINGLE_SOURCE": 5}
    assert len(set(pc.EXIT_CODES.values())) == 4
    assert 2 not in pc.EXIT_CODES.values()
    assert all(0 <= code <= 255 for code in pc.EXIT_CODES.values())


@pytest.mark.parametrize(
    "scenario,verdict",
    [
        ("agree", "OK"),
        ("disagree", "DISAGREE"),
        ("stale", "STALE"),
        ("one-dead", "SINGLE_SOURCE"),
        ("both-dead", "SINGLE_SOURCE"),
    ],
)
def test_each_verdict_leaves_through_its_own_exit_code(scenario, verdict, capsys):
    scenarios = {
        "agree": (quote("kraken", "100.00"), quote("binance", "100.00")),
        "disagree": (quote("kraken", "99.70"), quote("binance", "100.30")),
        "stale": (quote("kraken", "100.00", NOW - timedelta(seconds=999)), quote("binance")),
        "one-dead": (pc.SourceError("kraken", "timeout after 8s"), quote("binance")),
        "both-dead": (
            pc.SourceError("kraken", "timeout after 8s"),
            pc.SourceError("binance", "HTTP 503 Service Unavailable"),
        ),
    }
    kraken, binance = scenarios[scenario]
    rc = pc.main(
        [], fetchers={"kraken": fetcher_of(kraken), "binance": fetcher_of(binance)}, now=NOW
    )
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == verdict
    assert rc == pc.EXIT_CODES[verdict]
    assert (rc == 0) == (verdict == "OK")


def test_the_report_reaches_stdout_before_the_exit_code_is_returned(capsys):
    rc = pc.main(
        [],
        fetchers={
            "kraken": fetcher_of(pc.SourceError("kraken", "timeout after 8s")),
            "binance": fetcher_of(pc.SourceError("binance", "timeout after 8s")),
        },
        now=NOW,
    )
    captured = capsys.readouterr()
    assert rc != 0
    assert json.loads(captured.out)["reason"]
    assert captured.err == ""


def test_stdout_is_one_json_document_and_nothing_else(capsys):
    pc.main(
        [],
        fetchers={"kraken": fetcher_of(quote("kraken")), "binance": fetcher_of(quote("binance"))},
        now=NOW,
    )
    out = capsys.readouterr().out
    assert out.startswith("{")
    assert out.endswith("}\n")
    assert json.loads(out)


def test_main_uses_the_real_venues_when_no_fetchers_are_injected(monkeypatch):
    """The default wiring is real: no fetchers argument means the two public
    venues, not a stub left behind by a test."""
    seen = []

    def fake_fetch(name):
        def fetch(pair):
            seen.append(name)
            return quote(name, "100.00", NOW)

        return fetch

    monkeypatch.setitem(pc.DEFAULT_FETCHERS, "kraken", fake_fetch("kraken"))
    monkeypatch.setitem(pc.DEFAULT_FETCHERS, "binance", fake_fetch("binance"))
    assert pc.main([], now=NOW) == 0
    assert seen == ["kraken", "binance"]
    assert pc.DEFAULT_FETCHERS["kraken"] is not fake_fetch


def test_the_default_fetchers_are_the_two_module_level_functions():
    assert pc.DEFAULT_FETCHERS == {"kraken": pc.fetch_kraken, "binance": pc.fetch_binance}


# ===========================================================================
# 12. The real process -- the path a person actually enters by
# ===========================================================================
def test_the_script_runs_as_a_process_and_argparse_owns_exit_code_2(tmp_path):
    """Measured from outside: `sys.exit(main())` is a line no in-process test
    ever executes, and a bad exit status there is invisible until a caller is
    burned by it."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--max-age-seconds", "0"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "must be above 0" in result.stderr


def test_the_script_prints_its_help_as_a_process_and_exits_zero(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "--pair" in result.stdout


def test_importing_the_module_prints_nothing_and_opens_no_socket(tmp_path):
    """A skill script that chatters on import corrupts the JSON of anything
    that imports it."""
    result = subprocess.run(
        [sys.executable, "-c", "import price_check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        env={"PYTHONPATH": str(SCRIPT.parent), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
