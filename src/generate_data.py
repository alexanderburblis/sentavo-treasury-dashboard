"""
Synthetic treasury dataset generator
====================================

Builds a fully synthetic dataset for a FICTIONAL company, Sentavo Industrial
Group AG, to power a Group Treasury liquidity & bank-relationship dashboard
in Power BI.

Nothing in this dataset comes from a real company, bank or market feed.
Banks are anonymised by role (Core Bank 1-4, Regional Bank CH/PL/SG).
Interest-rate and FX paths are illustrative and are not market data.

Run:  python src/generate_data.py
Out:  data/sentavo_treasury_dataset.xlsx  (+ one CSV per table)

Tables: dimensions, daily positions, deals, fees, issues, spreads, the 13-week
cash forecast, a monthly treasury P&L (actual, budget, Q1 and Q2 reforecasts)
and a user-to-entity table for row-level security.
"""

from pathlib import Path
import numpy as np
import pandas as pd

SEED = 20261111
rng = np.random.default_rng(SEED)

START, END = "2024-10-01", "2026-09-30"
DAYS = pd.bdate_range(START, END)
AS_OF = DAYS[-1]
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
dim_entity = pd.DataFrame([
    # key,       legal name,                              country, ccy,  role
    ("SIG-CH01", "Sentavo Industrial Group AG",            "CH", "CHF", "Holding & in-house bank"),
    ("SIG-CH02", "Sentavo Manufacturing AG",               "CH", "CHF", "Operating company"),
    ("SIG-DE01", "Sentavo Deutschland GmbH",               "DE", "EUR", "Operating company"),
    ("SIG-FR01", "Sentavo France SAS",                     "FR", "EUR", "Sales company"),
    ("SIG-IT01", "Sentavo Italia S.r.l.",                  "IT", "EUR", "Sales company"),
    ("SIG-PL01", "Sentavo Polska Sp. z o.o.",              "PL", "PLN", "Operating company"),
    ("SIG-US01", "Sentavo Americas Inc.",                  "US", "USD", "Operating company"),
    ("SIG-SG01", "Sentavo Asia Pacific Pte. Ltd.",         "SG", "SGD", "Sales company"),
], columns=["EntityKey", "EntityName", "Country", "FunctionalCurrency", "Role"])

dim_bank = pd.DataFrame([
    # key,  label,              tier,     segment,                          country, rating, outlook,   limit CHF m, spread base bps
    ("B01", "Core Bank 1",       "Core",     "Global cash management",       "CH", "A+",   "Stable",   150, 48),
    ("B02", "Core Bank 2",       "Core",     "Global cash management",       "US", "AA-",  "Stable",   110, 40),
    ("B03", "Core Bank 3",       "Core",     "European relationship bank",   "DE", "A",    "Positive",  90, 70),
    ("B04", "Core Bank 4",       "Core",     "European relationship bank",   "FR", "A+",   "Stable",   100, 55),
    ("B05", "Regional Bank CH",  "Regional", "Domestic bank",                "CH", "AA",   "Stable",   100, 30),
    ("B06", "Regional Bank PL",  "Regional", "Local bank",                   "PL", "BBB+", "Stable",    12, 115),
    ("B07", "Regional Bank SG",  "Regional", "Local bank",                   "SG", "AA-",  "Stable",    30, 38),
], columns=["BankKey", "BankLabel", "Tier", "Segment", "Country", "Rating",
            "Outlook", "CounterpartyLimit_CHF_m", "_spread_base"])
RATING_ORDER = {"AA": 1, "AA-": 2, "A+": 3, "A": 4, "BBB+": 5}
dim_bank["RatingSort"] = dim_bank["Rating"].map(RATING_ORDER)
dim_bank["CounterpartyLimit_CHF"] = dim_bank["CounterpartyLimit_CHF_m"] * 1_000_000

dim_fund = pd.DataFrame([
    ("F01", "Core Bank 2 USD Treasury MMF",           "B02", "USD", "Public Debt CNAV", "AAAmmf", "AAA",     -0.12, 45e6),
    ("F02", "Core Bank 4 EUR Liquidity MMF",          "B04", "EUR", "LVNAV",            "AAAmmf", "AAA",     -0.08, 40e6),
    ("F03", "Core Bank 1 EUR Liquidity MMF",          "B01", "EUR", "LVNAV",            "AAAmmf", "AAA",     -0.10, 30e6),
    ("F04", "Core Bank 1 EUR Short-Term VNAV MMF",    "B01", "EUR", "Standard VNAV",    "AA+f",   "Non-AAA",  0.12, 15e6),
], columns=["FundKey", "FundName", "SponsorBankKey", "Currency", "FundType",
            "FundRating", "RatingBucket", "_spread_pct", "_target"])

dim_currency = pd.DataFrame([
    ("CHF", "Swiss franc"), ("EUR", "Euro"), ("USD", "US dollar"),
    ("PLN", "Polish zloty"), ("SGD", "Singapore dollar"), ("GBP", "Pound sterling"),
], columns=["CurrencyCode", "CurrencyName"])


# ---------------------------------------------------------------------------
# Market data (illustrative paths, NOT real market data)
# ---------------------------------------------------------------------------
def step_path(steps):
    """steps: list of (date, level). Returns a Series over DAYS."""
    s = pd.Series(np.nan, index=DAYS)
    for d, v in steps:
        s[s.index >= pd.Timestamp(d)] = v
    return s.ffill()

