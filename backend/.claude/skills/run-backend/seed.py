'''A superuser and the smallest data showing the admin's dictionaries: two cards producing a feature
with different keys in their dictionaries, and a combo needing it, whose rows override what it brings.'''
from django.contrib.auth.models import User
from spellbook.models import Card, CardInCombo, Combo, Feature, FeatureNeededInCombo, FeatureOfCard, ZoneLocation

USERNAME = 'agent'
PASSWORD = 'agent-password'


def card(name: str, type_line: str) -> Card:
    found = Card.objects.filter(name=name).first()
    if found is None:
        found = Card.objects.create(name=name, type_line=type_line)
    found.ensure_number()
    return found


def seed() -> None:
    user, _ = User.objects.get_or_create(username=USERNAME, defaults={'email': 'agent@example.com'})
    user.is_staff = user.is_superuser = True
    user.set_password(PASSWORD)
    user.save()
    outlet, _ = Feature.objects.get_or_create(name='Free Sacrifice Outlet', defaults={'status': Feature.Status.PUBLIC_UTILITY})
    loop, _ = Feature.objects.get_or_create(name='Infinite death triggers', defaults={'status': Feature.Status.STANDALONE})
    altar = card('Phyrexian Altar', 'Artifact')
    viscera = card('Viscera Seer', 'Creature - Vampire Wizard')
    FeatureOfCard.objects.update_or_create(card=altar, feature=outlet, defaults={
        'zone_locations': ZoneLocation.BATTLEFIELD,
        'dictionary': {'sac activation': 'Activate Phyrexian Altar by sacrificing', 'mana resolution': ', adding one mana of any color'},
    })
    FeatureOfCard.objects.update_or_create(card=viscera, feature=outlet, defaults={'zone_locations': ZoneLocation.BATTLEFIELD, 'dictionary': {'mana_needed': '{B}'}})
    combo = Combo.objects.filter(description__startswith='[[Free Sacrifice Outlet@sac activation]]').first()
    if combo is None:
        combo = Combo.objects.create(status=Combo.Status.GENERATOR, description='[[Free Sacrifice Outlet@sac activation]] Gravecrawler[[Free Sacrifice Outlet@mana resolution]].\nCast Gravecrawler from your graveyard.\nRepeat.')
        CardInCombo.objects.create(combo=combo, card=card('Gravecrawler', 'Creature - Zombie'), order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        CardInCombo.objects.create(combo=combo, card=card('Rooftop Storm', 'Enchantment'), order=2, zone_locations=ZoneLocation.BATTLEFIELD, dictionary={'name': ''})
        FeatureNeededInCombo.objects.create(combo=combo, feature=outlet, order=1, dictionary={'mana_needed': ''})
        combo.produces.add(loop)
    print(f'superuser {USERNAME} / {PASSWORD}')
    print(f'feature: /admin/spellbook/feature/{outlet.id}/change/')
    print(f'combo: /admin/spellbook/combo/{combo.id}/change/')
