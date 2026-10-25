"""Download the royalty-free Pexels photos used by the demo seed data.

Every listing in the seeded shop gets a real photograph instead of a drawn
illustration. The files live in ``static/seed_images/<category>/<subcat>-<n>.jpg``
and are re-encoded locally (max width 1000 px, JPEG q78) so the repository keeps
a predictable size.

Usage:
    python tools/fetch_seed_photos.py            # download what is missing
    python tools/fetch_seed_photos.py --force    # re-download everything
    python tools/fetch_seed_photos.py --only clothes

Source: Pexels (https://www.pexels.com) under the Pexels License:
free to use, no attribution required, no reselling unmodified copies.
Photo pages are recorded in ``static/seed_images/CREDITS.md``.

The script needs internet access once; ``seed.py`` only reads the files that
already exist, so a fresh clone without network still works (items fall back
to the clean placeholder).
"""
import argparse
import io
import os
import sys
import time
import urllib.error
import urllib.request

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is a hard requirement of the app
    sys.exit("Pillow is required: pip install Pillow")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "static", "seed_images")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
CDN = "https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg"
MAX_WIDTH = 1000
QUALITY = 78

# category -> subcategory prefix -> (subject, [pexels photo ids])
PHOTO_SETS = {
    "clothes": {
        "lehenga": ("Lehenga / bridal Indian wear", [
            32500101, 12762493, 28945134, 12062663, 13001261, 37628622]),
        "saree": ("Saree", [
            35108809, 35108811, 35108856, 35108820, 35108779, 7037125]),
        "sherwani": ("Sherwani / men's ethnic wear", [
            39344096, 34423735, 40341347, 28758558, 35542190]),
        "kurta": ("Kurta", [
            29138637, 34837439, 34423735, 40341347, 28758558, 35542190]),
        "kurta_set": ("Kurta set / salwar suit", [
            14975739, 30809730, 35445207, 35504999, 12279088, 15613165]),
        "western": ("Cocktail / evening dress", [
            26843702, 12476642, 19863391, 38748647, 12279088, 34673508]),
        "frock": ("Kids frock / party dress", [
            38472163, 14803470, 8385866, 8384366, 8384998, 9214908]),
        "blazer": ("Suit / blazer", [
            25460614, 27496865, 25409422, 30953662, 36807010]),
        "anarkali": ("Anarkali dress", [
            18380705, 18380709, 18380706, 34673508, 34602396, 15613165]),
    },
    "books": {
        "default": ("Books and reading", [
            11911071, 14548367, 4219043, 9065298, 35634276, 18698754]),
    },
    "farm_tools": {
        "tractor": ("Tractor", [
            25945334, 32480438, 38614360, 18900461, 33326126, 38693258]),
        "hand_tools": ("Hand tools", [
            7019367, 957090, 175039, 5194861, 12105083, 33074114]),
        "power_tools": ("Power tools / drill", [
            10824759, 30413428, 6790105, 30486981, 34602781, 6790808]),
        "sprayer": ("Crop sprayer", [
            30912665, 17903068, 13253192, 36027197, 19809409, 19809389]),
        "water_tank": ("Irrigation hose and water equipment", [
            13472779, 13688386, 9354300, 127944, 11819645]),
        "default": ("Farm equipment", [
            25945334, 32480438, 38614360, 18900461, 33326126]),
    },
    "electronics": {
        "camera": ("DSLR / mirrorless camera", [
            31667731, 33937881, 33044352, 29442188, 17333517]),
        "laptop": ("Laptop", [
            28225039, 37717006, 17367708, 28225038, 36123568]),
        "projector": ("Projector", [
            34786572, 6062806, 33381191, 3131971, 2507025, 8583821]),
        "speaker": ("Speaker / sound system", [
            33797083, 29617989, 31341733, 34241799, 33080375, 374902]),
        "microphone": ("Microphone", [
            23522931, 20539864, 16085548, 32963775, 17722679, 29233001]),
        "drone": ("Camera drone", [
            38800708, 17382874, 39562811, 30848299, 38584536, 28127213]),
        "console": ("Gaming console", [
            30366460, 39477564, 28920053, 12718841, 28448433, 12719143]),
        "screen": ("LED screen / television", [
            7947955, 4440621, 15467755, 7948010, 6020432, 34153693]),
        "lights": ("String lights", [
            754201, 11774109, 52907, 754262, 236075, 8778857]),
        "generator": ("Portable generator", [
            35042792]),
        "default": ("Consumer electronics", [
            28225039, 37717006, 17367708, 28225038, 36123568]),
    },
    "event_items": {
        "chairs": ("Chairs and event seating", [
            39429559, 39125968, 13241484, 36063995, 31761358, 39390831]),
        "tent": ("Tent / pandal", [
            6324407, 12470606, 28495152, 2398220, 5064887, 40279493]),
        "decoration": ("Wedding and party decoration", [
            39820649, 33485954, 12432503, 31307957, 14395559, 39797465]),
        "festival_items": ("Diya / festival lights", [
            4094847, 18849427, 33360798, 36587820, 38549243, 34641279]),
        "catering": ("Catering / buffet setup", [
            38549537, 38446238, 18281680, 32611690, 7245469, 32689482]),
        "photobooth": ("Photo booth props", [
            2449446, 6519361, 2606402, 6519366, 13788485, 6224606]),
        "default": ("Event equipment", [
            39429559, 39125968, 13241484, 36063995, 31761358]),
    },
    "bikes": {
        "motorcycle": ("Motorcycle", [
            36429479, 36148000, 28970108, 33589965, 28965338, 34440030]),
        "scooter": ("Scooter", [
            39297843, 36189975, 39554975, 38479852, 38542054, 39983315]),
        "bicycle": ("Bicycle", [
            38088169, 37559489, 33217877, 34251789, 36665360, 31636727]),
        "default": ("Two wheeler", [
            36429479, 36148000, 28970108, 33589965, 28965338]),
    },
    "furniture": {
        "default": ("Sofa / living room furniture", [
            18288701, 18559634, 24205168, 37988079, 19814639, 12749678]),
    },
}

