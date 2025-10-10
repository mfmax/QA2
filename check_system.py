#!/usr/bin/env python3
"""
Скрипт проверки готовности RAG Q&A системы к работе
"""
import sys
import os
from pathlib import Path
import sqlite3


def print_status(message, status="info"):
    """Вывод статуса с цветами"""
    colors = {
        "ok": "\033[92m",      # Зелёный
        "error": "\033[91m",   # Красный
        "warning": "\033[93m", # Жёлтый
        "info": "\033[94m"     # Синий
    }
    end = "\033[0m"
    
    icons = {
        "ok": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️"
    }
    
    color = colors.get(status, "")
    icon = icons.get(status, "•")
    print(f"{color}{icon} {message}{end}")


def check_python_version():
    """Проверка версии Python"""
    print("\n" + "="*60)
    print("🐍 ПРОВЕРКА PYTHON")
    print("="*60)
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print_status(f"Python версия: {version_str}", "info")
    
    if version.major >= 3 and version.minor >= 8:
        print_status("Версия Python подходит (требуется 3.8+)", "ok")
        return True
    else:
        print_status(f"Версия Python слишком старая (требуется 3.8+)", "error")
        return False


def check_env_file():
    """Проверка .env файла"""
    print("\n" + "="*60)
    print("🔐 ПРОВЕРКА .ENV ФАЙЛА")
    print("="*60)
    
    env_path = Path(".env")
    
    if not env_path.exists():
        print_status(".env файл не найден", "error")
        print_status("Создайте файл .env с содержимым:", "info")
        print("   OPENAI_API_KEY=sk-your-api-key-here")
        return False
    
    print_status(".env файл найден", "ok")
    
    # Проверка наличия ключа
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key or api_key == "your-api-key-here":
        print_status("OPENAI_API_KEY не установлен или имеет значение по умолчанию", "error")
        return False
    
    print_status(f"OPENAI_API_KEY установлен (длина: {len(api_key)} символов)", "ok")
    return True