bench = {
    ("SARON", "CHF"): step_path([(START, 0.95), ("2024-12-13", 0.45), ("2025-03-21", 0.20),
                                 ("2025-06-20", -0.05)]),
    ("€STR", "EUR"):  step_path([(START, 3.16), ("2024-10-23", 3.16), ("2024-12-18", 2.91),
                                 ("2025-02-05", 2.66), ("2025-03-12", 2.41), ("2025-04-23", 2.16),
                                 ("2025-06-11", 1.92)]),
    ("SOFR", "USD"):  step_path([(START, 4.85), ("2024-11-08", 4.60), ("2024-12-19", 4.33),
                                 ("2025-09-18", 4.10), ("2025-10-30", 3.87), ("2025-12-11", 3.62)]),
}
bench_rows = []
for (name, ccy), s in bench.items():
    noisy = s + rng.normal(0, 0.012, len(s))
    bench_rows.append(pd.DataFrame({"Date": DAYS, "Benchmark": name, "Currency": ccy,
                                    "Rate_pct": noisy.round(3).values}))
benchmark_rates = pd.concat(bench_rows, ignore_index=True)
BENCH = {ccy: s for (_, ccy), s in bench.items()}

fx_spec = {"EUR": (0.940, 0.930), "USD": (0.860, 0.805), "PLN": (0.218, 0.219),
           "SGD": (0.650, 0.625), "GBP": (1.120, 1.075)}
fx = {"CHF": pd.Series(1.0, index=DAYS)}
n = len(DAYS)
for ccy, (a, b) in fx_spec.items():
    vol = 0.0030 if ccy in ("EUR", "PLN") else 0.0045
    shocks = rng.normal(0, vol, n)
    walk = np.cumsum(shocks)
    walk = walk - np.linspace(0, walk[-1], n)          # pin the end point
    drift = np.log(np.linspace(a, b, n))
    fx[ccy] = pd.Series(np.exp(drift + walk), index=DAYS)
fx_rates = pd.concat([pd.DataFrame({"Date": DAYS, "CurrencyCode": c, "CHF_per_unit": s.round(5).values})
                      for c, s in fx.items()], ignore_index=True)


# ---------------------------------------------------------------------------
# Operating & treasury-centre bank accounts (current + notice)
# ---------------------------------------------------------------------------
# entity, bank, ccy, instrument, mean balance (LC m), volatility (LC m)
accounts = [
    ("SIG-CH01", "B01", "CHF", "Current account", 18, 4), ("SIG-CH01", "B01", "EUR", "Current account", 10, 3),
    ("SIG-CH01", "B02", "USD", "Current account", 12, 3), ("SIG-CH01", "B04", "EUR", "Current account", 8, 2),
    ("SIG-CH01", "B05", "CHF", "Current account", 12, 3), ("SIG-CH01", "B03", "EUR", "Current account", 6, 2),
    ("SIG-CH01", "B05", "CHF", "Notice account", 25, 0), ("SIG-CH01", "B01", "CHF", "Notice account", 20, 0),
    ("SIG-CH02", "B05", "CHF", "Current account", 14, 4), ("SIG-CH02", "B01", "CHF", "Current account", 6, 2),
    ("SIG-CH02", "B01", "EUR", "Current account", 4, 1.5),
    ("SIG-DE01", "B03", "EUR", "Current account", 22, 6), ("SIG-DE01", "B04", "EUR", "Current account", 6, 2),
    ("SIG-FR01", "B04", "EUR", "Current account", 14, 4),
    ("SIG-IT01", "B04", "EUR", "Current account", 7, 2), ("SIG-IT01", "B03", "EUR", "Current account", 3, 1),
    ("SIG-PL01", "B06", "PLN", "Current account", 26, 5), ("SIG-PL01", "B03", "EUR", "Current account", 2, 0.6),
    ("SIG-US01", "B02", "USD", "Current account", 24, 6),
    ("SIG-SG01", "B07", "SGD", "Current account", 14, 3), ("SIG-SG01", "B02", "USD", "Current account", 3, 1),
]

def month_end_bump(days):
    """Receipts cluster in the last 3 business days of each month."""
    ser = pd.Series(days)
    last = ser.groupby([ser.dt.year, ser.dt.month]).transform("max")
    gap = (last - ser).dt.days
    return np.where(gap <= 4, 1.0, 0.0)

bump = month_end_bump(DAYS)
pos_rows = []
for ent, bank, ccy, inst, mu, sd in accounts:
    if inst == "Notice account":
        # stepped monthly changes, held between 60% and 140% of mean
        lvl = np.empty(n); cur = mu
        for i, d in enumerate(DAYS):
            if i == 0 or d.month != DAYS[i - 1].month:
                cur = float(np.clip(cur + rng.normal(0, mu * 0.12), mu * 0.6, mu * 1.4))
            lvl[i] = cur
        bal = lvl
    else:
        x = np.empty(n); x[0] = mu
        for i in range(1, n):
            x[i] = x[i - 1] + 0.18 * (mu - x[i - 1]) + rng.normal(0, sd * 0.45) + bump[i] * sd * 0.5
        bal = np.maximum(x, mu * 0.15)
    bal = pd.Series(bal, index=DAYS)

    # Story: Polish subsidiary cash builds up in H1 2025, breaching the local bank
    # limit in June/July, then is up-streamed to the holding in August 2025.
    if ent == "SIG-PL01" and bank == "B06":
        build = np.interp(DAYS.astype("int64"),
                          pd.to_datetime(["2025-02-01", "2025-06-15", "2025-07-25", "2025-08-15"]).astype("int64"),
                          [0, 34, 36, 0], left=0, right=0)
        bal = bal + build

    # Story: dividend season — holding CHF balances run down ahead of mid-April payment.
    if ent == "SIG-CH01" and ccy == "CHF" and inst == "Current account":
        for yr in (2025, 2026):
            pay = pd.Timestamp(f"{yr}-04-15")
            mask = (DAYS >= pay) & (DAYS < pay + pd.Timedelta(days=21))
            bal[mask] = bal[mask] * 0.45

    pos_rows.append(pd.DataFrame({
        "Date": DAYS, "EntityKey": ent, "BankKey": bank, "FundKey": None,
        "Instrument": inst, "CounterpartyType": "Bank", "Currency": ccy,
        "Balance_LC": bal.values * 1e6,
    }))
