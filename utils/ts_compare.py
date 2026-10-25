"""TrustShield return-vs-handover photo comparison (Pillow only, heuristic).

Produces SUGGESTIONS ONLY: similarity, flagged regions, a confidence label and a
side-by-side overlay with red boxes. It NEVER creates a charge or a DamageRecord.
Auto-contrast normalisation means a pure brightness change flags nothing.
"""
import io
from PIL import Image, ImageChops, ImageOps, ImageDraw


def _normalise(path, size):
    img = Image.open(path).convert("L")
    img = ImageOps.autocontrast(img)          # kills pure brightness differences
    return img.resize((size, size))


def _block_means(a, b, grid):
    """Mean absolute per-block difference for a grid x grid partition."""
    pa = a.load()
    pb = b.load()
    size = a.size[0]
    cell = size // grid
    means = []
    for gy in range(grid):
        row = []
        for gx in range(grid):
            total = 0
            n = 0
            for y in range(gy * cell, min((gy + 1) * cell, size)):
                for x in range(gx * cell, min((gx + 1) * cell, size)):
                    total += abs(pa[x, y] - pb[x, y])
                    n += 1
            row.append(total / n if n else 0)
        means.append(row)
    return means, cell


def _merge_regions(flagged, grid, cell, merge_distance=1):
    """Merge neighbouring flagged blocks into bounding-box regions."""
    seen = [[False] * grid for _ in range(grid)]
    regions = []
    stack = []
    for gy in range(grid):
        for gx in range(grid):
            if flagged[gy][gx] and not seen[gy][gx]:
                # BFS over neighbours within merge_distance
                comps = []
                stack.append((gx, gy))
                seen[gy][gx] = True
                while stack:
                    cx, cy = stack.pop()
                    comps.append((cx, cy))
                    for ny in range(max(0, cy - merge_distance), min(grid, cy + merge_distance + 1)):
                        for nx in range(max(0, cx - merge_distance), min(grid, cx + merge_distance + 1)):
                            if flagged[ny][nx] and not seen[ny][nx]:
                                seen[ny][nx] = True
                                stack.append((nx, ny))
                xs = [c[0] for c in comps]
                ys = [c[1] for c in comps]
                regions.append({
                    "x": min(xs) * cell, "y": min(ys) * cell,
                    "w": (max(xs) - min(xs) + 1) * cell,
                    "h": (max(ys) - min(ys) + 1) * cell,
                    "blocks": len(comps),
                })
    return regions


def compare_pair(app, orig_path, ret_path, grid=None, threshold=None,
                 similarity_low=None, similarity_medium=None, merge_distance=1):
    """Compare two images. Returns dict with similarity, regions, confidence,
    overlay_stored_name (saved privately) and needs_manual."""
    import config as _c
    grid = grid or int(_c.TS_GRID_BLOCKS)
    threshold = threshold if threshold is not None else int(_c.TS_BLOCK_DIFF_THRESHOLD)
    sim_low = similarity_low if similarity_low is not None else float(_c.TS_SIMILARITY_LOW)
    sim_med = similarity_medium if similarity_medium is not None else float(_c.TS_SIMILARITY_MEDIUM)

    size = grid * (256 // grid) if grid <= 256 else 256
    size = 256 if size == 0 else size
    cell = size // grid

    a = _normalise(orig_path, size)
    b = _normalise(ret_path, size)
    means, _ = _block_means(a, b, grid)

    flagged = [[means[gy][gx] > threshold for gx in range(grid)] for gy in range(grid)]
    flagged_count = sum(sum(r) for r in flagged)
    total = grid * grid
    similarity = 1.0 - (flagged_count / float(total))
    regions = _merge_regions(flagged, grid, cell, merge_distance)

    if not regions:
        confidence = "high"
    elif similarity < sim_low:
        confidence = "low"
    elif similarity < sim_med:
        confidence = "medium"
    else:
        confidence = "low" if regions else "high"

    overlay_name = _build_overlay(app, orig_path, ret_path, regions, size)
    return {
        "similarity": round(similarity, 4),
        "regions": regions,
        "confidence": confidence,
        "overlay_stored_name": overlay_name,
        "needs_manual": False,
    }


def _build_overlay(app, orig_path, ret_path, regions, size):
    """Save a side-by-side (original | return+red boxes) JPEG privately."""
    orig = Image.open(orig_path).convert("RGB").resize((size, size))
    ret = Image.open(ret_path).convert("RGB").resize((size, size))
    draw = ImageDraw.Draw(ret)
    for r in regions:
        draw.rectangle([r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]],
                       outline=(225, 29, 72), width=3)
    canvas = Image.new("RGB", (size * 2 + 8, size), (255, 255, 255))
    canvas.paste(orig, (0, 0))
    canvas.paste(ret, (size + 8, 0))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=85)
    from utils.ts_evidence import save_bytes
    stored_name, _ = save_bytes(app, buf.getvalue(), suffix=".jpg", kind="overlay")
    return stored_name


def pair_by_angle(handover_files, return_files):
    """Match photos by angle. Returns list of (angle, orig_file, ret_file, missing)."""
    def by_angle(files):
        d = {}
        for f in files:
            if f.kind == "photo":
                d.setdefault(f.angle or "unlabeled", f)
        return d
    ho = by_angle(handover_files)
    rt = by_angle(return_files)
    out = []
    for angle, of in ho.items():
        rf = rt.get(angle)
        out.append((angle, of, rf, rf is None))
    return out


def overlaps_existing(angle, existing_damages):
    """Return the unrepaired existing DamageRecord matching this angle, else None.

    Used so a confirmed change that matches a previously-reported damage is NOT
    attributed to the current renter.
    """
    a = (angle or "").strip().lower()
    for d in existing_damages or []:
        if (getattr(d, "angle", "") or "").strip().lower() == a:
            return d
    return None
