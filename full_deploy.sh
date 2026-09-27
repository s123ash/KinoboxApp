#!/bin/bash
set -e

echo "=== 1. ПОЛУЧЕНИЕ КЛЮЧЕЙ ИЗ CONFIG.PY ==="
python3 -c '
import re
api_id = "0"
api_hash = ""
try:
    with open("app/src/main/python/config.py", "r", encoding="utf-8") as f:
        txt = f.read()
    m_id = re.search(r"API_ID\s*=\s*(\d+)", txt)
    m_hash = re.search(r"API_HASH\s*=\s*[\x27\"]([^\x27\"]+)[\x27\"]", txt)
    if m_id: api_id = m_id.group(1)
    if m_hash: api_hash = m_hash.group(1)
except Exception as e:
    print("Не удалось прочесть config.py:", e)

with open("app/src/main/python/tg_creds.py", "w", encoding="utf-8") as f:
    f.write(f"ADMIN_ID = 846768993\nAPI_ID = {api_id}\nAPI_HASH = \"{api_hash}\"\n")
print(f"✓ Ключи зафиксированы: API_ID={api_id}, ADMIN_ID=846768993")
'

echo "=== 2. СБОРКА БРОНЕБОЙНОГО SERVER.PY ==="
cat << 'PYEOF' > app/src/main/python/server.py
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

import tg_creds
API_ID = getattr(tg_creds, "API_ID", 0)
API_HASH = getattr(tg_creds, "API_HASH", "")
ADMIN_ID = getattr(tg_creds, "ADMIN_ID", 846768993)

routes = web.RouteTableDef()
pyro_client = None

def get_raw_db():
    return sqlite3.connect(db_path)

@routes.get("/")
@routes.get("/index.html")
async def index_handler(request):
    f = os.path.join(work_dir, "index.html")
    if os.path.exists(f):
        return web.FileResponse(f)
    return web.Response(text="index.html not found", status=404)

@routes.get("/api/movies")
async def get_movies(request):
    folder = request.query.get("folder", "zubarev")
    cat = request.query.get("category", "ALL")
    search = request.query.get("search", "").lower().strip()

    con = get_raw_db()
    cur = con.cursor()
    q = """
        SELECT m.post_id, m.title, m.year, m.category, m.genres, m.stream_date,
               CASE WHEN w.post_id IS NOT NULL THEN 1 ELSE 0 END,
               CASE WHEN wt.post_id IS NOT NULL THEN 1 ELSE 0 END,
               m.channel_id, m.channel_msg_id, m.folder
        FROM movies m
        LEFT JOIN watched w ON m.post_id = w.post_id AND w.user_id = ?
        LEFT JOIN watching wt ON m.post_id = wt.post_id AND wt.user_id = ?
        WHERE 1=1
    """
    args = [ADMIN_ID, ADMIN_ID]
    if folder and folder.lower() != "all":
        q += " AND m.folder = ?"; args.append(folder)
    if cat and cat.upper() != "ALL":
        q += " AND m.category = ?"; args.append(cat)
    if search:
        q += " AND LOWER(m.title) LIKE ?"; args.append(f"%{search}%")
    q += " ORDER BY m.post_id ASC"

    rows = cur.execute(q, args).fetchall()
    con.close()

    data = [{
        "post_id": r[0], "id": r[0], "pid": r[0],
        "title": r[1] or "", "year": r[2] or "",
        "category": r[3] or "Разное", "genres": r[4] or "",
        "stream_date": r[5] or "", "date": r[5] or "",
        "is_watched": bool(r[6]), "is_watching": bool(r[7]),
        "channel_id": r[8], "channel_msg_id": r[9],
        "folder": r[10] or "zubarev"
    } for r in rows]
    return web.json_response(data)

