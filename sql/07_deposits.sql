-- Term deposit pricing: each deal against the best quote of its month,
-- currency and tenor, and against the benchmark on its start date.
-- Principal is converted to CHF at the FX rate of the start date.
CREATE OR REPLACE VIEW v_deposit_pricing AS
WITH best AS (
    SELECT QuoteMonth, Currency, Tenor, MAX(QuotedRate_pct) AS BestQuote_pct
    FROM FactDepositQuotes
    GROUP BY QuoteMonth, Currency, Tenor
)
SELECT
    d.DealID,
    d.BankKey,
    d.Currency,
    d.Tenor,
    d.StartDate,
    d.MaturityDate,
    d.Status,
    d.Principal_LC * fx.CHF_per_unit                 AS Principal_CHF,
    d.InterestRate_pct,
    b.BestQuote_pct,
    r.Rate_pct                                       AS Benchmark_pct,
    (d.InterestRate_pct - b.BestQuote_pct) * 100     AS VsBestQuote_bps,
    (d.InterestRate_pct - r.Rate_pct) * 100          AS VsBenchmark_bps
FROM FactTermDeposits AS d
JOIN MarketFXRates AS fx
  ON fx.Date = d.StartDate AND fx.CurrencyCode = d.Currency
LEFT JOIN best AS b
  ON b.QuoteMonth = DATE_TRUNC('month', d.StartDate) AND b.Currency = d.Currency AND b.Tenor = d.Tenor
LEFT JOIN MarketBenchmarkRates AS r
  ON r.Date = d.StartDate AND r.Currency = d.Currency;

-- Maturity ladder of the deposits still outstanding at the as-of date.
CREATE OR REPLACE VIEW v_maturity_ladder AS
SELECT
    DATE_TRUNC('month', MaturityDate) AS MaturityMonth,
    Currency,
    COUNT(*)                          AS Deals,
    SUM(Principal_CHF)                AS Principal_CHF
FROM v_deposit_pricing
WHERE Status = 'Outstanding'
GROUP BY ALL
ORDER BY MaturityMonth, Currency;
