"""Bounded, metadata-free profile banners with visibility checked per request."""

from io import BytesIO
import json
import math
import warnings

from flask import Blueprint, Response, abort, current_app, g
from PIL import Image, ImageOps, UnidentifiedImageError

from app.achievements import normal_owner
from app.db import get_db


backgrounds = Blueprint('backgrounds', __name__)
PRESETS = (('castle', 'Castle'), ('aurora', 'Aurora'), ('obsidian', 'Obsidian'))


def background_crop(raw, width, height):
    if not raw:
        return None
    try:
        if len(raw) > 512:
            raise ValueError()
        crop = json.loads(raw)
        x, y, w, h = (crop[key] for key in ('x', 'y', 'width', 'height'))
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (x, y, w, h)):
            raise ValueError()
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width + .01 or y + h > height + .01:
            raise ValueError()
        if abs(w / h - 1600 / 600) > .01:
            raise ValueError()
        return x, y, min(width, x + w), min(height, y + h)
    except (ValueError, TypeError, KeyError):
        raise ValueError('Adjust your background crop again before saving.') from None


def normalize_background(upload, crop=None):
    data = upload.stream.read(2 * 1024 * 1024 + 1)
    if not data or len(data) > 2 * 1024 * 1024:
        raise ValueError('Choose a background smaller than 2 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=('JPEG', 'PNG', 'WEBP')) as source:
                if source.width * source.height > 12_000_000 or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('Use a still background with no more than 12 million pixels.')
                source.load()
                oriented = ImageOps.exif_transpose(source).convert('RGBA')
                box = background_crop(crop, oriented.width, oriented.height)
                if box:
                    oriented = oriented.crop(box)
                banner = ImageOps.fit(oriented, (1600, 600), method=Image.Resampling.LANCZOS)
                clean = Image.new('RGB', banner.size, '#182126')
                clean.paste(banner, mask=banner.getchannel('A'))
                output = BytesIO()
                clean.save(output, format='JPEG', quality=85, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Choose a valid, still JPG, PNG, or WebP background.') from None


def validate_background(form, files, profile):
    if form.get('background_controls') != 'yes':
        return None
    key = form.get('background_key', 'castle')
    if key not in {p[0] for p in PRESETS} | {'custom'}:
        raise ValueError('Choose an available profile background.')
    upload = files.get('background')
    remove = form.get('remove_background') == 'yes'
    image = normalize_background(upload, form.get('background_crop')) if upload and upload.filename and not remove else None
    if image is not None:
        key = 'custom'
    if remove and key == 'custom':
        key = 'castle'
    if key == 'custom' and image is None and not profile['has_background']:
        raise ValueError('Upload an image before choosing Custom.')
    shared = form.get('hide_background') != 'yes' if form.get('profile_privacy_controls') == 'yes' else form.get('share_background') == 'yes'
    return key, image, remove, shared


def save_background(db, owner, selection):
    if selection is None:
        return
    key, image, remove, share = selection
    db.execute('UPDATE profiles SET background_key = ?, share_background = ?, background_image = CASE WHEN ? THEN ? ELSE background_image END WHERE id = ?',
               (key, share, image is not None or remove, image, owner))


def image_response(image):
    if image is None:
        abort(404)
    response = Response(bytes(image), mimetype='image/jpeg')
    response.headers.update({'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                             'X-Robots-Tag': 'noindex, nofollow', 'Referrer-Policy': 'no-referrer'})
    return response


@backgrounds.get('/account/profile/background')
def own_image():
    if not normal_owner():
        abort(404)
    return image_response(get_db().execute('SELECT background_image FROM profiles WHERE id = ?', (g.user['id'],)).fetchone()[0])


@backgrounds.get('/players/<username>/background')
def public_image(username):
    if not current_app.config.get('AUTH_ENABLED'):
        abort(404)
    row = get_db().execute("SELECT background_image FROM profiles WHERE username = ? AND is_public = TRUE AND share_background = TRUE AND background_key = 'custom'", (username,)).fetchone()
    return image_response(row[0] if row else None)
