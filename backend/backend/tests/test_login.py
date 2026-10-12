from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from social_core.exceptions import AuthProviderError

from backend.login.discord import is_member_of_guild, set_default_permissions


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


class DiscordGuildMembershipTests(TestCase):
    @patch('backend.login.discord.requests.get')
    def test_discord_api_errors_raise_auth_provider_error(self, get):
        get.return_value.status_code = 503

        with self.assertRaises(AuthProviderError) as context:
            is_member_of_guild(
                backend=SimpleNamespace(name='discord', HOSTNAME='discord.com'),
                details={},
                response={'access_token': 'access-token'},
                uid='discord-user',
                user=None,
            )

        self.assertEqual(context.exception.code, 'unavailable')
        self.assertEqual(context.exception.status_code, 503)
