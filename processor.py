import re
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional

import config
from api_client import OpenAIClient

logger = logging.getLogger(__name__)


class DialogProcessor:
    def __init__(self, openai_client: OpenAIClient):
        self.client = openai_client
    
    def parse_filename_metadata(self, filename: str) -> Optional[Dict]:
        """
        Парсинг метаданных из имени файла
        Формат: 1756875457398472-in-74242490943-79140887950-20250903-075542-1756875342.2004096.txt
        """
        try:
            # Убираем расширение .txt
            name = filename.replace('.txt', '')
            
            # Разбиваем по дефисам
            parts = name.split('-')
            
            if len(parts) < 6:
                logger.warning(f"Неожиданный формат имени файла: {filename}")
                return None
            
            # Извлечение данных
            dialog_id = parts[0]
            call_direction = parts[1]  # in или out
            operator_phone = parts[2]
            client_phone = parts[3].replace('+', '').lstrip('_')  # убираем + и _ если есть
            date_str = parts[4]  # 20250903
            time_str = parts[5]  # 075542
            
            # Преобразование даты: 20250903 -> 2025-09-03
            call_date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            # Преобразование времени: 075542 -> 07:55:42
            call_time = f"{time_str[0:2]}:{time_str[2:4]}:{time_str[4:6]}"
            
            metadata = {
                'dialog_id': dialog_id,
                'call_direction': call_direction,
                'operator_phone': operator_phone,
                'client_phone': client_phone,
                'call_date': call_date,
                'call_time': call_time
            }
            
            logger.info(f"Распознаны метаданные файла {filename}: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Ошибка парсинга имени файла {filename}: {e}", exc_info=True)
            return None
    
    def clean_dialog_text(self, text: str) -> str:
        """Очистка текста диалога от таймкодов"""
        # Удаление таймкодов вида [0.00 - 18.74]
        cleaned = re.sub(r'\[\d+\.\d+\s*-\s*\d+\.\d+\]', '', text)
        
        # Удаление лишних пробелов
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Удаление пустых строк
        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
        
        return '\n'.join(lines)
    
    def generate_dialog_id(self, filename: str, content: str) -> str:
        """Генерация уникального ID диалога"""
        data = f"{filename}:{content[:100]}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def read_dialog_file(self, filepath: Path) -> Optional[str]:
        """Чтение файла диалога"""
        try:
            with open(filepath, 'r', encoding=config.INPUT_ENCODING) as f:
                content = f.read()
            
            if not content.strip():
                logger.warning(f"Файл пустой: {filepath.name}")
                return None
            
            return content
            
        except UnicodeDecodeError:
            logger.error(f"Ошибка кодировки файла: {filepath.name}")
            return None
        except Exception as e:
            logger.error(f"Ошибка чтения файла {filepath.name}: {e}")
            return None
    
    def validate_pairs(self, pairs: List[Dict]) -> List[Dict]:
        """Валидация и фильтрация пар по базовым критериям"""
        valid_pairs = []
        
        for i, pair in enumerate(pairs):
            question = pair.get('question', '').strip()
            answer = pair.get('answer', '').strip()
            
            # Проверка минимальной длины
            if len(question) < config.MIN_QUESTION_LENGTH:
                logger.debug(f"Пара {i}: вопрос слишком короткий ({len(question)} символов)")
                continue
            
            if len(answer) < config.MIN_ANSWER_LENGTH:
                logger.debug(f"Пара {i}: ответ слишком короткий ({len(answer)} символов)")
                continue
            
            # Проверка обязательных полей
            if not pair.get('direction'):
                logger.debug(f"Пара {i}: отсутствует направление")
                continue
            
            # Проверка качества если есть оценка
            quality_score = pair.get('quality_score', 10)
            if quality_score < config.MIN_QUALITY_SCORE:
                logger.debug(f"Пара {i}: низкая оценка качества ({quality_score})")
                continue
            
            valid_pairs.append(pair)
        
        logger.info(f"Валидных пар: {len(valid_pairs)} из {len(pairs)}")
        return valid_pairs
    
    def process_dialog(self, filepath: Path) -> Dict:
        """Обработка одного диалога"""
        filename = filepath.name
        logger.info(f"Обработка файла: {filename}")
        
        result = {
            'filename': filename,
            'success': False,
            'pairs': [],
            'has_business_pairs': False,
            'error': None,
            'dialog_id': None
        }
        
        # Чтение файла
        raw_content = self.read_dialog_file(filepath)
        if not raw_content:
            result['error'] = "Ошибка чтения файла"
            return result
        
        # Очистка текста
        cleaned_content = self.clean_dialog_text(raw_content)
        if not cleaned_content:
            result['error'] = "Файл пустой после очистки"
            return result
        
        # Генерация ID диалога
        dialog_id = self.generate_dialog_id(filename, cleaned_content)
        result['dialog_id'] = dialog_id
        
        # Парсинг метаданных из имени файла
        file_metadata = self.parse_filename_metadata(filename)
        result['file_metadata'] = file_metadata  # Сохраняем сразу в result
        
        if file_metadata:
            logger.info(f"Метаданные извлечены: {file_metadata}")
        else:
            logger.warning(f"Не удалось извлечь метаданные из {filename}")
        
        # Извлечение пар через OpenAI
        try:
            extraction_result = self.client.extract_qa_pairs(cleaned_content)
            
            if not extraction_result:
                result['error'] = "Ошибка извлечения пар (extract_qa_pairs вернул None)"
                logger.error(f"extract_qa_pairs вернул None для файла {filename}")
                return result
            
            has_business_pairs = extraction_result.get('has_business_pairs', False)
            pairs = extraction_result.get('pairs', [])
            
            result['has_business_pairs'] = has_business_pairs
            
            if not has_business_pairs or not pairs:
                logger.info(f"Файл {filename}: нет бизнес-пар")
                result['success'] = True
                return result
            
            # Валидация качества пар через OpenAI (опционально)
            # Временно отключено для упрощения - можно включить позже
            # validation_result = self.client.validate_qa_pairs(pairs)
            
            # Базовая валидация и фильтрация
            valid_pairs = self.validate_pairs(pairs)
            
            if valid_pairs:
                result['pairs'] = valid_pairs
                result['success'] = True
                logger.info(f"Файл {filename}: извлечено {len(valid_pairs)} пар")
            else:
                logger.warning(f"Файл {filename}: все пары отфильтрованы")
                result['success'] = True
                result['has_business_pairs'] = False
            
        except Exception as e:
            logger.error(f"Ошибка обработки файла {filename}: {e}", exc_info=True)
            result['error'] = str(e)
        
        return result