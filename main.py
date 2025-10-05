#!/usr/bin/env python3
"""
QA Extractor - Извлечение пар вопрос-ответ из диалогов
"""
import sys
import logging
from pathlib import Path
from typing import List
import argparse

from tqdm import tqdm

import config
from db import Database
from api_client import OpenAIClient
from processor import DialogProcessor


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def get_dialog_files(directory: Path) -> List[Path]:
    """Получить список файлов диалогов"""
    if not directory.exists():
        raise FileNotFoundError(f"Директория не найдена: {directory}")
    
    files = list(directory.glob("*.txt"))
    return sorted(files)


def print_statistics(stats: dict):
    """Вывод статистики"""
    print("\n" + "="*60)
    print("📊 СТАТИСТИКА ОБРАБОТКИ")
    print("="*60)
    print(f"Всего обработано файлов: {stats['total_files']}")
    print(f"Файлов с бизнес-парами: {stats['files_with_pairs']}")
    print(f"Всего извлечено пар: {stats['total_pairs']}")
    print(f"Средняя оценка качества: {stats['avg_quality_score']}/10")
    
    if stats['by_direction']:
        print("\n📍 По направлениям:")
        for direction, count in stats['by_direction'].items():
            print(f"  • {direction}: {count}")
    
    if stats['by_type']:
        print("\n📝 По типам вопросов:")
        for q_type, count in stats['by_type'].items():
            if q_type:
                print(f"  • {q_type}: {count}")
    
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Извлечение пар Q&A из диалогов с помощью OpenAI"
    )
    parser.add_argument(
        '--dir',
        type=str,
        default=str(config.DIALOGS_DIR),
        help=f"Директория с диалогами (по умолчанию: {config.DIALOGS_DIR})"
    )
    parser.add_argument(
        '--reprocess',
        action='store_true',
        help="Переобработать уже обработанные файлы"
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help="Только вывести статистику без обработки"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help="Ограничить количество обрабатываемых файлов"
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("="*60)
    logger.info("QA EXTRACTOR - ЗАПУСК")
    logger.info("="*60)
    
    try:
        # Инициализация компонентов
        db = Database(config.DB_PATH)
        
        # Если запрошена только статистика
        if args.stats_only:
            stats = db.get_statistics()
            print_statistics(stats)
            db.close()
            return 0
        
        openai_client = OpenAIClient()
        processor = DialogProcessor(openai_client)
        
        # Получение списка файлов
        dialogs_dir = Path(args.dir)
        all_files = get_dialog_files(dialogs_dir)
        
        if not all_files:
            logger.warning(f"Файлы не найдены в директории: {dialogs_dir}")
            return 0
        
        logger.info(f"Найдено файлов: {len(all_files)}")
        
        # Фильтрация уже обработанных файлов
        if not args.reprocess:
            files_to_process = [
                f for f in all_files 
                if not db.is_file_processed(f.name)
            ]
            skipped_count = len(all_files) - len(files_to_process)
            if skipped_count > 0:
                logger.info(f"Пропущено уже обработанных файлов: {skipped_count}")
        else:
            files_to_process = all_files
            logger.info("Режим переобработки: все файлы будут обработаны заново")
        
        # Применение лимита
        if args.limit:
            files_to_process = files_to_process[:args.limit]
            logger.info(f"Применён лимит: {args.limit} файлов")
        
        if not files_to_process:
            logger.info("Нет файлов для обработки")
            stats = db.get_statistics()
            print_statistics(stats)
            db.close()
            return 0
        
        logger.info(f"К обработке: {len(files_to_process)} файлов")
        
        # Обработка файлов
        success_count = 0
        error_count = 0
        total_pairs = 0
        
        progress_bar = tqdm(
            files_to_process,
            desc="Обработка диалогов",
            disable=not config.SHOW_PROGRESS_BAR
        )
        
        for filepath in progress_bar:
            progress_bar.set_postfix({
                'файл': filepath.name[:30],
                'успешно': success_count,
                'ошибок': error_count
            })
            
            try:
                # Обработка диалога
                result = processor.process_dialog(filepath)
                
                # Сохранение результатов
                if result['success']:
                    # Сохранение пар в БД
                    if result['pairs']:
                        file_metadata = result.get('file_metadata')
                        logger.info(f"Передача метаданных в save_qa_pairs: {file_metadata}")
                        
                        db.save_qa_pairs(
                            result['pairs'],
                            result['filename'],
                            result['dialog_id'],
                            file_metadata
                        )
                        total_pairs += len(result['pairs'])
                    
                    # Отметка файла как обработанного
                    db.mark_file_processed(
                        result['filename'],
                        len(result['pairs']),
                        result['has_business_pairs'],
                        result['error'],
                        file_metadata=result.get('file_metadata')
                    )
                    
                    success_count += 1
                else:
                    # Сохранение ошибки
                    db.mark_file_processed(
                        result['filename'],
                        0,
                        False,
                        result['error'],
                        file_metadata=result.get('file_metadata')
                    )
                    error_count += 1
                    logger.error(f"Ошибка обработки {filepath.name}: {result['error']}")
                
            except KeyboardInterrupt:
                logger.warning("\n⚠️  Прервано пользователем")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка при обработке {filepath.name}: {e}")
                error_count += 1
                continue
        
        # Итоговая статистика
        logger.info("="*60)
        logger.info("ОБРАБОТКА ЗАВЕРШЕНА")
        logger.info("="*60)
        logger.info(f"✅ Успешно обработано: {success_count}")
        logger.info(f"❌ Ошибок: {error_count}")
        logger.info(f"📝 Всего извлечено пар: {total_pairs}")
        
        # Общая статистика из БД
        stats = db.get_statistics()
        print_statistics(stats)
        
        db.close()
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Программа прервана пользователем")
        return 1
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())