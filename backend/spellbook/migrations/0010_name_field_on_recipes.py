# Generated by Django 5.0.1 on 2024-01-14 16:35

import django.db.models.manager
from django.db import migrations, models
from ._utils import PopulateNameField


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0009_preserialized_variants_and_gin_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='combo',
            name='name',
            field=models.CharField(default='N/A', editable=False, max_length=3835),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='variant',
            name='name',
            field=models.CharField(default='N/A', editable=False, max_length=3835),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='variantsuggestion',
            name='name',
            field=models.CharField(default='N/A', editable=False, max_length=3835),
            preserve_default=False,
        ),
        PopulateNameField(),
        migrations.AlterModelManagers(
            name='variant',
            managers=[
                ('recipes_prefetched', django.db.models.manager.Manager()),
            ],
        ),
    ]
