"""SQL and pandas must agree with each other and with the figures in the README."""

import pytest

from expected_figures import EXPECTED, matches


@pytest.mark.parametrize("key", EXPECTED)
def test_sql_matches_pandas(key, sql_figures, pandas_figures):
    s, p = sql_figures[key], pandas_figures[key]
    if isinstance(p, str):
        assert s == p
    else:
        assert s == pytest.approx(p, rel=1e-9, abs=1e-6)


@pytest.mark.parametrize("key", EXPECTED)
def test_readme_figure(key, sql_figures):
    expected, tol, _ = EXPECTED[key]
    assert matches(sql_figures[key], expected, tol), f"{key}: README {expected}, data {sql_figures[key]}"
