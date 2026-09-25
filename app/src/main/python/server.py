import os
import sys
import asyncio
import sqlite3
import re
from aiohttp import web

# Подгружаем переменные окружения и конфиг
work_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(work_dir, "tracker.db")

api_id = 0
api_hash = ""
try:
    with open(os.path.join(work_dir, ".env"), "r", encoding="utf-8") as f:
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

@routes.get('/api/movies')
async def get_movies(request):
    folder = request.query.get('folder', 'zubarev')
    category = request.query.get('category', 'ALL')
    search = request.query.get('search', '').lower().strip()

    con = get_db()
    cur = con.cursor()

    query = "SELECT post_id, title, year, category, genres, stream_date, is_watched, 0 FROM movies WHERE 1=1"
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

    data = [list(r) for r in rows]
    return web.json_response(data)

@routes.get('/api/stats')
async def get_stats(request):
    con = get_db()
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev'").fetchone()[0]
    watched = cur.execute("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev' AND is_watched = 1").fetchone()[0]
    con.close()
    return web.json_response({"total": total, "watched": watched, "is_admin": True})

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
            target_chat = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
            msg = await pyro_client.get_messages(target_chat, msg_id)

            if msg.media_group_id:
                group = await pyro_client.get_media_group(target_chat, msg_id)
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
        print(f"[Python] Ошибка получения частей: {e}")

    # Fallback, если оффлайн или 1 видео
    if not parts:
        parts.append({"part": 1, "msg_id": msg_id, "duration": 0, "size": 0})

    return web.json_response({
        "pid": pid,
        "title": title,
        "channel_id": channel_id,
        "parts": parts
    })

@routes.get('/stream')
async def stream_handler(request):
    channel_id = request.query.get('channel_id', '@zubszu')
    msg_id = int(request.query.get('msg_id', '0'))

    global pyro_client
    if not pyro_client or not pyro_client.is_connected:
        return web.Response(text="Pyrogram не подключен", status=503)

    target_chat = int(channel_id) if channel_id.lstrip('-').isdigit() else channel_id
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

    chunk_size = 1024 * 1024  # 1 МБ чанки
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
        print(f"[Python] Стриминг прерван клиентом: {e}")

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
        await pyro_client.start()
        print("[Python] Pyrogram клиент успешно авторизован и запущен")
        app = web.Application()
        app.add_routes(routes)
        return app

    app = loop.run_until_complete(init_app())
    web.run_app(app, host='127.0.0.1', port=8080, loop=loop, handle_signals=False)
