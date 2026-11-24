import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import reconcile_dashboard  # noqa: E402
import run_sql_checks  # noqa: E402


@pytest.fixture(scope="session")
def data_dir():
    return ROOT / "data"


@pytest.fixture(scope="session")
def con():
    return run_sql_checks.connect()


@pytest.fixture(scope="session")
def pandas_figures(data_dir):
    return reconcile_dashboard.compute(data_dir)


@pytest.fixture(scope="session")
def sql_figures(con):
    return run_sql_checks.compute(con)