def check_dependencies():
    """Проверка установленных зависимостей"""
    print("\n" + "="*60)
    print("📦 ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    print("="*60)
    
    required_packages = {
        "openai": "OpenAI API",
        "langchain": "LangChain",
        "langchain_community": "LangChain Community",
        "qdrant_client": "Qdrant Client",
        "sentence_transformers": "Sentence Transformers",
        "torch": "PyTorch",
        "flask": "Flask",
        "tqdm": "Progress Bar"
    }
    
    all_ok = True
    
    for package, name in required_packages.items():
        try:
            __import__(package)
            print_status(f"{name} установлен", "ok")
        except ImportError:
            print_status(f"{name} НЕ установлен", "error")
            all_ok = False
    
    if not all_ok:
        print_status("\nУстановите зависимости:", "warning")
        print("   pip install -r rag_requirements.txt")
    
    return all_ok


def check_database():
    """Проверка SQLite базы данных"""
    print("\n" + "="*60)
    print("💾 ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("="*60)
    
    db_path = Path("qa_database.db")
    
    if not db_path.exists():
        print_status("База данных qa_database.db не найдена", "error")
        print_status("Запустите: python main.py", "info")
        return False
    
    print_status("База данных найдена", "ok")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверка таблиц
        cursor.execute("SELECT COUNT(*) FROM qa_pairs")
        pairs_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM qa_pairs WHERE is_irrelevant = 0 OR is_irrelevant IS NULL")
        relevant_count = cursor.fetchone()[0]
        
        conn.close()
        
        print_status(f"Всего пар Q&A: {pairs_count}", "info")
        print_status(f"Релевантных пар: {relevant_count}", "info")
        
        if pairs_count == 0:
            print_status("База данных пустая", "warning")
            return False
        
        print_status("База данных содержит данные", "ok")
        return True
        
    except Exception as e:
        print_status(f"Ошибка при проверке базы данных: {e}", "error")
        return False


def check_qdrant_storage():
    """Проверка Qdrant хранилища"""
    print("\n" + "="*60)
    print("🔍 ПРОВЕРКА QDRANT ХРАНИЛИЩА")
    print("="*60)
    
    qdrant_path = Path("qdrant_storage")
    
    if not qdrant_path.exists():
        print_status("Qdrant хранилище не найдено", "error")
        print_status("Запустите: python rag_indexer.py", "info")
        return False
    
    print_status("Qdrant хранилище найдено", "ok")
    
    # Проверка наличия коллекции
    try:
        from qdrant_client import QdrantClient
        
        client = QdrantClient(path=str(qdrant_path))
        collections = client.get_collections()
        
        if len(collections.collections) == 0:
            print_status("Коллекций не найдено", "warning")
            return False
        
        for collection in collections.collections:
            info = client.get_collection(collection.name)
            print_status(
                f"Коллекция '{collection.name}': {info.points_count} документов", 
                "ok"
            )
        
        return True
        
    except Exception as e:
        print_status(f"Ошибка при проверке Qdrant: {e}", "error")
        return False


def check_rag_components():
    """Проверка RAG компонентов"""
    print("\n" + "="*60)
    print("🤖 ПРОВЕРКА RAG КОМПОНЕНТОВ")
    print("="*60)
    
    files_to_check = {
        "rag_config.py": "Конфигурация",
        "rag_indexer.py": "Индексер",
        "rag_retriever.py": "Retriever",
        "rag_app.py": "Веб-приложение",
        "templates/rag_index.html": "HTML шаблон"
    }
    
    all_ok = True
    
    for file_path, description in files_to_check.items():
        path = Path(file_path)
        if path.exists():
            print_status(f"{description} ({file_path})", "ok")
        else:
            print_status(f"{description} ({file_path}) НЕ НАЙДЕН", "error")
            all_ok = False
    
    return all_ok


def test_rag_initialization():
    """Тест инициализации RAG системы"""
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ RAG СИСТЕМЫ")
    print("="*60)
    
    try:
        print_status("Импорт модулей...", "info")
        from rag_retriever import RAGRetriever
        
        print_status("Инициализация RAG Retriever...", "info")
        retriever = RAGRetriever()
        
        print_status("RAG система успешно инициализирована", "ok")
        
        # Тестовый поиск
        print_status("Тестовый поиск...", "info")
        results = retriever.search_similar_pairs("тест", k=3)
        
        print_status(f"Найдено результатов: {len(results)}", "info")
        
        if len(results) > 0:
            print_status("Векторный поиск работает корректно", "ok")
        else:
            print_status("Поиск не вернул результатов (возможно низкая релевантность)", "warning")
        
        return True
        
    except Exception as e:
        print_status(f"Ошибка при тестировании: {e}", "error")
        import traceback
        traceback.print_exc()
        return False


def check_disk_space():
    """Проверка свободного места"""
    print("\n" + "="*60)
    print("💿 ПРОВЕРКА ДИСКОВОГО ПРОСТРАНСТВА")
    print("="*60)
    
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        
        free_gb = free // (2**30)
        total_gb = total // (2**30)
        
        print_status(f"Свободно: {free_gb} GB из {total_gb} GB", "info")
        
        if free_gb < 5:
            print_status("Мало свободного места (требуется минимум 5 GB)", "warning")
            return False
        
        print_status("Достаточно свободного места", "ok")
        return True
        
    except Exception as e:
        print_status(f"Не удалось проверить дисковое пространство: {e}", "warning")
        return True


def main():
    """Главная функция проверки"""
    print("\n" + "="*70)
    print("🚀 ПРОВЕРКА ГОТОВНОСТИ RAG Q&A СИСТЕМЫ")
    print("="*70)
    
    checks = [
        ("Python версия", check_python_version),
        (".env файл", check_env_file),
        ("Зависимости", check_dependencies),
        ("База данных", check_database),
        ("Qdrant хранилище", check_qdrant_storage),
        ("RAG компоненты", check_rag_components),
        ("Дисковое пространство", check_disk_space),
        ("Инициализация RAG", test_rag_initialization)
    ]
    
    results = {}
    
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print_status(f"Критическая ошибка при проверке '{name}': {e}", "error")
            results[name] = False
    
    # Итоговый отчёт
    print("\n" + "="*70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "ok" if result else "error"
        print_status(f"{name}: {'ПРОЙДЕНО' if result else 'ПРОВАЛЕНО'}", status)
    
    print("\n" + "="*70)
    
    if passed == total:
        print_status(f"ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ({passed}/{total})!", "ok")
        print_status("Система готова к работе!", "ok")
        print_status("\nЗапустите: python rag_app.py", "info")
        return 0
    else:
        print_status(f"НЕКОТОРЫЕ ПРОВЕРКИ ПРОВАЛЕНЫ ({passed}/{total})", "error")
        print_status("Исправьте ошибки перед запуском системы", "warning")
        return 1


if __name__ == "__main__":
    sys.exit(main())