"""
debug/show_rows.py

Displays the reconstructed text rows for a BOE PDF exactly as they appear
in `all_rows` / `page_rows` inside extract_tabular_groups() — i.e. the
lines that PT1 and PT2 regex matching runs against.

Usage:
    python debug/show_rows.py <pdf_path>
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from extractors.pdf_to_text import extract_words_with_coords


def build_rows(pdf_path: str) -> list[tuple[int, list[str]]]:
    """
    Replicates the row-building step from extract_tabular_groups().
    Returns a list of (page_no, rows) tuples.
    """
    pages_words = extract_words_with_coords(pdf_path)
    result = []

    for page_no, words in enumerate(pages_words, start=1):
        if not words:
            result.append((page_no, []))
            continue

        # Filter left-margin sidebar text (x0 <= 10)
        filtered = [w for w in words if w["x0"] > 10.0]
        if not filtered:
            result.append((page_no, []))
            continue

        sorted_words = sorted(filtered, key=lambda w: w["top"])
        row_groups = []
        current_row = [sorted_words[0]]

        for w in sorted_words[1:]:
            if abs(w["top"] - current_row[0]["top"]) <= 9:   # Y-Tolerance
                current_row.append(w)
            else:
                row_groups.append(current_row)
                current_row = [w]
        if current_row:
            row_groups.append(current_row)

        rows = []
        for row in row_groups:
            sorted_row = sorted(row, key=lambda w: w["x0"])
            parts = []
            for idx, w in enumerate(sorted_row):
                if idx > 0:
                    gap = w["x0"] - sorted_row[idx - 1]["x1"]
                    parts.append("    " if gap > 15 else " ")   # same threshold as extractor
                parts.append(w["text"])
            row_str = "".join(parts).strip()
            if row_str:
                rows.append(row_str)

        result.append((page_no, rows))

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show reconstructed text rows exactly as seen by the line-item extractor."
    )
    parser.add_argument("pdf_path", type=str, help="Path to the BOE PDF file")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: file not found — '{pdf_path}'", file=sys.stderr)
        sys.exit(1)

    pages = build_rows(str(pdf_path))
    total_rows = sum(len(rows) for _, rows in pages)

    print(f"\nFile : {pdf_path}")
    print(f"Pages: {len(pages)}   |   Total rows: {total_rows}\n")

    for page_no, rows in pages:
        print(f"{'═' * 72}")
        print(f"  PAGE {page_no}  ({len(rows)} rows)")
        print(f"{'═' * 72}")
        if not rows:
            print("  (no rows)")
        for idx, row in enumerate(rows):
            print(f"  [{idx:3d}]  {row}")
        print()


if __name__ == "__main__":
    main()
