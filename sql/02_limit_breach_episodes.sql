-- Limit-breach episodes (gaps and islands).
--
-- A new episode starts on a day over the limit when the previous business
-- day was not over it. LAG finds that previous day, and a running SUM of
-- episode starts numbers the episodes per bank.
CREATE OR REPLACE VIEW v_limit_breach_days AS
WITH flagged AS (
    SELECT
        *,
        Utilisation > 1.0  AS OverLimit,
        Utilisation > 0.8  AS OverAlert,
        LAG(Utilisation > 1.0, 1, FALSE) OVER (PARTITION BY BankKey ORDER BY Date) AS PrevOverLimit
    FROM v_bank_exposure_daily
)
SELECT
    *,
    SUM(CASE WHEN OverLimit AND NOT PrevOverLimit THEN 1 ELSE 0 END)
        OVER (PARTITION BY BankKey ORDER BY Date ROWS UNBOUNDED PRECEDING) AS EpisodeNo
FROM flagged;

CREATE OR REPLACE VIEW v_limit_breach_episodes AS
SELECT
    BankKey,
    BankLabel,
    EpisodeNo,
    MIN(Date)                          AS FirstDayOver,
    MAX(Date)                          AS LastDayOver,
    COUNT(*)                           AS BusinessDaysOver,
    MAX(Exposure_CHF)                  AS PeakExposure_CHF,
    MAX(Utilisation)                   AS PeakUtilisation,
    ARG_MAX(Date, Utilisation)         AS PeakDate
FROM v_limit_breach_days
WHERE OverLimit
GROUP BY BankKey, BankLabel, EpisodeNo
ORDER BY BankKey, EpisodeNo;

-- Early warning: how long before the first breach did the bank cross 80%?
CREATE OR REPLACE VIEW v_breach_early_warning AS
WITH alert AS (
    SELECT
        e.BankKey,
        e.BankLabel,
        e.EpisodeNo,
        e.FirstDayOver,
        MIN(d.Date) AS FirstDayOverAlert
    FROM v_limit_breach_episodes AS e
    JOIN v_limit_breach_days AS d
      ON d.BankKey = e.BankKey AND d.OverAlert AND d.Date <= e.FirstDayOver
    GROUP BY e.BankKey, e.BankLabel, e.EpisodeNo, e.FirstDayOver
)
SELECT
    *,
    DATE_DIFF('day', FirstDayOverAlert, FirstDayOver) / 7.0 AS WeeksOfWarning
FROM alert;
