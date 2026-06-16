import httpx
import os
from database import Database

FMP_KEY = os.getenv("FMP_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")

class FMP:
    """Financial Modeling Prep API - Fuente Principal"""
    
    BASE_URL = "https://financialmodelingprep.com/api/v3"
    
    @staticmethod
    async def get_quote(symbol: str):
        """Obtener precio actual"""
        # Buscar en caché primero
        cached = await Database.get(symbol, "quote", max_age_minutes=30)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"{FMP.BASE_URL}/quote/{symbol}"
                params = {"apikey": FMP_KEY}
                
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        result = {
                            "symbol": data[0].get("symbol"),
                            "price": data[0].get("price"),
                            "change": data[0].get("change"),
                            "changePercent": data[0].get("changePercent"),
                            "timestamp": data[0].get("timestamp")
                        }
                        await Database.save(symbol, "quote", result)
                        return result
        except Exception as e:
            print(f"Error obteniendo quote de {symbol}: {e}")
        
        return None
    
    @staticmethod
    async def get_company_profile(symbol: str):
        """Obtener perfil de la empresa"""
        cached = await Database.get(symbol, "profile", max_age_minutes=1440)  # 24 horas
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"{FMP.BASE_URL}/profile/{symbol}"
                params = {"apikey": FMP_KEY}
                
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        result = {
                            "name": data[0].get("companyName"),
                            "sector": data[0].get("sector"),
                            "industry": data[0].get("industry"),
                            "marketCap": data[0].get("mktCap"),
                            "description": data[0].get("description")
                        }
                        await Database.save(symbol, "profile", result)
                        return result
        except Exception as e:
            print(f"Error obteniendo profile de {symbol}: {e}")
        
        return None
    
    @staticmethod
    async def get_key_metrics(symbol: str):
        """Obtener métricas fundamentales"""
        cached = await Database.get(symbol, "metrics", max_age_minutes=1440)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"{FMP.BASE_URL}/key-metrics/{symbol}"
                params = {"period": "annual", "apikey": FMP_KEY}
                
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        metrics = data[0]
                        result = {
                            "peRatio": metrics.get("peRatio"),
                            "roe": metrics.get("roe"),
                            "roa": metrics.get("roa"),
                            "debtToEquity": metrics.get("debtToEquity"),
                            "dividendYield": metrics.get("dividendYield"),
                            "revenueGrowth": metrics.get("revenueGrowth"),
                            "netMargin": metrics.get("netMargin")
                        }
                        await Database.save(symbol, "metrics", result)
                        return result
        except Exception as e:
            print(f"Error obteniendo metrics de {symbol}: {e}")
        
        return None
    
    @staticmethod
    async def get_historical_prices(symbol: str, days: int = 365):
        """Obtener histórico de precios"""
        cached = await Database.get(symbol, f"historical_{days}", max_age_minutes=120)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient() as client:
                url = f"{FMP.BASE_URL}/historical-price-full/{symbol}"
                params = {"apikey": FMP_KEY}
                
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data and "historical" in data:
                        # Obtener últimos N días
                        historical = data["historical"][:days]
                        result = {
                            "symbol": data["symbol"],
                            "historical": historical
                        }
                        await Database.save(symbol, f"historical_{days}", result)
                        return result
        except Exception as e:
            print(f"Error obteniendo historical de {symbol}: {e}")
        
        return None

class Finnhub:
    """Finnhub API - Datos complementarios (futuro)"""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    @staticmethod
    async def get_news(symbol: str, days: int = 7):
        """Obtener noticias"""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{Finnhub.BASE_URL}/company-news"
                params = {
                    "symbol": symbol,
                    "from": "2024-01-01",  # Cambiar dinámicamente
                    "to": "2024-12-31",
                    "token": FINNHUB_KEY
                }
                
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"Error obteniendo noticias de {symbol}: {e}")
        
        return None
