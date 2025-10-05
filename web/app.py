#!/usr/bin/env python3
"""
Веб-интерфейс для просмотра извлеченных Q&A пар
"""
from flask import Flask, render_template, request, jsonify
import sqlite3
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
import config

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False


def get_db_connection():
    """Получение соединения с БД"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_statistics():
    """Получение статистики"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM qa_pairs")
    total_pairs = cursor.fetchone()['count']
    
    cursor.execute("""
        SELECT direction, COUNT(*) as count 
        FROM qa_pairs 
        GROUP BY direction
    """)
    by_direction = {row['direction']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'total_pairs': total_pairs,
        'client_to_operator': by_direction.get('Клиент → Оператор', 0),
        'operator_to_client': by_direction.get('Оператор → Клиент', 0)
    }


@app.route('/')
def index():
    """Главная страница"""
    search = request.args.get('search', '').strip()
    direction_filter = request.args.get('direction', '')
    type_filter = request.args.get('type', '')
    audit_filter = request.args.get('audit', '')
    no_pagination = request.args.get('no_pagination', '') == 'on'
    page = int(request.args.get('page', 1))
    per_page = 100
    
    stats = get_statistics()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id, question, answer, direction, question_type, keywords, is_audited 
        FROM qa_pairs 
        WHERE 1=1
    """
    params = []
    
    if search:
        query += " AND (question LIKE ? OR answer LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if direction_filter:
        query += " AND direction = ?"
        params.append(direction_filter)
    if type_filter:
        query += " AND question_type = ?"
        params.append(type_filter)
    if audit_filter == 'yes':
        query += " AND is_audited = 1"
    elif audit_filter == 'no':
        query += " AND is_audited = 0"
    
    count_query = "SELECT COUNT(*) as count FROM qa_pairs WHERE 1=1"
    count_params = []
    if search:
        count_query += " AND (question LIKE ? OR answer LIKE ?)"
        count_params.extend([f'%{search}%', f'%{search}%'])
    if direction_filter:
        count_query += " AND direction = ?"
        count_params.append(direction_filter)
    if type_filter:
        count_query += " AND question_type = ?"
        count_params.append(type_filter)
    if audit_filter == 'yes':
        count_query += " AND is_audited = 1"
    elif audit_filter == 'no':
        count_query += " AND is_audited = 0"
    
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()['count']
    
    query += " ORDER BY id DESC"
    if not no_pagination:
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"
        total_pages = (total_count + per_page - 1) // per_page
    else:
        total_pages = 1
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    qa_pairs = []
    for row in rows:
        try:
            keywords = json.loads(row['keywords']) if row['keywords'] else []
        except:
            keywords = []
        qa_pairs.append({
            'id': row['id'],
            'question': row['question'],
            'answer': row['answer'],
            'direction': row['direction'],
            'question_type': row['question_type'] or '',
            'keywords': keywords,
            'is_audited': row['is_audited']
        })
    
    cursor.execute("SELECT DISTINCT question_type FROM qa_pairs WHERE question_type IS NOT NULL AND question_type != '' ORDER BY question_type")
    question_types = [row['question_type'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) as count FROM qa_pairs WHERE is_audited = 1")
    audited_count = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template('index.html', qa_pairs=qa_pairs, stats=stats, total_count=total_count,
                          audited_count=audited_count, page=page, total_pages=total_pages,
                          search=search, direction_filter=direction_filter, type_filter=type_filter,
                          audit_filter=audit_filter, no_pagination=no_pagination, question_types=question_types)


@app.route('/api/toggle_audit/<int:pair_id>', methods=['POST'])
def toggle_audit(pair_id):
    """API для переключения статуса аудита"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_audited FROM qa_pairs WHERE id = ?", (pair_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        new_status = 0 if row['is_audited'] else 1
        cursor.execute("UPDATE qa_pairs SET is_audited = ? WHERE id = ?", (new_status, pair_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'is_audited': new_status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


@app.route('/')
def index():
    """Главная страница"""
    # Параметры фильтрации
    search = request.args.get('search', '').strip()
    direction_filter = request.args.get('direction', '')
    type_filter = request.args.get('type', '')
    audit_filter = request.args.get('audit', '')  # Новый фильтр аудита
    no_pagination = request.args.get('no_pagination', '') == 'on'
    page = int(request.args.get('page', 1))
    per_page = 100
    
    # Статистика
    stats = get_statistics()
    
    # Построение SQL запроса
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Базовый запрос
    query = """
        SELECT 
            id, question, answer, direction, question_type, keywords,
            call_direction, operator_phone, client_phone, call_date, call_time,
            is_audited
        FROM qa_pairs
        WHERE 1=1
    """
    params = []
    
    # Фильтр по поиску
    if search:
        query += " AND (question LIKE ? OR answer LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    # Фильтр по направлению Q&A
    if direction_filter:
        query += " AND direction = ?"
        params.append(direction_filter)
    
    # Фильтр по типу вопроса
    if type_filter:
        query += " AND question_type = ?"
        params.append(type_filter)
    
    # Фильтр по аудиту
    if audit_filter == 'yes':
        query += " AND is_audited = 1"
    elif audit_filter == 'no':
        query += " AND is_audited = 0"
    
    # Получаем общее количество для пагинации
    count_query = f"""
        SELECT COUNT(*) as count
        FROM qa_pairs
        WHERE 1=1
    """
    count_params = []
    
    if search:
        count_query += " AND (question LIKE ? OR answer LIKE ?)"
        count_params.extend([f'%{search}%', f'%{search}%'])
    
    if direction_filter:
        count_query += " AND direction = ?"
        count_params.append(direction_filter)
    
    if type_filter:
        count_query += " AND question_type = ?"
        count_params.append(type_filter)
    
    if audit_filter == 'yes':
        count_query += " AND is_audited = 1"
    elif audit_filter == 'no':
        count_query += " AND is_audited = 0"
    
    cursor.execute(count_query, count_params)
    result = cursor.fetchone()
    total_count = result['count'] if result else 0
    
    # Сортировка и пагинация
    query += " ORDER BY id DESC"
    
    if not no_pagination:
        offset = (page - 1) * per_page
        query += f" LIMIT {per_page} OFFSET {offset}"
        total_pages = (total_count + per_page - 1) // per_page
    else:
        total_pages = 1
    
    # Выполнение запроса
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Обработка результатов
    qa_pairs = []
    for row in rows:
        try:
            keywords = json.loads(row['keywords']) if row['keywords'] else []
        except:
            keywords = []
        
        qa_pairs.append({
            'id': row['id'],
            'question': row['question'],
            'answer': row['answer'],
            'direction': row['direction'],
            'question_type': row['question_type'] or '',
            'keywords': keywords,
            'call_direction': row['call_direction'] or '',
            'operator_phone': row['operator_phone'] or '',
            'client_phone': row['client_phone'] or '',
            'call_date': row['call_date'] or '',
            'call_time': row['call_time'] or '',
            'is_audited': row['is_audited']
        })
    
    # Получаем уникальные типы вопросов для фильтра
    cursor.execute("SELECT DISTINCT question_type FROM qa_pairs WHERE question_type IS NOT NULL AND question_type != '' ORDER BY question_type")
    question_types = [row['question_type'] for row in cursor.fetchall()]
    
    # Статистика аудита
    cursor.execute("SELECT COUNT(*) as count FROM qa_pairs WHERE is_audited = 1")
    audited_count = cursor.fetchone()['count']
    
    conn.close()
    
    return render_template(
        'index.html',
        qa_pairs=qa_pairs,
        stats=stats,
        total_count=total_count,
        audited_count=audited_count,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        search=search,
        direction_filter=direction_filter,
        type_filter=type_filter,
        audit_filter=audit_filter,
        no_pagination=no_pagination,
        question_types=question_types
    )


@app.route('/api/toggle_audit/<int:pair_id>', methods=['POST'])
def toggle_audit(pair_id):
    """API для переключения статуса аудита"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем текущий статус
        cursor.execute("SELECT is_audited FROM qa_pairs WHERE id = ?", (pair_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({'error': 'Пара не найдена'}), 404
        
        # Переключаем статус
        new_status = 0 if row['is_audited'] else 1
        cursor.execute("UPDATE qa_pairs SET is_audited = ? WHERE id = ?", (new_status, pair_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'is_audited': new_status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)