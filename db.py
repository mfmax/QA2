import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import json
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._init_db()
    
    def _init_db(self):
        """Инициализация БД и создание таблиц"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Таблица обработанных файлов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                dialog_id TEXT,
                call_direction TEXT,
                operator_phone TEXT,
                client_phone TEXT,
                call_date DATE,
                call_time TIME,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_pairs INTEGER DEFAULT 0,
                has_business_pairs BOOLEAN DEFAULT 1,
                error TEXT
            )
        """)
        
        # Таблица пар вопрос-ответ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dialog_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                call_direction TEXT,
                operator_phone TEXT,
                client_phone TEXT,
                call_date DATE,
                call_time TIME,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                direction TEXT NOT NULL,
                question_type TEXT,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                quality_score REAL,
                is_audited INTEGER DEFAULT 0,
                FOREIGN KEY (filename) REFERENCES processed_files(filename)
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_filename 
            ON qa_pairs(filename)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dialog_id 
            ON qa_pairs(dialog_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_direction 
            ON qa_pairs(direction)
        """)
        
        self.conn.commit()
        logger.info(f"База данных инициализирована: {self.db_path}")
    
    def is_file_processed(self, filename: str) -> bool:
        """Проверка, обработан ли файл"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM processed_files WHERE filename = ?",
            (filename,)
        )
        return cursor.fetchone() is not None
    
    def mark_file_processed(self, filename: str, total_pairs: int, 
                           has_business_pairs: bool, error: str = None, *,
                           file_metadata: dict = None):
        """Отметить файл как обработанный"""
        cursor = self.conn.cursor()
        
        # Проверяем, существует ли уже запись
        cursor.execute("SELECT id FROM processed_files WHERE filename = ?", (filename,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую запись
            if file_metadata:
                cursor.execute("""
                    UPDATE processed_files 
                    SET processed_at = CURRENT_TIMESTAMP,
                        total_pairs = ?,
                        has_business_pairs = ?,
                        error = ?,
                        dialog_id = ?,
                        call_direction = ?,
                        operator_phone = ?,
                        client_phone = ?,
                        call_date = ?,
                        call_time = ?
                    WHERE filename = ?
                """, (total_pairs, has_business_pairs, error,
                      file_metadata.get('dialog_id'),
                      file_metadata.get('call_direction'),
                      file_metadata.get('operator_phone'),
                      file_metadata.get('client_phone'),
                      file_metadata.get('call_date'),
                      file_metadata.get('call_time'),
                      filename))
            else:
                cursor.execute("""
                    UPDATE processed_files 
                    SET processed_at = CURRENT_TIMESTAMP,
                        total_pairs = ?,
                        has_business_pairs = ?,
                        error = ?
                    WHERE filename = ?
                """, (total_pairs, has_business_pairs, error, filename))
        else:
            # Создаём новую запись
            if file_metadata:
                cursor.execute("""
                    INSERT INTO processed_files 
                    (filename, total_pairs, has_business_pairs, error,
                     dialog_id, call_direction, operator_phone, client_phone, call_date, call_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (filename, total_pairs, has_business_pairs, error,
                      file_metadata.get('dialog_id'),
                      file_metadata.get('call_direction'),
                      file_metadata.get('operator_phone'),
                      file_metadata.get('client_phone'),
                      file_metadata.get('call_date'),
                      file_metadata.get('call_time')))
            else:
                cursor.execute("""
                    INSERT INTO processed_files (filename, total_pairs, has_business_pairs, error)
                    VALUES (?, ?, ?, ?)
                """, (filename, total_pairs, has_business_pairs, error))
        
        self.conn.commit()
        logger.info(f"Файл отмечен как обработанный: {filename}")
    
    def save_qa_pairs(self, pairs: List[Dict], filename: str, dialog_id: str, file_metadata: dict = None):
        """Сохранить пары Q&A"""
        cursor = self.conn.cursor()
        
        for pair in pairs:
            cursor.execute("""
                INSERT INTO qa_pairs 
                (dialog_id, filename, call_direction, operator_phone, client_phone,
                 call_date, call_time, question, answer, direction, 
                 question_type, keywords, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dialog_id,
                filename,
                file_metadata.get('call_direction') if file_metadata else None,
                file_metadata.get('operator_phone') if file_metadata else None,
                file_metadata.get('client_phone') if file_metadata else None,
                file_metadata.get('call_date') if file_metadata else None,
                file_metadata.get('call_time') if file_metadata else None,
                pair.get('question', ''),
                pair.get('answer', ''),
                pair.get('direction', ''),
                pair.get('question_type', ''),
                json.dumps(pair.get('keywords', []), ensure_ascii=False),
                pair.get('quality_score')
            ))
        
        self.conn.commit()
        logger.info(f"Сохранено {len(pairs)} пар для файла {filename}")
    
    def get_statistics(self) -> Dict:
        """Получить статистику по базе"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Всего обработано файлов
        cursor.execute("SELECT COUNT(*) as count FROM processed_files")
        stats['total_files'] = cursor.fetchone()['count']
        
        # Файлы с бизнес-парами
        cursor.execute("""
            SELECT COUNT(*) as count FROM processed_files 
            WHERE has_business_pairs = 1
        """)
        stats['files_with_pairs'] = cursor.fetchone()['count']
        
        # Всего пар
        cursor.execute("SELECT COUNT(*) as count FROM qa_pairs")
        stats['total_pairs'] = cursor.fetchone()['count']
        
        # По направлениям
        cursor.execute("""
            SELECT direction, COUNT(*) as count 
            FROM qa_pairs 
            GROUP BY direction
        """)
        stats['by_direction'] = {row['direction']: row['count'] 
                                 for row in cursor.fetchall()}
        
        # По типам вопросов
        cursor.execute("""
            SELECT question_type, COUNT(*) as count 
            FROM qa_pairs 
            WHERE question_type IS NOT NULL
            GROUP BY question_type
        """)
        stats['by_type'] = {row['question_type']: row['count'] 
                           for row in cursor.fetchall()}
        
        # Средняя оценка качества
        cursor.execute("SELECT AVG(quality_score) as avg FROM qa_pairs")
        avg_score = cursor.fetchone()['avg']
        stats['avg_quality_score'] = round(avg_score, 2) if avg_score else 0
        
        return stats
    
    def close(self):
        """Закрыть соединение"""
        if self.conn:
            self.conn.close()
            logger.info("Соединение с БД закрыто")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()