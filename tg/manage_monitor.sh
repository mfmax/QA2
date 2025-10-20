#!/bin/bash
# Скрипт управления Telegram мониторингом
# ОБНОВЛЕНО: Поддержка работы из подпапки /tg

# Определяем директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

COLOR_RESET='\033[0m'
COLOR_GREEN='\033[0;32m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'

print_header() {
    echo -e "${COLOR_BLUE}================================${COLOR_RESET}"
    echo -e "${COLOR_BLUE}$1${COLOR_RESET}"
    echo -e "${COLOR_BLUE}================================${COLOR_RESET}"
}

print_success() {
    echo -e "${COLOR_GREEN}✅ $1${COLOR_RESET}"
}

print_error() {
    echo -e "${COLOR_RED}❌ $1${COLOR_RESET}"
}

print_warning() {
    echo -e "${COLOR_YELLOW}⚠️  $1${COLOR_RESET}"
}

print_info() {
    echo -e "${COLOR_BLUE}ℹ️  $1${COLOR_RESET}"
}

# Проверка что мы в правильной директории
if [ ! -f "$SCRIPT_DIR/tg_monitor_realtime.py" ]; then
    print_error "Файл tg_monitor_realtime.py не найден!"
    print_info "Текущая директория: $SCRIPT_DIR"
    exit 1
fi

print_info "Рабочая директория: $SCRIPT_DIR"
print_info "Проект: $PROJECT_DIR"

show_menu() {
    print_header "Управление Telegram мониторингом"
    echo ""
    echo "1) 📚 Обработать историю чата"
    echo "2) 🔴 Запустить real-time мониторинг"
    echo "3) 📊 Показать логи real-time"
    echo "4) 📈 Статистика из БД"
    echo "5) 🛑 Остановить все процессы"
    echo "6) 🔧 Тест подключения"
    echo "0) Выход"
    echo ""
    read -p "Выберите действие: " choice
    
    case $choice in
        1) process_history ;;
        2) start_realtime ;;
        3) show_logs ;;
        4) show_stats ;;
        5) stop_all ;;
        6) test_connection ;;
        0) exit 0 ;;
        *) print_error "Неверный выбор!"; show_menu ;;
    esac
}

process_history() {
    print_header "Обработка истории чата"
    echo ""
    read -p "Количество сообщений для обработки (по умолчанию 1000): " limit
    limit=${limit:-1000}
    
    print_info "Запуск обработки последних $limit сообщений..."
    cd "$SCRIPT_DIR"
    python tg_monitor.py --limit $limit
    
    echo ""
    read -p "Нажмите Enter для возврата в меню..."
    show_menu
}

start_realtime() {
    print_header "Real-time мониторинг"
    echo ""
    echo "1) Интерактивный режим (в текущем терминале)"
    echo "2) Фоновый режим (screen)"
    echo "3) Фоновый режим (tmux)"
    echo "0) Назад"
    echo ""
    read -p "Выберите режим: " mode
    
    case $mode in
        1)
            print_info "Запуск в интерактивном режиме..."
            print_warning "Нажмите Ctrl+C для остановки"
            sleep 2
            cd "$SCRIPT_DIR"
            python tg_monitor_realtime.py
            ;;
        2)
            if ! command -v screen &> /dev/null; then
                print_error "screen не установлен!"
                print_info "Установите: sudo apt install screen"
            else
                print_info "Запуск в screen..."
                cd "$SCRIPT_DIR"
                screen -dmS telegram-monitor python tg_monitor_realtime.py
                print_success "Мониторинг запущен в фоне!"
                print_info "Подключиться: screen -r telegram-monitor"
                print_info "Отключиться: Ctrl+A, затем D"
            fi
            ;;
        3)
            if ! command -v tmux &> /dev/null; then
                print_error "tmux не установлен!"
                print_info "Установите: sudo apt install tmux"
            else
                print_info "Запуск в tmux..."
                cd "$SCRIPT_DIR"
                tmux new-session -d -s telegram-monitor "python tg_monitor_realtime.py"
                print_success "Мониторинг запущен в фоне!"
                print_info "Подключиться: tmux attach -t telegram-monitor"
                print_info "Отключиться: Ctrl+B, затем D"
            fi
            ;;
        0)
            show_menu
            return
            ;;
        *)
            print_error "Неверный выбор!"
            start_realtime
            return
            ;;
    esac
    
    echo ""
    read -p "Нажмите Enter для возврата в меню..."
    show_menu
}

