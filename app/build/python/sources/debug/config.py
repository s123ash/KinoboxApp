import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Вставь сюда актуальный URL от ngrok или своего домена
WEB_APP_URL = "https://kinase-creatures-occasionally-skating.trycloudflare.com"

ITEMS_PER_PAGE = 7

CATEGORIES_ZUBAREV = [
    "🦸‍♂️ Марвел / DC", "🪄 Фэнтези", "😆 Комедия",
    "🫣 Ужасы / Триллер", "🍿 Драма / Детектив",
    "🔫 Боевик / Экшен", "🧸 Мультфильмы",
    "📺 Шоу", "🚶‍♂️ IRL / Стримы"
]

CATEGORIES_MOVIES = [
    "🔫 Боевик", "😆 Комедия", "🫣 Ужасы / Триллер",
    "🍿 Драма / Мелодрама", "🪄 Фантастика / Фэнтези",
    "🧸 Мультфильмы / Аниме", "🕵️ Детектив / Криминал",
    "🌍 Приключения / Семейный", "📖 Биография / История",
    "🍿 Разное"
]
