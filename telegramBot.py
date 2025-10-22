import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from aiService import ad_text_generator
from aiService import parse_risposta_ai
from database import add_annuncement

load_dotenv()
TOKEN   = os.getenv("TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia un messaggio di benvenuto quando l'utente invia /start."""
    await update.message.reply_text(
        "Ciao! Sono il tuo assistente per creare annunci.\n"
        "Usa il comando /nuovo seguito dalla descrizione del tuo oggetto.\n\n"
        "Esempio: /nuovo Vendo iPhone 14 Pro viola, 128GB, ottime condizioni"
    )

async def nuovo_annuncio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce il comando /nuovo, genera il testo e lo salva nel database."""
    if not context.args:
        await update.message.reply_text("Per favore, fornisci una descrizione dopo il comando /nuovo.")
        return
        
    descrizione_input = " ".join(context.args)
    await update.message.reply_text(f"Ricevuto: '{descrizione_input}'.\nSto generando il testo con l'IA, attendi un momento...")

    testo_grezzo_ai = await ad_text_generator(descrizione_input)
    titolo, descrizione, prezzo = parse_risposta_ai(testo_grezzo_ai)
    
    categoria_temp = "Elettronica" # Per ora usiamo un valore fisso
    nuovo_id = add_annuncement(
        descrizione_input=descrizione_input,
        titolo_generato=titolo,
        descrizione_generata=descrizione,
        prezzo_suggerito=prezzo,
        categoria=categoria_temp
    )

    risposta_finale = (
        f"✅ Annuncio creato e salvato con ID: {nuovo_id}\n\n"
        f"**Titolo:**\n{titolo}\n\n"
        f"**Descrizione:**\n{descrizione}"
    )
    await update.message.reply_text(risposta_finale, parse_mode='Markdown')

# --- FUNZIONE DI AVVIO ---

def bot_start():
    """Crea l'applicazione e avvia il bot."""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("nuovo", nuovo_annuncio_handler))

    print("Bot avviato e in ascolto...")
    application.run_polling()