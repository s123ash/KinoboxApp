package com.kinobox.app

import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

class DatabaseHelper(private val context: Context) {
    private val dbName = "tracker.db"
    private val tag = "KinoboxDB"

    init {
        try {
            copyDatabaseIfNeeded()
        } catch (e: Exception) {
            Log.e(tag, "Ошибка копирования БД: ${e.message}", e)
        }
    }

    private fun copyDatabaseIfNeeded() {
        val dbFile = context.getDatabasePath(dbName)
        val assetSize = try {
            context.assets.open("databases/$dbName").use { it.available().toLong() }
        } catch (e: Exception) {
            0L
        }

        // Если файла нет, он пустой или отличается по размеру от ассета — обновляем
        if (!dbFile.exists() || dbFile.length() == 0L || (assetSize > 0 && dbFile.length() != assetSize)) {
            dbFile.parentFile?.mkdirs()
            context.assets.open("databases/$dbName").use { input ->
                FileOutputStream(dbFile).use { output ->
                    input.copyTo(output)
                }
            }
            Log.d(tag, "База успешно скопирована из assets (${dbFile.length()} байт)")
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

    fun getMoviesFiltered(folder: String?, category: String?, search: String?): String {
        val db = getReadableDb() ?: return "[]"
        val array = JSONArray()
        try {
            val queryBuilder = StringBuilder("SELECT * FROM movies WHERE 1=1")
            val args = mutableListOf<String>()

            if (!folder.isNullOrEmpty() && !folder.equals("all", ignoreCase = true)) {
                queryBuilder.append(" AND folder = ?")
                args.add(folder)
            }

            if (!category.isNullOrEmpty() && !category.equals("all", ignoreCase = true)) {
                queryBuilder.append(" AND category = ?")
                args.add(category)
            }

            if (!search.isNullOrEmpty()) {
                queryBuilder.append(" AND LOWER(title) LIKE ?")
                args.add("%${search.lowercase().trim()}%")
            }

            queryBuilder.append(" ORDER BY post_id ASC")

            val cursor = db.rawQuery(queryBuilder.toString(), args.toTypedArray())
            val columnNames = cursor.columnNames

            while (cursor.moveToNext()) {
                val obj = JSONObject()
                for (i in columnNames.indices) {
                    val col = columnNames[i]
                    when (cursor.getType(i)) {
                        Cursor.FIELD_TYPE_NULL -> obj.put(col, JSONObject.NULL)
                        Cursor.FIELD_TYPE_INTEGER -> obj.put(col, cursor.getLong(i))
                        Cursor.FIELD_TYPE_FLOAT -> obj.put(col, cursor.getDouble(i))
                        Cursor.FIELD_TYPE_STRING -> obj.put(col, cursor.getString(i))
                        Cursor.FIELD_TYPE_BLOB -> obj.put(col, "")
                    }
                }
                array.put(obj)
            }
            cursor.close()
        } catch (e: Exception) {
            Log.e(tag, "Ошибка getMoviesFiltered: ${e.message}", e)
        } finally {
            db.close()
        }
        return array.toString()
    }

    fun getSingleMovie(pid: String?): String {
        if (pid.isNullOrEmpty()) return "{}"
        val db = getReadableDb() ?: return "{}"
        val obj = JSONObject()
        try {
            val cursor = db.rawQuery("SELECT * FROM movies WHERE post_id = ? LIMIT 1", arrayOf(pid))
            if (cursor.moveToFirst()) {
                val columnNames = cursor.columnNames
                for (i in columnNames.indices) {
                    val col = columnNames[i]
                    when (cursor.getType(i)) {
                        Cursor.FIELD_TYPE_NULL -> obj.put(col, JSONObject.NULL)
                        Cursor.FIELD_TYPE_INTEGER -> obj.put(col, cursor.getLong(i))
                        Cursor.FIELD_TYPE_FLOAT -> obj.put(col, cursor.getDouble(i))
                        Cursor.FIELD_TYPE_STRING -> obj.put(col, cursor.getString(i))
                        Cursor.FIELD_TYPE_BLOB -> obj.put(col, "")
                    }
                }
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
            val totalCursor = db.rawQuery("SELECT COUNT(*) FROM movies", null)
            var total = 0
            if (totalCursor.moveToFirst()) total = totalCursor.getInt(0)
            totalCursor.close()

            val watchedCursor = db.rawQuery("SELECT COUNT(*) FROM movies WHERE is_watched = 1", null)
            var watched = 0
            if (watchedCursor.moveToFirst()) watched = watchedCursor.getInt(0)
            watchedCursor.close()

            obj.put("total", total)
            obj.put("watched", watched)
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
