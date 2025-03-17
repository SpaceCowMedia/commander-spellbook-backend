import os
import re
import random
import logging
import asyncpraw
import asyncprawcore
import asyncio
import asyncpraw.models
import asyncpraw.models.reddit
import asyncpraw.models.reddit.comment
import asyncpraw.models.reddit.redditor
import asyncpraw.models.reddit.submission
import asyncpraw.models.reddit.subreddit
from spellbook_client import VariantsApi, ApiException
from bot_utils import parse_queries, SpellbookQuery, API, compute_variant_recipe, url_from_variant


REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')

MAX_SEARCH_RESULTS = 5
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__file__)

SUBREDDITS = [
    # 'magicTCG',
    # 'MagicArena',
    # 'EDH',
    # 'BudgetBrews',
    # 'custommagic',
    # 'mtg',
    # 'BadMtgCombos',
    # 'PioneerMTG',
    # 'mtgrules',
    # 'Pauper',
    # 'CompetitiveEDH',
    # 'ModernMagic',
    # 'EDHBrews',
    # 'DegenerateEDH',
    # 'freemagic',
    # 'custommagic',
    # 'jankEDH',
    'CommanderSpellbook',
]


GOOD_BOT_RESPONSES = [
    'Thank you! I try my best to help.',
    'I appreciate the kind words!',
    'I am here to help!',
    'I am glad you think so!',
    'Thank you for the compliment!',
    '👍',
    '😊',
]

THANKS_RESPONSES = [
    'You are welcome!',
    'No problem!',
    'I am happy to help!',
]


async def process_input(text: str) -> str | None:
    queries = parse_queries(text)
    if not queries:
        return None
    reply = ''
    for query in queries:
        query_info = SpellbookQuery(query)
        try:
            async with API() as api_client:
                api = VariantsApi(api_client)
                result = await api.variants_list(
                    q=query_info.patched_query,
                    limit=MAX_SEARCH_RESULTS,
                    ordering='-popularity',
                )
            match result.count:
                case 0:
                    reply += f'{'* ' if len(queries) > 1 else ''}No results found for {query_info.summary}\n'
                case 1:
                    variant = result.results[0]
                    variant_recipe = compute_variant_recipe(variant)
                    variant_url = url_from_variant(variant)
                    variant_link = f'[{variant_recipe}]({variant_url})'
                    if len(queries) == 1:
                        reply += f'{variant_link}\n'
                    else:
                        reply += f'* Found 1 result for {query_info.summary}: {variant_link}\n'
                case n:
                    reply += f'{'* ' if len(queries) > 1 else ''}Found {n} results for {query_info.summary}, such as:\n'
                    for variant in result.results:
                        variant_recipe = compute_variant_recipe(variant)
                        variant_url = url_from_variant(variant)
                        variant_link = f'[{variant_recipe}]({variant_url})'
                        reply += f'  1. {variant_link} (found in {variant.popularity} decks)\n'
        except ApiException:
            if len(queries) == 1:
                reply += f'Failed to fetch results for {query_info.summary}\n'
            else:
                reply += f'* Failed to fetch results for {query_info.summary}\n'
    help_text = '^({{query}} to search combos, following the Commander Spellbook) [syntax](https://commanderspellbook.com/syntax-guide)'
    return f'{reply}\n\n{help_text}'


async def process_submissions(reddit: asyncpraw.Reddit):
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit('+'.join(SUBREDDITS))
    async for submission in subreddit.stream.submissions(skip_existing=True):
        submission: asyncpraw.models.reddit.submission.Submission
        author: asyncpraw.models.reddit.redditor.Redditor = submission.author
        if author.name == REDDIT_USERNAME:
            continue
        formatted_input = f'# {submission.title}\n\n{submission.selftext}'
        answer = await process_input(formatted_input)
        if answer:
            try:
                result = await submission.reply(answer)
                if result is None:
                    LOGGER.error('Failed to post reply to submission %s', submission.id)
            except asyncprawcore.exceptions.Forbidden:
                LOGGER.warning('Failed to post reply to submission %s', submission.id)
            except asyncprawcore.AsyncPrawcoreException as e:
                LOGGER.exception('Failed to post reply to submission %s', submission.id, exc_info=e)


async def answer_greeting(comment: asyncpraw.models.reddit.comment.Comment):
    if random.random() > 0.1:
        # Consider only replying to a fraction of comments to reduce spam
        return
    formatted_input = comment.body.strip()
    parent = await comment.parent()
    await parent.load()
    if parent.author.name == REDDIT_USERNAME and re.match(r'^(?:(?:good|amazing|great) (?:bot|job)|gj)', formatted_input, re.IGNORECASE):
        if getattr(parent, 'body', None) in GOOD_BOT_RESPONSES + THANKS_RESPONSES:
            answer = '👍'
        else:
            answer = random.choice(GOOD_BOT_RESPONSES)
    elif parent.author.name == REDDIT_USERNAME and re.match(r'^(?:thanks|thank you).{0,20}$', formatted_input, re.IGNORECASE):
        if getattr(parent, 'body', None) in GOOD_BOT_RESPONSES + THANKS_RESPONSES:
            answer = '👍'
        else:
            answer = random.choice(THANKS_RESPONSES)
    if answer:
        try:
            result = await comment.reply(answer)
            if result is None:
                LOGGER.error('Failed to post reply to comment %s', comment.id)
        except asyncprawcore.exceptions.Forbidden:
            LOGGER.warning('Failed to post reply to comment %s', comment.id)
        except asyncprawcore.AsyncPrawcoreException as e:
            LOGGER.exception('Failed to post reply to comment %s', comment.id, exc_info=e)


async def process_comments(reddit: asyncpraw.Reddit):
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit('+'.join(SUBREDDITS))
    async for comment in subreddit.stream.comments(skip_existing=True):
        comment: asyncpraw.models.reddit.comment.Comment
        author: asyncpraw.models.reddit.redditor.Redditor = comment.author
        if author.name == REDDIT_USERNAME:
            continue
        formatted_input = comment.body.strip()
        answer = await process_input(formatted_input)
        if answer:
            try:
                result = await comment.reply(answer)
                if result is None:
                    LOGGER.error('Failed to post reply to comment %s', comment.id)
            except asyncprawcore.exceptions.Forbidden:
                LOGGER.warning('Failed to post reply to comment %s', comment.id)
            except asyncprawcore.AsyncPrawcoreException as e:
                LOGGER.exception('Failed to post reply to comment %s', comment.id, exc_info=e)
        else:
            await answer_greeting(comment)


async def main():
    reddit = asyncpraw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        username=REDDIT_USERNAME,
        password=os.getenv('REDDIT_PASSWORD'),
        user_agent=f'Commander Spellbook bot for u/{os.getenv('REDDIT_USERNAME')}',
    )
    LOGGER.info('Starting Reddit bot as u/%s', REDDIT_USERNAME)
    await asyncio.gather(
        process_submissions(reddit),
        process_comments(reddit),
    )

if __name__ == "__main__":
    asyncio.run(main())
