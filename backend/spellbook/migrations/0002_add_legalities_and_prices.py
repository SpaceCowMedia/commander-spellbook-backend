# Generated by Django 4.2.5 on 2023-11-10 16:20

from decimal import Decimal
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='card',
            name='legal',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='legal',
        ),
        migrations.AddField(
            model_name='card',
            name='legal_brawl',
            field=models.BooleanField(default=True, help_text='Is this card legal in Brawl?', verbose_name='is legal in Brawl'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_commander',
            field=models.BooleanField(default=True, help_text='Is this card legal in Commander?', verbose_name='is legal in Commander'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_legacy',
            field=models.BooleanField(default=True, help_text='Is this card legal in Legacy?', verbose_name='is legal in Legacy'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_modern',
            field=models.BooleanField(default=True, help_text='Is this card legal in Modern?', verbose_name='is legal in Modern'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_oathbreaker',
            field=models.BooleanField(default=True, help_text='Is this card legal in Oathbreaker?', verbose_name='is legal in Oathbreaker'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_pauper',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pauper?', verbose_name='is legal in Pauper'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_pauper_commander_commander',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pauper Commander as commander?', verbose_name='is legal in Pauper Commander as commander'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_pauper_commander_main',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pauper Commander main deck?', verbose_name='is legal in Pauper Commander main deck'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_pioneer',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pioneer?', verbose_name='is legal in Pioneer'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_predh',
            field=models.BooleanField(default=True, help_text='Is this card legal in PreDH Commander?', verbose_name='is legal in Pre-Modern Commander'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_standard',
            field=models.BooleanField(default=True, help_text='Is this card legal in Standard?', verbose_name='is legal in Standard'),
        ),
        migrations.AddField(
            model_name='card',
            name='legal_vintage',
            field=models.BooleanField(default=True, help_text='Is this card legal in Vintage?', verbose_name='is legal in Vintage'),
        ),
        migrations.AddField(
            model_name='card',
            name='oracle_text',
            field=models.TextField(blank=True, default='', help_text='Card oracle text', verbose_name='oracle text of card'),
        ),
        migrations.AddField(
            model_name='card',
            name='price_cardkingdom',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Card price on Card Kingdom', max_digits=10, verbose_name='Card Kingdom price (USD)'),
        ),
        migrations.AddField(
            model_name='card',
            name='price_cardmarket',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Card price on Cardmarket', max_digits=10, verbose_name='Cardmarket price (EUR)'),
        ),
        migrations.AddField(
            model_name='card',
            name='price_tcgplayer',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Card price on TCGPlayer', max_digits=10, verbose_name='TCGPlayer price (USD)'),
        ),
        migrations.AddField(
            model_name='card',
            name='type_line',
            field=models.CharField(blank=True, default='', help_text='Card type line', max_length=255, verbose_name='type line of card'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_brawl',
            field=models.BooleanField(default=True, help_text='Is this card legal in Brawl?', verbose_name='is legal in Brawl'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_commander',
            field=models.BooleanField(default=True, help_text='Is this card legal in Commander?', verbose_name='is legal in Commander'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_legacy',
            field=models.BooleanField(default=True, help_text='Is this card legal in Legacy?', verbose_name='is legal in Legacy'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_modern',
            field=models.BooleanField(default=True, help_text='Is this card legal in Modern?', verbose_name='is legal in Modern'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_oathbreaker',
            field=models.BooleanField(default=True, help_text='Is this card legal in Oathbreaker?', verbose_name='is legal in Oathbreaker'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_pauper',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pauper?', verbose_name='is legal in Pauper'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_pauper_commander_commander',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pauper Commander as commander?', verbose_name='is legal in Pauper Commander as commander'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_pauper_commander_main',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pauper Commander main deck?', verbose_name='is legal in Pauper Commander main deck'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_pioneer',
            field=models.BooleanField(default=True, help_text='Is this card legal in Pioneer?', verbose_name='is legal in Pioneer'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_predh',
            field=models.BooleanField(default=True, help_text='Is this card legal in PreDH Commander?', verbose_name='is legal in Pre-Modern Commander'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_standard',
            field=models.BooleanField(default=True, help_text='Is this card legal in Standard?', verbose_name='is legal in Standard'),
        ),
        migrations.AddField(
            model_name='variant',
            name='legal_vintage',
            field=models.BooleanField(default=True, help_text='Is this card legal in Vintage?', verbose_name='is legal in Vintage'),
        ),
        migrations.AddField(
            model_name='variant',
            name='price_cardkingdom',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Card price on Card Kingdom', max_digits=10, verbose_name='Card Kingdom price (USD)'),
        ),
        migrations.AddField(
            model_name='variant',
            name='price_cardmarket',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Card price on Cardmarket', max_digits=10, verbose_name='Cardmarket price (EUR)'),
        ),
        migrations.AddField(
            model_name='variant',
            name='price_tcgplayer',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), help_text='Card price on TCGPlayer', max_digits=10, verbose_name='TCGPlayer price (USD)'),
        ),
        migrations.AddField(
            model_name='variantsuggestion',
            name='notes',
            field=models.TextField(blank=True, default='', help_text='Notes written by editors', validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')]),
        ),
    ]
