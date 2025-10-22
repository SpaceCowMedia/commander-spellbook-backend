from argparse import ArgumentParser
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
import asyncpraw.exceptions
from spellbook_client import PropertiesApi, VariantsApi, ApiException
from bot_utils import compute_variant_name, compute_variant_results, parse_queries, SpellbookQuery, API, compute_variant_recipe, url_from_variant, url_from_variant_id, WEBSITE_URL


REDDIT_USERNAME = os.getenv('KUBE_REDDIT_USERNAME', os.getenv('REDDIT_USERNAME'))
MAIN_SUBREDDIT = 'CommanderSpellbook'

MAX_SEARCH_RESULTS = 5
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__file__)

SUBREDDITS = [
    MAIN_SUBREDDIT,
    # 'magicTCG',
    # 'MagicArena',
    # 'EDH',
    # 'BudgetBrews',
    # 'custommagic',
    'mtg',
    # 'BadMtgCombos',
    # 'PioneerMTG',
    # 'mtgrules',
    # 'Pauper',
    'CompetitiveEDH',
    # 'ModernMagic',
    # 'EDHBrews',
    # 'DegenerateEDH',
    # 'freemagic',
    # 'custommagic',
    # 'jankEDH',
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
    help_text = 'Use {{query}} to search for combos. Commander Spellbook [syntax guide]'f'({WEBSITE_URL}).'
    return f'{reply}\n\n___\n{help_text}'


async def process_submissions(reddit: asyncpraw.Reddit):
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit('+'.join(SUBREDDITS))
    async for submission in subreddit.stream.submissions(skip_existing=True):
        submission: asyncpraw.models.reddit.submission.Submission
        author: asyncpraw.models.reddit.redditor.Redditor | None = submission.author
        if author is None:
            continue
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
                LOGGER.warning('Failed to post (forbidden) reply to submission %s', submission.id)
            except (asyncprawcore.AsyncPrawcoreException, asyncpraw.exceptions.AsyncPRAWException) as e:
                LOGGER.exception('Failed to post (error) reply to submission %s', submission.id, exc_info=e)


async def answer_greeting(comment: asyncpraw.models.reddit.comment.Comment):
    formatted_input = comment.body.strip()
    parent = await comment.parent()
    await parent.load()
    author: asyncpraw.models.reddit.redditor.Redditor | None = parent.author
    if author is None:
        return
    answer = None
    if author.name == REDDIT_USERNAME and re.match(r'^(?:(?:good|amazing|great) (?:bot|job)|gj)', formatted_input, re.IGNORECASE):
        if getattr(parent, 'body', None) in GOOD_BOT_RESPONSES + THANKS_RESPONSES:
            answer = '👍'
        else:
            answer = random.choice(GOOD_BOT_RESPONSES)
    elif author.name == REDDIT_USERNAME and re.match(r'^(?:thanks|thank you).{0,20}$', formatted_input, re.IGNORECASE):
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
            LOGGER.warning('Failed to post (forbidden) reply to comment %s', comment.id)
        except (asyncprawcore.AsyncPrawcoreException, asyncpraw.exceptions.AsyncPRAWException) as e:
            LOGGER.exception('Failed to post (error) reply to comment %s', comment.id, exc_info=e)


async def process_comments(reddit: asyncpraw.Reddit):
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit('+'.join(SUBREDDITS))
    async for comment in subreddit.stream.comments(skip_existing=True):
        comment: asyncpraw.models.reddit.comment.Comment
        author: asyncpraw.models.reddit.redditor.Redditor | None = comment.author
        if author is None:
            continue
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
                LOGGER.warning('Failed to post (forbidden) reply to comment %s', comment.id)
            except (asyncprawcore.AsyncPrawcoreException, asyncpraw.exceptions.AsyncPRAWException) as e:
                LOGGER.exception('Failed to post (error) reply to comment %s', comment.id, exc_info=e)
        else:
            await answer_greeting(comment)


async def post_daily_combo(reddit: asyncpraw.Reddit):
    try:
        async with API() as api_client:
            api = PropertiesApi(api_client)
            result = await api.properties_retrieve('combo_of_the_day')
            combo_of_the_day: str = result.value
            api = VariantsApi(api_client)
            variant = await api.variants_retrieve(combo_of_the_day)
    except ApiException:
        LOGGER.error('Failed to fetch combo of the day')
        return
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit(MAIN_SUBREDDIT)
    try:
        submission: asyncpraw.models.reddit.submission.Submission = await subreddit.submit(
            title='♾️ New Combo of the Day! ♾️',
            selftext=f'''
            ## Check out today's combo of the day

            ### Cards
            {compute_variant_name(variant, '\n')}

            ### Results
            {compute_variant_results(variant, '\n')}
            ---
            Explore more combos at [Commander Spellbook]({WEBSITE_URL})!
            ''',
            url=url_from_variant_id(combo_of_the_day),
            send_replies=False,
            spoiler=variant.spoiler,
        )
        if submission is None:
            LOGGER.error('Failed to post daily combo')
        else:
            LOGGER.info('Posted daily combo: %s', submission.id)
    except asyncprawcore.exceptions.Forbidden:
        LOGGER.warning('Failed to post (forbidden) daily combo: forbidden')
    except (asyncprawcore.AsyncPrawcoreException, asyncpraw.exceptions.AsyncPRAWException) as e:
        LOGGER.exception('Failed to post (error) daily combo', exc_info=e)


async def daily(reddit: asyncpraw.Reddit):
    await post_daily_combo(reddit)


async def main():
    parser = ArgumentParser()
    parser.add_argument('--daily', action='store_true', help='Run daily tasks')
    args = parser.parse_args()
    async with asyncpraw.Reddit(
        client_id=os.getenv('KUBE_REDDIT_CLIENT_ID', os.getenv('REDDIT_CLIENT_ID')),
        client_secret=os.getenv('KUBE_REDDIT_CLIENT_SECRET', os.getenv('REDDIT_CLIENT_SECRET')),
        username=REDDIT_USERNAME,
        password=os.getenv('KUBE_REDDIT_PASSWORD', os.getenv('REDDIT_PASSWORD')),
        user_agent=f'Commander Spellbook bot for u/{REDDIT_USERNAME}',
    ) as reddit:
        if args.daily:
            await daily(reddit)
            return
        LOGGER.info('Starting Reddit bot as u/%s', REDDIT_USERNAME)
        await asyncio.gather(
            process_submissions(reddit),
            process_comments(reddit),
        )

if __name__ == "__main__":
    asyncio.run(main())
