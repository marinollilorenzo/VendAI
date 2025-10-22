import telegram
import asyncio
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def ad_text_generator(product_description):
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


async def main():
    TOKEN   = os.getenv("TOKEN")
    CHAT_ID = os.getenv("CHAT_ID") 
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    descrizione_input = "Vendo Iphone 14 pro max viola, 128 gb, condizioni ottime"
    text_generated = await ad_text_generator(descrizione_input)
    
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text_generated)
    
if __name__ == "__main__":
    asyncio.run(main())