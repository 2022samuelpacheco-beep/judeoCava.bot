import os
import requests
import yfinance as yf
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

# Variables de entorno
TOKEN = os.environ.get('TOKEN')
ALPHA_KEY = os.environ.get('ALPHA_VANTAGE_KEY')

if not TOKEN:
    raise ValueError("TOKEN no configurado")

keep_alive()

# ============================================================================
# 1. PRECIO DE CRIPTOMONEDAS (CoinGecko)
# ============================================================================

async def precio_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /crypto bitcoin"""
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 Uso: `/crypto [nombre]`\n"
                "Ejemplo: `/crypto bitcoin`",
                parse_mode='Markdown'
            )
            return
        
        cripto = ' '.join(context.args).lower()
        url = "https://api.coingecko.com/api/v3/simple/price"
        
        params = {
            'ids': cripto,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_change': 'true'
        }
        
        response = requests.get(url, params=params, timeout=5)
        datos = response.json()
        
        if cripto not in datos:
            await update.message.reply_text(f"❌ No encontré {cripto}")
            return
        
        data = datos[cripto]
        precio = data['usd']
        cambio = data['usd_24h_change']
        market_cap = data.get('usd_market_cap')
        
        emoji = "📈" if cambio >= 0 else "📉"
        
        msg = f"""
💰 *{cripto.upper()}*
━━━━━━━━━━━━━
💵 Precio: ${precio:,.2f}
{emoji} Cambio 24h: {cambio:+.2f}%
📊 Market Cap: ${market_cap:,.0f}
        """
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error en crypto: {str(e)}")

# ============================================================================
# 2. PRECIO CON ALPHA VANTAGE (Acciones)
# ============================================================================

async def precio_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /stock AAPL"""
    try:
        if not ALPHA_KEY:
            await update.message.reply_text(
                "⚠️ Alpha Vantage no configurado\n"
                "Usa `/yf` en su lugar"
            )
            return
        
        if not context.args:
            await update.message.reply_text(
                "Uso: `/stock [símbolo]`\n"
                "Ejemplo: `/stock AAPL`"
            )
            return
        
        simbolo = context.args[0].upper()
        url = "https://www.alphavantage.co/query"
        
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': simbolo,
            'apikey': ALPHA_KEY
        }
        
        response = requests.get(url, params=params, timeout=5)
        datos = response.json()
        
        if 'Global Quote' not in datos or not datos['Global Quote']:
            await update.message.reply_text(f"❌ No encontré {simbolo}")
            return
        
        quote = datos['Global Quote']
        precio = float(quote.get('05. price', 0))
        cambio = float(quote.get('09. change', 0))
        volumen = int(float(quote.get('06. volume', 0)))
        
        emoji = "📈" if cambio >= 0 else "📉"
        
        msg = f"""
{emoji} *{simbolo}*
━━━━━━━━━━━━━
💵 Precio: ${precio:.2f}
📊 Cambio: {cambio:+.2f}
🔄 Volumen: {volumen:,}
        """
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error en stock: {str(e)}")

# ============================================================================
# 3. PRECIO CON YAHOO FINANCE (General)
# ============================================================================

async def precio_yfinance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /yf AAPL"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Uso: `/yf [símbolo]`\n"
                "Ejemplo: `/yf AAPL`"
            )
            return
        
        simbolo = context.args[0].upper()
        stock = yf.Ticker(simbolo)
        info = stock.info
        
        precio = info.get('currentPrice')
        nombre = info.get('longName', simbolo)
        cambio = info.get('regularMarketChange')
        volumen = info.get('volume')
        
        if not precio:
            await update.message.reply_text(f"❌ No encontré {simbolo}")
            return
        
        emoji = "📈" if cambio and cambio >= 0 else "📉"
        
        msg = f"""
{emoji} *{nombre}*
━━━━━━━━━━━━━
💵 Precio: ${precio:.2f}
📊 Cambio: {cambio:+.2f}
🔄 Volumen: {volumen:,}
        """
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error en yf: {str(e)}")

# ============================================================================
# 4. CONVERTIR MONEDAS
# ============================================================================

async def convertir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /convertir 100 USD EUR"""
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "Uso: `/convertir [cant] [de] [a]`\n"
                "Ejemplo: `/convertir 100 USD EUR`"
            )
            return
        
        cantidad = float(context.args[0])
        de = context.args[1].upper()
        a = context.args[2].upper()
        
        # Intentar con Yahoo Finance
        par = f"{de}{a}=X"
        stock = yf.Ticker(par)
        tasa = stock.info.get('currentPrice')
        
        if tasa:
            resultado = cantidad * tasa
            msg = f"""