acct_pos = pd.concat(pos_rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Deposit quotes (monthly bank quotes vs benchmark) — drives deposit placement
# ---------------------------------------------------------------------------
TENORS = {"1M": 1, "3M": 3, "6M": 6, "9M": 9, "12M": 12}
TERM_PREM = {"1M": 0.00, "3M": 0.03, "6M": 0.06, "9M": 0.08, "12M": 0.10}
QUOTE_SPREAD = {  # pct points vs benchmark; None = bank does not quote
    "CHF": {"B01": -0.02, "B02": None, "B03": -0.10, "B04": -0.08, "B05": 0.05},
    "EUR": {"B01": -0.05, "B02": -0.08, "B03": 0.04, "B04": 0.00, "B05": -0.10},
    "USD": {"B01": -0.03, "B02": 0.03, "B03": -0.06, "B04": -0.04, "B05": None},
}
months = pd.date_range(START, END, freq="MS")
q_rows = []
for m in months:
    d0 = DAYS[DAYS >= m][0]
    for ccy, banks in QUOTE_SPREAD.items():
        b = BENCH[ccy][d0]
        for bank, spr in banks.items():
            if spr is None:
                continue
            drift = rng.normal(0, 0.025)
            for t in TENORS:
                if ccy == "CHF" and bank == "B03" and t == "12M":
                    continue  # bank does not quote 12M CHF
                rate = b + spr + TERM_PREM[t] + drift + rng.normal(0, 0.015)
                if ccy == "CHF":
                    rate = max(rate, 0.0)  # corporate CHF deposits floored at zero
                q_rows.append((m, bank, ccy, t, TENORS[t], round(rate, 3)))
deposit_quotes = pd.DataFrame(q_rows, columns=["QuoteMonth", "BankKey", "Currency", "Tenor",
                                               "TenorMonths", "QuotedRate_pct"])
QUOTE_IDX = deposit_quotes.set_index(["QuoteMonth", "BankKey", "Currency", "Tenor"])["QuotedRate_pct"]


# ---------------------------------------------------------------------------
# Term deposits (deal level), placed by the in-house bank within counterparty limits
# ---------------------------------------------------------------------------
lim = dim_bank.set_index("BankKey")["CounterpartyLimit_CHF"]
acct_pos["Balance_CHF"] = acct_pos["Balance_LC"] * acct_pos.apply(
    lambda r: fx[r["Currency"]][r["Date"]], axis=1)
acct_exposure = acct_pos.groupby(["Date", "BankKey"])["Balance_CHF"].sum().unstack(fill_value=0)

def dep_target(ccy, d):
    base = {"CHF": 60e6, "EUR": 95e6, "USD": 45e6}[ccy]
    if ccy == "CHF":  # CHF deposits run off once SARON reaches zero
        base = np.interp(d.value, [pd.Timestamp("2025-03-01").value, pd.Timestamp("2025-08-01").value],
                         [60e6, 8e6])
    if ccy == "EUR" and d.month in (3, 4):  # liquidity held short ahead of dividend
        base *= 0.65
    return base

INTERNAL_CAP = 0.80  # treasury policy: place new deposits only up to 80% of a bank limit
deals, live = [], []
deal_id = 1
for d in DAYS:
    live = [x for x in live if x["MaturityDate"] > d]
    exp_dep = {}
    for x in live:
        exp_dep[x["BankKey"]] = exp_dep.get(x["BankKey"], 0) + x["Principal_LC"] * fx[x["Currency"]][d]
    for ccy in ("CHF", "EUR", "USD"):
        out = sum(x["Principal_LC"] for x in live if x["Currency"] == ccy)
        tgt = dep_target(ccy, d)
        tries = 0
        while out < tgt * 0.92 and tries < 3:
            tries += 1
            size = float(np.clip(rng.lognormal(np.log(10e6), 0.45), 3e6, 30e6))
            size = round(size / 1e6) * 1e6
            tenor = rng.choice(list(TENORS), p=[0.20, 0.35, 0.25, 0.10, 0.10])
            qm = pd.Timestamp(d.year, d.month, 1)
            cands = []
            for bank in QUOTE_SPREAD[ccy]:
                key = (qm, bank, ccy, tenor)
                if key not in QUOTE_IDX.index:
                    continue
                used = acct_exposure.loc[d, bank] + exp_dep.get(bank, 0)
                head = INTERNAL_CAP * lim[bank] - used   # keep a buffer below the hard limit
                if head >= size * fx[ccy][d]:
                    cands.append((QUOTE_IDX[key] + rng.normal(0, 0.01), bank))
            if not cands:
                break
            cands.sort(reverse=True)
            rate, bank = cands[0] if rng.random() > 0.2 or len(cands) == 1 else cands[1]
            if ccy == "CHF":
                rate = max(rate, 0.0)
            mat = d + pd.DateOffset(months=TENORS[tenor])
            x = {"DealID": f"TD-{deal_id:05d}", "EntityKey": "SIG-CH01", "BankKey": bank,
                 "Currency": ccy, "Principal_LC": size, "StartDate": d, "MaturityDate": mat,
                 "Tenor": tenor, "TenorMonths": TENORS[tenor], "InterestRate_pct": round(float(rate), 3)}
            deal_id += 1
            deals.append(x); live.append(x)
            exp_dep[bank] = exp_dep.get(bank, 0) + size * fx[ccy][d]
            out += size

deposits = pd.DataFrame(deals)
deposits["DayCount"] = np.where(deposits["Currency"] == "USD", 360, 360)
deposits["Interest_LC"] = (deposits["Principal_LC"] * deposits["InterestRate_pct"] / 100 *
                           (deposits["MaturityDate"] - deposits["StartDate"]).dt.days / deposits["DayCount"]).round(2)
deposits["Status"] = np.where(deposits["MaturityDate"] > AS_OF, "Outstanding", "Matured")

# daily outstanding deposits -> position table
dep_daily = []
for _, x in deposits.iterrows():
    live_days = DAYS[(DAYS >= x["StartDate"]) & (DAYS < x["MaturityDate"])]
    dep_daily.append(pd.DataFrame({"Date": live_days, "EntityKey": x["EntityKey"], "BankKey": x["BankKey"],
                                   "Currency": x["Currency"], "Balance_LC": x["Principal_LC"]}))
dep_pos = (pd.concat(dep_daily).groupby(["Date", "EntityKey", "BankKey", "Currency"], as_index=False)
           ["Balance_LC"].sum())
dep_pos["FundKey"] = None
dep_pos["Instrument"] = "Term deposit"
dep_pos["CounterpartyType"] = "Bank"


# ---------------------------------------------------------------------------
# Money market funds (daily holdings and 7-day yield)
# ---------------------------------------------------------------------------
mmf_rows, mmf_yield_rows = [], []
for _, f in dim_fund.iterrows():
    tgt = f["_target"]; x = np.empty(n); x[0] = tgt
    for i in range(1, n):
        d = DAYS[i]
        t = tgt * (0.55 if (f["Currency"] == "EUR" and d.month in (3, 4)) else 1.0)
        x[i] = x[i - 1] + 0.05 * (t - x[i - 1]) + rng.normal(0, tgt * 0.02)
    x = np.maximum(x, tgt * 0.2)
    b = BENCH[f["Currency"]]
    noise = 0.06 if f["FundType"] == "Standard VNAV" else 0.015
    y = b + f["_spread_pct"] + rng.normal(0, noise, n)
    mmf_rows.append(pd.DataFrame({"Date": DAYS, "EntityKey": "SIG-CH01", "BankKey": f["SponsorBankKey"],
                                  "FundKey": f["FundKey"], "Instrument": "Money market fund",
                                  "CounterpartyType": "Fund", "Currency": f["Currency"],
                                  "Balance_LC": (x / 1e5).round() * 1e5}))
    mmf_yield_rows.append(pd.DataFrame({"Date": DAYS, "FundKey": f["FundKey"],
                                        "Yield7d_pct": np.round(y.values, 3)}))
mmf_pos = pd.concat(mmf_rows, ignore_index=True)
mmf_yields = pd.concat(mmf_yield_rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Combined daily liquidity position
# ---------------------------------------------------------------------------
cols = ["Date", "EntityKey", "BankKey", "FundKey", "Instrument", "CounterpartyType", "Currency", "Balance_LC"]
position = pd.concat([acct_pos[cols], dep_pos[cols], mmf_pos[cols]], ignore_index=True)
fx_lookup = fx_rates.set_index(["Date", "CurrencyCode"])["CHF_per_unit"]
position["Balance_LC"] = position["Balance_LC"].round(0)
position["Balance_CHF"] = (position["Balance_LC"] *
                           fx_lookup.reindex(list(zip(position["Date"], position["Currency"]))).values).round(0)
position = position.sort_values(["Date", "EntityKey", "Instrument", "BankKey"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# FX deals
# ---------------------------------------------------------------------------
pairs = {  # pair: (weight, base spread bps, eligible banks with weights, default entity)
    "EUR/CHF": (0.35, 2.0, {"B01": .30, "B02": .20, "B03": .15, "B04": .22, "B05": .13}, "SIG-CH01"),
    "USD/CHF": (0.25, 2.5, {"B01": .30, "B02": .32, "B03": .10, "B04": .18, "B05": .10}, "SIG-CH01"),
    "EUR/USD": (0.15, 1.5, {"B01": .25, "B02": .30, "B03": .20, "B04": .25}, "SIG-CH01"),
    "EUR/PLN": (0.10, 8.0, {"B03": .45, "B06": .35, "B04": .20}, "SIG-PL01"),
    "USD/SGD": (0.08, 5.0, {"B02": .55, "B07": .45}, "SIG-SG01"),
    "GBP/CHF": (0.07, 3.0, {"B01": .45, "B04": .35, "B02": .20}, "SIG-CH01"),
}
bank_factor = {"B01": 1.0, "B02": 0.9, "B03": 1.15, "B04": 1.0, "B05": 1.3, "B06": 1.6, "B07": 1.2}
pair_names = list(pairs); pw = np.array([pairs[p][0] for p in pair_names]); pw /= pw.sum()
fx_rows = []
k = 1
for d in DAYS:
    for _ in range(rng.poisson(1.4)):
        p = rng.choice(pair_names, p=pw)
        _, base_spr, banks, ent = pairs[p]
        bk = list(banks); bw = np.array([banks[b] for b in bk]); bw /= bw.sum()
        bank = rng.choice(bk, p=bw)
        dtype = rng.choice(["Spot", "Forward", "Swap"], p=[0.5, 0.35, 0.15])
        tenor = "Spot" if dtype == "Spot" else rng.choice(["1M", "3M", "6M", "12M"], p=[.3, .4, .2, .1])
        months_ = 0 if tenor == "Spot" else TENORS[tenor]
        value = d + pd.offsets.BDay(2) if tenor == "Spot" else d + pd.DateOffset(months=months_)
        base_ccy = p.split("/")[0]
        notional = float(np.clip(rng.lognormal(np.log(3e6), 0.8), 2e5, 40e6))
        notional = round(notional / 1e5) * 1e5
        fx_rows.append({
            "DealID": f"FX-{k:05d}", "TradeDate": d, "ValueDate": pd.Timestamp(value).normalize(),
            "EntityKey": ent if rng.random() > 0.3 else "SIG-CH01", "BankKey": bank,
            "CurrencyPair": p, "BaseCurrency": base_ccy, "DealType": dtype, "Tenor": tenor,
            "BuySell_Base": rng.choice(["Buy", "Sell"]), "Notional_Base": notional,
            "Notional_CHF": round(notional * fx[base_ccy][d]),
            "Spread_bps": round(float(base_spr * bank_factor[bank] * rng.lognormal(0, 0.25)), 2),
            "ExecutionChannel": rng.choice(["Multi-bank platform", "Bilateral (phone)"], p=[0.85, 0.15]),
        })
        k += 1
fx_deals = pd.DataFrame(fx_rows)
fx_deals["DealSizeBand"] = pd.cut(fx_deals["Notional_CHF"], [0, 1e6, 5e6, 10e6, 1e12],
                                  labels=["< CHF 1m", "CHF 1–5m", "CHF 5–10m", "> CHF 10m"]).astype(str)


# ---------------------------------------------------------------------------
# Bank fees (monthly)
# ---------------------------------------------------------------------------
fee_base = {  # CHF thousand per month
    "B01": {"Account maintenance": 6.0, "Payments & collections": 14.0, "Cash pooling": 5.0, "Connectivity & eBanking": 4.0},
    "B02": {"Account maintenance": 4.0, "Payments & collections": 10.0, "Connectivity & eBanking": 6.0},
    "B03": {"Account maintenance": 3.0, "Payments & collections": 7.0, "Connectivity & eBanking": 2.0},
    "B04": {"Account maintenance": 4.0, "Payments & collections": 9.0, "Cash pooling": 2.0, "Connectivity & eBanking": 2.0},
    "B05": {"Account maintenance": 2.0, "Payments & collections": 5.0, "Connectivity & eBanking": 1.0},
    "B06": {"Account maintenance": 0.8, "Payments & collections": 2.2, "Connectivity & eBanking": 0.4},
    "B07": {"Account maintenance": 1.0, "Payments & collections": 2.5, "Connectivity & eBanking": 0.6},
}
fee_rows = []
for m in months:
    for bank, cats in fee_base.items():
        for cat, base in cats.items():
            amt = base * (1 + rng.normal(0, 0.08 if cat.startswith("Payments") else 0.03))
            if bank == "B03" and cat.startswith("Payments") and m >= pd.Timestamp("2026-01-01"):
                amt *= 1.25   # tariff increase
            if bank == "B01" and cat.startswith("Connectivity") and m >= pd.Timestamp("2025-07-01"):
                amt *= 0.85   # renegotiated
            fee_rows.append((m, bank, cat, round(amt * 1000, 2)))
bank_fees = pd.DataFrame(fee_rows, columns=["FeeMonth", "BankKey", "FeeCategory", "Amount_CHF"])


# ---------------------------------------------------------------------------
# Bank service issue log
# ---------------------------------------------------------------------------
issue_templates = {
    "Payments": ["Payment batch rejected – invalid creditor BIC", "Urgent payment executed after cut-off",
                 "Cross-border payment returned by intermediary", "Duplicate debit on outgoing payment"],
    "Statements": ["End-of-day statement missing for D-1", "Intraday statement delayed",
                   "Statement balance mismatch vs eBanking"],
    "Connectivity": ["Host-to-host channel unavailable", "Certificate renewal failed",
                     "File acknowledgement not received"],
    "eBanking access": ["User token reset delayed", "New user set-up pending", "Signing rights not applied"],
    "KYC & onboarding": ["Signatory update pending KYC refresh", "Account opening documents re-requested",
                         "Periodic KYC review – additional documents"],
    "Fees & billing": ["Fee charged twice", "Fee not in line with agreed tariff", "Missing fee statement"],
}
area_w = {"Payments": .30, "Statements": .20, "Connectivity": .15, "eBanking access": .12,
          "KYC & onboarding": .13, "Fees & billing": .10}
area_factor = {"Payments": 1.0, "Statements": 0.6, "Connectivity": 1.3, "eBanking access": 0.9,
               "KYC & onboarding": 2.5, "Fees & billing": 1.6}
bank_w = {"B01": .20, "B02": .17, "B03": .22, "B04": .17, "B05": .08, "B06": .10, "B07": .06}
bank_res = {"B01": 3, "B02": 4, "B03": 7, "B04": 5, "B05": 3, "B06": 12, "B07": 6}
iss_rows = []
for i in range(124):
    bank = rng.choice(list(bank_w), p=list(bank_w.values()))
    area = rng.choice(list(area_w), p=list(area_w.values()))
    opened = DAYS[rng.integers(0, n)] if i < 116 else DAYS[rng.integers(n - 20, n)]  # a few recent, still open
    res_days = max(1, int(round(rng.lognormal(np.log(bank_res[bank] * area_factor[area]), 0.5))))
    closed = opened + pd.Timedelta(days=res_days)
    sev = rng.choice(["Low", "Medium", "High"], p=[0.45, 0.4, 0.15])
    if closed <= AS_OF and i < 116:
        status, close_val, days_val = "Closed", closed, res_days
    else:
        status = "In progress" if rng.random() < 0.6 else "Open"
        close_val, days_val = pd.NaT, None
    ent = rng.choice(dim_entity["EntityKey"])
    iss_rows.append({"IssueID": f"ISS-{i + 1:04d}", "BankKey": bank, "EntityKey": ent, "Area": area,
                     "Description": rng.choice(issue_templates[area]), "Severity": sev,
                     "OpenDate": opened, "CloseDate": close_val, "Status": status,
                     "ResolutionDays": days_val})
bank_issues = pd.DataFrame(iss_rows).sort_values("OpenDate").reset_index(drop=True)
bank_issues["IssueID"] = [f"ISS-{i + 1:04d}" for i in range(len(bank_issues))]


# ---------------------------------------------------------------------------
# Credit spreads (synthetic 5Y CDS-style, bps)
# ---------------------------------------------------------------------------
common = np.zeros(n)
for i in range(1, n):
    common[i] = 0.97 * common[i - 1] + rng.normal(0, 0.02)
stress = np.exp(-np.maximum(0, (DAYS - pd.Timestamp("2025-04-07")).days.values) / 25.0)
stress[DAYS < pd.Timestamp("2025-04-07")] = 0
cs_rows = []
for _, b in dim_bank.iterrows():
    idio = np.zeros(n)
    for i in range(1, n):
        idio[i] = 0.98 * idio[i - 1] + rng.normal(0, 0.015)
    trend = np.linspace(0, -0.12 if b["Outlook"] == "Positive" else (0.15 if b["BankKey"] == "B06" else 0), n)
    s = b["_spread_base"] * np.exp(common + idio + trend + 0.35 * stress)
    cs_rows.append(pd.DataFrame({"Date": DAYS, "BankKey": b["BankKey"], "CreditSpread_bps": s.round(1)}))
credit_spreads = pd.concat(cs_rows, ignore_index=True)


# ---------------------------------------------------------------------------
# 13-week cash-flow forecast vs actual (weekly, by entity & flow category)
# ---------------------------------------------------------------------------
weeks = pd.date_range("2024-10-07", END, freq="W-MON")
rev = {"SIG-CH02": 9, "SIG-DE01": 10, "SIG-FR01": 5, "SIG-IT01": 3.5, "SIG-PL01": 2.5,
       "SIG-US01": 8, "SIG-SG01": 3}  # weekly receipts, CHF m
H = {1: (0.00, 0.04), 4: (0.02, 0.09), 13: (0.05, 0.18)}  # horizon: (optimism bias on receipts, error sd)
fc_rows = []
for w in weeks:
    season = 1 + 0.12 * np.sin(2 * np.pi * (w.dayofyear / 365.0))
    month_end = (w + pd.Timedelta(days=6)).month != w.month
    for ent, r in rev.items():
        rec = r * season * (1.5 if month_end else 0.9) * rng.lognormal(0, 0.10)
        flows = {
            "Customer receipts": rec,
            "Supplier payments": -0.55 * r * season * rng.lognormal(0, 0.12),
            "Payroll": -0.95 * r if (w.day <= 25 <= w.day + 6) else 0.0,
            "Taxes": -0.6 * r if (w.month in (3, 6, 9, 12) and month_end) else 0.0,
            "Capex": -r * rng.choice([0, 0, 0, 0.4, 1.2]),
            "Intercompany": -0.25 * r * 4 if month_end else 0.0,
        }
        for cat, act in flows.items():
            for h, (bias, sd) in H.items():
                if act == 0:
                    f = 0.0 if rng.random() > 0.05 else -0.2 * r  # occasional phantom forecast
                else:
                    b_ = bias if cat == "Customer receipts" else 0.0
                    sd_ = sd * (0.25 if cat == "Payroll" else (2.0 if cat == "Capex" else 1.0))
                    f = act * (1 + b_ + rng.normal(0, sd_))
                fc_rows.append((w, ent, cat, h, round(f * 1e6), round(act * 1e6)))
    # holding company receives intercompany sweeps and pays the dividend in April
    ic_in = 0.25 * sum(rev.values()) * 4 if month_end else 0.0
    div = -110.0 if (w.month == 4 and w.day <= 15 < w.day + 7) else 0.0
    for cat, act in {"Intercompany": ic_in, "Dividends": div, "Taxes": -1.5 if month_end else 0.0}.items():
        for h, (_, sd) in H.items():
            f = act * (1 + rng.normal(0, sd * 0.5)) if act else 0.0
            fc_rows.append((w, "SIG-CH01", cat, h, round(f * 1e6), round(act * 1e6)))
cash_forecast = pd.DataFrame(fc_rows, columns=["WeekStart", "EntityKey", "FlowCategory", "HorizonWeeks",
                                               "Forecast_CHF", "Actual_CHF"])
cash_forecast["Direction"] = np.where(cash_forecast["Actual_CHF"] + cash_forecast["Forecast_CHF"] >= 0,
                                      "Inflow", "Outflow")


# ---------------------------------------------------------------------------
# Treasury P&L: actual, budget and reforecasts (monthly)
# ---------------------------------------------------------------------------
# Built from the tables above, so actuals tie back to deposits, MMF holdings,
# FX deals and bank fees. A separate random stream keeps every table above
# identical to earlier versions of the dataset.
#
# Sign convention: income positive, cost negative. Variance = actual - plan,
# so a positive variance is always favourable.
rng_plan = np.random.default_rng(SEED + 1)
CAL = pd.date_range(START, END, freq="D")                  # calendar days for accruals
fx_cal = {c: s.reindex(CAL).ffill() for c, s in fx.items()}
month_of = lambda s: s.dt.to_period("M").dt.to_timestamp()

# 1 Interest income -----------------------------------------------------------
# Term deposits: daily accrual principal x rate / 360, booked to the month it accrues in.
td_acc = []
for _, x in deposits.iterrows():
    days = CAL[(CAL >= x["StartDate"]) & (CAL < x["MaturityDate"])]
    if len(days) == 0:
        continue
    td_acc.append(pd.DataFrame({
        "Date": days, "EntityKey": x["EntityKey"], "BankKey": x["BankKey"], "Category": "Term deposits",
        "Amount_CHF": x["Principal_LC"] * x["InterestRate_pct"] / 100 / 360 * fx_cal[x["Currency"]][days].values,
    }))
def to_calendar(df, keys, value_cols):
    """Carry business-day rows over weekends and holidays, per key."""
    out = []
    for k, g in df.groupby(keys):
        g = g.set_index("Date")[value_cols].reindex(CAL).ffill().dropna()
        g.index.name = "Date"
        g = g.reset_index()
        for col, val in zip(keys, k if isinstance(k, tuple) else (k,)):
            g[col] = val
        out.append(g)
    return pd.concat(out, ignore_index=True)

def chf(df, amount):
    rate = np.array([fx_cal[c][d] for c, d in zip(df["Currency"], df["Date"])])
    return amount * rate

# MMFs: holding x 7-day yield / 365, carried over weekends.
mmf_cal = to_calendar(mmf_pos.merge(mmf_yields, on=["Date", "FundKey"]),
                      ["FundKey", "BankKey", "Currency"], ["Balance_LC", "Yield7d_pct"])
mmf_cal["Amount_CHF"] = chf(mmf_cal, mmf_cal["Balance_LC"] * mmf_cal["Yield7d_pct"] / 100 / 365)
mmf_cal["EntityKey"], mmf_cal["Category"] = "SIG-CH01", "Money market funds"
# Notice accounts pay the benchmark less 10 bps, floored at zero. Current accounts pay nothing.
notice = to_calendar(acct_pos[acct_pos["Instrument"] == "Notice account"],
                     ["EntityKey", "BankKey", "Currency"], ["Balance_LC"])
bench_cal = {c: s.reindex(CAL).ffill() for c, s in BENCH.items()}
notice["Rate"] = [max(bench_cal[c][d] - 0.10, 0.0) for c, d in zip(notice["Currency"], notice["Date"])]
notice["Amount_CHF"] = chf(notice, notice["Balance_LC"] * notice["Rate"] / 100 / 365)
notice["Category"] = "Notice accounts"

pnl_cols = ["Month", "EntityKey", "BankKey", "Line", "Category", "Amount_CHF"]
interest = pd.concat(td_acc + [mmf_cal, notice], ignore_index=True).dropna(subset=["Amount_CHF"])
interest["Month"], interest["Line"] = month_of(interest["Date"]), "Interest income"

# 2 Bank fees -------------------------------------------------------------------
# Billed per bank; allocated to entities by the number of accounts each holds there.
acct_df = pd.DataFrame(accounts, columns=["EntityKey", "BankKey", "Currency", "Instrument", "_mu", "_sd"])
alloc = acct_df.groupby(["BankKey", "EntityKey"]).size().rename("n").reset_index()
alloc["Share"] = alloc["n"] / alloc.groupby("BankKey")["n"].transform("sum")
fees_pnl = bank_fees.merge(alloc[["BankKey", "EntityKey", "Share"]], on="BankKey")
fees_pnl = fees_pnl.assign(Month=fees_pnl["FeeMonth"], Line="Bank fees", Category=fees_pnl["FeeCategory"],
                           Amount_CHF=-fees_pnl["Amount_CHF"] * fees_pnl["Share"])

# 3 FX cost ---------------------------------------------------------------------
# Half the quoted bid-ask spread on the CHF notional, booked in the trade month.
fx_pnl = fx_deals.assign(Month=month_of(fx_deals["TradeDate"]), Line="FX cost", Category=fx_deals["CurrencyPair"],
                         Amount_CHF=-fx_deals["Notional_CHF"] * fx_deals["Spread_bps"] / 2 / 10_000)

actual_pnl = (pd.concat([interest[pnl_cols], fees_pnl[pnl_cols], fx_pnl[pnl_cols]])
              .groupby(pnl_cols[:-1], as_index=False)["Amount_CHF"].sum())
actual_pnl["Scenario"] = "Actual"

# 4 Budget ----------------------------------------------------------------------
# Each budget is built in the autumn before the year, on the run rate of the
# three months before it, plus planning assumptions:
#   rates are held flat (the 2025 budget therefore misses the SARON and €STR cuts),
#   fees +2% for tariff inflation, FX volumes +3%.
# The 2026 budget does not know about Core Bank 3's January payment tariff increase.
BUDGET_BASE = {2025: ("2024-10-01", "2024-12-01"), 2026: ("2025-07-01", "2025-09-01")}
UPLIFT = {"Interest income": 1.00, "Bank fees": 1.02, "FX cost": 1.03}
keys = ["EntityKey", "BankKey", "Line", "Category"]
plan_rows = []
for yr, (b0, b1) in BUDGET_BASE.items():
    base = actual_pnl[actual_pnl["Month"].between(b0, b1)]
    run = base.groupby(keys)["Amount_CHF"].sum() / 3
    for m in pd.date_range(f"{yr}-01-01", f"{yr}-12-01", freq="MS"):
        b = run.reset_index()
        b["Amount_CHF"] = b["Amount_CHF"] * b["Line"].map(UPLIFT)
        b["Month"], b["Scenario"] = m, "Budget"
        plan_rows.append(b)

# 5 Reforecasts -----------------------------------------------------------------
# Q1 forecast (built in April): actuals for Jan-Mar, then the Jan-Mar run rate.
# Q2 forecast (built in July):  actuals for Jan-Jun, then the Apr-Jun run rate.
for yr in (2025, 2026):
    for name, closed_to, run_from in (("Forecast Q1", 3, 1), ("Forecast Q2", 6, 4)):
        ytd = actual_pnl[(actual_pnl["Month"].dt.year == yr) & (actual_pnl["Month"].dt.month <= closed_to)]
        run = (ytd[ytd["Month"].dt.month >= run_from].groupby(keys)["Amount_CHF"].sum() /
               (closed_to - run_from + 1))
        plan_rows.append(ytd.assign(Scenario=name))
        for mm in range(closed_to + 1, 13):
            f = run.reset_index()
            f["Amount_CHF"] = f["Amount_CHF"] * (1 + rng_plan.normal(0, 0.02, len(f)))
            f["Month"], f["Scenario"] = pd.Timestamp(yr, mm, 1), name
            plan_rows.append(f)

treasury_pnl = pd.concat([actual_pnl] + plan_rows, ignore_index=True)
treasury_pnl["Amount_CHF"] = treasury_pnl["Amount_CHF"].round(2)
treasury_pnl = (treasury_pnl[["Month", "Scenario", "EntityKey", "BankKey", "Line", "Category", "Amount_CHF"]]
                .sort_values(["Scenario", "Month", "Line", "EntityKey", "BankKey", "Category"])
                .reset_index(drop=True))
dim_scenario = pd.DataFrame([
    ("Actual", 1, "Booked"), ("Budget", 2, "Plan"),
    ("Forecast Q1", 3, "Reforecast"), ("Forecast Q2", 4, "Reforecast"),
], columns=["Scenario", "ScenarioSort", "ScenarioType"])

# ---------------------------------------------------------------------------
# Row-level security: user-to-entity mapping (fictional users)
# ---------------------------------------------------------------------------
security_user_entity = pd.DataFrame(
    [("group.treasurer@sentavo.example", e) for e in dim_entity["EntityKey"]] +
    [("cfo.ch@sentavo.example", "SIG-CH02"),
     ("cfo.de@sentavo.example", "SIG-DE01"), ("cfo.de@sentavo.example", "SIG-FR01"),
     ("cfo.de@sentavo.example", "SIG-IT01"),
     ("cfo.pl@sentavo.example", "SIG-PL01"),
     ("cfo.us@sentavo.example", "SIG-US01"), ("cfo.apac@sentavo.example", "SIG-SG01")],
    columns=["UserPrincipalName", "EntityKey"])


# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
dim_bank_out = dim_bank.drop(columns=["_spread_base"])
dim_fund_out = dim_fund.drop(columns=["_spread_pct", "_target"])

tables = {
    "DimEntity": dim_entity,
    "DimBank": dim_bank_out,
    "DimFund": dim_fund_out,
    "DimCurrency": dim_currency,
    "FactLiquidityPosition": position,
    "FactTermDeposits": deposits.drop(columns=["DayCount"]),
    "FactMMFYield": mmf_yields,
    "FactDepositQuotes": deposit_quotes,
    "FactFXDeals": fx_deals,
    "FactBankFees": bank_fees,
    "FactBankIssues": bank_issues,
    "FactCreditSpreads": credit_spreads,
    "FactCashForecast": cash_forecast,
    "MarketBenchmarkRates": benchmark_rates,
    "MarketFXRates": fx_rates,
    "DimScenario": dim_scenario,
    "FactTreasuryPnL": treasury_pnl,
    "SecurityUserEntity": security_user_entity,
}

about = pd.DataFrame({"About this dataset": [
    "Synthetic dataset for a FICTIONAL company: Sentavo Industrial Group AG.",
    "Generated by src/generate_data.py (seed %d). No real company, bank, client or market data is used." % SEED,
    "Banks are anonymised by role (Core Bank 1-4, Regional Bank CH/PL/SG).",
    "Benchmark and FX rate paths are illustrative and must not be read as market data.",
    "Period: %s to %s (business days). Reporting currency: CHF." % (START, END),
]})

with pd.ExcelWriter(OUT / "sentavo_treasury_dataset.xlsx", engine="openpyxl") as xw:
    about.to_excel(xw, sheet_name="README", index=False)
    for name, df in tables.items():
        df.to_excel(xw, sheet_name=name, index=False)
for name, df in tables.items():
    df.to_csv(OUT / f"{name}.csv", index=False)

print("Written to", OUT)
for name, df in tables.items():
    print(f"  {name:24s} {len(df):>7,d} rows")
