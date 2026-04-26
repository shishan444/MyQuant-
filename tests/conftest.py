"""Shared test fixtures for MyQuant test suite.

All data generation is delegated to tests.helpers.data_factory.
Individual test files may define local fixtures with custom parameters.
"""

import pytest


# Re-export data_factory helpers as fixtures for backward compatibility.
# New tests should import directly from tests.helpers.data_factory.
from tests.helpers.data_factory import (
    make_ohlcv,
    make_dna,
    make_engine,
    make_enhanced_df,
    make_mtf_dna,
    make_ema_dna,
)
