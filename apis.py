import httpx
import json
from database import Database

# ============================================================================
# YAHOO FINANCE - Fuente principal (stocks y ETFs, 100% gratis)
# ============================================================================

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_QUOTE = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

class Yahoo:
    """Yahoo Finance API - Gratis, sin key, stocks y ETFs"""

    @staticmethod
    async def get_quote(symbol: str):
        """Obtener precio actual"""
        cached = await Database.get(symbol, "quote", max_age_minutes=15)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                url = f"{YAHOO_QUOTE}/{symbol}"
                params = {
                    "modules": "price,summaryDetail,defaultKeyStatistics,financialData",
                    "crumb": ""
                }
                response = await client.get(url, params=params, headers=HEADERS, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    result_data = data.get("quoteSummary", {}).get("result", [])

                    if result_data:
                        price_data = result_data[0].get("price", {})
                        result = {
                            "symbol": symbol,
                            "price": price_data.get("regularMarketPrice", {}).get("raw"),
                            "changePercent": price_data.get("regularMarketChangePercent", {}).get("raw", 0) * 100
                            if price_data.get("regularMarketChangePercent", {}).get("raw") is not None else 0,
                            "name": price_data.get("longName") or price_data.get("shortName", symbol),
                            "marketCap": price_data.get("marketCap", {}).get("raw"),
                            "currency": price_data.get("currency", "USD"),
                        }
                        if result["price"]:
                            await Database.save(symbol, "quote", result)
                            return result

            # Fallback: chart endpoint más simple
            return await Yahoo._get_quote_chart(symbol)

        except Exception as e:
            print(f"Yahoo quote error: {e}")
            return await Yahoo._get_quote_chart(symbol)

    @staticmethod
    async def _get_quote_chart(symbol: str):
        """Fallback usando endpoint de chart"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{YAHOO_BASE}/{symbol}"
                params = {"interval": "1d", "range": "5d"}
                response = await client.get(url, params=params, headers=HEADERS, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})

                    price = meta.get("regularMarketPrice")
                    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

                    if price and prev_close and prev_close != 0:
                        change_pct = ((price - prev_close) / prev_close) * 100
                    else:
                        change_pct = 0

                    if price:
                        result = {
                            "symbol": symbol,
                            "price": price,
                            "changePercent": round(change_pct, 2),
                            "name": meta.get("longName") or meta.get("symbol", symbol),
                            "marketCap": None,
                            "currency": meta.get("currency", "USD"),
                        }
                        await Database.save(symbol, "quote", result)
                        return result
        except Exception as e:
            print(f"Yahoo chart fallback error: {e}")
        return None

    @staticmethod
    async def get_key_metrics(symbol: str):
        """Obtener métricas fundamentales"""
        cached = await Database.get(symbol, "metrics", max_age_minutes=1440)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                url = f"{YAHOO_QUOTE}/{symbol}"
                params = {
                    "modules": "defaultKeyStatistics,financialData,summaryDetail"
                }
                response = await client.get(url, params=params, headers=HEADERS, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    result_data = data.get("quoteSummary", {}).get("result", [])

                    if result_data:
                        stats = result_data[0].get("defaultKeyStatistics", {})
                        fin = result_data[0].get("financialData", {})
                        summary = result_data[0].get("summaryDetail", {})

                        def raw(d, key):
                            val = d.get(key, {})
                            return val.get("raw") if isinstance(val, dict) else val

                        result = {
                            "peRatio": raw(summary, "trailingPE") or raw(stats, "forwardPE"),
                            "roe": raw(fin, "returnOnEquity"),
                            "roa": raw(fin, "returnOnAssets"),
                            "debtToEquity": raw(fin, "debtToEquity"),
                            "dividendYield": raw(summary, "dividendYield"),
                            "revenueGrowth": raw(fin, "revenueGrowth"),
                            "netMargin": raw(fin, "profitMargins"),
                        }
                        await Database.save(symbol, "metrics", result)
                        return result
        except Exception as e:
            print(f"Yahoo metrics error: {e}")
        return None

    @staticmethod
    async def get_historical_prices(symbol: str, days: int = 365):
        """Obtener historial de precios"""
        cached = await Database.get(symbol, f"historical_{days}", max_age_minutes=120)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                url = f"{YAHOO_BASE}/{symbol}"
                params = {
                    "interval": "1d",
                    "range": "2y",  # 2 años para tener suficientes datos para SMA200
                }
                response = await client.get(url, params=params, headers=HEADERS, timeout=20)

                if response.status_code == 200:
                    data = response.json()
                    result_data = data.get("chart", {}).get("result", [])

                    if result_data:
                        timestamps = result_data[0].get("timestamp", [])
                        closes = result_data[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])

                        historical = []
                        for ts, close in zip(timestamps, closes):
                            if close is not None:
                                historical.append({"close": close, "timestamp": ts})

                        if len(historical) >= 50:
                            result = {
                                "symbol": symbol,
                                "historical": historical[::-1],  # más reciente primero
                            }
                            await Database.save(symbol, f"historical_{days}", result)
                            return result
        except Exception as e:
            print(f"Yahoo historical error: {e}")
        return None

    @staticmethod
    async def get_company_profile(symbol: str):
        """Obtener perfil de la empresa"""
        cached = await Database.get(symbol, "profile", max_age_minutes=1440)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                url = f"{YAHOO_QUOTE}/{symbol}"
                params = {"modules": "assetProfile,price"}
                response = await client.get(url, params=params, headers=HEADERS, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    result_data = data.get("quoteSummary", {}).get("result", [])

                    if result_data:
                        profile = result_data[0].get("assetProfile", {})
                        price_d = result_data[0].get("price", {})

                        result = {
                            "name": price_d.get("longName") or price_d.get("shortName", symbol),
                            "sector": profile.get("sector", "N/A"),
                            "industry": profile.get("industry", "N/A"),
                            "marketCap": price_d.get("marketCap", {}).get("raw") if isinstance(price_d.get("marketCap"), dict) else None,
                            "description": (profile.get("longBusinessSummary", "N/A") or "N/A")[:300],
                        }
                        await Database.save(symbol, "profile", result)
                        return result
        except Exception as e:
            print(f"Yahoo profile error: {e}")
        return None


# ============================================================================
# COINGECKO - Para criptomonedas (100% gratis)
# ============================================================================

CRYPTO_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
    "SOL": "solana", "ADA": "cardano", "XRP": "ripple",
    "DOGE": "dogecoin", "DOT": "polkadot", "AVAX": "avalanche-2",
    "MATIC": "matic-network", "LTC": "litecoin", "LINK": "chainlink",
    "UNI": "uniswap", "ATOM": "cosmos", "XLM": "stellar",
}

class CoinGecko:
    """CoinGecko API - Cripto gratis"""
    BASE_URL = "https://api.coingecko.com/api/v3"

    @staticmethod
    def get_coin_id(symbol: str) -> str:
        """Convertir símbolo a ID de CoinGecko"""
        return CRYPTO_MAP.get(symbol.upper(), symbol.lower())

    @staticmethod
    async def get_quote(symbol: str):
        """Precio de cripto"""
        coin_id = CoinGecko.get_coin_id(symbol)
        cached = await Database.get(f"CRYPTO_{symbol}", "quote", max_age_minutes=10)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                url = f"{CoinGecko.BASE_URL}/simple/price"
                params = {
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                }
                response = await client.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if coin_id in data:
                        d = data[coin_id]
                        result = {
                            "symbol": symbol.upper(),
                            "price": d.get("usd"),
                            "changePercent": d.get("usd_24h_change", 0),
                            "name": symbol.upper(),
                            "marketCap": d.get("usd_market_cap"),
                            "currency": "USD",
                        }
                        await Database.save(f"CRYPTO_{symbol}", "quote", result)
                        return result
        except Exception as e:
            print(f"CoinGecko error: {e}")
        return None

    @staticmethod
    async def get_historical_prices(symbol: str, days: int = 365):
        """Historial de precios de cripto"""
        coin_id = CoinGecko.get_coin_id(symbol)
        cached = await Database.get(f"CRYPTO_{symbol}", "historical_365", max_age_minutes=120)
        if cached:
            return cached

        try:
            async with httpx.AsyncClient() as client:
                url = f"{CoinGecko.BASE_URL}/coins/{coin_id}/market_chart"
                params = {"vs_currency": "usd", "days": "730", "interval": "daily"}
                response = await client.get(url, params=params, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    prices = data.get("prices", [])
                    historical = [{"close": p[1], "timestamp": p[0] // 1000} for p in prices]

                    if len(historical) >= 50:
                        result = {
                            "symbol": symbol.upper(),
                            "historical": historical[::-1],
                        }
                        await Database.save(f"CRYPTO_{symbol}", "historical_365", result)
                        return result
        except Exception as e:
            print(f"CoinGecko historical error: {e}")
        return None


# ============================================================================
# DETECTOR: ¿stock o cripto?
# ============================================================================

CRYPTO_SYMBOLS = set(CRYPTO_MAP.keys()) | {
    "USDT", "USDC", "BUSD", "SHIB", "TRX", "TON", "NEAR", "ICP", "VET",
}

def is_crypto(symbol: str) -> bool:
    return symbol.upper() in CRYPTO_SYMBOLS
