from io import BytesIO
import json

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.profile_backgrounds import background_crop, normalize_background
from tests.test_accounts import ALICE, accounts, sign_in, submit


def test_background_crop_preserves_the_selected_region():
    source = Image.new('RGB', (800, 800), 'red')
    source.paste('blue', (400, 0, 800, 800))
    data = BytesIO()
    source.save(data, format='PNG')
    data.seek(0)
    output = normalize_background(FileStorage(stream=data, filename='banner.png'),
                                  json.dumps({'x': 400, 'y': 100, 'width': 400, 'height': 150}))
    with Image.open(BytesIO(output)) as image:
        assert image.size == (1600, 600)
        red, green, blue = image.getpixel((800, 300))
        assert blue > 240 and red < 10 and green < 10


@pytest.mark.parametrize('raw', ['{}', '[]', 'null', 'bad', 'x' * 513,
    '{"x":0,"y":0,"width":NaN,"height":30}',
    '{"x":-1,"y":0,"width":80,"height":30}',
    '{"x":750,"y":0,"width":80,"height":30}',
    '{"x":0,"y":0,"width":80,"height":80}',
    '{"x":true,"y":0,"width":80,"height":30}'])
def test_background_rejects_invalid_or_out_of_bounds_crops(raw):
    with pytest.raises(ValueError, match='Adjust your background crop'):
        background_crop(raw, 800, 800)


def test_background_without_crop_retains_centered_upload_support():
    assert background_crop(None, 800, 800) is None


def test_profile_save_applies_crop_and_rejects_invalid_crop_atomically(accounts):
    from app.db import get_db
    client = sign_in(accounts, 'alice')
    def upload():
        source = Image.new('RGB', (800, 800), 'red')
        source.paste('blue', (400, 0, 800, 800))
        data = BytesIO()
        source.save(data, format='PNG')
        data.seek(0)
        return data, 'banner.png'
    payload = {'display_name': 'Alice', 'background_controls': 'yes', 'background_key': 'custom',
               'background_crop': json.dumps({'x': 400, 'y': 100, 'width': 400, 'height': 150})}
    assert submit(client, '/settings/profile', {**payload, 'background': upload()}).status_code == 303
    original = client.get('/account/profile/background').data
    with Image.open(BytesIO(original)) as decoded:
        assert decoded.getpixel((800, 300))[2] > 240
    response = submit(client, '/settings/profile', {**payload, 'display_name': 'Rejected',
                                                  'background_crop': '{}', 'background': upload()})
    assert response.status_code == 200
    assert b'Adjust your background crop' in response.data
    assert client.get('/account/profile/background').data == original
    with accounts.app_context():
        assert get_db().execute('SELECT display_name FROM profiles WHERE id = ?', (ALICE,)).fetchone()[0] == 'Alice'
