import aiosqlite
import re
import math
import time
from datetime import datetime
from contextlib import asynccontextmanager

DB_PATH = 'tracker.db'

@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        yield db

async def init_db():
    async with get_db() as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, url TEXT, category TEXT,
                is_watched INTEGER DEFAULT 0,
                stream_date TEXT DEFAULT '0000-00-00',
                channel_id TEXT, channel_msg_id INTEGER,
                folder TEXT DEFAULT 'zubarev', year INTEGER, genres TEXT
            )
        ''')
        await db.execute('CREATE TABLE IF NOT EXISTS watched (user_id INTEGER, post_id INTEGER, PRIMARY KEY(user_id, post_id))')
        await db.execute('CREATE TABLE IF NOT EXISTS watching (user_id INTEGER, post_id INTEGER, PRIMARY KEY(user_id, post_id))')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_seen INTEGER,
                created_at INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp INTEGER
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                user_id INTEGER,
                message_id INTEGER,
                PRIMARY KEY(user_id, message_id)
            )
        ''')
        
        columns_to_add = [
            ("stream_date", "TEXT DEFAULT '0000-00-00'"),
            ("channel_id", "TEXT"),
            ("channel_msg_id", "INTEGER"),
            ("folder", "TEXT DEFAULT 'zubarev'"),
            ("year", "INTEGER"),
            ("genres", "TEXT")
        ]
        for col_name, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE movies ADD COLUMN {col_name} {col_type}")
            except aiosqlite.OperationalError:
                pass
        await db.commit()

async def record_chat_message(user_id: int, message_id: int):
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO chat_messages (user_id, message_id) VALUES (?, ?)", (user_id, message_id))
        await db.commit()

async def get_and_clear_chat_messages(user_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT message_id FROM chat_messages WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        msg_ids = [r[0] for r in rows]
        await db.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
        await db.commit()
        return msg_ids

async def register_or_update_user(user_id: int, username: str = "", first_name: str = ""):
    now = int(time.time())
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if await cursor.fetchone():
            await db.execute(
                "UPDATE users SET last_seen = ?, username = COALESCE(NULLIF(?, ''), username), first_name = COALESCE(NULLIF(?, ''), first_name) WHERE user_id = ?",
                (now, username, first_name, user_id)
            )
        else:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, last_seen, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username or "", first_name or "Без имени", now, now)
            )
        await db.commit()

async def log_user_action(user_id: int, action: str, details: str = ""):
    now = int(time.time())
    async with get_db() as db:
        await db.execute("INSERT INTO user_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)", (user_id, action, details, now))
        await db.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now, user_id))
        await db.commit()

async def get_all_guests_db():
    now = int(time.time())
    async with get_db() as db:
        cursor = await db.execute('''
            SELECT u.user_id, u.username, u.first_name, u.last_seen,
                   (SELECT COUNT(*) FROM watched WHERE user_id = u.user_id) as watched_count,
                   (SELECT COUNT(*) FROM watching WHERE user_id = u.user_id) as watching_count
            FROM users u
            ORDER BY u.last_seen DESC
        ''')
        rows = await cursor.fetchall()
        
    guests = []
    for r in rows:
        uid, uname, fname, last_seen, watched, watching = r
        diff = now - (last_seen or 0)
        if diff < 300:
            status_text = "🟢 В сети прямо сейчас"
            status_code = "online"
        elif diff < 3600:
            status_text = f"🟡 Был {diff // 60} мин. назад"
            status_code = "recent"
        elif diff < 86400:
            status_text = f"⚪️ Был {diff // 3600} ч. назад"
            status_code = "offline"
        else:
            dt = datetime.fromtimestamp(last_seen).strftime('%d.%m.%Y') if last_seen else "Давно"
            status_text = f"⚪️ Был {dt}"
            status_code = "offline"
            
        guests.append({
            "user_id": uid,
            "username": f"@{uname}" if uname else "нет",
            "name": fname or f"Гость {uid}",
            "status": status_text,
            "status_code": status_code,
            "watched": watched,
            "watching": watching
        })
    return guests

