# bot_services.py
from aiogram import Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from services import (
    data_manager,
    llm_analyzer,
    tavily_search,
)
import config
from logger import get_logger

logger = get_logger()
dp = Dispatcher()


@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    """Отправляет приветственное сообщение со списком команд."""
    help_text = (
        "👋 **Привет! Я бот для анализа новостей и работы с LLM.**\n\n"
        "**Доступные команды:**\n"
        "/help - Показать это сообщение\n"
        "/status - Показать статус системы\n"
        "/stats - Показать статистику анализа\n"
        "/chat `<текст>` - Пообщаться с LLM\n"
        "/web `<запрос>` - Поиск в интернете\n"
        "/analyze `<текст>` - Проанализировать произвольный текст"
    )
    await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Показывает статус компонентов системы."""
    status_text = (
        "✅ **Статус системы:**\n\n"
        "• **Бот:** Онлайн\n"
        f"• **Мониторинг канала:** `{config.TELEGRAM_CHANNEL_ID}`\n"
        f"• **LLM модель:** `{config.OLLAMA_MODEL}`"
    )
    await message.answer(status_text, parse_mode=ParseMode.MARKDOWN)


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показывает статистику анализа."""
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        stats = data_manager.get_statistics()
        if not stats or stats.get("total_messages", 0) == 0:
            await message.answer(
                "😔 Пока нет данных для статистики. Мониторинг еще не обработал ни одного сообщения."
            )
            return

        sentiment_counts = stats.get("sentiment_counts", {})
        hashtags = stats.get("popular_hashtags", [])
        hashtags_str = f"`{'`, `'.join(hashtags)}`" if hashtags else "нет"

        response = (
            f"📊 **Статистика анализа:**\n\n"
            f"📝 **Всего проанализировано:** {stats.get('total_messages', 0)}\n"
            f"📈 **Позитивных:** {sentiment_counts.get('Позитивная', 0)}\n"
            f"📉 **Негативных:** {sentiment_counts.get('Негативная', 0)}\n"
            f"➖ **Нейтральных:** {sentiment_counts.get('Нейтральная', 0)}\n\n"
            f"🏷️ **Топ-10 хештегов:**\n"
            f"{hashtags_str}"
        )
        await message.answer(response, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении статистики.")


@dp.message(Command("chat"))
async def cmd_chat(message: types.Message, command: CommandObject):
    """Общается с LLM."""
    if not command.args:
        await message.answer("Пожалуйста, напишите что-нибудь после команды `/chat`")
        return
    text = command.args

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    response = await llm_analyzer.get_chat_response(text)
    await message.answer(response)


@dp.message(Command("analyze"))
async def cmd_analyze(message: types.Message, command: CommandObject):
    """Анализирует произвольный текст."""
    if not command.args:
        await message.answer(
            "Пожалуйста, укажите текст для анализа: `/analyze <текст>`"
        )
        return
    text_to_analyze = command.args

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress_message = await message.answer("🔍 Анализирую текст...")

    analysis = await llm_analyzer.analyze_message(text_to_analyze)

    if analysis and analysis.summary:
        hashtags_str = (
            f"`{'`, `'.join(analysis.hashtags)}`" if analysis.hashtags else "нет"
        )
        response = (
            f"📊 **Результаты анализа:**\n\n"
            f"**Краткое содержание:**\n{analysis.summary}\n\n"
            f"**Тональность:** {analysis.sentiment}\n\n"
            f"**Хештеги:**\n{hashtags_str}"
        )
        await progress_message.edit_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await progress_message.edit_text(
            "❌ Не удалось проанализировать текст. Возможно, сервис LLM недоступен."
        )


@dp.message(Command("web"))
async def cmd_web(message: types.Message, command: CommandObject):
    """Выполняет поиск в интернете."""
    if not command.args:
        await message.answer("Пожалуйста, укажите поисковый запрос: `/web <запрос>`")
        return
    query = command.args

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    progress_message = await message.answer(
        f'🔍 Ищу информацию по запросу: "{query}"...'
    )

    search_results = await tavily_search.search(query)

    if search_results is None:
        await progress_message.edit_text(
            "❌ **Ошибка поиска**\n\nНе удалось связаться с сервисом поиска."
        )
        return

    if not search_results:
        await progress_message.edit_text(
            f"🤷‍♂️ По вашему запросу «{query}» ничего не найдено."
        )
        return

    formatted_search_results = tavily_search.format_search_results(
        search_results, query
    )
    await progress_message.edit_text(
        formatted_search_results,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


@dp.message()
async def handle_non_command(message: types.Message):
    """Обрабатывает сообщения без команд как чат с LLM."""
    if message.text and not message.text.startswith("/"):
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        response = await llm_analyzer.get_chat_response(message.text)
        await message.answer(response)
