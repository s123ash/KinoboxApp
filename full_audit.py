import os, sys, asyncio, re, sqlite3

print("=== 1. ПРОВЕРКА КЛЮЧЕЙ И CONFIG ===")
work_dir = "app/src/main/python"
sys.path.insert(0, work_dir)

api_id = None
api_hash = None
admin_id = 846768993

# Читаем .env напрямую по абсолютному пути
env_path = os.path.join(work_dir, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("API_ID="):
                api_id = int(line.strip().split("=", 1)[1])
            elif line.startswith("API_HASH="):
                api_hash = line.strip().split("=", 1)[1].strip("'\"")
    print(f"✓ .env прочитан успешно: API_ID={api_id}, API_HASH={'*' * 8}")
else:
    print("✗ .env не найден в app/src/main/python/")

print("\n=== 2. ТЕСТ СЕССИИ TELEGRAM И ПОСТА @zubszu #2 ===")
async def test_telegram_stream():
    try:
        from pyrogram import Client
        session_file = os.path.join(work_dir, "my_session")
        app = Client(session_file, api_id=api_id, api_hash=api_hash)
        await app.start()
        me = await app.get_me()
        print(f"✓ Авторизация успешна! Аккаунт: {me.first_name} (@{me.username}) [ID: {me.id}]")

        print("Запрос сообщения #2 из @zubszu...")
        msg = await app.get_messages("@zubszu", 2)
        if not msg:
            print("✗ Сообщение #2 не найдено")
            await app.stop()
            return

        print(f"  • media_group_id: {msg.media_group_id}")
        media = msg.video or msg.document
        if media:
            print(f"  • Тип медиа: {'video' if msg.video else 'document'}")
            print(f"  • Имя файла: {getattr(media, 'file_name', 'без имени')}")
            print(f"  • Размер файла: {round(media.file_size / (1024*1024), 2)} МБ")
            print(f"  • Длительность: {getattr(media, 'duration', 0)} сек")

            # Тест стриминга одного чанка
            print("Тестирование потоковой загрузки первого чанка (1 МБ)...")
            async for chunk in app.stream_media(msg, limit=1):
                print(f"✓ Чанк успешно получен из Telegram! Размер: {len(chunk)} байт")
                break
        else:
            print("✗ В сообщении нет видеофайла")

        # Если это альбом (несколько видео)
        if msg.media_group_id:
            group = await app.get_media_group("@zubszu", 2)
            print(f"  • Это альбом! Всего частей видео: {len(group)}")

        await app.stop()
    except Exception as e:
        print(f"✗ Ошибка при работе с Telegram: {e}")

asyncio.run(test_telegram_stream())

print("\n=== 3. ПРОВЕРКА КНОПОК В INDEX.HTML ===")
html_path = "app/src/main/python/index.html"
if os.path.exists(html_path):
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    
    # Ищем функции клика по кнопкам просмотра и статусов
    matches = re.findall(r"function\s+(?:toggle|watch|play|action)[a-zA-Z0-9_]*\s*\(.*?\)\s*\{", html)
    print("Найденные JS-функции действий:", matches)

    # Ищем вызовы эндпоинтов действий
    actions = set(re.findall(r"[\"'\`]/api/(?:action|watch|watching|stats)[\"'\`]", html))
    print("Эндпоинты действий в JS:", actions)
