import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()

        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
        
        # ADMIN_ID should be an integer
        admin_id_str = os.getenv("ADMIN_ID")
        self.ADMIN_ID = int(admin_id_str) if admin_id_str else None

        self.DB_PATH = os.getenv("DB_PATH", "annunci.db")

        self._validate_critical_keys()

    def _validate_critical_keys(self):
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN not found in environment variables. Please set it in the .env file.")
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in the .env file.")

# Instantiate the config object to load environment variables immediately
config = Config()
