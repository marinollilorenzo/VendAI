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

    # Optimized prompt for the Italian market.
    prompt_text = f"""
    Act as an expert Italian online seller. Analyze the image and user text to create a perfect ad.
    
    1. **Visual Analysis (High Priority):**
       - Identify the item, brand, model, color, and cosmetic condition.
       - Look for any defects or included accessories.
    
    2. **User Text Analysis:** "{product_description}"
       - Integrate this info only if it adds non-visible details (e.g., purchase year, reason for selling).
       
    3. **Required JSON Output:**
       - `title` (string): A catchy title optimized for search algorithms (e.g., Vinted/Subito), max 60 chars.
       - `description` (string): A fluid, persuasive, and honest paragraph. DO NOT use bullet points; write like a human. Use emojis moderately.
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
            model='gemini-1.5-flash',
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
