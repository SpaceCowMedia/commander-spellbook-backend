from ..abstract_command import AbstractCommand
from django.conf import settings
from discord_webhook import DiscordWebhook
from spellbook.models import VariantSuggestion, Variant
from social_django.models import UserSocialAuth


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
            webhook = DiscordWebhook(url=settings.DISCORD_WEBHOOK_URL, content=content)
            webhook.execute()
            self.log('Webhook sent', self.style.SUCCESS)
        else:
            self.log('No Discord Webhook set in settings', self.style.ERROR)

    def variant_suggestion_event(self, past_tense: str, identifiers: list[str]):
        webhook_text = ''
        for identifier in identifiers:
            vs = VariantSuggestion.objects.get(pk=identifier)
            author = vs.suggested_by
            if author:
                discord_account = UserSocialAuth.objects.filter(
                    user=author,
                    provider='discord',
                ).first()
                suggestion_name = f'`{vs.name}`'
                if vs.spoiler:
                    suggestion_name = f'||{suggestion_name}||'
                if discord_account:
                    webhook_text += f'<@{discord_account.uid}>, your suggestion for {suggestion_name} has been {past_tense}'
                else:
                    webhook_text += f'The suggestion from {author.username} for {suggestion_name} has been {past_tense}'
                if vs.notes:
                    webhook_text += f', with the following note: {vs.notes}'
                else:
                    webhook_text += '.'
                webhook_text += '\n'
        if webhook_text:
            self.discord_webhook(webhook_text)

    def run(self, *args, **options):
        self.log(f'Notifying about {options["event"]} with identifiers {options["identifiers"]}')
        match options['event']:
            case self.variant_suggestion_accepted:
                self.variant_suggestion_event('**accepted**', options['identifiers'])
            case self.variant_suggestion_rejected:
                self.variant_suggestion_event('rejected', options['identifiers'])
            case self.variant_published:
                plural = 's' if len(options['identifiers']) > 1 else ''
                verb = 'have' if len(options['identifiers']) > 1 else 'has'
                webhook_text = f'The following combo{plural} {verb} been added to the site:\n'
                for identifier in options['identifiers']:
                    v = Variant.objects.filter(pk=identifier).first()
                    if v:
                        webhook_text += f'[{v.name}](<{v.spellbook_link(raw=True)}>)\n'
                self.discord_webhook(webhook_text)
