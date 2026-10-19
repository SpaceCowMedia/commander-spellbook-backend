'''A stand-in for the backend: a local HTTP server answering with canned JSON responses.'''
import logging
from dataclasses import dataclass
from typing import Any
from aiohttp import web
from aiohttp.test_utils import TestServer


# asyncio debug mode, on in async test cases, logs every server start
logging.getLogger('asyncio').setLevel(logging.WARNING)


@dataclass
class ReceivedRequest:
    method: str
    path: str
    query: dict[str, str]
    body: str


class FakeBackend:
    '''Answers each request with the response registered for its method and path, or with a 404.'''

    def __init__(self):
        self.responses: dict[tuple[str, str], tuple[int, Any]] = {}
        self.requests: list[ReceivedRequest] = []
        application = web.Application()
        application.router.add_route('*', '/{path:.*}', self.handle)
        self.server = TestServer(application)

    @property
    def url(self) -> str:
        return str(self.server.make_url('')).rstrip('/')

    def respond(self, method: str, path: str, body: Any, status: int = 200):
        self.responses[method.upper(), path] = (status, body)

    async def handle(self, request: web.Request) -> web.Response:
        self.requests.append(ReceivedRequest(request.method, request.path, dict(request.query), await request.text()))
        status, body = self.responses.get((request.method, request.path), (404, {'detail': 'Not found.'}))
        return web.json_response(body, status=status)

    async def __aenter__(self):
        await self.server.start_server(access_log=None)
        return self

    async def __aexit__(self, *exc_info):
        await self.server.close()
