import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import Database
from apis import FMP
from analytics import TechnicalAnalysis, FundamentalAnalysis, ScoringSystem
from keep_alive import keep_alive

TOKEN = os.getenv("TOKEN")
FMP_KEY = os.getenv("FMP_KEY")

if not TOKEN or not FMP_KEY:
    raise ValueError("TOKEN o FMP_KEY no configurados")

keep_alive()

# ============================================================================
# COMANDOS DEL BOT
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Menú principal"""
    
    nombre = update.effective_user.first_name
    
    mensaje = f"""
👋 *¡Hola {nombre}!*

Soy tu asistente financiero profesional 📊

*💰 Comandos Disponibles:*

`/analizar [SÍMBOLO]` - Análisis completo (ej: /analizar AAPL)
`/comparar [SIM1] [SIM2]` - Comparar dos activos
`/watchlist` - Ver tu lista de vigilancia
`/cartera` - Ver tu cartera
`/noticias [SÍMBOLO]` - Últimas noticias

*📈 Activos que analizo:*
• Acciones: AAPL, MSFT, INTC, TSLA, etc
• ETFs: VOO, QQQ, SCHD, ACWI, IVV, ZTS

_Análisis con FMP, Finnhub y cálculos locales_
    """
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')

async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /analizar [SÍMBOLO] - Análisis completo"""
    
    try:
        if not context.args:
            await update.message.reply_text(
                "Uso: `/analizar [SÍMBOLO]`\n"
                "Ejemplo: `/analizar AAPL`",
                parse_mode='Markdown'
            )
            return
        
        simbolo = context.args[0].upper()
        
        # Mostrar que está procesando
        mensaje_espera = await update.message.reply_text(
            f"🔍 Analizando {simbolo}...\n_Obteniendo datos de FMP..._"
        )
        
        # Obtener datos de FMP
        quote = await FMP.get_quote(simbolo)
        if not quote:
            await mensaje_espera.edit_text(f"❌ No encontré datos para {simbolo}")
            return
        
        profile = await FMP.get_company_profile(simbolo)
        metrics = await FMP.get_key_metrics(simbolo)
        historical = await FMP.get_historical_prices(simbolo, days=365)
        
        if not historical:
            await mensaje_espera.edit_text(f"⚠️ No hay histórico disponible para {simbolo}")
            return
        
        # Análisis técnico
        technical = TechnicalAnalysis.analyze_technicals(historical["historical"])
        
        # Análisis fundamental
        fundamental = FundamentalAnalysis.analyze_fundamentals(metrics or {}, quote)
        
        # Sistema de puntuación
        score_data = ScoringSystem.calculate_score(technical or {}, fundamental or {})
        
        # ============ MENSAJE 1: RESUMEN ============
        precio = quote.get("price", "N/A")
        cambio = quote.get("changePercent", 0)
        emoji = "📈" if cambio >= 0 else "📉"
        nombre_empresa = profile.get("name", simbolo) if profile else simbolo
        sector = profile.get("sector", "N/A") if profile else "N/A"
        market_cap = profile.get("marketCap", "N/A") if profile else "N/A"
        
        msg1 = f"""
╔════════════════════════════════╗
║    📊 ANÁLISIS: {simbolo}
╚════════════════════════════════╝

**Empresa:** {nombre_empresa}
**Sector:** {sector}

💰 Precio: ${precio:.2f}
{emoji} Cambio: {cambio:+.2f}%
📊 Market Cap: ${market_cap:,.0f}

_(1/3) Analizando fundamental..._
        """
        
        await mensaje_espera.edit_text(msg1, parse_mode='Markdown')
        
        # ============ MENSAJE 2: ANÁLISIS FUNDAMENTAL ============
        pe = fundamental.get("pe_ratio", "N/A")
        roe = fundamental.get("roe", "N/A")
        dividend = fundamental.get("dividend_yield", "N/A")
        revenue_growth = fundamental.get("revenue_growth", "N/A")
        debt_to_eq = fundamental.get("debt_to_equity", "N/A")
        net_margin = fundamental.get("net_margin", "N/A")
        
        # Interpretaciones
        pe_estado = "🔴 Alto (>30)" if (pe != "N/A" and pe > 30) else "🟡 Normal (15-30)" if (pe != "N/A" and pe >= 15) else "🟢 Bajo (<15)" if pe != "N/A" else "⚪ N/A"
        roe_estado = "🟢 Excelente (>15%)" if (roe != "N/A" and roe > 0.15) else "🟡 Bueno (10-15%)" if (roe != "N/A" and roe > 0.10) else "🔴 Bajo (<10%)" if roe != "N/A" else "⚪ N/A"
        
        msg2 = f"""
╔════════════════════════════════╗
║    📊 ANÁLISIS FUNDAMENTAL
╚════════════════════════════════╝

**P/E Ratio:** {pe if pe != "N/A" else "N/A"}
{pe_estado}
_Valuación de la empresa_

**ROE:** {f'{roe*100:.1f}%' if roe != "N/A" else "N/A"}
{roe_estado}
_Rentabilidad sobre patrimonio_

**Dividend Yield:** {f'{dividend*100:.2f}%' if dividend != "N/A" else "N/A"}
_Rendimiento por dividendos_

**Revenue Growth:** {f'{revenue_growth*100:.1f}%' if revenue_growth != "N/A" else "N/A"}
_Crecimiento de ingresos_

**Debt/Equity:** {debt_to_eq if debt_to_eq != "N/A" else "N/A"}
_Nivel de endeudamiento_

**Net Margin:** {f'{net_margin*100:.1f}%' if net_margin != "N/A" else "N/A"}
_Margen neto_

_(2/3) Analizando técnico..._
        """
        
        await update.message.reply_text(msg2, parse_mode='Markdown')
        
        # ============ MENSAJE 3: ANÁLISIS TÉCNICO + SCORE ============
        current_price = technical.get("current_price", "N/A") if technical else "N/A"
        sma50 = technical.get("sma50", "N/A") if technical else "N/A"
        sma200 = technical.get("sma200", "N/A") if technical else "N/A"
        rsi = technical.get("rsi", "N/A") if technical else "N/A"
        trend = technical.get("trend", "NEUTRAL") if technical else "NEUTRAL"
        
        rsi_estado = "🔴 SOBRECOMPRA (>70)" if (rsi != "N/A" and rsi > 70) else "🟢 Normal (30-70)" if (rsi != "N/A" and rsi >= 30) else "🔴 SOBREVENTA (<30)" if rsi != "N/A" else "⚪ N/A"
        trend_emoji = "🟢" if trend == "ALCISTA" else "🔴"
        
        score = score_data.get("total_score", 0)
        score_color = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
        details = "\n".join(score_data.get("details", []))
        
        msg3 = f"""
╔════════════════════════════════╗
║    📈 ANÁLISIS TÉCNICO
╚════════════════════════════════╝

**Precio Actual:** ${current_price if current_price != "N/A" else "N/A"}

**SMA 50:** ${sma50 if sma50 != "N/A" else "N/A"}
**SMA 200:** ${sma200 if sma200 != "N/A" else "N/A"}

**RSI (14):** {rsi if rsi != "N/A" else "N/A"}
{rsi_estado}
_Momentum del precio_

**Tendencia:** {trend_emoji} {trend}
_Relación SMA50 vs SMA200_

╔════════════════════════════════╗
║    🎯 PUNTUACIÓN FINAL
╚════════════════════════════════╝

**Score:** {score_color} {score}/100

**Factores:**
{details}

**Conclusión:**
{nombre_empresa} muestra señales {'alcistas' if trend == 'ALCISTA' else 'bajistas'} técnicas.
Fundamentalmente, tiene {'valuación atractiva' if pe != 'N/A' and pe < 20 else 'valuación normal' if pe != 'N/A' else 'data incompleta'}.

⚖️ _Este análisis es educativo. No constituye asesoramiento financiero._

_(3/3) Análisis completado ✓_
        """
        
        await update.message.reply_text(msg3, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /comparar - Comparar dos activos"""
    
    try:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Uso: `/comparar [SIM1] [SIM2]`\n"
                "Ejemplo: `/comparar AAPL MSFT`",
                parse_mode='Markdown'
            )
            return
        
        sim1 = context.args[0].upper()
        sim2 = context.args[1].upper()
        
        await update.message.reply_text(f"⏳ Comparando {sim1} vs {sim2}...")
        
        # Obtener datos de ambos
        quote1 = await FMP.get_quote(sim1)
        quote2 = await FMP.get_quote(sim2)
        
        if not quote1 or not quote2:
            await update.message.reply_text("❌ No puedo obtener datos de ambos activos")
            return
        
        precio1 = quote1.get("price", "N/A")
        precio2 = quote2.get("price", "N/A")
        cambio1 = quote1.get("changePercent", 0)
        cambio2 = quote2.get("changePercent", 0)
        
        emoji1 = "📈" if cambio1 >= 0 else "📉"
        emoji2 = "📈" if cambio2 >= 0 else "📉"
        
        msg = f"""
⚖️ *Comparación*
━━━━━━━━━━━━━━━━━━━━━━━━

{emoji1} *{sim1}*
💵 Precio: ${precio1:.2f}
📊 Cambio: {cambio1:+.2f}%

{emoji2} *{sim2}*
💵 Precio: ${precio2:.2f}
📊 Cambio: {cambio2:+.2f}%
        """
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda - Ver ayuda"""
    
    msg = """
*📚 AYUDA*

`/analizar AAPL` - Análisis completo
`/comparar AAPL MSFT` - Comparar activos
`/watchlist` - Tu lista de vigilancia
`/cartera` - Tu cartera
`/noticias AAPL` - Últimas noticias

*Próximas características:*
✓ Alertas automáticas
✓ Comparativas más detalladas
✓ Histórico de análisis
    """
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesar mensajes que no son comandos"""
    
    await update.message.reply_text(
        "🤖 No entiendo ese comando.\n"
        "Usa `/start` para ver los comandos disponibles"
    )

# ============================================================================
# FUNCIÓN MAIN
# ============================================================================

async def main():
    """Inicializar el bot"""
    
    # Inicializar base de datos
    await Database.init()
    
    # Crear aplicación
    app = Application.builder().token(TOKEN).build()
    
    # Registrar comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analizar", analizar))
    app.add_handler(CommandHandler("comparar", comparar))
    app.add_handler(CommandHandler("ayuda", ayuda))
    
    # Procesar mensajes normales
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    
    print("✓ Bot iniciado")
    print("✓ Base de datos SQLite lista")
    print("✓ FMP API configurada")
    print("✓ Disponible 24/7 en Render")
    
    # Iniciar bot
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
