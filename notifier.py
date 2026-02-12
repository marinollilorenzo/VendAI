import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import config

# Riutilizziamo il tuo DatabaseManager esistente
from database import DatabaseManager

# Configurazione Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Notifier")

def get_publish_kb(id_pub):
    """Crea il bottone per la pubblicazione immediata"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Pubblica Ora", callback_data=f"publish_now:{id_pub}")]
    ])
    return keyboard

async def check_and_notify(bot: Bot, db: DatabaseManager):
    logger.info("🔍 Controllo scadenze...")
    
    try:
        st_scheduled = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='SCHEDULED'"))['id_status_type']
        st_pre = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='NOTIFIED_PRE'"))['id_status_type']
        st_final = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='NOTIFIED_FINAL'"))['id_status_type']
    except TypeError:
        logger.error("❌ Stati DB mancanti. Esegui INSERT per NOTIFIED_FINAL!")
        return

    now = datetime.now()
    
    # =========================================================================
    # FASE 1: PRE-NOTIFICA (Mancano 30 minuti)
    # =========================================================================
    warning_threshold = now + timedelta(minutes=30)
    
    query_warn = """
    SELECT pa.id_publication_ad, pa.id_ad, pa.scheduled_datetime, p.name as platform_name, a.id_telegram_user, a.generated_title
    FROM publication_ad pa
    JOIN ad a ON pa.id_ad = a.id_ad
    JOIN platform p ON pa.id_platform = p.id_platform
    WHERE pa.id_status_type = ? 
    AND pa.deleted_datetime IS NULL
    AND pa.scheduled_datetime <= ?
    """
    
    pending_warnings = await db._fetch_all(query_warn, (st_scheduled, warning_threshold.strftime("%Y-%m-%d %H:%M:%S")))
    
    for pub in pending_warnings:
        try:
            sched_time = datetime.strptime(pub['scheduled_datetime'], "%Y-%m-%d %H:%M:%S")
            minutes_left = int((sched_time - now).total_seconds() / 60)
            if minutes_left < 0: minutes_left = 0
            
            msg = (
                f"⏰ **PREAVVISO: -{minutes_left} min**\n"
                f"📦 Annuncio: {pub['generated_title']}\n"
                f"🌐 Piattaforma: **{pub['platform_name']}**\n\n"
                f"Vuoi anticipare e pubblicare subito?"
            )
            
            await bot.send_message(
                pub['id_telegram_user'], 
                msg, 
                parse_mode="Markdown",
                reply_markup=get_publish_kb(pub['id_publication_ad'])
            )
            
            # Aggiorna a NOTIFIED_PRE
            await db._execute_query(
                "UPDATE publication_ad SET id_status_type = ? WHERE id_publication_ad = ?",
                (st_pre, pub['id_publication_ad'])
            )
            logger.info(f"✅ Pre-avviso inviato per Pub #{pub['id_publication_ad']}")
            
        except Exception as e:
            logger.error(f"Errore warning {pub['id_publication_ad']}: {e}")

    # =========================================================================
    # FASE 2: NOTIFICA FINALE SOFT (È ORA)
    # =========================================================================
    # Cerchiamo annunci SCHEDULED o NOTIFIED_PRE che sono scaduti
    query_final = """
    SELECT pa.id_publication_ad, pa.id_ad, a.id_telegram_user, a.generated_title, p.name as platform_name
    FROM publication_ad pa
    JOIN ad a ON pa.id_ad = a.id_ad
    JOIN platform p ON pa.id_platform = p.id_platform
    WHERE pa.id_status_type IN (?, ?) 
    AND pa.deleted_datetime IS NULL
    AND pa.scheduled_datetime <= ?
    """
    
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    ready_to_publish = await db._fetch_all(query_final, (st_scheduled, st_pre, now_str))
    
    for pub in ready_to_publish:
        try:
            msg = (
                f"🔔 **È ORA DI PUBBLICARE!** 🔔\n"
                f"Il momento programmato è arrivato.\n\n"
                f"📦 {pub['generated_title']}\n"
                f"🌐 Su: **{pub['platform_name']}**\n\n"
                f"Premi il tasto qui sotto quando sei pronto per ricevere i testi 👇"
            )
            
            await bot.send_message(
                pub['id_telegram_user'],
                msg,
                parse_mode="Markdown",
                reply_markup=get_publish_kb(pub['id_publication_ad'])
            )
            
            # Aggiorna a NOTIFIED_FINAL (così il loop non lo ripesca più)
            await db._execute_query(
                "UPDATE publication_ad SET id_status_type = ? WHERE id_publication_ad = ?",
                (st_final, pub['id_publication_ad'])
            )
            logger.info(f"🚀 Notifica Soft inviata per Pub #{pub['id_publication_ad']}")
            
        except Exception as e:
            logger.error(f"Errore final notify {pub['id_publication_ad']}: {e}")

async def main_loop(bot: Bot):
    logger.info("🟢 Guardiano Notifiche Avviato")
    db = DatabaseManager()
    try:
        while True:
            await check_and_notify(bot, db)
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("🔴 Guardiano fermato manualmente")

if __name__ == "__main__":
    pass