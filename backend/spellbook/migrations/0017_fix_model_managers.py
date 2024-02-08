# Generated by Django 5.0.1 on 2024-02-08 10:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0016_alter_card_identity_alter_variant_identity'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='card',
            options={'default_manager_name': 'objects', 'ordering': ['name'], 'verbose_name': 'card', 'verbose_name_plural': 'cards'},
        ),
        migrations.AlterModelOptions(
            name='combo',
            options={'default_manager_name': 'objects', 'ordering': ['created'], 'verbose_name': 'combo', 'verbose_name_plural': 'combos'},
        ),
        migrations.AlterModelOptions(
            name='feature',
            options={'default_manager_name': 'objects', 'ordering': ['name'], 'verbose_name': 'feature', 'verbose_name_plural': 'features'},
        ),
        migrations.AlterModelOptions(
            name='job',
            options={'default_manager_name': 'objects', 'ordering': ['-created', 'name'], 'verbose_name': 'job', 'verbose_name_plural': 'jobs'},
        ),
        migrations.AlterModelOptions(
            name='template',
            options={'default_manager_name': 'objects', 'ordering': ['name'], 'verbose_name': 'card template', 'verbose_name_plural': 'templates'},
        ),
        migrations.AlterModelOptions(
            name='variant',
            options={'default_manager_name': 'objects', 'ordering': [models.Case(models.When(status='D', then=models.Value(0)), models.When(status='N', then=models.Value(1)), models.When(status='OK', then=models.Value(2)), models.When(status='E', then=models.Value(3)), models.When(status='R', then=models.Value(4)), models.When(status='NW', then=models.Value(5)), default=models.Value(10)), '-created'], 'verbose_name': 'variant', 'verbose_name_plural': 'variants'},
        ),
        migrations.AlterModelOptions(
            name='variantalias',
            options={'default_manager_name': 'objects', 'verbose_name': 'variant alias', 'verbose_name_plural': 'variant aliases'},
        ),
        migrations.AlterModelOptions(
            name='variantsuggestion',
            options={'default_manager_name': 'objects', 'ordering': [models.Case(models.When(status='NR', then=models.Value(0)), models.When(status='N', then=models.Value(1)), models.When(status='A', then=models.Value(2)), models.When(status='R', then=models.Value(3)), default=models.Value(10)), '-created'], 'verbose_name': 'variant suggestion', 'verbose_name_plural': 'variant suggestions'},
        ),
    ]
