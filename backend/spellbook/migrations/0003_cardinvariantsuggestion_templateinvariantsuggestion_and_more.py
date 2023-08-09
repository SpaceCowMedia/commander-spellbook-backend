# Generated by Django 4.2.4 on 2023-08-09 18:44

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import sortedm2m.fields
import spellbook.models.mixins


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('spellbook', '0002_alter_cardincombo_battlefield_card_state_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CardInVariantSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(help_text='Order of the card in the combo.', verbose_name='order')),
                ('zone_locations', models.CharField(default='H', help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location')),
                ('battlefield_card_state', models.CharField(blank=True, default='', help_text='State of the card on the battlefield, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='battlefield starting card state')),
                ('exile_card_state', models.CharField(blank=True, default='', help_text='State of the card in exile, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='exile starting card state')),
                ('library_card_state', models.CharField(blank=True, default='', help_text='State of the card in the library, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='library starting card state')),
                ('graveyard_card_state', models.CharField(blank=True, default='', help_text='State of the card in the graveyard, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='graveyard starting card state')),
                ('must_be_commander', models.BooleanField(default=False, help_text='Does the card have to be a commander?', verbose_name='must be commander')),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spellbook.card')),
            ],
            options={
                'ordering': ['order', 'id'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TemplateInVariantSuggestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(help_text='Order of the card in the combo.', verbose_name='order')),
                ('zone_locations', models.CharField(default='H', help_text='Starting location(s) for the card.', max_length=6, verbose_name='starting location')),
                ('battlefield_card_state', models.CharField(blank=True, default='', help_text='State of the card on the battlefield, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='battlefield starting card state')),
                ('exile_card_state', models.CharField(blank=True, default='', help_text='State of the card in exile, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='exile starting card state')),
                ('library_card_state', models.CharField(blank=True, default='', help_text='State of the card in the library, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='library starting card state')),
                ('graveyard_card_state', models.CharField(blank=True, default='', help_text='State of the card in the graveyard, if present.', max_length=200, validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')], verbose_name='graveyard starting card state')),
                ('must_be_commander', models.BooleanField(default=False, help_text='Does the card have to be a commander?', verbose_name='must be commander')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spellbook.template')),
            ],
            options={
                'ordering': ['order', 'id'],
                'abstract': False,
            },
        ),
        migrations.AlterField(
            model_name='variant',
            name='legal',
            field=models.BooleanField(editable=False, help_text='Is this variant legal in Commander?', verbose_name='is legal'),
        ),
        migrations.AlterField(
            model_name='variant',
            name='spoiler',
            field=models.BooleanField(editable=False, help_text='Is this variant a spoiler?', verbose_name='is spoiler'),
        ),
        migrations.CreateModel(
            name='VariantSuggestion',
            fields=[
                ('id', models.CharField(editable=False, help_text='Unique ID for this variant suggestion', max_length=128, primary_key=True, serialize=False, unique=True)),
                ('status', models.CharField(choices=[('N', 'New'), ('A', 'Accepted'), ('R', 'Rejected')], default='N', help_text='Suggestion status for editors', max_length=2)),
                ('mana_needed', models.CharField(blank=True, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', max_length=200, validators=[django.core.validators.RegexValidator(message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.', regex='^(?:(?:\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|U\\/B|U\\/R|B\\/R|B\\/G|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})[^\\{\\}\\[\\]]*)*$')])),
                ('other_prerequisites', models.TextField(blank=True, default='', help_text='Other prerequisites for this variant.', validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')])),
                ('description', models.TextField(blank=True, help_text='Long description, in steps', validators=[django.core.validators.RegexValidator(message='Unpaired double square brackets are not allowed.', regex='^(?:[^\\[]*(?:\\[(?!\\[)|\\[{2}[^\\[]+\\]{2}|\\[{3,}))*[^\\[]*$'), django.core.validators.RegexValidator(message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.', regex='^(?:[^\\{]*\\{(?:[WUBRG](?:\\/P)?|[0-9CPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})*[^\\{]*$'), django.core.validators.RegexValidator(message='Only ordinary characters are allowed.', regex='^[\\x0A\\x0D\\x20-\\x7E\\x80\\x95\\x99\\xA1\\xA9\\xAE\\xB0\\xB1-\\xB3\\xBC-\\xFF]*$')])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('identity', models.CharField(editable=False, help_text='Mana identity', max_length=5, validators=[django.core.validators.RegexValidator(message='Can be any combination of one or more letters in [W,U,B,R,G], in order, otherwise C for colorless.', regex='^(?:W?U?B?R?G?|C)$'), django.core.validators.MinLengthValidator(1)], verbose_name='mana identity')),
                ('legal', models.BooleanField(help_text='Is this variant legal in Commander?', verbose_name='is legal')),
                ('spoiler', models.BooleanField(help_text='Is this variant a spoiler?', verbose_name='is spoiler')),
                ('produces', sortedm2m.fields.SortedManyToManyField(help_text='Features that this variant produces', related_name='produced_by_variant_suggestions', to='spellbook.feature')),
                ('requires', models.ManyToManyField(blank=True, help_text='Templates that this variant requires', related_name='required_by_variant_suggestions', through='spellbook.TemplateInVariantSuggestion', to='spellbook.template', verbose_name='required templates')),
                ('suggested_by', models.ForeignKey(blank=True, editable=False, help_text='User that suggested this variant', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants', to=settings.AUTH_USER_MODEL)),
                ('uses', models.ManyToManyField(help_text='Cards that this variant uses', related_name='used_in_variant_suggestions', through='spellbook.CardInVariantSuggestion', to='spellbook.card')),
            ],
            options={
                'verbose_name': 'variant suggestion',
                'verbose_name_plural': 'variant suggestions',
                'ordering': ['-status', '-created'],
            },
            bases=(models.Model, spellbook.models.mixins.ScryfallLinkMixin),
        ),
        migrations.AddField(
            model_name='templateinvariantsuggestion',
            name='variant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spellbook.variantsuggestion'),
        ),
        migrations.AddField(
            model_name='cardinvariantsuggestion',
            name='variant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spellbook.variantsuggestion'),
        ),
        migrations.AddIndex(
            model_name='variantsuggestion',
            index=models.Index(fields=['id'], name='unique_suggestion_index'),
        ),
        migrations.AlterUniqueTogether(
            name='templateinvariantsuggestion',
            unique_together={('template', 'variant')},
        ),
        migrations.AlterUniqueTogether(
            name='cardinvariantsuggestion',
            unique_together={('card', 'variant')},
        ),
    ]
