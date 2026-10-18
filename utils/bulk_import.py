"""Bulk-listing import helpers (additive feature).

Stage 1 provides the column model and downloadable CSV/XLSX template builders.
Stage 2 extends this module with file parsing and row validation.

Everything is driven from config.CATEGORIES - nothing about a specific category
is hardcoded here, so books, clothes, tools, ... all work unchanged.
"""
import csv
import io


# --------------------------------------------------------------------------- #
# Column model
# --------------------------------------------------------------------------- #
def category_field_names(cfg, category):
    """Ordered list of the category's dynamic field names from config."""
    cat = cfg["CATEGORIES"].get(category) or {}
    return [f["name"] for f in cat.get("fields", []) if f.get("name")]


def bulk_columns(cfg, category):
    """Full ordered column list: base columns, category fields, extra columns."""
    return (
        list(cfg["BULK_BASE_COLUMNS"])
        + category_field_names(cfg, category)
        + list(cfg["BULK_EXTRA_COLUMNS"])
    )


def example_row(cfg, category, columns):
    """The single example data row that ships inside the template."""
    presets = cfg.get("BULK_TEMPLATE_EXAMPLES", {}).get(category, {})
    row = []
    for col in columns:
        if col in presets:
            row.append(str(presets[col]))
        else:
            row.append("")
    return row


# --------------------------------------------------------------------------- #
# Formula-injection guard (applies to EVERY exported text cell)
# --------------------------------------------------------------------------- #
def csv_safe(value):
    """Prefix a cell that starts with = + - @ with an apostrophe so spreadsheet
    apps treat it as plain text and never execute a formula."""
    s = "" if value is None else str(value)
    if s[:1] in ("=", "+", "-", "@"):
        return "'" + s
    return s


# --------------------------------------------------------------------------- #
# Template builders
# --------------------------------------------------------------------------- #
def build_template_csv(cfg, category):
    """Return the CSV template text (UTF-8, LF line endings) for a category."""
    columns = bulk_columns(cfg, category)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    writer.writerow([csv_safe(v) for v in example_row(cfg, category, columns)])
    return buf.getvalue()


def build_template_xlsx(cfg, category):
    """Return XLSX bytes for a category template (openpyxl)."""
    from openpyxl import Workbook

    columns = bulk_columns(cfg, category)
    wb = Workbook()
    ws = wb.active
    ws.title = (category[:31] or "template")
    ws.append(columns)
    ws.append([csv_safe(v) for v in example_row(cfg, category, columns)])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
