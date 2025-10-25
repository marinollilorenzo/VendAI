import os
from dotenv import load_dotenv
from dateutil.parser import isoparse
import dateparser
from telegram import(
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyKeyboardMarkup
)
from telegram.helpers import escape_markdown
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)
from database import (
    add_annuncement, 
    aggiorna_annuncio_con_programmazione, 
    ottieni_statistiche_stati,
    get_or_create_user,
    ottieni_annunci_utente
)
from aiService import ad_text_generator
from aiService import parse_risposta_ai

load_dotenv()
TOKEN   = os.getenv("TOKEN")

ATTESA_CATEGORIA, ATTESA_DATA = range(2)

T_CREA = "🆕 Crea Annuncio"
T_LISTA = "🛍️ I Miei Annunci"
T_VENDI = "✅ Segna come Venduto"
T_ANALISI = "📈 Statistiche"
T_AIUTO = "❓ Aiuto / Annulla"

#Funzione che crea i pulsanti del menu principale
def crea_menu_principale() -> ReplyKeyboardMarkup:
    """Crea la tastiera del menu principale."""
    tastiera = [
        [T_CREA],  # Una riga per il pulsante principale
        [T_LISTA, T_VENDI], # Due pulsanti sulla stessa riga
        [T_ANALISI, T_AIUTO] # Altri due
    ]
    
    return ReplyKeyboardMarkup(
        tastiera, 
        resize_keyboard=True, # Adatta la tastiera allo schermo
        one_time_keyboard=False # Rende la tastiera persistente
    )

#Funzione che crea i tasti per la categoria
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

#Funzione di inizio bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia il messaggio di benvenuto e mostra il menu principale."""
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente per le vendite.\n"
        "Usa i pulsanti qui sotto per iniziare 👇",
        reply_markup=crea_menu_principale() # <-- MOSTRA IL MENU
    )
    # Rimuoviamo qualsiasi stato di conversazione precedente
    return ConversationHandler.END

"""
async def nuovo_annuncio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text("Per favore, fornisci una descrizione dopo il comando /nuovo.")
        return ConversationHandler.END # Termina la conversazione
        
    descrizione_input = " ".join(context.args)
    
    # Chiama la funzione che processa e chiede la categoria
    return await processa_e_chiedi_categoria(descrizione_input, update, context, foto_bytes=None)
"""

#Funzione che analizza i dati degli annunci
async def analisi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Ricevuto comando /analisi")
    user = update.message.from_user
    id_telegram = user.id
    nome_telegram = user.first_name
    id_utente_db = get_or_create_user(id_telegram, nome_telegram)
    try:
        statistiche = ottieni_statistiche_stati(id_utente_db)

        if not statistiche:
            await update.message.reply_text("Nessun annuncio ancora nel database.")
            return

        messaggio_risposta = "📊 **Statistiche Annunci** 📊\n\n"
        messaggio_risposta += "Ecco un riepilogo dei tuoi annunci per stato:\n"
        
        totale_annunci = 0
        for stato in statistiche:
            messaggio_risposta += f"  - **{stato['nome_stato'].capitalize()}**: {stato['conteggio']} annunci\n"
            totale_annunci += stato['conteggio']
        
        messaggio_risposta += f"\n**Totale Annunci:** {totale_annunci}"

        await update.message.reply_text(messaggio_risposta, 
                                        parse_mode='Markdown',
                                        reply_markup=crea_menu_principale())

    except Exception as e:
        print(f"Errore durante /analisi: {e}")
        await update.message.reply_text(f"Si è verificato un errore durante la generazione delle statistiche: {e}")

#Funzione per la creazione di un annuncio
async def nuovo_annuncio_handler_testo_guida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Perfetto! 👍\nPer creare un nuovo annuncio, **inviami una foto con una breve descrizione nella didascalia**.",
        parse_mode='Markdown'
    )

#Funzione che prende la foto e lo manda a gemini
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

