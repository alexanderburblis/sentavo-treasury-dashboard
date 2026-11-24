-- Bank fees by month, bank and category, with the same month a year earlier.
-- Every bank and category has a row for every month, so LAG(..., 12) is the
-- prior-year month.
CREATE OR REPLACE VIEW v_bank_fees_yoy AS
SELECT
    f.FeeMonth,
    f.BankKey,
    b.BankLabel,
    f.FeeCategory,
    f.Amount_CHF,
    LAG(f.Amount_CHF, 12) OVER w                    AS Amount_PY_CHF,
    f.Amount_CHF / LAG(f.Amount_CHF, 12) OVER w - 1 AS YoY
FROM FactBankFees AS f
JOIN DimBank AS b USING (BankKey)
WINDOW w AS (PARTITION BY f.BankKey, f.FeeCategory ORDER BY f.FeeMonth);

-- Fee step changes: a fee line whose rolling 3-month total moves more than
-- 15% against the same three months a year earlier. A rolling window
-- smooths out monthly noise, so only lasting changes are flagged, such as
-- a tariff increase or a renegotiated price.
CREATE OR REPLACE VIEW v_bank_fee_step_changes AS
WITH rolling AS (
    SELECT
        *,
        SUM(Amount_CHF)    OVER r AS Amount_3M_CHF,
        SUM(Amount_PY_CHF) OVER r AS Amount_3M_PY_CHF,
        COUNT(Amount_PY_CHF) OVER r AS MonthsWithPY
    FROM v_bank_fees_yoy
    WINDOW r AS (PARTITION BY BankKey, FeeCategory ORDER BY FeeMonth ROWS 2 PRECEDING)
)
SELECT
    FeeMonth,
    BankKey,
    BankLabel,
    FeeCategory,
    Amount_3M_CHF,
    Amount_3M_PY_CHF,
    Amount_3M_CHF / Amount_3M_PY_CHF - 1 AS YoY_3M
FROM rolling
WHERE MonthsWithPY = 3
  AND ABS(Amount_3M_CHF / Amount_3M_PY_CHF - 1) > 0.15
-- first month each step is flagged
QUALIFY ROW_NUMBER() OVER (PARTITION BY BankKey, FeeCategory ORDER BY FeeMonth) = 1;

-- Service issues by bank: count, share of high severity, days to resolve.
CREATE OR REPLACE VIEW v_bank_service AS
SELECT
    i.BankKey,
    b.BankLabel,
    COUNT(*)                                          AS Issues,
    COUNT(*) FILTER (WHERE i.Status <> 'Closed')      AS OpenIssues,
    AVG(CASE WHEN i.Severity = 'High' THEN 1 ELSE 0 END) AS HighSeverityShare,
    MEDIAN(i.ResolutionDays)                          AS MedianDaysToResolve
FROM FactBankIssues AS i
JOIN DimBank AS b USING (BankKey)
GROUP BY i.BankKey, b.BankLabel
ORDER BY Issues DESC;
