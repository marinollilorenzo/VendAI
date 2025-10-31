from google import genai
from pydantic import BaseModel
from google.genai import types
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

class output(BaseModel):
    title: str
    description: str
    price:str
    
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def ad_text_generator(product_description, foto_bytes=None):
    """
    Questa funzione prende una descrizione (e opzionalmente un'immagine) e restituisce un annuncio strutturato.
    """

    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        print("Error in recovering the GEMINI_API_KEY in .env file")
    
    prompt = f"""
        Segui rigorosamente queste istruzioni ottimizzate per un'esecuzione efficiente e coerente:

        1. **Analisi dell'Immagine Allegata (PRIORITARIO):**
            - Identifica con precisione l’oggetto (categoria, marca/modello se visibile).
            - Rileva il colore, le condizioni generali (segni d’uso, difetti o eventuali elementi come scatola/originalità), dimensioni stimate o proporzioni.
            - Nota qualsiasi dettaglio distintivo o valore aggiunto (es. edizione limitata, accessori inclusi).
            - Utilizza algoritmi di visione artificiale per massima accuratezza.

        2. **Analisi del Testo Utente** :
            - Includi solo se aggiunge dati non evidenti dalla foto (es. anno di acquisto, funzionalità specifiche, motivo della vendita).
            - Ignora ripetizioni o dati già visibili.

        3. **Generazione Annuncio (Seguendo il formato obbligatorio sotto):**
            - Combina dati da foto e testo solo se apportano valore informativo aggiuntivo.
            - Usa uno stile chiaro, dettagliato e accattivante. Nessun linguaggio vago o promozionale.
            **TONO:** Sii DIRETTO, INFORMATIVO e NATURALE, come un venditore privato. Registro linguistico medio.

        Testo Utente: "{product_description}"
        
        Formato UFFICIALE da rispettare ESATTAMENTE in output per popolare i campi:

        1.  **title (string):**
        - Titolo generato sull’oggetto principale identificato dalla foto ricco di parole chiave
        - Usa uno stile chiaro e commerciale (es.Vinted).

        2.  **description (string):**
        - Scrivi una descrizione amichevole e dettagliata.
        - inserire testo utente solo se aggiunge info extra
        - ALLA FINE della descrizione, INCLUDI SEMPRE un elenco puntato formattato:
        
        Oggetto:[Nome preciso, anche con marca/modello]
        Caratteristiche:[Condizioni, colore, dimensioni o altre specifiche fisiche e funzionali]
        Dettagli:[Un dettaglio visivo chiave visto in foto che può elevare il valore]

        3.  **price (string):**
        - Fornisci una stima di prezzo realistica in Euro
        - fondata sui dati di mercato dell'usato, tenendo conto delle condizioni, del modello/marca e di eventuali dettagli extra
        - usa fonti aggiornate o dataset di annunci usati se disponibili

        **Note aggiuntive per l'IA:**
        - Ignora qualsiasi informazione priva di riscontro visivo o non verificabile.
        - Mantieni output coerente e privo di errori di formattazione o linguaggio.
        - Assicurati che ogni sezione sia sempre presente e rispettata, anche in caso di informazioni mancanti.
        - Adatta il registro linguistico all'ambito commerciale online (es. Subito, eBay, Facebook Marketplace).
    """
    
    immagine_caricata_correttamente = False
    if foto_bytes:
        try:
            image = types.Part.from_bytes(
                data=foto_bytes, mime_type="image/jpeg"
            )
            immagine_caricata_correttamente = True
        except Exception as e:
            print(f"Errore nel caricamento dell'immagine: {e}")
    
    # Se l'immagine non è stata caricata E il testo è vago, restituisci un errore
    if not immagine_caricata_correttamente and len(product_description) < 15:
         return "Titolo: Errore\nDescrizione: Immagine non valida e testo troppo vago."
    
    
    try:
        response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt, image],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": output
                }
            )
        if hasattr(response, 'parsed') and response.parsed:
            # response.parsed è già un oggetto OutputSchema (o un dizionario)
            if isinstance(response.parsed, output):
                return response.parsed
            else:
                # Se è un dizionario, lo validiamo
                return output(**response.parsed)
        else:
            # Fallback se .parsed non esiste
            print("Attenzione: .parsed non trovato, uso .text")
            json_output = json.loads(response.text)
            return output(**json_output)
    except Exception as e:
        print(f"Errore chiamata API Gemini o parsing: {e}")
        error_str = str(e) # Convertiamo l'errore in stringa
        if "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str:
            return {
                "title": "Errore 503", 
                "description": "L'IA è momentaneamente sovraccarica. 😅 Per favore, riprova tra qualche minuto!", 
                "price": "N/D"
            }
        if "Quota exceeded" in error_str:
            return {"title": "Errore Quota", "description": "Limite piano gratuito superato.", "price": "N/D"}
        
        if "ValidationError" in error_str or isinstance(e, json.JSONDecodeError):
             raw_text = "N/D"
             try: raw_text = response.text
             except: pass
             print(f"Errore validazione/JSON: {e}")
             print(f"Risposta grezza: {raw_text}")
             return {"title": "Errore Schema", "description": "L'IA non ha rispettato il formato JSON.", "price": "N/D"}
        # Errore generico
        return {"title": "Errore API", "description": f"Chiamata fallita: {e}", "price": "N/D"}