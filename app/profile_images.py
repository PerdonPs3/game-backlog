"""Decode bounded raster uploads and keep only a small, metadata-free JPEG."""

from io import BytesIO
import json
import math
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000


def crop_box(raw, width, height):
    try:
        if len(raw) > 512:
            raise ValueError
        values = json.loads(raw)
        if not isinstance(values, dict) or set(values) != {"x", "y", "size"}:
            raise ValueError
        x, y, size = (values[key] for key in ("x", "y", "size"))
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (x, y, size)):
            raise ValueError
        if x < 0 or y < 0 or size < 1 or x + size > width + 0.001 or y + size > height + 0.001:
            raise ValueError
        return x, y, min(width, x + size), min(height, y + size)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Choose a crop inside the photo and try again.") from None


def normalize_avatar(upload, crop=None):
    data = upload.stream.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Choose a photo smaller than 2 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as source:
                if source.width * source.height > MAX_IMAGE_PIXELS or getattr(source, "n_frames", 1) != 1:
                    raise ValueError("Use a still photo with no more than 12 million pixels.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                if crop:
                    selected = oriented.convert("RGBA").crop(crop_box(crop, *oriented.size))
                    thumbnail = selected.resize((256, 256), resample=Image.Resampling.LANCZOS)
                else:
                    thumbnail = ImageOps.fit(oriented.convert("RGBA"), (256, 256), method=Image.Resampling.LANCZOS)
                # Composite transparency and copy pixels into a fresh image to discard metadata.
                clean = Image.new("RGB", (256, 256), "#ffffff")
                clean.paste(thumbnail, mask=thumbnail.getchannel("A"))
                output = BytesIO()
                clean.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Choose a valid, still JPG, PNG, or WebP photo.") from None
