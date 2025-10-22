import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Error in recovering the GEMINI_API_KEY in .env file")
    
async def ad_text_generator(product_description):
    if not GEMINI_API_KEY:
        return "Error: API not configured"
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = """
    Sei un esperto venditore di articoli di seconda mano. 
    Crea un titolo accattivante e una descrizione dettagliata per un annuncio online.
    
    Ecco l'oggetto: "{descrizione_oggetto}"
    
    Restituisci solo il titolo e la descrizione, formattati in questo modo:
    
    Titolo: [Il tuo titolo qui]
    Descrizione: [La tua descrizione qui]
    """
    response = await model.generate_content_async(prompt)
    return response.text


def parse_risposta_ai(testo_grezzo):
    
    #Prende il testo grezzo dall'IA e lo divide in titolo, descrizione e prezzo. Restituisce i tre valori separati.
    try:
        parti = testo_grezzo.split("Descrizione:")
        titolo = parti[0].replace("Titolo:", "").strip()
        descrizione = parti[1].strip()
        prezzo_suggerito = "" 
        
        return titolo, descrizione, prezzo_suggerito
    except Exception as e:
        print(f"Errore nel parsing della risposta AI: {e}")
        # In caso di errore, restituiamo valori di default
        return "Titolo non trovato", "Descrizione non trovata", ""