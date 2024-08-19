import os
import telegram
import telegram.ext
import logging
from typing import Callable, Awaitable
from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.api_error import APIError
from spellbook_client.models.variant import Variant
from bot_utils import parse_queries, uri_validator, SpellbookQuery, API, url_from_variant, compute_variant_recipe, compute_variant_name, compute_variant_results
from text_utils import telegram_chunk, chunk_diff_async


MAX_SEARCH_RESULTS = 5


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__file__)


async def start(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        if context.args:
            if len(context.args) == 1:
                command = context.args[0]
                if command == 'syntax_guide':
                    await update.message.reply_text('Syntax guide: https://commanderspellbook.com/syntax-guide/')
            else:
                query = ' '.join(context.args)
                await handle_queries([query], update.message)
        else:
            await update.message.reply_text('Hello! I am Spellbook Bot. I can help you find the best combos for your deck. Use /search <query> to find combos for a specific card or /find_my_combos <deck_url> to find combos for your deck')
            await update.message.reply_text(f'You can also use me inline to search for combos. Just type @{context.bot.username} <query> in any chat')


async def post_init(application: telegram.ext.Application[telegram.ext.ExtBot[None], telegram.ext.ContextTypes.DEFAULT_TYPE, dict, dict, dict, telegram.ext.JobQueue[telegram.ext.ContextTypes.DEFAULT_TYPE]]):
    LOGGER.info(await application.bot.get_me())


def compute_variants_results(variants: list[Variant]) -> str:
    result = ''
    for variant in variants:
        variant_url = url_from_variant(variant)
        variant_recipe = compute_variant_recipe(variant)
        result += f'• [{variant_recipe}]({variant_url})\n'
    return result


async def handle_queries(
    queries: list[str],
    message: telegram.Message,
):
    await message.set_reaction('👀')
    reply = ''
    messages: list[telegram.Message] = []
    for query in queries:
        query_info = SpellbookQuery(query)
        try:
            result = await API.variants.get(
                request_configuration=RequestConfiguration[API.variants.VariantsRequestBuilderGetQueryParameters](
                    query_parameters=API.variants.VariantsRequestBuilderGetQueryParameters(
                        q=query_info.patched_query,
                        limit=MAX_SEARCH_RESULTS,
                        ordering='-popularity',
                    ),
                ),
            )
            if len(queries) == 1 and result.count == 1:
                variant = result.results[0]
                variant_url = url_from_variant(variant)
                variant_recipe = compute_variant_recipe(variant)
                reply += f'\n\n**Showing 1 result for {query_info.summary}**\n\n[{variant_recipe}](<{variant_url}>)'
            elif result.count > 0:
                reply += f'\n\n**Showing {len(result.results)} of {result.count} results for {query_info.summary}**\n\n'
                reply += compute_variants_results(result.results)
            else:
                reply += f'\n\nNo results found for {query_info.summary}'
            edit_message: Callable[[int, telegram.Message, str], Awaitable[telegram.Message]] = lambda _, m, c: m.edit_text(c, parse_mode=telegram.constants.ParseMode.MARKDOWN)  # type: ignore
            messages = await chunk_diff_async(
                new_chunks=telegram_chunk(reply),
                add=lambda _, c: message.reply_text(c, parse_mode=telegram.constants.ParseMode.MARKDOWN),
                update=edit_message,
                remove=lambda _, m: m.delete(),
                old_chunks_wrappers=messages,
                unwrap=lambda m: m.text or '',
            )
        except APIError:
            await message.set_reaction('👎')
            reply += f'\n\nFailed to fetch results for {query_info.summary}'
            edit_message: Callable[[int, telegram.Message, str], Awaitable[telegram.Message]] = lambda _, m, c: m.edit_text(c, parse_mode=telegram.constants.ParseMode.MARKDOWN)  # type: ignore
            messages = await chunk_diff_async(
                new_chunks=telegram_chunk(reply),
                add=lambda _, c: message.reply_text(c, parse_mode=telegram.constants.ParseMode.MARKDOWN),
                update=edit_message,
                remove=lambda _, m: m.delete(),
                old_chunks_wrappers=messages,
                unwrap=lambda m: m.text or '',
            )
            break
    await message.set_reaction('👍')
    


async def search(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message is not None:
        if context.args:
            query = ' '.join(context.args)
            await handle_queries([query], update.message)
        else:
            await update.message.reply_text('You haven\'t provided a query to search')


async def search_inline(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.inline_query is not None:
        inline_query = update.inline_query
        query = inline_query.query
        if not query:
            await inline_query.answer([], cache_time=0, button=telegram.InlineQueryResultsButton(
                text='Syntax Guide',
                start_parameter='syntax_guide',
            ))
            return
        current_offset = int(inline_query.offset or 0)
        result = await API.variants.get(
            request_configuration=RequestConfiguration[API.variants.VariantsRequestBuilderGetQueryParameters](
                query_parameters=API.variants.VariantsRequestBuilderGetQueryParameters(
                    q=query,
                    limit=MAX_SEARCH_RESULTS,
                    ordering='-popularity',
                    offset=current_offset,
                ),
            ),
        )
        next_offset = current_offset + MAX_SEARCH_RESULTS
        inline_results = [
            telegram.InlineQueryResultArticle(
                id=str(variant.id),
                title=compute_variant_name(variant),
                description=compute_variant_results(variant),
                input_message_content=telegram.InputTextMessageContent(
                    message_text=f'[{compute_variant_recipe(variant)}]({url_from_variant(variant)})',
                    parse_mode=telegram.constants.ParseMode.MARKDOWN,
                ),
                url=url_from_variant(variant),
            )
            for variant in result.results
        ]
        await inline_query.answer(
            results=inline_results,
            cache_time=24*60*60,
            is_personal=False,
            next_offset=str(next_offset) if next_offset < result.count else None,
        )


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
        if queries:
            await handle_queries(queries, update.message)


if __name__ == '__main__':
    application = telegram.ext.ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN', '')).post_init(post_init).build()
    start_handler = telegram.ext.CommandHandler('start', start)
    search_handler = telegram.ext.CommandHandler('search', search)
    find_my_combos_handler = telegram.ext.CommandHandler('find_my_combos', find_my_combos)
    message_handler = telegram.ext.MessageHandler(telegram.ext.filters.TEXT & (~telegram.ext.filters.COMMAND), on_message)
    inline_handler = telegram.ext.InlineQueryHandler(search_inline)
    application.add_handler(start_handler)
    application.add_handler(search_handler)
    application.add_handler(find_my_combos_handler)
    application.add_handler(message_handler)
    application.add_handler(inline_handler)
    
    application.run_polling()
