from ..abstract_command import AbstractCommand
from spellbook.models import VariantSuggestion, Variant, VariantUpdateSuggestion
from social_django.models import UserSocialAuth
from common.markdown_utils import escape_markdown


class Command(AbstractCommand):
    name = 'notify'
    help = 'Notifies that something happened'
    variant_suggestion_accepted = 'variant_suggestion_accepted'
    variant_suggestion_rejected = 'variant_suggestion_rejected'
    variant_update_suggestion_accepted = 'variant_update_suggestion_accepted'
    variant_update_suggestion_rejected = 'variant_update_suggestion_rejected'
    variant_published = 'variant_published'
    variant_updated = 'variant_updated'
    events = [
        variant_suggestion_accepted,
        variant_suggestion_rejected,
        variant_update_suggestion_accepted,
        variant_update_suggestion_rejected,
        variant_published,
        variant_updated,
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

    def variant_suggestion_event(self, accepted: bool, identifiers: list[str]):
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
                past_tense = 'accepted' if accepted else 'rejected'
                if discord_account:
                    webhook_text += f'<@{discord_account.uid}>, your suggestion for {suggestion_name} has been **{past_tense}**'
                else:
                    webhook_text += f'The suggestion from {escape_markdown(author.username)} for {suggestion_name} has been **{past_tense}**'
                if variant_suggestion.notes:
                    webhook_text += f', with the following note: _{escape_markdown(variant_suggestion.notes)}_'
                else:
                    webhook_text += '.'
                webhook_text += '\n'
                if accepted:
                    webhook_text += 'When an editor implements it, links to the combo\'s variants will be posted to this changelog.\n'
                if discord_account:
                    webhook_text += f'Thanks for your submission{'' if accepted else ' though'}!\n'
        if webhook_text:
            self.discord_webhook(webhook_text)

    def variant_update_suggestion_event(self, accepted: bool, identifiers: list[str]):
        webhook_text = ''
        for identifier in identifiers:
            variant_update_suggestion = VariantUpdateSuggestion.objects.get(pk=identifier)
            author = variant_update_suggestion.suggested_by
            if author:
                discord_account = UserSocialAuth.objects.filter(
                    user=author,
                    provider='discord',
                ).first()
                variants_count = variant_update_suggestion.variants.count()
                match variants_count:
                    case 0:
                        suggestion_name = 'no particular variant'
                    case 1:
                        variant: Variant = Variant.objects.filter(variant_update_suggestions__suggestion=variant_update_suggestion).first()  # type: ignore
                        suggestion_name = f'variant [{variant.id}](<{variant.spellbook_link(raw=True)}>)'
                    case _ if variants_count <= 3:
                        variants = list[str](f'[{variant.id}](<{variant.spellbook_link(raw=True)}>)' for variant in Variant.objects.filter(variant_update_suggestions__suggestion=variant_update_suggestion))
                        suggestion_name = f'variants {', '.join(variants[:-1])} and {variants[-1]}'
                    case _:
                        suggestion_name = f'{variants_count} variants'
                past_tense = 'accepted' if accepted else 'rejected'
                if discord_account:
                    webhook_text += f'<@{discord_account.uid}>, your update suggestion #{variant_update_suggestion.id} for {suggestion_name} has been **{past_tense}**'
                else:
                    webhook_text += f'The update suggestion #{variant_update_suggestion.id} from {escape_markdown(author.username)} for {suggestion_name} has been **{past_tense}**'
                if variant_update_suggestion.notes:
                    webhook_text += f', with the following note: _{escape_markdown(variant_update_suggestion.notes)}_'
                else:
                    webhook_text += '.'
                webhook_text += '\n'
                if accepted:
                    webhook_text += 'When an editor implements it, links to the updated variants will be posted to this changelog.\n'
                if discord_account:
                    webhook_text += f'Thanks for your submission{'' if accepted else ' though'}!\n'
        if webhook_text:
            self.discord_webhook(webhook_text)

    def run(self, *args, **options):
        self.log(f'Notifying about {options['event']} with identifiers {options['identifiers']}')
        match options['event']:
            case self.variant_suggestion_accepted:
                self.variant_suggestion_event(accepted=True, identifiers=options['identifiers'])
            case self.variant_suggestion_rejected:
                self.variant_suggestion_event(accepted=False, identifiers=options['identifiers'])
            case self.variant_update_suggestion_accepted:
                self.variant_update_suggestion_event(accepted=True, identifiers=options['identifiers'])
            case self.variant_update_suggestion_rejected:
                self.variant_update_suggestion_event(accepted=False, identifiers=options['identifiers'])
            case self.variant_published | self.variant_updated:
                plural = 's' if len(options['identifiers']) > 1 else ''
                verb = 'have' if len(options['identifiers']) > 1 else 'has'
                webhook_text = f'The following combo{plural} {verb} been ' + ('added to the site' if options['event'] == self.variant_published else 'updated') + ':\n'
                variants: list[Variant] = list(Variant.objects.filter(pk__in=options['identifiers']))
                if variants:
                    for variant in variants:
                        text = f'[{variant.name}](<{variant.spellbook_link(raw=True)}>)'
                        if variant.spoiler:
                            text = f'||{text}||'
                        webhook_text += text + '\n'
                    self.discord_webhook(webhook_text)
                else:
                    self.log('No variants found', self.style.ERROR)
