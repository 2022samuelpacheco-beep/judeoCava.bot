import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import time
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
# FUNCIÓN: REINTENTAR CON DELAY (Para evitar Rate Limiting)
# ============================================================================

def obtener_con_reintentos(ticker, intentos=3, delay=2):
    """
    Obtiene datos de Yahoo Finance con reintentos y delays
    Evita rate limiting esperando entre intentos
    """
    for intento in range(intentos):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Si obtuvimos datos, retornar
            if info:
                return stock, info
        
        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate" in str(e):
                if intento < intentos - 1:
                    # Esperar antes de reintentar (backoff exponencial)
                    espera = delay * (2 ** intento)
                    time.sleep(espera)
                    continue
            raise
    
    return None, None

# ============================================================================
# FUNCIÓN 1: OBTENER PRECIO DE CRIPTOMONEDAS (CoinGecko - Sin Rate Limit)
# ============================================================================

async def precio_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /crypto bitcoin"""
    try:
        if not context.args:
            mensaje = (
                "📊 *Obtener Precio de Criptomonedas*\n\n"
                "Uso: `/crypto [nombre]`\n\n"
                "*Ejemplos:*\n"
                "`/crypto bitcoin`\n"
                "`/crypto ethereum`\n"
                "`/crypto dogecoin`"
            )
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return
        
        cripto_nombre = ' '.join(context.args).lower()
        url = "https://api.coingecko.com/api/v3/simple/price"
        
        params = {
            'ids': cripto_nombre,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true'
        }
        
        # CoinGecko no tiene rate limit, así que sin delay
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        datos = response.json()
        
        if cripto_nombre not in datos:
            await update.message.reply_text(f"❌ No encontré *{cripto_nombre}*")
            return
        
        cripto_data = datos[cripto_nombre]
        precio = cripto_data['usd']
        market_cap = cripto_data['usd_market_cap']
        volumen = cripto_data['usd_24h_vol']
        cambio_24h = cripto_data['usd_24h_change']
        
        emoji_cambio = "📈" if cambio_24h >= 0 else "📉"
        
        mensaje = f"""
💰 *{cripto_nombre.upper()}*
━━━━━━━━━━━━━━━━━━━━━━━━
💵 Precio: ${precio:,.2f}
{emoji_cambio} Cambio 24h: {cambio_24h:+.2f}%
📊 Market Cap: ${market_cap:,.0f}
🔄 Volumen 24h: ${volumen:,.0f}
        """
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN 2: OBTENER PRECIO CON REINTENTOS (Yahoo Finance)
# ============================================================================

async def precio_yfinance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /yf AAPL"""
    try:
        if not context.args:
            mensaje = (
                "📊 *Obtener Precio*\n\n"
                "Uso: `/yf [símbolo]`\n\n"
                "*Ejemplos:*\n"
                "`/yf AAPL`\n"
                "`/yf BTC-USD`\n"
                "`/yf ^GSPC`"
            )
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return
        
        simbolo = context.args[0].upper()
        
        # Mostrar que está procesando
        await update.message.reply_text(f"⏳ Obteniendo datos de {simbolo}...")
        
        # Obtener con reintentos
        stock, info = obtener_con_reintentos(simbolo)
        
        if not stock or not info:
            await update.message.reply_text(
                f"❌ No puedo obtener datos para *{simbolo}*\n\n"
                "_Intenta de nuevo en unos segundos_"
            )
            return
        
        precio = info.get('currentPrice', None)
        nombre = info.get('longName', simbolo)
        cambio = info.get('regularMarketChange', None)
        volumen = info.get('volume', None)
        
        if not precio:
            await update.message.reply_text(f"❌ No encontré datos para *{simbolo}*")
            return
        
        emoji = "📈" if cambio and cambio >= 0 else "📉"
        
        mensaje = f"""
{emoji} *{nombre}*
━━━━━━━━━━━━━━━━━━━━━━━━
💵 Precio: ${precio:.2f}
📊 Cambio: {cambio:+.2f}
🔄 Volumen: {volumen:,}
        """
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error al obtener datos\n\n"
            f"_Intenta de nuevo en unos segundos_"
        )

# ============================================================================
# FUNCIÓN 3: CONVERTIR MONEDAS
# ============================================================================

