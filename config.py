from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
APP_URL = os.getenv('APP_URL')

# Проверка на локальном запуске
if __name__ == "__main__":
    print(f"BOT_TOKEN установлен: {'Да' if BOT_TOKEN else 'Нет'}")
    print(f"APP_URL: {APP_URL}")