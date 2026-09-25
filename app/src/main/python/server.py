import os
import sys
import asyncio
import sqlite3
import re
from aiohttp import web

work_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(work_dir, "tracker.db")

# Загружаем ключи авторизации из config.py или .env
api_id = 0
api_hash = ""
try:
    import config
    api_id = getattr(config, 'API_ID', 0)
    api_hash = getattr(config, 'API_HASH', '')
except Exception:
    pass

if not api_id:
    try:
        env_file = os.path.join(work_dir, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("API_ID="):
                        api_id = int(line.strip().split("=", 1)[1])
                    elif line.startswith("API_HASH="):
                        api_hash = line.strip().split("=", 1)[1].strip("'\"")
    except Exception as e:
        print(f"[Python] Ошибка чтения .env: {e}")

routes = web.RouteTableDef()
pyro_client = None

def get_db():
    return sqlite3.connect(db_path)

@routes.get('/')
@routes.get('/index.html')
async def index_handler(request):
    html_file = os.path.join(work_dir, "index.html")
    if os.path.exists(html_file):
        return web.FileResponse(html_file)
    return web.Response(text="index.html not found", status=404)

# 1. КАТАЛОГ ФИЛЬМОВ (с именованными полями title, category, stream_date)
@routes.get('/api/movies')
async def get_movies(request):
    folder = request.query.get('folder', 'zubarev')
    category = request.query.get('category', 'ALL')
    search = request.query.get('search', '').lower().strip()

    con = get_db()
    cur = con.cursor()

    query = "SELECT post_id, title, year, category, genres, stream_date, is_watched, channel_id, channel_msg_id, folder FROM movies WHERE 1=1"
    args = []

    if folder and folder.lower() != 'all':
        query += " AND folder = ?"
        args.append(folder)

    if category and category.upper() != 'ALL':
        query += " AND category = ?"
        args.append(category)

    if search:
        query += " AND LOWER(title) LIKE ?"
        args.append(f"%{search}%")

    query += " ORDER BY post_id ASC"
    rows = cur.execute(query, args).fetchall()
    con.close()

    data = []
    for r in rows:
        title = r[1] or ""
        cat = r[3] or "Разное"
        date = r[5] or ""
        data.append({
            "post_id": r[0],
            "id": r[0],
            "pid": r[0],
            "title": title,
            "year": r[2] or "",
            "category": cat,
            "genres": r[4] or "",
            "stream_date": date,
            "date": date,
            "is_watched": bool(r[6]),
            "is_watching": False,
            "channel_id": r[7],
            "channel_msg_id": r[8],
            "folder": r[9] or "zubarev"
        })

    return web.json_response(data)

# 2. ДЕТАЛИ КОНКРЕТНОГО ФИЛЬМА (по клику на карточку)
@routes.get('/api/movie')
async def get_single_movie(request):
    pid = request.query.get('pid') or request.query.get('id')
    if not pid or not pid.isdigit():
        return web.json_response({"error": "invalid pid"}, status=400)

    con = get_db()
    cur = con.cursor()
    r = cur.execute("SELECT post_id, title, category, stream_date, is_watched, folder, year, genres, channel_id, channel_msg_id FROM movies WHERE post_id = ?", (int(pid),)).fetchone()
    con.close()

    if not r:
        return web.json_response({"error": "not found"}, status=404)

    return web.json_response({
        "pid": r[0],
        "id": r[0],
        "post_id": r[0],
        "title": r[1] or "",
        "category": r[2] or "Разное",
        "date": r[3] or "",
        "stream_date": r[3] or "",
        "is_watched": bool(r[4]),
        "is_watching": False,
        "folder": r[5] or "zubarev",
        "year": r[6] or "",
        "genres": r[7] or "",
        "channel_id": r[8],
        "channel_msg_id": r[9]
    })

# 3. СТАТИСТИКА
@routes.get('/api/stats')
async def get_stats(request):
    con = get_db()
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev'").fetchone()[0]
    watched = cur.execute("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev' AND is_watched = 1").fetchone()[0]
    con.close()
    return web.json_response({"total": total, "watched": watched, "watching": 0, "is_admin": True})

# 4. РАЗДЕЛ "СМОТРЮ"
@routes.get('/api/watching')
async def get_watching(request):
    return web.json_response([])

# 5. ДЕЙСТВИЯ (ОТМЕТИТЬ ПРОСМОТРЕННЫМ)
@routes.post('/api/action')
async def post_action(request):
    try:
        body = await request.json()
        pid = int(body.get('pid', 0))
        action = body.get('action', '')
        if pid:
            con = get_db()
            cur = con.cursor()
            if action == 'toggle_watched':
                cur.execute("UPDATE movies SET is_watched = CASE WHEN is_watched = 1 THEN 0 ELSE 1 END WHERE post_id = ?", (pid,))
            con.commit()
            con.close()
    except Exception:
        pass
    return web.json_response({"status": "ok", "active": True})

# 6. КНОПКА "СМОТРЕТЬ"
@routes.post('/api/watch')
async def post_watch(request):
    return web.json_response({"status": "ok"})

# 7. ОЧИСТИТЬ ЧАТ
@routes.post('/api/clear_chat')
async def clear_chat(request):
    return web.json_response({"status": "ok"})

# 8. РАЗДЕЛ "ГОСТИ"
@routes.get('/api/guests')
async def get_guests(request):
    return web.json_response([])

@routes.get('/api/guest_detail')
async def get_guest_detail(request):
    return web.json_response({"messages": []})

@routes.post('/api/send_guest_message')
async def send_guest_message(request):
    return web.json_response({"status": "ok"})

# 9. ЧАСТИ ВИДЕО (1-3 ШТУКИ)
@routes.get('/api/parts')
async def get_movie_parts(request):
    pid = int(request.query.get('pid', '0'))
    con = get_db()
    cur = con.cursor()
    row = cur.execute("SELECT channel_id, channel_msg_id, title FROM movies WHERE post_id = ?", (pid,)).fetchone()
    con.close()

    if not row:
        return web.json_response({"error": "not found"}, status=404)

    channel_id, msg_id, title = row
    parts = []

    try:
        global pyro_client
        if pyro_client and pyro_client.is_connected:
            target_chat = int(channel_id) if str(channel_id).lstrip('-').isdigit() else channel_id
            msg = await pyro_client.get_messages(target_chat, int(msg_id))

            if msg.media_group_id:
                group = await pyro_client.get_media_group(target_chat, int(msg_id))
                for i, m in enumerate(group):
                    if m.video:
                        parts.append({
                            "part": i + 1,
                            "msg_id": m.id,
                            "duration": m.video.duration or 0,
                            "size": m.video.file_size or 0
                        })
            elif msg.video:
                parts.append({
                    "part": 1,
                    "msg_id": msg.id,
                    "duration": msg.video.duration or 0,
                    "size": msg.video.file_size or 0
                })
    except Exception as e:
        print(f"[Python] Ошибка извлечения частей: {e}")

    if not parts:
        parts.append({"part": 1, "msg_id": int(msg_id), "duration": 0, "size": 0})

    return web.json_response({
        "pid": pid,
        "title": title,
        "channel_id": channel_id,
        "parts": parts
    })

# 10. ПОТОКОВОЕ ВОСПРОИЗВЕДЕНИЕ ЧЕРЕЗ EXOPLAYER
@routes.get('/stream')
async def stream_handler(request):
    channel_id = request.query.get('channel_id', '@zubszu')
    msg_id = int(request.query.get('msg_id', '0'))

    global pyro_client
    if not pyro_client or not pyro_client.is_connected:
        return web.Response(text="Pyrogram не подключен", status=503)

    target_chat = int(channel_id) if str(channel_id).lstrip('-').isdigit() else channel_id
    msg = await pyro_client.get_messages(target_chat, msg_id)
    if not msg or not msg.video:
        return web.Response(text="Видео не найдено", status=404)

    file_size = msg.video.file_size
    range_header = request.headers.get('Range', None)

    start = 0
    end = file_size - 1

    if range_header:
        m = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if m:
            start = int(m.group(1))
            if m.group(2):
                end = int(m.group(2))

    content_length = end - start + 1
    headers = {
        'Content-Type': 'video/mp4',
        'Accept-Ranges': 'bytes',
        'Content-Range': f'bytes {start}-{end}/{file_size}',
        'Content-Length': str(content_length)
    }

    response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
    await response.prepare(request)

    chunk_size = 1024 * 1024
    start_chunk = start // chunk_size
    first_skip = start % chunk_size

    try:
        bytes_sent = 0
        async for chunk in pyro_client.stream_media(msg, offset=start_chunk):
            if first_skip > 0:
                chunk = chunk[first_skip:]
                first_skip = 0

            if bytes_sent + len(chunk) > content_length:
                chunk = chunk[:content_length - bytes_sent]

            await response.write(chunk)
            bytes_sent += len(chunk)

            if bytes_sent >= content_length:
                break
    except Exception as e:
        pass

    return response

def start_server_main(app_files_dir):
    global pyro_client, db_path, work_dir
    work_dir = app_files_dir
    db_path = os.path.join(work_dir, "tracker.db")

    session_path = os.path.join(work_dir, "my_session")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from pyrogram import Client
    pyro_client = Client(session_path, api_id=api_id, api_hash=api_hash)

    async def init_app():
        try:
            await pyro_client.start()
            print("[Python] Pyrogram клиент успешно подключен к Telegram")
        except Exception as e:
            print(f"[Python] Запуск без Pyrogram сессии: {e}")

        app = web.Application()
        app.add_routes(routes)
        return app

    app = loop.run_until_complete(init_app())
    web.run_app(app, host='127.0.0.1', port=8080, loop=loop, handle_signals=False)
