import uuid
from unittest.mock import patch
from django.tasks import TaskResult, TaskResultStatus
from spellbook.models import Card, CardInCombo, CardOracleTag, Combo, OracleTag, ZoneLocation, as_number
from spellbook.tasks import update_cards_task
from spellbook.tasks.scryfall import Scryfall, cards_by_name, expand_taggings, face_field, name_keys, update_cards
from spellbook.tasks.oracle_tags import update_oracle_tags
from .testing import SpellbookTestCaseWithSeeding, curated_card

LEGALITIES = {
    format: 'legal'
    for format in (
        'commander', 'paupercommander', 'paupercommander_c', 'oathbreaker', 'predh', 'standardbrawl',
        'brawl', 'competitivebrawl', 'alchemy', 'vintage', 'legacy', 'premodern', 'modern', 'pioneer',
        'standard', 'pauper', 'future',
    )
}


NO_LEGALITIES = {format: 'not_legal' for format in LEGALITIES}


def bulk_card(name: str, oracle_id: str, **overrides) -> dict:
    '''One card shaped the way the Scryfall bulk data ships it.'''
    return {
        'oracle_id': oracle_id,
        'name': name,
        'released_at': '2020-01-01',
        'reprint': False,
        'color_identity': ['G'],
        'colors': ['G'],
        'type_line': 'Creature — Elf',
        'oracle_text': 'Tap: add G.',
        'keywords': [],
        'cmc': 1.0,
        'mana_cost': '{G}',
        'power': '1',
        'toughness': '1',
        'produced_mana': ['G'],
        'layout': 'normal',
        'reserved': False,
        'game_changer': False,
        'legalities': dict(LEGALITIES),
        'set': 'TST',
        'games': ['paper'],
        'border_color': 'black',
        'rarity': 'common',
        'image_status': 'missing',
    } | overrides


def scryfall_data(*cards: dict, tags: list[dict] | None = None) -> Scryfall:
    tags = tags or []
    return Scryfall(
        cards=cards_by_name(cards),
        tags=tags,
        taggings=expand_taggings(tags),
        tutor=frozenset(),
        mass_land_denial=frozenset(),
        extra_turn=frozenset(),
    )


def bulk_tag(slug: str, tag_id: str, oracle_ids: list[str] = [], parent_ids: list[str] = [], aliases: list[str] = []) -> dict:
    return {
        'id': tag_id,
        'slug': slug,
        'label': slug,
        'description': '',
        'aliases': aliases,
        'parent_ids': parent_ids,
        'child_ids': [],
        'taggings': [{'oracle_id': oracle_id, 'weight': 'median'} for oracle_id in oracle_ids],
    }


