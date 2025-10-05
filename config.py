import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные из .env файла
load_dotenv()

# === OpenAI API ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Без дефолтного значения — пусть падает
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.3
OPENAI_MAX_TOKENS = 4000

# === Retry логика ===
MAX_RETRIES = 3
RETRY_DELAY = 2  # секунды
TIMEOUT = 60  # секунды для запроса

# === Пути ===
BASE_DIR = Path(__file__).parent
DIALOGS_DIR = Path("/home/mmax/project/qa2/all_txt_test")
DB_PATH = BASE_DIR / "qa_database.db"
LOG_FILE = BASE_DIR / "processing.log"

# === Обработка файлов ===
INPUT_ENCODING = "utf-8"
MIN_QA_PAIRS = 0  # минимум пар для валидного диалога
MAX_QA_PAIRS = 50  # максимум пар для извлечения

# === Валидация качества ===
MIN_QUESTION_LENGTH = 10  # минимум символов в вопросе
MIN_ANSWER_LENGTH = 15    # минимум символов в ответе
MIN_QUALITY_SCORE = 6.0   # минимальная средняя оценка (из 10)

# === Логирование ===
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR - временно для отладки
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# === CLI ===
SHOW_PROGRESS_BAR = True
BATCH_SIZE = 1  # файлов за раз (для будущего расширения)