💱 *Conversión*
━━━━━━━━━━━━━
{cantidad:,.2f} {de} = {resultado:,.2f} {a}
Tasa: 1 {de} = {tasa:,.4f} {a}
            """
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ No puedo convertir {de} a {a}")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# 5. COMPARAR ACTIVOS
# ============================================================================

async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /comparar AAPL GOOGL"""
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Uso: `/comparar [sim1] [sim2]`\n"
                "Ejemplo: `/comparar AAPL GOOGL`"
            )
            return
        
        sim1 = context.args[0].upper()
        sim2 = context.args[1].upper()
        
        stock1 = yf.Ticker(sim1)
        stock2 = yf.Ticker(sim2)
        
        info1 = stock1.info
        info2 = stock2.info
        
        precio1 = info1.get('currentPrice', 0)
        precio2 = info2.get('currentPrice', 0)
        nombre1 = info1.get('longName', sim1)
        nombre2 = info2.get('longName', sim2)
        cambio1 = info1.get('regularMarketChange', 0)
        cambio2 = info2.get('regularMarketChange', 0)
        
        emoji1 = "📈" if cambio1 >= 0 else "📉"
        emoji2 = "📈" if cambio2 >= 0 else "📉"
        
        msg = f"""
⚖️ *Comparación*
━━━━━━━━━━━━━━━
{emoji1} {nombre1}
💵 ${precio1:.2f}
📊 {cambio1:+.2f}

{emoji2} {nombre2}
💵 ${precio2:.2f}
📊 {cambio2:+.2f}
        """
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# 6. ANÁLISIS FUNDAMENTAL Y TÉCNICO (SIMPLIFICADO)
# ============================================================================

async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando: /analizar AAPL"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Uso: `/analizar [símbolo]`\n"
                "Ejemplo: `/analizar AAPL`"
            )
            return
        
        simbolo = context.args[0].upper()
        
        # Obtener datos
        stock = yf.Ticker(simbolo)
        info = stock.info
        
        # Validar que tenemos datos
        if not info or 'currentPrice' not in info:
            await update.message.reply_text(f"❌ No puedo obtener datos de {simbolo}")
            return
        
        # DATOS FUNDAMENTALES
        nombre = info.get('longName', simbolo)
        precio = info.get('currentPrice', 0)
        market_cap = info.get('marketCap', 0)
        sector = info.get('sector', 'N/A')
        
        pe = info.get('trailingPE', 'N/A')
        forward_pe = info.get('forwardPE', 'N/A')
        eps = info.get('trailingEps', 'N/A')
        roe = info.get('returnOnEquity', 'N/A')
        roa = info.get('returnOnAssets', 'N/A')
        debt_equity = info.get('debtToEquity', 'N/A')
        dividend = info.get('dividendYield', 'N/A')
        revenue_growth = info.get('revenueGrowth', 'N/A')
        
        # MENSAJE 1: RESUMEN
        msg1 = f"""
╔══════════════════════════════╗
║    📊 ANÁLISIS: {simbolo}
╚══════════════════════════════╝

**Empresa:** {nombre}
**Sector:** {sector}

💰 Precio: ${precio:.2f}
📈 Market Cap: ${market_cap/1e9:.2f}B

*Obteniendo análisis fundamental...*
        """
        
        await update.message.reply_text(msg1, parse_mode='Markdown')
        
        # INTERPRETACIONES
        if pe != 'N/A' and pe > 0:
            pe_estado = "🔴 Valuación ALTA" if pe > 30 else "🟡 Valuación NORMAL" if pe > 15 else "🟢 Valuación BAJA"
        else:
            pe_estado = "⚪ No disponible"
        
        if roe != 'N/A':
            roe_estado = "🟢 EXCELENTE (>15%)" if roe > 0.15 else "🟡 BUENO (10-15%)" if roe > 0.10 else "🔴 BAJO"
        else:
            roe_estado = "⚪ No disponible"
        
        if debt_equity != 'N/A' and debt_equity > 0:
            deuda_estado = "🟢 Bajo riesgo" if debt_equity < 0.5 else "🟡 Riesgo moderado" if debt_equity < 1.5 else "🔴 Alto riesgo"
        else:
            deuda_estado = "⚪ No disponible"
        
        # MENSAJE 2: ANÁLISIS FUNDAMENTAL
        msg2 = f"""
╔══════════════════════════════╗
║    📊 ANÁLISIS FUNDAMENTAL
╚══════════════════════════════╝

**P/E Ratio (Valuación):** {pe if pe != 'N/A' else 'N/A'}
{pe_estado}
_Relación precio/ganancias_

**Forward P/E:** {forward_pe if forward_pe != 'N/A' else 'N/A'}
_P/E esperado próximo año_

**EPS:** ${eps if eps != 'N/A' else 'N/A'}
_Ganancia por acción_

**ROE (Rentabilidad):** {f'{roe*100:.1f}%' if roe != 'N/A' else 'N/A'}
{roe_estado}
_Retorno sobre patrimonio_

**ROA:** {f'{roa*100:.1f}%' if roa != 'N/A' else 'N/A'}
_Eficiencia con activos_

**Deuda/Patrimonio:** {debt_equity if debt_equity != 'N/A' else 'N/A'}
{deuda_estado}
_Nivel de endeudamiento_

**Dividend Yield:** {f'{dividend*100:.2f}%' if dividend != 'N/A' else 'N/A'}
_Rendimiento por dividendos_

**Revenue Growth:** {f'{revenue_growth*100:.1f}%' if revenue_growth != 'N/A' else 'N/A'}
_Crecimiento de ingresos_

*Análisis fundamental completado...*
        """
        
        await update.message.reply_text(msg2, parse_mode='Markdown')
        
        # MENSAJE 3: ANÁLISIS TÉCNICO (SIMPLIFICADO)
        try:
            hist = stock.history(period="1y")
            
            if not hist.empty:
                # Datos técnicos simples
                precio_actual = hist['Close'].iloc[-1]
                precio_52_alto = hist['Close'].max()
                precio_52_bajo = hist['Close'].min()
                precio_200_dias = hist['Close'].iloc[-200] if len(hist) >= 200 else hist['Close'].iloc[0]
                
                # Tendencia
                if precio_actual > precio_200_dias:
                    tendencia = "🟢 ALCISTA"
                else:
                    tendencia = "🔴 BAJISTA"
                
                # Posición en rango
                rango = precio_52_alto - precio_52_bajo
                posicion = ((precio_actual - precio_52_bajo) / rango * 100) if rango > 0 else 50
                
                # Volatilidad
                cambios = hist['Close'].pct_change()
                volatilidad = cambios.std() * 100
                
                vol_estado = "🔴 ALTA" if volatilidad > 4 else "🟡 NORMAL" if volatilidad > 1 else "🟢 BAJA"
                
                msg3 = f"""
╔══════════════════════════════╗
║    📈 ANÁLISIS TÉCNICO
╚══════════════════════════════╝

**Tendencia General:** {tendencia}
_Precio vs promedio 200 días_

**Rango 52 Semanas:**
├ Máximo: ${precio_52_alto:.2f}
├ Mínimo: ${precio_52_bajo:.2f}
└ Posición: {posicion:.1f}%

**Precio Actual:** ${precio_actual:.2f}
_En la parte {'alta' if posicion > 70 else 'baja' if posicion < 30 else 'media'} del rango_

**Volatilidad:** {volatilidad:.2f}%
{vol_estado}
_Fluctuación de precios_

╔══════════════════════════════╗
║    🎯 CONCLUSIÓN
╚══════════════════════════════╝

**Resumen del Análisis:**

La empresa {nombre} muestra {'señales alcistas' if precio_actual > precio_200_dias else 'señales bajistas'} en el análisis técnico. 

En fundamental, tiene {'buena rentabilidad' if roe != 'N/A' and roe > 0.15 else 'rentabilidad moderada'}. La {'valuación es atractiva' if pe != 'N/A' and pe < 15 else 'valuación es normal' if pe != 'N/A' and pe < 25 else 'valuación es elevada'}.

⚖️ **Descargo:** Este análisis es solo educativo. No es recomendación de compra/venta. Consulta un asesor financiero.

*Análisis completado ✓*
                """
                
                await update.message.reply_text(msg3, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error en análisis técnico: {str(e)}")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error general: {str(e)}")

