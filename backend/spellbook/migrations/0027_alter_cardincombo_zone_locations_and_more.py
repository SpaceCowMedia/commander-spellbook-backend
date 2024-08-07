# Generated by Django 5.0.6 on 2024-07-06 10:43

import spellbook.models.ingredient
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0026_add_feature_attributes_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cardincombo',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
        migrations.AlterField(
            model_name='cardinvariant',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
        migrations.AlterField(
            model_name='cardusedinvariantsuggestion',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
        migrations.AlterField(
            model_name='featureofcard',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
        migrations.AlterField(
            model_name='templateincombo',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
        migrations.AlterField(
            model_name='templateinvariant',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
        migrations.AlterField(
            model_name='templaterequiredinvariantsuggestion',
            name='zone_locations',
            field=spellbook.models.ingredient.ZoneLocationsField(help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location'),
        ),
    ]
