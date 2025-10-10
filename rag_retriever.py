#!/usr/bin/env python3
"""
RAG Retriever - Поиск релевантных пар и генерация ответов
"""
import logging
from typing import List, Dict, Optional, Iterator
from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain.schema import Document
from qdrant_client import QdrantClient
from openai import OpenAI

import rag_config

logger = logging.getLogger(__name__)


class RAGRetriever:
    def __init__(self):
        """Инициализация RAG системы"""
        logger.info("Инициализация RAG Retriever...")
        
        # Проверка наличия Qdrant хранилища
        if not rag_config.QDRANT_PATH.exists():
            raise FileNotFoundError(
                f"Qdrant хранилище не найдено: {rag_config.QDRANT_PATH}\n"
                "Запустите сначала rag_indexer.py для индексации данных"
            )
        
        # Инициализация embeddings модели
        logger.info(f"Загрузка модели эмбеддингов: {rag_config.EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=rag_config.EMBEDDING_MODEL,
            model_kwargs={'device': rag_config.EMBEDDING_DEVICE},
            encode_kwargs={'batch_size': rag_config.EMBEDDING_BATCH_SIZE}
        )
        
        # Подключение к Qdrant
        logger.info("Подключение к Qdrant...")
        
        # Создаём клиент Qdrant
        from qdrant_client import QdrantClient
        qdrant_client = QdrantClient(path=str(rag_config.QDRANT_PATH))
        
        self.vectorstore = Qdrant(
            client=qdrant_client,
            collection_name=rag_config.QDRANT_COLLECTION_NAME,
            embeddings=self.embeddings
        )
        
        # Инициализация OpenAI клиента
        if not rag_config.OPENAI_API_KEY:
            raise ValueError("OpenAI API ключ не установлен в .env файле")
        
        self.openai_client = OpenAI(api_key=rag_config.OPENAI_API_KEY)
        
        logger.info("✅ RAG Retriever инициализирован")
    
    def search_similar_pairs(self, query: str, k: int = None) -> List[Dict]:
        """
        Поиск наиболее релевантных пар Q&A
        
        Args:
            query: Вопрос пользователя
            k: Количество результатов (по умолчанию из конфига)
        
        Returns:
            Список найденных пар с метаданными и score
        """
        k = k or rag_config.TOP_K_RESULTS
        
        logger.info(f"Поиск релевантных пар для запроса: '{query[:100]}...'")
        
        # Для multilingual-e5 модели НЕ добавляем префикс при поиске
        # Поиск с оценкой схожести
        results = self.vectorstore.similarity_search_with_score(
            query,  # Без префикса!
            k=k
        )
        
        # Фильтрация по порогу схожести и форматирование результатов
        filtered_results = []
        for doc, score in results:
            # Qdrant возвращает distance, преобразуем в similarity
            # Для COSINE distance: similarity = 1 - distance
            similarity = 1 - score
            
            if similarity >= rag_config.SIMILARITY_THRESHOLD:
                result = {
                    'question': doc.metadata.get('question', ''),
                    'answer': doc.metadata.get('answer', ''),
                    'direction': doc.metadata.get('direction', ''),
                    'question_type': doc.metadata.get('question_type', ''),
                    'keywords': doc.metadata.get('keywords', ''),
                    'similarity_score': round(similarity, 4),
                    'metadata': {
                        'id': doc.metadata.get('id'),
                        'filename': doc.metadata.get('filename', ''),
                        'call_date': doc.metadata.get('call_date', ''),
                        'call_time': doc.metadata.get('call_time', '')
                    }
                }
                filtered_results.append(result)
        
        logger.info(f"✅ Найдено {len(filtered_results)} релевантных пар (порог: {rag_config.SIMILARITY_THRESHOLD})")
        
        return filtered_results
    
    def format_context(self, pairs: List[Dict]) -> str:
        """Форматирование найденных пар в контекст для LLM"""
        if not pairs:
            return "Релевантной информации не найдено."
        
        context_parts = []
        for i, pair in enumerate(pairs, 1):
            context_parts.append(
                f"--- Пара #{i} (релевантность: {pair['similarity_score']:.2%}) ---\n"
                f"Вопрос: {pair['question']}\n"
                f"Ответ: {pair['answer']}\n"
            )
        
        return "\n".join(context_parts)
    
    def generate_answer(self, query: str, context: str) -> str:
        """
        Генерация ответа через OpenAI (без streaming)
        
        Args:
            query: Вопрос пользователя
            context: Контекст из найденных пар
        
        Returns:
            Сгенерированный ответ
        """
        logger.info("Генерация ответа через OpenAI...")
        
        messages = [
            {"role": "system", "content": rag_config.SYSTEM_PROMPT},
            {"role": "user", "content": rag_config.USER_PROMPT_TEMPLATE.format(
                question=query,
                context=context
            )}
        ]
        
        response = self.openai_client.chat.completions.create(
            model=rag_config.OPENAI_MODEL,
            messages=messages,
            temperature=rag_config.OPENAI_TEMPERATURE,
            max_tokens=rag_config.OPENAI_MAX_TOKENS
        )
        
        answer = response.choices[0].message.content
        logger.info("✅ Ответ сгенерирован")
        
        return answer
    
    def generate_answer_stream(self, query: str, context: str) -> Iterator[str]:
        """
        Генерация ответа через OpenAI с streaming
        
        Args:
            query: Вопрос пользователя
            context: Контекст из найденных пар
        
        Yields:
            Части ответа по мере генерации
        """
        logger.info("Генерация ответа через OpenAI (streaming)...")
        
        messages = [
            {"role": "system", "content": rag_config.SYSTEM_PROMPT},
            {"role": "user", "content": rag_config.USER_PROMPT_TEMPLATE.format(
                question=query,
                context=context
            )}
        ]
        
        stream = self.openai_client.chat.completions.create(
            model=rag_config.OPENAI_MODEL,
            messages=messages,
            temperature=rag_config.OPENAI_TEMPERATURE,
            max_tokens=rag_config.OPENAI_MAX_TOKENS,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
        
        logger.info("✅ Ответ сгенерирован (streaming)")
    
    def answer_question(self, query: str, use_streaming: bool = None) -> Dict:
        """
        Полный цикл: поиск + генерация ответа
        
        Args:
            query: Вопрос пользователя
            use_streaming: Использовать streaming (по умолчанию из конфига)
        
        Returns:
            Словарь с результатами
        """
        use_streaming = use_streaming if use_streaming is not None else rag_config.ENABLE_STREAMING
        
        try:
            # 1. Поиск релевантных пар
            similar_pairs = self.search_similar_pairs(query)
            
            if not similar_pairs:
                return {
                    'success': False,
                    'answer': 'К сожалению, в базе знаний не найдено релевантной информации для ответа на ваш вопрос.',
                    'source_pairs': [],
                    'query': query
                }
            
            # 2. Формирование контекста
            context = self.format_context(similar_pairs)
            
            # 3. Генерация ответа
            if use_streaming:
                return {
                    'success': True,
                    'answer_stream': self.generate_answer_stream(query, context),
                    'source_pairs': similar_pairs if rag_config.SHOW_SOURCE_PAIRS else [],
                    'query': query,
                    'streaming': True
                }
            else:
                answer = self.generate_answer(query, context)
                return {
                    'success': True,
                    'answer': answer,
                    'source_pairs': similar_pairs if rag_config.SHOW_SOURCE_PAIRS else [],
                    'query': query,
                    'streaming': False
                }
        
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}", exc_info=True)
            return {
                'success': False,
                'answer': f'Произошла ошибка при обработке запроса: {str(e)}',
                'source_pairs': [],
                'query': query,
                'error': str(e)
            }


def test_retriever():
    """Тестирование RAG системы"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ RAG СИСТЕМЫ")
    print("="*60 + "\n")
    
    retriever = RAGRetriever()
    
    test_queries = [
        "Как оформить возврат товара?",
        "Какие документы нужны для регистрации?",
        "Сроки доставки"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Вопрос: {query}")
        print(f"{'='*60}\n")
        
        result = retriever.answer_question(query, use_streaming=False)
        
        if result['success']:
            print(f"Ответ:\n{result['answer']}\n")
            
            if result.get('source_pairs'):
                print(f"Найдено источников: {len(result['source_pairs'])}")
                for i, pair in enumerate(result['source_pairs'], 1):
                    print(f"  {i}. Релевантность: {pair['similarity_score']:.2%}")
        else:
            print(f"Ошибка: {result['answer']}")
    
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_retriever()