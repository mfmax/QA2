#!/usr/bin/env python3
"""
Индексация пар Q&A из SQLite в Qdrant через LangChain
"""
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict
import sqlite3

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain.docstore.document import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from tqdm import tqdm

import rag_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QAIndexer:
    def __init__(self):
        """Инициализация индексера"""
        logger.info("Инициализация QA Indexer...")
        
        # Инициализация embeddings модели
        logger.info(f"Загрузка модели эмбеддингов: {rag_config.EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=rag_config.EMBEDDING_MODEL,
            model_kwargs={'device': rag_config.EMBEDDING_DEVICE},
            encode_kwargs={'batch_size': rag_config.EMBEDDING_BATCH_SIZE}
        )
        
        # Создание директории для Qdrant если не существует
        rag_config.QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ Индексер инициализирован")
    
    def load_qa_pairs_from_db(self) -> List[Dict]:
        """Загрузка пар Q&A из SQLite"""
        logger.info("Загрузка данных из базы данных...")
        
        conn = sqlite3.connect(rag_config.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Построение запроса с учётом настроек
        query = """
            SELECT 
                id, question, answer, direction, question_type, 
                keywords, filename, dialog_id,
                call_direction, operator_phone, client_phone, 
                call_date, call_time
            FROM qa_pairs
            WHERE 1=1
        """
        
        if rag_config.EXCLUDE_IRRELEVANT:
            query += " AND (is_irrelevant = 0 OR is_irrelevant IS NULL)"
        
        if not rag_config.INDEX_ALL_PAIRS:
            query += " AND is_audited = 1"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        # Преобразование в список словарей
        qa_pairs = []
        for row in rows:
            try:
                keywords = json.loads(row['keywords']) if row['keywords'] else []
            except:
                keywords = []
            
            qa_pairs.append({
                'id': row['id'],
                'question': row['question'],
                'answer': row['answer'],
                'direction': row['direction'],
                'question_type': row['question_type'] or '',
                'keywords': keywords,
                'filename': row['filename'],
                'dialog_id': row['dialog_id'],
                'call_direction': row['call_direction'] or '',
                'operator_phone': row['operator_phone'] or '',
                'client_phone': row['client_phone'] or '',
                'call_date': row['call_date'] or '',
                'call_time': row['call_time'] or ''
            })
        
        logger.info(f"✅ Загружено {len(qa_pairs)} пар Q&A")
        return qa_pairs
    
    def prepare_documents(self, qa_pairs: List[Dict]) -> List[Document]:
        """Подготовка документов для индексации"""
        logger.info("Подготовка документов для индексации...")
        
        documents = []
        for pair in qa_pairs:
            # Формируем текст для эмбеддинга (вопрос + ответ)
            # Префикс для multilingual-e5 моделей улучшает качество
            page_content = f"query: {pair['question']}\n\npassage: {pair['answer']}"
            
            # Метаданные для фильтрации и отображения
            metadata = {
                'id': pair['id'],
                'question': pair['question'],
                'answer': pair['answer'],
                'direction': pair['direction'],
                'question_type': pair['question_type'],
                'keywords': ', '.join(pair['keywords']),
                'filename': pair['filename'],
                'dialog_id': pair['dialog_id'],
                'call_direction': pair['call_direction'],
                'operator_phone': pair['operator_phone'],
                'client_phone': pair['client_phone'],
                'call_date': pair['call_date'],
                'call_time': pair['call_time']
            }
            
            doc = Document(page_content=page_content, metadata=metadata)
            documents.append(doc)
        
        logger.info(f"✅ Подготовлено {len(documents)} документов")
        return documents
    
    def index_documents(self, documents: List[Document]):
        """Индексация документов в Qdrant через LangChain"""
        logger.info("Индексация документов в Qdrant...")
        
        total_docs = len(documents)
        batch_size = 100  # Размер батча для прогресс-бара
        
        # Создаём прогресс-бар
        with tqdm(total=total_docs, desc="Индексация документов", unit="docs") as pbar:
            # Обёртка для отслеживания прогресса
            def progress_callback(batch_num, total_batches):
                pbar.update(batch_size)
            
            # Создание vectorstore через LangChain
            vectorstore = Qdrant.from_documents(
                documents=documents,
                embedding=self.embeddings,
                path=str(rag_config.QDRANT_PATH),
                collection_name=rag_config.QDRANT_COLLECTION_NAME,
                force_recreate=True,
                batch_size=batch_size
            )
            
            # Обновляем до конца если остались
            pbar.update(total_docs - pbar.n)
        
        logger.info("✅ Индексация завершена")
        return vectorstore
    
    def run(self):
        """Полный цикл индексации"""
        try:
            logger.info("="*60)
            logger.info("ЗАПУСК ИНДЕКСАЦИИ Q&A В QDRANT")
            logger.info("="*60)
            
            # 1. Загрузка данных
            qa_pairs = self.load_qa_pairs_from_db()
            
            if not qa_pairs:
                logger.warning("❌ Нет данных для индексации")
                return False
            
            # 2. Подготовка документов
            documents = self.prepare_documents(qa_pairs)
            
            # 3. Индексация (метод сам пересоздаст коллекцию)
            logger.info("Начинается индексация (это может занять время)...")
            vectorstore = self.index_documents(documents)
            
            # 4. Проверка (создаём новый клиент для проверки)
            check_client = QdrantClient(path=str(rag_config.QDRANT_PATH))
            collection_info = check_client.get_collection(
                collection_name=rag_config.QDRANT_COLLECTION_NAME
            )
            
            logger.info("="*60)
            logger.info("✅ ИНДЕКСАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
            logger.info("="*60)
            logger.info(f"📊 Проиндексировано документов: {collection_info.points_count}")
            logger.info(f"📁 Путь к хранилищу: {rag_config.QDRANT_PATH}")
            logger.info(f"📦 Коллекция: {rag_config.QDRANT_COLLECTION_NAME}")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка при индексации: {e}", exc_info=True)
            return False


def main():
    """Точка входа"""
    if not rag_config.DB_PATH.exists():
        logger.error(f"❌ База данных не найдена: {rag_config.DB_PATH}")
        logger.error("Запустите сначала main.py для создания базы данных")
        return 1
    
    indexer = QAIndexer()
    success = indexer.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())