# ============================================================================
# MENÚ PRINCIPAL
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú"""
    nombre = update.effective_user.first_name
    
    msg = f"""
👋 *¡Hola {nombre}!*

Soy tu bot financiero 📊

*💰 Comandos:*

`/crypto [nombre]` - Criptos
`/stock [símbolo]` - Acciones (Alpha Vantage)
`/yf [símbolo]` - Cualquier activo
`/convertir [cant] [de] [a]` - Monedas
`/comparar [sim1] [sim2]` - Comparar
`/analizar [símbolo]` - Análisis completo ⭐
`/ayuda` - Más información

_Datos en tiempo real_
    """
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
*📚 AYUDA*

`/crypto bitcoin` - Precio BTC
`/stock AAPL` - Apple (Alpha Vantage)
`/yf GOOGL` - Google (Yahoo)
`/yf BTC-USD` - Bitcoin
`/yf ^GSPC` - S&P 500
`/convertir 100 USD EUR` - EUR/USD
`/comparar AAPL MSFT` - Comparar
`/analizar TSLA` - Análisis completo

*Todas GRATUITAS ✓*
    """
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def procesar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 No entiendo. Usa `/start`"
    )

# ============================================================================
# MAIN
# ============================================================================

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("crypto", precio_crypto))
    app.add_handler(CommandHandler("stock", precio_stock))
    app.add_handler(CommandHandler("yf", precio_yfinance))
    app.add_handler(CommandHandler("convertir", convertir))
    app.add_handler(CommandHandler("comparar", comparar))
    app.add_handler(CommandHandler("analizar", analizar))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar))
    
    print("✓ Bot iniciado")
    print("✓ Comandos: /crypto /stock /yf /analizar")
    
    app.run_polling()

if __name__ == '__main__':
    main()
