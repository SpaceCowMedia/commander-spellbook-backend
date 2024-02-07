from django import template
from django.utils.safestring import mark_safe
from spellbook.models.utils import SORTED_COLORS

register = template.Library()


@register.simple_tag
def mana_identities_map():
    return mark_safe('new Map([{}])'
        .format(', '.join('["{}", "{}"]'
            .format(''.join(sorted(identity_set)), identity) for identity_set, identity in SORTED_COLORS.items()))
    )
