import asyncio
import logging
from aiohttp import web
from config import ADMIN_ID
from database import (
    get_db, get_movie_info, toggle_movie_action, get_user_stats, 
    get_watching_list, delete_movie_db, update_stream_date_db, parse_date,
    get_all_guests_db, get_guest_detail_db, log_user_action, 
    get_and_clear_chat_messages, record_chat_message
)

logger = logging.getLogger(__name__)
routes = web.RouteTableDef()

def resolve_user_id(val) -> int:
    try:
        uid = int(val)
        return uid if uid > 0 else ADMIN_ID
    except (TypeError, ValueError):
        return ADMIN_ID

@routes.get('/')
@routes.get('/index.html')
async def index_handler(request):
    response = web.FileResponse('static/index.html')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@routes.get('/api/movies')
async def get_movies_api(request):
    folder = request.query.get('folder', 'zubarev')
    category = request.query.get('category', 'ALL')
    search = request.query.get('search', '').lower().strip()
    user_id = resolve_user_id(request.query.get('user_id'))
    
    async with get_db() as db:
        base_query = """
            SELECT m.post_id, m.title, m.year, m.category, m.genres, m.stream_date,
                   CASE WHEN w.post_id IS NOT NULL THEN 1 ELSE 0 END,
                   CASE WHEN x.post_id IS NOT NULL THEN 1 ELSE 0 END
            FROM movies m
            LEFT JOIN watched w ON m.post_id = w.post_id AND w.user_id = ?
            LEFT JOIN watching x ON m.post_id = x.post_id AND x.user_id = ?
            WHERE m.folder = ?
        """
        params = [user_id, user_id, folder]
        
        if category == "DATE":
            base_query += " ORDER BY CASE WHEN m.stream_date = '0000-00-00' OR m.stream_date IS NULL THEN 1 ELSE 0 END, m.stream_date DESC"
        elif category != "ALL":
            if folder == 'zubarev':
                base_query += " AND m.category = ?"
                params.append(category)
            else:
                base_query += " AND (m.category = ? OR m.genres LIKE ?)"
                params.extend([category, f"%{category}%"])
                
        if category != "DATE":
            base_query += " ORDER BY m.post_id DESC"
            
        cursor = await db.execute(base_query, params)
        rows = await cursor.fetchall()
        
    data = []
    for r in rows:
        title = r[1]
        if search and search not in title.lower():
            continue
        cat_display = r[3] if folder == 'zubarev' else (r[4] or r[3] or 'Разное')
        data.append({
            "pid": r[0],
            "title": title,
            "year": r[2],
            "cat": cat_display,
            "date": r[5] if r[5] and r[5] != '0000-00-00' else None,
            "is_watched": bool(r[6]),
            "is_watching": bool(r[7])
        })
        
    return web.json_response(data)

@routes.get('/api/movie')
async def get_single_movie_api(request):
    pid_param = request.query.get('pid')
    if not pid_param or not pid_param.isdigit():
        return web.json_response({"error": "invalid pid"}, status=400)
    pid = int(pid_param)
    user_id = resolve_user_id(request.query.get('user_id'))
    
    m = await get_movie_info(user_id, pid)
    if not m:
        return web.json_response({"error": "not found"}, status=404)
        
    cat_display = m[2] if m[6] == 'zubarev' else (m[8] or m[2] or 'Разное')
    
    if user_id != ADMIN_ID:
        asyncio.create_task(log_user_action(user_id, "🔍 Открыл фильм", m[0]))
        
    return web.json_response({
        "pid": pid,
        "title": m[0],
        "category": cat_display,
        "date": m[3],
        "is_watched": bool(m[4]),
        "is_watching": bool(m[5]),
        "folder": m[6],
        "year": m[7],
        "genres": m[8],
        "is_admin": (user_id == ADMIN_ID)
    })

@routes.post('/api/action')
async def post_movie_action(request):
    data = await request.json()
    user_id = resolve_user_id(data.get('user_id'))
    pid = int(data['pid'])
    action = data['action']
    new_state = await toggle_movie_action(user_id, pid, action)
    
    m = await get_movie_info(user_id, pid)
    title = m[0] if m else f"ID: {pid}"
    if action == "watched":
        log_text = "✅ Отметил просмотренным" if new_state else "⏳ Снял отметку просмотра"
    else:
        log_text = "👀 Добавил в «Смотрю»" if new_state else "☑️ Убрал из «Смотрю»"
    asyncio.create_task(log_user_action(user_id, log_text, title))
    
    return web.json_response({"status": "ok", "active": new_state})

