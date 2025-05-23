# Generated by Django 5.1.1 on 2025-05-22 23:35

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0045_add_variant_update_suggestions'),
    ]

    operations = [
        migrations.RenameField(
            model_name='combo',
            old_name='notes',
            new_name='comment',
        ),
        migrations.RenameField(
            model_name='combo',
            old_name='public_notes',
            new_name='notes',
        ),
        migrations.RenameField(
            model_name='variant',
            old_name='notes',
            new_name='comment',
        ),
        migrations.RenameField(
            model_name='variant',
            old_name='public_notes',
            new_name='notes',
        ),
        migrations.AddField(
            model_name='variantupdatesuggestion',
            name='notes',
            field=models.TextField(blank=True, help_text='Notes written by editors', validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?|CHAOS|PW|TK|[WUBRG](?:\\/P)?|[1-9][0-9]{1,2}|H[WUBRG]|[0-9CPXYZSTQEA½∞])\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')]),
        ),
    ]
