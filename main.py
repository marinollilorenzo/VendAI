import telegram
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    TOKEN   = os.getenv("TOKEN")
    CHAT_ID = os.getenv("CHAT_ID") 
    bot = telegram.Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="Il mio primo messaggio dal bot!")
    
if __name__ == "__main__":
    asyncio.run(main())