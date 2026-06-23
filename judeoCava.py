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
# UTILIDADES DE FORMATO (evita crashes con None o "N/A")
# ============================================================================

def fmt_price(val, currency="$", decimals=2):
    """Formatear precio de forma segura"""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{currency}{float(val):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"

def fmt_pct(val, multiply=False):
    """Formatear porcentaje de forma segura"""
    if val is None or val == "N/A":
        return "N/A"
    try:
        v = float(val) * 100 if multiply else float(val)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    except (TypeError, ValueError):
        return "N/A"

def fmt_num(val, prefix="", suffix="", decimals=2):
    """Formatear número de forma segura"""
    if val is None or val == "N/A":
        return "N/A"
    try:
        return f"{prefix}{float(val):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"

def fmt_market_cap(val):
    """Formatear market cap en billones/millones"""
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
    except (TypeError, ValueError):
        return "N/A"

# ============================================================================
# COMANDOS DEL BOT
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    nombre = update.effective_user.first_name
    mensaje = (
        f"👋 *¡Hola {nombre}\\!*\n\n"
        "Soy tu asistente financiero 📊\n\n"
        "*Comandos disponibles:*\n\n"
        "`/analizar [SÍMBOLO]` — Análisis completo\n"
        "Ej: `/analizar AAPL` · `/analizar BTC`\n\n"
        "`/comparar [S1] [S2]` — Comparar dos activos\n"
        "Ej: `/comparar AAPL MSFT`\n\n"
        "`/precio [SÍMBOLO]` — Solo precio actual\n\n"
        "`/ayuda` — Ver esta ayuda\n\n"
        "*Activos soportados:*\n"
        "• Acciones: AAPL, MSFT, INTC, TSLA, NVDA…\n"
        "• ETFs: VOO, QQQ, SCHD, ACWI…\n"
        "• Cripto: BTC, ETH, SOL, ADA, XRP…\n\n"
        "_Fuentes: Yahoo Finance \\+ CoinGecko_"
    )
    await update.message.reply_text(mensaje, parse_mode='MarkdownV2')


async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /precio — solo precio actual rápido"""
    if not context.args:
        await update.message.reply_text(
            "Uso: `/precio AAPL` o `/precio BTC`",
            parse_mode='Markdown'
        )
        return

    simbolo = context.args[0].upper()
    msg_espera = await update.message.reply_text(f"⏳ Obteniendo precio de {simbolo}…")

    try:
        if is_crypto(simbolo):
            quote = await CoinGecko.get_quote(simbolo)
        else:
            quote = await Yahoo.get_quote(simbolo)

        if not quote or not quote.get("price"):
            await msg_espera.edit_text(
                f"❌ No encontré datos para `{simbolo}`\\.\n"
                "Verifica que el símbolo sea correcto\\.",
                parse_mode='MarkdownV2'
            )
            return

        price = quote["price"]
        change = quote.get("changePercent", 0) or 0
        name = quote.get("name", simbolo)
        emoji = "📈" if change >= 0 else "📉"
        sign = "+" if change >= 0 else ""

        await msg_espera.edit_text(
            f"{emoji} *{name}* (`{simbolo}`)\n\n"
            f"💰 Precio: *{fmt_price(price)}*\n"
            f"📊 Cambio 24h: *{sign}{change:.2f}%*",
            parse_mode='Markdown'
        )
    except Exception as e:
        await msg_espera.edit_text(f"❌ Error: {str(e)}")


async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /analizar — análisis completo"""
    if not context.args:
        await update.message.reply_text(
            "Uso: `/analizar [SÍMBOLO]`\nEjemplo: `/analizar AAPL` o `/analizar BTC`",
            parse_mode='Markdown'
        )
        return

    simbolo = context.args[0].upper()
    tipo = "cripto" if is_crypto(simbolo) else "stock/ETF"
    msg_espera = await update.message.reply_text(
        f"🔍 Analizando *{simbolo}* \\({tipo}\\)\\.\\.\\.",
        parse_mode='MarkdownV2'
    )

    try:
        # ── Obtener datos según tipo ──────────────────────────────────────────
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

        # ── Validar datos mínimos ─────────────────────────────────────────────
        if not quote or not quote.get("price"):
            await msg_espera.edit_text(
                f"❌ No encontré datos para `{simbolo}`\\.\n\n"
                "_Posibles causas:_\n"
                "• Símbolo incorrecto \\(verifica en Yahoo Finance\\)\n"
                "• Para cripto usa: BTC, ETH, SOL, ADA…\n"
                "• Para acciones usa el ticker exacto: AAPL, MSFT…",
                parse_mode='MarkdownV2'
            )
            return

        # ── Análisis técnico ──────────────────────────────────────────────────
        technical = None
        if historical_data and historical_data.get("historical"):
            hist = historical_data["historical"]
            if len(hist) >= 50:
                technical = TechnicalAnalysis.analyze_technicals(hist)

        # ── Análisis fundamental ──────────────────────────────────────────────
        fundamental = FundamentalAnalysis.analyze_fundamentals(metrics or {}, quote)

        # ── Score ─────────────────────────────────────────────────────────────
        score_data = ScoringSystem.calculate_score(technical or {}, fundamental or {})

        # ── Datos para mostrar ────────────────────────────────────────────────
        price = quote.get("price")
        change = quote.get("changePercent", 0) or 0
        name = quote.get("name") or (profile.get("name") if profile else simbolo) or simbolo
        sector = (profile.get("sector", "N/A") if profile else "N/A") or "N/A"
        market_cap = quote.get("marketCap") or (profile.get("marketCap") if profile else None)
        emoji = "📈" if change >= 0 else "📉"
        sign = "+" if change >= 0 else ""

        # ── MENSAJE 1: Resumen ────────────────────────────────────────────────
        mc_str = fmt_market_cap(market_cap)
        sector_line = f"🏭 Sector: {sector}\n" if sector != "N/A" else ""

        msg1 = (
            f"╔══════════════════════╗\n"
            f"║ 📊 ANÁLISIS: {simbolo}\n"
            f"╚══════════════════════╝\n\n"
            f"🏢 *{name}*\n"
            f"{sector_line}"
            f"\n"
            f"💰 Precio: *{fmt_price(price)}*\n"
            f"{emoji} Cambio: *{sign}{change:.2f}%*\n"
            f"📊 Market Cap: *{mc_str}*\n\n"
            f"_\\(1/3\\) Obteniendo fundamental\\.\\.\\._"
        )
        await msg_espera.edit_text(msg1, parse_mode='MarkdownV2')

        # ── MENSAJE 2: Fundamental ────────────────────────────────────────────
        if not is_crypto(simbolo) and fundamental:
            pe = fundamental.get("pe_ratio")
            roe = fundamental.get("roe")
            dividend = fundamental.get("dividend_yield")
            revenue_growth = fundamental.get("revenue_growth")
            debt_to_eq = fundamental.get("debt_to_equity")
            net_margin = fundamental.get("net_margin")

            if pe and pe > 30:
                pe_estado = "🔴 Alto \\(>30\\)"
            elif pe and pe >= 15:
                pe_estado = "🟡 Normal \\(15\\-30\\)"
            elif pe:
                pe_estado = "🟢 Bajo \\(<15\\)"
            else:
                pe_estado = "⚪ Sin datos"

            if roe and roe > 0.15:
                roe_estado = "🟢 Excelente \\(>15%\\)"
            elif roe and roe > 0.10:
                roe_estado = "🟡 Bueno \\(10\\-15%\\)"
            elif roe:
                roe_estado = "🔴 Bajo \\(<10%\\)"
            else:
                roe_estado = "⚪ Sin datos"

            pe_str = fmt_num(pe, decimals=1) if pe else "N/A"
            roe_str = fmt_pct(roe, multiply=True) if roe else "N/A"
            div_str = fmt_pct(dividend, multiply=True) if dividend else "N/A"
            rev_str = fmt_pct(revenue_growth, multiply=True) if revenue_growth else "N/A"
            debt_str = fmt_num(debt_to_eq, decimals=2) if debt_to_eq else "N/A"
            margin_str = fmt_pct(net_margin, multiply=True) if net_margin else "N/A"

            msg2 = (
                f"╔══════════════════════╗\n"
                f"║ 📋 ANÁLISIS FUNDAMENTAL\n"
                f"╚══════════════════════╝\n\n"
                f"*P/E Ratio:* {pe_str}\n"
                f"{pe_estado}\n\n"
                f"*ROE:* {roe_str}\n"
                f"{roe_estado}\n\n"
                f"*Dividend Yield:* {div_str}\n"
                f"*Revenue Growth:* {rev_str}\n"
                f"*Debt/Equity:* {debt_str}\n"
                f"*Net Margin:* {margin_str}\n\n"
                f"_\\(2/3\\) Calculando técnico\\.\\.\\._"
            )
        else:
            msg2 = (
                f"╔══════════════════════╗\n"
                f"║ 📋 ANÁLISIS FUNDAMENTAL\n"
                f"╚══════════════════════╝\n\n"
                f"⚪ _Datos fundamentales no disponibles para cripto_\n\n"
                f"_\\(2/3\\) Calculando técnico\\.\\.\\._"
            )

        await update.message.reply_text(msg2, parse_mode='MarkdownV2')

        # ── MENSAJE 3: Técnico + Score ─────────────────────────────────────────
        if technical:
            current_price = technical.get("current_price")
            sma50 = technical.get("sma50")
            sma200 = technical.get("sma200")
            rsi = technical.get("rsi")
            trend = technical.get("trend", "NEUTRAL")

            rsi_val = float(rsi) if rsi else None
            if rsi_val and rsi_val > 70:
                rsi_estado = "🔴 SOBRECOMPRA \\(>70\\)"
            elif rsi_val and rsi_val < 30:
                rsi_estado = "🔴 SOBREVENTA \\(<30\\)"
            elif rsi_val:
                rsi_estado = "🟢 Normal \\(30\\-70\\)"
            else:
                rsi_estado = "⚪ Sin datos"

            trend_emoji = "🟢" if trend == "ALCISTA" else "🔴"
            trend_esc = trend.replace("-", "\\-")

            tech_section = (
                f"*Precio Actual:* {fmt_price(current_price)}\n"
                f"*SMA 50:* {fmt_price(sma50)}\n"
                f"*SMA 200:* {fmt_price(sma200)}\n\n"
                f"*RSI \\(14\\):* {fmt_num(rsi, decimals=1)}\n"
                f"{rsi_estado}\n\n"
                f"*Tendencia:* {trend_emoji} {trend_esc}\n"
            )
        else:
            tech_section = "⚪ _No hay suficientes datos históricos para análisis técnico_\n"

        score = score_data.get("total_score", 0)
        score_color = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
        details = score_data.get("details", [])
        details_str = "\n".join(details) if details else "_Sin datos suficientes_"

        conclusion_trend = technical.get("trend", "NEUTRAL") if technical else "NEUTRAL"
        conclusion = "alcistas" if conclusion_trend == "ALCISTA" else "bajistas" if conclusion_trend == "BAJISTA" else "mixtas"
        name_esc = name.replace(".", "\\.").replace("-", "\\-").replace("(", "\\(").replace(")", "\\)")

        msg3 = (
            f"╔══════════════════════╗\n"
            f"║ 📈 ANÁLISIS TÉCNICO\n"
            f"╚══════════════════════╝\n\n"
            f"{tech_section}\n"
            f"╔══════════════════════╗\n"
            f"║ 🎯 PUNTUACIÓN FINAL\n"
            f"╚══════════════════════╝\n\n"
            f"*Score:* {score_color} {score}/100\n\n"
            f"*Factores:*\n{details_str}\n\n"
            f"*Conclusión:*\n"
            f"{name_esc} muestra señales técnicas {conclusion}\\.\n\n"
            f"⚖️ _Este análisis es educativo\\. No constituye asesoramiento financiero\\._\n\n"
            f"_\\(3/3\\) Análisis completado ✓_"
        )

        await update.message.reply_text(msg3, parse_mode='MarkdownV2')

    except Exception as e:
        print(f"Error en /analizar {simbolo}: {e}")
        await msg_espera.edit_text(
            f"❌ Error analizando `{simbolo}`\\: {str(e)[:100]}",
            parse_mode='MarkdownV2'
        )


async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /comparar"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: `/comparar [S1] [S2]`\nEjemplo: `/comparar AAPL MSFT`",
            parse_mode='Markdown'
        )
        return

    sim1 = context.args[0].upper()
    sim2 = context.args[1].upper()

    msg_espera = await update.message.reply_text(f"⏳ Comparando {sim1} vs {sim2}…")

    try:
        # Obtener ambos quotes
        q1 = await (CoinGecko.get_quote(sim1) if is_crypto(sim1) else Yahoo.get_quote(sim1))
        q2 = await (CoinGecko.get_quote(sim2) if is_crypto(sim2) else Yahoo.get_quote(sim2))

        if not q1 or not q1.get("price"):
            await msg_espera.edit_text(f"❌ No encontré datos para `{sim1}`", parse_mode='Markdown')
            return
        if not q2 or not q2.get("price"):
            await msg_espera.edit_text(f"❌ No encontré datos para `{sim2}`", parse_mode='Markdown')
            return

        p1 = q1["price"]
        p2 = q2["price"]
        c1 = q1.get("changePercent", 0) or 0
        c2 = q2.get("changePercent", 0) or 0
        n1 = q1.get("name", sim1)
        n2 = q2.get("name", sim2)

        e1 = "📈" if c1 >= 0 else "📉"
        e2 = "📈" if c2 >= 0 else "📉"
        s1 = "+" if c1 >= 0 else ""
        s2 = "+" if c2 >= 0 else ""

        ganador = sim1 if c1 > c2 else sim2 if c2 > c1 else None
        winner_line = f"\n🏆 *Mejor rendimiento hoy: {ganador}*" if ganador else "\n🤝 *Rendimiento similar hoy*"

        msg = (
            f"⚖️ *Comparación: {sim1} vs {sim2}*\n"
            f"{'─' * 28}\n\n"
            f"{e1} *{n1}* (`{sim1}`)\n"
            f"💵 Precio: *{fmt_price(p1)}*\n"
            f"📊 Cambio: *{s1}{c1:.2f}%*\n"
            f"📊 Market Cap: *{fmt_market_cap(q1.get('marketCap'))}*\n\n"
            f"{e2} *{n2}* (`{sim2}`)\n"
            f"💵 Precio: *{fmt_price(p2)}*\n"
            f"📊 Cambio: *{s2}{c2:.2f}%*\n"
            f"📊 Market Cap: *{fmt_market_cap(q2.get('marketCap'))}*"
            f"{winner_line}"
        )

        await msg_espera.edit_text(msg, parse_mode='Markdown')

    except Exception as e:
        await msg_espera.edit_text(f"❌ Error: {str(e)}")


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ayuda"""
    msg = (
        "*📚 AYUDA*\n\n"
        "`/analizar AAPL` — Análisis completo\n"
        "`/precio BTC` — Solo precio\n"
        "`/comparar AAPL MSFT` — Comparar activos\n"
        "`/ayuda` — Esta ayuda\n\n"
        "*Cripto soportada:*\n"
        "BTC, ETH, BNB, SOL, ADA, XRP, DOGE,\n"
        "DOT, AVAX, MATIC, LTC, LINK, UNI…\n\n"
        "*Próximas mejoras:*\n"
        "✓ Alertas automáticas\n"
        "✓ Watchlist personal\n"
        "✓ Noticias del activo"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensajes no reconocidos"""
    text = update.message.text.strip().upper()
    # Si parece un ticker, sugerir el comando
    if len(text) <= 6 and text.isalpha():
        await update.message.reply_text(
            f"💡 ¿Querías analizar `{text}`?\n"
            f"Usa: `/analizar {text}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🤖 No entiendo ese mensaje.\n"
            "Usa `/ayuda` para ver los comandos disponibles.",
            parse_mode='Markdown'
        )

# ============================================================================
# FUNCIÓN PRINCIPAL
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

    print("✓ Bot iniciado")
    print("✓ Keep-Alive activo (UptimeRobot listo)")
    print("✓ Yahoo Finance + CoinGecko configurados")
    print("✓ Disponible 24/7 en Render")

    asyncio.run(Database.init())
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
