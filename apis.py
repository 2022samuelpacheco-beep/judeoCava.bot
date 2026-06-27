import httpx
import os
from database import Database

FMP_KEY     = os.getenv("FMP_KEY", "")
AV_KEY      = os.getenv("ALPHA_VANTAGE_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_KEY", "")

def _safe_float(val):
    if val is None:
        return None
    try:
        f = float(str(val).replace("%","").strip())
        return f if f != 0 else None
    except:
        return None

async def _get(client, url, params, timeout=15):
    try:
        r = await client.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        print(f"HTTP {r.status_code} en {url}")
    except Exception as e:
        print(f"Error HTTP {url}: {e}")
    return None

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
        if data and "historical" in data:
            hist = data["historical"]
            parsed = [{"close": float(d["close"]), "timestamp": d.get("date")}
                      for d in hist if d.get("close")]
            if len(parsed) >= 50:
                return parsed
        return None

class Finnhub:
    BASE = "https://finnhub.io/api/v1"

    @staticmethod
    async def get_quote(symbol, client):
        data = await _get(client, f"{Finnhub.BASE}/quote",
                          {"symbol": symbol, "token": FINNHUB_KEY})
        if data:
            price = _safe_float(data.get("c"))
            prev  = _safe_float(data.get("pc"))
            if price:
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
            mktcap_raw = _safe_float(data.get("marketCapitalization"))
            return {
                "name":        data.get("name"),
                "sector":      data.get("finnhubIndustry"),
                "industry":    data.get("finnhubIndustry"),
                "marketCap":   mktcap_raw * 1e6 if mktcap_raw else None,
                "description": "",
            }
        return None

    @staticmethod
    async def get_metrics(symbol, client):
        data = await _get(client, f"{Finnhub.BASE}/stock/metric",
                          {"symbol": symbol, "metric": "all", "token": FINNHUB_KEY})
        if data and "metric" in data:
            m = data["metric"]
            roe = _safe_float(m.get("roeTTM"))
            roa = _safe_float(m.get("roaTTM"))
            npm = _safe_float(m.get("netProfitMarginTTM"))
            rg  = _safe_float(m.get("revenueGrowthTTMYoy"))
            # Finnhub devuelve ROE/ROA/margin como porcentaje (ej: 15.3), convertir a decimal
            return {
                "peRatio":       _safe_float(m.get("peNormalizedAnnual") or m.get("peTTM")),
                "roe":           roe / 100 if roe else None,
                "roa":           roa / 100 if roa else None,
                "debtToEquity":  _safe_float(m.get("totalDebt/totalEquityAnnual")),
                "dividendYield": _safe_float(m.get("dividendYieldIndicatedAnnual")),
                "revenueGrowth": rg / 100 if rg else None,
                "netMargin":     npm / 100 if npm else None,
            }
        return None

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
                pct_str = q.get("10. change percent", "0%").replace("%", "")
                return {
                    "price":         price,
                    "changePercent": _safe_float(pct_str),
                    "marketCap":     None,
                    "name":          None,
                    "source":        "AlphaVantage",
                }
        return None

    @staticmethod
    async def get_overview(symbol, client):
        data = await _get(client, AlphaVantage.BASE,
                          {"function": "OVERVIEW", "symbol": symbol, "apikey": AV_KEY})
        if data and data.get("Symbol"):
            roe = _safe_float(data.get("ReturnOnEquityTTM"))
            roa = _safe_float(data.get("ReturnOnAssetsTTM"))
            npm = _safe_float(data.get("ProfitMargin"))
            rg  = _safe_float(data.get("QuarterlyRevenueGrowthYOY"))
            dy  = _safe_float(data.get("DividendYield"))
            pe  = _safe_float(data.get("TrailingPE") or data.get("ForwardPE"))
            d2e = _safe_float(data.get("DebtToEquityRatio"))
            mc  = _safe_float(data.get("MarketCapitalization"))
            return {
                "profile": {
                    "name":        data.get("Name"),
                    "sector":      data.get("Sector"),
                    "industry":    data.get("Industry"),
                    "marketCap":   mc,
                    "description": (data.get("Description") or "")[:300],
                },
                "metrics": {
                    "peRatio":       pe,
                    "roe":           roe,
                    "roa":           roa,
                    "debtToEquity":  d2e,
                    "dividendYield": dy,
                    "revenueGrowth": rg,
                    "netMargin":     npm,
                },
            }
        return None

    @staticmethod
    async def get_historical(symbol, client):
        data = await _get(client, AlphaVantage.BASE,
                          {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol,
                           "outputsize": "full", "apikey": AV_KEY}, timeout=25)
        if data and "Time Series (Daily)" in data:
            ts = data["Time Series (Daily)"]
            hist = []
            for date_str, vals in ts.items():
                close = _safe_float(vals.get("5. adjusted close") or vals.get("4. close"))
                if close:
                    hist.append({"close": close, "timestamp": date_str})
            if len(hist) >= 50:
                return hist
        return None

