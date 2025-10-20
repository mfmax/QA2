#!/usr/bin/env python3
"""
Мониторинг Telegram группы и извлечение пар Q&A от юриста
ОБНОВЛЕНО: Поддержка работы из подпапки /tg + уникальное имя сессии
"""
import sys
import re
import sqlite3
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import MessageService
import logging

# Добавляем родительскую директорию в путь для импорта config
sys.path.append(str(Path(__file__).parent.parent))
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramMonitor:
    def __init__(self):
        """Инициализация мониторинга"""
        # Получаем credentials из config или .env
        self.api_id = config.TELEGRAM_API_ID
        self.api_hash = config.TELEGRAM_API_HASH
        self.phone = config.TELEGRAM_PHONE
        
        # Настройки группы
        self.chat_username = config.TELEGRAM_CHAT  # Например: 'fcb_lawyers' или ID
        self.lawyer_username = 'lawyer_fcb'
        
        # БД
        self.db_path = config.DB_PATH
        
        # Клиент Telegram с уникальным именем сессии
        self.client = TelegramClient('qa_monitor_session', self.api_id, self.api_hash)
    
    def clean_text(self, text: str) -> str:
        """Очистка текста от форматирования"""
        if not text:
            return ""
        
        # Удаление markdown разметки
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # **bold**
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # *italic*
        text = re.sub(r'__(.*?)__', r'\1', text)      # __underline__
        text = re.sub(r'`(.*?)`', r'\1', text)        # `code`
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # ```code blocks```
        
        # Удаление лишних пробелов и переносов
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def generate_dialog_id(self, question: str, answer: str) -> str:
        """Генерация уникального ID для пары"""
        data = f"tg:{question[:100]}:{answer[:100]}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def is_pair_exists(self, dialog_id: str) -> bool:
        """Проверка существования пары в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM qa_pairs WHERE dialog_id = ?",
            (dialog_id,)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def save_pair(self, question: str, answer: str, question_date: datetime):
        """Сохранение пары в БД"""
        dialog_id = self.generate_dialog_id(question, answer)
        
        # Проверка на дубликаты
        if self.is_pair_exists(dialog_id):
            logger.info(f"Пара уже существует (dialog_id: {dialog_id})")
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Сохраняем пару
            cursor.execute("""
                INSERT INTO qa_pairs 
                (dialog_id, filename, question, answer, direction, 
                 question_type, keywords, quality_score, source,
                 call_direction, operator_phone, client_phone, call_date, call_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dialog_id,
                f"tg_lawyers_{question_date.strftime('%Y%m%d')}",  # filename
                question,
                answer,
                'TG Чат юристы',  # direction
                None,  # question_type
                '[]',  # keywords (пустой JSON массив)
                None,  # quality_score
                'tglawyers',  # source
                None,  # call_direction
                None,  # operator_phone
                None,  # client_phone
                None,  # call_date
                None   # call_time
            ))
            
            conn.commit()
            logger.info(f"✅ Сохранена пара Q&A (dialog_id: {dialog_id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения пары: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    async def fetch_qa_pairs(self, limit: int = 1000):
        """Получение пар Q&A из группы"""
        await self.client.start(phone=self.phone)
        logger.info("✅ Подключено к Telegram")
        
        try:
            # Получаем сущность чата
            chat = await self.client.get_entity(self.chat_username)
            logger.info(f"📱 Чат найден: {chat.title}")
            
            # Получаем историю сообщений
            messages = await self.client.get_messages(chat, limit=limit)
            logger.info(f"📥 Загружено {len(messages)} сообщений")
            
            # Создаём словарь всех сообщений для быстрого поиска
            messages_dict = {msg.id: msg for msg in messages}
            
            pairs_found = 0
            pairs_saved = 0
            
            # Ищем ответы от юриста
            for msg in messages:
                # Пропускаем служебные сообщения
                if isinstance(msg, MessageService):
                    continue
                
                # Пропускаем если нет текста
                if not msg.text:
                    continue
                
                # Проверяем что это сообщение от юриста
                sender = await msg.get_sender()
                if not sender or sender.username != self.lawyer_username:
                    continue
                
                # Проверяем что это ответ на чьё-то сообщение
                if not msg.reply_to or not msg.reply_to.reply_to_msg_id:
                    continue
                
                # Находим исходное сообщение (вопрос)
                question_msg_id = msg.reply_to.reply_to_msg_id
                question_msg = messages_dict.get(question_msg_id)
                
                if not question_msg or not question_msg.text:
                    logger.warning(f"Не найден вопрос для ответа (msg_id: {msg.id})")
                    continue
                
                # Очищаем тексты
                question = self.clean_text(question_msg.text)
                answer = self.clean_text(msg.text)
                
                # Проверяем минимальную длину
                if len(question) < 10 or len(answer) < 15:
                    logger.debug(f"Пропущена пара: слишком короткая")
                    continue
                
                pairs_found += 1
                
                # Сохраняем пару
                if self.save_pair(question, answer, question_msg.date):
                    pairs_saved += 1
                
                logger.info(f"Пара #{pairs_found}:")
                logger.info(f"  Q: {question[:100]}...")
                logger.info(f"  A: {answer[:100]}...")
                logger.info(f"  Дата: {question_msg.date}")
                logger.info("")
            
            logger.info("="*60)
            logger.info(f"✅ ОБРАБОТКА ЗАВЕРШЕНА")
            logger.info(f"Найдено пар: {pairs_found}")
            logger.info(f"Сохранено новых: {pairs_saved}")
            logger.info(f"Пропущено (дубликаты): {pairs_found - pairs_saved}")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке: {e}", exc_info=True)
        finally:
            await self.client.disconnect()
    
    def run(self, limit: int = 1000):
        """Запуск мониторинга"""
        logger.info("="*60)
        logger.info("TELEGRAM MONITOR - ЗАПУСК")
        logger.info("="*60)
        
        asyncio.run(self.fetch_qa_pairs(limit))


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Мониторинг Telegram группы юристов и извлечение пар Q&A"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help="Количество последних сообщений для обработки (по умолчанию: 1000)"
    )
    
    args = parser.parse_args()
    
    # Проверка наличия БД
    if not config.DB_PATH.exists():
        logger.error(f"❌ База данных не найдена: {config.DB_PATH}")
        logger.error("Запустите сначала main.py для создания базы данных")
        return 1
    
    # Проверка настроек Telegram
    if not hasattr(config, 'TELEGRAM_API_ID') or not config.TELEGRAM_API_ID:
        logger.error("❌ Не настроены credentials для Telegram API")
        logger.error("Добавьте в config.py или .env:")
        logger.error("  TELEGRAM_API_ID=your_api_id")
        logger.error("  TELEGRAM_API_HASH=your_api_hash")
        logger.error("  TELEGRAM_PHONE=+your_phone")
        logger.error("  TELEGRAM_CHAT=chat_username_or_id")
        logger.error("")
        logger.error("Получить API credentials: https://my.telegram.org/apps")
        return 1
    
    try:
        monitor = TelegramMonitor()
        monitor.run(limit=args.limit)
        return 0
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Прервано пользователем")
        return 1
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())