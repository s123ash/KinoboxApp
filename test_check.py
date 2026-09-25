import os, sys, asyncio, sqlite3

print("=== 1. ПРОВЕРКА CONFIG И ADMIN_ID ===")
sys.path.insert(0, "app/src/main/python")
try:
    import config
    admin_id = getattr(config, 'ADMIN_ID', 0)
    api_id = getattr(config, 'API_ID', 0)
    print(f"✓ config.py загружен: ADMIN_ID={admin_id}, API_ID={api_id}")
except Exception as e:
    print(f"✗ Ошибка config.py: {e}")
    admin_id = 0

print("\n=== 2. ПРОВЕРКА ТАБЛИЦ В TRACKER.DB ===")
con = sqlite3.connect("app/src/main/python/tracker.db")
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Таблицы в базе:", tables)
for t in ["watched", "watching", "guests"]:
    if t in tables:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  • Таблица {t}: записей={cnt}")
con.close()

print("\n=== 3. ТЕСТ PYROGRAM СЕССИИ ===")
async def test_tg():
    from pyrogram import Client
    session_file = "app/src/main/python/my_session"
    app = Client(session_file, api_id=config.API_ID, api_hash=config.API_HASH)
    try:
        await app.start()
        me = await app.get_me()
        print(f"✓ Сессия Telegram активна! Авторизован как: {me.first_name} (@{me.username})")
        # Проверяем пост 2 из канала
        msg = await app.get_messages("@zubszu", 2)
        media_type = "video" if msg.video else ("document" if msg.document else "none")
        print(f"✓ Сообщение #2 получено успешно. Тип медиа: {media_type}")
        await app.stop()
    except Exception as e:
        print(f"✗ Ошибка подключения Telegram: {e}")

asyncio.run(test_tg())
