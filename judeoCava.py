import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import Database
from apis import StockAPI, CoinGecko, is_crypto
from analytics import TechnicalAnalysis, FundamentalAnalysis, ScoringSystem
from keep_alive import keep_alive

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN no configurado")

# ============================================================================
# FORMATO SEGURO
# ============================================================================

def fmt_price(val, decimals=2):
    try:
        return f"${float(val):,.{decimals}f}"
    except:
        return "N/A"

def fmt_pct(val, multiply=False):
    try:
        v = float(val) * 100 if multiply else float(val)
        return f"{'+' if v>=0 else ''}{v:.2f}%"
    except:
        return "N/A"

def fmt_num(val, decimals=2):
    try:
        return f"{float(val):,.{decimals}f}"
    except:
        return "N/A"

def fmt_cap(val):
    try:
        v = float(val)
        if v >= 1e12: return f"${v/1e12:.2f}T"
        if v >= 1e9:  return f"${v/1e9:.2f}B"
        if v >= 1e6:  return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"
    except:
        return "N/A"

# ============================================================================
# COMANDOS
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name
    await update.message.reply_text(
        f"Hola {nombre}! Soy tu asistente financiero\n\n"
        "/analizar AAPL - Analisis completo\n"
        "/precio BTC - Precio rapido\n"
        "/comparar AAPL MSFT - Comparar activos\n"
        "/ayuda - Ayuda\n\n"
        "Soporta acciones, ETFs y cripto (BTC, ETH, SOL...)"
    )


async def precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /precio AAPL  o  /precio BTC")
        return
    simbolo = context.args[0].upper()
    msg = await update.message.reply_text(f"Buscando precio de {simbolo}...")
    try:
        if is_crypto(simbolo):
            q = await CoinGecko.get_quote(simbolo)
        else:
            data = await StockAPI.get_all(simbolo)
            q = data.get("quote")

        if not q or not q.get("price"):
            await msg.edit_text(f"No encontre datos para {simbolo}")
            return
        change = q.get("changePercent") or 0
        e = "subio" if change >= 0 else "bajo"
        await msg.edit_text(
            f"{q.get('name', simbolo)} ({simbolo})\n\n"
            f"Precio: {fmt_price(q['price'])}\n"
            f"Hoy {e}: {fmt_pct(change)}"
        )
    except Exception as ex:
        print(f"Error /precio: {ex}")
        await msg.edit_text(f"Error obteniendo {simbolo}")


