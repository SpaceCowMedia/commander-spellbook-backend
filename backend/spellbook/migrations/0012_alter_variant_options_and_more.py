# Generated by Django 5.0.1 on 2024-01-17 14:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0011_featureneededincombo_alter_combo_needs'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='variant',
            options={'ordering': [models.Case(models.When(status='D', then=models.Value(0)), models.When(status='N', then=models.Value(1)), models.When(status='OK', then=models.Value(2)), models.When(status='E', then=models.Value(3)), models.When(status='R', then=models.Value(4)), models.When(status='NW', then=models.Value(5)), default=models.Value(10)), '-created'], 'verbose_name': 'variant', 'verbose_name_plural': 'variants'},
        ),
        migrations.AlterModelOptions(
            name='variantsuggestion',
            options={'ordering': [models.Case(models.When(status='N', then=models.Value(0)), models.When(status='A', then=models.Value(1)), models.When(status='R', then=models.Value(2)), default=models.Value(10)), '-created'], 'verbose_name': 'variant suggestion', 'verbose_name_plural': 'variant suggestions'},
        ),
        migrations.AlterField(
            model_name='variantalias',
            name='variant',
            field=models.ForeignKey(blank=True, help_text='Variant this alias redirects to', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aliases', to='spellbook.variant', verbose_name='redirects to'),
        ),
    ]
