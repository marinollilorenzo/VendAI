import google.generativeai as genai
import os
from dotenv import load_dotenv

# Carica la chiave API dal tuo file .env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Errore: Impossibile trovare GEMINI_API_KEY nel file .env")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)

        print("--- Elenco dei Modelli che supportano 'generateContent' ---")
        
        # Chiediamo a Google la lista di tutti i modelli
        for model in genai.list_models():
            # L'errore menzionava 'generateContent',
            # quindi filtriamo per i modelli che lo supportano.
            if 'generateContent' in model.supported_generation_methods:
                print(f"- {model.name}")
                
        print("----------------------------------------------------------")

    except Exception as e:
        print(f"Si è verificato un errore durante la connessione a Google: {e}")