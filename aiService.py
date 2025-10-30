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