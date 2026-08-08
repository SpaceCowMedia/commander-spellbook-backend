from website.models import FEATURED_TABS_COUNT
from .base import QueryValue, Explanation, Predicate, BE, PRODUCE, REQUIRE, USE, ValidationError

FEATURED_TABS_TAGS = [f'featured-{i}' for i in range(1, FEATURED_TABS_COUNT + 1)]


def tag_explanation(qv: QueryValue) -> Explanation:
    if qv.operator != ':':
        raise ValidationError(f'Operator {qv.operator} is not supported for tag search.')
    match qv.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            return Predicate(USE, 'a card that has only been previewed so far')
        case 'commander':
            return Predicate(REQUIRE, 'a specific commander')
        case 'reserved':
            return Predicate(USE, 'a card on the Reserved List')
        case 'mandatory':
            return Predicate(PRODUCE, 'a mandatory loop')
        case 'lock':
            return Predicate(PRODUCE, 'a lock')
        case 'mld' | 'masslanddestruction' | 'masslanddenial' | 'masslandremoval':
            return Predicate(PRODUCE, 'mass land destruction')
        case 'infinite':
            return Predicate(PRODUCE, 'an infinite loop')
        case 'risky' | 'allin':
            return Predicate(BE, 'risky to go for')
        case 'winning' | 'gamewinning' | 'win':
            return Predicate(PRODUCE, 'a way to win the game on the spot')
        case 'featured':
            return Predicate(BE, 'featured on the home page')
        case tag if tag in FEATURED_TABS_TAGS:
            return Predicate(BE, f'featured in home page tab {FEATURED_TABS_TAGS.index(tag) + 1}')
        case 'example':
            return Predicate(BE, 'an example combo')
        case 'hulkline' | 'meatandeggs' | 'hulktutorable':
            return Predicate(BE, 'tutorable with Protean Hulk')
        case 'complete':
            return Predicate(PRODUCE, 'a standalone effect')
        case _:
            raise ValidationError(f'Value "{qv.value}" is not supported for tag search.')
