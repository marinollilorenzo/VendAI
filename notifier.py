import os
import asyncio
import telegram
import datetime
from dateutil.parser import isoparse
from dotenv import load_dotenv
from database import ottieni_annunci_attivi, aggiorna_stato_annuncio

load_dotenv()
TOKEN = os.getenv("TOKEN")

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
    prezzo = annuncio['prezzo_suggerito']
    
    if tipo_notifica == "pre-notifica":
        header = f"⏰ **PREAVVISO, MANCANO MENO DI 30 MINUTI** ⏰"
        footer = f"Preparati a pubblicare l'annuncio (ID: #{annuncio['id']:04d}) che mancano meno di 30 minuti!"
    else: # "finale"
        header = f"🔔 **È ORA DI PUBBLICARE!** 🔔"
        footer = f"Ecco l'annuncio programmato (ID: #{annuncio['id']:04d})."

    return (
        f"{header}\n\n"
        f"**Titolo:**\n{titolo}\n\n"
        f"**Descrizione:**\n{descrizione}\n\n"
        f"**Prezzo:**\n{prezzo}€\n\n"
        f"---\n{footer}"
    )

async def main_loop():
    """Il ciclo principale del guardiano, ora con logica a 2 fasi."""
    if not TOKEN:
        print("Errore: TOKEN non trovato nel file .env.")
        return

    bot = telegram.Bot(token=TOKEN)
    print("Avvio del 'Guardiano Notifiche'")
    
    while True:
        now = datetime.datetime.now()        
        try:
            annunci_attivi = ottieni_annunci_attivi()
            
            if not annunci_attivi:
                print(".")
            
            for annuncio in annunci_attivi:
                chat_id_destinatario = annuncio['telegram_user_id']
                data_programmata = isoparse(annuncio['data_pubblicazione'])                
                # --- LOGICA FASE 1: PRE-NOTIFICA (30 MIN) ---
                if annuncio['id_stato'] == 2: # Se è 'programmato'
                    warning_time = data_programmata - datetime.timedelta(minutes=30)
                    
                    if now >= warning_time:
                        print(f"/")
                        messaggio = await formatta_messaggio(annuncio, "pre-notifica")
                        successo = await invia_notifica(bot, chat_id_destinatario, messaggio)
                        
                        if successo:
                            # Aggiorna lo stato a 3 ('pre-notificato')
                            aggiorna_stato_annuncio(annuncio['id'], 3)
                
                # --- LOGICA FASE 2: NOTIFICA FINALE ---
                if annuncio['id_stato'] == 3: # Se è 'pre-notificato'
                    
                    if now >= data_programmata:
                        print(f"|")
                        messaggio = await formatta_messaggio(annuncio, "finale")
                        successo = await invia_notifica(bot, chat_id_destinatario, messaggio)
                        
                        if successo:
                            # Aggiorna lo stato a 4 ('notificato')
                            aggiorna_stato_annuncio(annuncio['id'], 4)

        except Exception as e:
            print(f"\n[{datetime.datetime.now()}] ERRORE CRITICO nel guardiano: {e}")
        # Aspetta 60 secondi prima del prossimo controllo
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main_loop())