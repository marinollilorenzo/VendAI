import asyncio
import logging
import io
from aiogram import Router, F, types
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
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
    WAITING_EDIT_CHOICE = State() # Showing the edit menu during creation
    WAITING_EDIT_VALUE = State() # Waiting for new value during creation

class AdEditing(StatesGroup):
    CHOOSING_FIELD = State()
    WAITING_NEW_VALUE = State()

class AdSelling(StatesGroup):
    WAITING_AD_SELECTION = State()
    WAITING_PLATFORM = State()
    WAITING_PRICE = State()
class AdDeleting(StatesGroup):
    WAITING_CONFIRMATION = State()

# --- 1. 🧩 NUOVO STATO FSM ---
# Aggiungere questa classe insieme alle altre definizioni di StatesGroup
class AdPublishing(StatesGroup):
    WAITING_DATE = State()


# --- Helper Functions ---
async def clear_previous_ads_messages(state: FSMContext, bot, chat_id, keep_message_id: int = None):
    """
    Recupera la lista dei messaggi degli annunci salvati nello stato ed elimina tutti quelli
    che non corrispondono a keep_message_id.
    """
    data = await state.get_data()
    msg_ids = data.get('ad_message_ids', [])
    
    for msg_id in msg_ids:
        if keep_message_id and msg_id == keep_message_id:
            continue # Salta quello che vogliamo tenere visibile
        
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            # Ignora errori (es. messaggio già cancellato o troppo vecchio)
            pass
            
    # Aggiorniamo la lista nello stato: se ne abbiamo tenuto uno, rimane solo quello
    if keep_message_id:
        await state.update_data(ad_message_ids=[keep_message_id])
    else:
        await state.update_data(ad_message_ids=[])

async def clear_previous_menu_message(state: FSMContext, bot, chat_id):
    """
    Cancella l'ultimo messaggio di menu (Profilo, Abbonamenti, Stats) salvato nello stato.
    """
    data = await state.get_data()
    last_menu_id = data.get('last_menu_msg_id')
    
    if last_menu_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_menu_id)
        except Exception:
            pass # Già cancellato o troppo vecchio
            
    # Rimuoviamo l'ID dallo stato per pulizia
    await state.update_data(last_menu_msg_id=None)
    
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
    # 1. Pulizia Totale: Cancelliamo eventuali liste di annunci aperte
    await clear_previous_ads_messages(state, message.bot, message.chat.id)
    
    current_state = await state.get_state()
    if current_state is not None:
        logging.info(f"Cancelling state {current_state} due to menu navigation.")
        await state.clear()
        # Feedback visivo
        await message.answer("", reply_markup=kb.get_main_menu())

    # Route to the correct handler - ASSICURATI DI PASSARE 'state' A TUTTI
    if message.text == "🆕 Crea Annuncio":
        await start_ad_creation(message, state)
    elif message.text == "🛍️ I Miei Annunci":
        await my_ads_handler(message, state) 
    elif message.text == "✅ Segna Venduto":
        await start_sell_ad_wizard(message, state)
    elif message.text == "📊 Statistiche":
        await stats_handler(message, state) 
    elif message.text == "💎 Abbonamenti":
        await subscription_handler(message, state) 
    elif message.text == "👤 Profilo":
        await profile_handler(message, state)
    elif message.text == "❓ Aiuto":
        await start_handler(message, state)
        
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
async def profile_handler(message: Message, state: FSMContext): # Aggiungi state=None
    # 1. Pulizia: Cancelliamo menu precedenti (e anche la lista annunci se c'era)
    if state:
        await clear_previous_ads_messages(state, message.bot, message.chat.id)
        await clear_previous_menu_message(state, message.bot, message.chat.id)

    credits = await db.get_user_credits(message.from_user.id)
    
    # 2. Invio Nuovo Messaggio
    sent_msg = await message.answer(
        f"👤 **Profilo Utente**\n\nID: `{message.from_user.id}`\nCrediti: **{credits}** 💎",
        reply_markup=kb.get_profile_kb(), parse_mode="Markdown"
    )
    
    # 3. Salvataggio ID
    if state:
        await state.update_data(last_menu_msg_id=sent_msg.message_id)

@router.message(F.text == "💎 Abbonamenti", StateFilter(None))
async def subscription_handler(message: Message, state: FSMContext):
    if state:
        await clear_previous_ads_messages(state, message.bot, message.chat.id)
        await clear_previous_menu_message(state, message.bot, message.chat.id)

    mock_plans = [{"id_account_type": 2, "name": "Pro", "price_euro": 2.99}, {"id_account_type": 3, "name": "Ultimate", "price_euro": 4.99}]
    
    sent_msg = await message.answer("Scegli un piano:", reply_markup=kb.get_subscription_kb(mock_plans))
    
    if state:
        await state.update_data(last_menu_msg_id=sent_msg.message_id)

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
async def edit_creation_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Cosa vuoi modificare?", reply_markup=kb.get_edit_menu_kb(0)) # 0 as dummy ID
    await state.set_state(AdCreation.WAITING_EDIT_CHOICE)
    await callback.answer()

