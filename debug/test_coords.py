import sys
from extractors.pdf_to_text import extract_lines_with_coords

for pdf in sys.argv[1:]:
    print(f"\n--- {pdf} ---")
    pages = extract_lines_with_coords(pdf)
    for i, line in enumerate(pages[0]):
        text = " ".join(w["text"] for w in line)
        top = min(w["top"] for w in line)
        bottom = max(w["bottom"] for w in line)
        if 450 <= top <= 600:
            print(f"[{i}] top={top:.1f} bot={bottom:.1f}: {text}")
