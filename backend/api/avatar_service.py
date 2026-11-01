"""
Profile photos: any phone or camera photo in, a 256x256 JPEG of about 20 KB out.

Re-encoding also drops the photo's metadata (EXIF), which on phones often includes the GPS
position where the picture was taken.
"""
import io

from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000  # refuse "decompression bomb" images before decoding them fully
SIZE = 256
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class AvatarError(ValueError):
    pass


def process_avatar(upload) -> bytes:
    """Validate an uploaded image and return it as a square JPEG."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise AvatarError("The photo is too large. Use one under 5 MB.")
    try:
        with Image.open(upload) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise AvatarError("Use a JPEG, PNG or WebP photo.")
            if probe.width * probe.height > MAX_PIXELS:
                raise AvatarError("The photo has too many pixels.")
            probe.verify()  # detects truncated or corrupt files
        upload.seek(0)
        with Image.open(upload) as image:
            image = ImageOps.exif_transpose(image)  # phone photos taken sideways
            square = ImageOps.fit(image.convert("RGB"), (SIZE, SIZE), Image.Resampling.LANCZOS)
    # OSError also covers UnidentifiedImageError (not an image) and truncated files
    except (OSError, Image.DecompressionBombError) as exc:
        raise AvatarError("That file isn't a photo we can read.") from exc

    out = io.BytesIO()
    square.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()