class CardSyncTests(SpellbookTestCaseWithSeeding):
    def test_as_number_keeps_only_the_values_a_search_can_compare(self):
        self.assertEqual(as_number('3'), 3)
        self.assertEqual(as_number('0'), 0)
        self.assertEqual(as_number('-1'), -1)
        self.assertIsNone(as_number('*'))
        self.assertIsNone(as_number('1+*'))
        self.assertIsNone(as_number(''))

    def test_face_field_falls_back_to_the_front_face(self):
        transform = bulk_card('Front // Back', 'x', card_faces=[{'mana_cost': '{U}', 'power': '1'}, {'mana_cost': '', 'power': '3'}])
        del transform['mana_cost'], transform['power']
        self.assertEqual(face_field(transform, 'mana_cost'), '{U}')
        self.assertEqual(face_field(transform, 'power'), '1')
        self.assertEqual(face_field(bulk_card('Plain', 'y'), 'mana_cost'), '{G}')
        self.assertEqual(face_field(bulk_card('Plain', 'y'), 'loyalty'), '')

    def test_name_keys_are_compared_one_column_to_one(self):
        self.assertEqual(name_keys('H-H'), ('H-H', 'H-H', 'HH', 'H H'))
        # the same string under two different keys is two different cards, not a clash
        self.assertNotEqual(name_keys('______')[2], name_keys('_____')[2])

    def test_an_oracle_card_the_database_lacks_is_added_uncurated(self):
        new = bulk_card('Brand New Card', str(uuid.uuid4()))
        cards = list(Card.objects.order_by())
        to_save, to_create, _ = update_cards(cards, scryfall_data(new), log=lambda t: None, log_warning=lambda t: None, log_error=lambda t: None)
        self.assertEqual([card.name for card in to_create], ['Brand New Card'])
        created = to_create[0]
        self.assertIsNone(created.number)
        self.assertEqual(created.mana_cost, '{G}')
        self.assertEqual(created.power, '1')
        self.assertEqual(created.produced_mana, 'G')
        # the number a search compares is derived when the card is written, not by the sync
        self.assertIsNone(created.power_value)
        created.save()
        self.assertEqual(created.power_value, 1)
        # every card already in the database lost its oracle id, since this dataset does not hold it
        self.assertEqual(len(to_save), len(cards))

    def test_an_oracle_card_named_as_an_existing_one_is_left_out(self):
        existing = Card.objects.filter(number__isnull=False).first()
        assert existing is not None
        clash = bulk_card(existing.name, str(uuid.uuid4()))
        warnings: list[str] = []
        _, to_create, _ = update_cards(list(Card.objects.order_by()), scryfall_data(clash), log=lambda t: None, log_warning=warnings.append, log_error=lambda t: None)
        self.assertEqual(to_create, [])
        self.assertTrue(any(existing.name in warning for warning in warnings))

    def test_a_spoiled_card_headed_for_standard_is_legal_where_it_is_not_banned(self):
        spoiled = bulk_card(
            'Spoiled Standard Card',
            str(uuid.uuid4()),
            released_at='2999-01-01',
            games=['paper', 'arena'],
            legalities=NO_LEGALITIES | {'future': 'legal', 'competitivebrawl': 'banned'},
        )
        _, to_create, _ = update_cards(list(Card.objects.order_by()), scryfall_data(spoiled), log=lambda t: None, log_warning=lambda t: None, log_error=lambda t: None)
        created = to_create[0]
        self.assertTrue(created.spoiler)
        self.assertTrue(created.legal_standard)
        self.assertTrue(created.legal_alchemy)
        self.assertTrue(created.legal_brawl)
        self.assertTrue(created.legal_standard_brawl)
        self.assertFalse(created.legal_competitive_brawl)