#Funzione che torna la lista degli annunci
async def lista_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    print("Ricevuto comando /lista")
    
    # --- Autenticazione Utente ---
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    try:
        annunci = ottieni_annunci_utente(id_utente_db)

        if not annunci:
            await update.message.reply_text("Non hai ancora nessun annuncio nel database. Inizia con /start o inviando una foto.")
            return

        messaggio_risposta = "📑 **I Tuoi Annunci** 📑\n\n"
        
        for annuncio in annunci:
            titolo = annuncio['titolo_generato'] if annuncio['titolo_generato'] else "Senza Titolo"
            stato = annuncio['nome_stato'].capitalize() if annuncio['nome_stato'] else "Bozza"
            
            # Formattiamo un bel titolo per ogni annuncio
            messaggio_risposta += f"🆔 **ID:** `{annuncio['id']}`\n"
            messaggio_risposta += f"   **Titolo:** {escape_markdown(titolo, version=2)}\n"
            messaggio_risposta += f"   **Stato:** {stato}\n"
            
            # Aggiungiamo la data di programmazione se esiste
            if annuncio['data_pubblicazione']:
                data_prog = isoparse(annuncio['data_pubblicazione']).strftime('%d/%m/%y alle %H:%M')
                messaggio_risposta += f"   **Programmato:** {data_prog}\n"
            
            messaggio_risposta += "‐‐‐‐‐‐‐‐‐‐‐‐‐‐‐‐‐‐‐‐\n" # Separatore

        await update.message.reply_text(messaggio_risposta, 
                                        parse_mode='MarkdownV2',
                                        reply_markup=crea_menu_principale())

    except Exception as e:
        print(f"Errore durante /lista: {e}")
        await update.message.reply_text(f"Si è verificato un errore durante il recupero dei tuoi annunci: {e}")
           
#Funzione che segna venduto un annuncio    
async def vendi_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Funzione /vendi in costruzione! Torna presto.",
                                    reply_markup=crea_menu_principale())
    return ConversationHandler.END # Per ora non fa nulla 

