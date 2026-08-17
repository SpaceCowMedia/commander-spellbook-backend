from django.db import migrations
from ._utils import used_face_from_card_states


class Migration(migrations.Migration):

    dependencies = [
        ('spellbook', '0068_cardincombo_in_text_substitutions_and_more'),
    ]

    operations = [
        migrations.RunPython(used_face_from_card_states, migrations.RunPython.noop),
    ]
