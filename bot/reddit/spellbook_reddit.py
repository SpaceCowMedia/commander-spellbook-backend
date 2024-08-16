import os
import re
import random
import asyncpraw
import asyncprawcore
import asyncio
import asyncpraw.models
import asyncpraw.models.reddit
import asyncpraw.models.reddit.comment
import asyncpraw.models.reddit.redditor
import asyncpraw.models.reddit.submission
import asyncpraw.models.reddit.subreddit
from bot_utils import parse_queries


REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')

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
    'MTGComboFetcher',
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


async def process_input(text: str) -> str | None:
    queries = parse_queries(text)
    if not queries:
        return None
    return None


async def process_submissions(reddit: asyncpraw.Reddit):
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit('+'.join(SUBREDDITS))
    async for submission in subreddit.stream.submissions():
        submission: asyncpraw.models.reddit.submission.Submission
        author: asyncpraw.models.reddit.redditor.Redditor = submission.author
        if author.name == REDDIT_USERNAME:
            continue
        formatted_input = f'# {submission.title}\n\n{submission.selftext}'
        answer = await process_input(formatted_input)
        if answer:
            try:
                await submission.reply(answer)
            except asyncprawcore.exceptions.Forbidden:
                pass


async def process_comments(reddit: asyncpraw.Reddit):
    subreddit: asyncpraw.models.Subreddit = await reddit.subreddit('+'.join(SUBREDDITS))
    async for comment in subreddit.stream.comments():
        comment: asyncpraw.models.reddit.comment.Comment
        author: asyncpraw.models.reddit.redditor.Redditor = comment.author
        if author.name == REDDIT_USERNAME:
            continue
        formatted_input = f'{comment.body.strip()}'
        parent = await comment.parent()
        await parent.load()
        if parent.author.name == REDDIT_USERNAME and re.match(r'^(?:(?:good|amazing|great) (?:bot|job)|thanks?|thank you|gj)', formatted_input, re.IGNORECASE):
            if getattr(parent, 'body', None) in GOOD_BOT_RESPONSES:
                answer = '👍'
            else:
                answer = random.choice(GOOD_BOT_RESPONSES)
        else:
            answer = await process_input(formatted_input)
        if answer:
            try:
                await comment.reply(answer)
            except asyncprawcore.exceptions.Forbidden:
                pass


async def main():
    reddit = asyncpraw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        username=REDDIT_USERNAME,
        password=os.getenv('REDDIT_PASSWORD'),
        user_agent=f'Commander Spellbook bot for u/{os.getenv('REDDIT_USERNAME')}',
    )
    await asyncio.gather(
        process_submissions(reddit),
        process_comments(reddit),
    )

if __name__ == "__main__":
    asyncio.run(main())
