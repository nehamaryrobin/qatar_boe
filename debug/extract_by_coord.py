import argparse
import sys
from pathlib import Path

# Add project root to Python search path so modules can be imported correctly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from extractors.pdf_to_text import extract_words_with_coords

def main():
    parser = argparse.ArgumentParser(description="Extract lines from a BOE PDF exactly as seen by line_item_extraction.py.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file to extract.")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not Path(pdf_path).exists():
        print(f"Error: File '{pdf_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing PDF: {pdf_path}...\n")
    try:
        pages_words = extract_words_with_coords(pdf_path)
        print(f"Successfully processed {len(pages_words)} page(s).\n")
        
        for page_no, words in enumerate(pages_words, start=1):
            print(f"=== PAGE {page_no} ===")
            if not words:
                print("(No words found on this page)")
                print("=" * 15 + "\n")
                continue
            
            # Filter out vertical sidebar letters/words on the left margin (typically x0 <= 10.0)
            filtered_words = [w for w in words if w["x0"] > 10.0]
            if not filtered_words:
                print("(No words after left-margin filtering on this page)")
                print("=" * 15 + "\n")
                continue
            
            sorted_words = sorted(filtered_words, key=lambda w: w["top"])
            row_groups = []
            current_row = [sorted_words[0]]
            
            for w in sorted_words[1:]:
                if abs(w["top"] - current_row[0]["top"]) <= 9: # Y-Tolerance
                    current_row.append(w)
                else:
                    row_groups.append(current_row)
                    current_row = [w]
            if current_row:
                row_groups.append(current_row)

            for row in row_groups:
                # Reconstruct the line preserving wide visual gaps (needed for regex spaces)
                sorted_row = sorted(row, key=lambda w: w["x0"])
                line_parts = []
                for idx, w in enumerate(sorted_row):
                    if idx > 0:
                        gap = w["x0"] - sorted_row[idx - 1]["x1"]
                        # If gap > 15, we insert 4 spaces, otherwise a single space
                        spacing = "    " if gap > 15 else " "
                        line_parts.append(spacing)
                    line_parts.append(w["text"])
                row_str = "".join(line_parts).strip()
                if row_str:
                    print(row_str)
            print("=" * 15 + "\n")

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
