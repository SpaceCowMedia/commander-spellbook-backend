from django.contrib.auth.models import User
from django.test import TestCase
from backend.login.discord import set_default_permissions


class DefaultPermissionsTests(TestCase):
    salt_vote_permissions = ['spellbook.add_saltvote', 'spellbook.change_saltvote', 'spellbook.delete_saltvote', 'spellbook.view_saltvote']

    def test_new_users_can_vote_salt(self):
        user = User.objects.create(username='new')
        set_default_permissions(user=user, is_new=True)
        self.assertTrue(User.objects.get(pk=user.pk).has_perms(self.salt_vote_permissions))

    def test_returning_users_keep_their_permissions(self):
        user = User.objects.create(username='returning')
        set_default_permissions(user=user, is_new=False)
        self.assertFalse(User.objects.get(pk=user.pk).has_perm('spellbook.add_saltvote'))
