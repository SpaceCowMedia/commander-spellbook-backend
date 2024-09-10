import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .useragent import FAKE_USERAGENT


def get(url: str) -> dict | None:
    req = Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', FAKE_USERAGENT)
    try:
        with urlopen(req) as res:
            data = json.load(res)
            return data
    except (HTTPError, json.JSONDecodeError):
        return None
