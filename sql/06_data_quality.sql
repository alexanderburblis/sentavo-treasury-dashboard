-- Data quality checks. Each row is one check. Failures = 0 means it passes.
CREATE OR REPLACE VIEW v_data_quality AS
SELECT 'Liquidity rows without a known entity' AS CheckName,
       COUNT(*) AS Failures
FROM FactLiquidityPosition l ANTI JOIN DimEntity e USING (EntityKey)
UNION ALL
SELECT 'Liquidity rows without a known bank', COUNT(*)
FROM FactLiquidityPosition l ANTI JOIN DimBank b USING (BankKey)
UNION ALL
SELECT 'Fund positions without a known fund', COUNT(*)
FROM (SELECT * FROM FactLiquidityPosition WHERE CounterpartyType = 'Fund') l
ANTI JOIN DimFund f USING (FundKey)
UNION ALL
SELECT 'Negative balances', COUNT(*)
FROM FactLiquidityPosition WHERE Balance_CHF < 0
UNION ALL
SELECT 'Duplicate position keys', COUNT(*) FROM (
    SELECT Date, EntityKey, BankKey, FundKey, Instrument, Currency
    FROM FactLiquidityPosition
    GROUP BY Date, EntityKey, BankKey, FundKey, Instrument, Currency HAVING COUNT(*) > 1)
UNION ALL
SELECT 'Deposits maturing before they start', COUNT(*)
FROM FactTermDeposits WHERE MaturityDate <= StartDate
UNION ALL
SELECT 'FX deals without a known bank', COUNT(*)
FROM FactFXDeals f ANTI JOIN DimBank b USING (BankKey)
UNION ALL
SELECT 'Closed issues without a close date', COUNT(*)
FROM FactBankIssues WHERE Status = 'Closed' AND CloseDate IS NULL
UNION ALL
SELECT 'P&L rows without a known entity', COUNT(*)
FROM FactTreasuryPnL p ANTI JOIN DimEntity e USING (EntityKey)
UNION ALL
SELECT 'P&L rows with an unknown scenario', COUNT(*)
FROM FactTreasuryPnL p ANTI JOIN DimScenario s USING (Scenario)
UNION ALL
SELECT 'RLS users mapped to an unknown entity', COUNT(*)
FROM SecurityUserEntity u ANTI JOIN DimEntity e USING (EntityKey);

-- Row count and latest date per fact table.
CREATE OR REPLACE VIEW v_table_profile AS
SELECT 'FactLiquidityPosition' AS TableName, COUNT(*) AS Rows, MAX(Date)       AS LastDate FROM FactLiquidityPosition
UNION ALL SELECT 'FactTermDeposits',  COUNT(*), MAX(StartDate)  FROM FactTermDeposits
UNION ALL SELECT 'FactMMFYield',      COUNT(*), MAX(Date)       FROM FactMMFYield
UNION ALL SELECT 'FactDepositQuotes', COUNT(*), MAX(QuoteMonth) FROM FactDepositQuotes
UNION ALL SELECT 'FactFXDeals',       COUNT(*), MAX(TradeDate)  FROM FactFXDeals
UNION ALL SELECT 'FactBankFees',      COUNT(*), MAX(FeeMonth)   FROM FactBankFees
UNION ALL SELECT 'FactBankIssues',    COUNT(*), MAX(OpenDate)   FROM FactBankIssues
UNION ALL SELECT 'FactCreditSpreads', COUNT(*), MAX(Date)       FROM FactCreditSpreads
UNION ALL SELECT 'FactCashForecast',  COUNT(*), MAX(WeekStart)  FROM FactCashForecast
UNION ALL SELECT 'FactTreasuryPnL',   COUNT(*), MAX(Month)      FROM FactTreasuryPnL;
