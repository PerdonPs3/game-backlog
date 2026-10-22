"""Optional, user-selected country identity using locally bundled flag assets."""

import json
from pathlib import Path


COUNTRIES = tuple(json.loads(Path(__file__).with_name('data').joinpath('countries.json').read_text(encoding='utf-8')))
COUNTRY_NAMES = {item['code']: item['name'] for item in COUNTRIES}


def clean_country(value):
    code = value.strip().upper()
    if not code:
        return None
    if code not in COUNTRY_NAMES:
        raise ValueError('Choose a country from the list or leave it blank.')
    return code


def country_info(code):
    if code not in COUNTRY_NAMES:
        return None
    return {'code': code, 'name': COUNTRY_NAMES[code], 'flag': 'images/flags/' + code.lower() + '.svg'}