@router.callback_query(AdCreation.WAITING_EDIT_CHOICE, F.data.startswith("edit_field_"))
async def edit_creation_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[0].split("_")[-1] # title, description, price
    await state.update_data(field_to_edit=field)
    
    # Recuperiamo i dati attuali dallo stato per pre-compilare il tasto
    data = await state.get_data()
    current_value = ""
    if field == 'title':
        current_value = data.get('draft_title', '')
    elif field == 'description':
        current_value = data.get('draft_description', '')
    elif field == 'price':
        current_value = str(data.get('draft_price', ''))

    # Traduzione etichetta
    field_map = {"title": "Titolo", "description": "Descrizione", "price": "Prezzo"}
    field_label = field_map.get(field, field.capitalize())
    
    # Costruiamo la tastiera con il pulsante "Copia vecchio valore"
    builder = InlineKeyboardBuilder()
    if current_value:
        # switch_inline_query_current_chat inserisce il testo nella barra di input dell'utente
        builder.button(
            text=f"✏️ Copia e modifica attuale", 
            switch_inline_query_current_chat=str(current_value)
        )
    
    await callback.message.delete() # Puliamo il menu precedente per ordine
    await callback.message.answer(
        f"Inviami il nuovo valore per **{field_label}**.\n"
        "👇 Premi il tasto sotto per modificare quello esistente senza riscriverlo.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdCreation.WAITING_EDIT_VALUE)
    await callback.answer()

@router.message(AdCreation.WAITING_EDIT_VALUE, F.text)
async def save_creation_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field_to_edit']
    value = message.text
    
    # PULIZIA: Rimuoviamo il tag del bot se l'utente ha usato il tasto rapido
    bot_user = await message.bot.get_me()
    bot_mention = f"@{bot_user.username}"
    if value.startswith(bot_mention):
        value = value.replace(bot_mention, "").strip()

    key = None
    if field == 'price':
        try:
            # Sostituisce virgola con punto e converte
            value = float(value.replace(',', '.'))
            key = 'draft_price'
        except:
            await message.answer("❌ Prezzo non valido. Inserisci un numero (es. 12.50).")
            return
    elif field == 'title':
        key = 'draft_title'
    elif field == 'description':
        key = 'draft_description'
        
    if key:
        await state.update_data({key: value})
    
    await message.answer("✅ Modificato!", reply_markup=kb.get_edit_menu_kb(0)) # 0 è dummy ID
    await state.set_state(AdCreation.WAITING_EDIT_CHOICE)

@router.callback_query(AdCreation.WAITING_EDIT_CHOICE, F.data.startswith("finish_edit:"))
async def finish_creation_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    preview_text = f"✨ **Ecco la tua anteprima!** ✨\n\n**Titolo:**\n{data.get('draft_title')}\n\n**Descrizione:**\n{data.get('draft_description')}\n\n**Prezzo Suggerito:** {data.get('draft_price')} €"
    await callback.message.edit_text(preview_text, parse_mode="Markdown", reply_markup=kb.get_confirmation_kb("creation", 0))
    await state.set_state(AdCreation.WAITING_CONFIRM)
    await callback.answer()

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
async def my_ads_handler(message: Message, state: FSMContext = None): 
    # NOTA: ho aggiunto state=None opzionale per compatibilità, ma router passerà lo stato
    
    # 1. Recupero utente e gestione compatibilità (se chiamato da callback o message)
    user_id = message.from_user.id
    chat_id = message.chat.id
    bot = message.bot
    
    # Se ci viene passato lo stato, facciamo pulizia preventiva della vecchia lista
    if state:
        await clear_previous_ads_messages(state, bot, chat_id)
    
    # 2. Query Database (ordinata con priorità)
    user_ads = await db.get_user_ads(user_id, limit=10)
    user_ads = [ad for ad in user_ads if ad.get('status_name') != 'DELETED']

    if not user_ads:
        await message.answer("Nessun annuncio attivo. Inizia con '🆕 Crea Annuncio'!")
        if state: await state.update_data(ad_message_ids=[])
        return

    # 3. Invio messaggi e tracciamento ID
    await message.answer(f"📂 **I Miei Annunci** ({len(user_ads)})")
    
    new_msg_ids = [] # Lista per tracciare i nuovi messaggi
    
    for ad in user_ads:
        status_map = {
            'DRAFT': 'Bozza', 'SCHEDULED': 'Programmato', 'READY': 'Pronto',
            'PUBLISHED': 'Pubblicato', 'SOLD': 'Venduto', 'DELETED': 'Eliminato'
        }
        raw_status = ad.get('status_name', 'DRAFT')
        status = status_map.get(raw_status, raw_status)
        
        ad_text = f"🏷️ **{ad['generated_title']}**\nID: `{ad['id_ad']}` | Stato: `{status}`"
        
        sent_msg = await message.answer(
            ad_text, 
            parse_mode="Markdown", 
            reply_markup=kb.get_ad_manage_kb(ad['id_ad'], raw_status)
        )
        new_msg_ids.append(sent_msg.message_id)
        await asyncio.sleep(0.1)
        
    # 4. Salviamo gli ID nello stato per poterli cancellare dopo
    if state:
        await state.update_data(ad_message_ids=new_msg_ids)
# --- 3. Ad Editing FSM ---
@router.callback_query(F.data.startswith("edit_ad:"))
async def edit_ad_start(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    await state.update_data(ad_id_to_edit=ad_id)
    
    # --- AUTO-PULIZIA: FOCUS MODE ---
    # Cancelliamo tutti gli altri annunci dalla chat, tenendo solo questo
    await clear_previous_ads_messages(
        state, 
        callback.bot, 
        callback.message.chat.id, 
        keep_message_id=callback.message.message_id
    )
    
    # Modifichiamo l'unico messaggio rimasto
    await callback.message.edit_text(
        f"✏️ **Modifica Annuncio #{ad_id}**\n"
        "Cosa vuoi cambiare?", 
        reply_markup=kb.get_edit_menu_kb(ad_id)
    )
    await state.set_state(AdEditing.CHOOSING_FIELD)
    await callback.answer()
    
@router.callback_query(AdEditing.CHOOSING_FIELD, F.data.startswith("edit_field_"))
async def edit_field_ask_new_value(callback: CallbackQuery, state: FSMContext):
    field_to_edit = callback.data.split(":")[0].split("_")[-1]
    await state.update_data(field_to_edit=field_to_edit)
    
    # Recuperiamo l'ID annuncio dallo stato
    data = await state.get_data()
    ad_id = data.get('ad_id_to_edit')

    # Recuperiamo il valore ATTUALE dal database per pre-compilarlo
    current_value = ""
    try:
        ad_details = await db.get_ad_details(ad_id, callback.from_user.id)
        if ad_details:
            if field_to_edit == 'title':
                current_value = ad_details.get('generated_title', '')
            elif field_to_edit == 'description':
                current_value = ad_details.get('generated_description', '')
            elif field_to_edit == 'price':
                current_value = str(ad_details.get('suggested_price', ''))
    except Exception as e:
        logging.error(f"Errore recupero valore attuale edit: {e}")

    # Traduzione
    field_map = {"title": "Titolo", "description": "Descrizione", "price": "Prezzo"}
    field_label = field_map.get(field_to_edit, field_to_edit.capitalize())
    
    # Costruiamo il bottone magico
    builder = InlineKeyboardBuilder()
    if current_value:
        builder.button(
            text="✏️ Copia e modifica attuale", 
            switch_inline_query_current_chat=str(current_value)
        )

    await callback.message.delete()
    await callback.message.answer(
        f"OK, inviami il nuovo valore per **{field_label}**.\n"
        "👇 Usa il tasto per modificare il testo attuale.",
        reply_markup=builder.as_markup()
    )
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

    # PULIZIA: Rimuoviamo il tag del bot se l'utente ha usato il tasto rapido
    bot_user = await message.bot.get_me()
    bot_mention = f"@{bot_user.username}"
    if new_value.startswith(bot_mention):
        new_value = new_value.replace(bot_mention, "").strip()

    try:
        update_data = {}
        if field == 'price':
            price = float(new_value.replace(',', '.'))
            update_data = {"suggested_price": price}
        else:
            # For fields like 'title' and 'description'
            # Mappa i campi FSM ai nomi colonne DB corretti
            db_field = "generated_title" if field == 'title' else "generated_description"
            update_data = {db_field: new_value}
        await db.update_ad_details(ad_id, message.from_user.id, **update_data)
        label_map = {
            "title": "Titolo",
            "description": "Descrizione",
            "price": "Prezzo"
        }
        field_label = label_map.get(field, field.capitalize()) # Fallback se non trova la chiave

        await message.answer(f"✅ **{field_label}** aggiornato!", reply_markup=kb.get_edit_menu_kb(ad_id), parse_mode="Markdown")
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
    
    # 1. Pulizia: Cancelliamo il menu di modifica
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass 

    # 2. Feedback
    await callback.answer("✅ Modifiche salvate!")

    # 3. Recupero Dati Utente
    user_id = callback.from_user.id
    user_ads = await db.get_user_ads(user_id, limit=10)
    user_ads = [ad for ad in user_ads if ad.get('status_name') != 'DELETED']

    if not user_ads:
        await callback.message.answer("Nessun annuncio attivo. Inizia con '🆕 Crea Annuncio'!")
        return

    # 4. Ristampa con TRACCIAMENTO ID (Il Fix è qui)
    await callback.message.answer(f"📂 **I Miei Annunci** ({len(user_ads)})")
    
    new_msg_ids = [] # Lista per salvare i nuovi messaggi
    
    for ad in user_ads:
        status_map = {
            'DRAFT': 'Bozza', 'SCHEDULED': 'Programmato', 'READY': 'Pronto',
            'PUBLISHED': 'Pubblicato', 'SOLD': 'Venduto', 'DELETED': 'Eliminato'
        }
        raw_status = ad.get('status_name', 'DRAFT')
        status = status_map.get(raw_status, raw_status)
        
        ad_text = f"🏷️ **{ad['generated_title']}**\nID: `{ad['id_ad']}` | Stato: `{status}`"
        
        sent_msg = await callback.message.answer(
            ad_text, 
            parse_mode="Markdown", 
            reply_markup=kb.get_ad_manage_kb(ad['id_ad'], raw_status)
        )
        new_msg_ids.append(sent_msg.message_id) # Salviamo l'ID!
        await asyncio.sleep(0.1)

    # 5. Aggiorniamo lo stato con i nuovi ID per poterli cancellare in futuro
    await state.update_data(ad_message_ids=new_msg_ids)
    
@router.callback_query(F.data.startswith("sell_ad:"))
async def sell_ad_inline_start(callback: CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    await state.update_data(ad_id_to_sell=ad_id)

    # 1. Recuperiamo le piattaforme attive per questo annuncio
    active_platforms = await db.get_ad_active_platforms(ad_id)
    
    # 2. Costruiamo la tastiera di scelta
    builder = InlineKeyboardBuilder()
    
    # Aggiungiamo un bottone per ogni piattaforma attiva
    for p in active_platforms:
        builder.button(text=f"🌐 {p['name']}", callback_data=f"sold_on:{p['id_platform']}")
    
    # Aggiungiamo sempre l'opzione "Privatamente / Altro"
    builder.button(text="🤝 Privatamente / Altro", callback_data="sold_on:0")
    
    builder.adjust(1) # Una per riga per chiarezza

    # 3. Pulizia chat (Focus Mode)
    await clear_previous_ads_messages(state, callback.bot, callback.message.chat.id, keep_message_id=callback.message.message_id)

    await callback.message.edit_text(
        f"🎉 Ottimo! Dove hai venduto l'annuncio #{ad_id}?",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AdSelling.WAITING_PLATFORM)
    await callback.answer()


@router.callback_query(AdSelling.WAITING_PLATFORM, F.data.startswith("sold_on:"))
async def sell_ad_platform_selected(callback: CallbackQuery, state: FSMContext):
    # 1. Estraiamo l'ID della piattaforma dal bottone premuto
    platform_id = int(callback.data.split(":")[1])
    await state.update_data(sold_platform_id=platform_id)
    
    # 2. Recuperiamo il nome "Bello" per il messaggio
    # Default: Se l'ID è 0 o nullo, assumiamo sia una vendita privata
    display_text = "Privatamente" 

    if platform_id > 0:
        try:
            # Facciamo una query rapida per ottenere il nome (es. "Vinted", "Wallapop")
            # Nota: Usiamo _fetch_one che è disponibile nella tua classe DatabaseManager
            query = "SELECT name FROM platform WHERE id_platform = ?"
            result = await db._fetch_one(query, (platform_id,))
            
            if result:
                # Costruiamo la frase: "su Vinted"
                display_text = f"su {result['name']}"
            else:
                display_text = "sulla piattaforma" # Fallback se non trova il nome
        except Exception:
            display_text = "sulla piattaforma"

    # 3. Modifichiamo il messaggio chiedendo il prezzo
    await callback.message.edit_text(
        f"💰 A che prezzo l'hai venduto **{display_text}**?\n\n"
        "Scrivi la cifra (es. 25.00):",
        reply_markup=None,
        parse_mode="Markdown"
    )
    
    # Passiamo allo stato di attesa prezzo
    await state.set_state(AdSelling.WAITING_PRICE)
    await callback.answer()

@router.message(AdSelling.WAITING_PRICE, F.text)
async def sell_ad_save(message: Message, state: FSMContext):
    try:
        # Pulizia input prezzo
        price_text = message.text.replace(',', '.').replace('€', '').strip()
        price = float(price_text)
        
        data = await state.get_data()
        ad_id = data['ad_id_to_sell']
        platform_id = data['sold_platform_id']
        
        # CHIAMATA AL DB AGGIORNATA
        await db.finalize_sale(ad_id, platform_id, price)
        
        # Feedback finale e pulizia
        # Recuperiamo il messaggio del menu (che era editato per chiedere il prezzo) e lo eliminiamo o aggiorniamo
        # Se vogliamo pulizia totale:
        await clear_previous_ads_messages(state, message.bot, message.chat.id)
        
        await message.answer(
            f"✅ **Vendita Registrata!**\n"
            f"Annuncio #{ad_id} segnato come VENDUTO a {price:.2f}€.\n"
            "Le altre pubblicazioni sono state chiuse automaticamente.",
            reply_markup=kb.get_main_menu(), # O torna alla lista annunci
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer("⚠️ Prezzo non valido. Scrivi solo il numero (es. 10.50).")
        return # Rimaniamo nello stato WAITING_PRICE
    except Exception as e:
        logging.error(f"Errore salvataggio vendita: {e}")
        await message.answer("❌ Errore nel database.")
    
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
    
    # 1. Eseguiamo l'eliminazione nel DB
    success = await db.mark_ad_as_deleted(ad_id)
    
    if success:
        # 2. EFFETTO "POOF": Cancelliamo fisicamente il messaggio dalla chat
        try:
            await callback.message.delete()
            # Mostriamo un piccolo popup temporaneo di conferma
            await callback.answer("🗑️ Annuncio eliminato!", show_alert=False)
        except Exception as e:
            # Se per qualche motivo Telegram non fa cancellare il messaggio, modifichiamo il testo
            logging.error(f"Impossibile cancellare il messaggio: {e}")
            await callback.message.edit_text("🗑️ Annuncio eliminato.")
    else:
        await callback.answer("⚠️ Errore: Impossibile eliminare l'annuncio.", show_alert=True)

    await state.clear()
    # NOTA: Non richiamiamo più my_ads_handler, così la lista non si duplica.
    
# --- 6. Stats Handler ---
@router.message(F.text == "📊 Statistiche", StateFilter(None))
async def stats_handler(message: Message, state: FSMContext):
    # 1. Pulizia: Cancelliamo menu precedenti e liste annunci
    if state:
        await clear_previous_ads_messages(state, message.bot, message.chat.id)
        await clear_previous_menu_message(state, message.bot, message.chat.id)

    # 2. Generazione Dati
    processing_msg = await message.answer("📊 Sto generando le tue statistiche...")
    
    try:
        stats = await db.get_advanced_stats(message.from_user.id)
        chart_data = await db.get_category_chart_data(message.from_user.id)
        
        report = (f"--- **Panoramica** ---\n"
                  f"• Annunci Totali: **{stats['totale_annunci']}**\n"
                  f"• Annunci Venduti: **{stats['totale_vendite']}**\n\n"
                  f"--- **Guadagni** 💰 ---\n"
                  f"• Guadagno Totale: **{stats['guadagno_totale']:.2f} €**\n"
                  f"• Stima Guadagno Futuro: **{stats['stima_guadagno_futuro']:.2f} €**\n")
        
        chart_buf = generate_pie_chart(chart_data)
        
        # 3. Invio Risultato
        if chart_buf:
            sent_msg = await message.answer_photo(
                photo=BufferedInputFile(chart_buf.read(), "sales.png"), 
                caption=report, 
                parse_mode="Markdown"
            )
        else:
            sent_msg = await message.answer(report, parse_mode="Markdown")
        
        # 4. Salvataggio ID per pulizia futura
        if state:
            await state.update_data(last_menu_msg_id=sent_msg.message_id)
            
        # Cancelliamo il messaggio temporaneo "Sto generando..."
        await processing_msg.delete()

    except Exception as e:
        logging.error(f"Error in stats_handler: {e}")
        await processing_msg.edit_text("❌ Errore durante la generazione delle statistiche.")
        
# --- 4. HANDLER DI ANNULLAMENTO GLOBALE (NUOVA SEZIONE) ---
@router.callback_query(F.data.startswith("cancel_"))
async def universal_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """
    Cancella lo stato corrente, elimina il messaggio tecnico e ristabilisce il Menu Principale.
    """
    current_state = await state.get_state()
    if current_state is not None:
        logging.info(f"Cancelling state {current_state} via cancel button.")
        await state.clear()
    
    # 1. Cancelliamo il messaggio con i bottoni (es. "Vuoi eliminare?") per pulizia
    try:
        await callback.message.delete()
    except:
        pass # Se non riesce a cancellare (messaggio troppo vecchio), pazienza

    # 2. Confermiamo l'annullamento e RIMOSTRIAMO LA TASTIERA PRINCIPALE
    await callback.message.answer(
        "🚫 Operazione annullata.", 
        reply_markup=kb.get_main_menu()
    )
    await callback.answer()

# --- 5. VISUALIZZAZIONE DETTAGLI ANNUNCIO (NUOVA SEZIONE) ---
@router.callback_query(F.data.startswith("view_details:"))
async def view_ad_details_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    ad_id = int(callback.data.split(":")[1])

    try:
        ad_details = await db.get_ad_details(ad_id, callback.from_user.id)
        if not ad_details:
            await callback.answer("❌ Annuncio non trovato.", show_alert=True)
            return

        def format_dt(dt_str):
            if not dt_str: return None
            try:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            except: return None

        status_map = {'DRAFT': 'Bozza', 'SCHEDULED': 'Programmato', 'SOLD': 'Venduto', 'DELETED': 'Eliminato'}
        status = status_map.get(ad_details.get('status_name'), ad_details.get('status_name'))
        price = f"{ad_details.get('suggested_price'):.2f} €" if ad_details.get('suggested_price') else "N/D"

        details_text = (
            f"ℹ️ **Scheda Annuncio #{ad_id}**\n\n"
            f"**Titolo:** {ad_details.get('generated_title', 'N/A')}\n\n"
            f"**Descrizione:**\n{ad_details.get('generated_description', 'N/A')}\n\n"
            f"💰 **Prezzo:** {price}\n"
            f"📊 **Stato:** `{status}`\n"
            f"📂 **Categoria:** {ad_details.get('category_name', 'N/A')}\n"
        )

        # Sezione Venduto
        sold_date = format_dt(ad_details.get('sold_datetime'))
        if sold_date:
            details_text += f"\n🤝 **Venduto il:** {sold_date}\n"

        # --- FIX VISUALIZZAZIONE STORICO ---
        pub_list = await db.get_ad_publications(ad_id)
        history_pubs = []
        now = datetime.now()
        
        if pub_list:
            details_text += "\n**📅 Calendario Pubblicazioni:**\n"
            for pub in pub_list:
                try:
                    # pub['date'] arriva dal DB come stringa 'YYYY-MM-DD HH:MM' (formattata nella query)
                    # La parsiamo per confrontarla
                    dt_obj = datetime.strptime(pub['date'], '%Y-%m-%d %H:%M')
                    
                    if dt_obj < now:
                        # Passato
                        history_pubs.append(f"✅ Pubblicato: {pub['platform']} ({pub['date']})")
                    else:
                        # Futuro
                        history_pubs.append(f"🗓️ Programmato: {pub['platform']} ({pub['date']})")
                except ValueError:
                    continue
            
            details_text += "\n".join(history_pubs) + "\n"

        await callback.message.edit_text(details_text, reply_markup=callback.message.reply_markup, parse_mode="Markdown")
        await callback.answer()

    except Exception as e:
        logging.error(f"Error viewing details: {e}")
        await callback.answer("Errore recupero dettagli.")
        
@router.callback_query(F.data.startswith("copy_ad_data:"))
async def copy_ad_data_handler(callback: CallbackQuery, state: FSMContext):
    """
    Recupera la prossima piattaforma programmata, invia i dati separati 
    e pulisce tutti gli altri messaggi.
    """
    # 1. RISPONDIAMO SUBITO PER EVITARE TIMEOUT
    # Usiamo un try/except perché se l'utente clicca su un messaggio vecchio,
    # non vogliamo che il bot si blocchi solo perché non può fare l'animazione.
    try:
        await callback.answer("⏳ Recupero dati...")
    except Exception:
        pass 

    ad_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    try:
        # 2. Recupero dettagli base
        ad = await db.get_ad_details(ad_id, user_id)
        if not ad:
            # Qui usiamo message.answer perché il callback potrebbe essere scaduto
            await callback.message.answer("❌ Errore: Annuncio non trovato.")
            return

        # 3. Query Prossima Piattaforma
        query_next_pub = """
            SELECT p.name as platform_name, pa.scheduled_datetime
            FROM publication_ad pa
            JOIN platform p ON pa.id_platform = p.id_platform
            WHERE pa.id_ad = ? 
            AND pa.scheduled_datetime > datetime('now', 'localtime')
            AND pa.deleted_datetime IS NULL
            ORDER BY pa.scheduled_datetime ASC
            LIMIT 1
        """
        next_pub = await db._fetch_one(query_next_pub, (ad_id,))
        
        if next_pub:
            # Conversione sicura della data
            try:
                dt_obj = datetime.strptime(next_pub['scheduled_datetime'], '%Y-%m-%d %H:%M:%S')
                info_pub = f"🌐 {next_pub['platform_name']} ({dt_obj.strftime('%d/%m %H:%M')})"
            except ValueError:
                info_pub = f"🌐 {next_pub['platform_name']}"
        else:
            info_pub = "🌐 Nessuna prox. pubblicazione"

        # 4. PULIZIA TOTALE
        # Nota: keep_message_id=None cancella TUTTO, incluso il menu da cui hai cliccato.
        # Se vuoi tenere il menu, rimetti: keep_message_id=callback.message.message_id
        await clear_previous_ads_messages(
            state, 
            callback.bot, 
            callback.message.chat.id, 
            keep_message_id=callback.message.message_id 
        )

        # 5. Dati
        titolo = ad.get('generated_title', 'N/D')
        descrizione = ad.get('generated_description', 'N/D')
        prezzo = f"{ad.get('suggested_price', 0.0):.2f}".replace(',', '.')
        categoria = ad.get('category_name', 'Generica')

        # 6. INVIO MESSAGGI
        await callback.message.answer(
            f"📋 **Copia Rapida ID #{ad_id}**\n"
            f"📂 Cat: {categoria} | {info_pub}\n"
            "───────────────"
        )
        await asyncio.sleep(0.1)
        await callback.message.answer(titolo)
        await asyncio.sleep(0.1)
        await callback.message.answer(descrizione)
        await asyncio.sleep(0.1)
        await callback.message.answer(prezzo)

    except Exception as e:
        logging.error(f"Errore Copia Rapida: {e}")
        # Non usiamo callback.answer qui perché potrebbe essere scaduto
        await callback.message.answer("⚠️ Errore nel recupero dati.")

@router.callback_query(F.data.startswith("publish_now:"))
async def publish_now_handler(callback: CallbackQuery, state: FSMContext):
    """
    Gestisce il click su 'Pubblica Ora' dalla notifica.
    1. Invia i 4 messaggi per il copia incolla.
    2. Segna la pubblicazione come PUBLISHED nel DB.
    3. Aggiorna la data di pubblicazione a ADESSO.
    """
    # Rispondiamo subito per evitare timeout
    try:
        await callback.answer("🚀 Carico dati pubblicazione...")
    except: pass

    pub_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    try:
        # 1. Recuperiamo i dettagli COMPLETI usando pub_id
        # Dobbiamo fare una query join perché get_ad_details usa id_ad
        query = """
        SELECT a.generated_title, a.generated_description, a.suggested_price, 
               c.name as category_name, p.name as platform_name, a.id_ad
        FROM publication_ad pa
        JOIN ad a ON pa.id_ad = a.id_ad
        JOIN platform p ON pa.id_platform = p.id_platform
        LEFT JOIN category c ON a.id_category = c.id_category
        WHERE pa.id_publication_ad = ? AND a.id_telegram_user = ?
        """
        data = await db._fetch_one(query, (pub_id, user_id))
        
        if not data:
            await callback.message.answer("❌ Errore: Pubblicazione non trovata.")
            return

        # 2. Aggiornamento Stato nel DB (PUBLISHED + Data Runtime)
        st_published = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='PUBLISHED'"))['id_status_type']
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        await db._execute_query(
            """
            UPDATE publication_ad 
            SET id_status_type = ?, publication_datetime = ? 
            WHERE id_publication_ad = ?
            """,
            (st_published, now_iso, pub_id)
        )

        # 3. Invio Messaggi (Stile Copia Rapida)
        titolo = data['generated_title']
        descrizione = data['generated_description']
        prezzo = f"{data['suggested_price']:.2f}".replace(',', '.')
        
        # Header
        await callback.message.answer(
            f"🚀 **PUBBLICAZIONE AVVIATA!**\n"
            f"📂 {data['category_name']} | 🌐 {data['platform_name']}\n"
            "───────────────\n"
            "Copia i dati qui sotto 👇"
        )
        await asyncio.sleep(0.1)
        await callback.message.answer(titolo)
        await asyncio.sleep(0.1)
        await callback.message.answer(descrizione)
        await asyncio.sleep(0.1)
        await callback.message.answer(prezzo)

        # 4. Feedback visivo sul messaggio originale della notifica
        # Modifichiamo il messaggio "È ora di pubblicare" in "✅ Pubblicato"
        try:
            await callback.message.edit_text(
                f"✅ **PUBBLICATO**\n"
                f"Annuncio #{data['id_ad']} su {data['platform_name']}\n"
                f"📅 {datetime.now().strftime('%d/%m %H:%M')}",
                reply_markup=None
            )
        except:
            pass # Se non riesce a modificare (messaggio vecchio), pazienza

    except Exception as e:
        logging.error(f"Errore Publish Now: {e}")
        await callback.message.answer("⚠️ Errore durante la pubblicazione.")

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

    # --- TEMPORARY TEST DATA GENERATOR ---
from aiogram.filters import Command
import random
from datetime import timedelta
@router.message(Command("testdata"))
async def generate_test_data(message: Message):
    """
    Comando segreto per popolare il DB con dati falsi per testare le statistiche.
    FIX: Passa oggetti datetime corretti alle funzioni del DB.
    """
    user_id = message.from_user.id
    await message.answer("🧪 Inizio generazione dati fake...")

    # 1. Recupera ID utili
    cats = await db.get_all_categories()
    platforms = await db.get_all_platforms()
    if not cats or not platforms:
        await message.answer("Errore: Categorie o piattaforme mancanti nel DB.")
        return

    # Recupera ID stati
    st_sold = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='SOLD'"))['id_status_type']
    st_sched = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='SCHEDULED'"))['id_status_type']
    st_pub = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='PUBLISHED'"))['id_status_type']
    st_other = (await db._fetch_one("SELECT id_status_type FROM status_type WHERE name='SOLD_OTHER_PLATFORM'"))['id_status_type']

    # 2. Genera 5 annunci VENDUTI (passato)
    for i in range(1, 6):
        cat = random.choice(cats)['id_category']
        price = random.randint(10, 150) + 0.99
        ad_id = await db.add_ad(user_id, "Descrizione Fake", f"Oggetto Venduto #{i}", "Descrizione gen", price, cat)
        
        # Simula vendita su una piattaforma random
        winner_plat = random.choice(platforms)['id_platform']
        # NOTA: Per SQL grezzo serve STRINGA
        sold_date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d %H:%M:%S")
        
        await db._execute_query(
            "INSERT INTO publication_ad (id_ad, id_platform, id_status_type, sold_price, sold_datetime) VALUES (?, ?, ?, ?, ?)",
            (ad_id, winner_plat, st_sold, price, sold_date)
        )
        loser_plat = [p['id_platform'] for p in platforms if p['id_platform'] != winner_plat][0]
        await db._execute_query(
            "INSERT INTO publication_ad (id_ad, id_platform, id_status_type, deleted_datetime) VALUES (?, ?, ?, ?)",
            (ad_id, loser_plat, st_other, sold_date)
        )

    # 3. Genera 3 annunci PROGRAMMATI (futuro)
    for i in range(1, 4):
        cat = random.choice(cats)['id_category']
        price = random.randint(20, 80)
        ad_id = await db.add_ad(user_id, "Descrizione Fake", f"Oggetto Futuro #{i}", "Descrizione gen", price, cat)
        
        # NOTA: Per add_publication_entry serve OGGETTO DATETIME (senza strftime)
        future_date = datetime.now() + timedelta(days=random.randint(1, 7))
        plat = random.choice(platforms)['id_platform']
        
        await db.add_publication_entry(ad_id, plat, st_sched, future_date)

    # 4. Genera 2 annunci PUBBLICATI (attivi ora)
    for i in range(1, 3):
        cat = random.choice(cats)['id_category']
        price = random.randint(5, 50)
        ad_id = await db.add_ad(user_id, "Descrizione Fake", f"Oggetto Online #{i}", "Descrizione gen", price, cat)
        
        plat = random.choice(platforms)['id_platform']
        # NOTA: Per SQL grezzo serve STRINGA
        pub_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        
        await db._execute_query(
            "INSERT INTO publication_ad (id_ad, id_platform, id_status_type, publication_datetime) VALUES (?, ?, ?, ?)",
            (ad_id, plat, st_pub, pub_date)
        )

    await message.answer("✅ **Dati Generati!**\nOra prova a premere '📊 Statistiche' o '🛍️ I Miei Annunci'.")
    
@router.message(StateFilter(None)) # Cattura tutto solo se NON c'è uno stato attivo (es. non sto scrivendo la descrizione)
async def catch_all_message(message: Message):
    """
    Risponde a qualsiasi messaggio di testo non riconosciuto.
    """
    await message.answer(
        "🤔 Non ho capito questo comando.\n"
        "Usa i pulsanti del menu qui sotto per navigare.",
        reply_markup=kb.get_main_menu()
    )
    