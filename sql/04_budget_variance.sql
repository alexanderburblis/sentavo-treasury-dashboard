-- Treasury P&L: actual vs budget vs latest forecast.
-- Income is positive and cost negative, so Actual - Budget > 0 is favourable.

-- Last month with booked actuals, and the latest reforecast.
CREATE OR REPLACE VIEW v_pnl_close AS
SELECT
    MAX(Month) FILTER (WHERE Scenario = 'Actual')  AS LastActualMonth,
    'Forecast Q2'                                  AS LatestForecast
FROM FactTreasuryPnL;

-- Year to date (through the last actual month) by year and P&L line.
CREATE OR REPLACE VIEW v_budget_variance_ytd AS
SELECT
    YEAR(p.Month)                                                         AS Year,
    p.Line,
    SUM(p.Amount_CHF) FILTER (WHERE p.Scenario = 'Actual')                AS Actual_CHF,
    SUM(p.Amount_CHF) FILTER (WHERE p.Scenario = 'Budget')                AS Budget_CHF,
    SUM(p.Amount_CHF) FILTER (WHERE p.Scenario = c.LatestForecast)        AS Forecast_CHF,
    Actual_CHF - Budget_CHF                                               AS Variance_CHF,
    Variance_CHF / ABS(Budget_CHF)                                        AS Variance_Pct
FROM FactTreasuryPnL AS p, v_pnl_close AS c
WHERE MONTH(p.Month) <= MONTH(c.LastActualMonth) OR YEAR(p.Month) < YEAR(c.LastActualMonth)
GROUP BY YEAR(p.Month), p.Line
HAVING Budget_CHF IS NOT NULL
ORDER BY Year, Line;

-- Full-year outturn: actuals to date plus the latest forecast for the rest of the year.
CREATE OR REPLACE VIEW v_full_year_outturn AS
SELECT
    YEAR(p.Month)                                                              AS Year,
    p.Line,
    SUM(p.Amount_CHF) FILTER (WHERE p.Scenario = 'Budget')                     AS Budget_FY_CHF,
    SUM(p.Amount_CHF) FILTER (WHERE (p.Scenario = 'Actual' AND p.Month <= c.LastActualMonth)
                                 OR (p.Scenario = c.LatestForecast AND p.Month > c.LastActualMonth))
                                                                               AS Outturn_FY_CHF,
    Outturn_FY_CHF - Budget_FY_CHF                                             AS Variance_CHF
FROM FactTreasuryPnL AS p, v_pnl_close AS c
GROUP BY YEAR(p.Month), p.Line
HAVING Budget_FY_CHF IS NOT NULL
ORDER BY Year, Line;

-- Monthly view by entity, for the variance commentary.
CREATE OR REPLACE VIEW v_budget_variance_monthly AS
SELECT
    p.Month,
    p.EntityKey,
    p.Line,
    SUM(p.Amount_CHF) FILTER (WHERE p.Scenario = 'Actual') AS Actual_CHF,
    SUM(p.Amount_CHF) FILTER (WHERE p.Scenario = 'Budget') AS Budget_CHF,
    Actual_CHF - Budget_CHF                                AS Variance_CHF
FROM FactTreasuryPnL AS p
GROUP BY p.Month, p.EntityKey, p.Line;
