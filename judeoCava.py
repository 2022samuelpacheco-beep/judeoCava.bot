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
# FORMATO
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
# GLOSARIO
# ============================================================================

GLOSARIO = {
    "pe": (
        "P/E Ratio (Precio / Ganancia)\n\n"
        "Cuanto pagas por cada $1 de ganancia de la empresa.\n\n"
        "Como interpretarlo:\n"
        "< 15 — Barato (posible oportunidad o empresa en problemas)\n"
        "15-30 — Valoracion normal para la mayoria de empresas\n"
        "> 30 — Caro (el mercado espera mucho crecimiento futuro)\n\n"
        "Ejemplo: P/E de 20 significa que pagas $20 por cada $1 que gana la empresa al ano."
    ),
    "roe": (
        "ROE (Return on Equity / Retorno sobre Capital)\n\n"
        "Que tan eficiente es la empresa usando el dinero de sus accionistas para generar ganancias.\n\n"
        "Como interpretarlo:\n"
        "> 15% — Excelente, empresa muy rentable\n"
        "10-15% — Bueno\n"
        "< 10% — Bajo, puede indicar ineficiencia\n"
        "Negativo — La empresa esta perdiendo dinero\n\n"
        "Ejemplo: ROE de 20% significa que por cada $100 invertido por accionistas, genera $20 de ganancia."
    ),
    "roa": (
        "ROA (Return on Assets / Retorno sobre Activos)\n\n"
        "Que tan bien usa la empresa TODOS sus activos (no solo el capital de accionistas) para generar ganancias.\n\n"
        "Como interpretarlo:\n"
        "> 5% — Bueno\n"
        "< 5% — La empresa no usa bien sus activos\n"
        "Negativo — Esta perdiendo dinero\n\n"
        "Siempre es menor que el ROE. Si la diferencia es muy grande, la empresa tiene mucha deuda."
    ),
    "dividendo": (
        "Dividend Yield (Rendimiento por Dividendo)\n\n"
        "Porcentaje que recibes en dividendos por ano al comprar la accion al precio actual.\n\n"
        "Como interpretarlo:\n"
        "0% — No paga dividendos (reinvierte todo para crecer, ej: Amazon)\n"
        "1-3% — Dividendo moderado\n"
        "3-6% — Dividendo atractivo\n"
        "> 6% — Puede ser insostenible, revisar si la empresa puede mantenerlo\n\n"
        "Ejemplo: Yield de 3% con accion a $100 = recibes $3 al ano por accion."
    ),
    "deuda": (
        "Debt/Equity (Deuda / Capital)\n\n"
        "Cuanta deuda tiene la empresa comparado con su capital propio.\n\n"
        "Como interpretarlo:\n"
        "< 0.5 — Poca deuda, empresa solida\n"
        "0.5-2 — Nivel normal segun la industria\n"
        "> 2 — Alta deuda, mayor riesgo financiero\n\n"
        "Nota: Bancos y financieras normalmente tienen D/E alto por su modelo de negocio."
    ),
    "margen": (
        "Net Margin (Margen Neto)\n\n"
        "De cada $1 que vende la empresa, cuanto queda como ganancia despues de todos los gastos.\n\n"
        "Como interpretarlo:\n"
        "> 20% — Muy rentable (empresas de software, farmaceuticas)\n"
        "5-20% — Normal\n"
        "< 5% — Margen ajustado (supermercados, manufactura)\n"
        "Negativo — La empresa esta perdiendo dinero\n\n"
        "Ejemplo: Margen de 15% con ventas de $1,000,000 = gana $150,000 neto."
    ),
    "crecimiento": (
        "Revenue Growth (Crecimiento de Ingresos)\n\n"
        "Cuanto crecieron las ventas de la empresa vs el mismo periodo del ano anterior.\n\n"
        "Como interpretarlo:\n"
        "> 20% — Crecimiento alto (empresa en expansion)\n"
        "5-20% — Crecimiento saludable\n"
        "0-5% — Crecimiento lento (empresa madura)\n"
        "Negativo — Las ventas estan cayendo"
    ),
    "rsi": (
        "RSI (Relative Strength Index / Indice de Fuerza Relativa)\n\n"
        "Indicador de momentum que va de 0 a 100 y mide si un activo esta sobrecomprado o sobrevendido.\n\n"
        "Como interpretarlo:\n"
        "> 70 — SOBRECOMPRADO: el precio subio mucho rapido, posible correccion pronto\n"
        "30-70 — ZONA NORMAL: ni extremos de compra ni venta\n"
        "< 30 — SOBREVENDIDO: el precio cayo mucho rapido, posible rebote pronto\n\n"
        "Se calcula con los ultimos 14 dias de precios. Es una señal, no una garantia."
    ),
    "sma": (
        "SMA (Simple Moving Average / Media Movil Simple)\n\n"
        "Promedio del precio de cierre de los ultimos N dias. Muestra la tendencia.\n\n"
        "SMA 50 — Promedio de 50 dias (tendencia de corto/mediano plazo)\n"
        "SMA 200 — Promedio de 200 dias (tendencia de largo plazo)\n\n"
        "Como usarlos:\n"
        "SMA50 > SMA200 = Golden Cross = tendencia ALCISTA\n"
        "SMA50 < SMA200 = Death Cross = tendencia BAJISTA\n\n"
        "Si el precio esta sobre SMA200, se considera en territorio alcista."
    ),
    "marketcap": (
        "Market Cap (Capitalizacion de Mercado)\n\n"
        "Valor total de la empresa en bolsa = precio de la accion × numero total de acciones.\n\n"
        "Categorias:\n"
        "< $300M — Small Cap (pequena, mayor riesgo y potencial)\n"
        "$300M-$10B — Mid Cap (mediana)\n"
        "> $10B — Large Cap (grande, mas estable)\n"
        "> $200B — Mega Cap (gigantes como Apple, Microsoft)\n\n"
        "No confundir con el precio de la accion: una accion a $5 puede tener mayor market cap que una a $500."
    ),
    "score": (
        "Score de Inversion (0-100)\n\n"
        "Puntuacion que combina 4 factores para dar una vision rapida:\n\n"
        "P/E saludable (10-30) — hasta 25 puntos\n"
        "ROE > 15% — hasta 25 puntos\n"
        "RSI < 70 (sin sobrecompra) — hasta 25 puntos\n"
        "Tendencia alcista SMA50 > SMA200 — hasta 25 puntos\n\n"
        "Interpretacion:\n"
        "70-100 — Señales positivas\n"
        "50-69 — Señales mixtas\n"
        "0-49 — Señales negativas o datos insuficientes\n\n"
        "IMPORTANTE: Es educativo, no reemplaza investigacion propia ni asesoria financiera."
    ),
}

