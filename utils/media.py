"""Photo pipeline: validate, re-encode and store listing photos.

Every upload is verified with Pillow (extension *and* real bytes), capped at
``PHOTO_MAX_MB``, then re-encoded twice:

* ``<id>.jpg``       - large copy, max ``PHOTO_LARGE_PX`` (detail page/lightbox)
* ``<id>_thumb.jpg`` - thumbnail, max ``PHOTO_THUMB_PX`` (grids and thumbnails)

EXIF is dropped by re-encoding (also fixes phone-camera rotation via
``ImageOps.exif_transpose``). The storage backend is chosen by
``MEDIA_BACKEND``:

* ``local``      - files under ``MEDIA_FOLDER`` (served from /static/media)
* ``s3``         - boto3, bucket from ``S3_*`` settings
* ``cloudinary`` - the ``cloudinary`` SDK, credentials from ``CLOUDINARY_URL``
  (or the separate ``CLOUDINARY_*`` values)

Only the ``local`` backend is required for development; the cloud backends
raise a clear configuration error until their settings and SDK are present.
"""
from __future__ import annotations

import io
import os
import uuid

from flask import current_app, has_app_context
from PIL import Image, ImageOps

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_DESCRIPTION = "JPG, PNG or WebP"


class MediaError(ValueError):
    """A user-facing photo problem (wrong type, too big, corrupt file)."""


def _cfg(key, default=None):
    if has_app_context():
        value = current_app.config.get(key)
        if value is not None:
            return value
    import config
    return getattr(config, key, default)


def max_photo_bytes() -> int:
    return int(_cfg("PHOTO_MAX_MB", 5)) * 1024 * 1024


def max_photos() -> int:
    return int(_cfg("PHOTO_MAX_PER_ITEM", 6))


# ---------------------------------------------------------------------------
# Validation + re-encoding
# ---------------------------------------------------------------------------
def _open_image(data: bytes) -> Image.Image:
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()                      # cheap structural check
    except Exception as exc:                # noqa: BLE001 - any decode failure
        raise MediaError("That file is not a valid image.") from exc
    image = Image.open(io.BytesIO(data))
    if (image.format or "").upper() not in ALLOWED_FORMATS:
        raise MediaError(f"Please upload a {ALLOWED_DESCRIPTION} image.")
    return image


