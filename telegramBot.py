import os
from dotenv import load_dotenv
import re
import datetime
from dateutil.parser import isoparse
from datetime import timedelta
import matplotlib.pyplot as plt
import seaborn as sns
import io
plt.switch_backend('Agg')
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
    ottieni_statistiche_avanzate,
    get_or_create_user,
    ottieni_annunci_utente,
    segna_come_venduto,
    ottieni_annunci_non_venduti,
    ottieni_categorie_attive,
    ottieni_piattaforme_attive,
    disattiva_annuncio,
    ottieni_dettagli_annuncio,
    aggiorna_campo_annuncio,
    ottieni_dati_grafico_categorie
)
from aiService import ad_text_generator

load_dotenv()
TOKEN   = os.getenv("TOKEN")
# Mapping Italian month names to numbers (case-insensitive)
mesi = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

# Mapping Italian weekdays to numbers (0=Monday, 6=Sunday)
giorni_settimana = {
    "lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, "mercoledì": 2, "mercoledi": 2,
    "giovedì": 3, "giovedi": 3, "venerdì": 4, "venerdi": 4, "sabato": 5, "domenica": 6
}

(
    CREA_ATTESA_FOTO,
    CREA_ATTESA_CONFERMA_ANTEPRIMA,  # Step 1: Mostra l'anteprima e aspetta [Sì] o [Modifica]
    CREA_MENU_MODIFICA,             # Step 2 (Opzionale): Mostra [Titolo] [Descrizione] [Prezzo]
    CREA_ATTESA_NUOVO_TITOLO,       # Step 3 (Opzionale): Aspetta il nuovo titolo
    CREA_ATTESA_NUOVA_DESCRIZIONE,  # Step 3 (Opzionale): Aspetta la nuova descrizione
    CREA_ATTESA_NUOVO_PREZZO,       # Step 3 (Opzionale): Aspetta il nuovo prezzo
    CREA_ATTESA_CATEGORIA,          # Step 4: Chiede la Categoria
    CREA_ATTESA_PIATTAFORMA,        # Step 5: Chiede la Piattaforma
    CREA_ATTESA_DATA                # Step 6: Chiede la Data
) = range(9)
# ---STATI CONVERSAZIONE VENDI ---
VENDI_ATTESA_SCELTA, VENDI_ATTESA_PREZZO = range(9, 11)
# ---STATI CONVERSAZIONE ELIMINA ---
ELIMINA_ATTESA_SCELTA, ELIMINA_ATTESA_CONFERMA = range(11, 13)
(
    MODIFICA_ATTESA_SCELTA_ANNUNCIO,
    MODIFICA_MENU_CAMPI,
    MODIFICA_ATTESA_NUOVO_TITOLO,
    MODIFICA_ATTESA_NUOVA_DESCRIZIONE,
    MODIFICA_ATTESA_NUOVO_PREZZO
) = range(13, 18)
DETTAGLI_ATTESA_SCELTA = range(18, 19)

T_CREA = "🆕 Crea Annuncio"
T_LISTA = "🛍️ I Miei Annunci"
T_VENDI = "✅ Segna come Venduto"
T_ANALISI = "📈 Statistiche"
T_AIUTO = "❓ Aiuto / Annulla"
T_ELIMINA = "🗑️ Elimina Annuncio"
T_MODIFICA = "✏️ Modifica Annuncio"
T_DETTAGLI = "🔍 Vedi Dettagli"

# --- TASTIERE ---
def crea_menu_principale() -> ReplyKeyboardMarkup:
    """Crea la tastiera del menu principale."""
    tastiera = [
        [T_CREA],  # Una riga per il pulsante principale
        [T_LISTA, T_VENDI],
        [T_MODIFICA, T_ELIMINA],
        [T_ANALISI, T_DETTAGLI],
        [T_AIUTO]
    ]
    
    return ReplyKeyboardMarkup(
        tastiera, 
        resize_keyboard=True, # Adatta la tastiera allo schermo
        one_time_keyboard=False # Rende la tastiera persistente
    )

def crea_tastiera_categorie():
    """Crea una tastiera con le categorie prese dal DB."""
    pulsanti = []
    categorie = ottieni_categorie_attive()
    
    for cat in categorie:
        pulsanti.append([
            InlineKeyboardButton(cat['nome'], callback_data=f"cat_{cat['id']}")
        ])

    return InlineKeyboardMarkup(pulsanti)

def crea_tastiera_piattaforme():
    """Crea una tastiera con le piattaforme prese dal DB."""
    pulsanti = []
    piattaforme = ottieni_piattaforme_attive()
    
    for p in piattaforme:
        pulsanti.append([
            InlineKeyboardButton(p['nome'], callback_data=f"piat_{p['id']}")
        ])

    return InlineKeyboardMarkup(pulsanti)

def crea_tastiera_conferma_anteprima() -> InlineKeyboardMarkup:
    """Crea i pulsanti [Sì], [Modifica], [Annulla]"""
    pulsanti = [
        [InlineKeyboardButton("✅ Sì, prosegui", callback_data="crea_conferma_si")],
        [InlineKeyboardButton("✏️ Modifica Testo", callback_data="crea_conferma_modifica")],
        [InlineKeyboardButton("❌ Annulla Creazione", callback_data="crea_conferma_annulla")]
    ]
    return InlineKeyboardMarkup(pulsanti)

def crea_tastiera_menu_modifica() -> InlineKeyboardMarkup:
    """Crea i pulsanti [Titolo], [Descrizione], [Prezzo], [Fatto]"""
    pulsanti = [
        [
            InlineKeyboardButton("Titolo", callback_data="crea_modifica_titolo"),
            InlineKeyboardButton("Descrizione", callback_data="crea_modifica_desc"),
            InlineKeyboardButton("Prezzo", callback_data="crea_modifica_prezzo")
        ],
        [InlineKeyboardButton("↩️ Ho Fatto, torna all'anteprima", callback_data="crea_modifica_fatto")]
    ]
    return InlineKeyboardMarkup(pulsanti)

def crea_tastiera_conferma_elimina(id_annuncio) -> InlineKeyboardMarkup:
    """Crea i pulsanti [Sì, Elimina] e [No, Annulla]"""
    # Passiamo l'ID nel callback_data per sapere cosa eliminare
    pulsanti = [
        [
            InlineKeyboardButton("✅ Sì, Elimina", callback_data=f"elimina_conferma_si_{id_annuncio}"),
            InlineKeyboardButton("❌ No, Annulla", callback_data="elimina_conferma_no")
        ]
    ]
    return InlineKeyboardMarkup(pulsanti)