CRYPTO_MAP = {
    "BTC": "bitcoin",   "ETH": "ethereum",    "BNB": "binancecoin",
    "SOL": "solana",    "ADA": "cardano",      "XRP": "ripple",
    "DOGE": "dogecoin", "DOT": "polkadot",     "AVAX": "avalanche-2",
    "MATIC": "matic-network", "LTC": "litecoin", "LINK": "chainlink",
    "UNI": "uniswap",  "ATOM": "cosmos",      "XLM": "stellar",
    "TRX": "tron",     "NEAR": "near",        "SHIB": "shiba-inu",
}
CRYPTO_SYMBOLS = set(CRYPTO_MAP.keys())

def is_crypto(symbol: str) -> bool:
    return symbol.upper() in CRYPTO_SYMBOLS

class CoinGecko:
    BASE = "https://api.coingecko.com/api/v3"

    @staticmethod
    def _id(symbol):
        return CRYPTO_MAP.get(symbol.upper(), symbol.lower())

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
                        "sector":        "Cripto",
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

class StockAPI:
    """Orquesta FMP -> Finnhub/AV con cache SQLite."""

    @staticmethod
    async def get_all(symbol: str) -> dict:
        cached = await Database.get(symbol, "all_data", max_age_minutes=60)
        if cached:
            print(f"[CACHE] {symbol}")
            return cached

        result = {"quote": None, "profile": None, "metrics": None, "historical": None}

        async with httpx.AsyncClient() as client:
            # QUOTE: FMP -> Finnhub -> AV
            print(f"[API] {symbol}: quote...")
            result["quote"] = (
                await FMP.get_quote(symbol, client) or
                await Finnhub.get_quote(symbol, client) or
                await AlphaVantage.get_quote(symbol, client)
            )

            # OVERVIEW AV: un solo request da perfil + metricas
            print(f"[API] {symbol}: overview/metricas...")
            av = await AlphaVantage.get_overview(symbol, client)
            if av:
                result["profile"] = av["profile"]
                result["metrics"] = av["metrics"]
            else:
                result["profile"] = (
                    await FMP.get_profile(symbol, client) or
                    await Finnhub.get_profile(symbol, client)
                )
                result["metrics"] = (
                    await FMP.get_metrics(symbol, client) or
                    await Finnhub.get_metrics(symbol, client)
                )

            # Completar marketCap cruzando fuentes
            if result["profile"] and not result["profile"].get("marketCap"):
                mc = (result["quote"] or {}).get("marketCap")
                if mc:
                    result["profile"]["marketCap"] = mc
            if result["quote"] and not result["quote"].get("name"):
                name = (result["profile"] or {}).get("name")
                if name:
                    result["quote"]["name"] = name

            # HISTORICAL: FMP -> AV (Finnhub no tiene endpoint de historico gratis)
            print(f"[API] {symbol}: historico...")
            result["historical"] = (
                await FMP.get_historical(symbol, client) or
                await AlphaVantage.get_historical(symbol, client)
            )

        if result["quote"]:
            await Database.save(symbol, "all_data", result)

        q_src  = (result["quote"] or {}).get("source", "FALLO")
        hist_n = len(result["historical"]) if result["historical"] else 0
        has_m  = any(v is not None for v in (result["metrics"] or {}).values())
        print(f"[OK] {symbol}: quote={q_src}, metrics={'si' if has_m else 'no'}, hist={hist_n}d")

        return result
