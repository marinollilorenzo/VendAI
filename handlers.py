import asyncio
import logging
import io
from aiogram import Router, F, types
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardBuilder
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime


# Import all custom modules
from database import DatabaseManager
import keyboards as kb
from utils import parse_date_text
from aiService import ad_text_generator, AdOutput

# Initialize Router and Database Manager
router = Router()
db = DatabaseManager()

# --- FSM States ---
class AdCreation(StatesGroup):
    WAITING_PHOTO = State()
    WAITING_CONFIRM = State()
    WAITING_MANUAL_TEXT = State() # New state for manual edit
    WAITING_CATEGORY = State()
    WAITING_PLATFORM_SELECTION = State() # Renamed/New
    WAITING_DATE_INPUT = State() # Renamed/New

class AdEditing(StatesGroup):
    CHOOSING_FIELD = State()
    WAITING_NEW_VALUE = State()

class AdSelling(StatesGroup):
    WAITING_AD_SELECTION = State()
    WAITING_PRICE = State()

class AdDeleting(StatesGroup):
    WAITING_CONFIRMATION = State()

# --- 1. 🧩 NUOVO STATO FSM ---
# Aggiungere questa classe insieme alle altre definizioni di StatesGroup
class AdPublishing(StatesGroup):
    WAITING_DATE = State()


# --- Helper Functions ---
def generate_pie_chart(data: list) -> io.BytesIO | None:
    if not data:
        return None
    labels = [item['category'] for item in data]
    sizes = [item['count'] for item in data]
    
    plt.figure(figsize=(8, 6))
    sns.set_theme(style="whitegrid")
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("pastel"))
    plt.title('Vendite per Categoria')
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

# --- Global "Smart Navigation" Handlers ---
# These handlers reset the state if a main menu button is pressed mid-conversation.
@router.message(StateFilter("*"), F.text.in_({
    "🆕 Crea Annuncio", "🛍️ I Miei Annunci", "✅ Segna Venduto", 
    "📊 Statistiche", "💎 Abbonamenti", "👤 Profilo", "❓ Aiuto"
}))
async def global_menu_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        logging.info(f"Cancelling state {current_state} due to menu navigation.")
        await state.clear()
        await message.answer("Operazione precedente annullata.", reply_markup=kb.get_main_menu())

    # Route to the correct handler after clearing the state
    if message.text == "🆕 Crea Annuncio":
        await start_ad_creation(message, state)
    elif message.text == "🛍️ I Miei Annunci":
        await my_ads_handler(message)
    elif message.text == "✅ Segna Venduto":
        await start_sell_ad_wizard(message, state)
    elif message.text == "📊 Statistiche":
        await stats_handler(message)
    elif message.text == "💎 Abbonamenti":
        await subscription_handler(message)
    elif message.text == "👤 Profilo":
        await profile_handler(message)
    elif message.text == "❓ Aiuto":
        await start_handler(message, state)

# --- Core Command & Menu Handlers (No State) ---
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await db.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    # Check for initial credits bonus (Test Mode)
    credits = await db.get_user_credits(message.from_user.id)
    if credits == 0:
        await db.add_test_credits(message.from_user.id, 100)
        await message.answer("🎁 **Bonus Benvenuto!** Hai ricevuto 100 crediti per testare il bot.")

    welcome_text = (
        f"Ciao {message.from_user.first_name}, benvenuto su **VendAI**! 🤖✨\n\n"
        "Premi **🆕 Crea Annuncio** o invia una foto con didascalia per iniziare!"
    )
    await message.answer(welcome_text, reply_markup=kb.get_main_menu(), parse_mode="Markdown")

@router.message(F.text == "👤 Profilo", StateFilter(None))
async def profile_handler(message: Message):
    credits = await db.get_user_credits(message.from_user.id)
    await message.answer(
        f"👤 **Profilo Utente**\n\nID: `{message.from_user.id}`\nCrediti: **{credits}** 💎",
        reply_markup=kb.get_profile_kb(), parse_mode="Markdown"
    )

@router.message(F.text == "💎 Abbonamenti", StateFilter(None))
async def subscription_handler(message: Message):
    mock_plans = [{"id_account_type": 2, "name": "Pro", "price_euro": 2.99}, {"id_account_type": 3, "name": "Ultimate", "price_euro": 4.99}]
    await message.answer("Scegli un piano:", reply_markup=kb.get_subscription_kb(mock_plans))

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Sei nel menu principale.", reply_markup=kb.get_main_menu())
    await callback.answer()

