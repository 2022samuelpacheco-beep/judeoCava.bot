from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!', 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """Inicia un servidor Flask en background para mantener el servicio activo"""
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
