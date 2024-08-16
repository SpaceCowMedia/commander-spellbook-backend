import os
import asyncpraw
import asyncpraw.models.reddit.redditor
import asyncprawcore
import asyncio
import asyncpraw.models
import asyncpraw.models.reddit
import asyncpraw.models.reddit.comment
import asyncpraw.models.reddit.submission
import asyncpraw.models.reddit.subreddit


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


async def process_input(input: str) -> str | None:
    return input


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
        formatted_input = f'{comment.body}'
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
