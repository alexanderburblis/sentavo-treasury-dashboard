-- 13-week cash forecast accuracy.
-- WAPE = sum of absolute errors / sum of absolute 1-week actuals. The same
-- base is used for every horizon, so 1, 4 and 13 weeks are comparable.
CREATE OR REPLACE VIEW v_forecast_wape AS
WITH base AS (
    SELECT SUM(ABS(Actual_CHF)) AS AbsActual
    FROM FactCashForecast
    WHERE HorizonWeeks = 1
)
SELECT
    f.HorizonWeeks,
    SUM(ABS(f.Forecast_CHF - f.Actual_CHF)) / ANY_VALUE(base.AbsActual) AS WAPE
FROM FactCashForecast AS f, base
GROUP BY f.HorizonWeeks
ORDER BY f.HorizonWeeks;

-- Optimism bias on customer receipts, by horizon.
CREATE OR REPLACE VIEW v_receipts_bias AS
WITH actual AS (
    SELECT SUM(Actual_CHF) AS A
    FROM FactCashForecast
    WHERE FlowCategory = 'Customer receipts' AND HorizonWeeks = 1
)
SELECT
    f.HorizonWeeks,
    SUM(f.Forecast_CHF) / ANY_VALUE(actual.A) - 1 AS Bias
FROM FactCashForecast AS f, actual
WHERE f.FlowCategory = 'Customer receipts'
GROUP BY f.HorizonWeeks
ORDER BY f.HorizonWeeks;

-- Cumulative net cash flow over the last 13 weeks, intercompany excluded.
CREATE OR REPLACE VIEW v_last13w_cumulative AS
WITH weeks AS (
    SELECT DISTINCT WeekStart FROM FactCashForecast ORDER BY WeekStart DESC LIMIT 13
),
weekly AS (
    SELECT
        f.WeekStart,
        SUM(f.Actual_CHF)   FILTER (WHERE f.HorizonWeeks = 1)  AS Actual_CHF,
        SUM(f.Forecast_CHF) FILTER (WHERE f.HorizonWeeks = 1)  AS Fcst1W_CHF,
        SUM(f.Forecast_CHF) FILTER (WHERE f.HorizonWeeks = 13) AS Fcst13W_CHF
    FROM FactCashForecast AS f
    JOIN weeks USING (WeekStart)
    WHERE f.FlowCategory <> 'Intercompany'
    GROUP BY f.WeekStart
)
SELECT
    WeekStart,
    SUM(Actual_CHF)  OVER w AS CumActual_CHF,
    SUM(Fcst1W_CHF)  OVER w AS CumFcst1W_CHF,
    SUM(Fcst13W_CHF) OVER w AS CumFcst13W_CHF
FROM weekly
WINDOW w AS (ORDER BY WeekStart ROWS UNBOUNDED PRECEDING)
ORDER BY WeekStart;
