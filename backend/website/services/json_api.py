import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError


FAKE_USERAGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'


def get(url: str) -> dict | None:
    req = Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', FAKE_USERAGENT)
    try:
        with urlopen(req) as res:
            data = json.load(res)
            return data
    except HTTPError:
        return None
