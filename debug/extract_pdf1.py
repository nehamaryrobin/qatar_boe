import argparse
import sys
from pathlib import Path

# Add project root to Python search path so modules can be imported correctly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from extractors.pdf_to_text import extract_pages, NonNativePdfError

def main():
    parser = argparse.ArgumentParser(description="Extract pages from a BOE PDF and print the text.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file to extract.")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not Path(pdf_path).exists():
        print(f"Error: File '{pdf_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting text from: {pdf_path}...\n")
    try:
        pages = extract_pages(pdf_path)
        print(f"Successfully extracted {len(pages)} page(s).\n")
        for i, page_text in enumerate(pages, start=1):
            print(f"=== PAGE {i} ===")
            print(page_text)
            print("=" * 15 + "\n")

    except NonNativePdfError as e:
        print(f"Error: PDF appears to be non-native/scanned: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
