package com.kinobox.app

import android.content.Context
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
            Log.e(tag, "Ошибка копирования базы данных: ${e.message}", e)
        }
    }

    private fun copyDatabaseIfNeeded() {
        val dbFile = context.getDatabasePath(dbName)
        if (!dbFile.exists()) {
            dbFile.parentFile?.mkdirs()
            context.assets.open("databases/$dbName").use { input ->
                FileOutputStream(dbFile).use { output ->
                    input.copyTo(output)
                }
            }
            Log.d(tag, "База успешно скопирована из assets")
        }
    }

    fun getAllMoviesJson(): String {
        val dbFile = context.getDatabasePath(dbName)
        if (!dbFile.exists()) {
            Log.w(tag, "Файл базы данных не найден по пути: ${dbFile.path}")
            return "[]"
        }

        val array = JSONArray()
        var db: SQLiteDatabase? = null
        try {
            db = SQLiteDatabase.openDatabase(dbFile.path, null, SQLiteDatabase.OPEN_READONLY)

            // Ищем таблицу с фильмами (исключая системные таблицы sqlite)
            val tableCursor = db.rawQuery(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'android_%' LIMIT 1",
                null
            )
            var tableName = "movies"
            if (tableCursor.moveToFirst()) {
                tableName = tableCursor.getString(0)
            }
            tableCursor.close()

            val cursor = db.rawQuery("SELECT * FROM $tableName", null)
            val columnNames = cursor.columnNames

            while (cursor.moveToNext()) {
                val obj = JSONObject()
                for (col in columnNames) {
                    val index = cursor.getColumnIndex(col)
                    obj.put(col, cursor.getString(index) ?: "")
                }
                array.put(obj)
            }
            cursor.close()
        } catch (e: Exception) {
            Log.e(tag, "Ошибка чтения фильмов из БД: ${e.message}", e)
        } finally {
            db?.close()
        }
        return array.toString()
    }
}
