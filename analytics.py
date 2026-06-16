from typing import Dict, List

class TechnicalAnalysis:
    """Cálculos de indicadores técnicos (Sin numpy/pandas)"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calcular RSI (Relative Strength Index)"""
        try:
            if len(prices) < period + 1:
                return None
            
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            
            gains = [d if d > 0 else 0 for d in deltas[-period:]]
            losses = [-d if d < 0 else 0 for d in deltas[-period:]]
            
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            
            if avg_loss == 0:
                return 100.0 if avg_gain > 0 else 0.0
            
            rs = avg_gain / avg_loss
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
            
            sma = sum(prices[-period:]) / period
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
            prices = [float(day.get("close", 0)) for day in historical_data]
            
            if not prices or len(prices) < 200:
                return None
            
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
                "current_price": round(current_price, 2),
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
                "pe_ratio": metrics.get("peRatio") if metrics else None,
                "roe": metrics.get("roe") if metrics else None,
                "dividend_yield": metrics.get("dividendYield") if metrics else None,
                "revenue_growth": metrics.get("revenueGrowth") if metrics else None,
                "debt_to_equity": metrics.get("debtToEquity") if metrics else None,
                "net_margin": metrics.get("netMargin") if metrics else None
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
            pe = fundamental.get("pe_ratio") if fundamental else None
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
            roe = fundamental.get("roe") if fundamental else None
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
            rsi = technical.get("rsi") if technical else None
            if rsi:
                if rsi < 70:
                    score += 25
                    details.append("✅ RSI normal (sin sobrecompra)")
                else:
                    score += 10
                    details.append("⚠️ RSI alto (posible corrección)")
            
            # 4. Tendencia (SMA)
            if technical:
                sma50 = technical.get("sma50")
                sma200 = technical.get("sma200")
                if sma50 and sma200:
                    if sma50 > sma200:
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
