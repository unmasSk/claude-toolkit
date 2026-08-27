# Lifted from tradermonty/claude-trading-skills (MIT), 2026-08-27.
# Source: skills/position-sizer/scripts/tests/conftest.py
# Source: skills/drawdown-circuit-breaker/scripts/tests/conftest.py
# Source: skills/pre-trade-discipline-gate/scripts/tests/conftest.py
# Source: skills/trader-memory-core/scripts/tests/conftest.py
# https://github.com/tradermonty/claude-trading-skills
# Copyright (c) 2026 TraderMonty. See unmassk-trading/CREDITS.md.
#
# MERGE NOTE (Dante, lift pass): the three source skills each shipped their own
# conftest.py; collapsed into this one file because the three suites now live in
# a single tests/ directory. The three sources did the same job by two different
# spellings -- position-sizer used os.path and also added the tests/ dir to
# sys.path; the other two used pathlib and added only scripts/. This file is the
# union, so every one of the suites gets at least what it had before.
#
# WAVE 2: trader-memory-core's conftest.py joined the merge. It was a strict
# SUBSET of what is already here (one line: put the sibling scripts/ dir on
# sys.path), so nothing new had to be added -- only this note, so the fourth
# source is traceable and nobody later thinks it was dropped.
"""Shared fixtures for the lifted trading-script tests.

Puts the sibling ``scripts/`` directory (where position_sizer.py,
check_circuit_breaker.py and check_pre_trade_discipline.py live) and this
``tests/`` directory itself on sys.path, so the test modules can import the
scripts under test and any co-located helpers.
"""

import sys
from pathlib import Path

# Add scripts directory to path so modules can be imported
scripts_dir = Path(__file__).resolve().parents[1]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# Add tests directory to path so helpers can be imported
tests_dir = Path(__file__).resolve().parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))
