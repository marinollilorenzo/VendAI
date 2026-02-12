import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# --- IMPORT MODULI PERSONALI ---
from config import config  # <--- Importiamo la config
from database import DatabaseManager
from handlers import router as main_router
from notifier import main_loop as notifier_loop

# Configurazione Logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VendAI_Runner")

async def main():
    # 1. CONTROLLO PRESENZA DATABASE
    if not os.path.exists(config.DB_PATH):
        logger.critical(f"❌ DATABASE NON TROVATO: '{config.DB_PATH}' non esiste.")
        logger.critical("⚠️  Esegui prima 'python3 init_db.py'!")
        return

    # 2. Inizializzazione Database Manager (Test connessione opzionale)
    db = DatabaseManager()
    logger.info(f"✅ Database '{config.DB_PATH}' rilevato.")

    # 3. Configurazione Bot (Aiogram)
    # Usiamo il token dalla config
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(main_router)

    # 4. Avvio Parallelo
    logger.info("🚀 Avvio del sistema VendAI Completo...")

    await bot.delete_webhook(drop_pending_updates=True)

    bot_task = asyncio.create_task(dp.start_polling(bot))
    notify_task = asyncio.create_task(notifier_loop())

    logger.info("✅ Bot e Notifier sono attivi.")

    try:
        await asyncio.gather(bot_task, notify_task)
    except Exception as e:
        logger.error(f"Errore critico: {e}")
    finally:
        await bot.session.close()
        logger.info("🛑 Sistema spento.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Chiusura manuale.")