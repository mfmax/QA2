// Глобальная функция для переключения аудита (левая кнопка)
async function toggleAudit(pairId, rowElement) {
    try {
        const response = await fetch('/api/toggle_audit/' + pairId, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.is_audited) {
            rowElement.classList.add('audited');
            rowElement.classList.remove('irrelevant');
            rowElement.querySelector('.audit-star').textContent = '⭐';
        } else {
            rowElement.classList.remove('audited');
            rowElement.querySelector('.audit-star').textContent = '';
        }
        
        // Перезагружаем для обновления счётчика
        setTimeout(function() {
            location.reload();
        }, 300);
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Не удалось обновить статус');
    }
}

// Функция для переключения нерелевантности (правая кнопка)
async function toggleIrrelevant(pairId, rowElement) {
    try {
        const response = await fetch('/api/toggle_irrelevant/' + pairId, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.is_irrelevant) {
            rowElement.classList.add('irrelevant');
            rowElement.classList.remove('audited');
            rowElement.querySelector('.audit-star').textContent = '❌';
        } else {
            rowElement.classList.remove('irrelevant');
            rowElement.querySelector('.audit-star').textContent = '';
        }
        
        // Перезагружаем для обновления счётчика
        setTimeout(function() {
            location.reload();
        }, 300);
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Не удалось обновить статус');
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    highlightSearchResults();
    animateStats();
    setupRowClickHandlers();
});

// Настройка обработчиков кликов для строк
function setupRowClickHandlers() {
    const rows = document.querySelectorAll('.qa-row');
    
    rows.forEach(function(row) {
        // Отключаем стандартное контекстное меню на правый клик
        row.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const pairId = this.getAttribute('data-id');
            toggleIrrelevant(pairId, this);
            return false;
        });
        
        // Обработчик левого клика
        row.addEventListener('click', function(e) {
            // Игнорируем если это был правый клик
            if (e.button !== 0) return;
            
            e.preventDefault();
            e.stopPropagation();
            const pairId = this.getAttribute('data-id');
            toggleAudit(pairId, this);
        });
        
        // Дополнительная защита от обработки правого клика как обычного
        row.addEventListener('mousedown', function(e) {
            if (e.button === 2) { // Правая кнопка
                e.preventDefault();
                return false;
            }
        });
    });
}

function highlightSearchResults() {
    const searchQuery = new URLSearchParams(window.location.search).get('search');
    if (!searchQuery) return;
    
    const textCells = document.querySelectorAll('.text-cell');
    const searchTerms = searchQuery.toLowerCase().split(' ').filter(function(term) {
        return term.length > 2;
    });
    
    textCells.forEach(function(cell) {
        var html = cell.innerHTML;
        searchTerms.forEach(function(term) {
            var regex = new RegExp('(' + escapeRegExp(term) + ')', 'gi');
            html = html.replace(regex, '<mark>$1</mark>');
        });
        cell.innerHTML = html;
    });
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function animateStats() {
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(function(stat) {
        const target = parseInt(stat.textContent);
        if (isNaN(target)) return;
        
        var current = 0;
        const increment = target / 50;
        const stepTime = 20;
        
        stat.textContent = '0';
        const timer = setInterval(function() {
            current += increment;
            if (current >= target) {
                stat.textContent = target;
                clearInterval(timer);
            } else {
                stat.textContent = Math.floor(current);
            }
        }, stepTime);
    });
}

// Стили для подсветки поиска
const style = document.createElement('style');
style.textContent = 'mark { background-color: #fff59d; padding: 2px 4px; border-radius: 3px; font-weight: 600; }';
document.head.appendChild(style);