async def convertir_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /convertir 100 USD EUR"""
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "💱 Uso: `/convertir [cantidad] [de] [a]`\n"
                "Ejemplo: `/convertir 100 USD EUR`"
            )
            return
        
        cantidad = float(context.args[0])
        moneda_de = context.args[1].upper()
        moneda_a = context.args[2].upper()
        
        # Primero intentar con CoinGecko (sin rate limit)
        url = "https://api.coingecko.com/api/v3/simple/price"
        
        try:
            params = {
                'ids': moneda_de.lower(),
                'vs_currencies': moneda_a.lower()
            }
            
            response = requests.get(url, params=params, timeout=5)
            datos = response.json()
            
            if moneda_de.lower() in datos:
                tasa = datos[moneda_de.lower()].get(moneda_a.lower())
                
                if tasa:
                    resultado = cantidad * tasa
                    
                    mensaje = f"""
💱 *Conversión*
━━━━━━━━━━━━━━━━━━━━━━━━
{cantidad:,.2f} {moneda_de} = {resultado:,.2f} {moneda_a}
_Tasa: 1 {moneda_de} = {tasa:,.2f} {moneda_a}_
                    """
                    
                    await update.message.reply_text(mensaje, parse_mode='Markdown')
                    return
        except:
            pass
        
        # Si falla, intentar con Yahoo Finance (CON reintentos)
        try:
            await update.message.reply_text(f"⏳ Buscando tasa de cambio...")
            
            par = f"{moneda_de}{moneda_a}=X"
            stock, info = obtener_con_reintentos(par)
            
            if stock and info:
                tasa = info.get('currentPrice')
                
                if tasa:
                    resultado = cantidad * tasa
                    
                    mensaje = f"""
