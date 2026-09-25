package com.kinobox.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.FileOutputStream

class DatabaseHelper(private val context: Context) {
    private val dbName = "tracker.db"
    private val tag = "KinoboxDB"

    init {
        forceCopyDatabase()
    }

    private fun forceCopyDatabase() {
        try {
            val dbFile = context.getDatabasePath(dbName)
            dbFile.parentFile?.mkdirs()
            // Перезаписываем базу при каждом запуске, чтобы не читать пустой кэш
            context.assets.open("databases/$dbName").use { input ->
                FileOutputStream(dbFile).use { output ->
                    input.copyTo(output)
                }
            }
            Log.d(tag, "База успешно скопирована: ${dbFile.length()} байт")
        } catch (e: Exception) {
            Log.e(tag, "Ошибка копирования БД: ${e.message}", e)
        }
    }

    private fun getReadableDb(): SQLiteDatabase? {
        val dbFile = context.getDatabasePath(dbName)
        if (!dbFile.exists()) return null
        return try {
            SQLiteDatabase.openDatabase(dbFile.path, null, SQLiteDatabase.OPEN_READONLY)
        } catch (e: Exception) {
            Log.e(tag, "Ошибка открытия БД: ${e.message}", e)
            null
        }
    }

    // Возвращает массив массивов: [ [post_id, title, year, category, genres, stream_date, is_watched, is_watching], ... ]
    fun getMoviesFiltered(folder: String?, category: String?, search: String?): String {
        val db = getReadableDb() ?: return "[]"
        val rootArray = JSONArray()
        try {
            val queryBuilder = StringBuilder(
                "SELECT post_id, title, year, category, genres, stream_date, is_watched, 0 FROM movies WHERE 1=1"
            )
            val args = mutableListOf<String>()

            val activeFolder = if (folder.isNullOrEmpty() || folder.equals("all", ignoreCase = true)) "zubarev" else folder
            queryBuilder.append(" AND folder = ?")
            args.add(activeFolder)

            if (!category.isNullOrEmpty() && !category.equals("ALL", ignoreCase = true)) {
                queryBuilder.append(" AND category = ?")
                args.add(category)
            }

            if (!search.isNullOrEmpty()) {
                queryBuilder.append(" AND LOWER(title) LIKE ?")
                args.add("%${search.lowercase().trim()}%")
            }

            queryBuilder.append(" ORDER BY post_id ASC")

            val cursor = db.rawQuery(queryBuilder.toString(), args.toTypedArray())

            while (cursor.moveToNext()) {
                val row = JSONArray()
                row.put(cursor.getLong(0))                                     // post_id
                row.put(cursor.getString(1) ?: "")                             // title
                row.put(if (cursor.isNull(2)) JSONObject.NULL else cursor.getString(2)) // year
                row.put(cursor.getString(3) ?: "")                             // category
                row.put(if (cursor.isNull(4)) JSONObject.NULL else cursor.getString(4)) // genres
                row.put(cursor.getString(5) ?: "")                             // stream_date
                row.put(cursor.getInt(6))                                      // is_watched
                row.put(0)                                                     // is_watching
                rootArray.put(row)
            }
            cursor.close()
            Log.d(tag, "Найдено фильмов: ${rootArray.length()} для папки $activeFolder")
        } catch (e: Exception) {
            Log.e(tag, "Ошибка getMoviesFiltered: ${e.message}", e)
        } finally {
            db.close()
        }
        return rootArray.toString()
    }

    fun getSingleMovie(pid: String?): String {
        if (pid.isNullOrEmpty()) return "{}"
        val db = getReadableDb() ?: return "{}"
        val obj = JSONObject()
        try {
            val cursor = db.rawQuery("SELECT post_id, title, category, stream_date, is_watched, folder, genres FROM movies WHERE post_id = ? LIMIT 1", arrayOf(pid))
            if (cursor.moveToFirst()) {
                obj.put("pid", cursor.getLong(0))
                obj.put("title", cursor.getString(1) ?: "")
                obj.put("category", cursor.getString(2) ?: "Разное")
                obj.put("date", cursor.getString(3) ?: "")
                obj.put("is_watched", cursor.getInt(4) == 1)
                obj.put("is_watching", false)
                obj.put("folder", cursor.getString(5) ?: "zubarev")
            }
            cursor.close()
        } catch (e: Exception) {
            Log.e(tag, "Ошибка getSingleMovie: ${e.message}", e)
        } finally {
            db.close()
        }
        return obj.toString()
    }

    fun getStats(): String {
        val db = getReadableDb() ?: return "{\"total\":0,\"watched\":0}"
        val obj = JSONObject()
        try {
            val totalCursor = db.rawQuery("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev'", null)
            var total = 0
            if (totalCursor.moveToFirst()) total = totalCursor.getInt(0)
            totalCursor.close()

            val watchedCursor = db.rawQuery("SELECT COUNT(*) FROM movies WHERE folder = 'zubarev' AND is_watched = 1", null)
            var watched = 0
            if (watchedCursor.moveToFirst()) watched = watchedCursor.getInt(0)
            watchedCursor.close()

            obj.put("total", total)
            obj.put("watched", watched)
            obj.put("is_admin", true)
        } catch (e: Exception) {
            Log.e(tag, "Ошибка getStats: ${e.message}", e)
            obj.put("total", 0)
            obj.put("watched", 0)
        } finally {
            db.close()
        }
        return obj.toString()
    }
}
