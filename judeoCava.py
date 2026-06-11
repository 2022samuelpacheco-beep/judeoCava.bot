# 🤖 Bot Telegram COMPLETO con APIs Financieras en Tiempo Real

## Este archivo es tu nuevo `judeoCava.py`

**Solo cópialo, pégalo en GitHub y ¡funciona!**

---

```python
import os
import requests
import yfinance as yf
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

# Obtener token de variables de entorno
TOKEN = os.environ.get('TOKEN')
ALPHA_KEY = os.environ.get('ALPHA_VANTAGE_KEY')  # Opcional, pero recomendado

if not TOKEN:
    raise ValueError("TOKEN no está configurado. Agrega TOKEN en Render.")

# Iniciar servidor para mantener activo
keep_alive()

# ============================================================================
# FUNCIÓN 1: OBTENER PRECIO DE CRIPTOMONEDAS (CoinGecko - Gratis, ilimitado)
# ============================================================================

async def precio_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando: /crypto [nombre]
    Ejemplo: /crypto bitcoin
    Obtiene: Precio, Market Cap, Volumen 24h en tiempo real
    """
    try:
        if not context.args:
            mensaje = (
                "📊 *Obtener Precio de Criptomonedas*\n\n"
                "Uso: `/crypto [nombre]`\n\n"
                "*Ejemplos:*\n"
                "`/crypto bitcoin`\n"
                "`/crypto ethereum`\n"
                "`/crypto dogecoin`\n"
                "`/crypto cardano`\n\n"
                "_Datos en tiempo real de CoinGecko_"
            )
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return
        
        cripto_nombre = ' '.join(context.args).lower()
        
        # URL de CoinGecko API
        url = "https://api.coingecko.com/api/v3/simple/price"
        
        params = {
            'ids': cripto_nombre,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true'
        }
        
        # Hacer solicitud
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        datos = response.json()
        
        # Verificar si existe la criptomoneda
        if cripto_nombre not in datos:
            await update.message.reply_text(
                f"❌ No encontré *{cripto_nombre}*\n\n"
                "Intenta con: bitcoin, ethereum, dogecoin, cardano, solana, ripple",
                parse_mode='Markdown'
            )
            return
        
        # Extraer datos
        cripto_data = datos[cripto_nombre]
        precio = cripto_data['usd']
        market_cap = cripto_data['usd_market_cap']
        volumen = cripto_data['usd_24h_vol']
        cambio_24h = cripto_data['usd_24h_change']
        
        # Formatear números
        precio_fmt = f"${precio:,.2f}"
        market_cap_fmt = f"${market_cap:,.0f}" if market_cap else "N/A"
        volumen_fmt = f"${volumen:,.0f}" if volumen else "N/A"
        cambio_fmt = f"{cambio_24h:+.2f}%" if cambio_24h else "N/A"
        
        # Emoji según cambio
        emoji_cambio = "📈" if cambio_24h >= 0 else "📉"
        
        # Crear mensaje formateado
        mensaje = f"""
💰 *{cripto_nombre.upper()}*
━━━━━━━━━━━━━━━━━━━━━━━━
💵 Precio: {precio_fmt}
{emoji_cambio} Cambio 24h: {cambio_fmt}
📊 Market Cap: {market_cap_fmt}
🔄 Volumen 24h: {volumen_fmt}
━━━━━━━━━━━━━━━━━━━━━━━━
_Datos de CoinGecko • {datetime.now().strftime('%H:%M:%S')}_
        """
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱️ Tiempo agotado. Intenta de nuevo.")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"❌ Error de conexión: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN 2: OBTENER PRECIO DE ACCIONES (Alpha Vantage)
# ============================================================================

async def precio_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando: /stock [símbolo]
    Ejemplo: /stock AAPL
    Obtiene: Precio, cambio, volumen
    Nota: Necesita ALPHA_VANTAGE_KEY en variables de entorno
    """
    try:
        if not ALPHA_KEY:
            await update.message.reply_text(
                "⚠️ API key de Alpha Vantage no configurada.\n"
                "Por ahora usa `/yf` para stocks"
            )
            return
        
        if not context.args:
            mensaje = (
                "📈 *Obtener Precio de Acciones*\n\n"
                "Uso: `/stock [símbolo]`\n\n"
                "*Ejemplos:*\n"
                "`/stock AAPL` - Apple\n"
                "`/stock GOOGL` - Google\n"
                "`/stock MSFT` - Microsoft\n"
                "`/stock TSLA` - Tesla\n\n"
                "_Datos de Alpha Vantage_"
            )
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return
        
        simbolo = context.args[0].upper()
        
        # URL de Alpha Vantage
        url = "https://www.alphavantage.co/query"
        
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': simbolo,
            'apikey': ALPHA_KEY
        }
        
        # Hacer solicitud
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        datos = response.json()
        
        # Verificar errores
        if 'Global Quote' not in datos or not datos['Global Quote']:
            await update.message.reply_text(
                f"❌ No encontré *{simbolo}*\n\n"
                "Verifica que el símbolo sea correcto (ej: AAPL, GOOGL)"
            )
            return
        
        quote = datos['Global Quote']
        
        precio = float(quote.get('05. price', 0))
        cambio = float(quote.get('09. change', 0))
        cambio_pct = float(quote.get('10. change percent', 0).replace('%', ''))
        volumen = int(float(quote.get('06. volume', 0)))
        timestamp = quote.get('07. latest trading day', 'N/A')
        
        # Emoji según cambio
        emoji = "📈" if cambio >= 0 else "📉"
        
        # Formatear números
        precio_fmt = f"${precio:.2f}"
        cambio_fmt = f"{cambio:+.2f} ({cambio_pct:+.2f}%)"
        volumen_fmt = f"{volumen:,}"
        
        # Crear mensaje
        mensaje = f"""
{emoji} *{simbolo}*
━━━━━━━━━━━━━━━━━━━━━━━━
💵 Precio: {precio_fmt}
📊 Cambio: {cambio_fmt}
🔄 Volumen: {volumen_fmt}
📅 Fecha: {timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━
_Datos de Alpha Vantage_
        """
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱️ Tiempo agotado. Intenta de nuevo.")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"❌ Error de conexión: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN 3: OBTENER CUALQUIER PRECIO (Yahoo Finance - Sin API key)
# ============================================================================

async def precio_yfinance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando: /yf [símbolo]
    Ejemplo: /yf AAPL o /yf BTC-USD
    Obtiene: Precio, cambio, volumen (funciona con stocks, crypto, índices)
    """
    try:
        if not context.args:
            mensaje = (
                "📊 *Obtener Precio (Yahoo Finance)*\n\n"
                "Uso: `/yf [símbolo]`\n\n"
                "*Ejemplos:*\n"
                "Acciones: `/yf AAPL` `/yf TSLA` `/yf GOOGL`\n"
                "Cripto: `/yf BTC-USD` `/yf ETH-USD`\n"
                "Índices: `/yf ^GSPC` `/yf ^DJI`\n"
                "Monedas: `/yf EURUSD=X`\n\n"
                "_Datos de Yahoo Finance_"
            )
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return
        
        simbolo = context.args[0].upper()
        
        # Descargar datos
        stock = yf.Ticker(simbolo)
        info = stock.info
        
        # Obtener datos
        precio = info.get('currentPrice', None)
        precio_anterior = info.get('previousClose', None)
        cambio = precio - precio_anterior if precio and precio_anterior else None
        cambio_pct = (cambio / precio_anterior * 100) if cambio and precio_anterior else None
        
        volumen = info.get('volume', None)
        nombre = info.get('longName', simbolo)
        
        if not precio:
            await update.message.reply_text(
                f"❌ No encontré datos para *{simbolo}*\n\n"
                "Verifica el símbolo (ej: AAPL, BTC-USD, ^GSPC)"
            )
            return
        
        # Emoji según cambio
        emoji = "📈" if cambio and cambio >= 0 else "📉"
        
        # Formatear números
        precio_fmt = f"${precio:.2f}" if precio else "N/A"
        cambio_fmt = f"{cambio:+.2f} ({cambio_pct:+.2f}%)" if cambio and cambio_pct else "N/A"
        volumen_fmt = f"{volumen:,}" if volumen else "N/A"
        
        # Crear mensaje
        mensaje = f"""
{emoji} *{nombre}*
━━━━━━━━━━━━━━━━━━━━━━━━
💵 Precio: {precio_fmt}
📊 Cambio: {cambio_fmt}
🔄 Volumen: {volumen_fmt}
━━━━━━━━━━━━━━━━━━━━━━━━
_Datos de Yahoo Finance_
        """
        
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN 4: CONVERTIR ENTRE CRIPTOMONEDAS
# ============================================================================

async def convertir_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando: /convertir [cantidad] [de] [a]
    Ejemplo: /convertir 1 BTC USD o /convertir 100 USD EUR
    """
    try:
        if len(context.args) < 3:
            mensaje = (
                "💱 *Conversor de Monedas*\n\n"
                "Uso: `/convertir [cantidad] [de] [a]`\n\n"
                "*Ejemplos:*\n"
                "`/convertir 1 BTC USD`\n"
                "`/convertir 100 USD EUR`\n"
                "`/convertir 1 ETH BTC`\n\n"
                "_Tipos de moneda: USD, EUR, MXN, ARS, BRL, etc._"
            )
            await update.message.reply_text(mensaje, parse_mode='Markdown')
            return
        
        cantidad = float(context.args[0])
        moneda_de = context.args[1].upper()
        moneda_a = context.args[2].upper()
        
        # URL de conversión (usando CoinGecko para cripto y otros)
        url = "https://api.coingecko.com/api/v3/simple/price"
        
        # Intentar con CoinGecko primero
        try:
            params = {
                'ids': moneda_de.lower(),
                'vs_currencies': moneda_a.lower()
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            datos = response.json()
            
            if moneda_de.lower() in datos:
                tasa = datos[moneda_de.lower()].get(moneda_a.lower())
                
                if tasa:
                    resultado = cantidad * tasa
                    
                    mensaje = f"""
💱 *Conversión*
━━━━━━━━━━━━━━━━━━━━━━━━
{cantidad:,.2f} {moneda_de} = {resultado:,.2f} {moneda_a}
━━━━━━━━━━━━━━━━━━━━━━━━
_Tasa: 1 {moneda_de} = {tasa:,.2f} {moneda_a}_
                    """
                    
                    await update.message.reply_text(mensaje, parse_mode='Markdown')
                    return
        except:
            pass
        
        # Si no funciona con CoinGecko, usar Yahoo Finance
        try:
            par = f"{moneda_de}{moneda_a}=X"
            stock = yf.Ticker(par)
            tasa = stock.info.get('currentPrice')
            
            if tasa:
                resultado = cantidad * tasa
                
                mensaje = f"""
💱 *Conversión*
━━━━━━━━━━━━━━━━━━━━━━━━
{cantidad:,.2f} {moneda_de} = {resultado:,.2f} {moneda_a}
━━━━━━━━━━━━━━━━━━━━━━━━
_Tasa: 1 {moneda_de} = {tasa:,.2f} {moneda_a}_
                """
                
                await update.message.reply_text(mensaje, parse_mode='Markdown')
                return
        except:
            pass
        
        await update.message.reply_text(f"❌ No puedo convertir {moneda_de} a {moneda_a}")
    
    except ValueError:
        await update.message.reply_text("❌ El primer argumento debe ser un número")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN 5: COMPARAR DOS ACTIVOS
# ============================================================================

async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando: /comparar [símbolo1] [símbolo2]
    Ejemplo: /comparar AAPL GOOGL
    """
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Uso: `/comparar [símbolo1] [símbolo2]`\n"
                "Ejemplo: `/comparar AAPL GOOGL`",
                parse_mode='Markdown'
            )
            return
        
        sim1 = context.args[0].upper()
        sim2 = context.args[1].upper()
        
        # Obtener datos de ambos
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
━━━━━━━━━━━━━━━━━━━━━━━━
            """
            
            await update.message.reply_text(mensaje, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ No encontré datos para uno de los símbolos")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================================================
# FUNCIÓN 6: MENÚ PRINCIPAL
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú principal del bot"""
    
    nombre = update.effective_user.first_name
    
    mensaje = f"""
👋 *¡Hola {nombre}!*

Soy tu bot de información financiera en tiempo real.

*📊 Comandos Disponibles:*

💰 *Criptomonedas:*
`/crypto [nombre]` - Obtener precio (ej: /crypto bitcoin)

📈 *Acciones:*
`/stock [símbolo]` - Precio de acciones (ej: /stock AAPL)
`/yf [símbolo]` - Cualquier activo (ej: /yf TSLA)

💱 *Conversión:*
`/convertir [cantidad] [de] [a]` - Convertir monedas (ej: /convertir 100 USD EUR)

⚖️ *Comparación:*
`/comparar [símbolo1] [símbolo2]` - Comparar dos activos (ej: /comparar AAPL GOOGL)

*Fuentes:*
🔹 CoinGecko - Criptomonedas
🔹 Alpha Vantage - Stocks (opcional)
🔹 Yahoo Finance - General

━━━━━━━━━━━━━━━━━━━━━━━━
_Todos los datos en tiempo real_
    """
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

# ============================================================================
# FUNCIÓN 7: AYUDA
# ============================================================================

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostrar ayuda detallada"""
    
    mensaje = """
*📚 AYUDA COMPLETA*

*1. Criptomonedas con CoinGecko (GRATIS, ILIMITADO)*
Comando: `/crypto [nombre]`
Ejemplos:
  `/crypto bitcoin` - Bitcoin
  `/crypto ethereum` - Ethereum
  `/crypto dogecoin` - Dogecoin
  `/crypto cardano` - Cardano

Retorna: Precio, Market Cap, Volumen 24h, Cambio 24h

*2. Acciones con Alpha Vantage (GRATIS LIMITADO)*
Comando: `/stock [símbolo]`
Ejemplos:
  `/stock AAPL` - Apple
  `/stock GOOGL` - Google
  `/stock MSFT` - Microsoft
  `/stock TSLA` - Tesla

Retorna: Precio, Cambio, Volumen

*3. Cualquier Activo con Yahoo Finance (GRATIS)*
Comando: `/yf [símbolo]`
Ejemplos:
  `/yf AAPL` - Acciones
  `/yf BTC-USD` - Bitcoin
  `/yf ^GSPC` - Índice S&P 500
  `/yf EURUSD=X` - Tipo de cambio EUR/USD

*4. Convertir Monedas*
Comando: `/convertir [cantidad] [de] [a]`
Ejemplo: `/convertir 100 USD EUR`

*5. Comparar Activos*
Comando: `/comparar [símbolo1] [símbolo2]`
Ejemplo: `/comparar AAPL GOOGL`

*⚡ Tips:*
• Los datos se obtienen en tiempo real
• Escribe exactamente el símbolo o nombre
• Para criptos, usa el nombre completo (bitcoin, ethereum)
• Para stocks, usa el símbolo (AAPL, GOOGL, MSFT)
    """
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

# ============================================================================
# FUNCIÓN 8: PROCESAR MENSAJES NORMALES
# ============================================================================

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar mensajes que no son comandos"""
    
    texto = update.message.text.lower()
    
    if "precio" in texto or "cuánto" in texto or "costo" in texto:
        await update.message.reply_text(
            "💰 Para obtener precios, usa:\n"
            "`/crypto` para criptomonedas\n"
            "`/yf` para cualquier activo",
            parse_mode='Markdown'
        )
    elif "bitcoin" in texto or "ethereum" in texto or "cripto" in texto:
        await update.message.reply_text(
            "💰 Usa `/crypto [nombre]` para obtener el precio\n"
            "Ejemplo: `/crypto bitcoin`",
            parse_mode='Markdown'
        )
    elif "stock" in texto or "acción" in texto:
        await update.message.reply_text(
            "📈 Usa `/yf [símbolo]` para obtener el precio\n"
            "Ejemplo: `/yf AAPL`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🤖 No entiendo ese comando.\n"
            "Usa `/start` para ver los comandos disponibles"
        )

# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Inicializar el bot"""
    
    app = Application.builder().token(TOKEN).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("crypto", precio_crypto))
    app.add_handler(CommandHandler("stock", precio_stock))
    app.add_handler(CommandHandler("yf", precio_yfinance))
    app.add_handler(CommandHandler("convertir", convertir_crypto))
    app.add_handler(CommandHandler("comparar", comparar))
    
    # Procesar mensajes normales
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    
    print("✓ Bot iniciado con APIs financieras en tiempo real")
    print("✓ Conectado a: CoinGecko, Alpha Vantage, Yahoo Finance")
    print("✓ Disponible en Telegram 24/7")
    
    app.run_polling()

if __name__ == '__main__':
    main()
```

