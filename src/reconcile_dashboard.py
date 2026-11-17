"""
Cross-check of the dashboard numbers.

Recomputes the headline measures from the CSV files with pandas, independently
of the DAX model, so the figures on the Power BI page can be checked against
a second calculation.

Run:  python src/reconcile_dashboard.py data
"""

import sys
import pandas as pd

data = sys.argv[1] if len(sys.argv) > 1 else "data"

liq = pd.read_csv(f"{data}/FactLiquidityPosition.csv", parse_dates=["Date"])
bank = pd.read_csv(f"{data}/DimBank.csv").set_index("BankKey")
spreads = pd.read_csv(f"{data}/FactCreditSpreads.csv", parse_dates=["Date"])
fc = pd.read_csv(f"{data}/FactCashForecast.csv", parse_dates=["WeekStart"])

as_of = liq["Date"].max()
print(f"As of {as_of.date()}\n")

# --- Liquidity ---------------------------------------------------------------
today = liq[liq["Date"] == as_of]
cash = today["Balance_CHF"].sum()
outside = today.loc[today["EntityKey"] != "SIG-CH01", "Balance_CHF"].sum()
print(f"Cash                      CHF {cash / 1e6:6.1f}m")
print(f"Outside the in-house bank CHF {outside / 1e6:6.1f}m  ({outside / cash:.1%})")

# --- Counterparty limits -----------------------------------------------------
exposure = (
    liq[liq["CounterpartyType"] == "Bank"]
    .groupby(["Date", "BankKey"])["Balance_CHF"].sum()
    .unstack(fill_value=0)
)
util = exposure.div(bank["CounterpartyLimit_CHF"])
print(f"\nMax bank utilisation today: {util.loc[as_of].max():.1%}")

pl = util["B06"]  # Regional Bank PL
print("Regional Bank PL")
print(f"  limit CHF {bank.loc['B06', 'CounterpartyLimit_CHF'] / 1e6:.0f}m, "
      f"peak exposure CHF {exposure['B06'].max() / 1e6:.2f}m = {pl.max():.1%} on {pl.idxmax().date()}")
first80, first100 = pl[pl > 0.8].index.min(), pl[pl > 1].index.min()
print(f"  first above 80%: {first80.date()}, first above 100%: {first100.date()} "
      f"({(first100 - first80).days / 7:.1f} weeks later)")
print(f"  days above 100%: {int((pl > 1).sum())}")

latest_spread = spreads[spreads["Date"] == spreads["Date"].max()].set_index("BankKey")["CreditSpread_bps"]
print(f"  credit spread {spreads[spreads['BankKey'] == 'B06']['CreditSpread_bps'].iloc[0]:.1f} -> "
      f"{latest_spread['B06']:.1f} bps (other banks {latest_spread.drop('B06').min():.1f}-"
      f"{latest_spread.drop('B06').max():.1f})")

# --- Forecast quality --------------------------------------------------------
# WAPE: sum of absolute errors / sum of absolute 1-week actuals (same base for every horizon)
fc["abs_err"] = (fc["Forecast_CHF"] - fc["Actual_CHF"]).abs()
base = fc.loc[fc["HorizonWeeks"] == 1, "Actual_CHF"].abs().sum()
wape = {h: fc.loc[fc["HorizonWeeks"] == h, "abs_err"].sum() / base for h in (1, 4, 13)}
print("\nForecast WAPE   " + "  ".join(f"{h}w {v:.1%}" for h, v in wape.items()))

receipts = fc[fc["FlowCategory"] == "Customer receipts"]
actual = receipts.loc[receipts["HorizonWeeks"] == 1, "Actual_CHF"].sum()
bias = {h: receipts.loc[receipts["HorizonWeeks"] == h, "Forecast_CHF"].sum() / actual - 1 for h in (1, 4, 13)}
print("Receipts bias   " + "  ".join(f"{h}w {v:+.1%}" for h, v in bias.items()))

# Cumulative net cash flow over the last 13 weeks (intercompany excluded)
net = fc[fc["FlowCategory"] != "Intercompany"]
weeks = sorted(net["WeekStart"].unique())[-13:]
last13 = net[net["WeekStart"].isin(weeks)]
print(f"\nLast 13 weeks ({pd.Timestamp(weeks[0]).date()} to {pd.Timestamp(weeks[-1]).date()}), cumulative net, CHF m")
print(f"  actual        {last13.loc[last13['HorizonWeeks'] == 1, 'Actual_CHF'].sum() / 1e6:7.1f}")
for h in (1, 4, 13):
    print(f"  forecast {h:>2}w  {last13.loc[last13['HorizonWeeks'] == h, 'Forecast_CHF'].sum() / 1e6:7.1f}")
