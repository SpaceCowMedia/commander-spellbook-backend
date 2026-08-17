from django.apps import apps
from django.test import TestCase
from spellbook.migrations._utils import face_name_candidates, normalized_name, read_used_face, used_face_from_card_states
from spellbook.models import Card, CardInCombo, Combo, Feature, FeatureOfCard, ZoneLocation

BIRGI = ('Birgi, God of Storytelling // Harnfel, Horn of Bounty', 'Legendary Creature - God // Legendary Artifact')
ESIKA = ('Esika, God of the Tree // The Prismatic Bridge', 'Legendary Creature - God // Legendary Enchantment')
HELIOD = ('Heliod, the Radiant Dawn // Heliod, the Warped Eclipse', 'Legendary Creature - God // Legendary Creature - God')
KURUK = ('The Legend of Kuruk // Avatar Kuruk', 'Enchantment - Saga // Legendary Creature - Avatar')
MIMIC = ('Mirrorhall Mimic // Ghastly Mimicry', 'Creature - Shapeshifter // Enchantment - Aura')
WEREWOLF = ('Scorned Villager // Moonscarred Werewolf', 'Creature - Human Werewolf // Creature - Werewolf')


class FaceNameCandidatesTests(TestCase):
    def test_candidates_of_a_legendary_creature_include_the_short_form(self):
        self.assertEqual(face_name_candidates(*BIRGI), {
            'Birgi, God of Storytelling': {1},
            'Birgi': {1},
            'Harnfel, Horn of Bounty': {2},
        })

    def test_a_short_form_shared_by_both_faces_is_ambiguous(self):
        self.assertEqual(face_name_candidates(*HELIOD)['Heliod'], {1, 2})

    def test_a_face_that_is_not_a_legendary_creature_has_no_short_form(self):
        self.assertEqual(set(face_name_candidates(*ESIKA)), {'Esika, God of the Tree', 'Esika', 'The Prismatic Bridge'})

    def test_candidates_agree_with_the_card_model(self):
        for name, type_line in (BIRGI, ESIKA, HELIOD, KURUK, MIMIC, WEREWOLF):
            with self.subTest(name=name):
                card = Card(name=name, type_line=type_line)
                candidates = face_name_candidates(name, type_line)
                for face in range(1, name.count(' // ') + 2):
                    self.assertIn(card.face_name(face), candidates)
                    self.assertIn(card.face_name(face, short=True), candidates)


class NormalizedNameTests(TestCase):
    def test_articles_case_and_punctuation_are_dropped(self):
        self.assertEqual(normalized_name('Heliod, the Warped Eclipse'), normalized_name('Heliod, Warped Eclipse'))
        self.assertEqual(normalized_name('The Prismatic Bridge'), 'prismatic bridge')

    def test_different_names_stay_different(self):
        self.assertNotEqual(normalized_name('Heliod, the Radiant Dawn'), normalized_name('Heliod, the Warped Eclipse'))