async def analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Uso: /analizar SIMBOLO\nEj: /analizar AAPL  o  /analizar BTC"
        )
        return

    simbolo = context.args[0].upper()
    msg = await update.message.reply_text(f"Analizando {simbolo}, por favor espera...")

    try:
        # ── Obtener datos ─────────────────────────────────────────────────────
        if is_crypto(simbolo):
            q    = await CoinGecko.get_quote(simbolo)
            hist = await CoinGecko.get_historical(simbolo)
            profile  = None
            metrics  = None
        else:
            data     = await StockAPI.get_all(simbolo)
            q        = data.get("quote")
            profile  = data.get("profile")
            metrics  = data.get("metrics")
            hist     = data.get("historical")

        # ── Validar ───────────────────────────────────────────────────────────
        if not q or not q.get("price"):
            await msg.edit_text(
                f"No encontre datos para {simbolo}\n\n"
                "Verifica el simbolo (ej: AAPL, MSFT, BTC)"
            )
            return

        # ── Tecnico ───────────────────────────────────────────────────────────
        technical = None
        hist_n = len(hist) if hist else 0
        if hist and hist_n >= 50:
            technical = TechnicalAnalysis.analyze_technicals(hist)

        # ── Fundamental y score ───────────────────────────────────────────────
        fundamental = FundamentalAnalysis.analyze_fundamentals(metrics or {}, q)
        score_data  = ScoringSystem.calculate_score(technical or {}, fundamental or {})

        # ── Datos comunes ─────────────────────────────────────────────────────
        price  = q.get("price")
        change = q.get("changePercent") or 0
        name   = q.get("name") or (profile or {}).get("name") or simbolo
        sector = (profile or {}).get("sector") or "N/A"
        mktcap = q.get("marketCap") or (profile or {}).get("marketCap")
        e      = "sube" if change >= 0 else "baja"

        # ════════════════════════
        # MENSAJE 1 — Precio
        # ════════════════════════
        sector_line = f"Sector: {sector}\n" if sector != "N/A" else ""
        m1 = (
            f"ANALISIS: {simbolo}\n"
            f"{'='*22}\n\n"
            f"*{name}*\n"
            f"{sector_line}"
            f"\n"
            f"Precio: *{fmt_price(price)}*\n"
            f"Hoy {e}: *{fmt_pct(change)}*\n"
            f"Market Cap: *{fmt_cap(mktcap)}*\n\n"
            f"_1 de 3 calculando fundamental..._"
        )
        await msg.edit_text(m1, parse_mode='Markdown')

        # ════════════════════════
        # MENSAJE 2 — Fundamental
        # ════════════════════════
        if not is_crypto(simbolo) and fundamental:
            pe  = fundamental.get("pe_ratio")
            roe = fundamental.get("roe")
            div = fundamental.get("dividend_yield")
            rev = fundamental.get("revenue_growth")
            d2e = fundamental.get("debt_to_equity")
            nm  = fundamental.get("net_margin")

            any_data = any(v is not None for v in [pe, roe, div, rev, d2e, nm])

            if any_data:
                pe_ico  = ("alto" if pe and pe > 30
                           else "normal" if pe and pe >= 15
                           else "bajo" if pe else "sin datos")
                roe_ico = ("excelente" if roe and roe > 0.15
                           else "bueno" if roe and roe > 0.10
                           else "bajo" if roe else "sin datos")

                m2 = (
                    f"FUNDAMENTAL: {simbolo}\n"
                    f"{'='*22}\n\n"
                    f"P/E Ratio: *{fmt_num(pe, 1)}* ({pe_ico})\n"
                    f"ROE: *{fmt_pct(roe, multiply=True)}* ({roe_ico})\n"
                    f"Dividend Yield: *{fmt_pct(div, multiply=True)}*\n"
                    f"Revenue Growth: *{fmt_pct(rev, multiply=True)}*\n"
                    f"Debt/Equity: *{fmt_num(d2e)}*\n"
                    f"Net Margin: *{fmt_pct(nm, multiply=True)}*\n\n"
                    f"_2 de 3 calculando tecnico..._"
                )
            else:
                m2 = (
                    f"FUNDAMENTAL: {simbolo}\n"
                    f"{'='*22}\n\n"
                    f"Sin datos fundamentales disponibles\n"
                    f"(intenta de nuevo en unos minutos)\n\n"
                    f"_2 de 3 calculando tecnico..._"
                )
        else:
            m2 = (
                f"FUNDAMENTAL: {simbolo}\n"
                f"{'='*22}\n\n"
                f"No aplica para cripto\n\n"
                f"_2 de 3 calculando tecnico..._"
            )
        await update.message.reply_text(m2, parse_mode='Markdown')

        # ════════════════════════
        # MENSAJE 3 — Tecnico + Score
        # ════════════════════════
        if technical:
            cp     = technical.get("current_price")
            sma50  = technical.get("sma50")
            sma200 = technical.get("sma200")
            rsi    = technical.get("rsi")
            trend  = technical.get("trend", "NEUTRAL")
            rsi_v  = float(rsi) if rsi else None

            rsi_txt = ("SOBRECOMPRA >70" if rsi_v and rsi_v > 70
                       else "SOBREVENTA <30"  if rsi_v and rsi_v < 30
                       else "Normal 30-70"    if rsi_v else "N/A")
            t_ico   = "sube" if trend == "ALCISTA" else "baja"

            tech_txt = (
                f"Precio: *{fmt_price(cp)}*\n"
                f"SMA 50: *{fmt_price(sma50)}*\n"
                f"SMA 200: *{fmt_price(sma200)}*\n\n"
                f"RSI (14): *{fmt_num(rsi, 1)}* - {rsi_txt}\n\n"
                f"Tendencia: *{trend}* ({t_ico})\n"
            )
        else:
            tech_txt = f"Sin datos tecnicos ({hist_n} dias de historial, minimo 50)\n"

        score   = score_data.get("total_score", 0)
        s_txt   = "BUENO" if score >= 70 else "REGULAR" if score >= 50 else "BAJO"
        details = "\n".join(score_data.get("details", [])) or "Sin factores disponibles"
        concl   = ("alcistas" if technical and technical.get("trend") == "ALCISTA"
                   else "bajistas" if technical and technical.get("trend") == "BAJISTA"
                   else "mixtas")

        m3 = (
            f"TECNICO + SCORE: {simbolo}\n"
            f"{'='*22}\n\n"
            f"{tech_txt}\n"
            f"PUNTUACION: *{score}/100* ({s_txt})\n"
            f"{'='*22}\n"
            f"{details}\n\n"
            f"Conclusion: *{name}* muestra señales {concl}\n\n"
            f"_Educativo. No es asesoramiento financiero._\n"
            f"_3 de 3 completado_"
        )
        await update.message.reply_text(m3, parse_mode='Markdown')

    except Exception as ex:
        import traceback
        traceback.print_exc()
        await msg.edit_text(f"Error analizando {simbolo}: {str(ex)[:120]}")


