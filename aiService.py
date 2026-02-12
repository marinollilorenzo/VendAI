import logging
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types
from config import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic Model for Structured Output ---
class AdOutput(BaseModel):
    title: str
    description: str
    price: float

# --- Global Client Initialization ---
# Initialize the client once to be reused across function calls.
if not config.GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY not found! Please set it in the .env file.")
    client = None
else:
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        logger.info("✅ Gemini Client initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Gemini Client: {e}")
        client = None

async def ad_text_generator(product_description: str, foto_bytes: bytes = None) -> AdOutput | dict:
    """
    Generates a structured ad (title, description, price) using Gemini.
    It uses the google-genai SDK with native async support and structured output.
    """
    if not client:
        return {
            "title": "Errore di Configurazione",
            "description": "API Key di Gemini non configurata. Contatta l'amministratore.",
            "price": 0.0
        }

    prompt_text = f"""
    Sei un venditore online italiano esperto, con esperienza su Vinted, Subito ed eBay. 
    Sei bravo a scrivere annunci chiari, sinceri e coinvolgenti, ottimizzati per la ricerca e per convertire visite in messaggi. 
    Il tuo stile è amichevole ma professionale, mai esagerato o artificiale.

    Riceverai:
    - una FOTO (da analizzare visivamente)
    - un TESTO UTENTE {product_description} (potrebbe essere disordinato, incompleto o generico)

    Obiettivo: generare SOLO questo JSON valido (nessun testo fuori dal JSON):

    Il formato deve essere:
    "title": "string (<=60 chars)",
    "description": "string (1-3 frasi, tono amichevole e professionale; emoji moderate; 3-5 hashtag alla fine)",
    "price": float

    Regole:

    1. ANALISI VISIVA (priorità alta):
    - Identifica oggetto, marca, modello, colore, versione, eventuale taglia.
    - Valuta condizioni reali (ottime, buone, segni di usura, difetti visibili).
    - Nota accessori inclusi o assenti.
    - Non inventare informazioni non visibili.

    2. ANALISI TESTO UTENTE:
    - Il testo può essere impreciso o poco chiaro.
    - Estrai tutte le informazioni utili (anno acquisto, uso, misure, motivazione vendita).
    - Integra solo dettagli che non sono già evidenti dalla foto.
    - Se il testo contraddice la foto, fidati della foto.

    3. TITOLO:
    - Ottimizzato SEO marketplace (Vinted/Subito).
    - Max 60 caratteri.
    - Niente emoji nel titolo.
    - Inserisci brand/modello se certo.

    4. DESCRIZIONE:
    - 1/3 frasi fluide (max ~350 caratteri).
    - Tono umano, accogliente ma onesto.
    - Indica condizioni reali senza minimizzare difetti.
    - Includi una frase di invito tipo:
        "Scrivimi per info o altre foto 😊"
        oppure
        "Contattami per qualsiasi dubbio o misura."
    - Emoji moderate (max 2).
    - Concludi con 3/5 hashtag rilevanti (es. #nike #vintage #usato).

    5. PREZZO:
    - Stima realistica in EURO come numero (es. 49.99).
    - Non includere simboli o testo.
    - Arrotondamento commerciale (.99 / .90).
    - Se incertezza alta, prezzo leggermente prudente per favorire la vendita.
    - Non sovrastimare articoli usati.

    6. Non inserire:
    - dati personali
    - numeri di telefono
    - link esterni
    - testo fuori dal JSON

    7. Se la foto è poco chiara:
    - Usa titolo prudente.
    - Prezzo conservativo.
    - Mantieni comunque il JSON valido.
    """
    """
    # Optimized prompt for the Italian market.
    prompt_text = f
    Act as an expert Italian online seller. Analyze the image and user text to create a perfect ad.
    
    1. **Visual Analysis (High Priority):**
       - Identify the item, brand, model, color, and cosmetic condition.
       - Look for any defects or included accessories.
    
    2. **User Text Analysis:** "{product_description}"
       - Integrate this info only if it adds non-visible details (e.g., purchase year, reason for selling).
       
    3. **Required JSON Output:**
       - `title` (string): A catchy title optimized for search algorithms (e.g., Vinted/Subito), max 60 chars.
       - `description` (string): A fluid, persuasive, and honest paragraph. DO NOT use bullet points; write like a human. Use emojis moderately. ALWAYS append 3-5 relevant hashtags at the end (e.g., #vintage #nike #usato).
       - `price` (float): A realistic estimate in Euros for the used item. CRITICAL: Output ONLY a single number, DO NOT include "€" or any other text.
    """
    # Build the content parts for the request
    parts = [types.Part.from_text(text=prompt_text)]
    if foto_bytes:
        try:
            image_part = types.Part.from_bytes(data=foto_bytes, mime_type="image/jpeg")
            parts.insert(0, image_part) # Place the image before the text prompt
        except Exception as e:
            logger.error(f"Error loading image bytes: {e}")
    
    contents = [types.Content(role="user", parts=parts)]

    try:
        # Native async call with structured output (Pydantic)
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AdOutput,
                temperature=0.7 
            )
        )

        if response.parsed:
             return response.parsed
        else:
            logger.warning("Automatic parsing failed, attempting manual JSON parsing.")
            return AdOutput.model_validate_json(response.text)

    except ValidationError as e:
        logger.error(f"Pydantic validation failed: {e}. Raw response: {getattr(e, 'raw_response', 'N/A')}")
        return {
            "title": "Errore di Formato IA",
            "description": "L'IA non ha risposto nel formato JSON corretto. Prova a riformulare la richiesta.",
            "price": 0.0
        }
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        error_msg = str(e).lower()
        
        if "429" in error_msg or "quota" in error_msg:
             return {"title": "Limite Raggiunto", "description": "Troppe richieste in poco tempo. Riprova tra poco.", "price": 0.0}
        
        return {
            "title": "Errore Generico IA",
            "description": "Non sono riuscito a generare l'annuncio. Riprova, magari con una foto più chiara o una descrizione diversa.",
            "price": 0.0
        }