💱 *Conversión*
━━━━━━━━━━━━━━━━━━━━━━━━
{cantidad:,.2f} {moneda_de} = {resultado:,.2f} {moneda_a}
_Tasa: 1 {moneda_de} = {tasa:,.2f} {moneda_a}_
                """
                    
                    await update.message.reply_text(mensaje, parse_mode='Markdown')
                    return
        except:
            pass
        
        await update.message.reply_text(
            f"❌ No puedo convertir {moneda_de} a {moneda_a}\n\n"
            "_Intenta de nuevo en unos segundos_"
        )
    
    except ValueError:
        await update.message.reply_text("❌ El primer argumento debe ser un número")
    except Exception as e:
        await update.message.reply_text("⚠️ Error al procesar la conversión")

# ============================================================================
# FUNCIÓN 4: COMPARAR DOS ACTIVOS
# ============================================================================

async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /comparar AAPL GOOGL"""
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Uso: `/comparar [símbolo1] [símbolo2]`\n"
                "Ejemplo: `/comparar AAPL GOOGL`"
            )
            return
        
        sim1 = context.args[0].upper()
        sim2 = context.args[1].upper()
        
        await update.message.reply_text(f"⏳ Obteniendo datos...")
        
        # Obtener datos con reintentos
        stock1, info1 = obtener_con_reintentos(sim1)
        
        # Esperar un poco entre peticiones
        time.sleep(1)
        
        stock2, info2 = obtener_con_reintentos(sim2)
        
        if not (stock1 and info1 and stock2 and info2):
            await update.message.reply_text("❌ No puedo obtener los datos")
            return
        
        precio1 = info1.get('currentPrice', 0)
        precio2 = info2.get('currentPrice', 0)
        
        nombre1 = info1.get('longName', sim1)
        nombre2 = info2.get('longName', sim2)
        
        cambio1 = info1.get('regularMarketChange', 0)
        cambio2 = info2.get('regularMarketChange', 0)
        
        if precio1 and precio2:
            emoji1 = "📈" if cambio1 >= 0 else "📉"
            emoji2 = "📈" if cambio2 >= 0 else "📉"
            
            mensaje = f"""
⚖️ *Comparación*
━━━━━━━━━━━━━━━━━━━━━━━━
{emoji1} *{nombre1}*
💵 Precio: ${precio1:.2f}
📊 Cambio: {cambio1:+.2f}

{emoji2} *{nombre2}*
💵 Precio: ${precio2:.2f}
📊 Cambio: {cambio2:+.2f}
            """
            
            await update.message.reply_text(mensaje, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ No puedo obtener los datos")
    
    except Exception as e:
        await update.message.reply_text("⚠️ Error al comparar")

# ============================================================================
# FUNCIÓN 5: ANÁLISIS PROFESIONAL (CON MANEJO DE RATE LIMIT)
# ============================================================================

async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /analizar AAPL"""
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 Análisis Profesional\n\n"
                "Uso: `/analizar [símbolo]`\n"
                "Ejemplo: `/analizar AAPL`"
            )
            return
        
        simbolo = context.args[0].upper()
        await update.message.reply_text(f"🔍 Analizando {simbolo}... espera")
        
        # Obtener datos con reintentos
        stock, info = obtener_con_reintentos(simbolo)
        
        if not stock or not info:
            await update.message.reply_text(
                f"❌ No puedo obtener datos para {simbolo}\n\n"
                "_Intenta de nuevo en 30 segundos_"
            )
            return
        
        # Obtener histórico con reintentos
        try:
            hist = stock.history(period="1y")
        except:
            time.sleep(2)
            hist = stock.history(period="1y")
        
        if hist.empty:
            await update.message.reply_text(f"❌ No hay datos históricos para {simbolo}")
            return
        
        # Datos fundamentales
        nombre = info.get('longName', simbolo)
        precio = info.get('currentPrice', 0)
        market_cap = info.get('marketCap', 0)
        pe = info.get('trailingPE', 'N/A')
        forward_pe = info.get('forwardPE', 'N/A')
        eps = info.get('trailingEps', 'N/A')
        roe = info.get('returnOnEquity', 'N/A')
        roa = info.get('returnOnAssets', 'N/A')
        debt_equity = info.get('debtToEquity', 'N/A')
        dividend = info.get('dividendYield', 'N/A')
        sector = info.get('sector', 'N/A')
        
        # Calcular indicadores técnicos
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_actual = rsi.iloc[-1]
        
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_actual = macd.iloc[-1]
        signal_actual = signal.iloc[-1]
        
        ema20 = hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = hist['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        ema200 = hist['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
        
        volatilidad = hist['Close'].pct_change().std() * np.sqrt(252)
        
        high_52 = hist['Close'].max()
        low_52 = hist['Close'].min()
        
        # Mensaje 1: Resumen
        msg1 = f"""
╔════════════════════════════════╗
║      📊 {simbolo}
╚════════════════════════════════╝

**Empresa:** {nombre}
**Sector:** {sector}

💰 Precio: ${precio:.2f}
📈 Market Cap: ${market_cap/1e9:.2f}B

_(1/3) Procesando análisis..._
        """
        
        await update.message.reply_text(msg1, parse_mode='Markdown')
        
        # Mensaje 2: Fundamental
        pe_interpretacion = "Valuación BAJA" if (pe != 'N/A' and pe < 15) else "Valuación NORMAL" if (pe != 'N/A' and pe < 25) else "Valuación ALTA"
        roe_interpretacion = "EXCELENTE (>15%)" if (roe != 'N/A' and roe > 0.15) else "BUENO (>10%)" if (roe != 'N/A' and roe > 0.10) else "PROMEDIO"
        
        msg2 = f"""
╔════════════════════════════════╗
║    📊 ANÁLISIS FUNDAMENTAL
╚════════════════════════════════╝

**P/E Ratio:** {pe if pe != 'N/A' else 'N/A'}
→ {pe_interpretacion}

**Forward P/E:** {forward_pe if forward_pe != 'N/A' else 'N/A'}

**EPS:** ${eps if eps != 'N/A' else 'N/A'}

**ROE (Retorno):** {f'{roe*100:.2f}%' if roe != 'N/A' else 'N/A'}
→ {roe_interpretacion}

**ROA:** {f'{roa*100:.2f}%' if roa != 'N/A' else 'N/A'}

**Debt/Equity:** {debt_equity if debt_equity != 'N/A' else 'N/A'}

**Dividend Yield:** {f'{dividend*100:.2f}%' if dividend != 'N/A' else 'N/A'}

_(2/3) Análisis técnico..._
        """
        
        await update.message.reply_text(msg2, parse_mode='Markdown')
        
        # Mensaje 3: Técnico y conclusión
        rsi_estado = "SOBREVENTA" if rsi_actual < 30 else "SOBRECOMPRA" if rsi_actual > 70 else "NEUTRAL"
        macd_estado = "ALCISTA" if macd_actual > signal_actual else "BAJISTA"
        tendencia = "ALCISTA" if precio > ema200 else "BAJISTA"
        
        riesgos = []
        fortalezas = []
        
        if pe != 'N/A' and pe > 30:
            riesgos.append("⚠️ Valuación elevada")
        if rsi_actual > 70:
            riesgos.append("⚠️ Posible corrección (RSI)")
        if debt_equity != 'N/A' and debt_equity > 2:
            riesgos.append("⚠️ Alto endeudamiento")
        
        if roe != 'N/A' and roe > 0.15:
            fortalezas.append("✅ Excelente ROE")
        if macd_actual > signal_actual:
            fortalezas.append("✅ Momentum positivo")
        if precio > ema200:
            fortalezas.append("✅ Tendencia alcista")
        
        riesgos_txt = "\n".join(riesgos) if riesgos else "⚠️ Pocos riesgos detectados"
        fortalezas_txt = "\n".join(fortalezas) if fortalezas else "✅ Características normales"
        
        msg3 = f"""
╔════════════════════════════════╗
║    📈 ANÁLISIS TÉCNICO
╚════════════════════════════════╝

**RSI:** {rsi_actual:.2f} → {rsi_estado}
**MACD:** {macd_estado}
**Tendencia:** {tendencia}

**EMAs:**
├ EMA20: ${ema20:.2f}
├ EMA50: ${ema50:.2f}
└ EMA200: ${ema200:.2f}

**52 Semanas:**
├ Alto: ${high_52:.2f}
└ Bajo: ${low_52:.2f}

**Volatilidad:** {volatilidad*100:.2f}%

╔════════════════════════════════╗
║    🎯 CONCLUSIÓN
╚════════════════════════════════╝

**FORTALEZAS:**
{fortalezas_txt}

**RIESGOS:**
{riesgos_txt}

**Resumen:** {nombre} muestra señales {('alcistas' if precio > ema200 and macd_actual > signal_actual else 'bajistas' if precio < ema200 and macd_actual < signal_actual else 'mixtas')}.

⚖️ _Este análisis es educativo. No es recomendación._

_(3/3) Análisis completado ✓_
        """
        
        await update.message.reply_text(msg3, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Error al analizar\n\n"
            f"_Intenta de nuevo en 30 segundos_"
        )

# ============================================================================
# FUNCIONES MENÚ
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú principal"""
    
    nombre = update.effective_user.first_name
    
    mensaje = f"""
👋 *¡Hola {nombre}!*

Soy tu bot financiero profesional 📊

*💰 Comandos:*

`/crypto [nombre]` - Criptomonedas
`/yf [símbolo]` - Precio de activos
`/convertir [cant] [de] [a]` - Convertir monedas
`/comparar [sim1] [sim2]` - Comparar activos
`/analizar [símbolo]` - Análisis profesional ⭐
`/ayuda` - Ver más

_Datos en tiempo real | Rate Limit Manejado_
    """
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar ayuda"""
    
    mensaje = """
*📚 AYUDA*

`/crypto bitcoin` - Precio criptomonedas
`/yf AAPL` - Cualquier activo
`/yf BTC-USD` - Bitcoin
`/yf ^GSPC` - S&P 500
`/convertir 100 USD EUR` - Conversiones
`/comparar AAPL GOOGL` - Comparar
`/analizar AAPL` - Análisis profesional

⚠️ *Nota:* Si ves "rate limited", espera 30 segundos

*Todas las APIs son GRATUITAS*
    """
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar mensajes normales"""
    
    await update.message.reply_text(
        "🤖 No entiendo. Usa `/start` para ver comandos"
    )

# ============================================================================
# FUNCIÓN MAIN
# ============================================================================

def main():
    """Inicializar el bot"""
    
    app = Application.builder().token(TOKEN).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("crypto", precio_crypto))
    app.add_handler(CommandHandler("yf", precio_yfinance))
    app.add_handler(CommandHandler("convertir", convertir_crypto))
    app.add_handler(CommandHandler("comparar", comparar))
    app.add_handler(CommandHandler("analizar", analizar))
    
    # Procesar mensajes normales
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    
    print("✓ Bot iniciado - Rate Limiting Manejado")
    print("✓ Todos los comandos listos")
    
    app.run_polling()

if __name__ == '__main__':
    main()