@router.callback_query(F.data.startswith("sub:"))
async def sub_selection_handler(callback: CallbackQuery):
    """
    Handles subscription plan selection.
    For testing purposes, this adds 10 credits to the user.
    """
    # plan_id = int(callback.data.split(":")[1]) # Not used in test logic
    user_id = callback.from_user.id
    
    await db.add_test_credits(user_id, 10)
    new_balance = await db.get_user_credits(user_id)
    
    await callback.answer("💎 Piano attivato (TEST)!")
    await callback.message.answer(f"💎 Piano selezionato! Ti sono stati accreditati 10 crediti per il test. Saldo attuale: {new_balance}")

# --- 1. Ad Creation FSM ---
async def start_ad_creation(message: Message, state: FSMContext):
    await message.answer("Perfetto! **Inviami una foto con una breve descrizione nella didascalia**.", parse_mode="Markdown")
    await state.set_state(AdCreation.WAITING_PHOTO)

@router.message(AdCreation.WAITING_PHOTO, F.photo)
async def ad_creation_photo_handler(message: Message, state: FSMContext):
    if not message.caption:
        await message.answer("Per favore, invia la foto con una **didascalia**.")
        return

    processing_msg = await message.answer("✍️ Analizzo la tua foto con l'IA...")
    try:
        photo_file = await message.bot.get_file(message.photo[-1].file_id)
        photo_bytes = await message.bot.download_file(photo_file.file_path)
        ai_result = await ad_text_generator(message.caption, photo_bytes.read())

        if isinstance(ai_result, dict):
            await processing_msg.edit_text(f"❌ Errore IA: {ai_result['description']}")
            await state.clear()
            return
        
        await db.deduct_credits(message.from_user.id, 1) # Deduct credit on successful generation
        
        await state.update_data(draft_title=ai_result.title, draft_description=ai_result.description, draft_price=ai_result.price, input_description=message.caption)
        
        preview_text = f"✨ **Ecco la tua anteprima!** ✨\n\n**Titolo:**\n{ai_result.title}\n\n**Descrizione:**\n{ai_result.description}\n\n**Prezzo Suggerito:** {ai_result.price} €"
        await processing_msg.edit_text(preview_text, parse_mode="Markdown", reply_markup=kb.get_confirmation_kb("creation", 0))
        await state.set_state(AdCreation.WAITING_CONFIRM)
    except Exception as e:
        logging.error(f"Error in ad_creation_photo_handler: {e}")
        await processing_msg.edit_text("Si è verificato un errore critico. Riprova.")
        await state.clear()

# Handler for Manual Edit (Creation Phase)
@router.callback_query(AdCreation.WAITING_CONFIRM, F.data == "edit_creation_start")
async def ad_creation_manual_edit_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✏️ Inviami la nuova descrizione completa per l'annuncio.")
    await state.set_state(AdCreation.WAITING_MANUAL_TEXT)
    await callback.answer()

@router.message(AdCreation.WAITING_MANUAL_TEXT, F.text)
async def ad_creation_manual_edit_save(message: Message, state: FSMContext):
    # Update description, keep title/price from previous draft or ask? 
    # Simpler: just update description for now as it's the most common edit.
    await state.update_data(draft_description=message.text)
    data = await state.get_data()
    
    preview_text = f"✨ **Anteprima Aggiornata** ✨\n\n**Titolo:**\n{data.get('draft_title')}\n\n**Descrizione:**\n{data.get('draft_description')}\n\n**Prezzo Suggerito:** {data.get('draft_price')} €"
    await message.answer(preview_text, parse_mode="Markdown", reply_markup=kb.get_confirmation_kb("creation", 0))
    await state.set_state(AdCreation.WAITING_CONFIRM)

@router.callback_query(AdCreation.WAITING_CONFIRM, F.data.startswith("confirm_creation"))
async def ad_creation_ask_category(callback: CallbackQuery, state: FSMContext):
    # Init schedule list
    await state.update_data(schedule_list=[])
    
    await callback.message.edit_text("✅ Testo confermato! Ora scegli una categoria:", reply_markup=None)
    categories = await db.get_all_categories()
    await callback.message.answer("Scegli una categoria:", reply_markup=kb.get_categories_kb(categories))
    await state.set_state(AdCreation.WAITING_CATEGORY)
    await callback.answer()

