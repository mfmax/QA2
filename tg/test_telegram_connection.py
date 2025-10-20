#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Telegram
ОБНОВЛЕНО: Поддержка работы из подпапки /tg + уникальное имя сессии
"""
import sys
import asyncio
from pathlib import Path
from telethon import TelegramClient

# Добавляем родительскую директорию в путь для импорта config
sys.path.append(str(Path(__file__).parent.parent))
import config

async def test_connection():
    """Тест подключения к Telegram"""
    print("\n" + "="*60)
    print("🔍 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К TELEGRAM")
    print("="*60 + "\n")
    
    # Проверка credentials
    print("1️⃣ Проверка credentials...")
    
    if not hasattr(config, 'TELEGRAM_API_ID') or not config.TELEGRAM_API_ID:
        print("❌ TELEGRAM_API_ID не настроен")
        return False
    print(f"✅ TELEGRAM_API_ID: {config.TELEGRAM_API_ID}")
    
    if not hasattr(config, 'TELEGRAM_API_HASH') or not config.TELEGRAM_API_HASH:
        print("❌ TELEGRAM_API_HASH не настроен")
        return False
    print(f"✅ TELEGRAM_API_HASH: {config.TELEGRAM_API_HASH[:10]}...")
    
    if not hasattr(config, 'TELEGRAM_PHONE') or not config.TELEGRAM_PHONE:
        print("❌ TELEGRAM_PHONE не настроен")
        return False
    print(f"✅ TELEGRAM_PHONE: {config.TELEGRAM_PHONE}")
    
    if not hasattr(config, 'TELEGRAM_CHAT') or not config.TELEGRAM_CHAT:
        print("❌ TELEGRAM_CHAT не настроен")
        return False
    print(f"✅ TELEGRAM_CHAT: {config.TELEGRAM_CHAT}")
    
    # Подключение к Telegram
    print("\n2️⃣ Подключение к Telegram...")
    
    try:
        client = TelegramClient('qa_monitor_test_session', config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
        await client.start(phone=config.TELEGRAM_PHONE)
        print("✅ Успешно подключено к Telegram")
        
        # Получение информации о пользователе
        print("\n3️⃣ Информация о вашем аккаунте...")
        me = await client.get_me()
        print(f"✅ Имя: {me.first_name} {me.last_name or ''}")
        print(f"✅ Username: @{me.username}")
        print(f"✅ ID: {me.id}")
        
        # Проверка доступа к чату
        print("\n4️⃣ Проверка доступа к чату...")
        try:
            chat = await client.get_entity(config.TELEGRAM_CHAT)
            print(f"✅ Чат найден: {chat.title}")
            print(f"✅ ID чата: {chat.id}")
            print(f"✅ Тип: {type(chat).__name__}")
            
            # Получение последних сообщений
            print("\n5️⃣ Тест чтения сообщений...")
            messages = await client.get_messages(chat, limit=10)
            print(f"✅ Загружено {len(messages)} последних сообщений")
            
            if messages:
                print("\n📝 Последнее сообщение:")
                last_msg = messages[0]
                sender = await last_msg.get_sender()
                print(f"   От: {sender.first_name if sender else 'Unknown'}")
                print(f"   Дата: {last_msg.date}")
                print(f"   Текст: {last_msg.text[:100] if last_msg.text else '<без текста>'}...")
            
            # Поиск сообщений от юриста
            print("\n6️⃣ Поиск сообщений от @lawyer_fcb...")
            lawyer_count = 0
            for msg in messages:
                sender = await msg.get_sender()
                if sender and sender.username == 'lawyer_fcb':
                    lawyer_count += 1
            
            print(f"✅ Найдено {lawyer_count} сообщений от юриста в последних 10")
            
        except Exception as e:
            print(f"❌ Ошибка доступа к чату: {e}")
            print("\n💡 Возможные причины:")
            print("   - Неверный username или ID чата")
            print("   - Вы не являетесь участником этого чата")
            print("   - Чат был удалён или архивирован")
            return False
        
        await client.disconnect()
        
        print("\n" + "="*60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*60)
        print("\n🚀 Теперь можно запустить: python tg_monitor.py\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\n💡 Рекомендации:")
        print("   1. Проверьте правильность API credentials")
        print("   2. Убедитесь что номер телефона указан в международном формате")
        print("   3. При первом запуске введите код подтверждения из Telegram")
        return False


def main():
    """Точка входа"""
    asyncio.run(test_connection())


if __name__ == "__main__":
    main()