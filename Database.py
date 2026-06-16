import aiosqlite
import json
from datetime import datetime, timedelta
import os

DATABASE = "cache.db"

class Database:
    """Gestión de caché SQLite para reducir llamadas API"""
    
    @staticmethod
    async def init():
        """Crear tabla si no existe"""
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, data_type)
                )
            ''')
            await db.commit()
    
    @staticmethod
    async def get(symbol: str, data_type: str, max_age_minutes: int = 60):
        """
        Obtener datos del caché
        max_age_minutes: Máxima antigüedad permitida en minutos
        """
        try:
            async with aiosqlite.connect(DATABASE) as db:
                cursor = await db.execute(
                    'SELECT data, timestamp FROM cache WHERE symbol = ? AND data_type = ?',
                    (symbol.upper(), data_type)
                )
                row = await cursor.fetchone()
                
                if row:
                    data_str, timestamp_str = row
                    timestamp = datetime.fromisoformat(timestamp_str)
                    
                    # Verificar si el caché es válido
                    if datetime.now() - timestamp < timedelta(minutes=max_age_minutes):
                        return json.loads(data_str)
                
                return None
        except Exception as e:
            print(f"Error obteniendo caché: {e}")
            return None
    
    @staticmethod
    async def save(symbol: str, data_type: str, data: dict):
        """Guardar datos en el caché"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    '''INSERT OR REPLACE INTO cache (symbol, data_type, data) 
                       VALUES (?, ?, ?)''',
                    (symbol.upper(), data_type, json.dumps(data))
                )
                await db.commit()
        except Exception as e:
            print(f"Error guardando caché: {e}")
    
    @staticmethod
    async def clear_old(days: int = 7):
        """Limpiar caché antiguo"""
        try:
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute(
                    'DELETE FROM cache WHERE timestamp < datetime("now", ? || " days")',
                    (f'-{days}',)
                )
                await db.commit()
        except Exception as e:
            print(f"Error limpiando caché: {e}")
