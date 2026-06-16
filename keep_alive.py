from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive! 🤖', 200

def run():
    """Ejecutar servidor Flask"""
    app.run(host='0.0.0.0', port=8080, debug=False)

def keep_alive():
    """Iniciar servidor en thread daemon"""
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    print("✓ Keep-Alive server iniciado en puerto 8080")
