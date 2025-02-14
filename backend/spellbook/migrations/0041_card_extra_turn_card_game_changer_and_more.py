# Generated by Django 5.1.1 on 2025-02-14 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0040_remove_variant_spellbook_v_popular_50a711_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='card',
            name='extra_turn',
            field=models.BooleanField(default=False, help_text='Whether this card grants an extra turn', verbose_name='extra turn card'),
        ),
        migrations.AddField(
            model_name='card',
            name='game_changer',
            field=models.BooleanField(default=False, help_text='Whether this card is in the official Game Changer card list', verbose_name='game changer card'),
        ),
        migrations.AddField(
            model_name='card',
            name='mass_land_destruction',
            field=models.BooleanField(default=False, help_text='Whether this card can destroy multiple lands', verbose_name='mass land destruction card'),
        ),
        migrations.AddField(
            model_name='card',
            name='tutor',
            field=models.BooleanField(default=False, help_text='Whether this card can tutor for other cards', verbose_name='tutor card'),
        ),
        migrations.AddField(
            model_name='feature',
            name='relevant',
            field=models.BooleanField(default=False, help_text='Is this a relevant feature? Relevant features are enough to make the combo complete.', verbose_name='is relevant'),
        ),
        migrations.AddField(
            model_name='variant',
            name='bracket',
            field=models.PositiveSmallIntegerField(default=4, editable=False, help_text='Suggested bracket for this variant'),
        ),
        migrations.AddField(
            model_name='variant',
            name='complete',
            field=models.BooleanField(default=False, editable=False, help_text='Whether the variant is complete'),
        ),
        migrations.AddIndex(
            model_name='variant',
            index=models.Index(fields=['complete'], name='spellbook_v_complet_634bae_idx'),
        ),
        migrations.AddConstraint(
            model_name='feature',
            constraint=models.CheckConstraint(condition=models.Q(('relevant', True), ('utility', True), _negated=True), name='relevant_feature_not_utility', violation_error_message='Relevant features cannot be utility features.'),
        ),
    ]
