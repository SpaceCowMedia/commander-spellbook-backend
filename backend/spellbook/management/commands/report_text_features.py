from collections import defaultdict
from dataclasses import dataclass
from django.core.management.base import BaseCommand
from spellbook.models import CardInCombo, Combo, Feature, FeatureNeededInCombo, FeatureOfCard, FeatureProducedInCombo, TemplateInCombo
from spellbook.models.references import TEXT_KEYS, feature_references

LIVE_STATUSES = (Combo.Status.GENERATOR, Combo.Status.UTILITY)


@dataclass(frozen=True)
class TextFeature:
    '''A utility feature that only carries text for a companion: whatever produces it produces the
    companion too, and whatever needs it needs the companion too, so its texts can move into the
    dictionaries of the producers of the companion.'''
    feature: Feature
    companions: list[Feature]
    producers: list[FeatureOfCard | Combo]
    needed_by: list[Combo]


def texts_of(producer: FeatureOfCard | Combo) -> dict[str, object]:
    '''The texts a producer carries: every key of the dictionary of a card feature, the text fields of a combo.'''
    if isinstance(producer, FeatureOfCard):
        return {key: value for key, value in producer.dictionary.items() if value}
    return {key: text for key in TEXT_KEYS if (text := getattr(producer, key))}


def single_card_combos() -> dict[int, int]:
    '''The card of every combo that is a single card needing nothing else, by combo.'''
    cards = defaultdict[int, list[int]](list)
    for combo_id, card_id in CardInCombo.objects.filter(combo__status__in=LIVE_STATUSES).values_list('combo_id', 'card_id'):
        cards[combo_id].append(card_id)
    needing = set(FeatureNeededInCombo.objects.values_list('combo_id', flat=True))
    requiring = set(TemplateInCombo.objects.values_list('combo_id', flat=True))
    return {combo_id: used[0] for combo_id, used in cards.items() if len(used) == 1 and combo_id not in needing and combo_id not in requiring}


def text_features() -> list[TextFeature]:
    single = single_card_combos()
    producing_cards = defaultdict[int, set[int]](set)
    for feature_id, card_id in FeatureOfCard.objects.values_list('feature_id', 'card_id'):
        producing_cards[feature_id].add(card_id)
    produced_otherwise = set[int]()
    for feature_id, combo_id in FeatureProducedInCombo.objects.filter(combo__status__in=LIVE_STATUSES).values_list('feature_id', 'combo_id'):
        if combo_id in single:
            producing_cards[feature_id].add(single[combo_id])
        else:
            produced_otherwise.add(feature_id)
    needed_by = defaultdict[int, set[int]](set)
    for feature_id, combo_id in FeatureNeededInCombo.objects.filter(combo__status__in=LIVE_STATUSES).values_list('feature_id', 'combo_id'):
        needed_by[feature_id].add(combo_id)
    features = Feature.objects.in_bulk()
    result = list[TextFeature]()
    for feature_id, cards in sorted(producing_cards.items()):
        feature = features[feature_id]
        if not feature.is_utility or feature_id in produced_otherwise or not needed_by[feature_id]:
            continue
        companions = [
            features[other]
            for other, other_cards in sorted(producing_cards.items())
            if other != feature_id and cards <= other_cards and needed_by[feature_id] <= needed_by[other]
        ]
        if not companions:
            continue
        producers: list[FeatureOfCard | Combo] = [
            *FeatureOfCard.objects.filter(feature_id=feature_id).select_related('card').order_by('card__name'),
            *Combo.objects.filter(id__in=list(single), produces=feature_id).order_by('id'),
        ]
        # of two features made by the same cards for the same combos, the one carrying text is the companion
        if any(texts_of(producer) for producer in producers):
            result.append(TextFeature(
                feature=feature,
                companions=companions,
                producers=producers,
                needed_by=list(Combo.objects.filter(id__in=needed_by[feature_id]).order_by('id')),
            ))
    return result


class Command(BaseCommand):
    help = 'Reports the utility features that only carry text for a companion feature, which editors can turn into keys of the dictionaries of its producers.'

    def handle(self, *args, **options):
        found = text_features()
        for text_feature in found:
            feature = text_feature.feature
            self.stdout.write(self.style.MIGRATE_HEADING(f'{feature.name} (feature {feature.id}) carries text for {", ".join(f"{companion.name} (feature {companion.id})" for companion in text_feature.companions)}'))
            for producer in text_feature.producers:
                producer_name = producer.card.name if isinstance(producer, FeatureOfCard) else f'combo {producer.id}'
                self.stdout.write(f'  produced by {producer_name}: {texts_of(producer) or "no text"}')
            for combo in text_feature.needed_by:
                texts = [getattr(combo, key) for key in TEXT_KEYS]
                references = sorted({reference[0] for reference in feature_references(texts) if reference['feature'] == feature.name})
                self.stdout.write(f'  needed by combo {combo.id}: {", ".join(references) or "no reference"}')
        self.stdout.write(self.style.SUCCESS(f'{len(found)} feature{"" if len(found) == 1 else "s"} only carrying text.'))
