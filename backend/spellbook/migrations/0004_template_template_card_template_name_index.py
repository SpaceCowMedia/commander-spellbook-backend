# Generated by Django 4.1 on 2022-10-03 22:04

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0003_card_identity_variant_identity_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='short description of the template in natural language', max_length=255, verbose_name='template name')),
                ('scryfall_query', models.CharField(help_text='Variables supported: mv, manavalue, power, pow, toughness, tou, pt, powtou, loyalty, loyalty, c, color, id, identity, has, t, type, keyword, is, m, mana, devotion, produces. Operators supported: =, !=, <, >, <=, >=, :. You can compose a "and" expression made of "or" expression, like "(c:W or c:U) and (t:creature or t:artifact)". You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature". More info at https://scryfall.com/docs/syntax.', max_length=255, validators=[django.core.validators.RegexValidator(message='Invalid Scryfall query syntax.', regex='^(?:(?:(?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: or (?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*)|\\((?:(?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: or (?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*)\\)(?: (?:and )(?:(?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))|\\((?:(?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy))))(?: or (?:-?(?:(?:(?:c|color|id|identity)(?::|[<>]=?|!=|=)|(?:has|t|type|keyword|is):)(?:[^\\s:<>!=]+|"[^"]")|(?:m|mana|devotion|produces)(?::|[<>]=?|!=|=)(?:\\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|B\\/R|B\\/G|U\\/B|U\\/R|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\})+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)(?::|[<>]=?|!=|=)(?:\\d+|(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)))))*)\\)))*)$')], verbose_name='Scryfall query')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'card template',
                'verbose_name_plural': 'card templates',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='template',
            index=models.Index(fields=['name'], name='card_template_name_index'),
        ),
    ]