async def get_guest_detail_db(target_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT user_id, username, first_name, last_seen, created_at FROM users WHERE user_id = ?", (target_id,))
        u = await cursor.fetchone()
        if not u: return None
        
        w_z = (await (await db.execute("SELECT COUNT(*) FROM watched w JOIN movies m ON w.post_id = m.post_id WHERE w.user_id=? AND m.folder='zubarev'", (target_id,))).fetchone())[0]
        w_m = (await (await db.execute("SELECT COUNT(*) FROM watched w JOIN movies m ON w.post_id = m.post_id WHERE w.user_id=? AND m.folder='movies'", (target_id,))).fetchone())[0]
        wt_c = (await (await db.execute("SELECT COUNT(*) FROM watching WHERE user_id = ?", (target_id,))).fetchone())[0]
        
        cursor_logs = await db.execute("SELECT action, details, timestamp FROM user_logs WHERE user_id = ? ORDER BY id DESC LIMIT 50", (target_id,))
        raw_logs = await cursor_logs.fetchall()
        
    formatted_logs = []
    for action, details, ts in raw_logs:
        dt = datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')
        formatted_logs.append({"action": action, "details": details or "", "time": dt})
        
    return {
        "user_id": u[0],
        "username": f"@{u[1]}" if u[1] else "нет",
        "name": u[2] or f"Гость {u[0]}",
        "registered": datetime.fromtimestamp(u[4]).strftime('%d.%m.%Y') if u[4] else "Неизвестно",
        "watched_z": w_z,
        "watched_m": w_m,
        "total_watched": w_z + w_m,
        "watching_count": wt_c,
        "logs": formatted_logs
    }

def parse_date(date_str: str) -> str:
    if not date_str: return "0000-00-00"
    date_str = date_str.strip().lower()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str): return date_str
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
        'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04', 'май': '05', 'мая': '05',
        'июн': '06', 'июл': '07', 'авг': '08', 'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12'
    }
    try:
        clean_str = re.sub(r'[^0-9a-zа-я]', '.', date_str)
        parts = [p for p in clean_str.split('.') if p]
        if len(parts) >= 3:
            d, m, y = parts[0], parts[1], parts[2]
            for k, v in months.items():
                if k in m:
                    m = v
                    break
            if len(y) == 2: y = "20" + y
            if len(d) == 1: d = "0" + d
            if len(m) == 1: m = "0" + m
            if len(y) == 4 and y.isdigit() and m.isdigit() and d.isdigit():
                return f"{y}-{m}-{d}"
    except Exception: pass
    return "0000-00-00"

async def clean_database_dates():
    async with get_db() as db:
        async with db.execute("SELECT post_id, stream_date FROM movies") as cursor:
            movies = await cursor.fetchall()
            for pid, d in movies:
                if not d or d == '0000-00-00' or d == 'NULL': continue
                clean_d = re.sub(r'[^0-9]', '-', d)
                parts = [p for p in clean_d.split('-') if p]
                if len(parts) >= 3:
                    y, m, day = "", "", ""
                    if len(parts[0]) == 4: y, m, day = parts[0], parts[1], parts[2]
                    elif len(parts[2]) == 4: day, m, y = parts[0], parts[1], parts[2]
                    else: y, m, day = parts[0], parts[1], parts[2]
                    if len(y) == 2: y = "20" + y
                    if len(m) == 1: m = "0" + m
                    if len(day) == 1: day = "0" + day
                    if len(y) == 4 and y.isdigit() and m.isdigit() and day.isdigit():
                        fixed_date = f"{y}-{m}-{day}"
                        if fixed_date != d:
                            await db.execute("UPDATE movies SET stream_date = ? WHERE post_id = ?", (fixed_date, pid))
        await db.commit()

async def map_movie_categories():
    async with get_db() as db:
        async with db.execute("SELECT post_id, genres FROM movies WHERE folder='movies' AND category='ALL'") as cursor:
            movies = await cursor.fetchall()
            for pid, genres in movies:
                g = str(genres).lower() if genres else ""
                cat = "🍿 Разное"
                if "мульт" in g or "аниме" in g or "детск" in g: cat = "🧸 Мультфильмы / Аниме"
                elif "ужас" in g or "триллер" in g: cat = "🫣 Ужасы / Триллер"
                elif "комед" in g: cat = "😆 Комедия"
                elif "боевик" in g: cat = "🔫 Боевик"
                elif "фантаст" in g or "фэнтези" in g: cat = "🪄 Фантастика / Фэнтези"
                elif "драм" in g or "мелодр" in g: cat = "🍿 Драма / Мелодрама"
                elif "детект" in g or "кримин" in g: cat = "🕵️ Детектив / Криминал"
                elif "приключ" in g or "семейн" in g: cat = "🌍 Приключения / Семейный"
                elif "биограф" in g or "истор" in g or "документ" in g: cat = "📖 Биография / История"
                await db.execute("UPDATE movies SET category = ? WHERE post_id = ?", (cat, pid))
        await db.commit()

