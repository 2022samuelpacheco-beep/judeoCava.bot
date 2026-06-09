import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ← AGREGAR ESTAS 2 LÍNEAS ↓
from keep_alive import keep_alive
keep_alive()  # Inicia el servidor Flask
# ↑ ←

TOKEN = os.environ.get('TOKEN')

if not TOKEN:
    raise ValueError("TOKEN no está configurado.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy JudeoCava. Como te puedo ayudar hoy.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Dijiste: {update.message.text}")

def main():
    # SIN asyncio.run() - eso es lo que causa el problema
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    print("✓ JudeoCava iniciado. Presiona Ctrl+C para detenerlo.")
    app.run_polling()  # Aquí simplemente ejecuta sin asyncio.run()

if __name__ == '__main__':
    main()