# --- START BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    messaggio_benvenuto = (
        f"Ciao {user.first_name}, benvenuto nel tuo assistente per le vendite online!\n\n"
        "Sono il tuo assistente personale per creare e gestire annunci di vendita online.\n\n"
        "**Cosa posso fare per te:**\n"
        "1.  Genero titoli e descrizioni **usando l'IA** (analizzando anche le tue foto).\n"
        "2.  **Programmo** i tuoi annunci all'ora che preferisci.\n"
        "3.  Ti **notifico** 30 minuti prima e all'ora X.\n"
        "4.  Tengo traccia di tutti i tuoi annunci e delle tue **statistiche di vendita**.\n\n"
        "Usa i pulsanti del menu qui sotto per iniziare! 👇"
    )
    
    await update.message.reply_text(
        messaggio_benvenuto,
        reply_markup=crea_menu_principale(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


# --- CONVERSAZIONI ---
# --- CREA ANNUNCIO ---
async def nuovo_annuncio_handler_testo_guida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Perfetto! 👍\nPer creare un nuovo annuncio, **inviami una foto con una breve descrizione nella didascalia**.\n\nL'IA analizzerà l'immagine per darti suggerimenti migliori!"
        "\n\n(Puoi annullare in qualsiasi momento premendo '❓ Aiuto / Annulla')",
        parse_mode='Markdown'
    )
    return CREA_ATTESA_FOTO

async def foto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler per la foto con didascalia."""
    if not update.message.caption:
        await update.message.reply_text(
            "Foto ricevuta! 👍\nPer favore, inviala di nuovo ma aggiungendo "
            "una descrizione nella **didascalia**.",
            parse_mode='Markdown'
        )
        return  CREA_ATTESA_FOTO
    
    descrizione_input = update.message.caption
    
    foto = update.message.photo[-1]
    file_foto = await foto.get_file()
    foto_bytes = await file_foto.download_as_bytearray()
    
    # Chiama la funzione che processa e chiede la categoria
    return await processa_e_mostra_anteprima(descrizione_input, update, context, foto_bytes=foto_bytes)

async def processa_e_mostra_anteprima(descrizione_input: str, update: Update, context: ContextTypes.DEFAULT_TYPE, foto_bytes: bytearray = None) -> int:
    """
    genera l'annuncio, lo salva in bozza, chiede all'utente la categoria, entrando nello stato CREA_ATTESA_CATEGORIA.
    """
    #autentificazione utente
    user = update.message.from_user
    id_telegram = user.id
    nome_telegram = user.first_name
    id_utente_db = get_or_create_user(id_telegram, nome_telegram)
    context.user_data['id_utente_db'] = id_utente_db
    await update.message.reply_text(f"✍️ Ricevuto! Sto analizzando la foto e la tua descrizione con l'IA... Questo potrebbe richiedere alcuni secondi. Attendi...")
    
    risultato_ai = await ad_text_generator(descrizione_input, foto_bytes)
    # 2. Controlliamo se è un errore
    if isinstance(risultato_ai, dict) and "Errore" in risultato_ai.get("title", ""):
         await update.message.reply_text(f"Errore dall'IA: {risultato_ai['description']}", reply_markup=crea_menu_principale())
         return ConversationHandler.END # Termina la conversazione


    context.user_data['bozza_annuncio'] = {
        'descrizione_input': descrizione_input,
        'titolo': risultato_ai.title,
        'descrizione': risultato_ai.description,
        'prezzo': risultato_ai.price,
        'categoria': None # Verrà aggiunto dopo
    }
    titolo_pulito = escape_markdown(risultato_ai.title, version=2)
    descrizione_pulita = escape_markdown(risultato_ai.description, version=2)
    prezzo_stringa = f"{risultato_ai.price} €"
    prezzo_pulito = escape_markdown(prezzo_stringa, version=2)
    
    risposta_anteprima = (
        f"✨ **Ecco la tua anteprima\\!** ✨\n\n"
        f"**Titolo:**\n{titolo_pulito}\n\n"
        f"**Descrizione:**\n{descrizione_pulita}\n\n"
        f"**Prezzo Suggerito:** {prezzo_pulito}"
    )
    
    await update.message.reply_text(risposta_anteprima, parse_mode='MarkdownV2')
    # 5. Chiediamo la conferma
    messaggio_inviato = await update.message.reply_text(
        "Il testo generato va bene o vuoi modificare qualcosa?",
        reply_markup=crea_tastiera_conferma_anteprima()
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    # 6. Passiamo al nuovo stato d'attesa
    return CREA_ATTESA_CONFERMA_ANTEPRIMA

async def crea_prosegui_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    L'utente ha premuto [✅ Sì, prosegui].
    Ora salviamo l'annuncio nel DB e chiediamo la categoria.
    """
    query = update.callback_query
    await query.answer()

    # Recuperiamo i dati dallo "zainetto"
    bozza = context.user_data.get('bozza_annuncio')
    id_utente_db = context.user_data.get('id_utente_db')

    if not bozza or not id_utente_db:
        await query.edit_message_text("Si è verificato un errore, i dati della bozza sono andati persi. Riprova.", reply_markup=crea_menu_principale())
        context.user_data.clear()
        return ConversationHandler.END

    # È qui che la bozza diventa un annuncio vero nel DB
    nuovo_id = add_annuncement(
        id_utente=id_utente_db,
        descrizione_input=bozza['descrizione_input'],
        titolo_generato=bozza['titolo'],
        descrizione_generata=bozza['descrizione'],
        prezzo_suggerito=bozza['prezzo'],
        id_categoria=None # Lo impostiamo al prossimo step
    )
    
    # Aggiorniamo lo "zainetto":
    # Rimuoviamo la bozza e salviamo l'ID reale
    context.user_data.pop('bozza_annuncio')
    context.user_data['id_annuncio_corrente'] = nuovo_id

    # Ora chiediamo la categoria
    messaggio_inviato = await query.edit_message_text(
        text="✅ Testo confermato e salvato! Ora scegli una categoria:",
        reply_markup=crea_tastiera_categorie()
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    
    # Passiamo allo stato successivo (che già esiste!)
    return CREA_ATTESA_CATEGORIA

async def crea_menu_modifica_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    L'utente ha premuto [✏️ Modifica Testo].
    Mostriamo il menu di modifica [Titolo] [Descrizione] [Prezzo].
    """
    query = update.callback_query
    await query.answer()
    
    messaggio_inviato = await query.edit_message_text(
        text="Cosa vuoi modificare?",
        reply_markup=crea_tastiera_menu_modifica()
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    # Passiamo allo stato "Menu Modifica"
    return CREA_MENU_MODIFICA

async def _mostra_menu_modifica(update: Update, context: ContextTypes.DEFAULT_TYPE, messaggio_intro: str) -> int:
    """Helper per mostrare il menu di modifica."""
    messaggio_inviato = None
    # Controlla se l'update è un click (query) o un messaggio di testo
    if update.callback_query:
        await update.callback_query.answer()
        messaggio_inviato = await update.callback_query.edit_message_text(
            text=messaggio_intro,
            reply_markup=crea_tastiera_menu_modifica()
        )
    else: # L'update è un messaggio di testo (es. l'utente ha inviato un nuovo titolo)
        messaggio_inviato = await update.message.reply_text(
            text=messaggio_intro,
            reply_markup=crea_tastiera_menu_modifica()
        )
    if messaggio_inviato:
        context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    return CREA_MENU_MODIFICA

async def crea_richiedi_nuovo_titolo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede all'utente il nuovo titolo, usando 'switch_inline_query_current_chat'."""
    query = update.callback_query
    await query.answer()
    
    titolo_attuale = context.user_data.get('bozza_annuncio', {}).get('titolo', '')

    tastiera_prefill = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Clicca qui per modificare il titolo", 
            switch_inline_query_current_chat=titolo_attuale
        )]])
    
    messaggio_inviato = await query.edit_message_text(
        text="Inviami il nuovo titolo.\n(Clicca il pulsante sotto per pre-compilare la casella di testo 👇)",
        reply_markup=tastiera_prefill
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    return CREA_ATTESA_NUOVO_TITOLO

async def crea_richiedi_nuova_descrizione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede all'utente la nuova descrizione, usando 'switch_inline_query_current_chat'."""
    query = update.callback_query
    await query.answer()
    
    desc_attuale = context.user_data.get('bozza_annuncio', {}).get('descrizione', '')

    tastiera_prefill = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Clicca qui per modificare la descrizione", 
            switch_inline_query_current_chat=desc_attuale
        )]])
    
    messaggio_inviato = await query.edit_message_text(
        text="Inviami la nuova descrizione.\n(Clicca il pulsante sotto per pre-compilare 👇)",
        reply_markup=tastiera_prefill
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    return CREA_ATTESA_NUOVA_DESCRIZIONE

async def crea_richiedi_nuovo_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede all'utente il nuovo prezzo, usando 'switch_inline_query_current_chat'."""
    query = update.callback_query
    await query.answer()
    
    prezzo_attuale = context.user_data.get('bozza_annuncio', {}).get('prezzo', 0.0)

    tastiera_prefill = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Clicca qui per modificare il prezzo", 
            switch_inline_query_current_chat=str(prezzo_attuale)
        )]])
    
    messaggio_inviato = await query.edit_message_text(
        text="Inviami il nuovo prezzo (solo il numero, es. 25.50).\n(Clicca il pulsante sotto per pre-compilare 👇)",
        reply_markup=tastiera_prefill
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    return CREA_ATTESA_NUOVO_PREZZO

async def crea_ricevi_nuovo_titolo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Riceve il nuovo titolo, lo salva nello 'zainetto' e torna al menu modifica."""
    nuovo_titolo = update.message.text
    prefisso_bot = f"@{context.bot.username} "
    
    if nuovo_titolo.startswith(prefisso_bot):
        nuovo_titolo = nuovo_titolo[len(prefisso_bot):]
    context.user_data['bozza_annuncio']['titolo'] = nuovo_titolo
    
    # Torniamo al menu di modifica
    return await _mostra_menu_modifica(update, context, "✅ Titolo aggiornato! Cosa vuoi modificare ora?")

async def crea_ricevi_nuova_descrizione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Riceve la nuova descrizione, la salva e torna al menu modifica."""
    nuova_descrizione = update.message.text
    prefisso_bot = f"@{context.bot.username} "

    if nuova_descrizione.startswith(prefisso_bot):
        nuova_descrizione = nuova_descrizione[len(prefisso_bot):]
    context.user_data['bozza_annuncio']['descrizione'] = nuova_descrizione
    
    return await _mostra_menu_modifica(update, context, "✅ Descrizione aggiornata! Cosa vuoi modificare ora?")

async def crea_ricevi_nuovo_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Riceve il nuovo prezzo, lo valida, lo salva e torna al menu modifica."""
    prezzo_testo = update.message.text
    prefisso_bot = f"@{context.bot.username} "

    if prezzo_testo.startswith(prefisso_bot):
        prezzo_testo = prezzo_testo[len(prefisso_bot):]
    try:
        nuovo_prezzo = float(prezzo_testo.replace(',', '.'))
        context.user_data['bozza_annuncio']['prezzo'] = nuovo_prezzo
        
        return await _mostra_menu_modifica(update, context, f"✅ Prezzo aggiornato a {nuovo_prezzo}€! Cosa vuoi modificare ora?")
    
    except ValueError:
        # Se l'utente non scrive un numero
        await update.message.reply_text(
            "Errore 😅 Quello non è un numero valido. Riprova (es. 25 o 14.50)."
        )
        return CREA_ATTESA_NUOVO_PREZZO # Rimaniamo nello stato di attesa prezzo

async def crea_modifica_fatto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    L'utente ha finito di modificare. 
    Mostra di nuovo l'anteprima aggiornata e i pulsanti di conferma.
    """
    query = update.callback_query
    await query.answer()
    
    bozza = context.user_data.get('bozza_annuncio')
    
    if not bozza:
        await query.edit_message_text("Si è verificato un errore, i dati della bozza sono andati persi. Riprova.", reply_markup=crea_menu_principale())
        context.user_data.clear()
        return ConversationHandler.END

    # Ricostruiamo l'anteprima con i dati modificati
    titolo_pulito = escape_markdown(bozza['titolo'], version=2)
    descrizione_pulita = escape_markdown(bozza['descrizione'], version=2)
    prezzo_stringa = f"{bozza['prezzo']} €"
    prezzo_pulito = escape_markdown(prezzo_stringa, version=2)

    risposta_anteprima = (
        f"✨ **Ecco la tua anteprima aggiornata\\!** ✨\n\n"
        f"**Titolo:**\n{titolo_pulito}\n\n"
        f"**Descrizione:**\n{descrizione_pulita}\n\n"
        f"**Prezzo Suggerito:** {prezzo_pulito}\n\n"
        "Il testo va bene ora?"
    )
    
    messaggio_inviato = await query.edit_message_text(
        text=risposta_anteprima,
        reply_markup=crea_tastiera_conferma_anteprima(),
        parse_mode='MarkdownV2'
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    # Torniamo allo stato di conferma
    return CREA_ATTESA_CONFERMA_ANTEPRIMA

async def ricevi_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Questa funzione si attiva quando l'utente preme un pulsante di categoria.
    """
    query = update.callback_query
    await query.answer() # Risponde al "click" per far sparire l'icona di caricamento

    # Estraiamo l'ID della categoria dal pulsante (es. "cat_1" -> "1")
    id_categoria_scelta = int(query.data.split('_')[1])
    context.user_data['id_categoria_scelta'] = id_categoria_scelta
    messaggio_inviato = await query.edit_message_text(
        text=f"✅ Categoria scelta! Ora scegli su quale piattaforma vuoi pubblicare:",
        reply_markup=crea_tastiera_piattaforme()
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    # Diciamo al ConversationHandler di passare allo stato "CREA_ATTESA_DATA"
    return CREA_ATTESA_PIATTAFORMA

async def ricevi_piattaforma(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Riceve la piattaforma e chiede la data di programmazione.
    """
    query = update.callback_query
    await query.answer() 

    id_piattaforma_scelta = int(query.data.split('_')[1])

    # Salviamo la piattaforma nello "zainetto"
    context.user_data['id_piattaforma_scelta'] = id_piattaforma_scelta

    # Modifichiamo il messaggio e chiediamo la data
    await query.edit_message_text(text=f"✅ Piattaforma scelta!")

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Scrivimi una data e un'ora per la programmazione (es: 'domani alle 15:00')."
    )

    # Passiamo allo stato CREA_ATTESA_DATA
    return CREA_ATTESA_DATA

async def ricevi_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Questa funzione si attiva quando l'utente invia un testo nello stato CREA_ATTESA_DATA.
    """
    testo_data = update.message.text
    data_programmata = parse_date_regex(testo_data)
    
    if not data_programmata:
        await update.message.reply_text(
            "Non ho capito la data. 😅 Riprova (es. 'domani alle 15:00', 'tra 2 giorni alle 21')."
        )
        return CREA_ATTESA_DATA # Rimaniamo nello stesso stato

    # Recuperiamo i dati dalla memoria
    id_annuncio = context.user_data.get('id_annuncio_corrente')
    id_categoria = context.user_data.get('id_categoria_scelta')
    id_piattaforma = context.user_data.get('id_piattaforma_scelta')

    if not id_annuncio or not id_categoria:
        await update.message.reply_text("Si è verificato un errore, i dati dell'annuncio sono andati persi. Riprova con /start.")
        context.user_data.clear()
        return ConversationHandler.END

    # Aggiorniamo il database con TUTTE le informazioni
    aggiorna_annuncio_con_programmazione(id_annuncio, id_categoria, id_piattaforma, data_programmata)

    await update.message.reply_text(
        f"Perfetto! 👍 Annuncio {id_annuncio} salvato e programmato per:\n"
        f"**{data_programmata.strftime('%d %B %Y alle %H:%M')}** \n\nTi invierò una notifica 30 minuti prima e all'ora esatta.",
        parse_mode='Markdown',
        reply_markup=crea_menu_principale()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


# --- SEGNA VENDUTO ---  
async def vendi_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    annunci_non_venduti = ottieni_annunci_non_venduti(id_utente_db)
    
    if not annunci_non_venduti:
        await update.message.reply_text(
            "Non hai annunci attivi da segnare come venduti.",
            reply_markup=crea_menu_principale()
        )
        return ConversationHandler.END
    conteggio = len(annunci_non_venduti)
    messaggio_intro = f"Hai {conteggio} annunci attivi.\nQuale hai venduto?(Selezionalo dalla lista)"
    # Costruiamo i pulsanti in linea
    tastiera_annunci = []
    for annuncio in annunci_non_venduti:
        # Usiamo un prefisso 'vendi_' per il callback_data
        callback_data = f"vendi_{annuncio['id']}"
        titolo = annuncio['titolo_generato']
        id_formattato = f"#{annuncio['id']:04d}"
        testo_pulsante = f"🏷️ {id_formattato} - {titolo}"
        # Tronchiamo il titolo se è troppo lungo per un pulsante
        testo_pulsante_piccolo = (testo_pulsante[:40] + '...') if len(testo_pulsante) > 40 else testo_pulsante
        
        tastiera_annunci.append(
            [InlineKeyboardButton(testo_pulsante_piccolo, callback_data=callback_data)]
        )

    messaggio_inviato = await update.message.reply_text(
        messaggio_intro,
        reply_markup=InlineKeyboardMarkup(tastiera_annunci)
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    # Entriamo nel primo stato del wizard di vendita
    return VENDI_ATTESA_SCELTA

async def vendi_ricevi_scelta_annuncio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Riceve il click sul pulsante dell'annuncio.
    Chiede A QUANTO è stato venduto.
    """
    query = update.callback_query
    await query.answer()

    # Estraiamo l'ID (es. "vendi_14" -> "14")
    id_annuncio_scelto = int(query.data.split('_')[1])
    
    # Salviamo l'ID nello "zainetto" per il prossimo step
    context.user_data['id_annuncio_da_vendere'] = id_annuncio_scelto
    
    await query.edit_message_text(text=f"Ottimo! Annuncio {id_annuncio_scelto} selezionato.\n\nA che prezzo (in euro) l'hai venduto? Scrivi solo il numero (es. `25.50`):")
    
    # Passiamo al secondo stato
    return VENDI_ATTESA_PREZZO

async def vendi_ricevi_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Riceve il prezzo finale, aggiorna il DB e conclude.
    """
    prezzo_testo = update.message.text
    
    # Autentichiamo l'utente un'ultima volta per sicurezza
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    try:
        prezzo_finale = float(prezzo_testo.replace(',', '.'))
        id_annuncio = context.user_data.get('id_annuncio_da_vendere')

        if not id_annuncio:
            raise ValueError("ID annuncio non trovato nella sessione.")

        successo = segna_come_venduto(id_utente_db, id_annuncio, prezzo_finale)

        if successo:
            id_formattato = f"#{id_annuncio:04d}"
            await update.message.reply_text(
                f"🎉 Congratulazioni!\nAnnuncio **{id_formattato}** segnato come VENDUTO a **{prezzo_finale}€**.",
                parse_mode='Markdown',
                reply_markup=crea_menu_principale()
            )
        else:
            await update.message.reply_text(
                "❌ Operazione fallita. Non ho trovato un annuncio con quell'ID che ti appartiene.",
                reply_markup=crea_menu_principale()
            )

    except ValueError:
        await update.message.reply_text(
            "Non ho capito. 😅 Per favore, scrivi solo il numero (es. `25` o `14.50`)."
        )
        return VENDI_ATTESA_PREZZO # Rimaniamo nello stato
    
    # Puliamo lo "zainetto" e terminiamo
    context.user_data.clear()
    return ConversationHandler.END


# ---ELIMINA UN ANNUNCIO ---
async def elimina_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inizia il wizard /elimina.
    Chiede all'utente QUALE annuncio vuole eliminare.
    """
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    # Riutilizziamo la funzione che abbiamo scritto per /lista!
    annunci_attivi = ottieni_annunci_utente(id_utente_db)
    
    if not annunci_attivi:
        await update.message.reply_text(
            "Non hai annunci attivi da eliminare.",
            reply_markup=crea_menu_principale()
        )
        return ConversationHandler.END

    tastiera_annunci = []
    for annuncio in annunci_attivi:
        # Usiamo un prefisso 'elimina_' per il callback
        callback_data = f"elimina_{annuncio['id']}"
        id_formattato = f"#{annuncio['id']:04d}"
        titolo = annuncio['titolo_generato']
        
        testo_pulsante = f"🏷️ {id_formattato} - {titolo}"
        testo_pulsante_corto = (testo_pulsante[:40] + '...') if len(testo_pulsante) > 40 else testo_pulsante
        
        tastiera_annunci.append(
            [InlineKeyboardButton(testo_pulsante_corto, callback_data=callback_data)]
        )

    messaggio_inviato = await update.message.reply_text(
        f"Hai {len(annunci_attivi)} annunci attivi.\nQuale vuoi eliminare?",
        reply_markup=InlineKeyboardMarkup(tastiera_annunci)
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id

    return ELIMINA_ATTESA_SCELTA

async def elimina_ricevi_scelta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    L'utente ha scelto un annuncio. Chiediamo la conferma finale.
    """
    query = update.callback_query
    await query.answer()

    id_annuncio_scelto = int(query.data.split('_')[1])
    
    # --- MODIFICA CHIAVE ---
    # Invia il messaggio E salva l'oggetto "messaggio" in una variabile
    messaggio_inviato = await query.edit_message_text(
        text=f"Sei assolutamente sicuro di voler eliminare l'annuncio `#{id_annuncio_scelto:04d}`?\n\nL'azione non può essere annullata.",
        reply_markup=crea_tastiera_conferma_elimina(id_annuncio_scelto),
        parse_mode='Markdown'
    )
    
    # Salviamo l'ID di questo messaggio nello "zainetto"
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    # --- FINE MODIFICA ---
    
    return ELIMINA_ATTESA_CONFERMA

async def elimina_esegui_conferma(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    L'utente ha premuto [Sì, Elimina].
    Eseguiamo il 'soft delete' e terminiamo.
    """
    query = update.callback_query
    await query.answer()

    id_annuncio_da_eliminare = int(query.data.split('_')[-1]) # Estrae l'ID
    
    # Autentichiamo l'utente
    user = query.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    # Riutilizziamo la funzione di 'soft delete' che abbiamo già scritto!
    successo = disattiva_annuncio(id_utente_db, id_annuncio_da_eliminare)

    if successo:
        await query.edit_message_text(text=f"🗑️ Annuncio `#{id_annuncio_da_eliminare:04d}` eliminato con successo.")
    else:
        await query.edit_message_text(text="❌ Errore: Annuncio non trovato o non ti appartiene.")
    
    # Mandiamo un messaggio separato per ri-mostrare il menu principale
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Ritorno al menu principale.",
        reply_markup=crea_menu_principale()
    )
    context.user_data.clear()
    return ConversationHandler.END


# --- MODIFICA ANNUNCIO ---
async def modifica_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inizia il wizard /modifica. 
    Chiede all'utente QUALE annuncio vuole modificare.
    """
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    annunci_attivi = ottieni_annunci_utente(id_utente_db)
    
    if not annunci_attivi:
        await update.message.reply_text("Non hai annunci attivi da modificare.", reply_markup=crea_menu_principale())
        return ConversationHandler.END

    tastiera_annunci = []
    for annuncio in annunci_attivi:
        callback_data = f"modifica_{annuncio['id']}" # Prefisso 'modifica_'
        id_formattato = f"#{annuncio['id']:04d}"
        titolo = annuncio['titolo_generato']
        
        testo_pulsante = f"🏷️ {id_formattato} - {titolo}"
        testo_pulsante_corto = (testo_pulsante[:40] + '...') if len(testo_pulsante) > 40 else testo_pulsante
        
        tastiera_annunci.append([InlineKeyboardButton(testo_pulsante_corto, callback_data=callback_data)])

    messaggio_menu_modifica = await update.message.reply_text(
        f"Hai {len(annunci_attivi)} annunci.\nQuale vuoi modificare?",
        reply_markup=InlineKeyboardMarkup(tastiera_annunci)
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_menu_modifica.message_id
    
    return MODIFICA_ATTESA_SCELTA_ANNUNCIO

async def modifica_ricevi_scelta_annuncio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    L'utente ha scelto un annuncio. Salviamo l'ID e mostriamo il menu di modifica.
    """
    query = update.callback_query
    await query.answer()

    id_annuncio_scelto = int(query.data.split('_')[1])
    
    # Salviamo l'ID nello "zainetto" per tutti i prossimi step
    context.user_data['id_annuncio_da_modificare'] = id_annuncio_scelto
    
    messaggio_menu_modifica = await query.edit_message_text(
        text=f"Hai selezionato l'annuncio `#{id_annuncio_scelto:04d}`.\n\nCosa vuoi modificare?",
        # Riusiamo la stessa tastiera del wizard di creazione!
        reply_markup=crea_tastiera_menu_modifica(), 
        parse_mode='Markdown'
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_menu_modifica.message_id
    return MODIFICA_MENU_CAMPI

async def _mostra_menu_modifica_esistente(update: Update, context: ContextTypes.DEFAULT_TYPE, messaggio_intro: str) -> int:
    """Helper per mostrare il menu di modifica DOPO un aggiornamento."""
    # Questo è quasi identico a _mostra_menu_modifica, ma non possiamo riusarlo
    # perché lo stato di ritorno (MODIFICA_MENU_CAMPI) è diverso.
    messaggio_menu_modifica = None
    if update.callback_query:
        await update.callback_query.answer()
        messaggio_menu_modifica = await update.callback_query.edit_message_text(
            text=messaggio_intro,
            reply_markup=crea_tastiera_menu_modifica()
        )
    else: 
        messaggio_menu_modifica = await update.message.reply_text(
            text=messaggio_intro,
            reply_markup=crea_tastiera_menu_modifica()
        )
    if messaggio_menu_modifica:
        context.user_data['messaggio_con_pulsanti_id'] = messaggio_menu_modifica.message_id
    return MODIFICA_MENU_CAMPI

async def modifica_richiedi_nuovo_titolo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede il nuovo titolo, pre-compilandolo con quello attuale dal DB."""
    query = update.callback_query
    await query.answer()
    
    id_utente_db = get_or_create_user(query.from_user.id, query.from_user.first_name)
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    annuncio = ottieni_dettagli_annuncio(id_utente_db, id_annuncio)
    titolo_attuale = annuncio['titolo_generato'] if annuncio else ''

    tastiera_prefill = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Clicca qui per modificare il titolo", 
            switch_inline_query_current_chat=titolo_attuale
        )]])
    
    messaggio_menu_modifica = await query.edit_message_text(
        text="Inviami il nuovo titolo.\n(Clicca il pulsante sotto per pre-compilare 👇)",
        reply_markup=tastiera_prefill
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_menu_modifica.message_id
    return MODIFICA_ATTESA_NUOVO_TITOLO

async def modifica_richiedi_nuova_descrizione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede la nuova descrizione, pre-compilandola con quella attuale."""
    query = update.callback_query
    await query.answer()
    
    id_utente_db = get_or_create_user(query.from_user.id, query.from_user.first_name)
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    annuncio = ottieni_dettagli_annuncio(id_utente_db, id_annuncio)
    desc_attuale = annuncio['descrizione_generata'] if annuncio else ''

    tastiera_prefill = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Clicca qui per modificare la descrizione", 
            switch_inline_query_current_chat=desc_attuale
        )]])
    
    messaggio_menu_modifica = await query.edit_message_text(
        text="Inviami la nuova descrizione.\n(Clicca il pulsante sotto per pre-compilare 👇)",
        reply_markup=tastiera_prefill
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_menu_modifica.message_id

    return MODIFICA_ATTESA_NUOVA_DESCRIZIONE

async def modifica_richiedi_nuovo_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiede il nuovo prezzo, pre-compilandolo con quello attuale."""
    query = update.callback_query
    await query.answer()
    
    id_utente_db = get_or_create_user(query.from_user.id, query.from_user.first_name)
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    annuncio = ottieni_dettagli_annuncio(id_utente_db, id_annuncio)
    prezzo_attuale = annuncio['prezzo_suggerito'] if annuncio else 0.0

    tastiera_prefill = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="Clicca qui per modificare il prezzo", 
            switch_inline_query_current_chat=str(prezzo_attuale) # Convertiamo il float in stringa
        )]])
    
    messaggio_menu_modifica = await query.edit_message_text(
        text="Inviami il nuovo prezzo (solo il numero, es. 25.50).\n(Clicca il pulsante sotto per pre-compilare 👇)",
        reply_markup=tastiera_prefill
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_menu_modifica.message_id

    return MODIFICA_ATTESA_NUOVO_PREZZO

async def modifica_ricevi_nuovo_titolo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Riceve il nuovo titolo, lo pulisce, lo SALVA SUL DB e torna al menu modifica."""
    testo_pulito = update.message.text
    prefisso_bot = f"@{context.bot.username} "
    if testo_pulito.startswith(prefisso_bot):
        testo_pulito = testo_pulito[len(prefisso_bot):]

    id_utente_db = get_or_create_user(update.message.from_user.id, update.message.from_user.first_name)
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    # Aggiorniamo il DB immediatamente
    aggiorna_campo_annuncio(id_utente_db, id_annuncio, 'titolo_generato', testo_pulito)
    
    return await _mostra_menu_modifica_esistente(update, context, "✅ Titolo aggiornato! Vuoi modificare altro?")

async def modifica_ricevi_nuova_descrizione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Riceve la nuova descrizione, la pulisce, la SALVA SUL DB e torna al menu modifica."""
    
    desc_pulita = update.message.text
    prefisso_bot = f"@{context.bot.username} "
    if desc_pulita.startswith(prefisso_bot):
        desc_pulita = desc_pulita[len(prefisso_bot):]

    id_utente_db = get_or_create_user(update.message.from_user.id, update.message.from_user.first_name)
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    # Aggiorniamo il DB immediatamente
    aggiorna_campo_annuncio(id_utente_db, id_annuncio, 'descrizione_generata', desc_pulita)
    
    return await _mostra_menu_modifica_esistente(update, context, "✅ Descrizione aggiornata! Vuoi modificare altro?")

async def modifica_ricevi_nuovo_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Riceve il nuovo prezzo, lo pulisce, lo VALIDA, lo SALVA SUL DB e torna al menu modifica."""
    
    prezzo_testo = update.message.text
    prefisso_bot = f"@{context.bot.username} "
    if prezzo_testo.startswith(prefisso_bot):
        prezzo_testo = prezzo_testo[len(prefisso_bot):]

    id_utente_db = get_or_create_user(update.message.from_user.id, update.message.from_user.first_name)
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    try:
        nuovo_prezzo = float(prezzo_testo.replace(',', '.'))
        
        # Aggiorniamo il DB immediatamente
        aggiorna_campo_annuncio(id_utente_db, id_annuncio, 'prezzo_suggerito', nuovo_prezzo)
        
        return await _mostra_menu_modifica_esistente(update, context, f"✅ Prezzo aggiornato a {nuovo_prezzo}€! Vuoi modificare altro?")
    
    except ValueError:
        # Se l'utente non scrive un numero
        await update.message.reply_text(
            "Errore 😅 Quello non è un numero valido. Riprova (es. 25 o 14.50)."
        )
        return MODIFICA_ATTESA_NUOVO_PREZZO # Rimaniamo nello stato

async def modifica_fatto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """L'utente ha finito di modificare. Pulisce lo zainetto e torna al menu."""
    query = update.callback_query
    await query.answer()
    
    id_annuncio = context.user_data.get('id_annuncio_da_modificare')
    
    await query.edit_message_text(text=f"Modifiche all'annuncio `#{id_annuncio:04d}` salvate.", parse_mode='Markdown')
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Ritorno al menu principale.",
        reply_markup=crea_menu_principale()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# --- DETTAGLI ANNUNCIO ---
async def dettagli_wizard_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mostra la lista di annunci per vederne i dettagli."""
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    # Riusiamo la funzione che prende tutti gli annunci attivi
    annunci = ottieni_annunci_utente(id_utente_db)
    
    if not annunci:
        await update.message.reply_text("Nessun annuncio trovato.", reply_markup=crea_menu_principale())
        return ConversationHandler.END

    tastiera = []
    for annuncio in annunci:
        callback_data = f"dettagli_{annuncio['id']}"
        testo = f"🏷️ #{annuncio['id']:04d} - {annuncio['titolo_generato'][:30]}..."
        tastiera.append([InlineKeyboardButton(testo, callback_data=callback_data)])

    messaggio_inviato = await update.message.reply_text(
        "Di quale annuncio vuoi vedere i dettagli completi?",
        reply_markup=InlineKeyboardMarkup(tastiera)
    )
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id

    
    return DETTAGLI_ATTESA_SCELTA

async def dettagli_mostra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mostra la scheda completa dell'annuncio selezionato."""
    query = update.callback_query
    await query.answer()
    
    id_annuncio = int(query.data.split('_')[1])
    user = query.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    
    annuncio = ottieni_dettagli_annuncio(id_utente_db, id_annuncio)
    
    if not annuncio:
        await query.edit_message_text("Errore: Annuncio non trovato.")
        return ConversationHandler.END

    # Formattazione dei dati per la visualizzazione
    stato = annuncio['nome_stato'].upper() if annuncio['nome_stato'] else "N/D"
    piattaforma = annuncio['nome_piattaforma'].capitalize() if annuncio['nome_piattaforma'] else "N/D"
    categoria = annuncio['categoria'].capitalize() if annuncio['categoria'] else "N/D"
    data_creazione = annuncio['data_creazione'][:16] # Prende solo YYYY-MM-DD HH:MM
    
    scheda = (
        f"📄 SCHEDA ANNUNCIO #{annuncio['id']:04d}\n"
        f"Stato: {stato}\n"
        f"Creato il: {data_creazione}\n\n"
        f"📢 Titolo:\n{annuncio['titolo_generato']}\n\n"
        f"📝 Descrizione:\n{annuncio['descrizione_generata']}\n\n"
        f"💰 Prezzo Suggerito: {annuncio['prezzo_suggerito']} €\n"
        f"🏷️ Categoria: {categoria}\n"
        f"📱 Piattaforma: {piattaforma}\n"
    )
    
    # Aggiungiamo info extra se ci sono
    if annuncio['data_pubblicazione']:
        data_prog = isoparse(annuncio['data_pubblicazione'])
        data_formattata = data_prog.strftime('%d/%m/%Y alle %H:%M') # Es. 03/11/2025 alle 10:41
        scheda += f"🗓️ Programmato per: {data_formattata}\n"
    if annuncio['prezzo_vendita']:
        scheda += f"🎉 Venduto a: {annuncio['prezzo_vendita']} €\n"

    # Inviamo il messaggio (usiamo Markdown semplice per evitare errori con testi strani)
    # Aggiungiamo un pulsante "Indietro" per tornare al menu principale
    tastiera_indietro = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Torna al Menu", callback_data="dettagli_chiudi")]])
    
    messaggio_inviato = await query.edit_message_text(
        scheda,
        parse_mode=None, 
        reply_markup=tastiera_indietro
    ) # parse_mode=None è più sicuro per testi lunghi imprevedibili
    
    context.user_data['messaggio_con_pulsanti_id'] = messaggio_inviato.message_id
    
    return DETTAGLI_ATTESA_SCELTA # Rimaniamo in attesa per gestire il bottone "Indietro"

async def dettagli_chiudi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chiude la visualizzazione dettagli."""
    query = update.callback_query
    await query.answer()
    await query.delete_message() # Cancella la scheda
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Ritorno al menu principale.",
        reply_markup=crea_menu_principale()
    )
    return ConversationHandler.END

#HANDLER
# --- LISTA ANNUNCI ---
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
        conteggio = len(annunci)
        messaggio_risposta = f"📑 **I Tuoi {conteggio} Annunci** 📑\n\n"
        
        for annuncio in annunci:
            titolo = annuncio['titolo_generato'] if annuncio['titolo_generato'] else "Senza Titolo"
            stato = annuncio['nome_stato'].capitalize() if annuncio['nome_stato'] else "Bozza"
            
            # Formattiamo un bel titolo per ogni annuncio
            id_formattato = f"#{annuncio['id']:04d}" 
            messaggio_risposta += f"🏷️ **Rif:** `{id_formattato}`\n"
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

# --- ANALISI ---
async def analisi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Ricevuto comando /analisi")
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
    await update.message.reply_chat_action(action="upload_photo")
    try:
        statistiche = ottieni_statistiche_avanzate(id_utente_db)

        if not statistiche or statistiche['totale_annunci'] == 0:
            await update.message.reply_text("Nessun annuncio ancora nel database. Inizia a creare!")
            return
        totale_annunci = statistiche['totale_annunci']
        totale_vendite = statistiche['totale_vendite']
        guadagno_totale = statistiche['guadagno_totale']

        tasso_conversione = (totale_vendite / totale_annunci) * 100 if totale_annunci > 0 else 0
        prezzo_medio_vendita = guadagno_totale / totale_vendite if totale_vendite > 0 else 0

        # --- Costruzione del Messaggio di Risposta ---
        messaggio = "📊 **La Tua Dashboard Vendite** 📊\n\n"
        
        messaggio += "--- **Panoramica** ---\n"
        messaggio += f"•  Annunci Totali: **{totale_annunci}**\n"
        messaggio += f"•  Annunci Attivi: **{statistiche['totale_programmati']}**\n"
        messaggio += f"•  Annunci Venduti: **{totale_vendite}**\n"
        messaggio += f"•  Tasso di Conversione: **{tasso_conversione:.1f}%**\n\n"

        messaggio += "--- **Guadagni Reali** 💰 ---\n"
        messaggio += f"•  Guadagno Totale: **{guadagno_totale:.2f} €**\n"
        messaggio += f"•  Guadagno Ultimo Mese: **{statistiche['guadagno_mese']:.2f} €**\n"
        messaggio += f"•  Guadagno Ultimo Anno: **{statistiche['guadagno_anno']:.2f} €**\n"
        messaggio += f"•  Prezzo Medio Vendita: **{prezzo_medio_vendita:.2f} €**\n\n"
        
        messaggio += "--- **Potenziale Futuro** 🔮 ---\n"
        messaggio += f"•  Valore Stimato Annunci Attivi: **{statistiche['stima_guadagno_futuro']:.2f} €**\n"
        
        grafico_buffer = genera_grafico_vendite(id_utente_db)

        # --- 3. Invio (Combinato o Solo Testo) ---
        if grafico_buffer:
            # Diamo un nome al file in memoria, così Telegram sa che è un'immagine
            grafico_buffer.name = "grafico_vendite.png"
            
            await update.message.reply_photo(
                photo=grafico_buffer,
                caption=messaggio,
                parse_mode='Markdown'
            )
        else:
            # Se non abbiamo vendite (quindi niente grafico a torta), inviamo solo il testo
            await update.message.reply_text(messaggio, parse_mode='Markdown')

    except Exception as e:
        print(f"Errore durante /analisi: {e}")
        await update.message.reply_text(f"Si è verificato un errore durante la generazione delle statistiche: {e}")


# --- AIUTO / ANNULLA ---
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


# --- UTIL ---
async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Annulla la conversazione corrente, prova a eliminare la bozza
    e ritorna al menu principale.
    """
    messaggio_feedback = "Operazione annullata. Ritorno al menu principale."
    
    # Controlliamo se la bozza è in memoria (context) per pulirla
    if 'bozza_annuncio' in context.user_data:
        context.user_data.pop('bozza_annuncio')
        messaggio_feedback = "Operazione annullata. La bozza è stata eliminata."
    
    # Controlliamo se c'è un annuncio già salvato (per i flussi futuri)
    if 'id_annuncio_corrente' in context.user_data:
        context.user_data.pop('id_annuncio_corrente')

    id_messaggio_zombie = context.user_data.get('messaggio_con_pulsanti_id')        
    if id_messaggio_zombie:
        try:
            # Modifica il vecchio messaggio (lo zombie) per togliere i pulsanti
            await context.bot.edit_message_text(
                text="Operazione annullata dall'utente.",
                chat_id=update.effective_chat.id,
                message_id=id_messaggio_zombie
            )
        except Exception as e:
            # Non fa nulla se il messaggio è troppo vecchio o già eliminato
            print(f"Info: Impossibile editare il messaggio zombie: {e}")
    # Controlliamo se l'update proviene da un click su pulsante (CallbackQuery)
    if update.callback_query:
        await update.callback_query.answer() # Risponde al click
        # Modifica il messaggio (togliendo i pulsanti)
        await update.callback_query.edit_message_text(text=messaggio_feedback)
        # Invia un nuovo messaggio per mostrare il menu principale
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text="Sei nel menu principale.",
            reply_markup=crea_menu_principale()
        )
    else:
        # L'update proviene da un messaggio di testo (es. /annulla)
        await update.message.reply_text(
            messaggio_feedback,
            reply_markup=crea_menu_principale()
        )
    
    # Puliamo l'intero "zainetto" per sicurezza
    context.user_data.clear()
    return ConversationHandler.END