async def get_movie_info(user_id: int, post_id: int):
    async with get_db() as db:
        query = '''SELECT m.title, m.url, m.category, m.stream_date,
                   (SELECT 1 FROM watched WHERE user_id=? AND post_id=m.post_id),
                   (SELECT 1 FROM watching WHERE user_id=? AND post_id=m.post_id), 
                   m.folder, m.year, m.genres FROM movies m WHERE m.post_id = ?'''
        cursor = await db.execute(query, (user_id, user_id, post_id))
        return await cursor.fetchone()

async def toggle_movie_action(user_id: int, post_id: int, action: str):
    table = "watched" if action == "watched" else "watching"
    async with get_db() as db:
        cursor = await db.execute(f"SELECT 1 FROM {table} WHERE user_id=? AND post_id=?", (user_id, post_id))
        is_active = False
        if await cursor.fetchone():
            await db.execute(f"DELETE FROM {table} WHERE user_id=? AND post_id=?", (user_id, post_id))
        else:
            await db.execute(f"INSERT INTO {table} (user_id, post_id) VALUES (?, ?)", (user_id, post_id))
            is_active = True
        await db.commit()
        return is_active

async def get_movie_source(post_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT channel_id, channel_msg_id, url, title FROM movies WHERE post_id = ?", (post_id,))
        return await cursor.fetchone()

async def get_user_stats(user_id: int):
    async with get_db() as db:
        total_z = (await (await db.execute("SELECT COUNT(*) FROM movies WHERE folder='zubarev'")).fetchone())[0]
        total_m = (await (await db.execute("SELECT COUNT(*) FROM movies WHERE folder='movies'")).fetchone())[0]
        watched_z = (await (await db.execute("SELECT COUNT(*) FROM watched w JOIN movies m ON w.post_id = m.post_id WHERE w.user_id=? AND m.folder='zubarev'", (user_id,))).fetchone())[0]
        watched_m = (await (await db.execute("SELECT COUNT(*) FROM watched w JOIN movies m ON w.post_id = m.post_id WHERE w.user_id=? AND m.folder='movies'", (user_id,))).fetchone())[0]
        return {
            "total_z": total_z, "total_m": total_m,
            "watched_z": watched_z, "watched_m": watched_m,
            "total_watched": watched_z + watched_m
        }

async def get_watching_list(user_id: int):
    async with get_db() as db:
        cursor = await db.execute('''SELECT m.post_id, m.title, m.folder, m.year, m.category 
                                     FROM movies m JOIN watching x ON m.post_id = x.post_id 
                                     WHERE x.user_id = ? ORDER BY m.post_id DESC''', (user_id,))
        rows = await cursor.fetchall()
        return [{"pid": r[0], "title": r[1], "folder": r[2], "year": r[3], "cat": r[4]} for r in rows]

async def check_duplicate_movie(title: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute("SELECT 1 FROM movies WHERE LOWER(TRIM(title)) = ?", (title.strip().lower(),))
        return (await cursor.fetchone()) is not None

async def add_movie_db(title: str, url: str, category: str, stream_date: str, channel_id: str, channel_msg_id: int, folder: str, year: int = None, genres: str = None):
    async with get_db() as db:
        await db.execute('''
            INSERT INTO movies (title, url, category, stream_date, is_watched, channel_id, channel_msg_id, folder, year, genres)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
        ''', (title, url, category, stream_date, channel_id, channel_msg_id, folder, year, genres))
        await db.commit()

async def update_stream_date_db(post_id: int, new_date: str):
    async with get_db() as db:
        await db.execute("UPDATE movies SET stream_date = ? WHERE post_id = ?", (new_date, post_id))
        await db.commit()

async def delete_movie_db(post_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM movies WHERE post_id = ?", (post_id,))
        await db.execute("DELETE FROM watched WHERE post_id = ?", (post_id,))
        await db.execute("DELETE FROM watching WHERE post_id = ?", (post_id,))
        await db.commit()