CREDITS_HEADER = """# Seed photo credits

Every photo in this folder was downloaded from [Pexels](https://www.pexels.com)
and is used under the [Pexels License](https://www.pexels.com/license/):
free for commercial and non-commercial use, no attribution required, photos may
not be sold unmodified and identifiable people may not be shown in a bad light.

These files are demo seed data only. Owners upload their own photos through the
"Create listing" form; those uploads are stored separately in `static/media/`.

Re-generate the files with `python tools/fetch_seed_photos.py`.

| File | Subject | Source |
| --- | --- | --- |
"""


def _download(pid, retries=3):
    url = CDN.format(pid=pid) + "?auto=compress&cs=tinysrgb&w=1200"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=40) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"download failed for {pid}: {last}")


def _encode(raw):
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGB")
    if img.width > MAX_WIDTH:
        height = round(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, height), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=QUALITY, optimize=True, progressive=True)
    return out.getvalue()


def fetch(force=False, only=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    credits = []
    saved = skipped = failed = 0

    for category, sets in PHOTO_SETS.items():
        selected = not only or only.lower() == category.lower()
        folder = os.path.join(OUT_DIR, category)
        if selected:
            os.makedirs(folder, exist_ok=True)
        for prefix, (subject, ids) in sets.items():
            for index, pid in enumerate(ids, start=1):
                name = f"{prefix}-{index}.jpg"
                path = os.path.join(folder, name)
                rel = f"{category}/{name}"
                # Credits always cover every category, even a --only run.
                credits.append((rel, subject, pid))
                if not selected:
                    continue
                if os.path.isfile(path) and not force:
                    skipped += 1
                    continue
                try:
                    data = _encode(_download(pid))
                    with open(path, "wb") as fh:
                        fh.write(data)
                    saved += 1
                    print(f"  ok   {rel:<28} <- {pid} ({len(data) // 1024} KB)")
                except Exception as exc:  # keep going, report at the end
                    failed += 1
                    print(f"  FAIL {rel:<28} <- {pid}: {exc}")

    lines = [CREDITS_HEADER]
    for rel, subject, pid in credits:
        # A few Pexels ids expire; only credit the files that really exist.
        if not os.path.isfile(os.path.join(OUT_DIR, rel.replace("/", os.sep))):
            continue
        page = f"https://www.pexels.com/photo/{pid}/"
        lines.append(f"| `{rel}` | {subject} | [Pexels {pid}]({page}) |\n")
    with open(os.path.join(OUT_DIR, "CREDITS.md"), "w", encoding="utf-8") as fh:
        fh.write("".join(lines))

    print(f"\nSaved {saved}, skipped {skipped}, failed {failed}.")
    print(f"Photos:  {OUT_DIR}")
    print(f"Credits: {os.path.join(OUT_DIR, 'CREDITS.md')}")
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    parser.add_argument("--only", help="only this category (clothes, books, ...)")
    args = parser.parse_args()
    failed = fetch(force=args.force, only=args.only)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
