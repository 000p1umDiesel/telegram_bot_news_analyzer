# llm_analyzer.py
import json
import re
from typing import Optional, List, Dict, Any
from langchain_community.llms import Ollama
from pydantic import BaseModel, Field
from logger import get_logger
import config


# Pydantic модель для структурированного вывода от LLM
class NewsAnalysis(BaseModel):
    summary: str = Field(description="Краткое содержание новости на русском языке.")
    sentiment: str = Field(
        description="Тональность: 'Позитивная', 'Негативная' или 'Нейтральная'."
    )
    hashtags: List[str] = Field(
        description="Список из 3-5 уникальных и обобщенных хештегов."
    )

    def format_hashtags(self) -> str:
        """Форматирует хештеги в строку для вывода."""
        if not self.hashtags:
            return "Хештеги не сгенерированы."
        return " ".join(f"#{tag}" for tag in self.hashtags)


logger = get_logger()


class OllamaAnalyzer:
    def __init__(
        self, model: str = config.OLLAMA_MODEL, base_url: str = config.OLLAMA_BASE_URL
    ):
        self.logger = get_logger()
        self._log_device_info()
        try:
            self.llm = Ollama(model=model, base_url=base_url)
            # Простая проверка соединения
            self.llm.invoke("Hi", temperature=0.0)
            self.logger.info(f"OllamaAnalyzer инициализирован с моделью {model}")
        except Exception as e:
            self.logger.error(f"Не удалось инициализировать Ollama: {e}")
            raise

    def _log_device_info(self):
        """Логирует информацию о доступных устройствах (CUDA/MPS)."""
        try:
            import torch

            if torch.cuda.is_available():
                self.logger.info(
                    "Обнаружена поддержка CUDA. Ollama должна автоматически использовать GPU."
                )
            elif torch.backends.mps.is_available():
                self.logger.info(
                    "Обнаружена поддержка MPS. Ollama должна автоматически использовать MPS на Mac."
                )
            else:
                self.logger.info(
                    "CUDA и MPS не обнаружены. Ollama будет использовать CPU."
                )
        except ImportError:
            self.logger.info(
                "Библиотека torch не установлена. Невозможно определить доступность CUDA/MPS. "
                "Ollama будет использовать настройки по умолчанию."
            )
        except Exception as e:
            self.logger.warning(f"Ошибка при проверке устройства: {e}")

    def _clean_and_validate_hashtags(self, hashtags: List[Any]) -> List[str]:
        """Очищает, валидирует и дедуплицирует хештеги."""
        cleaned_hashtags = []
        if not isinstance(hashtags, list):
            return []

        for tag in hashtags:
            if not isinstance(tag, str):
                continue
            # Удаляем все, кроме букв, цифр и _, затем заменяем пробелы на _
            cleaned_tag = re.sub(r"[^\w\s]", "", tag).strip().replace(" ", "_")
            if cleaned_tag:
                cleaned_hashtags.append(cleaned_tag.lower())

        # Удаляем дубликаты, сохраняя порядок
        return list(dict.fromkeys(cleaned_hashtags))

    async def analyze_message(self, message_text: str) -> Optional[NewsAnalysis]:
        """Анализирует текст сообщения и возвращает структурированный результат."""
        prompt = f"""
Проанализируй новость и предоставь СТРОГО JSON-ответ со следующими ключами: "summary", "sentiment", "hashtags".

**Правила анализа:**
1.  **summary**: Сделай краткое, но емкое содержание новости на русском языке.
2.  **sentiment**: Определи тональность. Ответ должен быть ОДНИМ из этих слов: 'Позитивная', 'Негативная', 'Нейтральная'.
3.  **hashtags**: Создай список из 3-5 УНИКАЛЬНЫХ и ОЧЕНЬ ОБЩИХ хештегов.
    - Хештеги должны быть на русском языке и отражать одну из следующих категорий:
      'политика', 'экономика', 'происшествия', 'спорт', 'наука_и_технологии', 'культура', 'общество', 'другие_страны'.
    - Используй ТОЛЬКО предложенные категории. Не придумывай свои.
    - Хештеги НЕ должны дублироваться.
    - Выбери наиболее подходящие категории для данной новости.

**Текст новости для анализа:**
{message_text}
"""
        try:
            response = await self.llm.ainvoke(prompt)
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if not match:
                self.logger.warning(f"Не удалось найти JSON в ответе LLM: {response}")
                return None

            json_string = match.group(0)
            try:
                analysis_data = json.loads(json_string)
                # Очистка и валидация хештегов
                analysis_data["hashtags"] = self._clean_and_validate_hashtags(
                    analysis_data.get("hashtags", [])
                )

                return NewsAnalysis(**analysis_data)
            except (json.JSONDecodeError, TypeError) as e:
                self.logger.error(
                    f"Ошибка декодирования/валидации JSON: {e} из ответа: {json_string}"
                )
                return None

        except Exception as e:
            self.logger.error(f"Ошибка при анализе сообщения: {e}")
            return None

    async def get_chat_response(self, text: str) -> str:
        """Получает прямой ответ от LLM для функции чата."""
        prompt = f"""Ты - дружелюбный ассистент. Ответь на сообщение пользователя кратко и по существу.
Сообщение пользователя: {text}"""
        try:
            response = await self.llm.ainvoke(prompt)
            return response.strip()
        except Exception as e:
            self.logger.error(f"Ошибка при генерации ответа в чате: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса."
