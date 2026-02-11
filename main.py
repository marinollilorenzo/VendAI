import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from database import DatabaseManager
import keyboards as kb
from config import BOT_TOKEN


# Configurazione Logging
logging.basicConfig(level=logging.INFO)

async def main():
    # Inizializziamo il Database Manager
    db = DatabaseManager()
    
    # Inizializziamo Bot e Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # --- HANDLERS DI TEST NAVIGAZIONE ---

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        # Registriamo l'utente nel DB al primo accesso
        await db.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
        await message.answer(
            f"Ciao {message.from_user.first_name}! Benvenuto nella nuova versione di VendAI. 🚀",
            reply_markup=kb.get_main_menu()
        )

    @dp.message(F.text == "👤 Profilo")
    async def show_profile(message: types.Message):
        # Recuperiamo i crediti dal DB per mostrarli nel profilo
        credits = await db.get_user_credits(message.from_user.id)
        await message.answer(
            f"👤 **Il Tuo Profilo**\n\n💰 Crediti disponibili: {credits}",
            reply_markup=kb.get_profile_kb(),
            parse_mode="Markdown"
        )

    @dp.message(F.text == "💎 Abbonamenti")
    async def show_subs(message: types.Message):
        # Esempio di lista piani (in futuro la prenderemo dal DB)
        plans = [
            {"id_account_type": 1, "name": "Pro Launch", "price_euro": 2.99},
            {"id_account_type": 2, "name": "Ultimate Launch", "price_euro": 4.99}
        ]
        await message.answer(
            "💎 **Scegli il tuo piano**\nPotenzia le tue vendite con l'IA!",
            reply_markup=kb.get_subscription_kb(plans),
            parse_mode="Markdown"
        )

    @dp.callback_query(F.data == "main_menu")
    async def back_to_main(callback: types.CallbackQuery):
        await callback.message.edit_text("Ritorno al menu principale...")
        await callback.message.answer("Menu principale:", reply_markup=kb.get_main_menu())
        await callback.answer()

    # Avvio del Bot
    try:
        print("🚀 Bot avviato sul server...")
        await dp.start_polling(bot)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())