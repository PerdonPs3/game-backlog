from io import BytesIO

from PIL import Image
import pytest
from werkzeug.datastructures import FileStorage

from app.profile_images import normalize_avatar


def image_file(format="PNG", size=(400, 200)):
    stream = BytesIO()
    image = Image.new("RGB", size, "purple")
    exif = Image.Exif()
    exif[270] = "Private metadata"
    image.save(stream, format=format, exif=exif)
    stream.seek(0)
    return FileStorage(stream=stream, filename="photo.png")


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_avatar_is_normalized_and_metadata_removed(format):
    output = normalize_avatar(image_file(format))
    with Image.open(BytesIO(output)) as image:
        assert image.format == "JPEG" and image.size == (256, 256)
        assert not image.getexif()
        assert "Private metadata".encode() not in output
        assert len(output) < 102400


@pytest.mark.parametrize("data", [b"<svg></svg>", b"not a photo", b"", b"x" * (2 * 1024 * 1024 + 1)], ids=["svg", "text", "empty", "oversized"])
def test_invalid_or_oversized_photo_is_rejected(data):
    with pytest.raises(ValueError):
        normalize_avatar(FileStorage(stream=BytesIO(data), filename="fake.jpg", content_type="image/jpeg"))


def test_animated_photo_is_rejected():
    stream = BytesIO()
    Image.new("RGB", (10, 10), "red").save(stream, format="PNG", save_all=True,
                                         append_images=[Image.new("RGB", (10, 10), "blue")])
    stream.seek(0)
    with pytest.raises(ValueError, match="still photo"):
        normalize_avatar(FileStorage(stream=stream, filename="animated.png"))


def test_excessive_pixel_count_is_rejected_before_decoding():
    with pytest.raises(ValueError, match="12 million"):
        normalize_avatar(image_file(size=(4000, 3001)))


@pytest.mark.parametrize("crop", ['{}', '{"x":-1,"y":0,"size":100}', '{"x":0,"y":0,"size":0}', '{"x":300,"y":0,"size":200}', '{"x":0,"y":0,"size":NaN}', '{"x":true,"y":0,"size":100}', '[' * 600])
def test_invalid_crop_cannot_escape_photo_bounds(crop):
    with pytest.raises(ValueError, match="crop inside"):
        normalize_avatar(image_file(), crop)


def test_selected_crop_and_exif_orientation_are_applied_before_resizing():
    image = Image.new("RGB", (400, 200), "red")
    image.paste(Image.new("RGB", (200, 200), "blue"), (200, 0))
    exif = Image.Exif()
    exif[274] = 6
    data = BytesIO()
    image.save(data, format="JPEG", exif=exif)
    data.seek(0)
    output = normalize_avatar(FileStorage(stream=data, filename="rotated.jpg"), '{"x":0,"y":200,"size":200}')
    with Image.open(BytesIO(output)) as result:
        r, g, b = result.getpixel((128, 128))
        assert b > 230 and r < 20 and g < 20
        assert result.size == (256, 256) and not result.getexif()
