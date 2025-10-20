#!/usr/bin/env python3
"""
Real-time мониторинг Telegram группы через Bot API
Работает как daemon - постоянно слушает новые сообщения
"""
import sys
import re
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Добавляем родительскую директорию в путь для импорта config
sys.path.append(str(Path(__file__).parent.parent))
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tg_bot_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TelegramBotMonitor:
    def __init__(self):
        """Инициализация bot мониторинга"""
        # Получаем токен бота из config
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.lawyer_username = 'lawyer_fcb'  # Username юриста (без @)
        
        # БД
        self.db_path = config.DB_PATH
        
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
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'__(.*?)__', r'\1', text)
        text = re.sub(r'`(.*?)`', r'\1', text)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        
        # Удаление лишних пробелов
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def generate_dialog_id(self, question: str, answer: str) -> str:
        """Генерация уникального ID для пары"""
        data = f"tgbot:{question[:100]}:{answer[:100]}"
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
                f"tgbot_lawyers_{question_date.strftime('%Y%m%d')}",
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик входящих сообщений"""
        try:
            message = update.message
            
            # Пропускаем если нет текста
            if not message or not message.text:
                return
            
            self.stats['total_messages'] += 1
            
            # Проверяем что это сообщение от юриста
            if not message.from_user or message.from_user.username != self.lawyer_username:
                return
            
            self.stats['lawyer_replies'] += 1
            logger.info(f"🔍 Обнаружен ответ от @{self.lawyer_username}")
            
            # Проверяем что это reply на другое сообщение
            if not message.reply_to_message:
                logger.warning("⚠️  Сообщение юриста не является ответом (нет reply)")
                return
            
            # Получаем исходное сообщение (вопрос)
            question_msg = message.reply_to_message
            
            if not question_msg.text:
                logger.warning("⚠️  Исходное сообщение не содержит текста")
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
        """Запуск мониторинга"""
        logger.info("\n" + "="*60)
        logger.info("🤖 TELEGRAM BOT MONITOR - ЗАПУСК")
        logger.info("="*60)
        logger.info(f"👤 Отслеживаем ответы: @{self.lawyer_username}")
        logger.info(f"💾 База данных: {self.db_path}")
        logger.info("\n🚀 REAL-TIME МОНИТОРИНГ ЗАПУЩЕН")
        logger.info("⏰ Ожидание новых сообщений...")
        logger.info("💡 Нажмите Ctrl+C для остановки\n")
        
        # Создаём приложение бота
        application = ApplicationBuilder().token(self.bot_token).build()
        
        # Регистрируем обработчик всех текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Периодический вывод статистики
        from telegram.ext import JobQueue
        
        def stats_job(context):
            self.print_stats()
        
        # Статистика каждые 5 минут
        application.job_queue.run_repeating(stats_job, interval=300, first=300)
        
        try:
            # Запускаем бота
            await application.run_polling()
        except KeyboardInterrupt:
            logger.info("\n⚠️  Получен сигнал остановки...")
        finally:
            self.print_stats()
            logger.info("👋 Мониторинг остановлен\n")
    
    def run(self):
        """Точка входа"""
        import asyncio
        asyncio.run(self.start_monitoring())


def main():
    # Проверка наличия БД
    if not config.DB_PATH.exists():
        logger.error(f"❌ База данных не найдена: {config.DB_PATH}")
        logger.error("Запустите сначала main.py для создания базы данных")
        return 1
    
    # Проверка токена бота
    if not hasattr(config, 'TELEGRAM_BOT_TOKEN') or not config.TELEGRAM_BOT_TOKEN:
        logger.error("❌ Токен бота не настроен!")
        logger.error("Добавьте в .env:")
        logger.error("  TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHI...")
        logger.error("")
        logger.error("Получить токен: https://t.me/botfather")
        return 1
    
    try:
        monitor = TelegramBotMonitor()
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