import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import config
from handlers import router as main_router, db

# 1. Configurazione Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # 1. Inizializzazione Bot e Dispatcher
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
    dp = Dispatcher()

    # 2. Routing
    # Importiamo il router da handlers.py
    dp.include_router(main_router)

    # 3. Gestione Ciclo di Vita
    # Rimuove webhook pendenti all'avvio
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        logger.info("🚀 Bot avviato. In attesa di messaggi...")
        await dp.start_polling(bot)
    finally:
        # Chiusura pulita della connessione al database
        # Usiamo l'istanza 'db' importata da handlers per chiudere la connessione corretta
        await db.close()
        await bot.session.close()
        logger.info("🛑 Bot spento. Connessioni chiuse.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Bot interrotto manualmente (KeyboardInterrupt).")