@routes.post('/api/watch')
async def post_watch_api(request):
    data = await request.json()
    pid = int(data['pid'])
    user_id = resolve_user_id(data.get('user_id'))
    
    bot = request.app['bot']
    userbot = request.app['userbot']
    
    from handlers import deliver_video
    asyncio.create_task(deliver_video(user_id, pid, bot, userbot))
    return web.json_response({"status": "ok"})

@routes.post('/api/delete_movie')
async def delete_movie_api(request):
    data = await request.json()
    user_id = resolve_user_id(data.get('user_id'))
    if user_id != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)
        
    pid = int(data['pid'])
    await delete_movie_db(pid)
    asyncio.create_task(log_user_action(user_id, "🗑 Удалил фильм из базы", f"ID: {pid}"))
    return web.json_response({"status": "ok"})

@routes.post('/api/edit_date')
async def edit_date_api(request):
    data = await request.json()
    user_id = resolve_user_id(data.get('user_id'))
    if user_id != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)
        
    pid = int(data['pid'])
    new_date = parse_date(data.get('date', ''))
    await update_stream_date_db(pid, new_date)
    asyncio.create_task(log_user_action(user_id, "✏️ Изменил дату стрима", f"Фильм {pid} -> {new_date}"))
    return web.json_response({"status": "ok", "date": new_date})

@routes.post('/api/send_guest_message')
async def send_guest_message_api(request):
    data = await request.json()
    user_id = resolve_user_id(data.get('user_id'))
    if user_id != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)
        
    target_id = int(data.get('target_id', 0))
    text = str(data.get('text', '')).strip()
    if not target_id or not text:
        return web.json_response({"error": "empty data"}, status=400)
        
    bot = request.app['bot']
    try:
        sent_msg = await bot.send_message(chat_id=target_id, text=text)
        await record_chat_message(target_id, sent_msg.message_id)
        asyncio.create_task(log_user_action(target_id, "📩 Сообщение от админа", text))
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю {target_id}: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=400)

@routes.get('/api/guests')
async def get_guests_api(request):
    user_id = resolve_user_id(request.query.get('user_id'))
    if user_id != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)
    guests = await get_all_guests_db()
    return web.json_response(guests)

@routes.get('/api/guest_detail')
async def get_guest_detail_api(request):
    user_id = resolve_user_id(request.query.get('user_id'))
    if user_id != ADMIN_ID:
        return web.json_response({"error": "forbidden"}, status=403)
    target_id = int(request.query.get('target_id', 0))
    detail = await get_guest_detail_db(target_id)
    if not detail:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(detail)

@routes.post('/api/clear_chat')
async def clear_chat_api(request):
    data = await request.json()
    user_id = resolve_user_id(data.get('user_id'))
    bot = request.app['bot']
    userbot = request.app['userbot']
    bot_info = await bot.get_me()

    if user_id == ADMIN_ID and userbot.is_connected:
        try:
            msg_ids = []
            async for m in userbot.get_chat_history(bot_info.username, limit=200):
                msg_ids.append(m.id)
            if msg_ids:
                for i in range(0, len(msg_ids), 100):
                    await userbot.delete_messages(bot_info.username, msg_ids[i:i+100])
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Ошибка очистки через юзербота: {e}")

    msg_ids = await get_and_clear_chat_messages(user_id)
    if msg_ids:
        for i in range(0, len(msg_ids), 100):
            chunk = msg_ids[i:i+100]
            try:
                await bot.delete_messages(chat_id=user_id, message_ids=chunk)
            except Exception:
                for mid in chunk:
                    try: await bot.delete_message(chat_id=user_id, message_id=mid)
                    except Exception: pass
            await asyncio.sleep(0.05)

    from handlers import send_clean_start_message
    await send_clean_start_message(user_id, bot)
    
    asyncio.create_task(log_user_action(user_id, "🧹 Очистил историю чата"))
    return web.json_response({"status": "ok"})

@routes.get('/api/stats')
async def get_stats_api(request):
    user_id = resolve_user_id(request.query.get('user_id'))
    stats = await get_user_stats(user_id)
    stats["resolved_user_id"] = user_id
    stats["is_admin"] = (user_id == ADMIN_ID)
    return web.json_response(stats)

@routes.get('/api/watching')
async def get_watching_api(request):
    user_id = resolve_user_id(request.query.get('user_id'))
    data = await get_watching_list(user_id)
    return web.json_response(data)

app = web.Application()
app.add_routes(routes)
app.router.add_static('/static', 'static', show_index=False)
