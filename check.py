import sqlite3
import os
import zipfile

print("=== 1. ПРОВЕРКА БАЗЫ TRACKER.DB ===")
db_path = "app/src/main/assets/databases/tracker.db"
if os.path.exists(db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    print("Таблицы в базе:", tables)
    for t in tables:
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"\nТаблица '{t}' (записей: {count}):")
        print("Колонки:", cols)
        sample = cur.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
        print("Пример строки:", sample)
    con.close()
else:
    print("Файл tracker.db НЕ НАЙДЕН в app/src/main/assets/databases/")

print("\n=== 2. ПОИСК ЗАПРОСОВ В INDEX.HTML ===")
html_path = "app/src/main/assets/www/index.html"
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        line_clean = line.strip()
        if "fetch(" in line_clean or "/api" in line_clean or "loadMovies" in line_clean:
            print(f"Строка {i+1}: {line_clean[:120]}")
else:
    print("Файл index.html НЕ НАЙДЕН в app/src/main/assets/www/")

print("\n=== 3. ЭНДПОИНТЫ ИЗ АРХИВА BOT.ZIP ===")
zip_path = os.path.expanduser("~/Загрузки/bot.zip")
if os.path.exists(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith("web_server.py") or name.endswith("database.py"):
                print(f"\n--- {name} ---")
                content = z.read(name).decode("utf-8", errors="ignore")
                for line in content.splitlines():
                    if any(k in line for k in ["@routes", "def get_", "SELECT", "json_response"]):
                        print("  ", line.strip())
else:
    print("bot.zip не найден в ~/Загрузки")