class UnplayableCardTests(SpellbookTestCaseWithSeeding):
    '''Cards printed to be legal in no format at all, such as acorn stamped or silver bordered ones.'''

    def sync(self, *cards: dict) -> tuple[list[Card], list[Card], list[Card]]:
        return update_cards(list(Card.objects.order_by()), scryfall_data(*cards), log=lambda t: None, log_warning=lambda t: None, log_error=lambda t: None)

    def test_a_card_no_format_allows_is_not_added(self):
        for unplayable in (
            bulk_card('Silver Bordered Card', str(uuid.uuid4()), legalities=NO_LEGALITIES, border_color='silver'),
            bulk_card('Acorn Stamped Card', str(uuid.uuid4()), legalities=NO_LEGALITIES, security_stamp='acorn'),
            bulk_card('Playtest Card', str(uuid.uuid4()), legalities=NO_LEGALITIES),
        ):
            _, to_create, _ = self.sync(unplayable)
            self.assertEqual(to_create, [], unplayable['name'])

    def test_a_card_a_format_bans_is_added(self):
        banned = bulk_card('Banned Everywhere', str(uuid.uuid4()), legalities=NO_LEGALITIES | {'commander': 'banned'})
        _, to_create, _ = self.sync(banned)
        self.assertEqual([card.name for card in to_create], ['Banned Everywhere'])

    def test_an_unreleased_card_is_added_unless_its_stamp_or_border_says_otherwise(self):
        # every format calls an unreleased card not legal, so only its stamp and its border tell it apart
        spoiled = bulk_card('Spoiled Card', str(uuid.uuid4()), legalities=NO_LEGALITIES, released_at='2999-01-01')
        _, to_create, _ = self.sync(spoiled)
        self.assertEqual([card.name for card in to_create], ['Spoiled Card'])
        self.assertTrue(to_create[0].spoiler)
        spoiled_acorn = bulk_card('Spoiled Acorn Card', str(uuid.uuid4()), legalities=NO_LEGALITIES, released_at='2999-01-01', security_stamp='acorn')
        _, to_create, _ = self.sync(spoiled_acorn)
        self.assertEqual(to_create, [])

    def test_one_an_earlier_run_added_is_removed(self):
        oracle_id = uuid.uuid4()
        added_before_the_rule = Card.objects.create(name='Acorn Stamped Card', oracle_id=oracle_id, type_line='Creature — Elf')
        self.assertIsNone(added_before_the_rule.number)
        published = bulk_card('Acorn Stamped Card', str(oracle_id), legalities=NO_LEGALITIES, security_stamp='acorn')
        to_save, _, to_delete = self.sync(published)
        self.assertEqual([card.pk for card in to_delete], [added_before_the_rule.pk])
        self.assertNotIn(added_before_the_rule.pk, [card.pk for card in to_save])

    def test_one_an_editor_has_taken_in_keeps_being_updated(self):
        oracle_id = uuid.uuid4()
        acorn = curated_card(name='Acorn Stamped Card', oracle_id=oracle_id, type_line='Creature — Elf')
        published = bulk_card('Acorn Stamped Card', str(oracle_id), legalities=NO_LEGALITIES, security_stamp='acorn', type_line='Creature — Squirrel')
        to_save, to_create, _ = self.sync(published)
        self.assertEqual(to_create, [])
        updated = next(card for card in to_save if card.pk == acorn.pk)
        self.assertEqual(updated.type_line, 'Creature — Squirrel')
        self.assertEqual(updated.oracle_id, oracle_id)


class CardDroppedByScryfallTests(SpellbookTestCaseWithSeeding):
    '''Oracle cards Scryfall stops publishing, as when it retracts one or reissues it under a new oracle id.'''

    def sync(self, *cards: dict) -> tuple[list[Card], list[Card], list[Card]]:
        return update_cards(list(Card.objects.order_by()), scryfall_data(*cards), log=lambda t: None, log_warning=lambda t: None, log_error=lambda t: None)

    def test_one_nobody_curated_is_removed(self):
        dropped = Card.objects.create(name='Dropped Card', oracle_id=uuid.uuid4(), type_line='Creature — Elf')
        to_save, _, to_delete = self.sync()
        self.assertEqual([card.pk for card in to_delete], [dropped.pk])
        self.assertNotIn(dropped.pk, [card.pk for card in to_save])

    def test_one_an_editor_has_taken_in_only_loses_its_oracle_id(self):
        dropped = curated_card(name='Dropped Card', oracle_id=uuid.uuid4(), type_line='Creature — Elf')
        to_save, _, to_delete = self.sync()
        self.assertEqual(to_delete, [])
        unlinked = next(card for card in to_save if card.pk == dropped.pk)
        self.assertIsNone(unlinked.oracle_id)
        self.assertEqual(unlinked.number, dropped.number)

    def test_one_nobody_curated_makes_way_for_its_reissue_in_the_same_run(self):
        dropped = Card.objects.create(name='Reissued Card', oracle_id=uuid.uuid4(), type_line='Creature — Elf')
        reissued = bulk_card('Reissued Card', str(uuid.uuid4()))
        _, to_create, to_delete = self.sync(reissued)
        self.assertEqual([card.pk for card in to_delete], [dropped.pk])
        self.assertEqual([str(card.oracle_id) for card in to_create], [reissued['oracle_id']])

    def test_the_task_writes_both_outcomes(self):
        uncurated = Card.objects.create(name='Dropped Card', oracle_id=uuid.uuid4(), type_line='Creature — Elf')
        CardOracleTag.objects.create(card=uncurated, tag=OracleTag.objects.create(id=uuid.uuid4(), slug='mana-dork'))
        curated = curated_card(name='Dropped Curated Card', oracle_id=uuid.uuid4(), type_line='Creature — Elf')
        with patch('spellbook.tasks.update_cards.scryfall', return_value=scryfall_data()):
            result: TaskResult = update_cards_task.enqueue()
        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        self.assertFalse(Card.objects.filter(pk=uncurated.pk).exists())
        curated.refresh_from_db()
        self.assertIsNone(curated.oracle_id)
        self.assertIsNotNone(curated.number)


