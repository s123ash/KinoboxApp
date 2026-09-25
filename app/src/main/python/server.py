import os
import sys
import asyncio
import sqlite3
import re
from aiohttp import web

work_dir = os.path.dirname(os.path.abspath(__file__))
if work_dir not in sys.path:
    sys.path.insert(0, work_dir)

db_path = os.path.join(work_dir, "tracker.db")

API_ID = 0
API_HASH = ""
ADMIN_ID = 846768993

try:
    import tg_creds
    API_ID = getattr(tg_creds, 'API_ID', 0)
    API_HASH = getattr(tg_creds, 'API_HASH', '')
    ADMIN_ID = getattr(tg_creds, 'ADMIN_ID', 846768993)
except Exception:
    pass

routes = web.RouteTableDef()
pyro_client = None

def get_raw_db():
    return sqlite3.connect(db_path)

@routes.get('/')
@routes.get('/index.html')
async def index_handler(request):
    html_file = os.path.join(work_dir, "index.html")
    if os.path.exists(html_file):
        return web.FileResponse(html_file)
    return web.Response(text="index.html not found", status=404)

# КАТАЛОГ ФИЛЬМОВ
@routes.get('/api/movies')
async def get_movies(request):
    folder = request.query.get('folder', 'zubarev')
    category = request.query.get('category', 'ALL')
    search = request.query.get('search', '').lower().strip()

    con = get_raw_db()
    cur = con.cursor()

    query = """
        SELECT m.post_id, m.title, m.year, m.category, m.genres, m.stream_date,
               CASE WHEN w.post_id IS NOT NULL THEN 1 ELSE 0 END as is_watched,
               CASE WHEN wt.post_id IS NOT NULL THEN 1 ELSE 0 END as is_watching,
               m.channel_id, m.channel_msg_id, m.folder
        FROM movies m
        LEFT JOIN watched w ON m.post_id = w.post_id AND w.user_id = ?
        LEFT JOIN watching wt ON m.post_id = wt.post_id AND wt.user_id = ?
        WHERE 1=1
    """
    args = [ADMIN_ID, ADMIN_ID]

    if folder and folder.lower() != 'all':
        query += " AND m.folder = ?"
        args.append(folder)

    if category and category.upper() != 'ALL':
        query += " AND m.category = ?"
        args.append(category)

    if search:
        query += " AND LOWER(m.title) LIKE ?"
        args.append(f"%{search}%")

    query += " ORDER BY m.post_id ASC"
    rows = cur.execute(query, args).fetchall()
    con.close()

    data = []
    for r in rows:
        data.append({
            "post_id": r[0],
            "id": r[0],
            "pid": r[0],
            "title": r[1] or "",
            "year": r[2] or "",
            "category": r[3] or "Разное",
            "genres": r[4] or "",
            "stream_date": r[5] or "",
            "date": r[5] or "",
            "is_watched": bool(r[6]),
            "is_watching": bool(r[7]),
            "channel_id": r[8],
            "channel_msg_id": r[9],
            "folder": r[10] or "zubarev"
        })
    return web.json_response(data)

# ДЕТАЛИ ФИЛЬМА
@routes.get('/api/movie')
async def get_single_movie(request):
    pid = request.query.get('pid') or request.query.get('id')
    if not pid or not pid.isdigit():
        return web.json_response({"error": "invalid pid"}, status=400)

    con = get_raw_db()
    cur = con.cursor()
    query = """
        SELECT m.post_id, m.title, m.category, m.stream_date,
               CASE WHEN w.post_id IS NOT NULL THEN 1 ELSE 0 END as is_watched,
               CASE WHEN wt.post_id IS NOT NULL THEN 1 ELSE 0 END as is_watching,
               m.folder, m.year, m.genres, m.channel_id, m.channel_msg_id
        FROM movies m
        LEFT JOIN watched w ON m.post_id = w.post_id AND w.user_id = ?
        LEFT JOIN watching wt ON m.post_id = wt.post_id AND wt.user_id = ?
        WHERE m.post_id = ? LIMIT 1
    """
    r = cur.execute(query, (ADMIN_ID, ADMIN_ID, int(pid))).fetchone()
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
        "is_watching": bool(r[5]),
        "folder": r[6] or "zubarev",
        "year": r[7] or "",
        "genres": r[8] or "",
        "channel_id": r[9],
        "channel_msg_id": r[10]
    })

# СТАТИСТИКА
@routes.get('/api/stats')
async def get_stats(request):
    con = get_raw_db()
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev'").fetchone()[0]
    watched = cur.execute("SELECT COUNT(*) FROM watched WHERE user_id = ?", (ADMIN_ID,)).fetchone()[0]
    watching = cur.execute("SELECT COUNT(*) FROM watching WHERE user_id = ?", (ADMIN_ID,)).fetchone()[0]
    con.close()
    return web.json_response({"total": total, "watched": watched, "watching": watching, "is_admin": True})