@router.callback_query(AdCreation.WAITING_CATEGORY, F.data.startswith("cat:"))
async def ad_creation_start_platform_loop(callback: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(callback.data.split(":")[1]))
    await callback.message.edit_text("✅ Categoria scelta!", reply_markup=None)
    
    # Start Platform Loop
    platforms = await db.get_all_platforms()
    await callback.message.answer(
        "Su quali piattaforme vuoi pubblicare?\nSeleziona una piattaforma, imposta la data, e ripeti per aggiungerne altre.",
        reply_markup=kb.get_multi_platform_kb(platforms)
    )
    await state.set_state(AdCreation.WAITING_PLATFORM_SELECTION)
    await callback.answer()

@router.callback_query(AdCreation.WAITING_PLATFORM_SELECTION, F.data.startswith("platform:"))
async def ad_creation_platform_selected(callback: CallbackQuery, state: FSMContext):
    platform_id = int(callback.data.split(":")[1])
    
    await state.update_data(current_platform_id=platform_id)
    await callback.message.edit_text(
        f"📅 Quando vuoi pubblicare su questa piattaforma?\n\n"
        "Scrivimi una data e ora (es. 'domani alle 18:30').\n"
        "💡 **Orari consigliati:** 10:00-12:00 o 18:00-21:00.",
        reply_markup=None
    )
    await state.set_state(AdCreation.WAITING_DATE_INPUT)
    await callback.answer()

@router.message(AdCreation.WAITING_DATE_INPUT, F.text)
async def ad_creation_date_selected(message: Message, state: FSMContext):
    parsed_date = parse_date_text(message.text)
    if not parsed_date:
        await message.answer("⚠️ Data non valida. Riprova (es. 'domani 18:00').")
        return

    data = await state.get_data()
    schedule_list = data.get('schedule_list', [])
    current_platform_id = data.get('current_platform_id')
    
    # Add to list
    schedule_list.append({'platform_id': current_platform_id, 'date': parsed_date})
    await state.update_data(schedule_list=schedule_list)
    
    # Show Platform Menu Again
    platforms = await db.get_all_platforms()
    await message.answer(
        f"✅ Programmato per il {parsed_date.strftime('%d/%m %H:%M')}.\n\n"
        "Vuoi aggiungere un'altra piattaforma o concludere?",
        reply_markup=kb.get_multi_platform_kb(platforms)
    )
    await state.set_state(AdCreation.WAITING_PLATFORM_SELECTION)

