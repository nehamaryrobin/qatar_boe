import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from extractors.line_item_extraction import extract_tabular_groups

# ── Field display order ────────────────────────────────────────────────────
_FIELDS = [
    ("ITEM_NO",                       "Item No"),
    ("HS_CODE_22",                    "HS Code"),
    ("GOODS_DESCRIPTION_23",          "Goods Description"),
    ("ORIGIN_24",                     "Origin"),
    ("FOREIGN_VALUE_25",              "Foreign Value"),
    ("CURRENCY_TYPE_26",              "Currency Type"),
    ("CURRENCY_VALUE_27",             "Currency Value"),
    ("CIF_LOCAL_VALUE_28",            "CIF Local Value (QAR)"),
    ("D_RATE_29",                     "D. Rate"),
    ("INCOME_TYPE_30",                "Income Type"),
    ("TOTAL_DUTY_31",                 "Total Duty (QAR)"),
    ("PKG_QTY_32",                    "Package Qty"),
    ("PKG_TYPE_33",                   "Package Type"),
    ("ITEM_QTY_34",                   "Item Qty"),
    ("ITEM_UNIT_35",                  "Unit"),
    ("NET_WEIGHT_36",                 "Net Weight"),
    ("GROSS_WEIGHT_37",               "Gross Weight"),
    ("AIP_NO_37A",                    "AIP No"),
    ("AIP_DUTY_37B",                  "AIP Duty"),
    ("CUSTOMS_RELEASE_REF_41",        "Release Ref"),
    ("CUSTOMS_RESTRICTIONS_AGENCY_40","Agency"),
    ("EXEMPTION_CODE_42",             "Exemption Code"),
]

_KEY_W  = max(len(label) for _, label in _FIELDS) + 2
_SEP    = "─" * 70


def _print_item(item: dict) -> None:
    print(_SEP)
    for key, label in _FIELDS:
        val = item.get(key)
        display = str(val) if val is not None else "—"
        print(f"  {label:<{_KEY_W}} {display}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and display all line items from a Doha BOE PDF."
    )
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: file not found — '{pdf_path}'", file=sys.stderr)
        sys.exit(1)

    filename = pdf_path.name
    print(f"\nExtracting line items from: {pdf_path}\n")

    try:
        items = extract_tabular_groups(str(pdf_path), filename, dec_no="UNKNOWN")
    except Exception as e:
        print(f"Error during extraction: {e}", file=sys.stderr)
        sys.exit(1)

    if not items:
        print("No line items found.")
        return

    print(f"Found {len(items)} line item(s):\n")
    for item in items:
        _print_item(item)
    print(_SEP)
    print(f"\nTotal: {len(items)} item(s)")


if __name__ == "__main__":
    main()