async def gestisci_testo_sconosciuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Risponde a qualsiasi messaggio di testo non riconosciuto."""
    await update.message.reply_text(
        "Non ho capito... 😅\n"
        "Usa i pulsanti del menu qui sotto per dirmi cosa fare.",
        reply_markup=crea_menu_principale()
    )    

async def gestisci_testo_sconosciuto_in_conversazione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Risponde a un pulsante del menu premuto mentre si è in uno stato di attesa."""
    await update.message.reply_text(
        "Stai completando un'altra operazione! 😅\n"
        "Per favore, finisci l'inserimento o premi '❓ Aiuto / Annulla' per uscire.",
        reply_markup=update.message.reply_markup # Mantiene la tastiera (o la rimuove se non c'è)
    )

def parse_date_regex(text):
    """
    Parses Italian date/time strings using regex and Python logic.
    Prefers future dates.
    """
    now = datetime.datetime.now()
    text_lower = text.lower().strip()
    target_date = None

    # Pattern 1: "tra X minuti/ore"
    match = re.search(r"tra\s+(\d+)\s+(minut[oi]|or[ae])", text_lower)
    if match:
        quantita = int(match.group(1))
        unita = match.group(2)
        if unita.startswith("minut"):
            target_date = now + timedelta(minutes=quantita)
        else: # ore
            target_date = now + timedelta(hours=quantita)
        return target_date

    # Pattern 2: "domani alle HH[:MM]"
    match = re.search(r"domani\s+alle\s+(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        ora = int(match.group(1))
        minuti = int(match.group(2) or 0) # Default to 0 if minutes are omitted
        if 0 <= ora <= 23 and 0 <= minuti <= 59:
            domani = now.date() + timedelta(days=1)
            target_date = datetime.datetime(domani.year, domani.month, domani.day, ora, minuti)
            return target_date

    # Pattern 3: "tra X giorni alle HH[:MM]"
    match = re.search(r"tra\s+(\d+)\s+giorni\s+alle\s+(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        giorni = int(match.group(1))
        ora = int(match.group(2))
        minuti = int(match.group(3) or 0)
        if 0 <= ora <= 23 and 0 <= minuti <= 59:
            giorno_futuro = now.date() + timedelta(days=giorni)
            target_date = datetime.datetime(giorno_futuro.year, giorno_futuro.month, giorno_futuro.day, ora, minuti)
            return target_date

    # Pattern 4: "giorno_settimana prossimo alle HH[:MM]"
    match = re.search(r"([a-zì]+)\s+prossim[oi]\s+(?:alle\s+)?(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        nome_giorno = match.group(1)
        ora = int(match.group(2))
        minuti = int(match.group(3) or 0)
        if nome_giorno in giorni_settimana and 0 <= ora <= 23 and 0 <= minuti <= 59:
            giorno_target_num = giorni_settimana[nome_giorno]
            giorni_da_aggiungere = (giorno_target_num - now.weekday() + 7) % 7
            if giorni_da_aggiungere == 0: # If it's today, go to next week
                 giorni_da_aggiungere = 7
            giorno_futuro = now.date() + timedelta(days=giorni_da_aggiungere)
            target_date = datetime.datetime(giorno_futuro.year, giorno_futuro.month, giorno_futuro.day, ora, minuti)
            return target_date

    # Pattern 5: "alle HH[:MM]" (prefer future)
    match = re.search(r"alle\s+(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        ora = int(match.group(1))
        minuti = int(match.group(2) or 0)
        if 0 <= ora <= 23 and 0 <= minuti <= 59:
            ora_target = datetime.time(ora, minuti)
            ora_attuale = now.time()
            if ora_target > ora_attuale:
                # Same day, future time
                target_date = datetime.datetime.combine(now.date(), ora_target)
            else:
                # Next day
                domani = now.date() + timedelta(days=1)
                target_date = datetime.datetime.combine(domani, ora_target)
            return target_date

    # Pattern 6: "il GG mese alle HH[:MM]" or "GG mese HH:MM" or "GG mese alle HH"
    match = re.search(r"(?:il\s+)?(\d{1,2})\s+([a-zì]+)\s+(?:alle\s+)?(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        giorno = int(match.group(1))
        nome_mese = match.group(2)
        ora = int(match.group(3))
        minuti = int(match.group(4) or 0)
        if nome_mese in mesi and 1 <= giorno <= 31 and 0 <= ora <= 23 and 0 <= minuti <= 59:
            mese = mesi[nome_mese]
            anno = now.year
            # Basic logic: if month is in the past, assume next year
            if mese < now.month or (mese == now.month and giorno < now.day):
                anno += 1
            try:
                target_date = datetime.datetime(anno, mese, giorno, ora, minuti)
                return target_date
            except ValueError: # Invalid date like Feb 30
                pass # Try next pattern

    # Fallback/Default: if no pattern matched
    return None

def genera_grafico_vendite(id_utente_db):
    """
    Genera un grafico a torta delle vendite in memoria.
    Usa indici numerici perché la query restituisce tuple.
    """
    dati_grafico = ottieni_dati_grafico_categorie(id_utente_db)
    
    if not dati_grafico:
        return None

    # Preparazione dati usando gli indici numerici delle tuple
    # riga[0] = nome categoria, riga[1] = conteggio
    categorie = [riga[0] if riga[0] else "Altro" for riga in dati_grafico]
    valori = [riga[1] for riga in dati_grafico]

    # Creazione Grafico
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(6, 6))
    plt.pie(valori, labels=categorie, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("pastel"))
    plt.title('Le tue Vendite per Categoria')
    
    # Salvataggio nel buffer in memoria
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    return buffer
# --- FUNZIONE DI AVVIO ---
def bot_start():
    """Crea l'applicazione e avvia il bot con il menu principale."""
    application = Application.builder().token(TOKEN).build()

    main_conversation_handler = ConversationHandler(
        entry_points=[
            #MessageHandler(filters.PHOTO, foto_handler),
            MessageHandler(filters.Text(T_CREA), nuovo_annuncio_handler_testo_guida),
            MessageHandler(filters.Text(T_VENDI), vendi_wizard_start),
            MessageHandler(filters.Text(T_ELIMINA), elimina_wizard_start),
            MessageHandler(filters.Text(T_MODIFICA), modifica_wizard_start),
            MessageHandler(filters.Text(T_DETTAGLI), dettagli_wizard_start)
        ],
        states={
            # --- FLUSSO DI CREAZIONE ---
            CREA_ATTESA_FOTO: [
                MessageHandler(filters.PHOTO, foto_handler),
            ],
            CREA_ATTESA_CONFERMA_ANTEPRIMA: [
                CallbackQueryHandler(crea_prosegui_handler, pattern="^crea_conferma_si$"),
                CallbackQueryHandler(crea_menu_modifica_handler, pattern="^crea_conferma_modifica$"),
                CallbackQueryHandler(annulla, pattern="^crea_conferma_annulla$")
            ],
            CREA_MENU_MODIFICA: [
                CallbackQueryHandler(crea_richiedi_nuovo_titolo, pattern="^crea_modifica_titolo$"),
                CallbackQueryHandler(crea_richiedi_nuova_descrizione, pattern="^crea_modifica_desc$"),
                CallbackQueryHandler(crea_richiedi_nuovo_prezzo, pattern="^crea_modifica_prezzo$"),
                CallbackQueryHandler(crea_modifica_fatto, pattern="^crea_modifica_fatto$")            
            ],
            CREA_ATTESA_NUOVO_TITOLO: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, crea_ricevi_nuovo_titolo)
            ],
            CREA_ATTESA_NUOVA_DESCRIZIONE: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, crea_ricevi_nuova_descrizione)
            ],
            CREA_ATTESA_NUOVO_PREZZO: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, crea_ricevi_nuovo_prezzo)
            ],
            CREA_ATTESA_CATEGORIA: [
                MessageHandler(filters.Text([T_LISTA, T_ANALISI, T_VENDI, T_CREA]), gestisci_testo_sconosciuto_in_conversazione),
                CallbackQueryHandler(ricevi_categoria, pattern="^cat_") 
            ],
            CREA_ATTESA_PIATTAFORMA: [
                CallbackQueryHandler(ricevi_piattaforma, pattern="^piat_")
            ],
            CREA_ATTESA_DATA: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.Text([T_LISTA, T_ANALISI, T_VENDI, T_CREA]), gestisci_testo_sconosciuto_in_conversazione),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_data)
            ],
            # --- FLUSSO DI VENDITA ---
            VENDI_ATTESA_SCELTA: [
                CallbackQueryHandler(vendi_ricevi_scelta_annuncio, pattern="^vendi_")
            ],
            VENDI_ATTESA_PREZZO: [
                MessageHandler(filters.Text([T_LISTA, T_ANALISI, T_VENDI, T_CREA]), gestisci_testo_sconosciuto_in_conversazione),
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendi_ricevi_prezzo)
            ],
            # --- FLUSSO DI ELIMINAZIONE DI UN ANNUNCIO ---
            ELIMINA_ATTESA_SCELTA: [
                CallbackQueryHandler(elimina_ricevi_scelta, pattern="^elimina_")
            ],
            ELIMINA_ATTESA_CONFERMA: [
                CallbackQueryHandler(elimina_esegui_conferma, pattern="^elimina_conferma_si_"),
                CallbackQueryHandler(annulla, pattern="^elimina_conferma_no$"),
                MessageHandler(filters.Text(T_AIUTO), annulla),
            ],
            # --- FLUSSO DI MODIFICA ---
            MODIFICA_ATTESA_SCELTA_ANNUNCIO: [
                CallbackQueryHandler(modifica_ricevi_scelta_annuncio, pattern=r"^modifica_\d+$")
            ],
            MODIFICA_MENU_CAMPI: [
                CallbackQueryHandler(modifica_richiedi_nuovo_titolo, pattern="^crea_modifica_titolo$"),
                CallbackQueryHandler(modifica_richiedi_nuova_descrizione, pattern="^crea_modifica_desc$"),
                CallbackQueryHandler(modifica_richiedi_nuovo_prezzo, pattern="^crea_modifica_prezzo$"),
                CallbackQueryHandler(modifica_fatto, pattern="^crea_modifica_fatto$")
            ],
            MODIFICA_ATTESA_NUOVO_TITOLO: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, modifica_ricevi_nuovo_titolo)
            ],
            MODIFICA_ATTESA_NUOVA_DESCRIZIONE: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, modifica_ricevi_nuova_descrizione)
            ],
            MODIFICA_ATTESA_NUOVO_PREZZO: [
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, modifica_ricevi_nuovo_prezzo)
            ],
            # --- FLUSSO DI DETTAGLI DI UN ANNUNCIO ---
            DETTAGLI_ATTESA_SCELTA: [
                CallbackQueryHandler(dettagli_mostra, pattern=r"^dettagli_\d+$"),
                CallbackQueryHandler(dettagli_chiudi, pattern="^dettagli_chiudi$")
            ]
        },
        fallbacks=[
            # Il comando /annulla funziona DENTRO la conversazione
            CommandHandler("annulla", annulla),
            # Anche il pulsante 'Aiuto / Annulla' funziona
            MessageHandler(filters.Text(T_AIUTO), annulla)
        ],
        per_user=True,
        allow_reentry=False
        
    )
    
    # Aggiungiamo i gestori di conversazione
    application.add_handler(main_conversation_handler)

    # --- GESTORI GLOBALI (Il Menu Principale) ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Text(T_LISTA), lista_handler))
    application.add_handler(MessageHandler(filters.Text(T_ANALISI), analisi_handler))
    application.add_handler(MessageHandler(filters.Text(T_AIUTO), aiuto_annulla_globale))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gestisci_testo_sconosciuto))

    print("Bot avviato e in ascolto... (modalità MENU ATTIVA!)")
    application.run_polling()