@router.callback_query(AdCreation.WAITING_PLATFORM_SELECTION, F.data == "finish_platform_selection")
async def ad_creation_finish(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    schedule_list = data.get('schedule_list', [])
    
    if not schedule_list:
        await callback.answer("⚠️ Seleziona almeno una piattaforma!", show_alert=True)
        return

    await callback.message.edit_text("💾 Salvataggio in corso...", reply_markup=None)
    
    try:
        # 1. Save Ad
        ad_id = await db.add_ad(
            id_telegram_user=callback.from_user.id,
            input_description=data['input_description'],
            generated_title=data['draft_title'],
            generated_description=data['draft_description'],
            suggested_price=data['draft_price'],
            id_category=data.get('category_id')
        )
        
        # 2. Save Publications
        scheduled_status_id = await db.get_status_id_by_name('SCHEDULED')
        
        for item in schedule_list:
            await db.add_publication_entry(
                id_ad=ad_id,
                id_platform=item['platform_id'],
                id_status_type=scheduled_status_id,
                scheduled_datetime=item['date']
            )
            
        await callback.message.answer(
            f"🎉 **Annuncio #{ad_id} Creato con Successo!**\n"
            f"Programmato su {len(schedule_list)} piattaforme.\n"
            "Lo trovi in '🛍️ I Miei Annunci'.",
            reply_markup=kb.get_main_menu(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logging.error(f"Error finalizing ad creation: {e}")
        await callback.message.answer("❌ Errore durante il salvataggio. Riprova.")
    finally:
        await state.clear()
        await callback.answer()


# --- 2. Ad Listing and Management ---
@router.message(F.text == "🛍️ I Miei Annunci", StateFilter(None))
async def my_ads_handler(message: Message):
    user_ads = await db.get_user_ads(message.from_user.id, limit=20)
    if not user_ads:
        await message.answer("Nessun annuncio creato. Inizia con '🆕 Crea Annuncio'!")
        return
    await message.answer(f"Ecco i tuoi {len(user_ads)} annunci più recenti:")
    for ad in user_ads:
        status_map = {
            'DRAFT': 'Bozza',
            'SCHEDULED': 'Programmato',
            'READY': 'Pronto',
            'PUBLISHED': 'Pubblicato',
            'SOLD': 'Venduto',
            'DELETED': 'Eliminato'
        }
        raw_status = ad.get('status_name', 'DRAFT')
        status = status_map.get(raw_status, raw_status)
        
        ad_text = f"🏷️ **{ad['generated_title']}**\nID: `{ad['id_ad']}` | Stato: `{status}`"
        await message.answer(ad_text, parse_mode="Markdown", reply_markup=kb.get_ad_manage_kb(ad['id_ad'], raw_status)) # Pass raw status for logic
        await asyncio.sleep(0.1)

# --- 3. Ad Editing FSM ---
@router.callback_query(F.data.startswith("edit_ad:"))
async def edit_ad_start(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    await state.update_data(ad_id_to_edit=ad_id)
    await callback.message.edit_text(f"Cosa vuoi modificare per l'annuncio #{ad_id}?", reply_markup=kb.get_edit_menu_kb(ad_id))
    await state.set_state(AdEditing.CHOOSING_FIELD)
    await callback.answer()

@router.callback_query(AdEditing.CHOOSING_FIELD, F.data.startswith("edit_field_"))
async def edit_field_ask_new_value(callback: CallbackQuery, state: FSMContext):
    field_to_edit = callback.data.split(":")[0].split("_")[-1]
    await state.update_data(field_to_edit=field_to_edit)
    await callback.message.edit_text(f"OK, inviami il nuovo valore per **{field_to_edit.capitalize()}**.")
    await state.set_state(AdEditing.WAITING_NEW_VALUE)
    await callback.answer()

@router.message(AdEditing.WAITING_NEW_VALUE, F.text)
async def edit_field_save_new_value(message: Message, state: FSMContext):
    """
    Saves the new value for the field being edited, with added validation for price.
    """
    data = await state.get_data()
    field = data['field_to_edit']
    ad_id = data['ad_id_to_edit']
    new_value = message.text

    try:
        if field == 'price':
            price = float(new_value.replace(',', '.'))
            update_data = {"suggested_price": price}
        else:
            # For fields like 'title' and 'description'
            update_data = {f"generated_{field}": new_value}

        await db.update_ad_details(ad_id, message.from_user.id, **update_data)
        await message.answer(f"✅ {field.capitalize()} aggiornato!", reply_markup=kb.get_edit_menu_kb(ad_id))
        await state.set_state(AdEditing.CHOOSING_FIELD)

    except ValueError:
        # If price conversion fails
        await message.answer("❌ Prezzo non valido. Inserisci un numero (es. 12.50).")
        # Do not change state, allowing the user to retry
    except Exception as e:
        logging.error(f"Error updating field {field} for ad {ad_id}: {e}")
        await message.answer("Si è verificato un errore durante l'aggiornamento. Riprova.")
        await state.clear()

@router.callback_query(AdEditing.CHOOSING_FIELD, F.data.startswith("finish_edit:"))
async def edit_ad_finish(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    await state.clear()
    await callback.message.edit_text(f"✅ Modifiche all'annuncio #{ad_id} completate.")
    await callback.message.answer("Sei nel menu principale.", reply_markup=kb.get_main_menu())
    await callback.answer()

# --- 4. Mark as Sold FSM ---
@router.message(F.text == "✅ Segna Venduto", StateFilter(None))
async def start_sell_ad_wizard(message: Message, state: FSMContext):
    ads = await db.get_non_sold_ads(message.from_user.id)
    if not ads:
        await message.answer("Nessun annuncio attivo da segnare come venduto.")
        return
    builder = InlineKeyboardBuilder()
    for ad in ads:
        builder.button(text=f"#{ad['id_ad']} - {ad['generated_title']}", callback_data=f"sell_select:{ad['id_ad']}")
    builder.adjust(1)
    await message.answer("Quale annuncio hai venduto?", reply_markup=builder.as_markup())
    await state.set_state(AdSelling.WAITING_AD_SELECTION)

@router.callback_query(AdSelling.WAITING_AD_SELECTION, F.data.startswith("sell_select:"))
async def sell_ad_ask_price(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    pub_id = await db.get_latest_publication_id_for_ad(ad_id)
    if not pub_id:
        await callback.message.edit_text("Errore: Impossibile segnare come venduto un annuncio che non è mai stato pubblicato/schedulato.", reply_markup=None)
        await state.clear()
        return
    await state.update_data(pub_id_to_sell=pub_id)
    await callback.message.edit_text(f"A che prezzo hai venduto l'annuncio #{ad_id}?")
    await state.set_state(AdSelling.WAITING_PRICE)
    await callback.answer()

@router.message(AdSelling.WAITING_PRICE, F.text)
async def sell_ad_save(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(',', '.'))
        data = await state.get_data()
        await db.mark_publication_as_sold(data['pub_id_to_sell'], price)
        await message.answer(f"🎉 Congratulazioni! Annuncio segnato come venduto a {price}€.")
    except (ValueError, KeyError):
        await message.answer("Prezzo non valido. Inserisci solo un numero.")
        return
    finally:
        await state.clear()

# --- 5. Delete Ad FSM ---
@router.callback_query(F.data.startswith("delete_ad:"))
async def delete_ad_confirm(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    await state.update_data(ad_id_to_delete=ad_id)
    await callback.message.edit_text(f"Sei sicuro di voler eliminare l'annuncio #{ad_id}?", reply_markup=kb.get_confirmation_kb("delete", ad_id))
    await state.set_state(AdDeleting.WAITING_CONFIRMATION)
    await callback.answer()

@router.callback_query(AdDeleting.WAITING_CONFIRMATION, F.data.startswith("confirm_delete:"))
async def delete_ad_execute(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ad_id = data['ad_id_to_delete']
    pub_id = await db.get_latest_publication_id_for_ad(ad_id)
    if pub_id:
        await db.mark_publication_as_deleted(pub_id)
        await callback.message.edit_text(f"🗑️ Annuncio #{ad_id} eliminato.")
    else: # If no publication, we might need a way to delete the ad itself, this is a logic gap. For now, we assume it has a pub.
        await callback.message.edit_text("Impossibile eliminare, nessuna pubblicazione trovata.")
    await state.clear()
    await callback.answer()

# --- 6. Stats Handler ---
@router.message(F.text == "📊 Statistiche", StateFilter(None))
async def stats_handler(message: Message):
    await message.answer("📊 Sto generando le tue statistiche...")
    stats = await db.get_advanced_stats(message.from_user.id)
    chart_data = await db.get_category_chart_data(message.from_user.id)
    
    report = (f"--- **Panoramica** ---\n"
              f"• Annunci Totali: **{stats['totale_annunci']}**\n"
              f"• Annunci Venduti: **{stats['totale_vendite']}**\n\n"
              f"--- **Guadagni** 💰 ---\n"
              f"• Guadagno Totale: **{stats['guadagno_totale']:.2f} €**\n"
              f"• Stima Guadagno Futuro: **{stats['stima_guadagno_futuro']:.2f} €**\n")
    
    chart_buf = generate_pie_chart(chart_data)
    if chart_buf:
        await message.answer_photo(photo=BufferedInputFile(chart_buf.read(), "sales.png"), caption=report, parse_mode="Markdown")
    else:
        await message.answer(report, parse_mode="Markdown")

# --- 4. HANDLER DI ANNULLAMENTO GLOBALE (NUOVA SEZIONE) ---
@router.callback_query(F.data.startswith("cancel_"))
async def universal_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """
    A universal handler to cancel any FSM state and clean up the conversation.
    """
    current_state = await state.get_state()
    if current_state is not None:
        logging.info(f"Cancelling state {current_state} via cancel button.")
        await state.clear()
        await callback.message.edit_text("Operazione annullata.", reply_markup=None)
    else:
        # If no state is active, just remove the inline keyboard
        await callback.message.edit_text(callback.message.text, reply_markup=None)
        
    await callback.answer("Annullato.")


# --- 5. VISUALIZZAZIONE DETTAGLI ANNUNCIO (NUOVA SEZIONE) ---
@router.callback_query(F.data.startswith("view_details:"))
async def view_ad_details_handler(callback: CallbackQuery, state: FSMContext):
    """
    Displays the full details of a specific ad.
    This handler assumes a "ℹ️ Dettagli" button exists in the ad management keyboard.
    """
    await state.clear()  # Clear any active state to prevent conflicts
    ad_id = int(callback.data.split(":")[1])

    try:
        ad_details = await db.get_ad_details(ad_id, callback.from_user.id)
        if not ad_details:
            await callback.answer("❌ Annuncio non trovato o non di tua proprietà.", show_alert=True)
            return

        def format_dt(dt_str: str | None) -> str:
            """Safely formats a datetime string from the DB for display."""
            if not dt_str: return "Non impostata"
            try:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y alle %H:%M')
            except (ValueError, TypeError):
                return "Data non valida"

        # Translation Map
        status_map = {
            'DRAFT': 'Bozza',
            'SCHEDULED': 'Programmato',
            'READY': 'Pronto',
            'PUBLISHED': 'Pubblicato',
            'SOLD': 'Venduto',
            'DELETED': 'Eliminato'
        }
        
        raw_status = ad_details.get('status_name', 'DRAFT')
        status = status_map.get(raw_status, raw_status) # Fallback to raw if not found
        
        price = f"{ad_details.get('suggested_price'):.2f} €" if ad_details.get('suggested_price') is not None else "Non impostato"

        details_text = (
            f"ℹ️ **Scheda Annuncio #{ad_id}**\n\n"
            f"**Titolo:**\n{ad_details.get('generated_title', 'N/A')}\n\n"
            f"**Descrizione:**\n{ad_details.get('generated_description', 'N/A')}\n\n"
            f"--- **Dettagli** ---\n"
            f"**Stato:** `{status}`\n"
            f"**Prezzo Suggerito:** {price}\n"
            f"**Categoria:** {ad_details.get('category_name', 'N/A')}\n\n"
            f"--- **Cronologia** ---\n"
            f"**Creato il:** {format_dt(ad_details.get('created_datetime'))}\n"
            f"**Programmato per il:** {format_dt(ad_details.get('scheduled_datetime'))}\n"
            f"**Venduto il:** {format_dt(ad_details.get('sold_datetime'))}"
        )

        # We keep the same keyboard so the user can continue managing the ad
        await callback.message.edit_text(
            details_text,
            reply_markup=callback.message.reply_markup,
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logging.error(f"Error in view_ad_details_handler for ad {ad_id}: {e}")
        await callback.answer("Si è verificato un errore nel recupero dei dettagli.", show_alert=True)


# --- 6. LOGICA PUBBLICAZIONE BOZZA (NUOVA SEZIONE) ---
@router.callback_query(StateFilter(None), F.data.startswith("publish_ad:"))
async def publish_ad_start(callback: CallbackQuery, state: FSMContext):
    """
    Starts the process of publishing a draft ad by asking for a date.
    """
    ad_id = int(callback.data.split(":")[1])
    await state.update_data(ad_id_to_publish=ad_id)
    
    await callback.message.edit_text(
        f"🗓️ Quando vuoi pubblicare l'annuncio #{ad_id}?\n\n"
        "Scrivimi una data (es. 'domani alle 15:00') o 'subito'.",
        reply_markup=kb.get_confirmation_kb("publishing", ad_id)
    )
    await state.set_state(AdPublishing.WAITING_DATE)
    await callback.answer()

@router.message(AdPublishing.WAITING_DATE, F.text)
async def publish_ad_set_date(message: Message, state: FSMContext):
    """
    Receives the date, updates the publication entry to 'SCHEDULED' in the database.
    """
    data = await state.get_data()
    ad_id = data['ad_id_to_publish']

    if message.text.lower() == 'subito':
        parsed_date = datetime.now()
    else:
        parsed_date = parse_date_text(message.text)

    if not parsed_date:
        await message.answer("Non ho capito la data. 😅 Riprova (es. 'domani alle 15:00' o 'subito').")
        return

    try:
        pub_id = await db.get_latest_publication_id_for_ad(ad_id)
        if not pub_id:
            raise ValueError("Impossibile trovare una pubblicazione associata a questa bozza.")

        scheduled_status_id = await db.get_status_id_by_name('SCHEDULED')
        if not scheduled_status_id:
            raise ValueError("Stato 'SCHEDULED' non trovato nel database.")

        # This part requires a method to update scheduling details, which is missing
        # from the public API of DatabaseManager. A direct query is used as a workaround.
        conn = await db._get_connection()
        await conn.execute(
            "UPDATE publication_ad SET scheduled_datetime = ?, id_status_type = ? WHERE id_publication_ad = ?",
            (parsed_date.strftime("%Y-%m-%d %H:%M:%S"), scheduled_status_id, pub_id)
        )
        await conn.commit()

        await message.answer(f"✅ Annuncio #{ad_id} programmato per il {parsed_date.strftime('%d/%m/%Y alle %H:%M')}!", reply_markup=kb.get_main_menu())

    except Exception as e:
        logging.error(f"Failed to schedule ad {ad_id}: {e}")
        await message.answer(f"Si è verificato un errore durante la programmazione: {e}")
    finally:
        await state.clear()
