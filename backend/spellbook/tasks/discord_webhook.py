import logging
from django.conf import settings
from discord_webhook import DiscordWebhook
from text_utils import discord_chunk


logger = logging.getLogger(__name__)


def discord_webhook(content: str):
    logger.info('Sending Discord webhook post...')
    if settings.DISCORD_WEBHOOK_URL:
        messages = discord_chunk(content)
        for message in messages:
            webhook = DiscordWebhook(url=settings.DISCORD_WEBHOOK_URL, content=message)
            response = webhook.execute()
            if response.ok:
                logger.info('Webhook sent')
            else:
                logger.error(f'Webhook failed with status code {response.status_code}:\n{response.content.decode()}')
                raise Exception('Webhook failed')
    else:
        logger.error('No Discord Webhook set in settings')
