"""TrustShield private evidence storage.

Photos/videos are stored OUTSIDE static/, under instance/evidence, with random
uuid names. Images are re-encoded by Pillow (strips EXIF/GPS) and resized to
EVIDENCE_MAX_DIMENSION. Videos are checked by extension, size and signature.
Files are only ever served through GET /evidence/<id> (see routes/trustshield.py).
"""
import os
import io
import uuid

from PIL import Image, UnidentifiedImageError


# Common video container signatures (first bytes).
def _video_signature_ok(head: bytes, ext: str) -> bool:
    if ext in ("mp4", "m4v", "mov"):
        return head[4:8] == b"ftyp" or head[:4] == b"\x00\x00\x00\x18"
    if ext in ("mkv", "webm"):
        return head[:4] == b"\x1a\x45\xdf\xa3"          # EBML header
    if ext == "avi":
        return head[:4] == b"RIFF" and head[8:12] == b"AVI "
    return False


def evidence_root(app) -> str:
    """Return (and create) the private evidence directory for this app."""
    path = os.path.join(app.instance_path, "evidence")
    os.makedirs(path, exist_ok=True)
    return path


def _full_path(app, stored_name: str) -> str:
    # stored_name is always a bare uuid.ext (never contains a path separator).
    safe = os.path.basename(stored_name)
    return os.path.join(evidence_root(app), safe)


def save_image(app, file_storage, max_mb=None, kind: str = "photo"):
    """Validate + re-encode + resize an image. Returns (stored_name, size_bytes).

    Raises ValueError for empty / unreadable / oversize / non-image files.
    """
    from config import EVIDENCE_MAX_DIMENSION

    data = file_storage.read() if hasattr(file_storage, "read") else file_storage
    if isinstance(data, str):
        data = data.encode("utf-8", "ignore")
    if not data:
        raise ValueError("Empty file.")
    if max_mb and len(data) > max_mb * 1024 * 1024:
        raise ValueError("File is too large.")

    # Verify it really is an image (rejects a text file renamed .jpg).
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("File is not a valid image.")

    # Re-open (verify() invalidates the object) and re-encode to strip EXIF/GPS.
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    # Resize longest side to <= EVIDENCE_MAX_DIMENSION.
    max_dim = int(EVIDENCE_MAX_DIMENSION)
    w, h = img.size
    scale = min(1.0, max_dim / float(max(w, h) or 1))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)   # no exif passed -> metadata stripped
    payload = out.getvalue()

    stored_name = f"{kind}_{uuid.uuid4().hex}.jpg"
    dest = _full_path(app, stored_name)
    with open(dest, "wb") as fh:
        fh.write(payload)
    return stored_name, len(payload)


def save_video(app, file_storage, max_mb=None, allowed_exts=("mp4", "mov", "mkv", "webm", "avi"),
               kind: str = "video"):
    """Validate + store a video by extension, size and signature. Returns
    (stored_name, size_bytes). Raises ValueError otherwise."""
    raw_name = getattr(file_storage, "filename", "") or ""
    ext = raw_name.rsplit(".", 1)[1].lower() if "." in raw_name else ""
    if ext not in allowed_exts:
        raise ValueError("Video must be one of: " + ", ".join(allowed_exts))

    data = file_storage.read() if hasattr(file_storage, "read") else file_storage
    if isinstance(data, str):
        data = data.encode("utf-8", "ignore")
    if not data:
        raise ValueError("Empty file.")
    if max_mb and len(data) > max_mb * 1024 * 1024:
        raise ValueError("Video is too large.")
    if not _video_signature_ok(data[:12], ext):
        raise ValueError("Video file signature does not match its extension.")

    stored_name = f"{kind}_{uuid.uuid4().hex}.{ext}"
    dest = _full_path(app, stored_name)
    with open(dest, "wb") as fh:
        fh.write(data)
    return stored_name, len(data)


def save_bytes(app, payload: bytes, suffix: str = ".bin", kind: str = "file"):
    """Store arbitrary validated bytes (e.g. a quote PDF) with a random name."""
    stored_name = f"{kind}_{uuid.uuid4().hex}{suffix}"
    dest = _full_path(app, stored_name)
    with open(dest, "wb") as fh:
        fh.write(payload)
    return stored_name, len(payload)


def read_bytes(app, stored_name: str):
    p = _full_path(app, stored_name)
    if not os.path.isfile(p):
        return None
    with open(p, "rb") as fh:
        return fh.read()


def abs_path(app, stored_name: str) -> str:
    return _full_path(app, stored_name)
