# Generated by Django 5.1.1 on 2025-01-27 11:23

import django.db.models.deletion
import spellbook.parsers.lark_validator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0038_variant_mana_value_and_hulkline'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='cardusedinvariantsuggestion',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='featureproducedinvariantsuggestion',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='templaterequiredinvariantsuggestion',
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name='template',
            name='scryfall_query',
            field=models.CharField(blank=True, help_text='Variables supported: mv, manavalue, power, pow, toughness, tou, pt, powtou, loyalty, loy, c, color, id, identity, produces, has, t, type, keyword, kw, is, o, oracle, function, otag, oracletag, oracleid, m, mana, devotion.\nOperators supported: =, !=, <, >, <=, >=, :.\nYou can compose a "and"/"or" expression made of "and"/"or" expressions, like "(c:W or c:U) and (t:creature or t:artifact)".\nYou can also omit parentheses when not necessary, like "(c:W or c:U) t:creature".\nCard names are only supported if wrapped in double quotes and preceded by an exclamation mark (!) in order to match the exact name, like !"Lightning Bolt".\nYou can negate any expression by prepending a dash (-), like "-t:creature".\nMore info at: https://scryfall.com/docs/syntax.\n', max_length=1024, null=True, validators=[spellbook.parsers.lark_validator.LarkGrammarValidator('%import common.WS -> _WS\n%import common.SIGNED_INT -> INTEGER\n\n?start : expression\n\n?expression : term | expression OR term\n\n?term : factor | term (AND | _WS) factor\n\n?factor : matcher | LPAREN expression RPAREN\n\n?matcher: NEGATION_OPERATOR? value\n\n?value: "!" LONG_LITERAL | pair\n\npair : COMPARABLE_STRING_VARIABLE COMPARISON_OPERATOR string_value\n    | NUMERIC_VARIABLE COMPARISON_OPERATOR numeric_value\n    | MANA_VARIABLE COMPARISON_OPERATOR mana_value\n    | UNCOMPARABLE_STRING_VARIABLE ":" string_value\n\n?string_value : SHORT_LITERAL | LONG_LITERAL | REGEX_VALUE\n\n?numeric_value : INTEGER | NUMERIC_VARIABLE\n\n?mana_value : INTEGER | mana_expression\n\n?mana_expression : MANA_SYMBOL+\n\nLONG_LITERAL.10 : /"[^"]+"/\n\nOR.9 : " OR " | " or "\n\nAND.9 : " AND " | " and " | " && "\n\nLPAREN.9 : "("\n\nRPAREN.9 : ")"\n\nSHORT_LITERAL.-1 : /[^\\/\\s:<>!="()][^\\s:<>!="()]*/\n\nREGEX_VALUE : /\\/(?:\\\\\\/|[^\\/])+\\//\n\nNEGATION_OPERATOR : "-"\n\n        MANA_SYMBOL.5 : /\\{(?:C\\/[WUBRG]|[WUBRG](?:\\/P)?|[0-9CPXYZS∞]|[1-9][0-9]{1,2}|(?:2\\/[WUBRG]|W\\/U|W\\/B|U\\/B|U\\/R|B\\/R|B\\/G|R\\/G|R\\/W|G\\/W|G\\/U)(?:\\/P)?)\\}/\n        COMPARISON_OPERATOR : "=" | "!=" | "<" | ">" | "<=" | ">=" | ":"\n        NUMERIC_VARIABLE.4 : "mv" | "manavalue" | "power" | "pow" | "toughness" | "tou" | "pt" | "powtou" | "loyalty" | "loy"\n        MANA_VARIABLE.3 : "m" | "mana" | "devotion"\n        COMPARABLE_STRING_VARIABLE.2 : "c" | "color" | "id" | "identity" | "produces"\n        UNCOMPARABLE_STRING_VARIABLE.1 : "has" | "t" | "type" | "keyword" | "kw" | "is" | "o" | "oracle" | "function" | "otag" | "oracletag" | "oracleid"\n    ')], verbose_name='Scryfall query'),
        ),
        migrations.CreateModel(
            name='TemplateReplacement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spellbook.card')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='spellbook.template')),
            ],
            options={
                'unique_together': {('card', 'template')},
            },
        ),
        migrations.AddField(
            model_name='template',
            name='replacements',
            field=models.ManyToManyField(blank=True, help_text='Cards that are valid replacements of this template', related_name='replaces', through='spellbook.TemplateReplacement', to='spellbook.card', verbose_name='replacements for template'),
        ),
    ]