class NameSharedByTwoOracleCardsTests(SpellbookTestCaseWithSeeding):
    '''Two oracle cards printed under one name, as a playtest card and the card later named after it.'''

    playtest = bulk_card('Pick Your Poison', str(uuid.uuid4()), released_at='2021-08-20', legalities=NO_LEGALITIES)
    legal = bulk_card('Pick Your Poison', str(uuid.uuid4()), released_at='2024-02-09')

    def test_the_one_a_format_allows_stands_for_the_name(self):
        for bulk in ([self.playtest, self.legal], [self.legal, self.playtest]):
            self.assertEqual(cards_by_name(bulk)['pick your poison']['oracle_id'], self.legal['oracle_id'])

    def test_a_card_with_faces_takes_a_face_name_from_one_no_format_allows(self):
        playtest = bulk_card('Start // Fire', str(uuid.uuid4()), released_at='2021-08-20', legalities=NO_LEGALITIES, card_faces=[{'name': 'Start'}, {'name': 'Fire'}])
        legal = bulk_card('Fire // Ice', str(uuid.uuid4()), released_at='2023-01-13', card_faces=[{'name': 'Fire'}, {'name': 'Ice'}])
        for bulk in ([playtest, legal], [legal, playtest]):
            by_name = cards_by_name(bulk)
            self.assertEqual(by_name['fire']['oracle_id'], legal['oracle_id'])
            self.assertEqual(by_name['start']['oracle_id'], playtest['oracle_id'])

    def test_between_two_a_format_allows_the_first_printed_stands_for_the_name(self):
        first = bulk_card('Ancestral Recall', str(uuid.uuid4()), released_at='2014-06-16')
        faced = bulk_card('Emeritus of Ideation // Ancestral Recall', str(uuid.uuid4()), released_at='2026-04-24', card_faces=[{'name': 'Emeritus of Ideation'}, {'name': 'Ancestral Recall'}])
        later = bulk_card('Ancestral Recall', str(uuid.uuid4()), released_at='2026-04-24')
        for bulk in ([first, faced, later], [later, faced, first]):
            self.assertEqual(cards_by_name(bulk)['ancestral recall']['oracle_id'], first['oracle_id'])

    def test_the_sync_swaps_the_row_holding_the_playtest_card_in_one_run(self):
        held = Card.objects.create(name='Pick Your Poison', oracle_id=uuid.UUID(self.playtest['oracle_id']), type_line='Sorcery')
        _, to_create, to_delete = update_cards(list(Card.objects.order_by()), scryfall_data(self.playtest, self.legal), log=lambda t: None, log_warning=lambda t: None, log_error=lambda t: None)
        self.assertEqual([card.pk for card in to_delete], [held.pk])
        self.assertEqual([str(card.oracle_id) for card in to_create], [self.legal['oracle_id']])
        self.assertTrue(to_create[0].legal_commander)


