import csv
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from django.core.exceptions import ValidationError
from .useragent import FAKE_USERAGENT


def get(url: str) -> list[dict[str, object]] | None:
    req = Request(url)
    req.add_header('Accept', 'text/csv')
    req.add_header('User-Agent', FAKE_USERAGENT)
    try:
        with urlopen(req) as res:
            data = list(csv.reader(res.read().decode('utf-8').splitlines()))
            header = data[0]
            return [dict(zip(header, row, strict=True)) for row in data[1:]]
    except HTTPError as e:
        if e.code == 404:
            return None
        raise ValidationError('Error response from the website')
    except (csv.Error, ValueError, IndexError):
        raise ValidationError('Invalid response from the website')
