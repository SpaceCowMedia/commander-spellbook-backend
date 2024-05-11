from ..abstract_command import AbstractCommand
from django.conf import settings
from discord_webhook import DiscordWebhook
from spellbook.models import VariantSuggestion, Variant
from social_django.models import UserSocialAuth
from common.markdown import escape_markdown


DISCORD_MESSAGE_LIMIT = 2000


class Command(AbstractCommand):
    name = 'notify'
    help = 'Notifies that something happened'
    variant_suggestion_accepted = 'variant_suggestion_accepted'
    variant_suggestion_rejected = 'variant_suggestion_rejected'
    variant_published = 'variant_published'
    events = [
        variant_suggestion_accepted,
        variant_suggestion_rejected,
        variant_published,
    ]

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            'event',
            help='Event name',
            choices=self.events,
        )
        parser.add_argument(
            'identifiers',
            help='Identifier of the object',
            nargs='+',
        )

    def discord_webhook(self, content: str):
        if settings.DISCORD_WEBHOOK_URL:
            messages = []
            while content:
                next_block = content[:DISCORD_MESSAGE_LIMIT]
                if len(content) > DISCORD_MESSAGE_LIMIT and '\n' in next_block:
                    split = next_block.rindex('\n')
                elif len(content) > DISCORD_MESSAGE_LIMIT and ' ' in next_block:
                    split = next_block.rindex(' ')
                else:
                    split = DISCORD_MESSAGE_LIMIT
                messages.append(content[:split])
                content = content[split + 1:]
            for message in messages:
                webhook = DiscordWebhook(url=settings.DISCORD_WEBHOOK_URL, content=message)
                response = webhook.execute()
                if response.ok:
                    self.log('Webhook sent', self.style.SUCCESS)
                else:
                    self.log(f'Webhook failed with status code {response.status_code}:\n{response.content.decode()}', self.style.ERROR)
                    raise Exception('Webhook failed')
        else:
            self.log('No Discord Webhook set in settings', self.style.ERROR)

    def variant_suggestion_event(self, past_tense: str, identifiers: list[str]):
        webhook_text = ''
        for identifier in identifiers:
            variant_suggestion = VariantSuggestion.objects.get(pk=identifier)
            author = variant_suggestion.suggested_by
            if author:
                discord_account = UserSocialAuth.objects.filter(
                    user=author,
                    provider='discord',
                ).first()
                suggestion_name = f'`{escape_markdown(variant_suggestion.name)}`'
                if variant_suggestion.spoiler:
                    suggestion_name = f'||{suggestion_name}||'
                if discord_account:
                    webhook_text += f'<@{discord_account.uid}>, your suggestion for {suggestion_name} has been **{past_tense}**'
                else:
                    webhook_text += f'The suggestion from {escape_markdown(author.username)} for {suggestion_name} has been **{past_tense}**'
                if variant_suggestion.notes:
                    webhook_text += f', with the following note: _{escape_markdown(variant_suggestion.notes)}_'
                else:
                    webhook_text += '.'
                webhook_text += '\n'
        if webhook_text:
            self.discord_webhook(webhook_text)

    def run(self, *args, **options):
        self.log(f'Notifying about {options["event"]} with identifiers {options["identifiers"]}')
        match options['event']:
            case self.variant_suggestion_accepted:
                self.variant_suggestion_event('accepted', options['identifiers'])
            case self.variant_suggestion_rejected:
                self.variant_suggestion_event('rejected', options['identifiers'])
            case self.variant_published:
                plural = 's' if len(options['identifiers']) > 1 else ''
                verb = 'have' if len(options['identifiers']) > 1 else 'has'
                webhook_text = f'The following combo{plural} {verb} been added to the site:\n'
                variants: list[Variant] = list(Variant.objects.filter(pk__in=options['identifiers']))
                if variants:
                    for variant in variants:
                        webhook_text += f'[{variant.name}](<{variant.spellbook_link(raw=True)}>)\n'
                    self.discord_webhook(webhook_text)
                else:
                    self.log('No variants found', self.style.ERROR)
