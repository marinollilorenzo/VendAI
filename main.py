from database import db_initialization
from telegramBot import bot_start


if __name__ == "__main__":
    db_initialization()
    bot_start()