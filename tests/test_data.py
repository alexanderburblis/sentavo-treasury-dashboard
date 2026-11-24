"""Checks on the generated data and on the treasury P&L."""

import pandas as pd
import pytest


def test_data_quality_checks_pass(con):
    failed = con.execute("SELECT CheckName FROM v_data_quality WHERE Failures > 0").fetchall()
    assert failed == []


def test_breach_episodes(con):
    rows = con.execute("""
        SELECT COUNT(*), SUM(BusinessDaysOver), MIN(FirstDayOver), MAX(LastDayOver)
        FROM v_limit_breach_episodes WHERE BankKey = 'B06'""").fetchone()
    episodes, days, first, last = rows
    assert (episodes, days) == (5, 41)
    assert first.isoformat() == "2025-05-27" and last.isoformat() == "2025-07-30"


def test_fee_step_changes_find_the_two_scenarios(con):
    found = set(con.execute("SELECT BankKey, FeeCategory, SIGN(YoY_3M) FROM v_bank_fee_step_changes").fetchall())
    assert found == {("B03", "Payments & collections", 1), ("B01", "Connectivity & eBanking", -1)}


@pytest.fixture(scope="module")
def pnl(data_dir):
    return pd.read_csv(data_dir / "FactTreasuryPnL.csv", parse_dates=["Month"])


def test_actual_fees_tie_to_fee_table(pnl, data_dir):
    fees = pd.read_csv(data_dir / "FactBankFees.csv")
    actual = pnl.loc[(pnl["Scenario"] == "Actual") & (pnl["Line"] == "Bank fees"), "Amount_CHF"].sum()
    assert actual == pytest.approx(-fees["Amount_CHF"].sum(), abs=1.0)


def test_actual_fx_cost_ties_to_deals(pnl, data_dir):
    deals = pd.read_csv(data_dir / "FactFXDeals.csv")
    actual = pnl.loc[(pnl["Scenario"] == "Actual") & (pnl["Line"] == "FX cost"), "Amount_CHF"].sum()
    assert actual == pytest.approx(-(deals["Notional_CHF"] * deals["Spread_bps"] / 2 / 1e4).sum(), abs=1.0)


def test_sign_convention(pnl):
    lines = pnl.groupby("Line")["Amount_CHF"]
    assert (lines.min()["Bank fees"] <= 0) and (lines.max()["Bank fees"] <= 0)
    assert lines.max()["FX cost"] <= 0
    assert pnl.loc[pnl["Line"] == "Interest income", "Amount_CHF"].sum() > 0


def test_budget_covers_full_years(pnl):
    budget = pnl[pnl["Scenario"] == "Budget"]
    assert sorted(budget["Month"].dt.year.unique()) == [2025, 2026]
    assert budget.groupby(budget["Month"].dt.year)["Month"].nunique().eq(12).all()


@pytest.mark.parametrize("scenario,closed_to", [("Forecast Q1", 3), ("Forecast Q2", 6)])
def test_reforecast_carries_actuals_for_closed_months(pnl, scenario, closed_to):
    for year in (2025, 2026):
        closed = lambda sc: pnl[(pnl["Scenario"] == sc) & (pnl["Month"].dt.year == year) &
                                (pnl["Month"].dt.month <= closed_to)]["Amount_CHF"].sum()
        assert closed(scenario) == pytest.approx(closed("Actual"), abs=0.01)


def test_rls_mapping(data_dir):
    users = pd.read_csv(data_dir / "SecurityUserEntity.csv")
    entities = pd.read_csv(data_dir / "DimEntity.csv")["EntityKey"]
    treasurer = users[users["UserPrincipalName"].str.startswith("group.treasurer")]
    assert set(treasurer["EntityKey"]) == set(entities)
    assert not users.duplicated().any()
