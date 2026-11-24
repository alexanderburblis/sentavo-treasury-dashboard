"""
Cross-check of the dashboard numbers with pandas.

Recomputes the headline measures from the CSV files, independently of the
DAX model and of the SQL views, so the figures on the Power BI pages can be
checked against a second and a third calculation.

Run:  python src/reconcile_dashboard.py data
"""

import sys
from pathlib import Path

import pandas as pd

IHB = "SIG-CH01"          # holding company and in-house bank
PL_BANK = "B06"           # Regional Bank PL


def compute(data="data"):
    """Return the headline figures as a flat dict (amounts in CHF, shares as fractions)."""
    data = Path(data)
    liq = pd.read_csv(data / "FactLiquidityPosition.csv", parse_dates=["Date"])
    bank = pd.read_csv(data / "DimBank.csv").set_index("BankKey")
    spreads = pd.read_csv(data / "FactCreditSpreads.csv", parse_dates=["Date"])
    fc = pd.read_csv(data / "FactCashForecast.csv", parse_dates=["WeekStart"])
    fees = pd.read_csv(data / "FactBankFees.csv", parse_dates=["FeeMonth"])
    pnl = pd.read_csv(data / "FactTreasuryPnL.csv", parse_dates=["Month"])

    r = {}
    as_of = liq["Date"].max()
    r["as_of"] = as_of.date().isoformat()

    # Liquidity
    today = liq[liq["Date"] == as_of]
    r["cash_chf"] = today["Balance_CHF"].sum()
    r["outside_ihb_chf"] = today.loc[today["EntityKey"] != IHB, "Balance_CHF"].sum()
    r["outside_ihb_share"] = r["outside_ihb_chf"] / r["cash_chf"]

    # Counterparty limits
    exposure = (liq[liq["CounterpartyType"] == "Bank"]
                .groupby(["Date", "BankKey"])["Balance_CHF"].sum().unstack(fill_value=0))
    util = exposure.div(bank["CounterpartyLimit_CHF"])
    r["max_utilisation_today"] = util.loc[as_of].max()
    pl = util[PL_BANK]
    r["pl_peak_exposure_chf"] = exposure[PL_BANK].max()
    r["pl_peak_utilisation"] = pl.max()
    r["pl_peak_date"] = pl.idxmax().date().isoformat()
    first80, first100 = pl[pl > 0.8].index.min(), pl[pl > 1].index.min()
    r["pl_first_over_80"] = first80.date().isoformat()
    r["pl_first_over_100"] = first100.date().isoformat()
    r["pl_weeks_of_warning"] = (first100 - first80).days / 7
    r["pl_days_over_limit"] = int((pl > 1).sum())
    last = spreads[spreads["Date"] == spreads["Date"].max()].set_index("BankKey")["CreditSpread_bps"]
    r["pl_spread_start_bps"] = spreads.loc[spreads["BankKey"] == PL_BANK, "CreditSpread_bps"].iloc[0]
    r["pl_spread_end_bps"] = last[PL_BANK]

    # Forecast quality
    fc["abs_err"] = (fc["Forecast_CHF"] - fc["Actual_CHF"]).abs()
    base = fc.loc[fc["HorizonWeeks"] == 1, "Actual_CHF"].abs().sum()
    for h in (1, 4, 13):
        r[f"wape_{h}w"] = fc.loc[fc["HorizonWeeks"] == h, "abs_err"].sum() / base
    rec = fc[fc["FlowCategory"] == "Customer receipts"]
    rec_actual = rec.loc[rec["HorizonWeeks"] == 1, "Actual_CHF"].sum()
    r["receipts_bias_13w"] = rec.loc[rec["HorizonWeeks"] == 13, "Forecast_CHF"].sum() / rec_actual - 1
    net = fc[fc["FlowCategory"] != "Intercompany"]
    weeks = sorted(net["WeekStart"].unique())[-13:]
    last13 = net[net["WeekStart"].isin(weeks)]
    r["last13w_actual_chf"] = last13.loc[last13["HorizonWeeks"] == 1, "Actual_CHF"].sum()
    r["last13w_fcst13w_chf"] = last13.loc[last13["HorizonWeeks"] == 13, "Forecast_CHF"].sum()

    # Bank fees: Core Bank 3 payments tariff, Jan-Sep 2026 vs Jan-Sep 2025
    b3 = fees[(fees["BankKey"] == "B03") & (fees["FeeCategory"] == "Payments & collections")]
    ytd = lambda y: b3[(b3["FeeMonth"].dt.year == y) & (b3["FeeMonth"].dt.month <= 9)]["Amount_CHF"].sum()
    r["b03_payments_fees_yoy"] = ytd(2026) / ytd(2025) - 1
    tot = lambda y: fees[(fees["FeeMonth"].dt.year == y) & (fees["FeeMonth"].dt.month <= 9)]["Amount_CHF"].sum()
    r["fees_ytd_2026_chf"] = tot(2026)
    r["fees_yoy_2026"] = tot(2026) / tot(2025) - 1

    # Treasury P&L: budget variance
    last_actual = pnl.loc[pnl["Scenario"] == "Actual", "Month"].max()
    pnl["Year"] = pnl["Month"].dt.year
    for y in (2025, 2026):
        p = pnl[pnl["Year"] == y]
        to_date = p[p["Month"] <= last_actual]
        s = lambda df, sc, line: df.loc[(df["Scenario"] == sc) & (df["Line"] == line), "Amount_CHF"].sum()
        r[f"interest_actual_ytd_{y}_chf"] = s(to_date, "Actual", "Interest income")
        r[f"interest_budget_ytd_{y}_chf"] = s(to_date, "Budget", "Interest income")
        total_act = to_date.loc[to_date["Scenario"] == "Actual", "Amount_CHF"].sum()
        total_bud = to_date.loc[to_date["Scenario"] == "Budget", "Amount_CHF"].sum()
        r[f"pnl_variance_ytd_{y}_chf"] = total_act - total_bud
        outturn = (p.loc[(p["Scenario"] == "Actual") & (p["Month"] <= last_actual), "Amount_CHF"].sum() +
                   p.loc[(p["Scenario"] == "Forecast Q2") & (p["Month"] > last_actual), "Amount_CHF"].sum())
        r[f"pnl_outturn_fy_{y}_chf"] = outturn
        r[f"pnl_budget_fy_{y}_chf"] = p.loc[p["Scenario"] == "Budget", "Amount_CHF"].sum()
    b3p = pnl[(pnl["Year"] == 2026) & (pnl["Month"] <= last_actual) &
              (pnl["Line"] == "Bank fees") & (pnl["BankKey"] == "B03")]
    act = b3p.loc[b3p["Scenario"] == "Actual", "Amount_CHF"].sum()
    bud = b3p.loc[b3p["Scenario"] == "Budget", "Amount_CHF"].sum()
    r["b03_fees_vs_budget_2026"] = act / bud - 1

    # Term deposits: pricing against the best quote and the benchmark, weighted by CHF principal
    dep = pd.read_csv(data / "FactTermDeposits.csv", parse_dates=["StartDate", "MaturityDate"])
    fxr = pd.read_csv(data / "MarketFXRates.csv", parse_dates=["Date"])
    quotes = pd.read_csv(data / "FactDepositQuotes.csv", parse_dates=["QuoteMonth"])
    bench = pd.read_csv(data / "MarketBenchmarkRates.csv", parse_dates=["Date"])
    dep = dep.merge(fxr, left_on=["StartDate", "Currency"], right_on=["Date", "CurrencyCode"]).drop(columns="Date")
    dep["Principal_CHF"] = dep["Principal_LC"] * dep["CHF_per_unit"]
    dep["QuoteMonth"] = dep["StartDate"].dt.to_period("M").dt.to_timestamp()
    best = quotes.groupby(["QuoteMonth", "Currency", "Tenor"], as_index=False)["QuotedRate_pct"].max()
    dep = dep.merge(best, on=["QuoteMonth", "Currency", "Tenor"], how="left")
    dep = dep.merge(bench[["Date", "Currency", "Rate_pct"]], left_on=["StartDate", "Currency"],
                    right_on=["Date", "Currency"], how="left")
    w = dep["Principal_CHF"] / dep["Principal_CHF"].sum()
    r["deposits_vs_best_quote_bps"] = (w * (dep["InterestRate_pct"] - dep["QuotedRate_pct"])).sum() * 100
    r["deposits_vs_benchmark_bps"] = (w * (dep["InterestRate_pct"] - dep["Rate_pct"])).sum() * 100
    r["deposits_outstanding_chf"] = dep.loc[dep["Status"] == "Outstanding", "Principal_CHF"].sum()
    r["deposits_share_below_best"] = (dep["InterestRate_pct"] < dep["QuotedRate_pct"] - 1e-9).mean()

    b01 = fees[(fees["BankKey"] == "B01") & (fees["FeeCategory"] == "Connectivity & eBanking")]
    window = lambda a, b: b01.loc[b01["FeeMonth"].between(a, b), "Amount_CHF"].sum()
    r["b01_connectivity_fees_change"] = window("2025-10-01", "2026-06-01") / window("2024-10-01", "2025-06-01") - 1
    b03 = util["B03"]
    r["b03_breach_day"] = b03[b03 > 1].index.min().date().isoformat()
    return r


