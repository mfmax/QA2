// Глобальная функция для переключения аудита (левая кнопка)
async function toggleAudit(pairId, rowElement) {
    try {
        // Проверяем текущее состояние ДО изменения
        const wasIrrelevant = rowElement.classList.contains('irrelevant');
        const wasAudited = rowElement.classList.contains('audited');
        
        const response = await fetch('/api/toggle_audit/' + pairId, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.is_audited) {
            rowElement.classList.add('audited');
            rowElement.classList.remove('irrelevant');
            rowElement.querySelector('.audit-star').textContent = '⭐';
            
            // Если не была проверенной, увеличиваем счётчик
            if (!wasAudited) {
                updateCounter('audited', 1);
            }
            
            // Если была нерелевантной, уменьшаем счётчик нерелевантных
            if (wasIrrelevant) {
                updateCounter('irrelevant', -1);
            }
        } else {
            rowElement.classList.remove('audited');
            rowElement.querySelector('.audit-star').textContent = '';
            
            // Если была проверенной, уменьшаем счётчик
            if (wasAudited) {
                updateCounter('audited', -1);
            }
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Не удалось обновить статус');
    }
}

// Функция для переключения нерелевантности (правая кнопка)
async function toggleIrrelevant(pairId, rowElement) {
    try {
        // Проверяем текущее состояние ДО изменения
        const wasAudited = rowElement.classList.contains('audited');
        const wasIrrelevant = rowElement.classList.contains('irrelevant');
        
        const response = await fetch('/api/toggle_irrelevant/' + pairId, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.is_irrelevant) {
            rowElement.classList.add('irrelevant');
            rowElement.classList.remove('audited');
            rowElement.querySelector('.audit-star').textContent = '❌';
            
            // Если не была нерелевантной, увеличиваем счётчик
            if (!wasIrrelevant) {
                updateCounter('irrelevant', 1);
            }
            
            // Если была проверенной, уменьшаем счётчик проверенных
            if (wasAudited) {
                updateCounter('audited', -1);
            }
        } else {
            rowElement.classList.remove('irrelevant');
            rowElement.querySelector('.audit-star').textContent = '';
            
            // Если была нерелевантной, уменьшаем счётчик
            if (wasIrrelevant) {
                updateCounter('irrelevant', -1);
            }
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Не удалось обновить статус');
    }
}

// Функция обновления счётчиков
function updateCounter(type, delta) {
    let counterElement;
    
    if (type === 'audited') {
        // Находим карточку "Проверено" (4-я карточка)
        counterElement = document.querySelector('.stat-card-audit .stat-value');
    } else if (type === 'irrelevant') {
        // Находим карточку "Нерелевантно" (5-я карточка)
        counterElement = document.querySelector('.stat-card-irrelevant .stat-value');
    }
    
    if (counterElement) {
        const currentValue = parseInt(counterElement.textContent) || 0;
        const newValue = Math.max(0, currentValue + delta);
        
        // Плавная анимация изменения числа
        animateCounterChange(counterElement, currentValue, newValue);
    }
}

// Анимация изменения счётчика
function animateCounterChange(element, from, to) {
    const duration = 300; // milliseconds
    const steps = 20;
    const stepValue = (to - from) / steps;
    const stepTime = duration / steps;
    
    let current = from;
    let step = 0;
    
    const timer = setInterval(function() {
        step++;
        current += stepValue;
        
        if (step >= steps) {
            element.textContent = to;
            clearInterval(timer);
        } else {
            element.textContent = Math.round(current);
        }
    }, stepTime);
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    highlightSearchResults();
    animateStats();
    setupRowClickHandlers();
    markInitialStates();
});

// Помечаем начальное состояние строк
function markInitialStates() {
    const rows = document.querySelectorAll('.qa-row');
    rows.forEach(function(row) {
        if (row.classList.contains('audited')) {
            row.dataset.wasAudited = 'true';
        }
        if (row.classList.contains('irrelevant')) {
            row.dataset.wasIrrelevant = 'true';
        }
    });
}

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