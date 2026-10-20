"""Decode bounded raster uploads and keep only a small, metadata-free JPEG."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000


def normalize_avatar(upload):
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
                thumbnail = ImageOps.fit(oriented.convert("RGBA"), (256, 256), method=Image.Resampling.LANCZOS)
                # Composite transparency and copy pixels into a fresh image to discard metadata.
                clean = Image.new("RGB", (256, 256), "#ffffff")
                clean.paste(thumbnail, mask=thumbnail.getchannel("A"))
                output = BytesIO()
                clean.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Choose a valid, still JPG, PNG, or WebP photo.") from None
