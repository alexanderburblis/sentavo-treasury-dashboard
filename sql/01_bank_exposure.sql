-- Daily bank exposure and limit utilisation.
-- Only balances held at banks count against a limit: money market fund
-- positions are excluded through CounterpartyType, as in the DAX model.
CREATE OR REPLACE VIEW v_bank_exposure_daily AS
SELECT
    l.Date,
    l.BankKey,
    b.BankLabel,
    b.Rating,
    b.CounterpartyLimit_CHF,
    SUM(l.Balance_CHF)                              AS Exposure_CHF,
    SUM(l.Balance_CHF) / b.CounterpartyLimit_CHF    AS Utilisation
FROM FactLiquidityPosition AS l
JOIN DimBank AS b USING (BankKey)
WHERE l.CounterpartyType = 'Bank'
GROUP BY l.Date, l.BankKey, b.BankLabel, b.Rating, b.CounterpartyLimit_CHF;

-- Group cash and the share held outside the in-house bank, per day.
CREATE OR REPLACE VIEW v_cash_daily AS
SELECT
    l.Date,
    SUM(l.Balance_CHF)                                                    AS Cash_CHF,
    SUM(l.Balance_CHF) FILTER (WHERE e.Role <> 'Holding & in-house bank') AS Outside_IHB_CHF,
    Outside_IHB_CHF / Cash_CHF                                            AS Outside_IHB_Share
FROM FactLiquidityPosition AS l
JOIN DimEntity AS e USING (EntityKey)
GROUP BY l.Date;
