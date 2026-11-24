-- FX execution: volume, spread and half-spread cost by pair, bank and channel.
-- Spreads are weighted by CHF notional. Cost is half the quoted spread on the notional.

CREATE OR REPLACE VIEW v_fx_deals AS
SELECT d.*,
       b.BankLabel,
       d.Notional_CHF * d.Spread_bps / 2 / 10000 AS SpreadCost_CHF
FROM FactFXDeals d
JOIN DimBank b USING (BankKey);

CREATE OR REPLACE VIEW v_fx_by_pair AS
SELECT CurrencyPair,
       COUNT(*)                                          AS Deals,
       SUM(Notional_CHF)                                 AS Volume_CHF,
       SUM(Notional_CHF * Spread_bps) / SUM(Notional_CHF) AS Spread_bps,
       SUM(SpreadCost_CHF)                               AS SpreadCost_CHF
FROM v_fx_deals
GROUP BY CurrencyPair;

CREATE OR REPLACE VIEW v_fx_by_bank AS
SELECT BankKey, BankLabel,
       COUNT(*)                                            AS Deals,
       SUM(Notional_CHF)                                   AS Volume_CHF,
       SUM(Notional_CHF) / SUM(SUM(Notional_CHF)) OVER ()  AS ShareOfWallet,
       SUM(Notional_CHF * Spread_bps) / SUM(Notional_CHF)  AS Spread_bps
FROM v_fx_deals
GROUP BY BankKey, BankLabel;

-- Pair and channel together: within a pair, does the channel change the price?
CREATE OR REPLACE VIEW v_fx_pair_channel AS
SELECT CurrencyPair, ExecutionChannel,
       COUNT(*)                                            AS Deals,
       SUM(Notional_CHF)                                   AS Volume_CHF,
       SUM(Notional_CHF * Spread_bps) / SUM(Notional_CHF)  AS Spread_bps
FROM v_fx_deals
GROUP BY CurrencyPair, ExecutionChannel;
