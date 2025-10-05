from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
import json
import time
import logging
from typing import Dict, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

import config
from prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT, QUALITY_CHECK_PROMPT

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self):
        # Проверка API ключа
        if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "your-api-key-here":
            raise ValueError(
                "OpenAI API ключ не установлен! "
                "Установите переменную окружения OPENAI_API_KEY или измените config.py"
            )
        
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        logger.info(f"OpenAI клиент инициализирован с моделью {self.model}")
    
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=config.RETRY_DELAY, max=10),
        retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)),
        reraise=True
    )
    def _make_request(self, messages: list, temperature: float = None) -> str:
        """Выполнить запрос к API с retry логикой"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or config.OPENAI_TEMPERATURE,
                max_tokens=config.OPENAI_MAX_TOKENS,
                timeout=config.TIMEOUT
            )
            return response.choices[0].message.content
        except AuthenticationError as e:
            logger.error(f"Ошибка аутентификации OpenAI: {e}")
            raise
        except RateLimitError as e:
            logger.warning(f"Превышен лимит запросов: {e}")
            raise
        except APIError as e:
            logger.error(f"Ошибка API OpenAI: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к OpenAI: {e}")
            raise
    
    def extract_qa_pairs(self, dialog_text: str) -> Optional[Dict]:
        """Извлечь пары Q&A из диалога"""
        logger.info("Отправка диалога на извлечение пар Q&A")
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": EXTRACTION_PROMPT.format(dialog_text=dialog_text)}
        ]
        
        try:
            response_text = self._make_request(messages)
            
            # Очистка от markdown кодблоков если есть
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Парсинг JSON
            result = json.loads(response_text)
            
            logger.info(f"Извлечено пар: {len(result.get('pairs', []))}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от OpenAI: {e}")
            logger.debug(f"Ответ API: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при извлечении пар: {e}")
            return None
    
    def validate_qa_pairs(self, pairs: list) -> Optional[Dict]:
        """Валидация качества пар Q&A"""
        logger.info(f"Валидация {len(pairs)} пар Q&A")
        
        pairs_json = json.dumps(pairs, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": QUALITY_CHECK_PROMPT.format(pairs_json=pairs_json)}
        ]
        
        try:
            response_text = self._make_request(messages, temperature=0.2)
            
            # Очистка от markdown
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)
            
            # Добавление оценок к оригинальным парам
            for i, pair in enumerate(pairs):
                if i < len(result.get('pairs', [])):
                    quality_data = result['pairs'][i]
                    pair['quality_score'] = quality_data.get('average_score', 0)
                    pair['quality_recommendation'] = quality_data.get('recommendation', 'keep')
            
            logger.info("Валидация завершена")
            return result
            
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON валидации: {e}")
            # Если валидация не удалась, возвращаем пары без оценок
            return None
        except Exception as e:
            logger.warning(f"Ошибка при валидации: {e}")
            return None