@routes.get("/api/movie")
async def get_single_movie(request):
    pid = request.query.get("pid") or request.query.get("id") or "0"
    con = get_raw_db()
    cur = con.cursor()
    q = """
        SELECT m.post_id, m.title, m.category, m.stream_date,
               CASE WHEN w.post_id IS NOT NULL THEN 1 ELSE 0 END,
               CASE WHEN wt.post_id IS NOT NULL THEN 1 ELSE 0 END,
               m.folder, m.year, m.genres, m.channel_id, m.channel_msg_id
        FROM movies m
        LEFT JOIN watched w ON m.post_id = w.post_id AND w.user_id = ?
        LEFT JOIN watching wt ON m.post_id = wt.post_id AND wt.user_id = ?
        WHERE m.post_id = ? LIMIT 1
    """
    r = cur.execute(q, (ADMIN_ID, ADMIN_ID, int(pid))).fetchone()
    con.close()
    if not r: return web.json_response({"error": "not found"}, status=404)
    return web.json_response({
        "pid": r[0], "id": r[0], "post_id": r[0],
        "title": r[1] or "", "category": r[2] or "Разное",
        "date": r[3] or "", "stream_date": r[3] or "",
        "is_watched": bool(r[4]), "is_watching": bool(r[5]),
        "folder": r[6] or "zubarev", "year": r[7] or "",
        "genres": r[8] or "", "channel_id": r[9], "channel_msg_id": r[10]
    })

@routes.get("/api/stats")
async def get_stats(request):
    con = get_raw_db()
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev'").fetchone()[0]
    watched = cur.execute("SELECT COUNT(*) FROM watched WHERE user_id = ?", (ADMIN_ID,)).fetchone()[0]
    watching = cur.execute("SELECT COUNT(*) FROM watching WHERE user_id = ?", (ADMIN_ID,)).fetchone()[0]
    con.close()
    return web.json_response({"total": total, "watched": watched, "watching": watching, "is_admin": True})

@routes.get("/api/watching")
async def get_watching(request):
    con = get_raw_db()
    cur = con.cursor()
    q = """
        SELECT m.post_id, m.title, m.year, m.category, m.genres, m.stream_date
        FROM movies m
        INNER JOIN watching wt ON m.post_id = wt.post_id AND wt.user_id = ?
        ORDER BY wt.rowid DESC
    """
    rows = cur.execute(q, (ADMIN_ID,)).fetchall()
    con.close()
    return web.json_response([{
        "post_id": r[0], "id": r[0], "pid": r[0],
        "title": r[1] or "", "category": r[3] or "Разное",
        "date": r[5] or "", "is_watched": False, "is_watching": True
    } for r in rows])

