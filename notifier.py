import os
import asyncio
import telegram
import datetime
from dateutil.parser import isoparse
from dotenv import load_dotenv

# Importiamo le nostre funzioni del database
from database import ottieni_annunci_attivi, aggiorna_stato_annuncio

# Carichiamo le variabili d'ambiente
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def invia_notifica(bot, chat_id, testo_notifica):
    """Funzione generica per inviare una notifica."""
    try:
        await bot.send_message(
            chat_id=chat_id, 
            text=testo_notifica, 
            parse_mode='Markdown'
        )
        return True
    except Exception as e:
        print(f"Errore nell'invio della notifica: {e}")
        return False


async def formatta_messaggio(annuncio, tipo_notifica="finale"):
    """Prepara il testo del messaggio da inviare."""
    titolo = annuncio['titolo_generato']
    descrizione = annuncio['descrizione_generata']
    
    if tipo_notifica == "pre-notifica":
        header = f"⏰ **PREAVVISO 30 MINUTI** ⏰"
        footer = f"Preparati a pubblicare l'annuncio (ID: {annuncio['id']}) tra 30 minuti!"
    else: # "finale"
        header = f"🔔 **È ORA DI PUBBLICARE!** 🔔"
        footer = f"Ecco l'annuncio programmato (ID: {annuncio['id']})."

    return (
        f"{header}\n\n"
        f"**Titolo:**\n{titolo}\n\n"
        f"**Descrizione:**\n{descrizione}\n\n"
        f"---\n{footer}"
    )


async def main_loop():
    """Il ciclo principale del guardiano, ora con logica a 2 fasi."""
    if not TOKEN or not CHAT_ID:
        print("Errore: TOKEN o CHAT_ID non trovati nel file .env.")
        return

    bot = telegram.Bot(token=TOKEN)
    print("Avvio del 'Guardiano Notifiche' (Logica a 2 fasi)... Controllo ogni 60 secondi.")
    
    while True:
        print(f"Controllo annunci... (Ora: {datetime.datetime.now()})")
        now = datetime.datetime.now()        
        try:
            annunci_attivi = ottieni_annunci_attivi()
            
            if not annunci_attivi:
                print("Nessun annuncio attivo in attesa.")
            
            for annuncio in annunci_attivi:
                chat_id_destinatario = annuncio['telegram_user_id']
                data_programmata = isoparse(annuncio['data_pubblicazione'])                
                # --- LOGICA FASE 1: PRE-NOTIFICA (30 MIN) ---
                if annuncio['id_stato'] == 2: # Se è 'programmato'
                    warning_time = data_programmata - datetime.timedelta(minutes=30)
                    
                    if now >= warning_time:
                        print(f"Invio PRE-NOTIFICA per ID: {annuncio['id']}")
                        messaggio = await formatta_messaggio(annuncio, "pre-notifica")
                        successo = await invia_notifica(bot, CHAT_ID, messaggio)
                        
                        if successo:
                            # Aggiorna lo stato a 3 ('pre-notificato')
                            aggiorna_stato_annuncio(annuncio['id'], 3)
                
                # --- LOGICA FASE 2: NOTIFICA FINALE ---
                if annuncio['id_stato'] == 3: # Se è 'pre-notificato'
                    
                    if now >= data_programmata:
                        print(f"Invio NOTIFICA FINALE per ID: {annuncio['id']}")
                        messaggio = await formatta_messaggio(annuncio, "finale")
                        successo = await invia_notifica(bot, CHAT_ID, messaggio)
                        
                        if successo:
                            # Aggiorna lo stato a 4 ('notificato')
                            aggiorna_stato_annuncio(annuncio['id'], 4)

        except Exception as e:
            print(f"Errore durante il ciclo di controllo: {e}")
        
        # Aspetta 60 secondi prima del prossimo controllo
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main_loop())