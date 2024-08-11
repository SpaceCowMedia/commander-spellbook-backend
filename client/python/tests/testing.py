from django.test import LiveServerTestCase
from kiota_abstractions.authentication.anonymous_authentication_provider import AnonymousAuthenticationProvider
from kiota_http.httpx_request_adapter import HttpxRequestAdapter
from ..spellbook_client import SpellbookClient
from spellbook.tests.testing import TestCaseMixinWithSeeding


class SpellbookClientTest(TestCaseMixinWithSeeding, LiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.anonymous_auth_provider = AnonymousAuthenticationProvider()
        self.anonymous_request_adapter = HttpxRequestAdapter(self.anonymous_auth_provider, base_url=self.live_server_url)
        self.spellbook_client_anonymous = SpellbookClient(self.anonymous_request_adapter)
