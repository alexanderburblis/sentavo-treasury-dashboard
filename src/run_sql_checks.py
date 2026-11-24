"""
SQL checks with DuckDB.

Loads every CSV in data/ as a view, creates the analytical views in sql/,
and compares the SQL results with the figures quoted in the README and with
the pandas reconciliation. Together with DAX in Power BI that gives three
independent calculations of the same numbers.

Run:  python src/run_sql_checks.py            (prints the checks, exits 1 on a mismatch)
      python src/run_sql_checks.py --show     (also prints the breach episodes and data-quality checks)
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from expected_figures import EXPECTED, matches  # noqa: E402


def connect(data=ROOT / "data", sql=ROOT / "sql"):
    """In-memory DuckDB with one view per CSV and the views in sql/*.sql."""
    con = duckdb.connect()
    for csv in sorted(Path(data).glob("*.csv")):
        con.execute(f"CREATE VIEW {csv.stem} AS SELECT * FROM read_csv_auto('{csv.as_posix()}')")
    for script in sorted(Path(sql).glob("*.sql")):
        con.execute(script.read_text(encoding="utf-8"))
    return con


def compute(con):
    """The headline figures, from SQL only. Same keys as reconcile_dashboard.compute."""
    one = lambda q: con.execute(q).fetchone()
    r = {}
    as_of, cash, outside, share = one(
        "SELECT Date, Cash_CHF, Outside_IHB_CHF, Outside_IHB_Share FROM v_cash_daily ORDER BY Date DESC LIMIT 1")
    r.update(as_of=as_of.isoformat(), cash_chf=cash, outside_ihb_chf=outside, outside_ihb_share=share)
    r["max_utilisation_today"] = one(
        "SELECT MAX(Utilisation) FROM v_bank_exposure_daily WHERE Date = (SELECT MAX(Date) FROM v_bank_exposure_daily)")[0]

    days, peak_chf, peak_util, peak_date = one("""
        SELECT SUM(BusinessDaysOver), MAX(PeakExposure_CHF), MAX(PeakUtilisation), ARG_MAX(PeakDate, PeakUtilisation)
        FROM v_limit_breach_episodes WHERE BankKey = 'B06'""")
    r.update(pl_days_over_limit=int(days), pl_peak_exposure_chf=peak_chf,
             pl_peak_utilisation=peak_util, pl_peak_date=peak_date.isoformat())
    first80, first100, weeks = one("""
        SELECT FirstDayOverAlert, FirstDayOver, WeeksOfWarning
        FROM v_breach_early_warning WHERE BankKey = 'B06' AND EpisodeNo = 1""")
    r.update(pl_first_over_80=first80.isoformat(), pl_first_over_100=first100.isoformat(),
             pl_weeks_of_warning=weeks)
    r["pl_spread_start_bps"], r["pl_spread_end_bps"] = one("""
        SELECT ARG_MIN(CreditSpread_bps, Date), ARG_MAX(CreditSpread_bps, Date)
        FROM FactCreditSpreads WHERE BankKey = 'B06'""")

    for h, w in con.execute("SELECT HorizonWeeks, WAPE FROM v_forecast_wape").fetchall():
        r[f"wape_{h}w"] = w
    r["receipts_bias_13w"] = one("SELECT Bias FROM v_receipts_bias WHERE HorizonWeeks = 13")[0]
    r["last13w_actual_chf"], r["last13w_fcst13w_chf"] = one(
        "SELECT CumActual_CHF, CumFcst13W_CHF FROM v_last13w_cumulative ORDER BY WeekStart DESC LIMIT 1")

    r["b03_payments_fees_yoy"] = one("""
        SELECT SUM(Amount_CHF) / SUM(Amount_PY_CHF) - 1 FROM v_bank_fees_yoy
        WHERE BankKey = 'B03' AND FeeCategory = 'Payments & collections'
          AND YEAR(FeeMonth) = 2026 AND MONTH(FeeMonth) <= 9""")[0]
    r["fees_ytd_2026_chf"], r["fees_yoy_2026"] = one("""
        SELECT SUM(Amount_CHF), SUM(Amount_CHF) / SUM(Amount_PY_CHF) - 1 FROM v_bank_fees_yoy
        WHERE YEAR(FeeMonth) = 2026 AND MONTH(FeeMonth) <= 9""")

    for y in (2025, 2026):
        r[f"interest_actual_ytd_{y}_chf"], r[f"interest_budget_ytd_{y}_chf"] = one(
            f"SELECT Actual_CHF, Budget_CHF FROM v_budget_variance_ytd WHERE Year = {y} AND Line = 'Interest income'")
        r[f"pnl_variance_ytd_{y}_chf"] = one(
            f"SELECT SUM(Variance_CHF) FROM v_budget_variance_ytd WHERE Year = {y}")[0]
        r[f"pnl_outturn_fy_{y}_chf"], r[f"pnl_budget_fy_{y}_chf"] = one(
            f"SELECT SUM(Outturn_FY_CHF), SUM(Budget_FY_CHF) FROM v_full_year_outturn WHERE Year = {y}")
    r["b03_fees_vs_budget_2026"] = one("""
        SELECT SUM(Amount_CHF) FILTER (WHERE Scenario = 'Actual')
             / SUM(Amount_CHF) FILTER (WHERE Scenario = 'Budget') - 1
        FROM FactTreasuryPnL, v_pnl_close
        WHERE Line = 'Bank fees' AND BankKey = 'B03' AND YEAR(Month) = 2026 AND Month <= LastActualMonth""")[0]
    r["deposits_vs_best_quote_bps"], r["deposits_vs_benchmark_bps"] = one("""
        SELECT SUM(Principal_CHF * VsBestQuote_bps) / SUM(Principal_CHF),
               SUM(Principal_CHF * VsBenchmark_bps) / SUM(Principal_CHF)
        FROM v_deposit_pricing""")
    r["deposits_outstanding_chf"] = one("SELECT SUM(Principal_CHF) FROM v_maturity_ladder")[0]
    r["deposits_share_below_best"] = one(
        "SELECT AVG(CASE WHEN VsBestQuote_bps < -1e-6 THEN 1.0 ELSE 0.0 END) FROM v_deposit_pricing")[0]
    # Core Bank 1 connectivity fees, Oct 2025 to Jun 2026 against the same months a year earlier
    r["b01_connectivity_fees_change"] = one("""
        SELECT SUM(Amount_CHF) / SUM(Amount_PY_CHF) - 1 FROM v_bank_fees_yoy
        WHERE BankKey = 'B01' AND FeeCategory = 'Connectivity & eBanking'
          AND FeeMonth BETWEEN DATE '2025-10-01' AND DATE '2026-06-01'""")[0]
    r["b03_breach_day"] = one(
        "SELECT FirstDayOver FROM v_limit_breach_episodes WHERE BankKey = 'B03'")[0].isoformat()
    r["fx_deals"], r["fx_volume_chf"], r["fx_spread_bps"], r["fx_cost_chf"], r["fx_platform_share"] = one("""
        SELECT COUNT(*), SUM(Notional_CHF), SUM(Notional_CHF * Spread_bps) / SUM(Notional_CHF),
               SUM(SpreadCost_CHF),
               SUM(Notional_CHF) FILTER (WHERE ExecutionChannel = 'Multi-bank platform') / SUM(Notional_CHF)
        FROM v_fx_deals""")
    r["fx_eurpln_spread_bps"] = one("SELECT Spread_bps FROM v_fx_by_pair WHERE CurrencyPair = 'EUR/PLN'")[0]
    r["fx_eurusd_spread_bps"] = one("SELECT Spread_bps FROM v_fx_by_pair WHERE CurrencyPair = 'EUR/USD'")[0]
    r["fx_b06_spread_bps"] = one("SELECT Spread_bps FROM v_fx_by_bank WHERE BankKey = 'B06'")[0]
    r["fx_b01_spread_bps"] = one("SELECT Spread_bps FROM v_fx_by_bank WHERE BankKey = 'B01'")[0]
    return r


def main():
    con = connect()
    sql = compute(con)
    failed = 0
    print(f"{'Figure':34s} {'README':>14s} {'SQL':>14s}  ")
    for key, (expected, tol, fmt) in EXPECTED.items():
        ok = matches(sql[key], expected, tol)
        failed += not ok
        show = lambda v: fmt.format(v) if not isinstance(v, str) else v
        print(f"{key:34s} {show(expected):>14s} {show(sql[key]):>14s}  {'ok' if ok else 'MISMATCH'}")

    dq = con.execute("SELECT CheckName, Failures FROM v_data_quality").fetchall()
    dq_failed = [name for name, n in dq if n]
    print(f"\nData quality: {len(dq) - len(dq_failed)} of {len(dq)} checks pass")
    for name in dq_failed:
        print(f"  FAILED: {name}")

    if "--show" in sys.argv:
        print("\nLimit-breach episodes")
        print(con.sql("SELECT * FROM v_limit_breach_episodes"))
        print(con.sql("SELECT * FROM v_bank_fee_step_changes ORDER BY FeeMonth"))
        print(con.sql("SELECT * FROM v_budget_variance_ytd"))
        print(con.sql("SELECT * FROM v_full_year_outturn"))
        print(con.sql("SELECT * FROM v_table_profile"))

    print(f"\n{'All figures match.' if not failed else f'{failed} figure(s) do not match.'}")
    sys.exit(1 if failed or dq_failed else 0)


if __name__ == "__main__":
    main()
