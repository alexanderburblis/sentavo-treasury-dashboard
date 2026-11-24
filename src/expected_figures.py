"""
Figures quoted in the README, with the tolerance each is checked to.

run_sql_checks.py and the tests compare SQL and pandas results against these,
so the README cannot drift from the data without a check failing.
Amounts are CHF, shares are fractions. Tolerances match the rounding in the README.
"""

# key: (value, absolute tolerance, display format)
EXPECTED = {
    "as_of":                       ("2026-09-30", None, "{}"),
    "cash_chf":                    (516.9e6, 0.05e6, "{:,.0f}"),
    "outside_ihb_chf":             (154.4e6, 0.05e6, "{:,.0f}"),
    "outside_ihb_share":           (0.299, 0.0005, "{:.1%}"),
    "max_utilisation_today":       (0.781, 0.0005, "{:.1%}"),
    "pl_first_over_80":            ("2025-03-03", None, "{}"),
    "pl_first_over_100":           ("2025-05-27", None, "{}"),
    "pl_weeks_of_warning":         (12.0, 0.15, "{:.1f}"),
    "pl_peak_exposure_chf":        (15.4e6, 0.05e6, "{:,.0f}"),
    "pl_peak_utilisation":         (1.29, 0.005, "{:.1%}"),
    "pl_peak_date":                ("2025-06-03", None, "{}"),
    "pl_days_over_limit":          (41, 0, "{}"),
    "pl_spread_start_bps":         (115, 0.5, "{:.1f}"),
    "pl_spread_end_bps":           (139, 0.5, "{:.1f}"),
    "wape_1w":                     (0.045, 0.0005, "{:.1%}"),
    "wape_4w":                     (0.084, 0.0005, "{:.1%}"),
    "wape_13w":                    (0.157, 0.0005, "{:.1%}"),
    "receipts_bias_13w":           (0.053, 0.0005, "{:+.1%}"),
    "last13w_actual_chf":          (-39.1e6, 0.05e6, "{:,.0f}"),
    "last13w_fcst13w_chf":         (-14.8e6, 0.05e6, "{:,.0f}"),
    "b03_payments_fees_yoy":       (0.35, 0.005, "{:+.1%}"),
    "b03_fees_vs_budget_2026":     (0.16, 0.005, "{:+.1%}"),
    "interest_actual_ytd_2025_chf": (7.16e6, 0.005e6, "{:,.0f}"),
    "interest_budget_ytd_2025_chf": (9.76e6, 0.005e6, "{:,.0f}"),
    "pnl_variance_ytd_2025_chf":    (-2.54e6, 0.005e6, "{:,.0f}"),
    "interest_actual_ytd_2026_chf": (4.26e6, 0.005e6, "{:,.0f}"),
    "interest_budget_ytd_2026_chf": (5.13e6, 0.005e6, "{:,.0f}"),
    "pnl_variance_ytd_2026_chf":    (-0.82e6, 0.005e6, "{:,.0f}"),
    "pnl_outturn_fy_2026_chf":      (4.30e6, 0.005e6, "{:,.0f}"),
    "pnl_budget_fy_2026_chf":       (5.46e6, 0.005e6, "{:,.0f}"),
    "deposits_vs_best_quote_bps":   (-3.7, 0.05, "{:+.1f}"),
    "deposits_vs_benchmark_bps":    (3.9, 0.05, "{:+.1f}"),
    "deposits_outstanding_chf":     (132.2e6, 0.05e6, "{:,.0f}"),
    "deposits_share_below_best":    (0.75, 0.03, "{:.0%}"),
    "b01_connectivity_fees_change": (-0.17, 0.005, "{:+.1%}"),
    "b03_breach_day":               ("2025-01-31", None, "{}"),
    "fx_deals":                     (749, 0, "{}"),
    "fx_volume_chf":                (2.80e9, 0.005e9, "{:,.0f}"),
    "fx_spread_bps":                (3.23, 0.005, "{:.2f}"),
    "fx_cost_chf":                  (452e3, 0.5e3, "{:,.0f}"),
    "fx_platform_share":            (0.843, 0.0005, "{:.1%}"),
    "fx_eurpln_spread_bps":         (10.65, 0.005, "{:.2f}"),
    "fx_eurusd_spread_bps":         (1.54, 0.005, "{:.2f}"),
    "fx_b06_spread_bps":            (13.38, 0.005, "{:.2f}"),
    "fx_b01_spread_bps":            (2.30, 0.005, "{:.2f}"),
}


def matches(actual, expected, tol):
    if tol is None:
        return str(actual) == str(expected)
    return abs(float(actual) - float(expected)) <= tol
