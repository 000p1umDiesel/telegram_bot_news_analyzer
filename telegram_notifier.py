# telegram_notifier.py
from typing import Dict, Any
from aiogram import Bot
from logger import get_logger
import config

logger = get_logger()


async def send_analysis_result(bot: Bot, analysis_data: Dict[str, Any]):
    """
    Отправляет отформатированный результат анализа в заданный чат Telegram.

    Args:
        bot (Bot): Экземпляр бота aiogram для отправки сообщения.
        analysis_data (Dict[str, Any]): Словарь, содержащий данные анализа.
            Ожидаемые ключи: "channel_title", "message_link", "original_message",
            "summary", "sentiment", "hashtags_formatted".
    """
    if not config.TELEGRAM_CHAT_ID:
        logger.warning(
            "TELEGRAM_CHAT_ID не установлен. Отправка результата анализа невозможна."
        )
        return

    # Словарь для преобразования тональности в хештег
    sentiment_to_hashtag = {
        "Позитивная": "#позитивная_новость",
        "Негативная": "#негативная_новость",
        "Нейтральная": "#нейтральная_новость",
    }
    sentiment_hashtag = sentiment_to_hashtag.get(analysis_data["sentiment"], "#новость")

    try:
        # Формируем текст сообщения
        message_text = (
            f"📊 **Анализ из «{analysis_data['channel_title']}»**\n\n"
            f"**📝 Краткое содержание:**\n{analysis_data['summary']}\n\n"
            f"🔗 [Оригинал]({analysis_data['message_link']})\n\n"
            f"{analysis_data['hashtags_formatted']}\n"
            f"{sentiment_hashtag}"
        )

        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message_text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        logger.info(
            f"Результат анализа для сообщения {analysis_data['message_link']} успешно отправлен."
        )

    except Exception as e:
        logger.error(f"Ошибка при отправке результата анализа: {e}")
