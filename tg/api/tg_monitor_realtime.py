#!/usr/bin/env python3
"""
Real-time мониторинг Telegram группы и автоматическое извлечение пар Q&A
Работает как daemon - постоянно слушает новые сообщения
"""
import sys
import re
import sqlite3
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import MessageService
import logging

# Добавляем родительскую директорию в путь для импорта config
sys.path.append(str(Path(__file__).parent.parent))
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tg_monitor_realtime.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TelegramRealtimeMonitor:
    def __init__(self):
        """Инициализация real-time мониторинга"""
        # Получаем credentials из config
        self.api_id = config.TELEGRAM_API_ID
        self.api_hash = config.TELEGRAM_API_HASH
        self.phone = config.TELEGRAM_PHONE
        
        # Настройки группы
        self.chat_username = config.TELEGRAM_CHAT
        self.lawyer_username = 'lawyer_fcb'
        
        # БД
        self.db_path = config.DB_PATH
        
        # Клиент Telegram
        self.client = TelegramClient('session_realtime', self.api_id, self.api_hash)
        
        # Статистика
        self.stats = {
            'total_messages': 0,
            'lawyer_replies': 0,
            'pairs_saved': 0,
            'duplicates_skipped': 0,
            'errors': 0,
            'started_at': datetime.now()
        }
    
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
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM qa_pairs WHERE dialog_id = ?",
                (dialog_id,)
            )
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"Ошибка проверки дубликата: {e}")
            return False
    
    def save_pair(self, question: str, answer: str, question_date: datetime) -> bool:
        """Сохранение пары в БД"""
        dialog_id = self.generate_dialog_id(question, answer)
        
        # Проверка на дубликаты
        if self.is_pair_exists(dialog_id):
            logger.info(f"⏭️  Пара уже существует (dialog_id: {dialog_id[:16]}...)")
            self.stats['duplicates_skipped'] += 1
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Сохраняем пару
            cursor.execute("""
                INSERT INTO qa_pairs 
                (dialog_id, filename, question, answer, direction, 
                 question_type, keywords, quality_score, source,
                 call_direction, operator_phone, client_phone, call_date, call_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dialog_id,
                f"tg_lawyers_{question_date.strftime('%Y%m%d')}",
                question,
                answer,
                'TG Чат юристы',
                None,
                '[]',
                None,
                'tglawyers',
                None, None, None, None, None
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Сохранена новая пара Q&A")
            logger.info(f"   Q: {question[:80]}...")
            logger.info(f"   A: {answer[:80]}...")
            
            self.stats['pairs_saved'] += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пары: {e}")
            self.stats['errors'] += 1
            return False
    
    async def process_lawyer_reply(self, event):
        """Обработка ответа юриста"""
        try:
            message = event.message
            
            # Получаем отправителя
            sender = await message.get_sender()
            
            # Проверяем что это юрист
            if not sender or sender.username != self.lawyer_username:
                return
            
            self.stats['lawyer_replies'] += 1
            logger.info(f"🔍 Обнаружен ответ от @{self.lawyer_username}")
            
            # Проверяем что это ответ на чьё-то сообщение
            if not message.reply_to or not message.reply_to.reply_to_msg_id:
                logger.warning("⚠️  Сообщение юриста не является ответом (нет reply_to)")
                return
            
            # Получаем исходное сообщение (вопрос)
            question_msg = await message.get_reply_message()
            
            if not question_msg or not question_msg.text:
                logger.warning("⚠️  Не удалось получить исходный вопрос")
                return
            
            # Очищаем тексты
            question = self.clean_text(question_msg.text)
            answer = self.clean_text(message.text)
            
            # Проверяем минимальную длину
            if len(question) < 10:
                logger.debug(f"⏭️  Вопрос слишком короткий ({len(question)} символов)")
                return
            
            if len(answer) < 15:
                logger.debug(f"⏭️  Ответ слишком короткий ({len(answer)} символов)")
                return
            
            # Сохраняем пару
            self.save_pair(question, answer, question_msg.date)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}", exc_info=True)
            self.stats['errors'] += 1
    
    def print_stats(self):
        """Вывод статистики"""
        uptime = datetime.now() - self.stats['started_at']
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        logger.info("\n" + "="*60)
        logger.info("📊 СТАТИСТИКА МОНИТОРИНГА")
        logger.info("="*60)
        logger.info(f"⏱️  Время работы: {hours}ч {minutes}м {seconds}с")
        logger.info(f"📨 Всего сообщений: {self.stats['total_messages']}")
        logger.info(f"💬 Ответов юриста: {self.stats['lawyer_replies']}")
        logger.info(f"✅ Сохранено пар: {self.stats['pairs_saved']}")
        logger.info(f"⏭️  Пропущено (дубликаты): {self.stats['duplicates_skipped']}")
        logger.info(f"❌ Ошибок: {self.stats['errors']}")
        logger.info("="*60 + "\n")
    
    async def start_monitoring(self):
        """Запуск постоянного мониторинга"""
        await self.client.start(phone=self.phone)
        logger.info("✅ Подключено к Telegram")
        
        try:
            # Получаем сущность чата
            chat = await self.client.get_entity(self.chat_username)
            logger.info(f"📱 Мониторинг чата: {chat.title}")
            logger.info(f"👤 Отслеживаем ответы: @{self.lawyer_username}")
            logger.info(f"💾 База данных: {self.db_path}")
            
            logger.info("\n" + "="*60)
            logger.info("🚀 REAL-TIME МОНИТОРИНГ ЗАПУЩЕН")
            logger.info("="*60)
            logger.info("⏰ Ожидание новых сообщений...")
            logger.info("💡 Нажмите Ctrl+C для остановки\n")
            
            # Регистрируем обработчик новых сообщений
            @self.client.on(events.NewMessage(chats=chat))
            async def handler(event):
                self.stats['total_messages'] += 1
                
                # Пропускаем служебные сообщения
                if isinstance(event.message, MessageService):
                    return
                
                # Пропускаем если нет текста
                if not event.message.text:
                    return
                
                # Обрабатываем сообщение
                await self.process_lawyer_reply(event)
            
            # Периодический вывод статистики (каждые 5 минут)
            async def periodic_stats():
                while True:
                    await asyncio.sleep(300)  # 5 минут
                    self.print_stats()
            
            # Запускаем периодический вывод статистики
            asyncio.create_task(periodic_stats())
            
            # Держим соединение открытым
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  Получен сигнал остановки...")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        finally:
            self.print_stats()
            await self.client.disconnect()
            logger.info("👋 Мониторинг остановлен\n")
    
    def run(self):
        """Запуск мониторинга"""
        logger.info("\n" + "="*60)
        logger.info("🤖 TELEGRAM REAL-TIME MONITOR")
        logger.info("="*60 + "\n")
        
        asyncio.run(self.start_monitoring())


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Real-time мониторинг Telegram группы юристов"
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help="Запустить как daemon (в фоне)"
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
        monitor = TelegramRealtimeMonitor()
        monitor.run()
        return 0
    except KeyboardInterrupt:
        logger.info("\n⚠️  Программа прервана пользователем")
        return 0
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())