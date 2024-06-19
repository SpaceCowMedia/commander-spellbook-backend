from django.db import migrations
from spellbook.models.recipe import Recipe


def populate_name_field(apps, schema_editor):
    Variant = apps.get_model('spellbook', 'Variant')
    Combo = apps.get_model('spellbook', 'Combo')
    VariantSuggestion = apps.get_model('spellbook', 'VariantSuggestion')
    objs = list(Variant.objects.all().only('id', 'name').prefetch_related(
        'cardinvariant_set',
        'templateinvariant_set',
        'featureproducedbyvariant_set',
        'cardinvariant_set__card',
        'templateinvariant_set__template',
        'featureproducedbyvariant_set__feature',
    ))
    for obj in objs:
        obj.name = Recipe.compute_name(
            cards={c.card.name: c.quantity for c in obj.cardinvariant_set.all()},
            templates={t.template.name: t.quantity for t in obj.templateinvariant_set.all()},
            features_needed={},
            features_produced={f.feature.name: f.quantity for f in obj.featureproducedbyvariant_set.all()},
        )
        obj.pre_save = lambda: None
    Variant.objects.bulk_update(objs, ['name'])
    objs = list(Combo.objects.all().only('id', 'name').prefetch_related(
        'cardincombo_set',
        'templateincombo_set',
        'featureneededincombo_set',
        'featureproducedincombo_set',
        'cardincombo_set__card',
        'templateincombo_set__template',
        'featureneededincombo_set__feature',
        'featureproducedincombo_set__feature',
    ))
    for obj in objs:
        obj.name = Recipe.compute_name(
            cards={c.card.name: c.quantity for c in obj.cardincombo_set.all()},
            templates={t.template.name: t.quantity for t in obj.templateincombo_set.all()},
            features_needed={f.feature.name: f.quantity for f in obj.featureneededincombo_set.all()},
            features_produced={f.feature.name: 1 for f in obj.featureproducedincombo_set.all()},
        )
        obj.pre_save = lambda: None
    Combo.objects.bulk_update(objs, ['name'])
    objs = list(VariantSuggestion.objects.all().only('id', 'name').prefetch_related(
        'uses',
        'requires',
        'produces',
    ))
    for obj in objs:
        obj.name = Recipe.compute_name(
            cards={c.card: c.quantity for c in obj.uses.all()},
            templates={t.template: t.quantity for t in obj.requires.all()},
            features_needed={},
            features_produced={f.feature: 1 for f in obj.produces.all()},
        )
        obj.pre_save = lambda: None
    VariantSuggestion.objects.bulk_update(objs, ['name'])


class PopulateNameField(migrations.RunPython):
    def __init__(self) -> None:
        super().__init__(code=populate_name_field, reverse_code=migrations.RunPython.noop)
