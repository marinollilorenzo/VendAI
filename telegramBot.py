import os
from dotenv import load_dotenv
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from aiService import ad_text_generator
from aiService import parse_risposta_ai
from database import add_annuncement, aggiorna_categoria_annuncio


load_dotenv()
TOKEN   = os.getenv("TOKEN")

ATTESA_DESCRIZIONE, ATTESA_CATEGORIA = range(2)

def crea_tastiera_categorie():
    """Crea una tastiera con le categorie prese dal DB."""
    pulsanti = [
        [InlineKeyboardButton("👕 Abbigliamento", callback_data="cat_1")],
        [InlineKeyboardButton("🔌 Elettronica", callback_data="cat_2")],
        [InlineKeyboardButton("📚 Libri/Hobby", callback_data="cat_3")],
        [InlineKeyboardButton("🏠 Casa", callback_data="cat_4")],
        [InlineKeyboardButton("Altro", callback_data="cat_5")],
    ]
    return InlineKeyboardMarkup(pulsanti)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Funzione di avvio."""
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente per creare annunci.\n"
        "Puoi inviarmi una **foto con didascalia** per iniziare.\n\n"
        "Oppure usa il comando /nuovo seguito dalla descrizione (solo testo).\n\n"
        "Puoi annullare in qualsiasi momento con /annulla.",
        parse_mode='Markdown'
    )
    # Diciamo al ConversationHandler che non stiamo ancora in uno stato specifico
    return ConversationHandler.END


async def nuovo_annuncio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler per il comando /nuovo (solo testo)."""
    if not context.args:
        await update.message.reply_text("Per favore, fornisci una descrizione dopo il comando /nuovo.")
        return ConversationHandler.END # Termina la conversazione
        
    descrizione_input = " ".join(context.args)
    
    # Chiama la funzione che processa e chiede la categoria
    return await processa_e_chiedi_categoria(descrizione_input, update, context, foto_bytes=None)


async def foto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler per la foto con didascalia."""
    if not update.message.caption:
        await update.message.reply_text(
            "Foto ricevuta! 👍\nPer favore, inviala di nuovo ma aggiungendo "
            "una descrizione nella **didascalia**.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END # Termina la conversazione
    
    descrizione_input = update.message.caption
    
    foto = update.message.photo[-1]
    file_foto = await foto.get_file()
    foto_bytes = await file_foto.download_as_bytearray()
    
    # Chiama la funzione che processa e chiede la categoria
    return await processa_e_chiedi_categoria(descrizione_input, update, context, foto_bytes=foto_bytes)


async def processa_e_chiedi_categoria(descrizione_input: str, update: Update, context: ContextTypes.DEFAULT_TYPE, foto_bytes: bytearray = None) -> int:
    """
    genera l'annuncio, lo salva in bozza, chiede all'utente la categoria, entrando nello stato ATTESA_CATEGORIA.
    """
    await update.message.reply_text(f"✍️ Ricevuto: '{descrizione_input}'.\nSto analizzando testo e immagine con l'IA, attendi...")

    testo_grezzo_ai = await ad_text_generator(descrizione_input, foto_bytes)
    titolo, descrizione, prezzo = parse_risposta_ai(testo_grezzo_ai)
    
    # Salviamo l'annuncio in bozza (categoria e piattaforma sono ancora vuote/default)
    nuovo_id = add_annuncement(
        descrizione_input=descrizione_input,
        titolo_generato=titolo,
        descrizione_generata=descrizione,
        prezzo_suggerito=prezzo,
        id_categoria=None # Lo chiederemo ora
    )
    context.user_data['id_annuncio_corrente'] = nuovo_id
    
    titolo_pulito = escape_markdown(titolo, version=2)
    descrizione_pulita = escape_markdown(descrizione, version=2)
    prezzo_pulito = escape_markdown(prezzo, version=2)

    risposta_anteprima = (
        f"✅ Annuncio in bozza creato con ID: {nuovo_id}\n\n"
        f"**Titolo:**\n{titolo_pulito}\n\n"
        f"**Descrizione:**\n{descrizione_pulita}\n\n"
        f"**Prezzo Suggerito:** {prezzo_pulito}"
    )
    
    await update.message.reply_text(risposta_anteprima, parse_mode='MarkdownV2')
    
    # Ora facciamo la domanda con i pulsanti
    await update.message.reply_text(
        "Ottimo! Ora scegli una categoria per l'annuncio:",
        reply_markup=crea_tastiera_categorie()
    )
    
    # Diciamo al ConversationHandler di passare allo stato "ATTESA_CATEGORIA"
    return ATTESA_CATEGORIA


async def ricevi_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Questa funzione si attiva quando l'utente preme un pulsante di categoria.
    """
    query = update.callback_query
    await query.answer() # Risponde al "click" per far sparire l'icona di caricamento

    # Estraiamo l'ID della categoria dal pulsante (es. "cat_1" -> "1")
    id_categoria_scelta = int(query.data.split('_')[1])
    
    # Recuperiamo l'ID dell'annuncio dalla memoria della conversazione
    id_annuncio = context.user_data.get('id_annuncio_corrente')

    if not id_annuncio:
        await query.edit_message_text(text="Si è verificato un errore, non trovo l'annuncio da aggiornare. Riprova con /start.")
        return ConversationHandler.END

    # Aggiorniamo il database!
    aggiorna_categoria_annuncio(id_annuncio, id_categoria_scelta)

    # Modifichiamo il messaggio dei pulsanti con la conferma
    await query.edit_message_text(text=f"Perfetto! Annuncio {id_annuncio} salvato e impostato come 'pubblicato' nella categoria scelta.")
    
    # Puliamo la memoria
    context.user_data.clear()
    
    # Diciamo al ConversationHandler che questa conversazione è FINITA
    return ConversationHandler.END


async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Funzione per annullare la conversazione in qualsiasi momento."""
    await update.message.reply_text("Operazione annullata. Riprova quando vuoi con /start.")
    # Puliamo la memoria
    context.user_data.clear()
    return ConversationHandler.END

# --- FUNZIONE DI AVVIO ---

def bot_start():
    """Crea l'applicazione e avvia il bot usando il ConversationHandler."""
    application = Application.builder().token(TOKEN).build()


    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("nuovo", nuovo_annuncio_handler),
            MessageHandler(filters.PHOTO, foto_handler)
        ],
        states={
            ATTESA_CATEGORIA: [
                CallbackQueryHandler(ricevi_categoria) # Ascolta solo i click sui pulsanti
            ],
        },
        fallbacks=[
            CommandHandler("annulla", annulla) # Permette di uscire con /annulla
        ],
    )
    
    # Aggiungiamo il nostro gestore di conversazioni all'applicazione
    application.add_handler(conv_handler)
    
    # Aggiungiamo un handler /start "di riserva" fuori dalla conversazione
    # per sbloccare il bot se si dovesse incastrare
    application.add_handler(CommandHandler("start", start))

    print("Bot avviato e in ascolto... (modalità conversazione attiva!)")
    application.run_polling()