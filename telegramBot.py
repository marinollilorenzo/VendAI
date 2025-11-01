import os
from dotenv import load_dotenv
import re
import datetime
from dateutil.parser import isoparse
from datetime import timedelta
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
    disattiva_annuncio
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
ATTESA_FOTO, ATTESA_CATEGORIA, ATTESA_PIATTAFORMA, ATTESA_DATA = range(4)
VENDI_ATTESA_SCELTA, VENDI_ATTESA_PREZZO = range(4,6)

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
    pulsanti = []
    categorie = ottieni_categorie_attive()
    
    for cat in categorie:
        pulsanti.append([
            InlineKeyboardButton(cat['nome'], callback_data=f"cat_{cat['id']}")
        ])

    return InlineKeyboardMarkup(pulsanti)

#Funzione che crea i tasti per la piattaforma
def crea_tastiera_piattaforme():
    """Crea una tastiera con le piattaforme prese dal DB."""
    pulsanti = []
    piattaforme = ottieni_piattaforme_attive()
    
    for p in piattaforme:
        pulsanti.append([
            InlineKeyboardButton(p['nome'], callback_data=f"piat_{p['id']}")
        ])

    return InlineKeyboardMarkup(pulsanti)

#Util
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

#Funzione di inizio bot
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


#HANDLERS:
#Crea annuncio:
async def nuovo_annuncio_handler_testo_guida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Perfetto! 👍\nPer creare un nuovo annuncio, **inviami una foto con una breve descrizione nella didascalia**.\n\nL'IA analizzerà l'immagine per darti suggerimenti migliori!",
        parse_mode='Markdown'
    )
    return ATTESA_FOTO

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
    await update.message.reply_text(f"✍️ Ricevuto! Sto analizzando la foto e la tua descrizione con l'IA... Questo potrebbe richiedere alcuni secondi. Attendi...")
    #autentificazione utente
    user = update.message.from_user
    id_telegram = user.id
    nome_telegram = user.first_name
    id_utente_db = get_or_create_user(id_telegram, nome_telegram)
    
    
    risultato_ai = await ad_text_generator(descrizione_input, foto_bytes)
    # 2. Controlliamo se è un errore
    if isinstance(risultato_ai, dict) and "Errore" in risultato_ai.get("title", ""):
         await update.message.reply_text(f"Errore dall'IA: {risultato_ai['description']}", reply_markup=crea_menu_principale())
         return ConversationHandler.END # Termina la conversazione

    # 3. Se non è un errore, accediamo ai campi .title, .description, .price
    titolo = risultato_ai.title
    descrizione = risultato_ai.description
    # Il prezzo è un float, lo formattiamo e puliamo solo il simbolo "€"
    prezzo = risultato_ai.price # Aggiungiamo uno spazio per sicurezza
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
    prezzo_stringa = f"{prezzo}€" 
    prezzo_pulito = escape_markdown(prezzo_stringa, version=2)

    risposta_anteprima = (
        f"✅ **Annuncio in bozza creato\\!**\n\n"
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
    context.user_data['id_categoria_scelta'] = id_categoria_scelta
    await query.edit_message_text(
        text=f"✅ Categoria scelta! Ora scegli su quale piattaforma vuoi pubblicare:",
        reply_markup=crea_tastiera_piattaforme()
    )
    
    # Diciamo al ConversationHandler di passare allo stato "ATTESA_DATA"
    return ATTESA_PIATTAFORMA

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

    # Passiamo allo stato ATTESA_DATA
    return ATTESA_DATA

async def ricevi_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Questa funzione si attiva quando l'utente invia un testo nello stato ATTESA_DATA.
    """
    testo_data = update.message.text
    data_programmata = parse_date_regex(testo_data)
    
    if not data_programmata:
        await update.message.reply_text(
            "Non ho capito la data. 😅 Riprova (es. 'domani alle 15:00', 'tra 2 giorni alle 21')."
        )
        return ATTESA_DATA # Rimaniamo nello stesso stato

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


#Segna venduto un annuncio:   
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

    await update.message.reply_text(
        messaggio_intro,
        reply_markup=InlineKeyboardMarkup(tastiera_annunci)
    )
    
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


#La lista degli annunci
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


#Analisi:
async def analisi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Ricevuto comando /analisi")
    user = update.message.from_user
    id_utente_db = get_or_create_user(user.id, user.first_name)
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
        
        # NOTA: Usiamo 'Markdown' (v1) perché è meno rigido di 'MarkdownV2' 
        # con i numeri decimali e i simboli. È più sicuro per questo messaggio.
        await update.message.reply_text(messaggio, parse_mode='Markdown')

    except Exception as e:
        print(f"Errore durante /analisi: {e}")
        await update.message.reply_text(f"Si è verificato un errore durante la generazione delle statistiche: {e}")

#Annulla l'azione che si sta facendo
async def annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Annulla la conversazione corrente, prova a eliminare la bozza
    e ritorna al menu principale.
    """
    messaggio_feedback = "Operazione annullata. Ritorno al menu principale."
    
    # Controlliamo se c'è un annuncio in corso nello "zainetto"
    id_annuncio_corrente = context.user_data.get('id_annuncio_corrente')
    
    if id_annuncio_corrente:
        print(f"Annullamento: Trovato annuncio in corso ID: {id_annuncio_corrente}")
        # Identifichiamo l'utente per sicurezza
        user = update.effective_user # Otteniamo l'utente (da messaggio o callback)
        if user:
            id_utente_db = get_or_create_user(user.id, user.first_name)
            # Proviamo a eliminare
            eliminato = disattiva_annuncio(id_utente_db, id_annuncio_corrente)
            if eliminato:
                messaggio_feedback = "Operazione annullata. La bozza dell'annuncio è stata eliminata."
            else:
                 messaggio_feedback = "Operazione annullata. Non sono riuscito a eliminare la bozza (potrebbe essere già stata completata o cancellata)."
        else:
             print("Annullamento: Impossibile identificare l'utente per l'eliminazione.")

    await update.callback_query.edit_message_text(text=messaggio_feedback) if update.callback_query else await update.message.reply_text(messaggio_feedback, reply_markup=crea_menu_principale())

    # Puliamo lo "zainetto" in ogni caso
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

async def gestisci_testo_sconosciuto_in_conversazione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Risponde a un pulsante del menu premuto mentre si è in uno stato di attesa."""
    await update.message.reply_text(
        "Stai completando un'altra operazione! 😅\n"
        "Per favore, finisci l'inserimento o premi '❓ Aiuto / Annulla' per uscire.",
        reply_markup=update.message.reply_markup # Mantiene la tastiera (o la rimuove se non c'è)
    )
    


# --- FUNZIONE DI AVVIO ---
def bot_start():
    """Crea l'applicazione e avvia il bot con il menu principale."""
    application = Application.builder().token(TOKEN).build()

    main_conversation_handler = ConversationHandler(
        entry_points=[
            #MessageHandler(filters.PHOTO, foto_handler),
            MessageHandler(filters.Text(T_CREA), nuovo_annuncio_handler_testo_guida),
            MessageHandler(filters.Text(T_VENDI), vendi_wizard_start)  
        ],
        states={
            ATTESA_FOTO: [
                MessageHandler(filters.PHOTO, foto_handler),
            ],
            ATTESA_CATEGORIA: [
                CallbackQueryHandler(ricevi_categoria, pattern="^cat_") 
            ],
            ATTESA_PIATTAFORMA: [
                CallbackQueryHandler(ricevi_piattaforma, pattern="^piat_")
            ],
            ATTESA_DATA: [
                MessageHandler(filters.Text([T_LISTA, T_ANALISI, T_VENDI, T_CREA]), gestisci_testo_sconosciuto_in_conversazione),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ricevi_data)
            ],
            VENDI_ATTESA_SCELTA: [
                CallbackQueryHandler(vendi_ricevi_scelta_annuncio, pattern="^vendi_")
            ],
            VENDI_ATTESA_PREZZO: [
                MessageHandler(filters.Text([T_LISTA, T_ANALISI, T_VENDI, T_CREA]), gestisci_testo_sconosciuto_in_conversazione),
                MessageHandler(filters.Text(T_AIUTO), annulla),
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendi_ricevi_prezzo)
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