import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from django.core.exceptions import ValidationError
from .useragent import FAKE_USERAGENT


def get(url: str, user_agent: str | None = None) -> dict | None:
    req = Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', user_agent or FAKE_USERAGENT)
    try:
        with urlopen(req) as res:
            data = json.load(res)
            return data
    except HTTPError as e:
        if e.code == 404:
            return None
        raise ValidationError('Error response from the website')
    except json.JSONDecodeError:
        ValidationError('Invalid response from the website')