# СПИСОК "СМОТРЮ"
@routes.get('/api/watching')
async def get_watching(request):
    con = get_raw_db()
    cur = con.cursor()
    query = """
        SELECT m.post_id, m.title, m.year, m.category, m.genres, m.stream_date, 0, 1, m.channel_id, m.channel_msg_id, m.folder
        FROM movies m
        INNER JOIN watching wt ON m.post_id = wt.post_id AND wt.user_id = ?
        ORDER BY wt.rowid DESC
    """
    rows = cur.execute(query, (ADMIN_ID,)).fetchall()
    con.close()

    data = []
    for r in rows:
        data.append({
            "post_id": r[0],
            "id": r[0],
            "pid": r[0],
            "title": r[1] or "",
            "category": r[3] or "Разное",
            "date": r[5] or "",
            "is_watched": False,
            "is_watching": True,
            "folder": r[10] or "zubarev"
        })
    return web.json_response(data)

# ДЕЙСТВИЯ КНОПОК ("watched", "watching")
@routes.post('/api/action')
async def post_action(request):
    try:
        body = await request.json()
        pid = int(body.get('pid', 0))
        action = body.get('action', '')
        active = False

        con = get_raw_db()
        cur = con.cursor()

        if action == 'watched':
            exists = cur.execute("SELECT 1 FROM watched WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid)).fetchone()
            if exists:
                cur.execute("DELETE FROM watched WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid))
                active = False
            else:
                cur.execute("INSERT OR IGNORE INTO watched (user_id, post_id) VALUES (?, ?)", (ADMIN_ID, pid))
                cur.execute("DELETE FROM watching WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid))
                active = True

        elif action == 'watching':
            exists = cur.execute("SELECT 1 FROM watching WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid)).fetchone()
            if exists:
                cur.execute("DELETE FROM watching WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid))
                active = False
            else:
                cur.execute("INSERT OR IGNORE INTO watching (user_id, post_id) VALUES (?, ?)", (ADMIN_ID, pid))
                active = True

        con.commit()
        con.close()
        return web.json_response({"status": "ok", "active": active})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=400)

@routes.post('/api/watch')
async def post_watch(request):
    return web.json_response({"status": "ok"})

@routes.post('/api/clear_chat')
async def clear_chat(request):
    return web.json_response({"status": "ok"})

@routes.get('/api/guests')
async def get_guests(request):
    return web.json_response([])

# ИЗВЛЕЧЕНИЕ 1-3 ЧАСТЕЙ ВИДЕО ИЗ КАНАЛА
@routes.get('/api/parts')
async def get_movie_parts(request):
    pid = int(request.query.get('pid', '0'))
    con = get_raw_db()
    cur = con.cursor()
    row = cur.execute("SELECT channel_id, channel_msg_id, title FROM movies WHERE post_id = ?", (pid,)).fetchone()
    con.close()

    if not row:
        return web.json_response({"error": "not found"}, status=404)

    channel_id, msg_id, title = row
    parts = []

    global pyro_client
    if pyro_client and pyro_client.is_connected:
        try:
            target_chat = int(channel_id) if str(channel_id).lstrip('-').isdigit() else channel_id
            msg = await pyro_client.get_messages(target_chat, int(msg_id))

            if msg.media_group_id:
                group = await pyro_client.get_media_group(target_chat, int(msg_id))
                group = sorted(group, key=lambda m: m.id)
                for idx, m in enumerate(group):
                    media = m.video or m.document
                    if media:
                        parts.append({
                            "part": idx + 1,
                            "msg_id": m.id,
                            "duration": getattr(media, 'duration', 0) or 0,
                            "size": getattr(media, 'file_size', 0) or 0
                        })
            else:
                media = msg.video or msg.document
                if media:
                    parts.append({
                        "part": 1,
                        "msg_id": msg.id,
                        "duration": getattr(media, 'duration', 0) or 0,
                        "size": getattr(media, 'file_size', 0) or 0
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

# ПОТОКОВОЕ ВОСПРОИЗВЕДЕНИЕ (С ПОДДЕРЖКОЙ HEAD И RANGE ДЛЯ ФАЙЛОВ > 2 ГБ)
@routes.route('HEAD', '/stream')
@routes.get('/stream')
async def stream_handler(request):
    channel_id = request.query.get('channel_id', '@zubszu')
    msg_id = int(request.query.get('msg_id', '0'))

    global pyro_client
    if not pyro_client or not pyro_client.is_connected:
        return web.Response(text="Pyrogram не подключен", status=503)

    target_chat = int(channel_id) if str(channel_id).lstrip('-').isdigit() else channel_id
    try:
        msg = await pyro_client.get_messages(target_chat, msg_id)
    except Exception as e:
        return web.Response(text=f"Сообщение не найдено: {e}", status=404)

    media = msg.video or msg.document
    if not media:
        return web.Response(text="Видео не найдено", status=404)

    file_size = int(media.file_size)

    # Обработка HEAD-запроса от ExoPlayer
    if request.method == 'HEAD':
        return web.Response(status=200, headers={
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size)
        })

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
    except Exception:
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
    pyro_client = Client(session_path, api_id=API_ID, api_hash=API_HASH)

    async def init_app():
        try:
            await pyro_client.start()
            print("[Python] Pyrogram успешно подключен к Telegram")
            try:
                await pyro_client.get_chat("@zubszu")
            except Exception:
                pass
        except Exception as e:
            print(f"[Python] Ошибка старта Pyrogram: {e}")

        app = web.Application()
        app.add_routes(routes)
        return app

    app = loop.run_until_complete(init_app())
    web.run_app(app, host='127.0.0.1', port=8080, loop=loop, handle_signals=False)
