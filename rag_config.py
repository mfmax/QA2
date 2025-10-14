import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Paths ===
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "qa_database.db"

# === Qdrant Settings ===
QDRANT_PATH = BASE_DIR / "qdrant_storage"  # Локальное хранилище
QDRANT_COLLECTION_NAME = "qa_pairs"

# === Embeddings Settings ===
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
EMBEDDING_DEVICE = "cpu"  # Или "cuda" если есть GPU
EMBEDDING_BATCH_SIZE = 16

# === Retrieval Settings ===
TOP_K_RESULTS = 8  # Количество наиболее релевантных пар для поиска
SIMILARITY_THRESHOLD = 0.0  # Минимальный порог схожести (0.0-1.0)

# === OpenAI Settings ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.4
OPENAI_MAX_TOKENS = 1000

# === Streaming Settings ===
ENABLE_STREAMING = True  # True для потоковой передачи, False для полного ответа

# === Display Settings ===
SHOW_SOURCE_PAIRS = True  # True - показывать исходные пары, False - только финальный ответ

# === Data Indexing Settings ===
# Какие данные индексировать
INDEX_ALL_PAIRS = True  # True - все пары, False - только is_audited=1
EXCLUDE_IRRELEVANT = True  # True - исключать is_irrelevant=1

# === Prompt Templates ===
SYSTEM_PROMPT = """Ты — профессиональный ассистент службы поддержки.

Твоя задача: на основе найденных в базе знаний пар вопрос-ответ предоставить пользователю 
чёткий, деловой и полезный ответ.

ПРИНЦИПЫ РАБОТЫ:
- Используй информацию из предоставленных пар Q&A как основу для ответа
- Формулируй ответ профессионально и структурированно
- Если найденная информация не полностью отвечает на вопрос, честно об этом сообщи
- Не придумывай информацию, которой нет в предоставленном контексте
- Адаптируй язык ответа под вопрос пользователя (деловой, но понятный)
- Не указывай что данные получены из источников

СТРУКТУРА ОТВЕТА:
1. Прямой ответ на вопрос
2. Дополнительные детали если есть
3. При необходимости — рекомендации или следующие шаги"""

USER_PROMPT_TEMPLATE = """Вопрос пользователя: {question}

Релевантная информация из базы знаний:
{context}

Сформулируй профессиональный ответ на основе этой информации."""