async def comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /comparar AAPL MSFT")
        return

    s1, s2 = context.args[0].upper(), context.args[1].upper()
    msg = await update.message.reply_text(f"Comparando {s1} vs {s2}...")

    try:
        async def get_q(sym):
            if is_crypto(sym):
                return await CoinGecko.get_quote(sym)
            return (await StockAPI.get_all(sym)).get("quote")

        q1, q2 = await asyncio.gather(get_q(s1), get_q(s2))

        if not q1 or not q1.get("price"):
            await msg.edit_text(f"No encontre datos para {s1}")
            return
        if not q2 or not q2.get("price"):
            await msg.edit_text(f"No encontre datos para {s2}")
            return

        c1 = q1.get("changePercent") or 0
        c2 = q2.get("changePercent") or 0
        ganador = s1 if c1 > c2 else (s2 if c2 > c1 else None)
        winner = f"\nGanador de hoy: *{ganador}*" if ganador else "\nRendimiento similar hoy"

        await msg.edit_text(
            f"COMPARACION: {s1} vs {s2}\n"
            f"{'='*22}\n\n"
            f"*{q1.get('name', s1)}*\n"
            f"Precio: *{fmt_price(q1['price'])}*  Cambio: *{fmt_pct(c1)}*\n"
            f"Cap: {fmt_cap(q1.get('marketCap'))}\n\n"
            f"*{q2.get('name', s2)}*\n"
            f"Precio: *{fmt_price(q2['price'])}*  Cambio: *{fmt_pct(c2)}*\n"
            f"Cap: {fmt_cap(q2.get('marketCap'))}"
            f"{winner}",
            parse_mode='Markdown'
        )
    except Exception as ex:
        print(f"Error /comparar: {ex}")
        await msg.edit_text(f"Error comparando {s1} vs {s2}")


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "AYUDA\n\n"
        "/analizar AAPL - Analisis completo con tecnico y fundamental\n"
        "/precio BTC - Solo el precio actual\n"
        "/comparar AAPL MSFT - Comparar dos activos\n\n"
        "Cripto: BTC ETH BNB SOL ADA XRP DOGE DOT AVAX LTC LINK UNI ATOM\n\n"
        "Fuentes: FMP + Alpha Vantage + Finnhub + CoinGecko"
    )


async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if len(text) <= 6 and text.isalpha():
        await update.message.reply_text(f"Para analizar {text} usa:\n/analizar {text}")
    else:
        await update.message.reply_text("Usa /ayuda para ver los comandos disponibles.")


# ============================================================================
# MAIN
# ============================================================================

def main():
    keep_alive()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start",    start))
    application.add_handler(CommandHandler("analizar", analizar))
    application.add_handler(CommandHandler("comparar", comparar))
    application.add_handler(CommandHandler("precio",   precio))
    application.add_handler(CommandHandler("ayuda",    ayuda))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))

    print("Bot iniciado - FMP + Alpha Vantage + Finnhub + CoinGecko")
    asyncio.run(Database.init())
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
