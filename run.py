import asyncio
import os
from dotenv import load_dotenv
from telegram.ext import Application

# Importiamo la funzione che configura l'applicazione
from telegramBot import setup_bot_application
# Importiamo il loop del notifier
from notifier import main_loop as notifier_loop
# Importiamo l'inizializzazione DB
from database import db_initialization
load_dotenv()
TOKEN = os.getenv("TOKEN")
async def main():
    # 1. Inizializza DB
    db_initialization()
    
    # 2. Costruisci il bot usando la funzione dal modulo telegram_bot
    application = setup_bot_application(TOKEN) # Passiamo il token
    
    # 3. Avvia i due task in parallelo
    print("🚀 Avvio di VendAI (Bot + Notifier insieme)...")
    
    # Task 1: Il bot Telegram
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Task 2: Il guardiano delle notifiche
    notifier_task = asyncio.create_task(notifier_loop())
    
    print("✅ Tutto attivo! Premi Ctrl+C per fermare.")
    
    # Mantiene vivo il programma principale finché uno dei due non termina
    try:
        await asyncio.gather(notifier_task) # Aspettiamo solo il notifier_task (il bot gestisce il suo loop)
    except KeyboardInterrupt:
        print("Spegnimento in corso...")
    finally:
        # Pulizia corretta quando si spegne
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    asyncio.run(main())