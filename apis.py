import httpx
import os
import time
from database import Database

FMP_KEY     = os.getenv("FMP_KEY", "")
AV_KEY      = os.getenv("ALPHA_VANTAGE_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "")

# ============================================================================
# HELPERS
# ============================================================================

def _safe_float(val):
    """Convierte a float. Maneja 'None' como string, vacíos y N/A."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("None", "N/A", "-", "", "nan", "Infinity"):
        return None
    try:
        return float(s.replace("%", "").replace(",", ""))
    except:
        return None

def _first(*values):
    """Primer valor que no sea None."""
    for v in values:
        if v is not None:
            return v
    return None

async def _get(client, url, params, timeout=15):
    try:
        r = await client.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            # Detectar respuestas de error de AV y FMP
            if isinstance(data, dict):
                if data.get("Note") or data.get("Information") or data.get("Error Message"):
                    print(f"API limit/error en {url}: {str(data)[:80]}")
                    return None
            return data
        print(f"HTTP {r.status_code} en {url}")
    except Exception as e:
        print(f"Error {url}: {e}")
    return None

# ============================================================================
# FMP
# ============================================================================

class FMP:
    BASE = "https://financialmodelingprep.com/api/v3"

    @staticmethod
    async def get_quote(symbol, client):
        data = await _get(client, f"{FMP.BASE}/quote/{symbol}", {"apikey": FMP_KEY})
        if data and isinstance(data, list) and data:
            d = data[0]
            price = _safe_float(d.get("price"))
            if price:
                return {
                    "price":         price,
                    "changePercent": _safe_float(d.get("changesPercentage")),
                    "marketCap":     _safe_float(d.get("marketCap")),
                    "name":          d.get("name"),
                    "source":        "FMP",
                }
        return None

    @staticmethod
    async def get_profile(symbol, client):
        data = await _get(client, f"{FMP.BASE}/profile/{symbol}", {"apikey": FMP_KEY})
        if data and isinstance(data, list) and data:
            d = data[0]
            return {
                "name":        d.get("companyName"),
                "sector":      d.get("sector"),
                "industry":    d.get("industry"),
                "marketCap":   _safe_float(d.get("mktCap")),
                "description": (d.get("description") or "")[:300],
            }
        return None

    @staticmethod
    async def get_metrics(symbol, client):
        data = await _get(client, f"{FMP.BASE}/key-metrics/{symbol}",
                          {"period": "annual", "limit": "1", "apikey": FMP_KEY})
        if data and isinstance(data, list) and data:
            d = data[0]
            return {
                "peRatio":       _safe_float(d.get("peRatio")),
                "roe":           _safe_float(d.get("roe")),
                "roa":           _safe_float(d.get("roa")),
                "debtToEquity":  _safe_float(d.get("debtToEquity")),
                "dividendYield": _safe_float(d.get("dividendYield")),
                "revenueGrowth": _safe_float(d.get("revenueGrowth")),
                "netMargin":     _safe_float(d.get("netMargin")),
            }
        return None

    @staticmethod
    async def get_historical(symbol, client):
        data = await _get(client, f"{FMP.BASE}/historical-price-full/{symbol}",
                          {"apikey": FMP_KEY}, timeout=20)
        if data and isinstance(data, dict) and "historical" in data:
            hist = data["historical"]
            parsed = [{"close": float(d["close"]), "timestamp": d.get("date")}
                      for d in hist if d.get("close")]
            print(f"FMP historical {symbol}: {len(parsed)} dias")
            if len(parsed) >= 50:
                return parsed   # más reciente primero
        return None

    @staticmethod
    async def get_news(symbol, client):
        data = await _get(client, f"{FMP.BASE}/stock_news",
                          {"tickers": symbol, "limit": "5", "apikey": FMP_KEY})
        if data and isinstance(data, list):
            return [{"title":   n.get("title", ""),
                     "summary": n.get("text", "")[:200],
                     "url":     n.get("url", ""),
                     "date":    n.get("publishedDate", "")[:10],
                     "source":  n.get("site", "FMP")}
                    for n in data[:5]]
        return None

# ============================================================================
# FINNHUB
# ============================================================================

class Finnhub:
    BASE = "https://finnhub.io/api/v1"

    @staticmethod
    async def get_quote(symbol, client):
        data = await _get(client, f"{Finnhub.BASE}/quote",
                          {"symbol": symbol, "token": FINNHUB_KEY})
        if data and _safe_float(data.get("c")):
            price = _safe_float(data.get("c"))
            prev  = _safe_float(data.get("pc"))
            change_pct = ((price - prev) / prev * 100) if prev else None
            return {
                "price":         price,
                "changePercent": change_pct,
                "marketCap":     None,
                "name":          None,
                "source":        "Finnhub",
            }
        return None

    @staticmethod
    async def get_profile(symbol, client):
        data = await _get(client, f"{Finnhub.BASE}/stock/profile2",
                          {"symbol": symbol, "token": FINNHUB_KEY})
        if data and data.get("name"):
            mc_raw = _safe_float(data.get("marketCapitalization"))
            return {
                "name":        data.get("name"),
                "sector":      data.get("finnhubIndustry"),
                "industry":    data.get("finnhubIndustry"),
                "marketCap":   mc_raw * 1e6 if mc_raw else None,
                "description": "",
            }
        return None

    @staticmethod
    async def get_metrics(symbol, client):
        data = await _get(client, f"{Finnhub.BASE}/stock/metric",
                          {"symbol": symbol, "metric": "all", "token": FINNHUB_KEY})
        if data and "metric" in data:
            m = data["metric"]
            # Finnhub da ROE/ROA/margin como % (ej 15.3), convertir a decimal
            def pct_to_dec(key):
                v = _safe_float(m.get(key))
                return v / 100 if v is not None else None

            return {
                "peRatio":       _first(_safe_float(m.get("peNormalizedAnnual")),
                                        _safe_float(m.get("peTTM"))),
                "roe":           pct_to_dec("roeTTM"),
                "roa":           pct_to_dec("roaTTM"),
                "debtToEquity":  _safe_float(m.get("totalDebt/totalEquityAnnual")),
                "dividendYield": _safe_float(m.get("dividendYieldIndicatedAnnual")),
                "revenueGrowth": pct_to_dec("revenueGrowthTTMYoy"),
                "netMargin":     pct_to_dec("netProfitMarginTTM"),
            }
        return None

    @staticmethod
    async def get_historical(symbol, client):
        """Finnhub /stock/candle con resolución diaria."""
        now = int(time.time())
        two_years_ago = now - (730 * 24 * 3600)
        data = await _get(client, f"{Finnhub.BASE}/stock/candle",
                          {"symbol": symbol, "resolution": "D",
                           "from": two_years_ago, "to": now,
                           "token": FINNHUB_KEY}, timeout=20)
        if data and data.get("s") == "ok" and data.get("c"):
            closes = data["c"]
            timestamps = data.get("t", [])
            hist = [{"close": c, "timestamp": t}
                    for c, t in zip(closes, timestamps) if c]
            hist.reverse()   # más reciente primero
            print(f"Finnhub historical {symbol}: {len(hist)} dias")
            if len(hist) >= 50:
                return hist
        return None

    @staticmethod
    async def get_news(symbol, client):
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        data = await _get(client, f"{Finnhub.BASE}/company-news",
                          {"symbol": symbol, "from": month_ago, "to": today,
                           "token": FINNHUB_KEY})
        if data and isinstance(data, list) and data:
            news = []
            for n in data[:5]:
                news.append({
                    "title":   n.get("headline", ""),
                    "summary": (n.get("summary") or "")[:200],
                    "url":     n.get("url", ""),
                    "date":    str(n.get("datetime", ""))[:10],
                    "source":  n.get("source", "Finnhub"),
                })
            return news
        return None

# ============================================================================
# ALPHA VANTAGE
# ============================================================================

class AlphaVantage:
    BASE = "https://www.alphavantage.co/query"

    @staticmethod
    async def get_quote(symbol, client):
        data = await _get(client, AlphaVantage.BASE,
                          {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": AV_KEY})
        if data and "Global Quote" in data:
            q = data["Global Quote"]
            price = _safe_float(q.get("05. price"))
            if price:
                pct = _safe_float((q.get("10. change percent") or "0").replace("%", ""))
                return {
                    "price":         price,
                    "changePercent": pct,
                    "marketCap":     None,
                    "name":          None,
                    "source":        "AlphaVantage",
                }
        return None

    @staticmethod
    async def get_overview(symbol, client):
        """Un request que da perfil + todas las métricas fundamentales."""
        data = await _get(client, AlphaVantage.BASE,
                          {"function": "OVERVIEW", "symbol": symbol, "apikey": AV_KEY})
        if not data or not data.get("Symbol"):
            return None

        # P/E: intentar TrailingPE, si es None string usar ForwardPE
        pe = _first(_safe_float(data.get("TrailingPE")),
                    _safe_float(data.get("ForwardPE")))

        # Debt/Equity: AV no siempre lo tiene, intentar ambos campos posibles
        d2e = _first(_safe_float(data.get("DebtToEquityRatio")),
                     _safe_float(data.get("debtToEquityRatio")))

        return {
            "profile": {
                "name":        data.get("Name"),
                "sector":      data.get("Sector"),
                "industry":    data.get("Industry"),
                "marketCap":   _safe_float(data.get("MarketCapitalization")),
                "description": (data.get("Description") or "")[:300],
            },
            "metrics": {
                "peRatio":       pe,
                "roe":           _safe_float(data.get("ReturnOnEquityTTM")),
                "roa":           _safe_float(data.get("ReturnOnAssetsTTM")),
                "debtToEquity":  d2e,
                "dividendYield": _safe_float(data.get("DividendYield")),
                "revenueGrowth": _safe_float(data.get("QuarterlyRevenueGrowthYOY")),
                "netMargin":     _safe_float(data.get("ProfitMargin")),
            },
        }

    @staticmethod
    async def get_historical(symbol, client):
        data = await _get(client, AlphaVantage.BASE,
                          {"function": "TIME_SERIES_DAILY_ADJUSTED",
                           "symbol": symbol, "outputsize": "full", "apikey": AV_KEY},
                          timeout=25)
        key = "Time Series (Daily)"
        if data and key in data:
            ts = data[key]
            hist = []
            for date_str, vals in ts.items():
                close = _first(_safe_float(vals.get("5. adjusted close")),
                               _safe_float(vals.get("4. close")))
                if close:
                    hist.append({"close": close, "timestamp": date_str})
            print(f"AV historical {symbol}: {len(hist)} dias")
            if len(hist) >= 50:
                return hist   # más reciente primero (dict ordenado en AV)
        return None

    @staticmethod
    async def get_news(symbol, client):
        data = await _get(client, AlphaVantage.BASE,
                          {"function": "NEWS_SENTIMENT", "tickers": symbol,
                           "limit": "5", "apikey": AV_KEY})
        if data and "feed" in data:
            news = []
            for n in data["feed"][:5]:
                sentiment = n.get("overall_sentiment_label", "")
                sent_map = {"Bullish": "alcista", "Bearish": "bajista",
                            "Neutral": "neutral", "Somewhat-Bullish": "algo alcista",
                            "Somewhat-Bearish": "algo bajista"}
                news.append({
                    "title":   n.get("title", ""),
                    "summary": (n.get("summary") or "")[:200],
                    "url":     n.get("url", ""),
                    "date":    (n.get("time_published") or "")[:8],
                    "source":  n.get("source", "AV"),
                    "sentiment": sent_map.get(sentiment, sentiment),
                })
            return news
        return None

# ============================================================================
# COINGECKO
# ============================================================================

CRYPTO_MAP = {
    "BTC": "bitcoin",    "ETH": "ethereum",     "BNB": "binancecoin",
    "SOL": "solana",     "ADA": "cardano",       "XRP": "ripple",
    "DOGE": "dogecoin",  "DOT": "polkadot",      "AVAX": "avalanche-2",
    "MATIC": "matic-network", "LTC": "litecoin", "LINK": "chainlink",
    "UNI": "uniswap",   "ATOM": "cosmos",        "XLM": "stellar",
    "TRX": "tron",      "NEAR": "near",          "SHIB": "shiba-inu",
}
CRYPTO_SYMBOLS = set(CRYPTO_MAP.keys())

def is_crypto(symbol: str) -> bool:
    return symbol.upper() in CRYPTO_SYMBOLS

class CoinGecko:
    BASE = "https://api.coingecko.com/api/v3"

    @staticmethod
    def _id(sym):
        return CRYPTO_MAP.get(sym.upper(), sym.lower())

    @staticmethod
    async def get_quote(symbol):
        coin_id = CoinGecko._id(symbol)
        cached = await Database.get(f"CG_{symbol}", "quote", max_age_minutes=10)
        if cached:
            return cached
        try:
            async with httpx.AsyncClient() as client:
                data = await _get(client, f"{CoinGecko.BASE}/simple/price", {
                    "ids": coin_id, "vs_currencies": "usd",
                    "include_24hr_change": "true", "include_market_cap": "true",
                })
                if data and coin_id in data:
                    d = data[coin_id]
                    result = {
                        "price":         _safe_float(d.get("usd")),
                        "changePercent": _safe_float(d.get("usd_24h_change")),
                        "marketCap":     _safe_float(d.get("usd_market_cap")),
                        "name":          symbol.upper(),
                    }
                    if result["price"]:
                        await Database.save(f"CG_{symbol}", "quote", result)
                        return result
        except Exception as e:
            print(f"CoinGecko quote error: {e}")
        return None

    @staticmethod
    async def get_historical(symbol):
        coin_id = CoinGecko._id(symbol)
        cached = await Database.get(f"CG_{symbol}", "historical", max_age_minutes=120)
        if cached:
            return cached
        try:
            async with httpx.AsyncClient() as client:
                data = await _get(client, f"{CoinGecko.BASE}/coins/{coin_id}/market_chart",
                                  {"vs_currency": "usd", "days": "730", "interval": "daily"},
                                  timeout=20)
                if data and "prices" in data:
                    hist = [{"close": p[1], "timestamp": p[0]//1000}
                            for p in data["prices"] if p[1]]
                    if len(hist) >= 50:
                        hist_desc = hist[::-1]
                        await Database.save(f"CG_{symbol}", "historical", hist_desc)
                        return hist_desc
        except Exception as e:
            print(f"CoinGecko historical error: {e}")
        return None

    @staticmethod
    async def get_news(symbol):
        """CoinGecko no tiene noticias — usar AV como fuente."""
        return None

# ============================================================================
# FACHADA PRINCIPAL
# ============================================================================

class StockAPI:

    @staticmethod
    async def get_all(symbol: str) -> dict:
        cached = await Database.get(symbol, "all_data_v2", max_age_minutes=60)
        if cached:
            print(f"[CACHE] {symbol}")
            return cached

        result = {"quote": None, "profile": None, "metrics": None, "historical": None}

        async with httpx.AsyncClient() as client:

            # 1. QUOTE: FMP -> Finnhub -> AV
            result["quote"] = (
                await FMP.get_quote(symbol, client) or
                await Finnhub.get_quote(symbol, client) or
                await AlphaVantage.get_quote(symbol, client)
            )
            print(f"[{symbol}] quote: {(result['quote'] or {}).get('source','FALLO')}")

            # 2. PERFIL + MÉTRICAS: AV Overview (1 request) -> FMP+Finnhub por separado
            av = await AlphaVantage.get_overview(symbol, client)
            if av:
                result["profile"] = av["profile"]
                result["metrics"] = av["metrics"]
                print(f"[{symbol}] overview: AV OK")
            else:
                result["profile"] = (
                    await FMP.get_profile(symbol, client) or
                    await Finnhub.get_profile(symbol, client)
                )
                result["metrics"] = (
                    await FMP.get_metrics(symbol, client) or
                    await Finnhub.get_metrics(symbol, client)
                )
                print(f"[{symbol}] overview: fallback a FMP/Finnhub")

            # Rellenar marketCap cruzando fuentes
            if result["profile"] and not result["profile"].get("marketCap"):
                mc = (result["quote"] or {}).get("marketCap")
                if mc:
                    result["profile"]["marketCap"] = mc
            if result["quote"] and not result["quote"].get("name"):
                name = (result["profile"] or {}).get("name")
                if name:
                    result["quote"]["name"] = name

            # 3. HISTÓRICO: FMP -> Finnhub candle -> AV
            result["historical"] = (
                await FMP.get_historical(symbol, client) or
                await Finnhub.get_historical(symbol, client) or
                await AlphaVantage.get_historical(symbol, client)
            )
            hist_n = len(result["historical"]) if result["historical"] else 0
            print(f"[{symbol}] historical: {hist_n} dias")

        if result["quote"]:
            await Database.save(symbol, "all_data_v2", result)

        return result

    @staticmethod
    async def get_news(symbol: str) -> list:
        """Noticias: Finnhub (mejor) -> FMP -> AV."""
        cached = await Database.get(symbol, "news", max_age_minutes=30)
        if cached:
            return cached

        async with httpx.AsyncClient() as client:
            news = (
                await Finnhub.get_news(symbol, client) or
                await FMP.get_news(symbol, client) or
                await AlphaVantage.get_news(symbol, client)
            )

        if news:
            await Database.save(symbol, "news", news)
        return news or []
