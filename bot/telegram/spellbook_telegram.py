import os
import telegram
import telegram.ext
import logging
from bot_utils import parse_queries, uri_validator


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__file__)


async def post_init(application: telegram.ext.Application[telegram.ext.ExtBot[None], telegram.ext.ContextTypes.DEFAULT_TYPE, dict, dict, dict, telegram.ext.JobQueue[telegram.ext.ContextTypes.DEFAULT_TYPE]]):
    LOGGER.info(await application.bot.get_me())


async def search(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        if context.args:
            query = ' '.join(context.args)
            await update.message.reply_text(f'Debug input: {query}')
        else:
            await update.message.reply_text('You haven\'t provided a query to search')


async def search_inline(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.inline_query is not None:
        query = update.inline_query.query
        if not query:
            return
        results = []
        results.append(
            telegram.InlineQueryResultArticle(
                id=str(1),
                title='Result title',
                input_message_content=telegram.InputTextMessageContent(f'Debug input: {query}')
            )
        )
        await context.bot.answer_inline_query(update.inline_query.id, results)


async def find_my_combos(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        match context.args:
            case None | []:
                await update.message.reply_text('You haven\'t provided a deck url')
            case [url]:
                if uri_validator(url):
                    await update.message.reply_text(f'Debug input: {url}')
                else:
                    await update.message.reply_text('The url you have provided is not valid')
            case _:
                await update.message.reply_text('You have provided too many arguments')


async def on_message(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message is not None and update.message.text is not None:
        queries = parse_queries(update.message.text)
        for query in queries:
            await update.message.reply_text(f'Debug input: {query}')


if __name__ == '__main__':
    application = telegram.ext.ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN', '')).post_init(post_init).build()
    
    search_handler = telegram.ext.CommandHandler('search', search)
    find_my_combos_handler = telegram.ext.CommandHandler('find_my_combos', find_my_combos)
    message_handler = telegram.ext.MessageHandler(telegram.ext.filters.TEXT & (~telegram.ext.filters.COMMAND), on_message)
    inline_handler = telegram.ext.InlineQueryHandler(search_inline)
    application.add_handler(search_handler)
    application.add_handler(find_my_combos_handler)
    application.add_handler(message_handler)
    application.add_handler(inline_handler)
    
    application.run_polling()