@routes.post("/api/action")
async def post_action(request):
    try:
        body = await request.json()
        pid = int(body.get("pid", 0))
        act = body.get("action", "")
        con = get_raw_db()
        cur = con.cursor()
        active = False
        if act == "watched":
            ex = cur.execute("SELECT 1 FROM watched WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid)).fetchone()
            if ex:
                cur.execute("DELETE FROM watched WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid))
            else:
                cur.execute("INSERT OR IGNORE INTO watched (user_id, post_id) VALUES (?, ?)", (ADMIN_ID, pid))
                cur.execute("DELETE FROM watching WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid))
                active = True
        elif act == "watching":
            ex = cur.execute("SELECT 1 FROM watching WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid)).fetchone()
            if ex:
                cur.execute("DELETE FROM watching WHERE user_id = ? AND post_id = ?", (ADMIN_ID, pid))
            else:
                cur.execute("INSERT OR IGNORE INTO watching (user_id, post_id) VALUES (?, ?)", (ADMIN_ID, pid))
                active = True
        con.commit()
        con.close()
        return web.json_response({"status": "ok", "active": active})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=400)

@routes.post("/api/watch")
@routes.post("/api/clear_chat")
async def simple_ok(request):
    return web.json_response({"status": "ok"})

@routes.get("/api/guests")
async def guests_handler(request):
    return web.json_response([])

@routes.get("/api/parts")
async def get_parts(request):
    pid = int(request.query.get("pid", "0"))
    con = get_raw_db()
    cur = con.cursor()
    row = cur.execute("SELECT channel_id, channel_msg_id, title FROM movies WHERE post_id = ?", (pid,)).fetchone()
    con.close()
    if not row: return web.json_response({"error": "not found"}, status=404)

    cid, mid, title = row
    parts = []
    global pyro_client
    if pyro_client and pyro_client.is_connected:
        try:
            chat = int(cid) if str(cid).lstrip("-").isdigit() else cid
            msg = await pyro_client.get_messages(chat, int(mid))
            if msg.media_group_id:
                group = await pyro_client.get_media_group(chat, int(mid))
                for idx, m in enumerate(sorted(group, key=lambda x: x.id)):
                    media = m.video or m.document
                    if media:
                        parts.append({"part": idx + 1, "msg_id": m.id, "size": getattr(media, "file_size", 0)})
            else:
                media = msg.video or msg.document
                if media:
                    parts.append({"part": 1, "msg_id": msg.id, "size": getattr(media, "file_size", 0)})
        except Exception:
            pass

    if not parts:
        parts.append({"part": 1, "msg_id": int(mid), "size": 0})
    return web.json_response({"pid": pid, "title": title, "channel_id": cid, "parts": parts})

@routes.head("/stream")
@routes.get("/stream")
async def stream_handler(request):
    cid = request.query.get("channel_id", "@zubszu")
    mid = int(request.query.get("msg_id", "0"))
    global pyro_client
    if not pyro_client or not pyro_client.is_connected:
        return web.Response(text="Pyrogram offline", status=503)

    chat = int(cid) if str(cid).lstrip("-").isdigit() else cid
    msg = await pyro_client.get_messages(chat, mid)
    media = msg.video or msg.document
    if not media: return web.Response(text="No media", status=404)

    fsize = int(media.file_size)
    if request.method == "HEAD":
        return web.Response(headers={"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Content-Length": str(fsize)})

    rh = request.headers.get("Range", None)
    start, end = 0, fsize - 1
    if rh:
        m = re.search(r"bytes=(\d+)-(\d*)", rh)
        if m:
            start = int(m.group(1))
            if m.group(2): end = int(m.group(2))

    clen = end - start + 1
    res = web.StreamResponse(status=206 if rh else 200, headers={
        "Content-Type": "video/mp4", "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{fsize}", "Content-Length": str(clen)
    })
    await res.prepare(request)

    csize = 1024 * 1024
    schunk = start // csize
    fskip = start % csize
    sent = 0

    try:
        async for chunk in pyro_client.stream_media(msg, offset=schunk):
            if fskip > 0:
                chunk = chunk[fskip:]; fskip = 0
            if sent + len(chunk) > clen:
                chunk = chunk[:clen - sent]
            await res.write(chunk)
            sent += len(chunk)
            if sent >= clen: break
    except Exception:
        pass
    return res

def start_server_main(app_files_dir):
    global pyro_client, db_path, work_dir
    work_dir = app_files_dir
    db_path = os.path.join(work_dir, "tracker.db")
    sess_path = os.path.join(work_dir, "my_session")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if API_ID and API_HASH:
        try:
            from pyrogram import Client
            pyro_client = Client(sess_path, api_id=API_ID, api_hash=API_HASH)
            async def tg_init():
                try: await pyro_client.start()
                except Exception as e: print("TG error:", e)
            loop.run_until_complete(tg_init())
        except Exception as e:
            print("Pyrogram init error:", e)

    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, host="127.0.0.1", port=8080, loop=loop, handle_signals=False)
PYEOF

echo "=== 3. ЛОКАЛЬНЫЙ ТЕСТ СЕРВЕРА НА ВАШЕМ НОУТБУКЕ ==="
python3 -c '
import sys, subprocess, time, urllib.request, json
p = subprocess.Popen([sys.executable, "-c", "import sys; sys.path.insert(0, \x27app/src/main/python\x27); import server; server.start_server_main(\x27app/src/main/python\x27)"])
time.sleep(2)
try:
    with urllib.request.urlopen("http://127.0.0.1:8080/api/movies?folder=zubarev", timeout=3) as resp:
        data = json.loads(resp.read().decode())
        print(f"✓ ТЕСТ ПРОЙДЕН УСПЕШНО! Сервер вернул {len(data)} фильмов")
finally:
    p.terminate()
'

echo "=== 4. ОБНОВЛЕНИЕ MAINACTIVITY (СОКЕТНЫЙ ПОЛЛИНГ + ВЫВОД ОШИБОК) ==="
cat << 'KTEOF' > app/src/main/java/com/kinobox/app/MainActivity.kt
package com.kinobox.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.util.Log
import android.webkit.*
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.io.FileOutputStream
import java.net.Socket
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        copyAsset("tracker.db", false)
        copyAsset("my_session.session", false)
        copyAsset("index.html", true)

        webView = WebView(this).apply { setBackgroundColor(Color.parseColor("#0D0D11")) }
        setContentView(webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            cacheMode = WebSettings.LOAD_DEFAULT
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                if (request?.isForMainFrame == true) {
                    view?.postDelayed({ view.loadUrl("http://127.0.0.1:8080") }, 1000)
                }
            }
        }

        webView.addJavascriptInterface(object {
            @JavascriptInterface
            fun openPlayer(pid: Int) {
                startActivity(Intent(this@MainActivity, PlayerActivity::class.java).apply { putExtra("PID", pid) })
            }
        }, "KinoboxNative")

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else { isEnabled = false; onBackPressedDispatcher.onBackPressed() }
            }
        })

        if (!Python.isStarted()) Python.start(AndroidPlatform(this))

        // Запуск Python сервера
        thread(isDaemon = true) {
            try {
                Python.getInstance().getModule("server").callAttr("start_server_main", filesDir.absolutePath)
            } catch (e: Throwable) {
                val err = Log.getStackTraceString(e)
                runOnUiThread {
                    webView.loadDataWithBaseURL(null,
                        "<html><body style='background:#111;color:#ff5555;padding:20px;font-family:monospace;'><h2>Ошибка Python:</h2><pre>$err</pre></body></html>",
                        "text/html", "utf-8", null)
                }
            }
        }

        // Сокетный поллинг: открываем WebView сразу, как только порт 8080 оживет
        thread(isDaemon = true) {
            var ready = false
            for (i in 1..40) {
                try {
                    val s = Socket("127.0.0.1", 8080)
                    s.close()
                    ready = true
                    break
                } catch (e: Exception) {
                    Thread.sleep(250)
                }
            }
            runOnUiThread {
                if (ready) {
                    webView.loadUrl("http://127.0.0.1:8080")
                }
            }
        }
    }

    private fun copyAsset(name: String, overwrite: Boolean) {
        val dest = File(filesDir, name)
        if (overwrite || !dest.exists() || dest.length() == 0L) {
            try {
                assets.open(name).use { input ->
                    dest.parentFile?.mkdirs()
                    FileOutputStream(dest).use { input.copyTo(it) }
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }
}
KTEOF

echo "=== 5. СИНХРОНИЗАЦИЯ ASSETS ==="
mkdir -p app/src/main/assets
cp app/src/main/python/tracker.db app/src/main/assets/tracker.db
cp app/src/main/python/my_session.session app/src/main/assets/my_session.session
cp app/src/main/python/index.html app/src/main/assets/index.html

echo "=== 6. КОММИТ И ПУШ НА GITHUB ==="
git add .
git commit -m "Fix: socket polling, robust server verification and on-screen traceback"
git push

echo "=== 7. ОТСЛЕЖИВАНИЕ СБОРКИ ==="
if command -v gh &> /dev/null; then
    gh run watch
else
    echo "Отслеживание доступно в браузере:"
    echo "https://github.com/s123ash/KinoboxApp/actions"
fi
