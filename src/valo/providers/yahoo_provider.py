"""YahooProvider — yfinance pinné. Données live + reconstitution historique (ancre marché)."""
from datetime import date, datetime, timedelta

import yfinance as yf

from valo.logging import logger
from valo.providers.base import MarketDataProvider, MarketSnapshot


class HistoricalDataUnavailable(Exception):
    """Levée quand yfinance ne couvre pas la date demandée (IPO postérieure, etc.)."""


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
        revenue_growth = info.get("revenueGrowth")  # YoY trailing (décimal), parfois absent

        source = {
            "market_cap": "yfinance:marketCap",
            "net_debt": "yfinance:totalDebt-totalCash",
            "revenue_ltm": "yfinance:totalRevenue",
            "revenue_growth": "yfinance:revenueGrowth(trailing)",
        }

        log.info("yahoo_snapshot_ok", market_cap=market_cap, growth=revenue_growth)
        return MarketSnapshot(
            ticker=ticker,
            fetched_at=datetime.utcnow(),
            market_cap=market_cap,
            net_debt=net_debt,
            cash=cash,
            revenue_ltm=revenue_ltm,
            source_by_field=source,
            revenue_growth=revenue_growth,
        )

    def resolve_ticker(self, ticker: str) -> dict:
        """Résout un ticker → {ticker, valid, name}. Garde-fou anti-collision/hallucination LLM."""
        ticker = ticker.strip().upper()
        try:
            info = yf.Ticker(ticker).info
            name = info.get("longName") or info.get("shortName")
            has_price = bool(info.get("regularMarketPrice") or info.get("currentPrice") or info.get("marketCap"))
            return {"ticker": ticker, "valid": bool(name and has_price), "name": name}
        except Exception:
            return {"ticker": ticker, "valid": False, "name": None}

    def fetch_historical_snapshot(self, ticker: str, as_of: date) -> MarketSnapshot:
        """
        Reconstitue une capi/EV/revenue à une date passée (best-effort) :
          - market_cap ≈ close historique × shares outstanding (courant, faute de mieux)
          - net_debt  ← bilan trimestriel le plus proche ≤ as_of
          - revenue   ← income statement le plus proche ≤ as_of (annualisé si trimestriel)
        Lève HistoricalDataUnavailable si le prix à la date est introuvable.
        """
        log = logger.bind(ticker=ticker, provider="yahoo", as_of=str(as_of))
        tk = yf.Ticker(ticker)

        # Prix historique autour de la date (fenêtre ±7 jours)
        start = as_of - timedelta(days=7)
        end = as_of + timedelta(days=7)
        try:
            hist = tk.history(start=start.isoformat(), end=end.isoformat())
        except Exception as exc:
            raise HistoricalDataUnavailable(f"{ticker}: history() a échoué ({exc})") from exc
        if hist is None or hist.empty:
            raise HistoricalDataUnavailable(f"{ticker}: aucun prix autour de {as_of} (IPO postérieure ?)")
        close = float(hist["Close"].iloc[-1])

        info = tk.info
        shares = info.get("sharesOutstanding")
        market_cap = close * shares if shares else None

        net_debt = self._nearest_net_debt(tk, as_of)
        revenue = self._nearest_revenue(tk, as_of)
        revenue_growth = self._growth_at(tk, as_of)

        source = {
            "market_cap": f"yfinance:hist_close({as_of})×sharesOutstanding",
            "net_debt": "yfinance:quarterly_balance_sheet~as_of",
            "revenue_ltm": "yfinance:income_stmt~as_of",
            "revenue_growth": "yfinance:income_stmt YoY~as_of",
        }
        log.info("yahoo_historical_ok", market_cap=market_cap, close=close, growth=revenue_growth)
        return MarketSnapshot(
            ticker=ticker,
            fetched_at=datetime.utcnow(),
            market_cap=market_cap,
            net_debt=net_debt,
            cash=None,
            revenue_ltm=revenue,
            source_by_field=source,
            revenue_growth=revenue_growth,
            as_of_date=as_of,
        )

    @staticmethod
    def _nearest_net_debt(tk, as_of: date) -> float | None:
        """Dette nette au bilan le plus proche ≤ as_of : trimestriel puis annuel (profondeur)."""
        debt_labels = ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"]
        cash_labels = ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash"]
        for getter in ("quarterly_balance_sheet", "balance_sheet"):
            try:
                bs = getattr(tk, getter)
            except Exception:
                continue
            if bs is None or bs.empty:
                continue
            cols = [c for c in bs.columns if c.date() <= as_of]
            if not cols:
                continue
            col = max(cols)
            debt = _row(bs, col, debt_labels)
            cash = _row(bs, col, cash_labels)
            if debt is not None:
                return debt - (cash or 0)
        return None

    @staticmethod
    def _growth_at(tk, as_of: date) -> float | None:
        """Croissance YoY du revenue à la date : revenue(année ≤ as_of) / revenue(année précédente) − 1."""
        labels = ["Total Revenue", "Revenue", "Operating Revenue"]
        try:
            fin = tk.income_stmt
            if fin is None or fin.empty:
                return None
            cols = sorted([c for c in fin.columns if c.date() <= as_of], reverse=True)
            if len(cols) < 2:
                return None
            cur = _row(fin, cols[0], labels)
            prev = _row(fin, cols[1], labels)
            if cur is None or not prev:
                return None
            return cur / prev - 1
        except Exception:
            return None

    @staticmethod
    def _nearest_revenue(tk, as_of: date) -> float | None:
        """Revenue LTM : somme 4 trimestres si dispo, sinon revenue annuel le plus proche ≤ as_of."""
        labels = ["Total Revenue", "Revenue", "Operating Revenue"]
        # 1) Trimestriel (LTM = somme 4 derniers trimestres)
        try:
            fin = tk.quarterly_income_stmt
            if fin is not None and not fin.empty:
                cols = sorted([c for c in fin.columns if c.date() <= as_of], reverse=True)
                quarters = [_row(fin, c, labels) for c in cols[:4]]
                quarters = [q for q in quarters if q is not None]
                if len(quarters) == 4:
                    return sum(quarters)
        except Exception:
            pass
        # 2) Fallback annuel (revenue plein exercice ≈ LTM)
        try:
            fin = tk.income_stmt
            if fin is not None and not fin.empty:
                cols = [c for c in fin.columns if c.date() <= as_of]
                if cols:
                    return _row(fin, max(cols), labels)
        except Exception:
            pass
        return None


def _row(df, col, candidates: list[str]) -> float | None:
    """Récupère la 1re ligne existante parmi candidates pour une colonne donnée."""
    for name in candidates:
        if name in df.index:
            val = df.loc[name, col]
            if val is not None and not (isinstance(val, float) and val != val):  # NaN check
                return float(val)
    return None
