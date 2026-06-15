import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

TOKEN = os.environ.get('TOKEN')
ALPHA_KEY = os.environ.get('ALPHA_VANTAGE_KEY')

if not TOKEN:
    raise ValueError("TOKEN no está configurado.")

keep_alive()

# ============================================================================
# FUNCIÓN: ANÁLISIS FINANCIERO PROFESIONAL COMPLETO
# ============================================================================

def calcular_indicadores_tecnicos(ticker):
    """
    Calcula todos los indicadores técnicos para un activo
    """
    try:
        # Descargar datos históricos (último año)
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        
        if hist.empty:
            return None
        
        # Calcular indicadores técnicos manualmente
        indicadores = {}
        
        # RSI (14 períodos)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        indicadores['RSI'] = rsi.iloc[-1]
        
        # MACD
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicadores['MACD'] = macd.iloc[-1]
        indicadores['Signal_Line'] = signal.iloc[-1]
        
        # EMAs
        indicadores['EMA20'] = hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        indicadores['EMA50'] = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        indicadores['EMA100'] = hist['Close'].ewm(span=100, adjust=False).mean().iloc[-1]
        indicadores['EMA200'] = hist['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        
        # Volatilidad
        indicadores['Volatilidad'] = hist['Close'].pct_change().std() * np.sqrt(252)
        
        # Soportes y Resistencias (últimos 52 semanas)
        indicadores['52W_High'] = hist['Close'].max()
        indicadores['52W_Low'] = hist['Close'].min()
        indicadores['Support'] = hist['Close'].tail(50).min()
        indicadores['Resistance'] = hist['Close'].tail(50).max()
        
        # Volumen
        indicadores['Avg_Volume'] = hist['Volume'].mean()
        indicadores['Current_Volume'] = hist['Volume'].iloc[-1]
        
        return indicadores
    
    except Exception as e:
        return None

def obtener_datos_fundamentales(ticker):
    """
    Obtiene datos fundamentales de Yahoo Finance
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        datos = {
            'company_name': info.get('longName', 'N/A'),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'current_price': info.get('currentPrice', 0),
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('trailingPE', 'N/A'),
            'forward_pe': info.get('forwardPE', 'N/A'),
            'eps': info.get('trailingEps', 'N/A'),
            'roe': info.get('returnOnEquity', 'N/A'),
            'roa': info.get('returnOnAssets', 'N/A'),
            'net_margin': info.get('profitMargins', 'N/A'),
            'operating_margin': info.get('operatingMargins', 'N/A'),
            'debt_equity': info.get('debtToEquity', 'N/A'),
            'dividend_yield': info.get('dividendYield', 'N/A'),
            'revenue_growth': info.get('revenueGrowth', 'N/A'),
            'earnings_growth': info.get('earningsGrowth', 'N/A'),
            'free_cash_flow': info.get('freeCashflow', 'N/A'),
            'book_value': info.get('bookValue', 'N/A'),
            'beta': info.get('beta', 'N/A'),
            'description': info.get('longBusinessSummary', 'N/A')[:500]
        }
        
        return datos
    
    except Exception as e:
        return None

def formatear_numero(valor, es_porcentaje=False):
    """Formatea números para presentación"""
    if valor == 'N/A' or valor is None:
        return 'N/A'
    
    try:
        if es_porcentaje:
            return f"{valor*100:.2f}%"
        if valor >= 1e9:
            return f"${valor/1e9:.2f}B"
        if valor >= 1e6:
            return f"${valor/1e6:.2f}M"
        return f"{valor:.2f}"
    except:
        return 'N/A'

def generar_informe_profesional(ticker):
    """
    Genera informe profesional completo
    """
    try:
        # Obtener datos
        datos_fund = obtener_datos_fundamentales(ticker)
        datos_tecn = calcular_indicadores_tecnicos(ticker)
        
        if not datos_fund or not datos_tecn:
            return None
        
        informe = {
            'datos_fundamentales': datos_fund,
            'datos_tecnicos': datos_tecn
        }
        
        return informe
    
    except Exception as e:
        return None

async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando: /analizar [símbolo]
    Ejemplo: /analizar AAPL
    
    Genera análisis financiero profesional completo
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 *Análisis Financiero Profesional*\n\n"
                "Uso: `/analizar [símbolo]`\n\n"
                "Ejemplo: `/analizar AAPL`\n\n"
                "_Genera análisis fundamental y técnico completo_"
            )
            return
        
        simbolo = context.args[0].upper()
        
        # Mostrar que está procesando
        await update.message.reply_text(f"🔍 Analizando {simbolo}... Por favor espera...")
        
        # Generar informe
        informe = generar_informe_profesional(simbolo)
        
        if not informe:
            await update.message.reply_text(f"❌ No puedo obtener datos para {simbolo}")
            return
        
        datos_f = informe['datos_fundamentales']
        datos_t = informe['datos_tecnicos']
        
        # ==== MENSAJE 1: RESUMEN GENERAL ====
        
        precio = datos_f['current_price']
        market_cap = datos_f['market_cap']
        sector = datos_f['sector']
        
        resumen = f"""
╔════════════════════════════════════╗
║     📊 ANÁLISIS: {simbolo}
╚════════════════════════════════════╝

**Empresa:** {datos_f['company_name']}
**Sector:** {sector}

💰 **Precio Actual:** ${precio:.2f}
📈 **Market Cap:** {formatear_numero(market_cap)}

**Descripción:**
_{datos_f['description']}_

⏳ *Obteniendo análisis... (1/4)*
        """
        
        msg1 = await update.message.reply_text(resumen, parse_mode='Markdown')
        
        # ==== MENSAJE 2: ANÁLISIS FUNDAMENTAL ====
        
        pe = datos_f['pe_ratio']
        forward_pe = datos_f['forward_pe']
        eps = datos_f['eps']
        roe = datos_f['roe']
        roa = datos_f['roa']
        
        # Interpretaciones
        if pe != 'N/A' and pe > 0:
            pe_interpretacion = "Valuación BAJA (Oportunidad)" if pe < 15 else "Valuación NORMAL" if pe < 25 else "Valuación ALTA (Premium)"
        else:
            pe_interpretacion = "No disponible"
        
        if roe != 'N/A':
            roe_interpretacion = "EXCELENTE (>15%)" if roe > 0.15 else "BUENO (>10%)" if roe > 0.10 else "PROMEDIO"
        else:
            roe_interpretacion = "No disponible"
        
        fundamental = f"""
╔════════════════════════════════════╗
║   📊 ANÁLISIS FUNDAMENTAL
╚════════════════════════════════════╝

**P/E Ratio (Relación Precio/Ganancias)**
├ ¿Qué es?: Compara precio con ganancias
├ Valor: {pe if pe != 'N/A' else 'N/A'} x
└ Interpretación: {pe_interpretacion}

**Forward P/E**
├ ¿Qué es?: P/E esperado próximo año
├ Valor: {forward_pe if forward_pe != 'N/A' else 'N/A'} x
└ Interpretación: Ganancias futuras

**EPS (Ganancias por Acción)**
├ ¿Qué es?: Beneficio generado por acción
├ Valor: ${eps if eps != 'N/A' else 'N/A'}
└ Tendencia: Crecimiento de rentabilidad

**ROE (Retorno sobre Patrimonio)**
├ ¿Qué es?: Rentabilidad generada con capital
├ Valor: {formatear_numero(roe, True) if roe != 'N/A' else 'N/A'}
└ Interpretación: {roe_interpretacion}

**ROA (Retorno sobre Activos)**
├ ¿Qué es?: Eficiencia en uso de activos
├ Valor: {formatear_numero(roa, True) if roa != 'N/A' else 'N/A'}
└ Interpretación: Eficiencia operativa

**Debt to Equity (Deuda vs Capital)**
├ ¿Qué es?: Nivel de endeudamiento
├ Valor: {datos_f['debt_equity'] if datos_f['debt_equity'] != 'N/A' else 'N/A'}
└ Interpretación: {'Bajo riesgo' if datos_f['debt_equity'] != 'N/A' and datos_f['debt_equity'] < 1 else 'Riesgo moderado' if datos_f['debt_equity'] != 'N/A' else 'N/A'}

**Dividend Yield**
├ ¿Qué es?: Rendimiento por dividendos
├ Valor: {formatear_numero(datos_f['dividend_yield'], True) if datos_f['dividend_yield'] != 'N/A' else 'N/A'}
└ Interpretación: {'Buen dividendo' if datos_f['dividend_yield'] != 'N/A' and datos_f['dividend_yield'] > 0.03 else 'Dividendo bajo/nulo'}

⏳ *Análisis fundamental completado... (2/4)*
        """
        
        await update.message.reply_text(fundamental, parse_mode='Markdown')
        
        # ==== MENSAJE 3: ANÁLISIS TÉCNICO ====
        
        rsi = datos_t['RSI']
        macd = datos_t['MACD']
        signal = datos_t['Signal_Line']
        ema20 = datos_t['EMA20']
        ema50 = datos_t['EMA50']
        ema200 = datos_t['EMA200']
        
        # Interpretaciones técnicas
        if rsi < 30:
            rsi_estado = "SOBREVENTA (Posible rebote)"
        elif rsi > 70:
            rsi_estado = "SOBRECOMPRA (Posible caída)"
        else:
            rsi_estado = "NEUTRAL"
        
        if macd > signal:
            macd_estado = "ALCISTA (Momentum positivo)"
        else:
            macd_estado = "BAJISTA (Momentum negativo)"
        
        if precio > ema200:
            tendencia = "ALCISTA (Arriba de EMA200)"
        else:
            tendencia = "BAJISTA (Abajo de EMA200)"
        
        tecnico = f"""
╔════════════════════════════════════╗
║   📈 ANÁLISIS TÉCNICO
╚════════════════════════════════════╝

**RSI (Índice de Fuerza Relativa)**
├ ¿Qué es?: Mide impulso de precios 0-100
├ Valor: {rsi:.2f}
├ Nivel: {rsi_estado}
└ Señal: Zona de {('sobrecompra' if rsi > 70 else 'sobreventa' if rsi < 30 else 'equilibrio')}

**MACD (Convergencia/Divergencia)**
├ ¿Qué es?: Indicador de tendencia e impulso
├ MACD: {macd:.4f}
├ Signal: {signal:.4f}
├ Diferencia: {macd - signal:.4f}
└ Interpretación: {macd_estado}

**Promedios Móviles (EMAs)**
├ EMA 20: ${ema20:.2f} (Corto plazo)
├ EMA 50: ${ema50:.2f} (Mediano plazo)
├ EMA 100: ${datos_t['EMA100']:.2f}
├ EMA 200: ${ema200:.2f} (Largo plazo)
└ Tendencia: {tendencia}

**Soportes y Resistencias**
├ Resistencia: ${datos_t['Resistance']:.2f}
├ Precio Actual: ${precio:.2f}
├ Soporte: ${datos_t['Support']:.2f}
└ Rango 52 semanas: ${datos_t['52W_Low']:.2f} - ${datos_t['52W_High']:.2f}

**Volumen**
├ Volumen Promedio: {formatear_numero(datos_t['Avg_Volume'])}
├ Volumen Actual: {formatear_numero(datos_t['Current_Volume'])}
└ Comparación: {'Alto' if datos_t['Current_Volume'] > datos_t['Avg_Volume'] * 1.2 else 'Normal'}

**Volatilidad**
├ ¿Qué es?: Fluctuación de precios
├ Valor: {datos_t['Volatilidad']*100:.2f}%
└ Interpretación: {'Alta volatilidad (Riesgo)' if datos_t['Volatilidad'] > 0.3 else 'Volatilidad normal' if datos_t['Volatilidad'] > 0.15 else 'Baja volatilidad'}

⏳ *Análisis técnico completado... (3/4)*
        """
        
        await update.message.reply_text(tecnico, parse_mode='Markdown')
        
        # ==== MENSAJE 4: CONCLUSIÓN ====
        
        # Análisis de riesgos
        riesgos = []
        if pe != 'N/A' and pe > 30:
            riesgos.append("Valuación elevada")
        if rsi > 70:
            riesgos.append("Posible corrección (RSI en sobrecompra)")
        if datos_f['debt_equity'] != 'N/A' and datos_f['debt_equity'] > 2:
            riesgos.append("Alto endeudamiento")
        if datos_t['Volatilidad'] > 0.3:
            riesgos.append("Alta volatilidad")
        
        # Fortalezas
        fortalezas = []
        if roe != 'N/A' and roe > 0.15:
            fortalezas.append("Excelente ROE (rentabilidad)")
        if macd > signal:
            fortalezas.append("Momentum técnico positivo")
        if precio > ema200:
            fortalezas.append("Tendencia alcista (precio > EMA200)")
        if datos_f['dividend_yield'] != 'N/A' and datos_f['dividend_yield'] > 0.03:
            fortalezas.append("Buen rendimiento por dividendos")
        
        riesgos_txt = "\n".join([f"⚠️ {r}" for r in riesgos]) if riesgos else "⚠️ Pocos riesgos detectados"
        fortalezas_txt = "\n".join([f"✅ {f}" for f in fortalezas]) if fortalezas else "✅ Características normales"
        
        conclusion = f"""
╔════════════════════════════════════╗
║   🎯 CONCLUSIÓN PROFESIONAL
╚════════════════════════════════════╝

**FORTALEZAS DETECTADAS**
{fortalezas_txt}

**RIESGOS DETECTADOS**
{riesgos_txt}

**TENDENCIA GENERAL**
Basado en análisis técnico: {tendencia}

**RESUMEN**
{simbolo} muestra {'señales alcistas' if precio > ema200 and macd > signal else 'señales bajistas' if precio < ema200 and macd < signal else 'señales mixtas'} en el análisis técnico.

La valuación es {'atractiva (bajo P/E)' if pe != 'N/A' and pe < 15 else 'normal' if pe != 'N/A' and pe < 25 else 'elevada'} y la rentabilidad {'es fuerte' if roe != 'N/A' and roe > 0.15 else 'es normal' if roe != 'N/A' else 'no disponible'}.

**DESCARGO DE RESPONSABILIDAD**
Este análisis tiene fines educativos e informativos únicamente. No constituye asesoramiento financiero, recomendación de compra/venta ni garantía de rendimientos futuros. Realizar análisis independiente y consultar con asesor financiero antes de invertir.

---
*Análisis generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*
*Fuentes: Yahoo Finance, análisis técnico calculado*
        """
        
        await update.message.reply_text(conclusion, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN START (SIN CAMBIOS)
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú principal del bot"""
    
    nombre = update.effective_user.first_name
    
    mensaje = f"""
👋 *¡Hola {nombre}!*

Soy tu bot de información financiera PROFESIONAL en tiempo real.

*📊 Comandos Disponibles:*

💰 *Criptomonedas:*
`/crypto [nombre]` - Obtener precio (ej: /crypto bitcoin)

📈 *Acciones:*
`/stock [símbolo]` - Precio de acciones (ej: /stock AAPL)
`/yf [símbolo]` - Cualquier activo (ej: /yf TSLA)

📊 *ANÁLISIS PROFESIONAL:*
`/analizar [símbolo]` - Análisis financiero completo (ej: /analizar AAPL)

💱 *Conversión:*
`/convertir [cantidad] [de] [a]` - Convertir monedas (ej: /convertir 100 USD EUR)

⚖️ *Comparación:*
`/comparar [símbolo1] [símbolo2]` - Comparar dos activos (ej: /comparar AAPL GOOGL)

*Fuentes:*
🔹 CoinGecko - Criptomonedas
🔹 Yahoo Finance - Análisis profesional
🔹 Alpha Vantage - Stocks (opcional)

━━━━━━━━━━━━━━━━━━━━━━━━
_Todos los datos en tiempo real_
    """
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

# ============================================================================
# FUNCIÓN MAIN
# ============================================================================

def main():
    """Inicializar el bot"""
    
    app = Application.builder().token(TOKEN).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analizar", analizar))
    # ... (agregar otros handlers aquí)
    
    print("✓ Bot iniciado con Análisis Financiero Profesional")
    print("✓ Comando /analizar disponible")
    app.run_polling()

if __name__ == '__main__':
    main()
