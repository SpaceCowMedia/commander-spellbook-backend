from kiota_abstractions.authentication.anonymous_authentication_provider import AnonymousAuthenticationProvider
from kiota_http.httpx_request_adapter import HttpxRequestAdapter
from spellbook_client import SpellbookClient


class AnonymousSpellbookClient(SpellbookClient):
    def __init__(self, base_url: str) -> None:
        anonymous_auth_provider = AnonymousAuthenticationProvider()
        anonymous_request_adapter = HttpxRequestAdapter(anonymous_auth_provider, base_url=base_url)
        super().__init__(request_adapter=anonymous_request_adapter)
