#!/usr/bin/env python3
"""
Flask веб-интерфейс для RAG системы вопросов-ответов
"""
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import logging
import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.append(str(Path(__file__).parent.parent))

import rag_config
from rag_retriever import RAGRetriever

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Глобальный экземпляр retriever (инициализируется при старте)
retriever = None


def init_retriever():
    """Инициализация RAG retriever"""
    global retriever
    try:
        logger.info("Инициализация RAG системы...")
        retriever = RAGRetriever()
        logger.info("✅ RAG система готова к работе")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации RAG системы: {e}", exc_info=True)
        return False


@app.route('/')
def index():
    """Главная страница"""
    return render_template('rag_index.html', 
                         show_sources=rag_config.SHOW_SOURCE_PAIRS,
                         streaming=rag_config.ENABLE_STREAMING)


@app.route('/api/ask', methods=['POST'])
def ask_question():
    """
    API endpoint для вопросов
    Возвращает JSON с ответом (без streaming)
    """
    if not retriever:
        return jsonify({
            'success': False,
            'error': 'RAG система не инициализирована'
        }), 500
    
    try:
        data = request.get_json()
        query = data.get('question', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Вопрос не может быть пустым'
            }), 400
        
        logger.info(f"Получен вопрос: {query}")
        
        # Получаем ответ без streaming
        result = retriever.answer_question(query, use_streaming=False)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Ошибка при обработке вопроса: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ask_stream', methods=['POST'])
def ask_question_stream():
    """
    API endpoint для вопросов со streaming
    Возвращает Server-Sent Events (SSE)
    """
    if not retriever:
        return jsonify({
            'success': False,
            'error': 'RAG система не инициализирована'
        }), 500
    
    try:
        data = request.get_json()
        query = data.get('question', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Вопрос не может быть пустым'
            }), 400
        
        logger.info(f"Получен вопрос (streaming): {query}")
        
        # Получаем ответ со streaming
        result = retriever.answer_question(query, use_streaming=True)
        
        def generate():
            """Генератор для SSE"""
            import json
            
            # Сначала отправляем source_pairs если нужно
            if result.get('source_pairs'):
                yield f"data: {json.dumps({'type': 'sources', 'data': result['source_pairs']}, ensure_ascii=False)}\n\n"
            
            # Затем стримим ответ
            if result['success']:
                yield f"data: {json.dumps({'type': 'answer_start'}, ensure_ascii=False)}\n\n"
                
                for chunk in result['answer_stream']:
                    yield f"data: {json.dumps({'type': 'answer_chunk', 'data': chunk}, ensure_ascii=False)}\n\n"
                
                yield f"data: {json.dumps({'type': 'answer_end'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'data': result.get('answer', 'Ошибка')}, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
    
    except Exception as e:
        logger.error(f"Ошибка при обработке вопроса (streaming): {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health')
def health_check():
    """Проверка состояния системы"""
    return jsonify({
        'status': 'ok' if retriever else 'not_initialized',
        'config': {
            'embedding_model': rag_config.EMBEDDING_MODEL,
            'top_k': rag_config.TOP_K_RESULTS,
            'similarity_threshold': rag_config.SIMILARITY_THRESHOLD,
            'streaming_enabled': rag_config.ENABLE_STREAMING,
            'show_sources': rag_config.SHOW_SOURCE_PAIRS
        }
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ЗАПУСК RAG ВЕБ-ИНТЕРФЕЙСА")
    print("="*60)
    
    # Инициализация RAG системы
    if not init_retriever():
        print("\n❌ Не удалось инициализировать RAG систему")
        print("Убедитесь что:")
        print("1. Запущен rag_indexer.py для индексации данных")
        print("2. Установлены все зависимости из rag_requirements.txt")
        print("3. Настроен .env файл с OPENAI_API_KEY")
        sys.exit(1)
    
    print(f"\n📊 Конфигурация:")
    print(f"  • Модель эмбеддингов: {rag_config.EMBEDDING_MODEL}")
    print(f"  • Top-K результатов: {rag_config.TOP_K_RESULTS}")
    print(f"  • Порог схожести: {rag_config.SIMILARITY_THRESHOLD}")
    print(f"  • Streaming: {'✅' if rag_config.ENABLE_STREAMING else '❌'}")
    print(f"  • Показ источников: {'✅' if rag_config.SHOW_SOURCE_PAIRS else '❌'}")
    
    print(f"\n🌐 Сервер запускается на http://0.0.0.0:5001")
    print("="*60 + "\n")
    
    # Запуск без debug mode чтобы избежать двойной инициализации
    app.run(debug=False, host='0.0.0.0', port=5001)