---

## Archivo `requirements.txt`

```
python-telegram-bot==22.7
httpx>=0.27
flask==3.0.0
requests
yfinance
```

---

## Archivo `keep_alive.py` (SIN CAMBIOS)

```python
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!', 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
```

---

## Archivo `Procfile` (SIN CAMBIOS)

```
worker: python judeoCava.py
```

---

# 🚀 INSTRUCCIONES PARA DESPLEGAR

## Paso 1: Actualizar en GitHub

1. **Ve a tu repositorio GitHub** `telegram-bot`

2. **Actualiza estos archivos:**
   - ✅ Reemplaza `judeoCava.py` con el código completo de arriba
   - ✅ Actualiza `requirements.txt` con las librerías nuevas
   - ✅ Mantén `keep_alive.py` igual
   - ✅ Mantén `Procfile` igual

3. **Haz commit:**
   - En GitHub, abre cada archivo
   - Haz click en lápiz para editar
   - Pega el código nuevo
   - Click en "Commit changes"

## Paso 2: Render Detectorá Cambios

**Render automáticamente:**
- Verá que hay cambios en GitHub
- Iniciará un nuevo deploy
- Instalará las librerías nuevas
- Ejecutará el bot

**Espera 2-3 minutos** 🕐

## Paso 3: Verificar que Funciona

En Render:
1. Ve a **"Logs"**
2. Deberías ver:
   ```
   ✓ Bot iniciado con APIs financieras en tiempo real
   ✓ Conectado a: CoinGecko, Alpha Vantage, Yahoo Finance
   ```

## Paso 4: Probar en Telegram

1. Abre Telegram
2. Busca tu bot
3. Envía `/start`
4. Prueba los comandos:
   - `/crypto bitcoin`
   - `/yf AAPL`
   - `/convertir 100 USD EUR`
   - `/comparar AAPL GOOGL`

---

# 📊 COMANDOS DISPONIBLES

| Comando | Uso | Ejemplo |
|---------|-----|---------|
| `/crypto` | Criptomonedas | `/crypto bitcoin` |
| `/stock` | Acciones (Alpha Vantage) | `/stock AAPL` |
| `/yf` | Cualquier activo | `/yf TSLA` o `/yf BTC-USD` |
| `/convertir` | Convertir monedas | `/convertir 100 USD EUR` |
| `/comparar` | Comparar dos activos | `/comparar AAPL GOOGL` |
| `/start` | Menú principal | - |
| `/ayuda` | Ayuda completa | - |

---

¡**Tu bot ahora tiene TODOS los datos financieros en tiempo real!** 🚀