#Funzione che continua la creazione
async def processa_e_chiedi_categoria(descrizione_input: str, update: Update, context: ContextTypes.DEFAULT_TYPE, foto_bytes: bytearray = None) -> int:
    """
    genera l'annuncio, lo salva in bozza, chiede all'utente la categoria, entrando nello stato ATTESA_CATEGORIA.
    """
    await update.message.reply_text(f"✍️ Ricevuto: '{descrizione_input}'.\nSto analizzando testo e immagine con l'IA, attendi...")
    #autentificazione utente
    user = update.message.from_user
    id_telegram = user.id
    nome_telegram = user.first_name
    id_utente_db = get_or_create_user(id_telegram, nome_telegram)
    
    
    testo_grezzo_ai = await ad_text_generator(descrizione_input, foto_bytes)
    titolo, descrizione, prezzo = parse_risposta_ai(testo_grezzo_ai)
    
    # Salviamo l'annuncio in bozza (categoria e piattaforma sono ancora vuote/default)
    nuovo_id = add_annuncement(
        id_utente=id_utente_db,
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

#Funzione che riceve la categoria e la inserisce all'annuncio
async def ricevi_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Questa funzione si attiva quando l'utente preme un pulsante di categoria.
    """
    query = update.callback_query
    await query.answer() # Risponde al "click" per far sparire l'icona di caricamento

    # Estraiamo l'ID della categoria dal pulsante (es. "cat_1" -> "1")
    id_categoria_scelta = int(query.data.split('_')[1])
    context.user_data['id_categoria_scelta'] = id_categoria_scelta
    await query.edit_message_text(text=f"✅ Categoria scelta! Ora dimmi quando vuoi programmare l'annuncio.")
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Scrivimi una data e un'ora (es: 'domani alle 15:00', '25 ottobre 10:30', o 'tra 2 ore')."
    )
    # Diciamo al ConversationHandler di passare allo stato "ATTESA_DATA"
    return ATTESA_DATA

#Funzione che riceve la data e la inserisce all'annuncio
async def ricevi_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Questa funzione si attiva quando l'utente invia un testo nello stato ATTESA_DATA.
    """
    testo_data = update.message.text
    
    # Usiamo dateparser per "capire" il testo
    data_programmata = dateparser.parse(testo_data, languages=['it'])

    if not data_programmata:
        # L'utente ha scritto qualcosa che non capiamo
        await update.message.reply_text(
            "Non ho capito la data. 😅 Riprova con un formato più semplice (es. 'domani alle 15:00')."
        )
        return ATTESA_DATA # Rimaniamo nello stesso stato

    # Recuperiamo i dati dalla memoria
    id_annuncio = context.user_data.get('id_annuncio_corrente')
    id_categoria = context.user_data.get('id_categoria_scelta')

    if not id_annuncio or not id_categoria:
        await update.message.reply_text("Si è verificato un errore, i dati dell'annuncio sono andati persi. Riprova con /start.")
        context.user_data.clear()
        return ConversationHandler.END

    # Aggiorniamo il database con TUTTE le informazioni
    aggiorna_annuncio_con_programmazione(id_annuncio, id_categoria, data_programmata)

    await update.message.reply_text(
        f"Perfetto! 👍 Annuncio {id_annuncio} salvato e programmato per:\n"
        f"**{data_programmata.strftime('%d %B %Y alle %H:%M')}**",
        parse_mode='Markdown',
        reply_markup=crea_menu_principale()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

#Funzione che annulla l'azione che si sta facendo
async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annulla la conversazione e ritorna al menu principale."""
    await update.message.reply_text(
        "Operazione annullata. Ritorno al menu principale.",
        reply_markup=crea_menu_principale()
    )
    context.user_data.clear()
    return ConversationHandler.END

#Funzione di aiuto
async def aiuto_annulla_globale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler per il pulsante 'Aiuto / Annulla'."""
    await update.message.reply_text(
        "Sei nel menu principale. Non c'è nessuna operazione da annullare.\n\n"
        "Premi i pulsanti per iniziare:\n"
        "🆕 **Crea Annuncio**: Invia una foto con didascalia per iniziare.\n"
        "🛍️ **I Miei Annunci**: Mostra tutti i tuoi annunci.\n"
        "✅ **Segna come Venduto**: Inizia la procedura per segnare un annuncio come venduto.\n"
        "📈 **Statistiche**: Mostra l'analisi delle tue vendite.",
        reply_markup=crea_menu_principale(),
        parse_mode='Markdown'
    )

#gestione dei messaggi senza senso
async def gestisci_testo_sconosciuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Risponde a qualsiasi messaggio di testo non riconosciuto."""
    await update.message.reply_text(
        "Non ho capito... 😅\n"
        "Usa i pulsanti del menu qui sotto per dirmi cosa fare.",
        reply_markup=crea_menu_principale()
    )    
# --- FUNZIONE DI AVVIO ---
def bot_start(): # o avvia_bot()
    """Crea l'applicazione e avvia il bot con il menu principale."""
    application = Application.builder().token(TOKEN).build()

    # --- CONVERSAZIONE 1: CREAZIONE ANNUNCIO ---
    conv_handler_crea = ConversationHandler(
        entry_points=[
            # L'utente può iniziare o inviando una foto...
            MessageHandler(filters.PHOTO, foto_handler),
            # ...o cliccando il pulsante (che gestiamo dopo)
            MessageHandler(filters.Text(T_CREA), nuovo_annuncio_handler_testo_guida)
        ],
        states={
            ATTESA_CATEGORIA: [
                CallbackQueryHandler(ricevi_categoria) 
            ],
            ATTESA_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_data)
            ]
        },
        fallbacks=[
            # Il comando /annulla funziona DENTRO la conversazione
            CommandHandler("annulla", annulla),
            # Anche il pulsante 'Aiuto / Annulla' funziona
            MessageHandler(filters.Text(T_AIUTO), annulla)
        ],
    )
    
    # --- CONVERSAZIONE 2: VENDITA ANNUNCIO ---
    # Per ora è vuota, ma la prepariamo
    conv_handler_vendi = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(T_VENDI), vendi_wizard_start)],
        states={
            # ... (qui definiremo gli stati per scegliere l'annuncio e inserire il prezzo)
        },
        fallbacks=[
            CommandHandler("annulla", annulla),
            MessageHandler(filters.Text(T_AIUTO), annulla)
        ],
    )

    # Aggiungiamo i gestori di conversazione
    application.add_handler(conv_handler_crea)
    # application.add_handler(conv_handler_vendi) # La attiveremo quando sarà pronta

    # --- GESTORI GLOBALI (Il Menu Principale) ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Text(T_LISTA), lista_handler))
    application.add_handler(MessageHandler(filters.Text(T_ANALISI), analisi_handler))
    application.add_handler(MessageHandler(filters.Text(T_AIUTO), aiuto_annulla_globale))
    application.add_handler(MessageHandler(filters.Text(T_VENDI), vendi_wizard_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_testo_sconosciuto))

    print("Bot avviato e in ascolto... (modalità MENU ATTIVA!)")
    application.run_polling()