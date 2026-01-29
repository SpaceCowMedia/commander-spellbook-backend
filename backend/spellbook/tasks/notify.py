import logging
from django.tasks import task
from spellbook.models import VariantSuggestion, Variant, VariantUpdateSuggestion
from social_django.models import UserSocialAuth
from common.markdown_utils import escape_markdown
from .discord_webhook import discord_webhook


logger = logging.getLogger(__name__)


def variant_suggestion_event(accepted: bool, identifiers: list[str]):
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
        discord_webhook(webhook_text)


def variant_update_suggestion_event(accepted: bool, identifiers: list[str]):
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
        discord_webhook(webhook_text)


@task(priority=10)
def notify_task(event: str, identifiers: list[str]):
    logger.info(f'Notifying about {event} with identifiers {identifiers}')
    match event:
        case EventNotification.variant_suggestion_accepted:
            variant_suggestion_event(accepted=True, identifiers=identifiers)
        case EventNotification.variant_suggestion_rejected:
            variant_suggestion_event(accepted=False, identifiers=identifiers)
        case EventNotification.variant_update_suggestion_accepted:
            variant_update_suggestion_event(accepted=True, identifiers=identifiers)
        case EventNotification.variant_update_suggestion_rejected:
            variant_update_suggestion_event(accepted=False, identifiers=identifiers)
        case EventNotification.variant_published | EventNotification.variant_updated:
            plural = 's' if len(identifiers) > 1 else ''
            verb = 'have' if len(identifiers) > 1 else 'has'
            webhook_text = f'The following combo{plural} {verb} been ' + ('added to the site' if event == EventNotification.variant_published else 'updated') + ':\n'
            variants: list[Variant] = list(Variant.objects.filter(pk__in=identifiers))
            if variants:
                for variant in variants:
                    text = f'[{variant.name}](<{variant.spellbook_link(raw=True)}>)'
                    if variant.spoiler:
                        text = f'||{text}||'
                    webhook_text += text + '\n'
                discord_webhook(webhook_text)
            else:
                logger.error('No variants found')


class EventNotification:
    variant_suggestion_accepted = 'variant_suggestion_accepted'
    variant_suggestion_rejected = 'variant_suggestion_rejected'
    variant_update_suggestion_accepted = 'variant_update_suggestion_accepted'
    variant_update_suggestion_rejected = 'variant_update_suggestion_rejected'
    variant_published = 'variant_published'
    variant_updated = 'variant_updated'
