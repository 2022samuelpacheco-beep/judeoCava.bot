import os
import httpx
import pandas as pd
import numpy as np
import aiosqlite

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)

load_dotenv()

TOKEN = os.getenv("TOKEN")
FMP_KEY = os.getenv("FMP_KEY")

DB = "cache.db"


# =========================
# CACHE SQLITE
# =========================

async def init_db():

    async with aiosqlite.connect(DB) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            symbol TEXT PRIMARY KEY,
            data TEXT
        )
        """)

        await db.commit()


# =========================
# FMP
# =========================

async def get_quote(symbol):

    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_KEY}"

    async with httpx.AsyncClient(timeout=15) as client:

        r = await client.get(url)

    data = r.json()

    if not data:
        return None

    return data[0]


async def get_profile(symbol):

    url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}?apikey={FMP_KEY}"

    async with httpx.AsyncClient(timeout=15) as client:

        r = await client.get(url)

    data = r.json()

    if not data:
        return None

    return data[0]


async def get_ratios(symbol):

    url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{symbol}?apikey={FMP_KEY}"

    async with httpx.AsyncClient(timeout=15) as client:

        r = await client.get(url)

    data = r.json()

    if not data:
        return None

    return data[0]


async def get_history(symbol):

    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?serietype=line&apikey={FMP_KEY}"

    async with httpx.AsyncClient(timeout=15) as client:

        r = await client.get(url)

    data = r.json()

    return data.get("historical", [])


# =========================
# RSI
# =========================

def calcular_rsi(df, period=14):

    delta = df["close"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi.iloc[-1], 2)


# =========================
# ANALIZAR
# =========================

async def analizar(update: Update,
                   context: ContextTypes.DEFAULT_TYPE):

    if not context.args:

        await update.message.reply_text(
            "Uso:\n/analizar INTC"
        )

        return

    symbol = context.args[0].upper()

    try:

        quote = await get_quote(symbol)

        profile = await get_profile(symbol)

        metrics = await get_ratios(symbol)

        history = await get_history(symbol)

        if not quote:

            await update.message.reply_text(
                "No encontré el símbolo."
            )

            return

        df = pd.DataFrame(history)

        rsi = calcular_rsi(df)

        sma50 = round(
            df["close"].rolling(50).mean().iloc[-1],
            2
        )

        sma200 = round(
            df["close"].rolling(200).mean().iloc[-1],
            2
        )

        precio = quote["price"]

        tendencia = (
            "🟢 Alcista"
            if sma50 > sma200
            else "🔴 Bajista"
        )

        pe = metrics.get("peRatioTTM")

        roe = metrics.get(
            "roeTTM",
            0
        )

        dividend = metrics.get(
            "dividendYieldPercentageTTM",
            0
        )

        score = 0

        if pe and pe < 20:
            score += 25

        if roe and roe > 0.15:
            score += 25

        if rsi < 70:
            score += 25

        if sma50 > sma200:
            score += 25

        msg = f"""
📊 {profile['companyName']}

💵 Precio: ${precio}

═══════════════
FUNDAMENTAL
═══════════════

P/E:
{round(pe,2) if pe else 'N/A'}

ROE:
{round(roe*100,2)}%

Dividend Yield:
{round(dividend,2)}%

═══════════════
TÉCNICO
═══════════════

RSI:
{rsi}

SMA50:
{sma50}

SMA200:
{sma200}

Tendencia:
{tendencia}

═══════════════
SCORE
═══════════════

⭐ {score}/100

⚠️ No es recomendación financiera.
"""

        await update.message.reply_text(msg)

    except Exception as e:

        await update.message.reply_text(
            f"Error:\n{e}"
        )


# =========================
# START
# =========================

async def start(update: Update,
                context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Bot Financiero\n\n"
        "/analizar INTC"
    )


# =========================
# MAIN
# =========================

async def post_init(app):

    await init_db()


def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "analizar",
            analizar
        )
    )

    print("Bot iniciado")

    app.run_polling()


if __name__ == "__main__":
    main()
