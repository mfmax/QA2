#!/usr/bin/env python3
"""
Скрипт миграции БД - добавление поля is_irrelevant
"""
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
import config

def migrate():
    """Добавить поле is_irrelevant в таблицу qa_pairs"""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли уже поле
        cursor.execute("PRAGMA table_info(qa_pairs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_irrelevant' not in columns:
            print("Добавление поля is_irrelevant...")
            cursor.execute("""
                ALTER TABLE qa_pairs 
                ADD COLUMN is_irrelevant INTEGER DEFAULT 0
            """)
            conn.commit()
            print("✅ Поле is_irrelevant успешно добавлено!")
        else:
            print("⚠️  Поле is_irrelevant уже существует")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        conn.close()
        sys.exit(1)

if __name__ == "__main__":
    migrate()