def main():
    r = compute(sys.argv[1] if len(sys.argv) > 1 else "data")
    m = lambda v: f"CHF {v / 1e6:7.2f}m"
    print(f"As of {r['as_of']}\n")
    print(f"Cash                          {m(r['cash_chf'])}")
    print(f"Outside the in-house bank     {m(r['outside_ihb_chf'])}  ({r['outside_ihb_share']:.1%})")
    print(f"Max bank utilisation today    {r['max_utilisation_today']:.1%}")
    print("\nRegional Bank PL")
    print(f"  first above 80%   {r['pl_first_over_80']}")
    print(f"  first above 100%  {r['pl_first_over_100']}  ({r['pl_weeks_of_warning']:.1f} weeks later)")
    print(f"  peak              {m(r['pl_peak_exposure_chf'])} = {r['pl_peak_utilisation']:.1%} on {r['pl_peak_date']}")
    print(f"  business days over limit {r['pl_days_over_limit']}")
    print(f"  credit spread {r['pl_spread_start_bps']:.1f} -> {r['pl_spread_end_bps']:.1f} bps")
    print("\nForecast WAPE   " + "  ".join(f"{h}w {r[f'wape_{h}w']:.1%}" for h in (1, 4, 13)))
    print(f"Receipts bias at 13 weeks {r['receipts_bias_13w']:+.1%}")
    print(f"Last 13 weeks: actual {m(r['last13w_actual_chf'])}, 13-week forecast {m(r['last13w_fcst13w_chf'])}")
    print(f"\nBank fees Jan-Sep 2026        {m(r['fees_ytd_2026_chf'])}  ({r['fees_yoy_2026']:+.1%} YoY)")
    print(f"Core Bank 3 payment fees YoY  {r['b03_payments_fees_yoy']:+.1%}")
    print(f"Core Bank 3 fees vs budget    {r['b03_fees_vs_budget_2026']:+.1%}")
    print(f"\nTerm deposits: {r['deposits_vs_best_quote_bps']:+.1f} bps vs best quote, "
          f"{r['deposits_vs_benchmark_bps']:+.1f} bps vs benchmark, outstanding {m(r['deposits_outstanding_chf'])}")
    for y in (2025, 2026):
        print(f"\nTreasury P&L {y}")
        print(f"  interest income YTD  actual {m(r[f'interest_actual_ytd_{y}_chf'])}  "
              f"budget {m(r[f'interest_budget_ytd_{y}_chf'])}")
        print(f"  total variance YTD   {m(r[f'pnl_variance_ytd_{y}_chf'])}")
        print(f"  full year            outturn {m(r[f'pnl_outturn_fy_{y}_chf'])}  "
              f"budget {m(r[f'pnl_budget_fy_{y}_chf'])}")


if __name__ == "__main__":
    main()