class ReadUsedFaceTests(TestCase):
    def read(self, card: tuple[str, str], card_state: str, zone_wording: str = 'on the battlefield'):
        return read_used_face(*card, zone_wording, card_state)

    def test_a_state_that_is_only_a_specifier_is_emptied(self):
        conversion = self.read(BIRGI, 'as Birgi')
        assert conversion is not None
        self.assertEqual((conversion.used_face, conversion.card_state, conversion.problem), (1, '', ''))

    def test_a_trailing_period_is_taken_along(self):
        conversion = self.read(ESIKA, 'as The Prismatic Bridge.')
        assert conversion is not None
        self.assertEqual((conversion.used_face, conversion.card_state), (2, ''))

    def test_the_zone_wording_the_field_already_carries_is_dropped(self):
        conversion = self.read(WEREWOLF, 'on the battlefield as Moonscarred Werewolf and without summoning sickness')
        assert conversion is not None
        self.assertEqual((conversion.used_face, conversion.card_state), (2, 'without summoning sickness'))

    def test_what_the_state_says_besides_the_specifier_is_kept(self):
        conversion = self.read(MIMIC, 'as Ghastly Mimicry attached to CREATURE')
        assert conversion is not None
        self.assertEqual((conversion.used_face, conversion.card_state), (2, 'attached to CREATURE'))

    def test_a_specifier_repeated_by_merging_states_is_taken_out_of_every_copy(self):
        conversion = self.read(KURUK, 'as Avatar Kuruk as Avatar Kuruk')
        assert conversion is not None
        self.assertEqual((conversion.used_face, conversion.card_state, conversion.problem), (2, '', ''))

    def test_a_shared_short_form_is_resolved_by_the_longest_phrase_naming_one_face(self):
        '''Both faces are called Heliod, and this state misspells the second one by dropping its article.'''
        conversion = self.read(HELIOD, 'as Heliod, Warped Eclipse')
        assert conversion is not None
        self.assertEqual((conversion.used_face, conversion.card_state, conversion.problem), (2, '', ''))

    def test_a_shared_short_form_naming_no_face_is_reported(self):
        conversion = self.read(HELIOD, 'as Heliod, Something Else')
        assert conversion is not None
        self.assertEqual(conversion.used_face, 0)
        self.assertIn('names more than one face', conversion.problem)

    def test_specifiers_disagreeing_on_the_face_are_reported(self):
        conversion = self.read(BIRGI, 'as Birgi and as Harnfel, Horn of Bounty')
        assert conversion is not None
        self.assertEqual(conversion.used_face, 0)
        self.assertIn('names more than one face', conversion.problem)

    def test_a_state_naming_another_card_is_left_alone(self):
        self.assertIsNone(self.read(MIMIC, 'as a copy of Cavalier of Night'))

    def test_a_state_without_a_specifier_is_left_alone(self):
        self.assertIsNone(self.read(BIRGI, 'without summoning sickness'))

    def test_a_face_name_not_introduced_by_as_is_left_alone(self):
        self.assertIsNone(self.read(BIRGI, 'sacrificed to Birgi'))


class UsedFaceFromCardStatesTests(TestCase):
    '''The migration itself, over the models carrying a used face.'''

    def setUp(self):
        super().setUp()
        self.card = Card.objects.create(name=BIRGI[0], type_line=BIRGI[1], faces=2)
        self.single_faced_card = Card.objects.create(name='Single Faced Card', type_line='Creature - Elf')
        self.combo = Combo.objects.create(status=Combo.Status.GENERATOR)
        self.feature = Feature.objects.create(name='UFF')

    def test_the_specifier_moves_into_the_used_face_of_every_model_carrying_one(self):
        card_in_combo = CardInCombo.objects.create(combo=self.combo, card=self.card, order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='as Harnfel, Horn of Bounty')
        feature_of_card = FeatureOfCard.objects.create(card=self.card, feature=self.feature, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='on the battlefield as Birgi and without summoning sickness')

        used_face_from_card_states(apps, None)

        card_in_combo.refresh_from_db()
        self.assertEqual((card_in_combo.used_face, card_in_combo.battlefield_card_state), (2, ''))
        feature_of_card.refresh_from_db()
        self.assertEqual((feature_of_card.used_face, feature_of_card.battlefield_card_state), (1, 'without summoning sickness'))

    def test_the_states_of_a_single_faced_card_are_left_alone(self):
        card_in_combo = CardInCombo.objects.create(combo=self.combo, card=self.single_faced_card, order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='as a copy of Birgi')

        used_face_from_card_states(apps, None)

        card_in_combo.refresh_from_db()
        self.assertEqual((card_in_combo.used_face, card_in_combo.battlefield_card_state), (None, 'as a copy of Birgi'))

    def test_a_row_already_using_another_face_is_left_alone(self):
        card_in_combo = CardInCombo.objects.create(combo=self.combo, card=self.card, order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='as Birgi', used_face=2)

        used_face_from_card_states(apps, None)

        card_in_combo.refresh_from_db()
        self.assertEqual((card_in_combo.used_face, card_in_combo.battlefield_card_state), (2, 'as Birgi'))

    def test_only_the_state_of_the_zone_it_belongs_to_is_read(self):
        card_in_combo = CardInCombo.objects.create(
            combo=self.combo,
            card=self.card,
            order=1,
            zone_locations=ZoneLocation.BATTLEFIELD + ZoneLocation.GRAVEYARD,
            battlefield_card_state='as Birgi',
            graveyard_card_state='milled',
        )

        used_face_from_card_states(apps, None)

        card_in_combo.refresh_from_db()
        self.assertEqual((card_in_combo.used_face, card_in_combo.battlefield_card_state, card_in_combo.graveyard_card_state), (1, '', 'milled'))