def _flatten(image: Image.Image) -> Image.Image:
    """EXIF-correct rotation and a white backdrop for transparent images."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        canvas = Image.new("RGB", image.size, "white")
        canvas.paste(image, mask=image.split()[-1])
        return canvas
    return image.convert("RGB")


def _encode(image: Image.Image, max_px: int, quality: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    copy.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def build_images(file) -> dict:
    """Validate one uploaded file and return encoded large + thumbnail bytes."""
    filename = str(getattr(file, "filename", "") or "")
    if not filename:
        raise MediaError("Please choose a photo to upload.")
    data = file.read(max_photo_bytes() + 1)
    if not data:
        raise MediaError(f"'{filename}' is empty.")
    if len(data) > max_photo_bytes():
        raise MediaError(
            f"'{filename}' is larger than {_cfg('PHOTO_MAX_MB', 5)} MB. "
            "Please upload a smaller photo.")
    image = _flatten(_open_image(data))
    large = _encode(image, int(_cfg("PHOTO_LARGE_PX", 1600)),
                    int(_cfg("PHOTO_JPEG_QUALITY", 82)))
    thumb = _encode(image, int(_cfg("PHOTO_THUMB_PX", 600)), 78)
    stem = uuid.uuid4().hex
    return {"large": large, "thumb": thumb, "stem": stem}


# ---------------------------------------------------------------------------
# Storage backends
# ---------------------------------------------------------------------------
class LocalStorage:
    name = "local"

    def _folder(self) -> str:
        folder = _cfg("MEDIA_FOLDER")
        os.makedirs(folder, exist_ok=True)
        return folder

    def _rel(self, name: str) -> str:
        """Static-relative key, e.g. 'media/abc.jpg' when inside /static."""
        folder = os.path.normpath(self._folder())
        static_root = os.path.normpath(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"))
        if folder.startswith(static_root):
            rel = os.path.relpath(folder, static_root)
            return (rel.replace(os.sep, "/") + "/" + name).lstrip("./")
        return "media/" + name

    def save(self, name: str, data: bytes) -> str:
        with open(os.path.join(self._folder(), name), "wb") as fh:
            fh.write(data)
        return self._rel(name)

    def url(self, key: str) -> str:
        rel = key.replace("\\", "/")
        if has_app_context():
            from flask import url_for
            return url_for("static", filename=rel)
        return "/static/" + rel.lstrip("/")


class S3Storage:
    name = "s3"

    def __init__(self):
        bucket = _cfg("S3_BUCKET", "")
        if not bucket:
            raise MediaError(
                "MEDIA_BACKEND=s3 but S3_BUCKET is not set. Add the S3_* values "
                "to .env or switch MEDIA_BACKEND back to local.")
        try:
            import boto3
        except ImportError as exc:
            raise MediaError(
                "MEDIA_BACKEND=s3 requires boto3. Install it (pip install boto3) "
                "or switch MEDIA_BACKEND back to local.") from exc
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=_cfg("S3_REGION") or None,
            aws_access_key_id=_cfg("S3_ACCESS_KEY_ID") or None,
            aws_secret_access_key=_cfg("S3_SECRET_ACCESS_KEY") or None,
        )

    def save(self, name: str, data: bytes) -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=name, Body=data, ContentType="image/jpeg",
            CacheControl="public, max-age=31536000",
        )
        return name

    def url(self, key: str) -> str:
        base = (_cfg("S3_PUBLIC_BASE_URL", "") or
                f"https://{self.bucket}.s3.amazonaws.com")
        return base.rstrip("/") + "/" + key.lstrip("/")


class CloudinaryStorage:
    name = "cloudinary"

    def __init__(self):
        if not (_cfg("CLOUDINARY_CLOUD_NAME") and _cfg("CLOUDINARY_API_KEY")
                and _cfg("CLOUDINARY_API_SECRET")):
            raise MediaError(
                "MEDIA_BACKEND=cloudinary but CLOUDINARY_URL (or the "
                "CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET trio) is not set. "
                "Add it to the environment or switch MEDIA_BACKEND back to local.")
        try:
            import cloudinary
            import cloudinary.uploader
        except ImportError as exc:
            raise MediaError(
                "MEDIA_BACKEND=cloudinary requires the cloudinary package. "
                "Install it (pip install cloudinary) or switch MEDIA_BACKEND "
                "back to local.") from exc
        cloudinary.config(
            cloud_name=_cfg("CLOUDINARY_CLOUD_NAME"),
            api_key=_cfg("CLOUDINARY_API_KEY"),
            api_secret=_cfg("CLOUDINARY_API_SECRET"),
            secure=True,
        )
        self._uploader = cloudinary.uploader

    def save(self, name: str, data: bytes) -> str:
        result = self._uploader.upload(
            io.BytesIO(data), public_id=os.path.splitext(name)[0],
            resource_type="image", overwrite=True)
        return result["secure_url"]

    def url(self, key: str) -> str:
        return key


def get_storage():
    backend = str(_cfg("MEDIA_BACKEND", "local") or "local").lower()
    if backend == "s3":
        return S3Storage()
    if backend == "cloudinary":
        return CloudinaryStorage()
    return LocalStorage()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def save_photo(file) -> dict:
    """Validate one upload, store large + thumb, return keys and URLs.

    Raises ``MediaError`` with a message that is safe to show to the user.
    """
    encoded = build_images(file)
    storage = get_storage()
    large_key = storage.save(encoded["stem"] + ".jpg", encoded["large"])
    thumb_key = storage.save(encoded["stem"] + "_thumb.jpg", encoded["thumb"])
    return {
        "key": large_key,
        "thumb_key": thumb_key,
        "url": storage.url(large_key),
        "thumb_url": storage.url(thumb_key),
    }


def save_photos(files, limit=None) -> list:
    """Save every valid file in ``files``; returns the list of saved dicts.

    The caller decides how to report a ``MediaError`` (it always names the
    offending file so the user can fix it).
    """
    limit = max_photos() if limit is None else int(limit)
    saved = []
    for index, file in enumerate(files):
        if index >= limit:
            break
        if not file or not getattr(file, "filename", ""):
            continue
        saved.append(save_photo(file))
    return saved


def thumb_for(key: str) -> str:
    """Thumbnail key for a stored photo ('media/x.jpg' -> 'media/x_thumb.jpg')."""
    key = str(key or "")
    if key.startswith(("http://", "https://")):
        return key
    if key.endswith("_thumb.jpg"):
        return key
    if key.endswith(".jpg"):
        return key[:-4] + "_thumb.jpg"
    return key


def photo_url(key: str) -> str:
    key = str(key or "")
    if key.startswith(("http://", "https://")):
        return key
    return get_storage().url(key)
