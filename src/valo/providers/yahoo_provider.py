"""YahooProvider — yfinance pinné, fallback sur données manquantes."""
from datetime import datetime

import yfinance as yf

from valo.logging import logger
from valo.providers.base import MarketDataProvider, MarketSnapshot


class YahooProvider(MarketDataProvider):
    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        log = logger.bind(ticker=ticker, provider="yahoo")
        try:
            info = yf.Ticker(ticker).info
        except Exception as exc:
            log.error("yahoo_fetch_failed", error=str(exc))
            raise

        market_cap = info.get("marketCap")
        total_debt = info.get("totalDebt", 0) or 0
        cash = info.get("totalCash", 0) or 0
        net_debt = total_debt - cash
        revenue_ltm = info.get("totalRevenue")

        source = {
            "market_cap": "yfinance:marketCap",
            "net_debt": "yfinance:totalDebt-totalCash",
            "revenue_ltm": "yfinance:totalRevenue",
        }

        log.info("yahoo_snapshot_ok", market_cap=market_cap)
        return MarketSnapshot(
            ticker=ticker,
            fetched_at=datetime.utcnow(),
            market_cap=market_cap,
            net_debt=net_debt,
            cash=cash,
            revenue_ltm=revenue_ltm,
            source_by_field=source,
        )

    def suggest_comps(self, target_description: str) -> list[dict]:
        # P3 — panel suggestion via LLM ; placeholder pour P1
        raise NotImplementedError("suggest_comps requires LLM integration (P3)")