GLOSARIO_MENU = (
    "Elige el termino que quieres entender:\n\n"
    "/glosario pe — P/E Ratio\n"
    "/glosario roe — ROE (Retorno sobre Capital)\n"
    "/glosario roa — ROA (Retorno sobre Activos)\n"
    "/glosario dividendo — Dividend Yield\n"
    "/glosario deuda — Debt/Equity\n"
    "/glosario margen — Net Margin\n"
    "/glosario crecimiento — Revenue Growth\n"
    "/glosario rsi — RSI\n"
    "/glosario sma — SMA 50 y SMA 200\n"
    "/glosario marketcap — Market Cap\n"
    "/glosario score — Score de Inversion"
)

# ============================================================================
# COMANDOS
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name
    await update.message.reply_text(
        f"Hola {nombre}! Soy tu asistente financiero\n\n"
        "/analizar AAPL — Analisis completo\n"
        "/precio BTC — Precio rapido\n"
        "/noticias INTC — Ultimas noticias\n"
        "/comparar AAPL MSFT — Comparar activos\n"
        "/glosario — Que significa cada termino\n"
        "/ayuda — Ayuda completa\n\n"
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
        e = "sube" if change >= 0 else "baja"
        await msg.edit_text(
            f"*{q.get('name', simbolo)}* ({simbolo})\n\n"
            f"Precio: *{fmt_price(q['price'])}*\n"
            f"Hoy {e}: *{fmt_pct(change)}*\n"
            f"Market Cap: *{fmt_cap(q.get('marketCap'))}*",
            parse_mode='Markdown'
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
        # Obtener datos
        if is_crypto(simbolo):
            q        = await CoinGecko.get_quote(simbolo)
            hist     = await CoinGecko.get_historical(simbolo)
            profile  = None
            metrics  = None
        else:
            data     = await StockAPI.get_all(simbolo)
            q        = data.get("quote")
            profile  = data.get("profile")
            metrics  = data.get("metrics")
            hist     = data.get("historical")

        if not q or not q.get("price"):
            await msg.edit_text(
                f"No encontre datos para {simbolo}\n"
                "Verifica el simbolo (ej: AAPL, MSFT, BTC)"
            )
            return

        # Tecnico
        technical = None
        hist_n = len(hist) if hist else 0
        if hist and hist_n >= 50:
            technical = TechnicalAnalysis.analyze_technicals(hist)

        # Fundamental y score
        fundamental = FundamentalAnalysis.analyze_fundamentals(metrics or {}, q)
        score_data  = ScoringSystem.calculate_score(technical or {}, fundamental or {})

        price  = q.get("price")
        change = q.get("changePercent") or 0
        name   = q.get("name") or (profile or {}).get("name") or simbolo
        sector = (profile or {}).get("sector") or "N/A"
        mktcap = q.get("marketCap") or (profile or {}).get("marketCap")
        e      = "sube" if change >= 0 else "baja"

        # MSG 1 — Precio
        sector_line = f"Sector: {sector}\n" if sector != "N/A" else ""
        await msg.edit_text(
            f"ANALISIS: {simbolo}\n{'='*22}\n\n"
            f"*{name}*\n{sector_line}\n"
            f"Precio: *{fmt_price(price)}*\n"
            f"Hoy {e}: *{fmt_pct(change)}*\n"
            f"Market Cap: *{fmt_cap(mktcap)}*\n\n"
            f"_1 de 3 calculando fundamental..._",
            parse_mode='Markdown'
        )

        # MSG 2 — Fundamental
        if not is_crypto(simbolo) and fundamental:
            pe  = fundamental.get("pe_ratio")
            roe = fundamental.get("roe")
            div = fundamental.get("dividend_yield")
            rev = fundamental.get("revenue_growth")
            d2e = fundamental.get("debt_to_equity")
            nm  = fundamental.get("net_margin")

            def pe_label(v):
                if v is None: return "sin datos"
                return "alto" if v > 30 else "normal" if v >= 15 else "bajo"
            def roe_label(v):
                if v is None: return "sin datos"
                return "excelente" if v > 0.15 else "bueno" if v > 0.10 else "bajo"

            # Mostrar N/A con sugerencia si no hay datos
            pe_str  = f"{fmt_num(pe, 1)} ({pe_label(pe)})" if pe is not None else "N/A — intenta /noticias " + simbolo
            roe_str = f"{fmt_pct(roe, multiply=True)} ({roe_label(roe)})" if roe is not None else "N/A"

            m2 = (
                f"FUNDAMENTAL: {simbolo}\n{'='*22}\n\n"
                f"P/E Ratio: *{pe_str}*\n"
                f"ROE: *{roe_str}*\n"
                f"Dividend Yield: *{fmt_pct(div, multiply=True) if div is not None else 'N/A'}*\n"
                f"Revenue Growth: *{fmt_pct(rev, multiply=True) if rev is not None else 'N/A'}*\n"
                f"Debt/Equity: *{fmt_num(d2e) if d2e is not None else 'N/A'}*\n"
                f"Net Margin: *{fmt_pct(nm, multiply=True) if nm is not None else 'N/A'}*\n\n"
                f"_Usa /glosario para entender cada termino_\n\n"
                f"_2 de 3 calculando tecnico..._"
            )
        else:
            m2 = (
                f"FUNDAMENTAL: {simbolo}\n{'='*22}\n\n"
                f"No aplica para cripto\n\n"
                f"_2 de 3 calculando tecnico..._"
            )
        await update.message.reply_text(m2, parse_mode='Markdown')

        # MSG 3 — Tecnico + Score
        if technical:
            cp     = technical.get("current_price")
            sma50  = technical.get("sma50")
            sma200 = technical.get("sma200")
            rsi    = technical.get("rsi")
            trend  = technical.get("trend", "NEUTRAL")
            rsi_v  = float(rsi) if rsi else None

            rsi_txt = ("SOBRECOMPRA >70" if rsi_v and rsi_v > 70
                       else "SOBREVENTA <30" if rsi_v and rsi_v < 30
                       else "Normal 30-70"   if rsi_v else "N/A")
            t_txt = "sube" if trend == "ALCISTA" else "baja"

            tech_txt = (
                f"Precio actual: *{fmt_price(cp)}*\n"
                f"SMA 50: *{fmt_price(sma50)}*\n"
                f"SMA 200: *{fmt_price(sma200)}*\n\n"
                f"RSI (14): *{fmt_num(rsi, 1)}* — {rsi_txt}\n\n"
                f"Tendencia: *{trend}* (precio {t_txt})\n"
            )
        else:
            tech_txt = f"Tecnico no disponible ({hist_n} dias de historial, minimo 50)\n"

        score = score_data.get("total_score", 0)
        s_txt = "BUENO" if score >= 70 else "REGULAR" if score >= 50 else "BAJO"
        details = "\n".join(score_data.get("details", [])) or "Sin factores disponibles"
        concl = ("alcistas" if technical and technical.get("trend") == "ALCISTA"
                 else "bajistas" if technical and technical.get("trend") == "BAJISTA"
                 else "mixtas")

        m3 = (
            f"TECNICO + SCORE: {simbolo}\n{'='*22}\n\n"
            f"{tech_txt}\n"
            f"PUNTUACION: *{score}/100* ({s_txt})\n{'='*22}\n"
            f"{details}\n\n"
            f"Conclusion: *{name}* muestra señales {concl}\n\n"
            f"_Educativo. No es asesoramiento financiero._\n"
            f"_3 de 3 completado | /noticias {simbolo} para ver noticias_"
        )
        await update.message.reply_text(m3, parse_mode='Markdown')

    except Exception as ex:
        import traceback
        traceback.print_exc()
        await msg.edit_text(f"Error analizando {simbolo}: {str(ex)[:120]}")


async def noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /noticias AAPL  o  /noticias BTC")
        return

    simbolo = context.args[0].upper()
    msg = await update.message.reply_text(f"Buscando noticias de {simbolo}...")

    try:
        if is_crypto(simbolo):
            # Para cripto usar AV con el nombre completo si es posible
            from apis import AlphaVantage
            import httpx
            async with httpx.AsyncClient() as client:
                news = await AlphaVantage.get_news(simbolo, client)
        else:
            news = await StockAPI.get_news(simbolo)

        if not news:
            await msg.edit_text(
                f"No encontre noticias recientes para {simbolo}\n"
                "Intenta mas tarde o verifica el simbolo."
            )
            return

        lines = [f"NOTICIAS: {simbolo}\n{'='*22}\n"]
        for i, n in enumerate(news[:5], 1):
            title   = n.get("title", "Sin titulo")[:80]
            date    = n.get("date", "")[:10]
            source  = n.get("source", "")
            url     = n.get("url", "")
            sentiment = n.get("sentiment", "")
            sent_line = f" [{sentiment}]" if sentiment else ""

            lines.append(
                f"{i}. *{title}*\n"
                f"   {date} — {source}{sent_line}\n"
                f"   {url}\n"
            )

        await msg.edit_text("\n".join(lines), parse_mode='Markdown',
                            disable_web_page_preview=True)

    except Exception as ex:
        print(f"Error /noticias: {ex}")
        await msg.edit_text(f"Error buscando noticias de {simbolo}")


async def glosario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(GLOSARIO_MENU)
        return

    termino = context.args[0].lower()
    texto = GLOSARIO.get(termino)

    if texto:
        await update.message.reply_text(texto)
    else:
        await update.message.reply_text(
            f"No encontre el termino '{termino}'\n\n" + GLOSARIO_MENU
        )


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
            f"COMPARACION: {s1} vs {s2}\n{'='*22}\n\n"
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
        "COMANDOS DISPONIBLES\n\n"
        "/analizar AAPL — Analisis completo (precio, fundamental, tecnico, score)\n"
        "/precio BTC — Solo el precio actual\n"
        "/noticias INTC — Ultimas noticias del activo\n"
        "/comparar AAPL MSFT — Comparar dos activos lado a lado\n"
        "/glosario — Que significa P/E, ROE, RSI, SMA...\n\n"
        "CRIPTO SOPORTADA:\n"
        "BTC ETH BNB SOL ADA XRP DOGE DOT AVAX LTC LINK UNI ATOM TRX NEAR SHIB\n\n"
        "FUENTES:\n"
        "FMP + Alpha Vantage + Finnhub + CoinGecko"
    )


async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if len(text) <= 6 and text.isalpha():
        await update.message.reply_text(
            f"Para analizar {text} usa:\n/analizar {text}\n\nO para solo el precio:\n/precio {text}"
        )
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
    application.add_handler(CommandHandler("precio",   precio))
    application.add_handler(CommandHandler("noticias", noticias))
    application.add_handler(CommandHandler("glosario", glosario))
    application.add_handler(CommandHandler("comparar", comparar))
    application.add_handler(CommandHandler("ayuda",    ayuda))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))

    print("Bot iniciado - FMP + Alpha Vantage + Finnhub + CoinGecko")
    asyncio.run(Database.init())
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
