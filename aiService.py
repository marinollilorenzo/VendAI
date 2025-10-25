import google.generativeai as genai
import os
from dotenv import load_dotenv
import io
from PIL import Image

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Error in recovering the GEMINI_API_KEY in .env file")


async def ad_text_generator(product_description, foto_bytes=None):
    """
    Questa funzione prende una descrizione (e opzionalmente un'immagine) e restituisce un annuncio strutturato.
    """
    
    if not GEMINI_API_KEY:
        return "Error: API not configured"
    
    model = genai.GenerativeModel('models/gemini-2.5-flash')

    prompt = f"""
    Sei "VendiRapido", un assistente esperto. Il tuo compito primario è ANALIZZARE L'IMMAGINE ALLEGATA.
    L'immagine è la fonte principale di informazioni. Il testo dell'utente è solo un contesto aggiuntivo.

    1.  **Analizza l'immagine:** Identifica l'oggetto, il colore, le condizioni visibili e qualsiasi dettaglio notevole.
    2.  **Leggi il testo utente (se utile):** "{product_description}"
    3.  **Combina le informazioni:** Usa i dettagli visti nell'immagine come base per l'annuncio.

    Genera un annuncio completo rispettando ESATTAMENTE questo formato:

    Titolo: [Un titolo basato sull'oggetto visto nell'immagine]
    
    Descrizione: [Una descrizione amichevole basata sui dettagli visti in foto. Usa il testo dell'utente solo se fornisce informazioni extra.]
    
    Elenco Puntato:
    - Oggetto: [Nome dell'oggetto identificato dalla foto]
    - Colore: [Colore identificato dalla foto]
    - Dettagli Visivi: [Un dettaglio specifico visto nella foto]
    
    Prezzo Suggerito: [Fai una stima realistica del prezzo in Euro per l'oggetto in foto]
    """
    
    contenuto_prompt = [prompt]
    immagine_caricata_correttamente = False

    if foto_bytes:
        try:
            img = Image.open(io.BytesIO(foto_bytes))
            contenuto_prompt.append(img)
            immagine_caricata_correttamente = True
        except Exception as e:
            print(f"Errore nel caricamento dell'immagine: {e}")
            pass
    
    # Se l'immagine non è stata caricata E il testo è vago, restituisci un errore
    if not immagine_caricata_correttamente and len(product_description) < 15:
         return "Titolo: Errore\nDescrizione: Immagine non valida e testo troppo vago."
    
    # La chiamata corretta, asincrona, che usa il nostro 'contenuto_prompt'
    response = await model.generate_content_async(contenuto_prompt)
    
    return response.text

def parse_risposta_ai(testo_grezzo):
    """
    Prende il testo grezzo e strutturato dall'IA e lo divide in campi separati.
    Questa versione è più robusta e ignora il grassetto e il testo introduttivo.
    """
    try:
        dati = {}
        sezione_corrente = ""
        
        if "**Titolo:**" not in testo_grezzo:
             if "Titolo:" not in testo_grezzo:
                raise ValueError("Formato AI non riconosciuto, 'Titolo:' non trovato.")
             indice_inizio = testo_grezzo.find("Titolo:")
        else:
             indice_inizio = testo_grezzo.find("**Titolo:**")
        
        testo_annuncio = testo_grezzo[indice_inizio:]

        righe = [riga.strip() for riga in testo_grezzo.split('\n') if riga.strip()]

        for riga in righe:
            riga_pulita = riga.replace("**", "").strip()

            if riga_pulita.startswith("Titolo:"):
                dati["titolo"] = riga_pulita.replace("Titolo:", "").strip()
                sezione_corrente = "titolo"
            elif riga_pulita.startswith("Descrizione:"):
                dati["descrizione"] = riga_pulita.replace("Descrizione:", "").strip()
                sezione_corrente = "descrizione"
            elif riga_pulita.startswith("Elenco Puntato:"):
                dati["descrizione"] += "\n\n**Caratteristiche:**"
                sezione_corrente = "descrizione"
            elif riga_pulita.startswith("Prezzo Suggerito:"):
                dati["prezzo"] = riga_pulita.replace("Prezzo Suggerito:", "").strip()
                sezione_corrente = "prezzo"
            elif sezione_corrente == "descrizione":
                dati["descrizione"] += "\n" + riga_pulita

        return (
            dati.get("titolo", "Titolo non trovato (parsing fallito)"),
            dati.get("descrizione", "Descrizione non trovata (parsing fallito)"),
            dati.get("prezzo", "")
        )
    except Exception as e:
        print(f"Errore critico nel parsing della risposta AI: {e}")
        print(f"--- OUTPUT PROBLEMATICO ---\n{testo_grezzo}\n-------------------------")
        return "Titolo non trovato (errore)", "Descrizione non trovata (errore)", ""