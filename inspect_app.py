import sqlite3, os

print("=== 1. ТАБЛИЦЫ И КОЛОНКИ В tracker.db ===")
con = sqlite3.connect("app/src/main/python/tracker.db")
cur = con.cursor()
for t in ["watched", "watching", "movies"]:
    try:
        cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
        print(f"Таблица {t}: {[c[1] for c in cols]}")
        sample = cur.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
        print(f"  Пример записи {t}: {sample}")
    except Exception as e:
        print(f"Ошибка {t}: {e}")
con.close()

print("\n=== 2. ПОИСК ФУНКЦИЙ СТАТИСТИКИ И ДЕЙСТВИЙ В index.html ===")
with open("app/src/main/python/index.html", "r", encoding="utf-8", errors="ignore") as f:
    html = f.read()

for endpoint in ["/api/stats", "/api/action"]:
    pos = html.find(endpoint)
    if pos != -1:
        print(f"\n--- Фрагмент кода вокруг {endpoint} ---")
        start = max(0, pos - 80)
        end = min(len(html), pos + 250)
        print(html[start:end])
