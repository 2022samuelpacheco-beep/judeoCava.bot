import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import Database
from apis import Yahoo, CoinGecko, is_crypto
from analytics import TechnicalAnalysis, FundamentalAnalysis, ScoringSystem
from keep_alive import keep_alive

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN no configurado en variables de entorno")

# ============================================================================
# UTILIDADES DE FORMATO
# ============================================================================

def fmt_price(val, decimals=2):
    if val is None:
        return "N/A"
    try:
        return f"${float(val):,.{decimals}f}"
    except:
        return "N/A"

def fmt_pct(val, multiply=False):
    if val is None:
        return "N/A"
    try:
        v = float(val) * 100 if multiply else float(val)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    except:
        return "N/A"

def fmt_num(val, decimals=2):
    if val is None:
        return "N/A"
    try:
        return f"{float(val):,.{decimals}f}"
    except:
        return "N/A"

def fmt_market_cap(val):
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        if v >= 1e9:
            return f"${v/1e9:.2f}B"
        if v >= 1e6:
            return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"
    except:
        return "N/A"

# ============================================================================
# COMANDOS
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name
    msg = (
        f"👋 *Hola {nombre}!*\n\n"
        "Soy tu asistente financiero 📊\n\n"
        "*Comandos:*\n"
        "`/analizar AAPL` - Análisis completo\n"
        "`/precio BTC` - Solo precio\n"
        "`/comparar AAPL MSFT` - Comparar activos\n"
        "`/ayuda` - Ayuda\n\n"
        "*Soporta:*\n"
        "Acciones: AAPL, MSFT, INTC, TSLA...\n"
        "ETFs: VOO, QQQ, SCHD...\n"
        "Cripto: BTC, ETH, SOL, ADA, XRP..."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: `/precio AAPL` o `/precio BTC`", parse_mode='Markdown')
        return

    simbolo = context.args[0].upper()
    msg_espera = await update.message.reply_text(f"Obteniendo precio de {simbolo}...")

    try:
        quote = await CoinGecko.get_quote(simbolo) if is_crypto(simbolo) else await Yahoo.get_quote(simbolo)

        if not quote or not quote.get("price"):
            await msg_espera.edit_text(
                f"No encontre datos para *{simbolo}*\n"
                "Verifica que el simbolo sea correcto.",
                parse_mode='Markdown'
            )
            return

        change = quote.get("changePercent", 0) or 0
        emoji = "📈" if change >= 0 else "📉"

        await msg_espera.edit_text(
            f"{emoji} *{quote.get('name', simbolo)}* (`{simbolo}`)\n\n"
            f"Precio: *{fmt_price(quote['price'])}*\n"
            f"Cambio 24h: *{fmt_pct(change)}*",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Error /precio {simbolo}: {e}")
        await msg_espera.edit_text(f"Error obteniendo precio de {simbolo}")


async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: `/analizar SIMBOLO`\nEjemplos: `/analizar AAPL` o `/analizar BTC`",
            parse_mode='Markdown'
        )
        return

    simbolo = context.args[0].upper()

    # IMPORTANTE: mensaje inicial SIN parse_mode para evitar errores de formato
    msg_espera = await update.message.reply_text(
        f"Analizando {simbolo}... por favor espera"
    )

    try:
        # ── Obtener datos ────────────────────────────────────────────────────
        if is_crypto(simbolo):
            quote = await CoinGecko.get_quote(simbolo)
            historical_data = await CoinGecko.get_historical_prices(simbolo)
            profile = None
            metrics = None
        else:
            quote = await Yahoo.get_quote(simbolo)
            historical_data = await Yahoo.get_historical_prices(simbolo)
            profile = await Yahoo.get_company_profile(simbolo)
            metrics = await Yahoo.get_key_metrics(simbolo)

        # ── Validar quote ────────────────────────────────────────────────────
        if not quote or not quote.get("price"):
            await msg_espera.edit_text(
                f"No encontre datos para {simbolo}\n\n"
                "Posibles causas:\n"
                "- Simbolo incorrecto\n"
                "- Para cripto usa: BTC, ETH, SOL, ADA...\n"
                "- Para acciones usa el ticker exacto: AAPL, MSFT..."
            )
            return

        # ── Análisis técnico ─────────────────────────────────────────────────
        technical = None
        hist_count = 0
        if historical_data and historical_data.get("historical"):
            hist = historical_data["historical"]
            hist_count = len(hist)
            if hist_count >= 50:
                technical = TechnicalAnalysis.analyze_technicals(hist)

        # ── Fundamental y score ───────────────────────────────────────────────
        fundamental = FundamentalAnalysis.analyze_fundamentals(metrics or {}, quote)
        score_data = ScoringSystem.calculate_score(technical or {}, fundamental or {})

        # ── Datos comunes ─────────────────────────────────────────────────────
        price  = quote.get("price")
        change = quote.get("changePercent", 0) or 0
        name   = quote.get("name") or (profile.get("name") if profile else simbolo) or simbolo
        sector = (profile.get("sector") if profile else None) or "N/A"
        mktcap = quote.get("marketCap") or (profile.get("marketCap") if profile else None)
        emoji  = "📈" if change >= 0 else "📉"

        # ════════════════════════════════════════
        # MSG 1 — Precio
        # ════════════════════════════════════════
        sector_line = f"Sector: {sector}\n" if sector != "N/A" else ""
        msg1 = (
            f"ANALISIS: {simbolo}\n"
            f"{'='*24}\n\n"
            f"*{name}*\n"
            f"{sector_line}"
            f"\n"
            f"Precio: *{fmt_price(price)}*\n"
            f"{emoji} Cambio: *{fmt_pct(change)}*\n"
            f"Market Cap: *{fmt_market_cap(mktcap)}*\n\n"
            f"_1 de 3 - calculando fundamental..._"
        )
        await msg_espera.edit_text(msg1, parse_mode='Markdown')

        # ════════════════════════════════════════
        # MSG 2 — Fundamental
        # ════════════════════════════════════════
        if not is_crypto(simbolo) and fundamental:
            pe  = fundamental.get("pe_ratio")
            roe = fundamental.get("roe")
            div = fundamental.get("dividend_yield")
            rev = fundamental.get("revenue_growth")
            d2e = fundamental.get("debt_to_equity")
            nm  = fundamental.get("net_margin")

            pe_ico  = "🔴" if pe and pe > 30 else "🟡" if pe and pe >= 15 else "🟢" if pe else "⚪"
            roe_ico = "🟢" if roe and roe > 0.15 else "🟡" if roe and roe > 0.10 else "🔴" if roe else "⚪"

            msg2 = (
                f"FUNDAMENTAL: {simbolo}\n"
                f"{'='*24}\n\n"
                f"{pe_ico} P/E Ratio: *{fmt_num(pe, 1)}*\n"
                f"{roe_ico} ROE: *{fmt_pct(roe, multiply=True)}*\n"
                f"Dividend Yield: *{fmt_pct(div, multiply=True)}*\n"
                f"Revenue Growth: *{fmt_pct(rev, multiply=True)}*\n"
                f"Debt/Equity: *{fmt_num(d2e)}*\n"
                f"Net Margin: *{fmt_pct(nm, multiply=True)}*\n\n"
                f"_2 de 3 - calculando tecnico..._"
            )
        else:
            msg2 = (
                f"FUNDAMENTAL: {simbolo}\n"
                f"{'='*24}\n\n"
                f"⚪ _No disponible para cripto_\n\n"
                f"_2 de 3 - calculando tecnico..._"
            )

        await update.message.reply_text(msg2, parse_mode='Markdown')

        # ════════════════════════════════════════
        # MSG 3 — Técnico + Score
        # ════════════════════════════════════════
        if technical:
            cp     = technical.get("current_price")
            sma50  = technical.get("sma50")
            sma200 = technical.get("sma200")
            rsi    = technical.get("rsi")
            trend  = technical.get("trend", "NEUTRAL")

            rsi_v = float(rsi) if rsi else None
            if rsi_v and rsi_v > 70:
                rsi_ico = "🔴 SOBRECOMPRA (>70)"
            elif rsi_v and rsi_v < 30:
                rsi_ico = "🔴 SOBREVENTA (<30)"
            elif rsi_v:
                rsi_ico = "🟢 Normal (30-70)"
            else:
                rsi_ico = "⚪ N/A"

            trend_ico = "🟢" if trend == "ALCISTA" else "🔴"

            tech_txt = (
                f"Precio actual: *{fmt_price(cp)}*\n"
                f"SMA 50: *{fmt_price(sma50)}*\n"
                f"SMA 200: *{fmt_price(sma200)}*\n\n"
                f"RSI (14): *{fmt_num(rsi, 1)}*\n"
                f"{rsi_ico}\n\n"
                f"Tendencia: {trend_ico} *{trend}*\n"
            )
        else:
            if hist_count > 0:
                histmsg = f"solo {hist_count} registros, se necesitan 200+"
            else:
                histmsg = "sin historial disponible"
            tech_txt = f"⚪ _Tecnico no disponible ({histmsg})_\n"

        score   = score_data.get("total_score", 0)
        s_ico   = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
        details = "\n".join(score_data.get("details", [])) or "_Sin datos suficientes_"

        if technical and technical.get("trend") == "ALCISTA":
            conclusion = "alcistas"
        elif technical and technical.get("trend") == "BAJISTA":
            conclusion = "bajistas"
        else:
            conclusion = "mixtas"

        msg3 = (
            f"TECNICO + SCORE: {simbolo}\n"
            f"{'='*24}\n\n"
            f"{tech_txt}\n"
            f"PUNTUACION FINAL\n"
            f"{'='*24}\n\n"
            f"Score: {s_ico} *{score}/100*\n\n"
            f"Factores:\n{details}\n\n"
            f"*{name}* muestra señales {conclusion}.\n\n"
            f"_Analisis educativo. No es asesoramiento financiero._\n\n"
            f"_3 de 3 - Completado_"
        )

        await update.message.reply_text(msg3, parse_mode='Markdown')

    except Exception as e:
        print(f"Error en /analizar {simbolo}: {e}")
        import traceback
        traceback.print_exc()
        await msg_espera.edit_text(f"Error analizando {simbolo}: {str(e)[:150]}")


async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: `/comparar S1 S2`\nEjemplo: `/comparar AAPL MSFT`",
            parse_mode='Markdown'
        )
        return

    sim1, sim2 = context.args[0].upper(), context.args[1].upper()
    msg_espera = await update.message.reply_text(f"Comparando {sim1} vs {sim2}...")

    try:
        q1 = await (CoinGecko.get_quote(sim1) if is_crypto(sim1) else Yahoo.get_quote(sim1))
        q2 = await (CoinGecko.get_quote(sim2) if is_crypto(sim2) else Yahoo.get_quote(sim2))

        if not q1 or not q1.get("price"):
            await msg_espera.edit_text(f"No encontre datos para {sim1}")
            return
        if not q2 or not q2.get("price"):
            await msg_espera.edit_text(f"No encontre datos para {sim2}")
            return

        c1 = q1.get("changePercent", 0) or 0
        c2 = q2.get("changePercent", 0) or 0
        e1 = "📈" if c1 >= 0 else "📉"
        e2 = "📈" if c2 >= 0 else "📉"
        ganador = sim1 if c1 > c2 else (sim2 if c2 > c1 else None)
        winner  = f"\n🏆 *Mejor hoy: {ganador}*" if ganador else "\n🤝 *Rendimiento similar*"

        msg = (
            f"COMPARACION: {sim1} vs {sim2}\n"
            f"{'='*24}\n\n"
            f"{e1} *{q1.get('name', sim1)}*\n"
            f"Precio: *{fmt_price(q1['price'])}*\n"
            f"Cambio: *{fmt_pct(c1)}*\n"
            f"Cap: {fmt_market_cap(q1.get('marketCap'))}\n\n"
            f"{e2} *{q2.get('name', sim2)}*\n"
            f"Precio: *{fmt_price(q2['price'])}*\n"
            f"Cambio: *{fmt_pct(c2)}*\n"
            f"Cap: {fmt_market_cap(q2.get('marketCap'))}"
            f"{winner}"
        )
        await msg_espera.edit_text(msg, parse_mode='Markdown')

    except Exception as e:
        print(f"Error /comparar: {e}")
        await msg_espera.edit_text(f"Error comparando {sim1} vs {sim2}")


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "*AYUDA*\n\n"
        "`/analizar AAPL` - Analisis completo\n"
        "`/precio BTC` - Solo precio actual\n"
        "`/comparar AAPL MSFT` - Comparar dos activos\n\n"
        "*Cripto soportada:*\n"
        "BTC, ETH, BNB, SOL, ADA, XRP, DOGE,\n"
        "DOT, AVAX, MATIC, LTC, LINK, UNI, ATOM\n\n"
        "*Proximas mejoras:*\n"
        "Alertas de precio\n"
        "Watchlist personal"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if len(text) <= 6 and text.isalpha():
        await update.message.reply_text(
            f"Para analizar *{text}* usa:\n`/analizar {text}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "Comando no reconocido. Usa `/ayuda` para ver los comandos.",
            parse_mode='Markdown'
        )

# ============================================================================
# MAIN
# ============================================================================

def main():
    keep_alive()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("analizar", analizar))
    application.add_handler(CommandHandler("comparar", comparar))
    application.add_handler(CommandHandler("precio", precio))
    application.add_handler(CommandHandler("ayuda", ayuda))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))

    print("Bot iniciado")
    print("Keep-Alive activo para UptimeRobot")
    print("Yahoo Finance + CoinGecko listos")

    asyncio.run(Database.init())
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