class OracleTagExpansionTests(SpellbookTestCaseWithSeeding):
    def test_a_tag_carries_the_cards_of_the_tags_below_it(self):
        # removal has no card of its own in the real data either: its whole membership comes from its children
        parent = bulk_tag('removal', 'p')
        child = bulk_tag('removal-creature', 'c', oracle_ids=['card-a'], parent_ids=['p'])
        grandchild = bulk_tag('removal-creature-cheap', 'g', oracle_ids=['card-b'], parent_ids=['c'])
        taggings = expand_taggings([parent, child, grandchild])
        self.assertEqual(taggings['p'], frozenset({'card-a', 'card-b'}))
        self.assertEqual(taggings['c'], frozenset({'card-a', 'card-b'}))
        self.assertEqual(taggings['g'], frozenset({'card-b'}))

    def test_a_cycle_between_tags_terminates(self):
        one = bulk_tag('one', '1', oracle_ids=['card-a'], parent_ids=['2'])
        two = bulk_tag('two', '2', oracle_ids=['card-b'], parent_ids=['1'])
        taggings = expand_taggings([one, two])
        self.assertEqual(taggings['1'], frozenset({'card-a', 'card-b'}))
        self.assertEqual(taggings['2'], frozenset({'card-a', 'card-b'}))


class CardWithoutOracleIdTests(SpellbookTestCaseWithSeeding):
    '''An editor can enter a card Scryfall has not published yet, and the sync adopts it later.'''

    def test_a_card_without_an_oracle_id_can_be_curated_and_used(self):
        spoiled = curated_card(name='Not On Scryfall Yet', type_line='Creature — Human', identity='W')
        self.assertIsNone(spoiled.oracle_id)
        self.assertIsNotNone(spoiled.number)
        # nothing about it is deferred except what Scryfall would have told us
        CardInCombo.objects.create(card=spoiled, combo=Combo.objects.first(), order=99, zone_locations=ZoneLocation.BATTLEFIELD)
        self.assertEqual(spoiled.used_in_combos.count(), 1)

    def test_the_sync_adopts_it_by_name_without_adding_a_second_row(self):
        spoiled = curated_card(name='Not On Scryfall Yet', type_line='Creature — Human', identity='W')
        oracle_id = str(uuid.uuid4())
        published = bulk_card('Not On Scryfall Yet', oracle_id, type_line='Creature — Human')
        to_save, to_create, _ = update_cards(
            list(Card.objects.order_by()),
            scryfall_data(published),
            log=lambda t: None, log_warning=lambda t: None, log_error=lambda t: None,
        )
        self.assertEqual([card.name for card in to_create], [])
        adopted = next(card for card in to_save if card.pk == spoiled.pk)
        self.assertEqual(str(adopted.oracle_id), oracle_id)
        self.assertEqual(adopted.number, spoiled.number)

    def test_its_tags_wait_for_the_oracle_id(self):
        spoiled = curated_card(name='Not On Scryfall Yet', type_line='Creature — Human', identity='W')
        tag = bulk_tag('mana-dork', str(uuid.uuid4()), oracle_ids=[str(uuid.uuid4())])
        update_oracle_tags(scryfall_data(tags=[tag]))
        self.assertEqual(spoiled.oracle_tags.count(), 0)


class DerivedCharacteristicTests(SpellbookTestCaseWithSeeding):
    def test_the_numbers_a_search_compares_follow_what_the_card_prints(self):
        card = curated_card(name='Derived Characteristics', type_line='Creature — Elf', power='2', toughness='3', loyalty='')
        self.assertEqual((card.power_value, card.toughness_value, card.loyalty_value), (2, 3, None))
        card.power = '*'
        card.toughness = '1+*'
        card.save()
        card.refresh_from_db()
        self.assertEqual((card.power_value, card.toughness_value), (None, None))

    def test_they_are_derived_through_a_bulk_write_too(self):
        card = curated_card(name='Bulk Derived Characteristics', type_line='Creature — Elf', power='1', toughness='1')
        card.power = '7'
        Card.objects.bulk_update([card], ['power', 'power_value'])
        card.refresh_from_db()
        self.assertEqual(card.power_value, 7)
