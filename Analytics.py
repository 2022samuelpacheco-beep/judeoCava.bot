import pandas as pd
import numpy as np
from typing import Dict, List

class TechnicalAnalysis:
    """Cálculos de indicadores técnicos"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calcular RSI (Relative Strength Index)"""
        try:
            if len(prices) < period:
                return None
            
            prices = np.array(prices)
            deltas = np.diff(prices)
            
            seed = deltas[:period+1]
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            
            rs = up / down if down != 0 else 0
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
        except Exception as e:
            print(f"Error calculando RSI: {e}")
            return None
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> float:
        """Calcular SMA (Simple Moving Average)"""
        try:
            if len(prices) < period:
                return None
            
            prices = np.array(prices[-period:])
            sma = prices.mean()
            
            return round(sma, 2)
        except Exception as e:
            print(f"Error calculando SMA: {e}")
            return None
    
    @staticmethod
    def analyze_technicals(historical_data: List[Dict]) -> Dict:
        """Análisis técnico completo"""
        try:
            if not historical_data or len(historical_data) < 200:
                return None
            
            # Invertir para que sea cronológico (ascendente)
            historical_data = historical_data[::-1]
            
            # Extraer precios
            prices = [float(day["close"]) for day in historical_data]
            
            # Calcular indicadores
            current_price = prices[-1]
            sma50 = TechnicalAnalysis.calculate_sma(prices, 50)
            sma200 = TechnicalAnalysis.calculate_sma(prices, 200)
            rsi = TechnicalAnalysis.calculate_rsi(prices, 14)
            
            # Determinar tendencia
            if sma50 and sma200:
                trend = "ALCISTA" if sma50 > sma200 else "BAJISTA"
            else:
                trend = "NEUTRAL"
            
            return {
                "current_price": current_price,
                "sma50": sma50,
                "sma200": sma200,
                "rsi": rsi,
                "trend": trend
            }
        except Exception as e:
            print(f"Error en análisis técnico: {e}")
            return None

class FundamentalAnalysis:
    """Análisis fundamental"""
    
    @staticmethod
    def analyze_fundamentals(metrics: Dict, quote: Dict) -> Dict:
        """Análisis fundamental completo"""
        try:
            result = {
                "pe_ratio": metrics.get("peRatio"),
                "roe": metrics.get("roe"),
                "dividend_yield": metrics.get("dividendYield"),
                "revenue_growth": metrics.get("revenueGrowth"),
                "debt_to_equity": metrics.get("debtToEquity"),
                "net_margin": metrics.get("netMargin")
            }
            
            return result
        except Exception as e:
            print(f"Error en análisis fundamental: {e}")
            return None

class ScoringSystem:
    """Sistema de puntuación 0-100"""
    
    @staticmethod
    def calculate_score(technical: Dict, fundamental: Dict) -> Dict:
        """
        Calcular score basado en:
        - P/E saludable: +25
        - ROE > 15%: +25
        - RSI < 70 (no sobrecompra): +25
        - SMA50 > SMA200 (tendencia alcista): +25
        """
        try:
            score = 0
            details = []
            
            # 1. P/E Ratio (Valuación)
            pe = fundamental.get("pe_ratio")
            if pe:
                if 10 < pe < 30:
                    score += 25
                    details.append("✅ P/E saludable")
                elif pe < 10:
                    score += 20
                    details.append("🟡 P/E bajo (posible valor)")
                else:
                    score += 10
                    details.append("🔴 P/E alto (valuación cara)")
            
            # 2. ROE (Rentabilidad)
            roe = fundamental.get("roe")
            if roe:
                if roe > 0.15:
                    score += 25
                    details.append("✅ ROE excelente (>15%)")
                elif roe > 0.10:
                    score += 15
                    details.append("🟡 ROE bueno (10-15%)")
                else:
                    score += 5
                    details.append("🔴 ROE bajo (<10%)")
            
            # 3. RSI (Momentum)
            rsi = technical.get("rsi")
            if rsi:
                if rsi < 70:
                    score += 25
                    details.append("✅ RSI normal (sin sobrecompra)")
                else:
                    score += 10
                    details.append("⚠️ RSI alto (posible corrección)")
            
            # 4. Tendencia (SMA)
            if technical.get("sma50") and technical.get("sma200"):
                if technical["sma50"] > technical["sma200"]:
                    score += 25
                    details.append("✅ Tendencia alcista (SMA50 > SMA200)")
                else:
                    score += 10
                    details.append("🔴 Tendencia bajista (SMA50 < SMA200)")
            
            return {
                "total_score": min(score, 100),
                "details": details
            }
        except Exception as e:
            print(f"Error calculando score: {e}")
            return {"total_score": 0, "details": []}