show_logs() {
    print_header "Логи real-time мониторинга"
    echo ""
    
    LOG_FILE="$SCRIPT_DIR/tg_monitor_realtime.log"
    
    if [ ! -f "$LOG_FILE" ]; then
        print_warning "Файл логов не найден!"
        print_info "Возможно мониторинг ещё не запускался"
    else
        echo "1) Показать последние 50 строк"
        echo "2) Следить в реальном времени (tail -f)"
        echo "3) Открыть весь файл (less)"
        echo "0) Назад"
        echo ""
        read -p "Выберите действие: " choice
        
        case $choice in
            1)
                tail -n 50 "$LOG_FILE"
                ;;
            2)
                print_info "Нажмите Ctrl+C для выхода"
                sleep 1
                tail -f "$LOG_FILE"
                ;;
            3)
                less "$LOG_FILE"
                ;;
            0)
                show_menu
                return
                ;;
        esac
    fi
    
    echo ""
    read -p "Нажмите Enter для возврата в меню..."
    show_menu
}

show_stats() {
    print_header "Статистика из базы данных"
    echo ""
    
    DB_FILE="$PROJECT_DIR/qa_database.db"
    
    if [ ! -f "$DB_FILE" ]; then
        print_error "База данных не найдена!"
        print_info "Ожидается: $DB_FILE"
    else
        print_info "Загрузка статистики..."
        echo ""
        
        # Общая статистика
        total=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM qa_pairs WHERE source = 'tglawyers';")
        print_success "Всего пар из Telegram: $total"
        
        # По датам
        echo ""
        print_info "По датам создания (последние 7 дней):"
        sqlite3 -column -header "$DB_FILE" \
            "SELECT DATE(created_at) as date, COUNT(*) as pairs 
             FROM qa_pairs 
             WHERE source = 'tglawyers' 
             AND created_at >= datetime('now', '-7 days')
             GROUP BY DATE(created_at)
             ORDER BY date DESC;"
        
        # Последние добавленные
        echo ""
        print_info "Последние 5 добавленных пар:"
        sqlite3 -column "$DB_FILE" \
            "SELECT 
                substr(question, 1, 50) || '...' as question,
                datetime(created_at) as added
             FROM qa_pairs 
             WHERE source = 'tglawyers'
             ORDER BY created_at DESC
             LIMIT 5;"
    fi
    
    echo ""
    read -p "Нажмите Enter для возврата в меню..."
    show_menu
}

stop_all() {
    print_header "Остановка процессов"
    echo ""
    
    # Поиск процессов
    print_info "Поиск запущенных процессов мониторинга..."
    
    pids=$(pgrep -f "tg_monitor_realtime.py")
    
    if [ -z "$pids" ]; then
        print_warning "Активных процессов не найдено"
    else
        echo "Найдены процессы: $pids"
        read -p "Остановить эти процессы? (y/n): " confirm
        
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            for pid in $pids; do
                kill $pid 2>/dev/null && print_success "Процесс $pid остановлен" || print_error "Не удалось остановить $pid"
            done
        fi
    fi
    
    # Проверка screen сессий
    if command -v screen &> /dev/null; then
        screen_session=$(screen -ls | grep telegram-monitor)
        if [ ! -z "$screen_session" ]; then
            print_info "Найдена screen сессия: telegram-monitor"
            read -p "Завершить screen сессию? (y/n): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                screen -S telegram-monitor -X quit
                print_success "Screen сессия завершена"
            fi
        fi
    fi
    
    # Проверка tmux сессий
    if command -v tmux &> /dev/null; then
        tmux_session=$(tmux ls 2>/dev/null | grep telegram-monitor)
        if [ ! -z "$tmux_session" ]; then
            print_info "Найдена tmux сессия: telegram-monitor"
            read -p "Завершить tmux сессию? (y/n): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                tmux kill-session -t telegram-monitor
                print_success "Tmux сессия завершена"
            fi
        fi
    fi
    
    echo ""
    read -p "Нажмите Enter для возврата в меню..."
    show_menu
}

test_connection() {
    print_header "Тест подключения к Telegram"
    echo ""
    
    TEST_FILE="$SCRIPT_DIR/test_telegram_connection.py"
    
    if [ ! -f "$TEST_FILE" ]; then
        print_error "Файл test_telegram_connection.py не найден!"
        print_info "Ожидается: $TEST_FILE"
    else
        print_info "Запуск тестов..."
        cd "$SCRIPT_DIR"
        python test_telegram_connection.py
    fi
    
    echo ""
    read -p "Нажмите Enter для возврата в меню..."
    show_menu
}

# Точка входа
clear
show_menu